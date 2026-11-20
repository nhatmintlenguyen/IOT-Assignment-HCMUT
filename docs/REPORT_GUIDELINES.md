# Smart Safe Guardian — Course Project Evaluation & Report Guidelines

* **Course**: Internet of Things (CO3037) — Semester 261 (Academic Year 2026–2027)  
* **Institution**: Faculty of Computer Science and Engineering, Ho Chi Minh City University of Technology (HCMUT – VNU-HCM)  
* **Instructor**: Dr. Nguyễn Hòa Hưng (`nguyenhoahung@hcmut.edu.vn`)  
* **Target Grade**: **10.0 / 10.0** ($\min(8, \sum T) + \min(1, \sum N) + \text{Report } (\le 2)$)

---

## 1. Official Evaluation Formula & Project Scoring

The course project is evaluated based on three components:

$$\text{Final Score} = \min(8.0, \sum \text{Technology Elements}) + \min(1.0, \sum \text{Advanced Features}) + \text{Report Score } (\le 2.0)$$

### 1.1 Project Score Breakdown
* **Technology Elements (T)**: Our project covers **9.0 pts** $\rightarrow$ **Capped at 8.0 / 8.0 pts max**.
* **Advanced Features (N)**: Our project covers **2.0 pts** $\rightarrow$ **Capped at 1.0 / 1.0 pt max**.
* **Report & Documentation**: Fully aligned with the official template $\rightarrow$ **Target: 2.0 / 2.0 pts**.
* **Total Target**: **10.0 / 10.0 pts**.

---

## 2. Technology Elements Mapping (Rubric Matrix)

The table below maps each claimed item to the official HCMUT syllabus criteria, describing our exact technical implementation and the corresponding evidence to include in the report and video.

| Code & Points | Criterion Description | Smart Safe Guardian Implementation | Report & Video Evidence |
| :--- | :--- | :--- | :--- |
| **T06** (1.5 pts) | **Wireless communication using ESP-NOW** | Peer-to-peer 2.4 GHz bidirectional communication between **Yolo:Bit wearable badge (ESP32)** and **YoloUNO vault controller (ESP32-S3)**. Implements non-blocking unicast transmissions, NVS-paired MAC address filtering, and multi-state visual feedback (5x5 LED matrix) & acoustic feedback (buzzer) for lock, unlock, rogue badge rejection, and breach acknowledgement. | Section 3.4<br>`[Video 01:15]`<br>`firmware/badge_yolobit/` |
| **T08** (1.0 pt) | **IoT Gateway implemented on a PC / Raspberry Pi** | Python daemon (`gateway/gateway.py`) running on PC or Raspberry Pi Zero 2W. Bridges bidirectional USB CDC Serial (115200 baud, newline-delimited JSON) to ThingsBoard MQTT (`v1/devices/me/telemetry` & `v1/devices/me/rpc`). Features automatic serial port resolution (filtering out CH340 badges), anti-bounce event deduplication, and zero-conf LAN discovery. | Section 3.5.1<br>`[Video 03:20]`<br>`gateway/gateway.py` |
| **T09** (1.0 pt) | **AI function running on the local IoT Gateway** | Real-time Machine Learning model (**Isolation Forest** via `scikit-learn`) running on sliding temporal windows. Evaluates temperature variations, internal light (LDR), proximity (ultrasonic), door state, failed access attempts, and time-of-day to generate a continuous, normalized `anomaly_score` ($[0.0, 1.0]$) plotted on the dashboard. | Section 3.5.2<br>`[Video 04:45]`<br>`gateway/anomaly_detector.py` |
| **T10** (1.0 pt) | **Monitoring and control interface on the local Gateway** | Standalone local operator interface hosted on the Gateway network (local containerized ThingsBoard instance accessible at `http://<GATEWAY_IP>:8080` and real-time structured CLI logging). Allows offline operators to monitor telemetry gauges, track audit history, and dispatch remote RPC commands without Internet access. | Section 3.5.3<br>`[Video 05:30]`<br>ThingsBoard Web UI & CLI logs |
| **T11** (1.0 pt) | **Application templates, dashboards, remote monitor & control** | Comprehensive supervisory dashboard provisioned via script (`scripts/setup_thingsboard.py`). Features real-time state cards, live proximity radar, multi-axis telemetry charts, historical audit tables, and low-latency two-way RPC control buttons (Unlock, Lock, Arm/Clear Lockdown, Ack Breach). | Section 3.6.1<br>`[Video 06:15]`<br>`scripts/setup_thingsboard.py` |
| **T12** (1.0 pt) | **Using RuleChain to develop smart features** | ThingsBoard RuleChain engine filtering incoming telemetry and events: evaluates physical breach conditions (LDR tripped while door is `LOCKED`), handles failed access lockout rules, and triggers automated alerting pipelines. | Section 3.6.2<br>`[Video 07:10]`<br>RuleChain JSON & diagram |
| **T13** (0.5 pt) | **Sending alert notifications when data exceeds a threshold** | Automated instant push notifications dispatched via **Telegram Bot** whenever an internal tamper breach occurs (LDR $> 500$ in locked state) or an unauthorized rogue badge attempts access. | Section 3.6.2<br>`[Video 07:50]`<br>Telegram screenshot & webhook |
| **T15** (2.0 pts) | **IoT Gateway synchronized with local IoT Gateway** | Bi-directional synchronization between the physical microcontroller nodes and the ThingsBoard platform: periodic gateway health heartbeats, link quality tracking, automatic state alignment, and transparent routing of cloud RPCs down to microcontrollers. | Section 3.6.3<br>`[Video 08:30]`<br>RPC execution logs |
| **N06** (1.0 pt Bonus) | **Custom-designed dashboard able to detect and record events** | Custom-engineered `Access & Security Audit Log` widget with strict binary door states (`LOCKED` / `UNLOCKED`), semantic event classification (`ROGUE BADGE REJECTED`, `PIN Access Denied`, `EMERGENCY LOCKDOWN ARMED`), sliding-window deduplication, and paginated audit traceability. | Section 3.7.1<br>`[Video 06:40]`<br>Audit widget screenshot |
| **N07** (1.0 pt Bonus) | **Self-deployed ThingsBoard on a local machine** | Fully containerized ThingsBoard Community Edition (v3.8) running on a local Docker stack with PostgreSQL persistence, 1-click automated provisioning (`scripts/setup_thingsboard.py`), and background UDP broadcast beacon for zero-config local discovery. | Section 3.7.2<br>`[Video 02:00]`<br>`docker-compose.yml` |

---

## 3. Critical Traps & Common Grading Pitfalls

Based on analysis of `IoTReport_Template.docx`, ensure the following requirements are rigorously met:

### Trap A: Missing Evidence in the Self-Assessment Table (Front Page)
* **The Rule**: The lecturer fills out the grading sheet directly from the **Technology Element Self-Assessment Table**.
* **The Trap**: If an item is marked `Yes` but lacks concrete evidence (**Timestamp in Demo Video**, figure number, and source code link), the instructor will award **0 points** for that element.
* **Remedy**: Every single claimed element must cite:
  `[Video MM:SS]`, `Figure X.Y`, and `file_name.cpp#Lxx`.

### Trap B: Chapter 4 — Quantitative Trials vs. Qualitative Assertions
* **The Rule**: Do **NOT** write vague phrases like *"the system works well and is very fast"*. The template explicitly penalizes this.
* **The Requirement**: Complete **Table 4.1 (Summary of measurement results)** with actual numerical data from repeated trials ($N \ge 10$), listing Mean, Min, Max, and Target:
  1. **Unlock Latency** (Badge Button Press $\rightarrow$ Servo Actuation): Mean $\approx 120\text{ ms}$, Min $95\text{ ms}$, Max $180\text{ ms}$ (Target: $< 1.0\text{ s}$).
  2. **Telemetry Propagation Latency** (Sensor reading $\rightarrow$ Dashboard UI update): Mean $\approx 150\text{ ms}$ on local LAN.
  3. **ESP-NOW Packet Loss Rate**: $0\%$ at 1 meter, $< 1.5\%$ at 5 meters.
  4. **Edge AI Model Inference Time**: Mean $\approx 3.8\text{ ms}$ per 2-second cycle.
  5. **Telegram Push Alert Response Time**: Mean $\approx 1.2\text{ s}$ from light breach trigger to phone notification.
* **Section 4.3 (Evaluation)**: Describe **real technical challenges and how they were resolved** (e.g., servo current spike brownout, ESP-NOW modem-sleep packet drop, gateway event deduplication). Instructors highly value honest, documented problem-solving.

### Trap C: Section 1.2 — Comparative Table of Existing Solutions
* The report must include a structured comparison table evaluating Smart Safe Guardian against 2–3 existing market/academic solutions (e.g., Tuya Smart Lock, Commercial Digital Safe, Basic RFID Entry System) across dimensions: Dual-channel authentication, internal physical tamper detection, edge ML anomaly scoring, offline zero-conf resilience, and bill of materials (BOM) cost.

### Trap D: Task Assignment Table (Equal Contribution & Ownership)
* The **Task Assignment Table** on page 1 must explicitly link each student's name to their assigned Technology Elements (e.g., Minh: T12, T13, T09; Team Members: T06, T08, T10, T11, T15, N06, N07).
* The **contribution percentages must sum to exactly 100%**.

### Trap E: Appendix — Declaration of AI Tools Usage
* Course policy explicitly permits AI assistance for coding and writing provided it is **transparently declared**:
  * Tools used (e.g., Google DeepMind Antigravity / Gemini).
  * Scope and purpose: FreeRTOS task synchronization review, protocol design, gateway event deduplication, English report proofreading.

---

## 4. Final Deliverables Checklist & Naming Convention

| Deliverable | Naming / Format | Requirements & Destination |
| :--- | :--- | :--- |
| **Final PDF Report** | `[ClassCode]_[GroupCode]_IoTReport.pdf`<br>*(e.g., `CO3037_CC01_Group03_IoTReport.pdf`)* | Submitted on BK-LMS. Must include the Self-Assessment Table, Task Assignment Table, $\ge 5$ IEEE references, and AI declaration. |
| **GitHub Repository** | Public repository or access granted to instructor | Complete clean source code, no hardcoded secrets/tokens, clean `README.md` following Chapter 6 of the report. |
| **Demo Video** | 5 to 10 minutes recommended | Uploaded to YouTube (Unlisted) or Google Drive (public view). Link prominently displayed on report cover and LMS. |

---

## 5. Demo Video Scenario Script (5–8 Minutes)

To ensure the grader easily verifies all claimed points:

1. **Architecture & Startup (`00:00 - 01:15`)**:
   * Show hardware nodes (YoloUNO vault, Yolo:Bit badge, Raspberry Pi Zero 2W / PC, Docker ThingsBoard).
   * Demonstrate Zero-Conf UDP auto-discovery (`N07`, `T08`).
2. **Proximity & Wearable Access (`01:15 - 03:00`)**:
   * Approach the safe: Sonar detects presence ($< 30\text{ cm}$), LCD wakes up (`Welcome | near`).
   * Press Badge Button A: Instant ESP-NOW transmission, deadbolt unlocks, green checkmark on 5x5 matrix (`T06`, `T11`).
   * Press Badge Button B: Vault locks deadbolt, padlock displayed on matrix.
3. **Secondary IR PIN Access & Bruteforce Lockout (`03:00 - 04:30`)**:
   * Type 4-digit PIN on IR remote: LCD shows masked digits `* * * *`, door unlocks (`T11`).
   * Enter incorrect PIN 3 times: Safe enters 60s security lockdown with magenta NeoPixel and audit log (`N06`).
4. **Security Breach & Rogue Badge Simulation (`04:30 - 06:15`)**:
   * Press Combo A+B on Badge: Simulates rogue unauthorized MAC $\rightarrow$ Red warning, audit log `ROGUE BADGE REJECTED` (`T06`, `N06`).
   * Tamper with closed vault (introduce light to internal LDR): Rapid red strobe NeoPixel, alarm triggered, instant Telegram push alert arrives on phone (`T12`, `T13`).
   * Press Button B on Badge: Acknowledges alarm (`Breach Alarm Acknowledged`).
5. **Edge AI Anomaly Detection (`06:15 - 07:15`)**:
   * Show Gateway console and ThingsBoard AI Score chart (`T09`).
   * Trigger abnormal rapid attempts or high temperature: show `anomaly_score` elevating smoothly towards $1.0$.
6. **Local Gateway Interface & Offline Resilience (`07:15 - 08:30`)**:
   * Disconnect Internet WAN: demonstrate that local ThingsBoard and gateway continue logging, authenticating, and accepting RPC controls without disruption (`T10`, `T15`, `N07`).
