# Project Blueprint: Smart Safe Guardian (IoT Secure Vault)

---

## 1. Project Overview & Objectives

### 1.1 Executive Summary
**Smart Safe Guardian** is a multi-node, dual-channel IoT security vault designed to safeguard sensitive assets (such as hazardous chemicals, high-value laboratory equipment, or secure servers). The system integrates local wireless access control, multi-sensor environmental and tamper monitoring, edge-level machine learning anomaly detection, on-device emergency web management, and high-availability cloud supervision with offline containerized redundancy.

### 1.2 Core Objectives
* **Contactless & Backup Access**: Authorized personnel request entry via a wearable wireless smart badge (**ESP-NOW** on Yolo:Bit), with an infrared remote keypad as a secondary fallback mechanism.
* **Environmental & Tamper Defense**: Continuous internal climate monitoring (**DHT20**) coupled with an internal optical sensor (**LDR**) that detects physical door breaches when the safe is locked.
* **Edge Anomaly Detection (`T09`)**: A lightweight Machine Learning model (**`scikit-learn` Isolation Forest**) executing on the local Gateway to detect abnormal access hours and anomalous sensor vectors.
* **High-Availability Dual-Redundancy (`N07`)**: Concurrent telemetry streaming and RPC dispatch via a **self-deployed local ThingsBoard CE container** via Docker to guarantee continuous supervision during Internet disruptions.

### 1.3 Technology Element Self-Assessment (Course Rubric Mapping)

The table below maps the official CO3037 course evaluation rubric elements (**T01–T15** and **N01–N07**) to the concrete implementations within the **Smart Safe Guardian** project.

| Technology Code (TE / N) | TE Description (Official HCMUT Rubric) | Implementation & Response in Smart Safe Guardian |
| :--- | :--- | :--- |
| **T06** (1.5 pts) | **Wireless communication using ESP-NOW** | Peer-to-peer 2.4 GHz bidirectional communication between the **Yolo:Bit wearable badge (ESP32)** and the **YoloUNO vault controller (ESP32-S3)**. Implements non-blocking unicast transmissions, NVS-paired MAC address filtering, and multi-state visual feedback (5x5 LED matrix) & acoustic feedback (buzzer) for lock, unlock, rogue badge simulation, and breach acknowledgement. |
| **T08** (1.0 pt) | **IoT Gateway implemented on a PC (or Raspberry Pi)** | Python daemon (`gateway/gateway.py`) executing on PC / Raspberry Pi Zero 2W. Bridges bidirectional USB CDC Serial (115200 baud, newline-delimited JSON) to ThingsBoard MQTT (`v1/devices/me/telemetry` and `v1/devices/me/rpc`). Features automatic port resolution (distinguishing YoloUNO from Badge CH340), anti-bounce deduplication, and zero-configuration UDP discovery. |
| **T09** (1.0 pt) | **AI function running on the local IoT Gateway to analyze data** | Real-time Machine Learning model (**Isolation Forest** via `scikit-learn`) running on sliding temporal windows. Evaluates temperature variations, internal light (LDR), proximity (ultrasonic), door state, failed access attempts, and time-of-day to generate a continuous, normalized `anomaly_score` ($[0.0, 1.0]$) streamed to the cloud dashboard. |
| **T10** (1.0 pt) | **Monitoring and control interface on the local IoT Gateway** | Standalone local operator interface hosted on the Gateway network: an embedded HTTP operator console (`gateway/web_server.py`) running on `http://localhost:5000` with native Server-Sent Events (SSE `/api/stream`), 7 live telemetry cards, 5 hardware control buttons, an interactive serial CLI, and a 2000-line circular log buffer, alongside the containerized ThingsBoard instance on port 8080. Allows offline operators to monitor telemetry, track audit history, and dispatch remote RPC commands without WAN access. |
| **T11** (1.0 pt) | **Application templates, dashboards, and remote monitoring/control** | Comprehensive 24-column Security Operations Center (SOC) dashboard provisioned via script (`scripts/setup_thingsboard.py`) and exported as [`dashboards/smart_safe_dashboard.json`](file:///mnt/Data/Documents/Scolarité/6-HCMUT/261/CO3037%20-%20Internet%20Of%20Things%20Development/Assignment/IOT-Assignment-HCMUT/dashboards/smart_safe_dashboard.json). Features 8 top status cards (size $3\times3$), a 10-column multi-axis telemetry chart with fixed Y-axes (Light 0–1000 ADC, Distance 0–100 cm, Temp 0–50°C, AI Score 0–1.0), a 7-column Access & Security Audit Log, a 7-column RuleChain Alarms table, and a 5-button bottom control bar (Unlock, Lock, Arm/Clear Lockdown, Ack Breach). |
| **T12** (1.0 pt) | **Using RuleChain to develop smart features** | ThingsBoard Root RuleChain automation ([`dashboards/smart_safe_rule_chain.json`](file:///mnt/Data/Documents/Scolarité/6-HCMUT/261/CO3037%20-%20Internet%20Of%20Things%20Development/Assignment/IOT-Assignment-HCMUT/dashboards/smart_safe_rule_chain.json)): filters incoming telemetry and events, evaluates physical breach conditions (LDR $> 500$ in locked state), thermal attack vectors ($T > 35.0^\circ\text{C}$), and Isolation Forest AI anomaly scores ($\ge 0.50$) to create `CRITICAL SECURITY_BREACH` alarms, auto-clearing them upon resolution. |
| **T13** (0.5 pt) | **Sending alert notifications when data exceeds a threshold** | Automated instant push notifications dispatched via **Telegram Bot** ([`@hcmut_iot_bot`](https://t.me/hcmut_iot_bot)): (1) Optical tamper breach alerts (LDR $> 500$ while locked), (2) **Thermal Anomaly - Temperature Alert** state machine (`🔥 HOT` $> 35.0^\circ\text{C}$, `❄️ COLD` $< 20.0^\circ\text{C}$, `✅ NORMAL` return, and startup alert), and (3) Anti-bruteforce lockout warnings upon 3 consecutive failed attempts. |
| **T15** (2.0 pts) | **IoT Gateway synchronized with local IoT Gateway** | Bi-directional synchronization between the physical microcontroller nodes and the ThingsBoard platform: periodic gateway health heartbeats, link quality tracking, automatic state alignment, and transparent routing of cloud RPCs down to microcontrollers. |
| **N06** (1.0 pt - Bonus) | **Custom-designed dashboard able to detect and record events** | Custom-engineered `Access & Security Audit Log` widget with strict binary door states (`LOCKED` / `UNLOCKED`), semantic event classification (`ROGUE BADGE REJECTED`, `PIN Access Denied`, `EMERGENCY LOCKDOWN ARMED`), sliding-window deduplication, and paginated audit traceability. |
| **N07** (1.0 pt - Bonus) | **Self-deployed ThingsBoard on a local machine** | Fully containerized ThingsBoard Community Edition (v3.8) running on a local Docker stack with PostgreSQL persistence, 1-click automated provisioning (`scripts/setup_thingsboard.py`), and background UDP broadcast beacon for zero-config local discovery. |

> **Score Summary**:
> * **Technology Elements (T)**: $\sum = 9.0 \text{ pts} \rightarrow$ **Capped at 8.0 / 8.0 pts max**.
> * **Advanced Features (N)**: $\sum = 2.0 \text{ pts} \rightarrow$ **Capped at 1.0 / 1.0 pt max**.
> * **Target Technical Total**: **9.0 / 9.0 pts** (before the 2.0 pts report).

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
|  - Local Operator Console (T10): Embedded Web UI (HTTP :5000, SSE Live)   |
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
        | - Timer: 30s wait     |       +-----------------------+
        +-----------+-----------+
                    |
              30s Timeout
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
The Gateway executes an **Isolation Forest** machine learning model (`scikit-learn`) on every incoming telemetry frame to detect physical tampering, environmental attacks, and anomalous access vectors in real time.

* **Mathematical Principle**: Isolation Forest builds 100 randomized decision trees (`n_estimators=100`, `contamination=0.02`). Anomalous multi-variable vectors are structurally isolated near the root of the trees (short average path length $h(x)$), whereas nominal operating states require deep partition splits.
* **7-Dimensional Input Vector ($X$)**:
  1. `hour` (0–23): Time of day (flags unauthorized nocturnal access attempts).
  2. `temp` (°C): Ambient DHT20 temperature.
  3. `hum` (%): Ambient DHT20 relative humidity.
  4. `is_unlocked` (0 = `LOCKED`, 1 = `UNLOCKED`): Binary physical door lock state.
  5. `light_adc` (0–4095): Internal optical enclosure sensor (LDR).
  6. `distance_cm` (cm): Ultrasonic proximity radar (HC-SR04).
  7. `is_breach` (0/1): Hardware tamper alarm flag.
* **Feature Normalization**: Centered and scaled via `StandardScaler()` so high-magnitude readings (e.g. ADC 0–4095) do not skew continuous temperature or distance values.
* **Domain Security Rules & Penalties**:
  - **Optical Drill Breach**: Internal light detected ($> 700$ ADC) while door is locked ($+0.80$ penalty).
  - **Thermal Attack Vector**: High heat torch ($T > 36^\circ\text{C}$) or cryogenic liquid nitrogen tamper ($T < 14^\circ\text{C}$).
  - **Moisture Flooding**: Humidity exceeds $85\%$.
* **Scoring & Real-Time Output**: Computes a continuous normalized score ($[0.0, 1.0]$) streamed to ThingsBoard. If $\text{score} \ge 0.50$, an anomaly alert is raised with structured diagnosis (`anomaly_reason`).
* **Empirical Performance**: **96.68% accuracy**, 100.00% precision (0 false alarms on normal baseline), **9.52 ms** edge inference latency (measured over 1,000 trials).
* **Real-World Calibration Protocol**: Features a zero-shot synthetic baseline for immediate cold-start operation; can be re-fitted on real sensor CSV telemetry (`.joblib` persistence) to adapt to laboratory ambient temperature and the physical light-tightness of the safe enclosure.

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
| **Group 4: Local Gateway** | **`T08`**: Gateway on PC aggregating serial data, publishing to CoreIOT, managing RPC<br>**`T09`**: Gateway AI anomaly detection using Scikit-Learn Isolation Forest<br>**`T10`**: Local embedded operator web console on Gateway (HTTP :5000, SSE stream) | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**1.0 / 1.0** |
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
  └── Build local Operator Web Console (`gateway/web_server.py` on port 5000)

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

---

## 8. Hardware Flashing & Execution Guide (PlatformIO)

### 8.1 Prerequisites & PlatformIO Setup
The PlatformIO Core CLI is symlinked into `~/.local/bin/pio` and directly available in your terminal:
```bash
pio --version
# Should output: PlatformIO Core, version 6.2.0 (or higher)
```

### 8.2 Flashing Microcontrollers via Makefile or CLI

#### 1. Central Vault Controller (YoloUNO - ESP32-S3)
Connect the YoloUNO to your computer via USB-C (usually appears as `/dev/ttyACM0`):
```bash
# Standard flash:
make flash-vault

# Flash and immediately open serial monitor in one go:
make flash-vault monitor
# (Or shortcut: make flash-vault-monitor)

# Inspect runtime logs separately (115200 baud):
make monitor-vault
```

#### 2. Wearable Security Badge (Yolo:Bit - ESP32)
Connect the Yolo:Bit via USB (usually appears as `/dev/ttyUSB0`):
```bash
# Standard flash:
make flash-badge

# Flash and immediately open serial monitor in one go:
make flash-badge monitor
# (Or shortcut: make flash-badge-monitor)

# Inspect runtime logs separately (115200 baud):
make monitor-badge
```

### 8.3 Running the Local Gateway (PC / Raspberry Pi Zero 2W)
Once the YoloUNO is connected via USB, launch the Python Gateway bridge:
```bash
# Standard Human-Readable Mode (auto-discovers ThingsBoard):
make run-gateway

# Verbose / Debug Mode (streams raw serial and MQTT payloads):
make run-gateway ARGS="--debug"

# Target a manual IP and custom port:
make run-gateway HOST=192.168.1.50

# Direct execution via virtual environment:
gateway/.venv/bin/python gateway/gateway.py --host auto --debug
```
*Console Output Formats:*
* **Standard Mode**: Displays clean, timestamped human-readable events (`[HH:MM:SS] 🔓 [ACCESS] Door Unlocked via Badge`, `[HH:MM:SS] 📊 [TELEMETRY] ...`, and real-time AI score shifts).
* **Debug Mode (`--debug` / `-v`)**: Shows full raw incoming USB CDC serial packets (`[DEBUG SERIAL RX]`) and outgoing MQTT telemetry/RPC payloads (`[DEBUG MQTT TX]`).

*Port Auto-detection:* The gateway automatically discovers `/dev/ttyACM*` or `/dev/ttyUSB*` ports. To target a specific port:
```bash
gateway/.venv/bin/python gateway/gateway.py --serial-port /dev/ttyACM0 --host auto
```

### 8.4 Standalone Local Embedded Operator Web Console (T10)

The IoT Gateway embeds a zero-dependency, high-performance local operator console powered by Python's standard `ThreadingHTTPServer` (`gateway/web_server.py`), accessible directly on the local network without requiring external web frameworks or cloud connectivity:

* **Console URL**: `http://localhost:5000` (or `http://<GATEWAY_IP>:5000`)
* **Real-Time Streaming**: Native Server-Sent Events (SSE `/api/stream`) broadcasting live telemetry cards and serial events with sub-millisecond response latency.
* **7 Live Operational KPI Cards**: Door lock state, internal temperature, relative humidity, enclosure light ADC, ultrasonic distance radar, AI anomaly score, and emergency lockdown flag.
* **5 Direct Hardware RPC Buttons**: One-click manual triggers to `Unlock Safe`, `Lock Safe`, `Arm Lockdown`, `Clear Lockdown`, and `Acknowledge Alarm`.
* **Interactive Serial CLI**: Execute raw commands directly to the YoloUNO controller from the browser.
* **Circular Rolling Log Buffer**: 2,000-line live terminal buffer with real-time ANSI escape code filtering.
* **CLI Execution Options**:
  ```bash
  # Change web console port (default: 5000):
  gateway/.venv/bin/python gateway/gateway.py --web-port 5050

  # Disable local web server if running in headless background mode:
  gateway/.venv/bin/python gateway/gateway.py --disable-web
  ```

### 8.5 Autonomous Raspberry Pi Zero 2W Deployment
On the Raspberry Pi Zero 2W connected to the YoloUNO via USB:
```bash
# 1. Install and enable the systemd boot service (pulls git and runs gateway automatically):
make setup-rpi-service

# 2. Check live execution logs:
sudo journalctl -u smart-safe-gateway.service -f
```
The script `scripts/rpi_boot_gateway.sh` automatically waits for network, pulls the latest code from `origin/main`, provisions the python environment, and launches the daemon targeting your ThingsBoard server.

### 8.6 Automated System Benchmarks & Metrics (Report Chapter 4)
Smart Safe Guardian includes an automated performance testing and metrics harness (`scripts/system_benchmark.py`) designed to empirically populate **Table 4.1** of the official HCMUT report:

1. **Edge AI Anomaly Detection (`T09`)**: Evaluates the *Isolation Forest* against 2,500 samples (2,000 normal, 500 adversarial attack vectors: optical drill, heat torch, cryogenic freeze, flooding, loitering). Computes Confusion Matrix, Precision, Recall, Specificity, F1, and Inference Latency (< 10 ms).
2. **Gateway Serialization Pipeline (`T08`, `T15`)**: Measures JSON decoding, normalization, and MQTT encoding throughput (frames/sec).
3. **Remote RPC Execution Round-Trip (`T11`, `T15`)**: Measures full lifecycle latency for `unlock`, `lock`, `lockdown`, and `ack_alarm` commands.
4. **Telegram Notification Latency (`T13`)**: Tests real HTTP API round-trip dispatch to Telegram servers.
5. **ESP-NOW RF Reliability (`T06`)**: Analyzes packet delivery ratio (PDR) and effective loss rate with hardware retransmission.

#### Running the Benchmark Suite:
```bash
# Mode A: Software-In-The-Loop (SIL) Simulation (CI / test without hardware):
make benchmark
# Or:
gateway/.venv/bin/python scripts/system_benchmark.py --mock

# Mode B: Live Physical Hardware Testing (when YoloUNO is connected via USB):
make benchmark ARGS="--live"
# Or target a specific port:
gateway/.venv/bin/python scripts/system_benchmark.py --live --port /dev/ttyACM0
```
All measurement results are printed in a clean ASCII table and automatically saved to `docs/benchmark_results.json` for inclusion in the final report.

---

### 8.7 Interactive Telegram Security & Remote Control Bot (T13)

The IoT Gateway integrates an asynchronous, bidirectional Telegram bot daemon connecting administrators directly to the vault perimeter.

* **Official Bot Handle:** [@hcmut_iot_bot](https://t.me/hcmut_iot_bot)
* **Configuration (`.env`):**
  ```ini
  TELEGRAM_TOKEN=your_bot_token_from_botfather
  TELEGRAM_CHAT_ID=1979409784,1252255798  # Comma-separated list for multi-administrator access
  ```

#### 1. Security & Role-Based Access Control (RBAC)
* **Strict Whitelisting:** Only Telegram users whose Chat ID is explicitly registered in `.env` can execute control or diagnostic commands.
* **Unauthorized Access Handling:** Any message or command sent by an unrecognized account (e.g. evaluating instructor or guest) immediately receives an access denial:
  > `⛔ Access Denied - you're not registered as a SmartSafeGuardian Administrator`
* **Automated Security Audit:** Every unauthorized attempt is logged to the Gateway console and recorded directly in ThingsBoard's `Access & Security Audit Log` widget with category `SECURITY`.

#### 2. Interactive Admin Commands
| Command | Action | Audit Log Trace |
| :--- | :--- | :--- |
| `/status` | Returns live sensor readings, lock state, breach alert, and emergency lockdown flag | — |
| `/unlock` | Remotely commands the servo to unlock the vault door | `Door Unlocked (Telegram by <Name>)` |
| `/lock` | Remotely commands the servo to lock the vault door | `Door Locked (Telegram by <Name>)` |
| `/lockdown` | Arms emergency lockdown (forces door locked, ignores physical PINs and badges) | `Emergency Lockdown Armed (Telegram by <Name>)` |
| `/unlockdown` | Disarms emergency lockdown and restores normal physical access | `Emergency Lockdown Cleared (Telegram by <Name>)` |
| `/ack` | Acknowledges active security breach siren and silences buzzer | `Breach Alarm Acknowledged (Telegram by <Name>)` |
| `/id` | Displays caller's Chat ID and administrator authorization status | — |

#### 3. Real-Time Push Notifications (T13)
* **Physical Tamper Breach Alert:** Instant push alert dispatched when the internal LDR detects light in `LOCKED` state (`INTERNAL SENSOR TRIPPED`).
* **Thermal Anomaly - Temperature Alert State Machine:**
  * `🔥 HOT`: High Temperature Warning ($T > 35.0^\circ\text{C}$, suspected thermal drill or fire hazard).
  * `❄️ COLD`: Low Temperature Warning ($T < 20.0^\circ\text{C}$, suspected cryogenic freeze tampering).
  * `✅ NORMAL`: Return to nominal temperature range ($20.0^\circ\text{C} - 35.0^\circ\text{C}$) with green checkmark confirmation.
  * `(System Startup)`: Automatically flagged if the vault boots with abnormal thermal readings.
* **Bruteforce Lockout Alert:** Push alert dispatched when 3 consecutive fraudulent access attempts trigger emergency lockdown.
* **Resolution Clearance:** Instant confirmation dispatched when an authorized operator acknowledges the alarm via Telegram, ThingsBoard dashboard, IR remote, or physical badge.

#### 4. Instant Connectivity Test
Verify Telegram bot credentials and end-to-end delivery across all registered administrators:
```bash
gateway/.venv/bin/python gateway/gateway.py --test-telegram
```

---

### 8.8 Automated Provisioning & Standalone Dashboard/RuleChain Exports (T11, T12)

Smart Safe Guardian provides an end-to-end automated setup script (`scripts/setup_thingsboard.py`) that configures the entire IoT supervision platform in 1 click via REST API:

```bash
# Provision local ThingsBoard CE instance (or CoreIOT Cloud):
gateway/.venv/bin/python scripts/setup_thingsboard.py
```

The script automatically executes:
1. **Tenant & Admin Account Provisioning**: Configures tenant administrator `admin@smartsafeguardian.com`.
2. **Device Registration**: Registers `Smart Safe Guardian` vault device and `Smart Safe Gateway`.
3. **24-Column SOC Dashboard Deployment**: Builds and deploys the balanced Security Operations Center layout (8 top KPI status cards, 10-column multi-axis telemetry chart with fixed Y-axes, 7-column Access Audit Log, 7-column Alarms Table, 5 bottom RPC buttons).
4. **Root RuleChain Automation (T12)**: Injects `Detect Breach & AI Anomaly` (evaluating physical breach, optical LDR $> 500$, thermal attack $> 35.0^\circ\text{C}$, and AI score $\ge 0.50$), `Create Security Alarm` (`CRITICAL SECURITY_BREACH`), and `Check Breach Resolved` $\to$ `Clear Security Alarm`.
5. **Standalone CoreIOT Artifact Exports**:
   * [`dashboards/smart_safe_dashboard.json`](file:///mnt/Data/Documents/Scolarité/6-HCMUT/261/CO3037%20-%20Internet%20Of%20Things%20Development/Assignment/IOT-Assignment-HCMUT/dashboards/smart_safe_dashboard.json): Importable in 1 click into CoreIOT Cloud.
   * [`dashboards/smart_safe_rule_chain.json`](file:///mnt/Data/Documents/Scolarité/6-HCMUT/261/CO3037%20-%20Internet%20Of%20Things%20Development/Assignment/IOT-Assignment-HCMUT/dashboards/smart_safe_rule_chain.json): Standalone Root Rule Chain for CoreIOT Rule Engine import.



