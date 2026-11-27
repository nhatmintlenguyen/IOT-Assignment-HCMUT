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
| **T06** (1.5 pts) | **Wireless communication using ESP-NOW** | Peer-to-peer 2.4 GHz bidirectional communication between the **Yolo:Bit wearable badge (ESP32)** and the **YoloUNO vault controller (ESP32-S3)**. Implements unicast request/response frames (unencrypted, `peer.encrypt = false`), MAC whitelisting through a **mandatory pairing procedure at every boot** (see §4.0), and multi-state visual feedback (5x5 LED matrix) & acoustic feedback (buzzer) for lock, unlock, rogue badge simulation, and breach acknowledgement. |
| **T08** (1.0 pt) | **IoT Gateway implemented on a PC (or Raspberry Pi)** | Python daemon (`gateway/gateway.py`) executing on PC / Raspberry Pi Zero 2W. Bridges bidirectional USB CDC Serial (115200 baud, newline-delimited JSON) to ThingsBoard MQTT (`v1/devices/me/telemetry` and `v1/devices/me/rpc`). Features automatic port resolution (distinguishing YoloUNO from Badge CH340), anti-bounce deduplication, and zero-configuration UDP discovery. |
| **T09** (1.0 pt) | **AI function running on the local IoT Gateway to analyze data** | Two **Isolation Forest** models (`scikit-learn`) evaluate every telemetry frame individually (no temporal window): an *environment model* (time of day, temperature, humidity, door state, internal light, distance, breach flag) and an *access-time model* trained on legitimate openings only. The ML can raise an anomaly **on its own** (e.g. door opened at 03:00 with otherwise normal readings); explicit physical rules add explainable `rule_flags`. Output: `anomaly`, `anomaly_score` ($[0.0, 1.0]$, anomaly $\Leftrightarrow$ score $\ge 0.50$), `ml_score`, `rule_flags`, `anomaly_reason`, streamed to the dashboards. |
| **T10** (1.0 pt) | **Monitoring and control interface on the local IoT Gateway** | Standalone local operator interface hosted on the Gateway network: an embedded HTTP operator console (`gateway/web_server.py`) running on `http://localhost:5000` with native Server-Sent Events (SSE `/api/stream`), 7 live telemetry cards, 5 hardware control buttons, an interactive serial CLI, and a 2000-line circular log buffer, alongside the containerized ThingsBoard instance on port 8080. Allows offline operators to monitor telemetry, track audit history, and dispatch remote RPC commands without WAN access. |
| **T11** (1.0 pt) | **Application templates, dashboards, and remote monitoring/control** | Comprehensive 24-column Security Operations Center (SOC) dashboard provisioned via script (`scripts/setup_thingsboard.py`) and exported as [`dashboards/smart_safe_dashboard.json`](dashboards/smart_safe_dashboard.json). Features 8 top status cards (size $3\times3$), a 10-column multi-axis telemetry chart with fixed Y-axes (Light 0–1000 ADC, Distance 0–100 cm, Temp 0–50°C, AI Score 0–1.0), a 7-column Access & Security Audit Log, a 7-column RuleChain Alarms table, and a 5-button bottom control bar (Unlock, Lock, Arm/Clear Lockdown, Ack Breach). |
| **T12** (1.0 pt) | **Using RuleChain to develop smart features** | ThingsBoard RuleChain automation ([`dashboards/smart_safe_rule_chain.json`](dashboards/smart_safe_rule_chain.json)): filters incoming telemetry and events, evaluates physical breach conditions (LDR $> 500$ in locked state), thermal attack vectors ($T > 35.0^\circ\text{C}$), and Isolation Forest AI anomaly scores ($\ge 0.50$) to create `CRITICAL SECURITY_BREACH` alarms, auto-clearing them upon resolution or acknowledgment. The provisioning script injects these nodes into the tenant's root rule chain; the exported JSON must be set as root (or assigned to the device profile) after import. |
| **T13** (0.5 pt) | **Sending alert notifications when data exceeds a threshold** | Instant push notifications dispatched **by the local Gateway** (`gateway/gateway.py`) via the **Telegram Bot API** ([`@hcmut_iot_bot`](https://t.me/hcmut_iot_bot)) — the RuleChain itself raises dashboard alarms but contains no notification node: (1) Optical tamper breach alerts (LDR $> 500$ while locked), (2) **Thermal Anomaly - Temperature Alert** state machine (`🔥 HOT` $> 35.0^\circ\text{C}$, `❄️ COLD` $< 20.0^\circ\text{C}$, `✅ NORMAL` return, and startup alert), and (3) Anti-bruteforce lockout warnings upon 3 consecutive failed attempts. |
| **T15** (2.0 pts) | **IoT Gateway synchronized with local IoT Gateway** | The local Gateway is connected simultaneously to the self-hosted ThingsBoard and to CoreIOT (`v1/devices/me/telemetry`, `v1/devices/me/rpc`): the same telemetry and audit events are published to both, RPCs are accepted from both and routed to the YoloUNO, and a bounded **store-and-forward buffer** keeps CoreIOT telemetry with its original timestamp while the cloud link is down and replays it on reconnection. A `Smart Safe Gateway` device (gateway flag) receives a heartbeat on the local instance. The ThingsBoard Gateway API (`v1/gateway/*`, sub-devices) is **not** used. |
| **N06** (1.0 pt - Bonus) | **Custom-designed dashboard able to detect and record events** | Custom-designed dashboard with an `Access & Security Audit Log` (ThingsBoard time-series table configured with a custom cell-style function) fed by events that the Gateway detects and classifies (`Rogue Badge Rejected`, `PIN Access Denied`, `Emergency Lockdown Armed`, …) with strict binary door states (`LOCKED` / `UNLOCKED`), 1.5 s duplicate suppression and paginated history. |
| **N07** (1.0 pt - Bonus) | **Self-deployed ThingsBoard on a local machine** | Fully containerized ThingsBoard Community Edition (`thingsboard/tb-node:4.3.1.8`) running on a local Docker stack with PostgreSQL 18 persistence, 1-click automated provisioning (`scripts/setup_thingsboard.py`), and background UDP broadcast beacon for zero-config local discovery. |

> **Score Summary**:
> * **Technology Elements (T)**: $\sum = 9.0 \text{ pts} \rightarrow$ **Capped at 8.0 / 8.0 pts max**.
> * **Advanced Features (N)**: $\sum = 2.0 \text{ pts} \rightarrow$ **Capped at 1.0 / 1.0 pt max**.
> * **Target Technical Total**: **9.0 / 9.0 pts** (before the 2.0 pts report).

---

## 2. Hardware Architecture & Interfaces

For detailed specifications, electrical ratings, voltage compatibility, and anti-brownout recommendations, consult [`HARDWARE.md`](HARDWARE.md).

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
|   - 1602 LCD Display (PCF8574) --------> Grove I2C #2 (Address 0x21)       |
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
|   - FreeRTOS Scheduler Tasks ----------> Watchdog & Dedicated I/O Queues |
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
|  - Telegram Bot (T13): threshold & intrusion alerts, remote commands      |
+--------------------------------------------------------------------------+
                                     |
                                     | MQTT over TCP/IP (v1/devices/me)
                                     v
+--------------------------------------------------------------------------+
|                       CLOUD PLATFORM (CoreIOT Platform)                  |
|  - Dashboards & Telemetry Graphs (T11)                                   |
|  - RuleChain Automated Threshold Logic (T12)                             |
|  - RuleChain CRITICAL alarms shown in the Alarms widget (T12)           |
|  - Remote Administrative RPC Lock/Unlock Triggers (T11)                  |
+--------------------------------------------------------------------------+
```

---

## 3. System Architecture (5-Layer IoT Model)

1. **Perception Layer**: Multi-sensor environment capturing telemetry (DHT20, LDR, Ultrasonic) and user access credentials (IR Receiver, Yolo:Bit buttons).
2. **Transport & Network Layer**:
   * **Local Wireless**: High-speed, connectionless peer-to-peer **ESP-NOW** between Yolo:Bit and YoloUNO.
   * **Host-Controller Bus**: Structured JSON over USB **UART Serial** between YoloUNO and the PC Gateway.
   * **WAN Transport**: **MQTT** (`v1/devices/me/telemetry` & `v1/devices/me/rpc`) over TCP/IP to CoreIOT and the local ThingsBoard broker.
3. **Gateway & Edge Processing Layer**:
   * Python-based Gateway daemon parsing serial frames and maintaining connection state.
   * Local machine learning inference engine executing **Scikit-Learn Isolation Forest** models on every telemetry frame (one frame at a time) to detect multi-variable anomalies.
4. **Cloud / Middleware Layer (CoreIOT + Local Docker ThingsBoard)**:
   * **CoreIOT Platform**: Long-term time-series storage, administrative supervisory dashboard, and RuleChain alarms (Telegram alerts are sent by the Gateway).
   * **Local ThingsBoard Engine (`N07`)**: Containerized instance on `localhost:8080 / 1883` receiving the same telemetry, so local supervision keeps working during Internet outages (CoreIOT telemetry is buffered and replayed on reconnection, up to `COREIOT_BUFFER_SIZE` frames, default 5000 ≈ 2.8 h).
5. **Application / Business Layer**:
   * Real-time access auditing, automated tamper alerting, and compliance logging for hazardous storage.

---

## 4. Operational Workflows & Logic

```
                          +-------------------+
                          |    IDLE / SLEEP   |
                          | (Door Locked)     |
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
        | - Servo rotates to 0° |       | - LCD: PIN INCORRECT  |
        | - NeoPixel turns Green|       | - Badge: red cross    |
        | - LCD: "Unlocked"     |       | - Strike count +1     |
        | - Timer: 30s wait     |       +-----------------------+
        +-----------+-----------+
                    |
              30s Timeout
                    |
                    v
          (Return to IDLE / Lock)
```

### 4.0 Mandatory Badge Pairing (at every boot)
Neither board keeps the pairing after a reboot (both clear their NVS pairing cache at startup), so the badge must be paired each time the vault or the badge restarts:
1. Open a **15 s pairing window** on the vault: press the YoloUNO **BOOT** button, or IR key **E** (requires presence < 30 cm), or send `pair` on the serial console. LCD shows `[PAIRING MODE]`, NeoPixel strobes cyan.
2. On the Yolo:Bit, press **A and B simultaneously and hold ≥ 1.5 s** (a beep and a cyan dot confirm), then release: the badge broadcasts `PAIR_REQ`.
3. The vault stores the badge MAC (`BADGE PAIRED!`), the badge shows a green check then a blue padlock.

⚠️ Until a badge is paired, any badge command is rejected **and counted as a failed attempt** (3 failures → lockdown). Pressing A then B one after the other (not simultaneously) sends `FAKE_BADGE` instead of a pairing request.

### 4.1 Wearable Smart Badge Access (ESP-NOW - `T06`)
1. **Approach Detection**: An approaching operator enters the detection cone (< 30 cm) of the ultrasonic sensor. The LCD wakes up from its cycling telemetry and displays: `"WELCOME / Badge or IR PIN"`.
2. **Instant Wireless Unlock (Button A Short Press)**:
   * The Yolo:Bit transmits a unicast ESP-NOW frame (`"UNLOCK"` + sequence counter). Frames are **not encrypted** and the counter is only echoed back (no replay protection); the vault authorizes the sender by its paired MAC address.
   * YoloUNO validates proximity: if person is near, deadbolt servo rotates to unlocked position (0°), NeoPixel turns **Solid Green**, and LCD pops up `BADGE / Access Granted` for 1.2s before displaying the live 30s unlock countdown (`DOOR UNLOCKED / F: Lock | 30s`).
   * Yolo:Bit matrix plays a two-stage animation: **Green Checkmark (✔)** (400ms, 1500Hz chime) $\to$ **Green Open Padlock (🔓)** (800ms, 2200Hz chime).
3. **Manual Lock (Button B Short Press)**:
   * Sends `"LOCK"` via ESP-NOW. YoloUNO engages the servo deadbolt (180°), and LCD pops up `BADGE / Vault Locked`.
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
1. **PIN Code Entry**: 4-digit numeric code via remote control (default PIN: `1234`; a changed PIN is kept in RAM only and returns to `1234` after a reboot). Keypresses require physical proximity (< 30 cm); remote attempts from a distance display `ACCESS DENIED / Approach first`.
2. **Full Keypad Mapping**:
   * `0`–`9` : Digit entry with masked feedback (`* * * _`).
   * `A` : Backspace last digit / Cancel prompt.
   * `B` : Clear and acknowledge active security breach alarm (`PIN / IR REMOTE / Breach Acked`).
   * `C` : Validate entered PIN code.
   * `D` : Clear entire PIN buffer.
   * `E` : Open the 15 s badge pairing window (see §4.0).
   * `F` : Immediate manual lock when door is open.
   * `▲ / ▼ / ◄ / ►` : Wake the LCD backlight & extend the standby window (pages auto-scroll every 4 s, Welcome screen on proximity).
   * Settings key (`0x15`) : Change PIN (see below).
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
* **Lockdown Recovery**: The lockdown has **no timeout**. It is lifted by an administrator: dashboard button (local ThingsBoard or CoreIOT), Telegram `/unlockdown`, local web console, or serial `lockdown 0`. Lockdown and breach states are held in RAM (a power cycle of the vault clears them).

### 4.4 Tamper & Intrusion Detection
* **Physical Forced Entry**: If the safe door is forced open without prior authentication, the internal LDR optical sensor detects ambient room light while in `LOCKED` state.
* **Instant Alarm & Latching**: Triggered when the LDR reads **≥ 1200 ADC for 3 consecutive samples (200 ms apart)** while locked. The onboard NeoPixel flashes **Strobe Red** (80 ms cycle), the LCD displays `SECURITY BREACH / Waiting for ACK`, and a `breach` event is pushed over UART. If the door is left physically open when the 30 s auto-relock fires, this also raises a breach.
* **Tri-Channel Acknowledgment**: The intrusion state remains persistently latched until explicitly acknowledged via:
  1. Yolo:Bit Badge: Long press Button A (≥ 1 s), or short press Button B (LOCK, which acknowledges an active breach).
  2. IR Remote: Key B or authorized PIN entry.
  3. Cloud / Web: ThingsBoard dashboard button / RPC `ack`.

### 4.5 Transient 1.2s Notification Banners
Every interaction on the safe triggers a high-visibility, 1.2-second LCD status banner clearly identifying the control channel and action result:
* **Badge Actions**: `BADGE / Access Granted`, `BADGE / Vault Locked`, `BADGE / Breach Acked`, `ROGUE BADGE / Access Denied`, `BADGE DENIED / Approach first`.
* **IR Keypad Actions**: `PIN CODE / Access Granted`, `PIN / IR REMOTE / Breach Acked`, `PIN / IR REMOTE / Vault Locked`.
* **Remote Cloud Actions**: `WEB / CLOUD / Access Granted`, `WEB / CLOUD / Vault Locked`, `WEB / CLOUD / Breach Acked`, `WEB / CLOUD / Lockdown ON/OFF`.

### 4.6 Edge AI Anomaly Detection (`T09`)
The Gateway evaluates every incoming telemetry frame (one frame at a time, no temporal window) with two **Isolation Forest** models (`scikit-learn`, `n_estimators=100`) plus explicit physical rules.

* **Principle**: Isolation Forest isolates samples with random axis-aligned splits; outliers need few splits (short path length $h(x)$). Values outside the training range are scored like the most extreme training points, so the baseline uses bell-shaped (sparse-tailed) distributions.
* **Environment model** (`contamination=0.02`) — 7-dimensional input vector $X$:
  1. `hour` (fractional hour of the Gateway clock, e.g. 14.5 = 14:30)
  2. `temp` (°C) and 3. `hum` (%) — DHT20
  4. `is_unlocked` (0 = `LOCKED`, 1 = `UNLOCKED`)
  5. `light_adc` (0–4095) — internal LDR
  6. `distance_cm` — ultrasonic sensor
  7. `is_breach` (0/1) — firmware tamper flag
* **Access-time model** (`contamination=0.01`): trained on legitimate unlocked frames only (opening time ~ $\mathcal{N}(13.5\,h, 2.5\,h)$ truncated to 08:00–20:00). It flags a door opened before ~08:00 or after ~19:30.
* **Training data**: synthetic baseline of 4000 normal frames (80 % locked at any hour, 20 % legitimate accesses), regenerated in ~1 s at every Gateway start. Nothing is persisted to disk; the models are not trained on recorded sensor data.
* **Feature normalization**: `StandardScaler()`.
* **Rule flags** (explainable, each one is an anomaly by itself): `BREACH_FLAG`, `LIGHT_WHILE_LOCKED` (> 700 ADC), `THERMAL_HOT` (> 35 °C), `THERMAL_COLD` (< 14 °C), `HUMIDITY_HIGH` (> 85 %).
* **Scores**: `ml_score` maps the Isolation Forest decision function to $[0, 1]$ with the decision boundary at 0.50; `anomaly_score = max(ml_score, rule score)`; `anomaly` $\Leftrightarrow$ `anomaly_score` $\ge 0.50$ (same threshold as the RuleChain).
* **Evaluation** (`make benchmark`, synthetic test set of 2500 frames: 2000 normal + 500 attack vectors, seed 101): see §8.6 for the exact figures. The test set is synthetic and generated with assumptions close to the training baseline, so these numbers measure consistency, not field performance. The *loitering* vector (person < 9 cm, door locked) is **not detected** by the current model.

### 4.7 Dual Platform Publishing & Offline Buffer (`N07`, `T15`)
* The Gateway Python application publishes MQTT packets simultaneously to:
  1. `app.coreiot.io:1883` (Primary Cloud Dashboard).
  2. The local ThingsBoard Docker container (`THINGSBOARD_HOST`, default auto-discovered via UDP beacon).
* If the Internet link drops, the local ThingsBoard keeps recording (Gateway and Docker host on the same LAN). Telemetry destined for CoreIOT is kept in a bounded in-memory buffer (`COREIOT_BUFFER_SIZE`, default 5000 frames) with its original timestamp (`{"ts": …, "values": …}`) and replayed in order when the connection returns. The buffer is lost if the Gateway process restarts.

### 4.8 Multi-Level Thresholds (why the values differ)
The layers deliberately use different thresholds: the cloud warns early, the AI scores the risk, and the firmware only latches a hardware alarm on a strong, confirmed signal.

| Signal | Level 1 — Cloud early warning (RuleChain, CoreIOT / local TB) | Level 2 — AI rule flag (Gateway) | Level 3 — Hardware latch (YoloUNO firmware) | Telegram (Gateway) |
| :--- | :--- | :--- | :--- | :--- |
| Internal light, door **locked** | `light_adc > 500` → `CRITICAL SECURITY_BREACH` alarm | `> 700` ADC → `LIGHT_WHILE_LOCKED` | `≥ 1200` ADC on **3 consecutive samples** (200 ms) → latched breach (reset of the sample counter below `800`) | on the firmware `breach` event |
| High temperature | `temp > 35.0 °C` → alarm | `> 35.0 °C` → `THERMAL_HOT` | — | `> 35.0 °C` HOT, back to NORMAL at `≤ 33.5 °C` |
| Low temperature | alarm cleared only within 20–35 °C | `< 14.0 °C` → `THERMAL_COLD` | — | `< 20.0 °C` COLD, back to NORMAL at `≥ 21.0 °C` |
| Humidity | — | `> 85 %` → `HUMIDITY_HIGH` | — | — |
| AI score | `anomaly_score ≥ 0.50` → alarm | anomaly ⇔ `anomaly_score ≥ 0.50` | — | — |
| Failed authentications | — | — | 3 consecutive → lockdown (no timeout) | on the firmware `bruteforce_detected` alarm |

Consequence: a light level between 500 and 1199 ADC with the door locked raises a cloud alarm (and an AI flag above 700) without latching the hardware breach, so no Telegram breach alert is sent and the vault LED does not strobe.

---

## 5. Technology Mapping to Course Grading Rubric

| Category | Item Code & Description | Allocated Points |
| :--- | :--- | :---: |
| **Group 3: Local Comms & Interfaces** | **`T06`**: Peer-to-peer wireless communication via ESP-NOW (Yolo:Bit $\leftrightarrow$ YoloUNO) | **1.5 / 1.5** |
| **Group 4: Local Gateway** | **`T08`**: Gateway on PC aggregating serial data, publishing to CoreIOT, managing RPC<br>**`T09`**: Gateway AI anomaly detection using Scikit-Learn Isolation Forest<br>**`T10`**: Local embedded operator web console on Gateway (HTTP :5000, SSE stream) | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**1.0 / 1.0** |
| **Group 5: CoreIOT Platform** | **`T11`**: CoreIOT Dashboards with telemetry gauges and remote RPC unlock switches<br>**`T12`**: RuleChain automated logic for breach and climate threshold detection<br>**`T13`**: Telegram alarm notification on intrusion<br>**`T15`**: IoT Gateway on CoreIOT synchronized with local Gateway (bidirectional RPC & state) | **1.0 / 1.0**<br>**1.0 / 1.0**<br>**0.5 / 0.5**<br>**2.0 / 2.0** |
| **Technology Subtotal** | *Raw points: 9.0 points* $\rightarrow$ **Capped at Maximum** | **8.0 / 8.0** |
| **Official Report** | 6-chapter structure (course report template), self-assessment & task assignment tables, $\ge 5$ academic references | **2.0 / 2.0** |
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
        └── Task 6: FreeRTOS scheduler watchdog & UART telemetry stream

[Phase 2: Local Gateway & Docker (PC)]
  ├── Run ThingsBoard CE via Docker (`docker-compose up -d`)
  ├── Build Python Gateway daemon (`pyserial` + `paho-mqtt` dual publish)
  ├── Implement `scikit-learn` Isolation Forest anomaly detector
  └── Build local Operator Web Console (`gateway/web_server.py` on port 5000)

[Phase 3: CoreIOT & Integration]
  ├── Configure CoreIOT telemetry widgets, status cards, and RPC buttons
  ├── Set up RuleChain alarms (Telegram notifications are sent by the Gateway)
  └── Collect evaluation metrics and record demo video
```

---

## 7. Local ThingsBoard CE Deployment (Docker - `N07`)

The project includes a local ThingsBoard Community Edition environment (`thingsboard/tb-node:4.3.1.8`, overridable with `TB_VERSION`) backed by PostgreSQL 18.

### 7.1 Quickstart Commands

```bash
# First-time full setup (DB schema + start + provisioning of tenant, devices,
# dashboard and rule chain via scripts/setup_thingsboard.py + discovery beacon):
make init-all

# (Equivalent step by step: `make init` then `make setup-thingsboard`)

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
* **Accounts** (values from `.env`):
  * **System Administrator**: `sysadmin@thingsboard.org` / `sysadmin` (ThingsBoard default)
  * **Tenant Administrator** (created by `setup_thingsboard.py`): `admin@smartsafeguardian.com` / `tenant`
  * `tenant@thingsboard.org` only exists if the DB was initialized with `make init LOAD_DEMO=true`.
* **Devices registered by `setup_thingsboard.py`**:
  * `Smart Safe Guardian` — access token `6EzRR6gcTvnOcgVF53hP` (**local demo token only**, not a CoreIOT credential; change `THINGSBOARD_TOKEN` if the instance is reachable from outside your LAN)
  * `Smart Safe Gateway` (gateway flag) — token `GATEWAY_SECRET_TOKEN` (heartbeat link)

### 7.3 Instant Verification (Test Telemetry via curl)

```bash
curl -X POST "http://localhost:8080/api/v1/6EzRR6gcTvnOcgVF53hP/telemetry" \
  -H "Content-Type: application/json" \
  -d '{"temp": 28.5, "hum": 65.2, "light_adc": 140, "distance_cm": 42.0, "state": "LOCKED", "breach": false, "lockdown": false}'
```

---

## 8. Hardware Flashing & Execution Guide (PlatformIO)

### 8.1 Prerequisites & PlatformIO Setup
Install PlatformIO Core if needed (`make install-pio` installs it and links it into `~/.local/bin/pio`), then check:
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

# Target a manual IP (and optionally another MQTT port):
make run-gateway HOST=192.168.1.50 MQTT_PORT=1883

# Direct execution via virtual environment:
gateway/.venv/bin/python gateway/gateway.py --host auto --debug
```
*Console Output Formats:*
* **Standard Mode**: Displays clean, timestamped human-readable events (`[HH:MM:SS] 🔓 [ACCESS] Door Unlocked via Badge`, `[HH:MM:SS] 📊 [TELEMETRY] ...`, and real-time AI score shifts).
* **Debug Mode (`--debug` / `-v`)**: Shows full raw incoming USB CDC serial packets (`[DEBUG SERIAL RX]`) and outgoing MQTT telemetry/RPC payloads (`[DEBUG MQTT TX]`).

*Port Auto-detection:* The gateway automatically discovers `/dev/ttyACM*` or `/dev/ttyUSB*` ports (`SERIAL_PORT=auto` in `.env`). To target a specific port:
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

### 8.6 Benchmarks, Tests & Metrics (Report Chapter 4)
`scripts/system_benchmark.py` produces **Table 4.1**. Every row carries a **Source** label and a computed verdict:

| Source | Meaning |
| :--- | :--- |
| `LIVE` | measured on the physical hardware / real network service |
| `MEASURED` | measured on the machine running the script (AI model on the synthetic test set) |
| `SIMULATED` | statistical simulation — **not a measurement**, no PASS/FAIL verdict |
| `N/A` | not measured in this run |

| Row | Metric | How it is obtained |
| :--- | :--- | :--- |
| 1 | Sensor → dashboard latency | **Not measured** (needs server-side timestamps) → `N/A` |
| 2 | ESP-NOW packet loss | Monte-Carlo **simulation** (1.2 % raw loss, 3 retries) → `SIMULATED` |
| 3–4 | AI accuracy (95 % Wilson CI) / inference latency | 2500-frame synthetic test set (2000 normal + 500 attacks), 1000 inference calls → `MEASURED` |
| 5 | Serial command round-trip (Gateway → YoloUNO → Gateway, USB) | `--live` only, 6 commands → `LIVE` |
| 6 | Telegram API round-trip | 5 × Bot API `getMe` with a real token → `LIVE`; simulated otherwise |

```bash
make benchmark                      # no hardware (default)
make benchmark ARGS="--live"        # YoloUNO connected over USB
gateway/.venv/bin/python scripts/system_benchmark.py --rebuild docs/benchmarks/pi_benchmark_results.json
```
Results are written to `docs/benchmarks/benchmark_results.json`. Historical live runs: `docs/benchmarks/laptop_benchmark_results.json` and `pi_benchmark_results.json` (measured with the first AI model, tables re-computed with `--rebuild`; on the Raspberry Pi Zero 2W the AI inference latency of 71.9 ms **fails** the 10 ms target). `docs/benchmarks/benchmark_comparison.py` draws Figure 4.1 from these two files (measured rows only).

**Current AI model — synthetic test set, host laptop (x86_64):**

| Metric | Value |
| :--- | :--- |
| Confusion matrix | TP = 417, TN = 1994, FP = 6, FN = 83 |
| Accuracy | 96.44 % (95 % CI 95.64 – 97.10) |
| Precision / Recall / F1 | 98.58 % / 83.40 % / 90.36 % |
| Specificity | 99.70 % |
| Detected by | rules only 408, ML + rules 9, ML only 6 (= the 6 false positives) |
| Per attack vector | optical drill 84/84, heat torch 84/84, cryogenic 83/83, flooding 83/83, breach flag 83/83, **loitering 0/83** |
| ML-only scenario (separate: 100 door openings between 20:30 and 07:00, all other readings normal) | 100/100 detected by the ML alone |
| Inference latency | ≈ 6 ms mean on the host laptop; not re-measured on the Raspberry Pi |

**Unit tests (no hardware, no network):**
```bash
gateway/.venv/bin/python -m unittest discover -s tests -v
```
They cover the anomaly detector (ML-only detection, rule flags, score/threshold consistency) and the Gateway offline logic (CoreIOT buffer and replay, `getState` / `getLockdown` RPC, telemetry keys, redaction of tokens and PIN in the web console log).

---

### 8.7 Interactive Telegram Security & Remote Control Bot (T13)

The IoT Gateway integrates an asynchronous, bidirectional Telegram bot daemon connecting administrators directly to the vault perimeter.

* **Official Bot Handle:** [@hcmut_iot_bot](https://t.me/hcmut_iot_bot)
* **Configuration (`.env`):**
  ```ini
  TELEGRAM_TOKEN=your_bot_token_from_botfather
  TELEGRAM_CHAT_ID=<admin_chat_id_1>,<admin_chat_id_2>  # Comma-separated list for multi-administrator access
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
| `/ack` | Acknowledges (clears) the latched security breach alarm | `Breach Alarm Acknowledged (Telegram by <Name>)` |
| `/id` | Displays caller's Chat ID and administrator authorization status | — |

#### 3. Real-Time Push Notifications (T13)
* **Physical Tamper Breach Alert:** Instant push alert dispatched when the internal LDR detects light in `LOCKED` state (`INTERNAL SENSOR TRIPPED`).
* **Thermal Anomaly - Temperature Alert State Machine:**
  * `🔥 HOT`: High Temperature Warning ($T > 35.0^\circ\text{C}$, suspected thermal drill or fire hazard).
  * `❄️ COLD`: Low Temperature Warning ($T < 20.0^\circ\text{C}$, suspected cryogenic freeze tampering).
  * `✅ NORMAL`: Return to nominal temperature range ($20.0^\circ\text{C} - 35.0^\circ\text{C}$) with green checkmark confirmation.
  * `(System Startup)`: Automatically flagged if the vault boots with abnormal thermal readings.
* **Bruteforce Lockout Alert:** Push alert dispatched when 3 consecutive failed attempts trigger the emergency lockdown (active until an administrator clears it).
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
4. **RuleChain Automation (T12)**: Injects into the tenant's root rule chain `Detect Breach & AI Anomaly` (evaluating physical breach, optical LDR $> 500$, thermal attack $> 35.0^\circ\text{C}$, and AI score $\ge 0.50$), `Create Security Alarm` (`CRITICAL SECURITY_BREACH`), and `Check Breach Resolved` $\to$ `Clear Security Alarm`.
5. **Standalone CoreIOT Artifact Exports**:
   * [`dashboards/smart_safe_dashboard.json`](dashboards/smart_safe_dashboard.json): Importable into CoreIOT. The entity alias points to the device ID of the instance it was exported from: after import, edit the alias `Smart Safe Guardian` and select your own device.
   * [`dashboards/smart_safe_rule_chain.json`](dashboards/smart_safe_rule_chain.json): Standalone rule chain for CoreIOT import (set it as root, or assign it to the device profile, after import).

---

## 9. Team & Roles

| Member | GitHub identity | Main responsibilities | Contribution |
| :--- | :--- | :--- | :--- |
| Morel (Pierre) Louis | `Louis Morel` (also `Lumerios`, unified in `.mailmap`) | Gateway (`gateway.py`, Telegram bot, CoreIOT link), Edge AI (`anomaly_detector.py`), local web console, ESP-NOW badge firmware, ThingsBoard provisioning / dashboard / RuleChain, benchmarks, documentation | 50 % |
| Lê Nguyễn Nhật Minh | `nhatminh` | Vault firmware architecture (sensor monitor: DHT20 / LDR / ultrasonic, proximity detection, LCD display, vault state machine), Docker Compose & Makefile base, project proposal | 50 % |

The detailed Task Assignment Table is in the report.
