# Project Blueprint: Smart Safe Guardian (IoT Secure Vault)

---

## 1. Project Overview & Objectives

### 1.1 Executive Summary
**Smart Safe Guardian** is a multi-node, dual-authentication IoT enclosure security system designed to safeguard sensitive assets (such as hazardous chemicals, expensive lab equipment, or secure servers). The system combines local low-power wireless access control, multi-sensor tamper and environmental monitoring, edge-level anomaly detection, and cloud supervision with local failover redundancy.

### 1.2 Core Objectives
* **Contactless & Backup Access**: Allow authorized technicians to request entry via a wearable wireless smart badge (**ESP-NOW**), with an infrared remote keypad as a secondary fallback.
* **Environmental & Tamper Defense**: Continuously monitor internal temperature/humidity (**DHT20**) and detect unauthorized cabinet breaches using an internal optical sensor (**LDR**).
* **Edge Anomaly Detection**: Run a lightweight Machine Learning model (**scikit-learn** or local Small Language Model) on the local Gateway to detect abnormal access patterns and environmental excursions.
* **High-Availability Cloud & Edge Dual-Redundancy**: Stream live telemetry and receive remote RPC commands from **CoreIOT**, backed up by a **self-deployed local ThingsBoard instance** via Docker to guarantee 100% offline operation.

---

## 2. Hardware Architecture & Pinout

```
+--------------------------------------------------------------------------+
|                          WEARABLE BADGE (Yolo:Bit)                       |
|  - ESP32 Processor (ESP-NOW Transmitter)                                 |
|  - Button A: Wireless Unlock Request                                     |
|  - Button B: Emergency Duress / Panic Alarm                              |
|  - 5x5 RGB Matrix: Visual Feedback (Checkmark / Lock Icon)               |
|  - Integrated Buzzer: Welcome Chime & Alert Beeps                        |
+--------------------------------------------------------------------------+
                                     |
                                     | ESP-NOW (2.4 GHz P2P)
                                     v
+--------------------------------------------------------------------------+
|                           VAULT UNIT (YoloUNO - ESP32-S3)                |
|  Inputs:                                                                 |
|   - DHT20 Temp & Humidity Sensor ------> I2C Bus (SDA / SCL)             |
|   - 1602 LCD Display (PCF8574) --------> I2C Bus (Shared SDA / SCL)      |
|   - LDR Internal Light Sensor ---------> Analog ADC                      |
|   - Ultrasonic Distance Sensor --------> 2x Digital GPIOs (Trig / Echo)  |
|   - IR Receiver Module (1838) ---------> 1x Digital GPIO                 |
|  Outputs:                                                                |
|   - MG90 Micro Servo (Deadbolt) -------> PWM (LEDC Channel)              |
|   - Built-in RGB NeoPixel -------------> GPIO 45 (1-Wire Addressable)    |
|   - Built-in Status LED ---------------> GPIO 48 (Heartbeat)             |
+--------------------------------------------------------------------------+
                                     |
                                     | USB Serial (UART @ 115200 baud)
                                     v
+--------------------------------------------------------------------------+
|                      LOCAL IOT GATEWAY (PC / Pi Zero 2 W)                |
|  - Serial Driver: Python `pyserial` bridge                               |
|  - Edge AI: Scikit-Learn Anomaly Detector / Local SLM (T09)              |
|  - Local GUI: Streamlit / Tkinter Dashboard (T10)                        |
|  - Local Cloud: Self-deployed ThingsBoard Community Container (N07)       |
+--------------------------------------------------------------------------+
                                     |
                                     | MQTT over TLS / Wi-Fi
                                     v
+--------------------------------------------------------------------------+
|                       CLOUD PLATFORM (CoreIOT Platform)                  |
|  - Live Dashboards, RuleChain Automation, Telegram Alarms, Remote RPC    |
+--------------------------------------------------------------------------+
```

### Detailed Component Roles:

| Device | Component | Interface / Pin | Functional Role |
| :--- | :--- | :--- | :--- |
| **Yolo:Bit** | **Button A** | Internal GPIO | Triggers instantaneous encrypted unlock token over ESP-NOW. |
| | **Button B** | Internal GPIO | Triggers an immediate silent duress / panic alarm to the vault. |
| | **5×5 LED Matrix** | Internal Matrix | Displays access granted (✔), access denied (✖), or lock icon. |
| | **Buzzer** | Internal Audio | Emits operational feedback (audible confirmation & alert chirps). |
| **YoloUNO** | **DHT20** | I2C (Address `0x38`) | Continuous climate telemetry (heat dissipation and fire warning). |
| | **1602 LCD** | I2C (Address `0x27`/`0x3F`) | Local UI displaying instructions, sensor values, and lock status. |
| | **LDR Light** | Analog ADC | Placed inside the vault. Detects physical door breach when locked. |
| | **Ultrasonic** | Digital GPIOs (Trig/Echo) | Measures user distance (activates UI at \\(< 30\text{ cm}\\)). |
| | **IR Receiver** | Digital GPIO | Captures NEC protocol pulses from the remote control for manual PIN. |
| | **MG90 Servo** | PWM (50 Hz) | Acts as the mechanical door deadbolt (0° = Unlocked, 90° = Locked). |
| | **NeoPixel** | GPIO 45 | Visual beacon: **Green** (Open), **Blue** (Input), **Red** (Locked/Alarm). |
| | **LED** | GPIO 48 | 1 Hz heartbeat indicating FreeRTOS scheduling health. |

---

## 3. System Architecture (5-Layer IoT Model)

1. **Perception Layer**: Multi-sensor environment capturing telemetry (DHT20, LDR, Ultrasonic) and access inputs (IR Receiver, Yolo:Bit buttons).
2. **Transport & Network Layer**:
   * **Local Wireless**: High-speed, connectionless peer-to-peer **ESP-NOW** between Yolo:Bit and YoloUNO.
   * **Host-Controller Bus**: Structured JSON over USB **UART Serial** between YoloUNO and Gateway.
   * **WAN Transport**: **MQTT** (`v1/devices/me/telemetry` & `v1/devices/me/rpc`) over TCP/IP to CoreIOT and the local ThingsBoard broker.
3. **Gateway & Edge Processing Layer**:
   * Python-based Gateway daemon parsing serial frames and maintaining connection state.
   * Local machine learning inference engine executing an **Isolation Forest** or **One-Class SVM** (`scikit-learn`) on continuous telemetry frames to detect multi-variable anomalies.
4. **Cloud / Middleware Layer (CoreIOT + Local Docker ThingsBoard)**:
   * **CoreIOT Platform**: Long-term time-series storage, administrative supervisory dashboard, and RuleChain alerting (Telegram bot webhooks).
   * **Local ThingsBoard Engine (`N07`)**: Containerized instance on `localhost:8080 / 1883` receiving mirrored telemetry to guarantee zero data loss during Internet outages.
5. **Application / Business Layer**:
   * Real-time access auditing, automated tamper alerting, and compliance logging for hazardous storage.

---

## 4. Operational Workflows & Logic

```
                          +-------------------+
                          |    IDLE / SLEEP   |
                          | (Door Locked, Red)|
                          +---------+---------+
                                    |
                    Ultrasonic Distance < 30 cm
                                    v
                          +-------------------+
                          |  AWAKE / STANDBY  |
                          | LCD: "Ready..."   |
                          +----+---------+----+
                               |         |
         ESP-NOW Badge Pressed |         | IR Remote Code Entered
                               v         v
                     +-----------------------------+
                     |    AUTHENTICATION CHECK     |
                     +--------------+--------------+
                                    |
                    +---------------+---------------+
                    |                               |
              [Valid Token / PIN]            [Invalid Attempt]
                    |                               |
                    v                               v
        +-----------------------+       +-----------------------+
        |     ACCESS GRANTED    |       |     ACCESS DENIED     |
        | - Servo rotates to 0° |       | - NeoPixel Flashes Red|
        | - NeoPixel turns Green|       | - LCD: "Invalid Code" |
        | - LCD: "Unlocked"     |       | - Strike count +1     |
        | - Timer: 10s wait     |       +-----------------------+
        +-----------+-----------+
                    |
              10s Timeout
                    |
                    v
          (Return to IDLE / Lock)
```

### 4.1 Normal Badge Access (ESP-NOW)
1. **Approach**: A technician approaches within 30 cm. The ultrasonic sensor triggers the LCD to backlight and display: `"Welcome. Present Badge or IR PIN"`.
2. **Transmission**: The technician presses **Button A** on the Yolo:Bit. The badge broadcasts an ESP-NOW payload containing its static authorization token.
3. **Execution**: The YoloUNO validates the token, unlocks the MG90 servo, switches the NeoPixel to **Green**, and sends an unlock log over UART. The Yolo:Bit matrix flashes a **check mark (✔)** and chirps a confirmation tone.
4. **Auto-Relock**: After 10 seconds, the servo swings back to 90°, the NeoPixel returns to **Solid Red**, and the LCD returns to idle.

### 4.2 Backup IR Remote Access
1. If the technician does not have the badge, they enter a 4-digit PIN (e.g., `1-2-3-4`) on the IR remote.
2. The IR task on the YoloUNO decodes the pulses in real time, updating the LCD with masked asterisks (`PIN: * * * *`).
3. If correct, the safe unlocks. If incorrect 3 times, the system enters a 60-second penalty lockout and sends a tamper warning to the Gateway.

### 4.3 Tamper & Intrusion Detection
* **Physical Forced Entry**: If the safe door is forced open without prior authentication, the internal LDR sensor immediately detects ambient room light (\\(> 80\text{ lux}\\)) while the state machine is in `LOCKED` mode.
* **Response**: The onboard NeoPixel flashes **Strobe Red**, the LCD warns `"SECURITY BREACH"`, and the Gateway immediately pushes a critical alarm through the CoreIOT RuleChain, dispatching a Telegram alert.

### 4.4 Edge AI Anomaly Detection (`T09`)
* The Gateway runs a background thread analyzing sliding windows of telemetry (temperature trends, light fluctuations, and rate of failed IR attempts).
* An **Isolation Forest** model evaluates the multivariate vector. If an unexpected combination is detected (e.g., abnormal heat combined with repeated distance-sensor triggers after business hours), the script pushes an `anomaly_score` metric to CoreIOT and flags an early-warning event.

### 4.5 Dual Cloud / Offline Redundancy (`N07`)
* The Gateway Python application publishes MQTT packets simultaneously to:
  1. `app.coreiot.io:1883` (Primary Cloud Dashboard).
  2. `localhost:1883` (Local ThingsBoard Docker Container).
* If the lab Wi-Fi drops, the local ThingsBoard continues recording data without interruption.

---

## 5. Technology Mapping to Course Grading Rubric

| Category | Item Code & Description | Allocated Points |
| :--- | :--- | :---: |
| **Group 1: Sensors** | **`T01`**: Digital I2C sensor integration (DHT20 on shared I2C bus) | **0.5 / 0.5** |
| **Group 3: Local Comms**| **`T06`**: Peer-to-peer wireless communication via ESP-NOW (Yolo:Bit \\(\leftrightarrow\\) YoloUNO) | **1.5 / 1.5** |
| **Group 4: Local Gateway**| **`T08`**: Gateway on PC/Pi Zero aggregating serial data and managing RPC<br>**`T09`**: Gateway AI anomaly detection using scikit-learn<br>**`T10`**: Local graphical dashboard on Gateway (Streamlit / Tkinter) | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**1.0 / 1.0** |
| **Group 5: CoreIOT** | **`T11`**: CoreIOT Dashboards with telemetry charts and RPC unlock buttons<br>**`T12`**: RuleChain automated logic for threshold detection<br>**`T13`**: Telegram / Email alarm notifications<br>**`T14`**: Remote Over-The-Air (OTA) firmware update over Wi-Fi | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**0.5 / 0.5**<br>**2.0 / 2.0** |
| **Technology Subtotal** | *Raw points: 9.5 points* \\(\rightarrow\\) **Capped at Maximum** | **8.0 / 8.0** |
| **Report** | Official 6-chapter structure (`IoTReport_Template.docx`) with \\(\ge 5\\) references | **2.0 / 2.0** |
| **Advanced Feature** | **`N07`**: Self-deployed local ThingsBoard instance via Docker on local machine | **1.0 / 1.0** |
| **Grand Total** | | **10.0 / 10.0** |

---

## 6. Implementation Action Plan

```
[Phase 1: Embedded Nodes]
  ├── Yolo:Bit Firmware: ESP-NOW broadcast on Button A, sound chime, matrix display
  └── YoloUNO Firmware: FreeRTOS architecture
        ├── Task 1: Ultrasonic distance polling
        ├── Task 2: I2C bus reading (DHT20) + ADC LDR reading
        ├── Task 3: IR receiver NEC decoding
        ├── Task 4: ESP-NOW listener callback
        └── Task 5: Actuator state machine (Servo PWM + NeoPixel + LCD)

[Phase 2: Local Gateway & Docker]
  ├── Run ThingsBoard CE via Docker (`docker-compose.yml`)
  ├── Build Python Gateway daemon (`pyserial` + `paho-mqtt`)
  ├── Implement `scikit-learn` Isolation Forest anomaly detector
  └── Build local Streamlit status page

[Phase 3: CoreIOT & Integration]
  ├── Configure CoreIOT telemetry widgets, status cards, and RPC buttons
  ├── Set up RuleChain for Telegram bot breach notifications
  └── Enable OTA update capability
```

