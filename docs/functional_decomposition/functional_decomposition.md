flowchart TB
    classDef root fill:#f1f5f9,stroke:#0f172a,stroke-width:2.5px,color:#0f172a;
    classDef sub1 fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0f172a;
    classDef sub2 fill:#dcfce7,stroke:#059669,stroke-width:2px,color:#0f172a;
    classDef sub3 fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a;
    classDef sub4 fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#0f172a;
    classDef leaf fill:#ffffff,stroke:#94a3b8,stroke-width:1.5px,color:#1e293b;

    Root["<b>SMART SAFE GUARDIAN SYSTEM</b><br/>Functional Decomposition (F01 - F12)"]

    S1["<b>1. Access Control Subsystem</b><br/><i>(F01, F03, F08, F09)</i>"]
    S1_1["<b>Acquisition</b><br/>ESP-NOW Badge & NEC IR Keypad"]
    S1_2["<b>Processing & Auth</b><br/>Proximity (&lt;30cm), NVS MAC & 4-Digit PIN"]
    S1_3["<b>Security Defense</b><br/>3-Strike Anti-Bruteforce Lockdown"]
    S1_4["<b>Actuation & Control</b><br/>Servo Deadbolt (0°/180°) & 30s Auto-Relock"]

    S2["<b>2. Sensing & Tamper Subsystem</b><br/><i>(F02, F09)</i>"]
    S2_1["<b>Acquisition</b><br/>DHT20 (5s), LDR & HC-SR04 (200ms)"]
    S2_2["<b>Signal Processing</b><br/>Jump Filter & Hysteresis (&lt;30 / ≥35cm)"]
    S2_3["<b>Tamper Detection</b><br/>Optical Breach Latch (≥1200 ADC)"]
    S2_4["<b>Local Display</b><br/>LCD 1602 Banners, NeoPixel & Badge Matrix"]

    S3["<b>3. Edge Gateway & AI Subsystem</b><br/><i>(F04, F05, F10, F11)</i>"]
    S3_1["<b>Transmission</b><br/>USB CDC Serial ↔ Dual MQTT Bridge"]
    S3_2["<b>AI Processing (T09)</b><br/>7D Isolation Forest (Anomaly Score 0-1)"]
    S3_3["<b>Local Console (T10)</b><br/>Embedded Web UI (:5000 SSE) & Serial CLI"]
    S3_4["<b>Alerting & Automation</b><br/>Telegram RBAC Bot (T13), UDP Beacon & Systemd"]

    S4["<b>4. Cloud Supervision Subsystem</b><br/><i>(F06, F07, F10)</i>"]
    S4_1["<b>Storage & Audit (N06)</b><br/>Time-Series DB & Deduplicated Audit Log"]
    S4_2["<b>Rule Processing (T12)</b><br/>Root RuleChain Alarms & Auto-Clear"]
    S4_3["<b>SOC Display (T11)</b><br/>24-Col Dashboard, KPI Cards & Multi-Axis Charts"]
    S4_4["<b>Remote Control</b><br/>Admin RPC Dispatch (Unlock / Lock / Ack)"]

    Root --> S1
    Root --> S2
    Root --> S3
    Root --> S4

    S1 --> S1_1 --> S1_2 --> S1_3 --> S1_4
    S2 --> S2_1 --> S2_2 --> S2_3 --> S2_4
    S3 --> S3_1 --> S3_2 --> S3_3 --> S3_4
    S4 --> S4_1 --> S4_2 --> S4_3 --> S4_4

    class Root root;
    class S1 sub1;
    class S2 sub2;
    class S3 sub3;
    class S4 sub4;
    class S1_1,S1_2,S1_3,S1_4,S2_1,S2_2,S2_3,S2_4,S3_1,S3_2,S3_3,S3_4,S4_1,S4_2,S4_3,S4_4 leaf;