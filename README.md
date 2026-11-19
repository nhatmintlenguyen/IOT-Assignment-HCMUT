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
|  - ESP32 Dual-Core (ESP-NOW 2.4 GHz Bidirectional Link)                  |
|  - Button A (Short): Instant Wireless Unlock Request                     |
|  - Button A (Long >= 1s): Acknowledge Security Breach Alarm              |
|  - Button B (Short): Manual Vault Lock Request                           |
|  - Combo A + B: Simulated Rogue / Unauthorized Badge                     |
|  - 5x5 RGB Matrix: Multi-step Pixel Art Feedback:                        |
|      ✔ Checkmark | ✖ Cross | 🔓/🔒 Padlocks | ⚠ Warning | ☠ Skull | ⛔ No-Entry |
|  - Integrated Buzzer: Synthesized Tones, Startup Sweep & Warning Cues    |
+--------------------------------------------------------------------------+
                                     |
                                     | ESP-NOW (2.4 GHz P2P Bidirectional)
                                     v
+--------------------------------------------------------------------------+
|                           VAULT UNIT (YoloUNO - ESP32-S3)                |
|  Inputs (All Grove Plug-and-Play with Non-Blocking I/O):                 |
|   - DHT20 Temp & Humidity Sensor ------> Grove I2C #1 (Address 0x38)     |
|   - 1602 LCD Display (PCF8574) --------> Grove I2C #2 (Address 0x21 / 0x27) |
|   - LDR Internal Light Sensor ---------> Grove Analog A1-A0 (Signal A0)  |
|   - Ultrasonic Distance Sensor --------> Grove Digital D4-D3 (Trig D3, Echo D4) |
|   - IR Receiver Module (1838) ---------> Grove Digital D6-D5 (Signal D5) |
|  Outputs & Security Logic:                                               |
|   - Micro Servo (Deadbolt) ------------> Dedicated GVS Header D11 (GPIO 38) |
|   - Onboard NeoPixel RGB LED ----------> GPIO 45 (Strobe/Magenta/Colors) |
|   - Onboard Status LED (Heartbeat) ----> GPIO 48 (FreeRTOS Watchdog)     |
|   - Anti-Bruteforce Engine ------------> Automatic Lockdown after 3 Strikes |
|   - Dynamic PIN Configuration ---------> IR Key 0x15 State Machine       |
|   - Transient Notification Banners ----> 1.2s LCD Action Banners         |
|  Network & Cloud Interface:                                              |
|   - USB Serial Gateway Stream ---------> Telemetry & Bi-directional RPC  |
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

### 4.1 Wearable Smart Badge Access (ESP-NOW - `T06`)
1. **Approach Detection**: An approaching operator enters the detection cone (< 30 cm) of the ultrasonic sensor. The LCD wakes up from its cycling telemetry and displays: `"WELCOME / Badge or IR PIN"`.
2. **Instant Wireless Unlock (Button A Short Press)**:
   * The Yolo:Bit transmits an encrypted ESP-NOW packet (`"UNLOCK"` with anti-replay sequence counter).
   * YoloUNO validates proximity: if person is near, deadbolt servo rotates to unlocked position (0°), NeoPixel turns **Solid Green**, and LCD pops up `BADGE / Access Granted` for 1.2s before displaying the live 30s unlock countdown (`DOOR UNLOCKED / F: Lock | 30s`).
   * Yolo:Bit matrix plays a two-stage animation: **Green Checkmark (✔)** (400ms, 1500Hz chime) $\to$ **Green Open Padlock (🔓)** (800ms, 2200Hz chime).
3. **Manual Lock (Button B Short Press)**:
   * Sends `"LOCK"` via ESP-NOW. YoloUNO engages the servo deadbolt (90°), and LCD pops up `BADGE / Vault Locked`.
   * Yolo:Bit displays **Green Checkmark (✔)** $\to$ **Blue Closed Padlock (🔒)** (1100Hz tone).
4. **Security Breach Acknowledgment (Button A Long Press >= 1.0s)**:
   * If a security breach alarm is active, holding Button A clears the latched breach and silences alarms. Yolo:Bit displays **Red Warning Triangle (⚠)** $\to$ **Green Checkmark (✔)** with ascending double chime.
   * If no breach is active, Yolo:Bit immediately displays a **Red Cross (✖)** with a refusal buzz.
5. **Rogue / Unauthorized Badge Simulation (Combo A + B)**:
   * Pressing Buttons A and B simultaneously simulates an unauthorized badge (`"FAKE_BADGE"`).
   * YoloUNO logs `ROGUE_BADGE_DETECTED`, counts a failed attempt, and returns `DENIED_UNAUTHORIZED`.
   * Yolo:Bit displays a **Red Cross (✖)** $\to$ **Glowing Bone Skull (☠)** with an ominous low warning buzz (320Hz $\to$ 220Hz).
6. **Auto-Relock Safeguard**: After 30 seconds of inactivity, the deadbolt automatically re-engages and logs an `auto_locked` event.

### 4.2 Backup IR Remote Access & In-Field Management
1. **PIN Code Entry**: 4-digit numeric code via remote control (default factory PIN: `1234`). Keypresses require physical proximity (< 30 cm); remote attempts from a distance display `ACCESS DENIED / Approach first`.
2. **Full Keypad Mapping**:
   * `0`–`9` : Digit entry with masked feedback (`* * * _`).
   * `A` : Backspace last digit / Cancel prompt.
   * `B` : Clear and acknowledge active security breach alarm (`PIN / IR REMOTE / Breach Acked`).
   * `C` : Validate entered PIN code.
   * `D` : Clear entire PIN buffer.
   * `F` : Immediate manual lock when door is open.
   * `▲ / ►` : Next LCD telemetry page.
   * `▼ / ◄` : Previous LCD telemetry page.
3. **Dynamic PIN Modification (Key 0x15 / Settings)**:
   * Operators can change the safe PIN directly on-device without reflashing firmware.
   * Pressing Key `0x15` launches an interactive state machine:
     1. Prompt: `CHANGE PIN? / C:Yes   A:Cancel`
     2. Current PIN challenge: `ENTER OLD PIN` (validated against memory).
     3. New credential definition: `ENTER NEW PIN`.
     4. Confirmation banner: `PIN CHANGED / Success!`.

### 4.3 Anti-Bruteforce Defense & Vault Lockdown
* **Strike Counter**: The system monitors consecutive fraudulent access attempts (wrong IR PIN, wrong old PIN during change, or unauthorized rogue badge).
* **Automatic Lockdown Engagement**: On the **3rd consecutive failure**:
  * YoloUNO immediately locks down: deadbolt is forced shut, NeoPixel switches to **Solid Magenta**, and LCD displays `VAULT LOCKDOWN / Access Disabled`.
  * All physical access (IR keypad and smart badges) is strictly suspended.
  * A critical security alarm is broadcast via UART: `{"type":"alarm","alarm":"bruteforce_detected","action":"lockdown_engaged"}`.
* **Lockdown Recovery**: Lockdown can only be lifted remotely by an administrator via ThingsBoard Cloud / CoreIOT or through the Gateway serial console (`lockdown:0`).

### 4.4 Tamper & Intrusion Detection
* **Physical Forced Entry**: If the safe door is forced open without prior authentication, the internal LDR optical sensor detects ambient room light while in `LOCKED` state.
* **Instant Alarm & Latching**: The onboard NeoPixel flashes an aggressive **Strobe Red** (80ms cycle), the LCD displays `SECURITY BREACH / Waiting for ACK`, and an alarm frame is pushed over UART.
* **Tri-Channel Acknowledgment**: The intrusion state remains persistently latched until explicitly acknowledged via:
  1. Yolo:Bit Badge: Long press Button A (or Button B).
  2. IR Remote: Key B or authorized PIN entry.
  3. Cloud / Web: ThingsBoard dashboard button / RPC `ack`.

### 4.5 Transient 1.2s Notification Banners
Every interaction on the safe triggers a high-visibility, 1.2-second LCD status banner clearly identifying the control channel and action result:
* **Badge Actions**: `BADGE / Access Granted`, `BADGE / Vault Locked`, `BADGE / Breach Acked`, `ROGUE BADGE / Access Denied`, `BADGE DENIED / Approach first`.
* **IR Keypad Actions**: `PIN CODE / Access Granted`, `PIN / IR REMOTE / Breach Acked`, `PIN / IR REMOTE / Vault Locked`.
* **Remote Cloud Actions**: `WEB / CLOUD / Access Granted`, `WEB / CLOUD / Vault Locked`, `WEB / CLOUD / Breach Acked`, `WEB / CLOUD / Lockdown ON/OFF`.

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

---

## 7. Local ThingsBoard CE Deployment (Docker - `N07`)

The project includes a production-ready, local ThingsBoard Community Edition (v4.3) environment backed by PostgreSQL 18.

### 7.1 Quickstart Commands

```bash
# First-time initialization (creates PostgreSQL DB schema and starts services):
make init

# Standard startup (subsequent runs):
make up

# View container logs:
make logs

# Stop containers (preserves all data in Docker volume):
make down
```

### 7.2 Access & Credentials

* **Web UI URL**: [http://localhost:8080](http://localhost:8080)
* **MQTT Broker**: `localhost:1883`
* **Pre-configured Accounts**:
  * **System Administrator**: `sysadmin@thingsboard.org` / `sysadmin`
  * **Tenant Administrator**: `tenant@thingsboard.org` / `tenant`
* **Pre-registered Device**:
  * **Device Name**: `Smart Safe Guardian`
  * **Device Access Token**: `6EzRR6gcTvnOcgVF53hP`

### 7.3 Instant Verification (Test Telemetry via curl)

```bash
curl -X POST "http://localhost:8080/api/v1/6EzRR6gcTvnOcgVF53hP/telemetry" \
  -H "Content-Type: application/json" \
  -d '{"temp": 28.5, "hum": 65.2, "light_adc": 140, "distance_cm": 42.0, "state": "LOCKED", "breach": false, "lockdown": false}'
```
