# Project Blueprint: Smart Safe Guardian (IoT Secure Vault)

---

## 1. Project Overview & Objectives

### 1.1 Executive Summary
**Smart Safe Guardian** is a multi-node, dual-channel IoT security vault designed to safeguard sensitive assets (such as hazardous chemicals, high-value laboratory equipment, or secure servers). The system integrates local wireless access control, multi-sensor environmental and tamper monitoring, edge-level machine learning anomaly detection, on-device emergency web management, and high-availability cloud supervision with offline containerized redundancy.

### 1.2 Core Objectives
* **Contactless & Backup Access**: Authorized personnel request entry via a wearable wireless smart badge (**ESP-NOW** on Yolo:Bit), with an infrared remote keypad as a secondary fallback mechanism.
* **Environmental & Tamper Defense**: Continuous internal climate monitoring (**DHT20**) coupled with an internal optical sensor (**LDR**) that detects physical door breaches when the safe is locked.
* **Emergency On-Device Web Server (`T07`)**: An integrated lightweight HTTP server running on the YoloUNO microcontroller providing a direct local dashboard and manual override portal without external network dependencies.
* **Edge Anomaly Detection (`T09`)**: A lightweight Machine Learning model (**`scikit-learn` Isolation Forest**) executing on the local Gateway to detect abnormal access hours and anomalous sensor vectors.
* **High-Availability Dual-Redundancy (`N07`)**: Concurrent telemetry streaming and RPC dispatch via **CoreIOT** (primary cloud) and a **self-deployed local ThingsBoard CE container** via Docker to guarantee continuous supervision during Internet disruptions.

---

## 2. Hardware Architecture & Interfaces

For detailed specifications, electrical ratings, voltage compatibility, and anti-brownout recommendations, consult [`HARDWARE.md`](file:///home/lumerios/Documents/Scolarité/6-HCMUT/261/CO3037 - Internet Of Things Development/Assignment/IOT-Assignment-HCMUT/HARDWARE.md).

```
+--------------------------------------------------------------------------+
|                          WEARABLE BADGE (Yolo:Bit)                       |
|  - ESP32 Dual-Core (ESP-NOW 2.4 GHz Transmitter)                         |
|  - Button A: Instant Wireless Unlock Request                             |
|  - Button B: Emergency Duress / Panic Silent Alarm                       |
|  - 5x5 RGB Matrix: Visual Feedback (Checkmark ✔ / Cross ✖ / Lock)        |
|  - Integrated Buzzer: Audible Confirmation & Warning Tones               |
+--------------------------------------------------------------------------+
                                     |
                                     | ESP-NOW (2.4 GHz P2P Wireless)
                                     v
+--------------------------------------------------------------------------+
|                           VAULT UNIT (YoloUNO - ESP32-S3)                |
|  Inputs (All Grove Plug-and-Play):                                       |
|   - DHT20 Temp & Humidity Sensor ------> Grove I2C (Address 0x38)        |
|   - 1602 LCD Display (PCF8574) --------> Grove I2C (Address 0x27 / 0x3F) |
|   - LDR Internal Light Sensor ---------> Grove Analog (A0 / ADC1)        |
|   - Ultrasonic Distance Sensor --------> Grove Digital (D2)              |
|   - IR Receiver Module (1838) ---------> Grove Digital (D4)              |
|  Outputs:                                                                |
|   - MG90 Micro Servo (Deadbolt) -------> Dedicated GVS Header (PWM LEDC) |
|   - Onboard NeoPixel RGB LED ----------> GPIO 45 (1-Wire Addressable)    |
|   - Onboard Status LED (Heartbeat) ----> GPIO 48 (FreeRTOS Watchdog)     |
|  Network:                                                                |
|   - Emergency Web Server (T07) --------> HTTP Port 80 (Wi-Fi AP/LAN)     |
+--------------------------------------------------------------------------+
                                     |
                                     | USB Serial CDC (UART @ 115200 baud)
                                     v
+--------------------------------------------------------------------------+
|                         LOCAL IOT GATEWAY (PC / Laptop)                  |
|  - Serial Driver: Python `pyserial` JSON bridge                          |
|  - Edge AI Engine (T09): Scikit-Learn Isolation Forest (Anomaly scoring) |
|  - Local Operator GUI (T10): Streamlit Interactive Dashboard             |
|  - Local Cloud Failover (N07): Containerized ThingsBoard Community CE     |
+--------------------------------------------------------------------------+
                                     |
                                     | MQTT over TCP/IP (v1/devices/me)
                                     v
+--------------------------------------------------------------------------+
|                       CLOUD PLATFORM (CoreIOT Platform)                  |
|  - Dashboards & Telemetry Graphs (T11)                                   |
|  - RuleChain Automated Threshold Logic (T12)                             |
|  - Real-Time Telegram Alarm Webhooks (T13)                               |
|  - Remote Administrative RPC Lock/Unlock Triggers (T11)                  |
+--------------------------------------------------------------------------+
```

---

## 3. System Architecture (5-Layer IoT Model)

1. **Perception Layer**: Multi-sensor environment capturing telemetry (DHT20, LDR, Ultrasonic) and user access credentials (IR Receiver, Yolo:Bit buttons).
2. **Transport & Network Layer**:
   * **Local Wireless**: High-speed, connectionless peer-to-peer **ESP-NOW** between Yolo:Bit and YoloUNO.
   * **Local Web Interface**: Embedded HTTP web server on YoloUNO port 80.
   * **Host-Controller Bus**: Structured JSON over USB **UART Serial** between YoloUNO and the PC Gateway.
   * **WAN Transport**: **MQTT** (`v1/devices/me/telemetry` & `v1/devices/me/rpc`) over TCP/IP to CoreIOT and the local ThingsBoard broker.
3. **Gateway & Edge Processing Layer**:
   * Python-based Gateway daemon parsing serial frames and maintaining connection state.
   * Local machine learning inference engine executing a **Scikit-Learn Isolation Forest** on sliding telemetry windows to detect multi-variable anomalies.
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

### 4.1 Normal Badge Access (ESP-NOW - `T06`)
1. **Approach**: A technician approaches within 30 cm. The ultrasonic sensor triggers the LCD to backlight and display: `"Welcome. Present Badge or IR PIN"`.
2. **Transmission**: The technician presses **Button A** on the Yolo:Bit. The badge broadcasts an ESP-NOW payload containing its authorization token.
3. **Execution**: The YoloUNO validates the token, unlocks the MG90 servo (deadbolt 0°), switches the NeoPixel to **Green**, and sends an unlock log over UART. The Yolo:Bit matrix flashes a **check mark (✔)** and chirps a confirmation tone.
4. **Auto-Relock**: After 10 seconds, the servo swings back to 90°, the NeoPixel returns to **Solid Red**, and the LCD returns to standby.

### 4.2 Backup IR Remote Access
1. If the technician does not have the badge, they enter a 4-digit PIN (e.g., `1-2-3-4`) on the IR remote.
2. The IR task on the YoloUNO decodes the NEC pulses in real time, updating the LCD with masked asterisks (`PIN: * * * *`).
3. If correct, the safe unlocks. If incorrect 3 times, the system enters a 60-second penalty lockout and sends a tamper warning to the Gateway.

### 4.3 Emergency On-Device Web Server (`T07`)
1. In the event of a gateway failure or for local maintenance, an authorized technician connects directly to the YoloUNO local IP / SoftAP.
2. A responsive HTTP dashboard (served directly from the ESP32-S3 Flash memory) displays live temperature, humidity, light levels, and provides a manual "Emergency Unlock / Lock" toggle switch.

### 4.4 Tamper & Intrusion Detection
* **Physical Forced Entry**: If the safe door is forced open without prior authentication, the internal LDR sensor immediately detects ambient room light while the state machine is in `LOCKED` mode.
* **Response**: The onboard NeoPixel flashes **Strobe Red**, the LCD warns `"SECURITY BREACH"`, and the Gateway immediately pushes a critical alarm through the CoreIOT RuleChain (`T12`), dispatching a real-time Telegram alert (`T13`).

### 4.5 Edge AI Anomaly Detection (`T09`)
* The Gateway runs a Python background thread analyzing sliding windows of telemetry (access hour, failed PIN attempts, temperature variations).
* An **Isolation Forest** model evaluates the multi-variable vector. If an unexpected combination is detected (e.g., repeated access attempts at 3:00 AM combined with abnormal temperature rises), the script pushes an `anomaly_score` to CoreIOT and flags an early-warning event.

### 4.6 Dual Cloud / Offline Redundancy (`N07`)
* The Gateway Python application publishes MQTT packets simultaneously to:
  1. `app.coreiot.io:1883` (Primary Cloud Dashboard).
  2. `localhost:1883` (Local ThingsBoard Docker Container).
* If the lab Wi-Fi drops, the local ThingsBoard continues recording data without interruption.

---

## 5. Technology Mapping to Course Grading Rubric

| Category | Item Code & Description | Allocated Points |
| :--- | :--- | :---: |
| **Group 3: Local Comms & Interfaces** | **`T06`**: Peer-to-peer wireless communication via ESP-NOW (Yolo:Bit $\leftrightarrow$ YoloUNO)<br>**`T07`**: On-device web server (self-implemented emergency local portal on YoloUNO) | **1.5 / 1.5**<br>**1.0 / 1.0** |
| **Group 4: Local Gateway** | **`T08`**: Gateway on PC aggregating serial data, publishing to CoreIOT, managing RPC<br>**`T09`**: Gateway AI anomaly detection using Scikit-Learn Isolation Forest<br>**`T10`**: Local graphical dashboard on Gateway (Streamlit) | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**1.0 / 1.0** |
| **Group 5: CoreIOT Platform** | **`T11`**: CoreIOT Dashboards with telemetry gauges and remote RPC unlock switches<br>**`T12`**: RuleChain automated logic for breach and climate threshold detection<br>**`T13`**: Telegram alarm notification on intrusion | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**0.5 / 0.5** |
| **Technology Subtotal** | *Raw points: 8.0 points* $\rightarrow$ **Capped at Maximum** | **8.0 / 8.0** |
| **Official Report** | 6-chapter structure (`IoTReport_Template.docx`), self-assessment & task assignment tables, $\ge 5$ academic references | **2.0 / 2.0** |
| **Advanced Bonus** | **`N07`**: Self-deployed local ThingsBoard instance via Docker (`docker-compose.yml`) | **1.0 / 1.0** |
| **Grand Total** | $\min(8.0, \sum \text{Tech}) + \text{Report} + \min(1.0, \sum \text{Bonus})$ | **10.0 / 10.0** |

---

## 6. Implementation Action Plan

```
[Phase 1: Embedded Nodes Firmware (Yolo:Bit & YoloUNO)]
  ├── Yolo:Bit Firmware: ESP-NOW broadcast on Button A/B, audio chimes, 5x5 matrix
  └── YoloUNO Firmware: FreeRTOS architecture
        ├── Task 1: Ultrasonic distance polling (< 30 cm standby trigger)
        ├── Task 2: Grove I2C bus (DHT20 reading) + ADC LDR reading
        ├── Task 3: IR receiver NEC decoding (4-digit PIN buffer)
        ├── Task 4: ESP-NOW listener callback (token validation)
        ├── Task 5: Actuator state machine (Servo PWM + NeoPixel + LCD 1602)
        └── Task 6: On-device Web Server (HTTP port 80 emergency portal)

[Phase 2: Local Gateway & Docker (PC)]
  ├── Run ThingsBoard CE via Docker (`docker-compose up -d`)
  ├── Build Python Gateway daemon (`pyserial` + `paho-mqtt` dual publish)
  ├── Implement `scikit-learn` Isolation Forest anomaly detector
  └── Build local Streamlit interactive GUI (`streamlit run gateway_app.py`)

[Phase 3: CoreIOT & Integration]
  ├── Configure CoreIOT telemetry widgets, status cards, and RPC buttons
  ├── Set up RuleChain for Telegram bot breach notifications
  └── Collect evaluation metrics and record demo video
```
