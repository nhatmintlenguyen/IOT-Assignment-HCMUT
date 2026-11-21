# Smart Safe Guardian - Telegram Security Alert Setup Guide (T13)

This document describes how Telegram security breach notifications are integrated into the **Smart Safe Guardian** IoT system.

---

## 1. System Architecture Overview

Smart Safe Guardian implements a resilient **Dual-Layer Alert Architecture** designed specifically for self-hosted ThingsBoard deployments:

```text
       ┌──────────────────────────────┐
       │   YoloUNO Vault Controller   │
       │  (LDR Light Sensor + Sonar)  │
       └──────────────┬───────────────┘
                      │ USB Serial CDC
                      ▼
       ┌──────────────────────────────┐
       │     IoT Gateway Daemon       │
       │   (Raspberry Pi / PC Linux)  │
       └──────┬────────────────┬──────┘
              │                │
              │ Layer 1:       │ Layer 2:
              │ Direct Alert   │ MQTT Telemetry
              │ (Debounced)    │ (v1/devices/me/telemetry)
              ▼                ▼
     ┌─────────────────┐ ┌───────────────────────────┐
     │  Telegram API   │ │   ThingsBoard CE Local    │
     │  (@hcmut_iot_   │ │  (Docker container :8080) │
     │      bot)       │ └─────────────┬─────────────┘
     └────────▲────────┘               │
              │                        │ Root Rule Chain
              │ Layer 2 REST Call      │ (Alarm: SECURITY_BREACH)
              └────────────────────────┘
```

* **Layer 1: Gateway Direct Alert (Low Latency & Resilient)**
  * Handled directly by `gateway/gateway.py` in a background daemon thread using Python's standard library `urllib.request`.
  * Triggers instantly as soon as the YoloUNO controller detects a security breach (`breach: true`) while the vault is locked.
  * Features **hardware-level debouncing**: sends exactly **one** alert per breach incident, preventing message flooding when telemetry is streamed every 2 seconds.
  * Dispatches an automatic resolution notice when the alarm is acknowledged by an operator or authorized badge.

* **Layer 2: ThingsBoard Platform Alert (Audit & Rule Engine)**
  * Handled by ThingsBoard Community Edition's Root Rule Chain.
  * Records a persistent `SECURITY_BREACH` alarm with severity `CRITICAL` in the database, displays the event on the web dashboard, and dispatches a REST API call to Telegram.

---

## 2. Credentials & Prerequisites

* **Telegram Bot Username:** `@hcmut_iot_bot`
* **Bot Access Token:** Configured via `TELEGRAM_TOKEN` in `.env`
* **Target Chat ID:** Configured via `TELEGRAM_CHAT_ID` in `.env`

### Quick Connectivity Test via curl
Run the following terminal command to verify that the Telegram API and chat ID are functional:

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_TOKEN>/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id": <CHAT_ID>, "text": "Smart Safe Guardian: Test connection successful!"}'
```

---

## 3. Configuration in `.env`

Configure your credentials in `.env` in the repository root. Ensure `.env` is never committed to Git:

```env
# Telegram Alert Bot Configuration (from @BotFather)
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

Template variables are documented in `.env.example`:

```env
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 4. Layer 1: Gateway Direct Notification

The gateway automatically reads `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` from `.env`.

### Testing Gateway Telegram Connectivity
You can test the bot connection directly from the gateway CLI using the `--test-telegram` flag:

```bash
gateway/.venv/bin/python gateway/gateway.py --test-telegram
```

Expected output:
```text
[SUCCESS] Test message successfully delivered to Telegram chat <CHAT_ID>!
```

### Gateway CLI Options
* `--telegram-token <TOKEN>`: Override Telegram Bot token from CLI.
* `--telegram-chat-id <CHAT_ID>`: Override Telegram Chat ID from CLI.
* `--disable-telegram`: Disables direct Telegram alerts even if tokens are present in `.env`.
* `--test-telegram`: Sends a test message on startup and exits immediately.

### Anti-Spam (Debounce) Behavior
1. When light enters the vault while locked (`breach: true`), the first frame triggers an immediate Telegram alert.
2. Subsequent telemetry frames (streamed every 2 seconds by YoloUNO) are recognized as an active breach and suppressed.
3. When the operator acknowledges the alarm via:
   * ThingsBoard Dashboard (`ack` RPC)
   * Yolo:Bit Badge (Holding Button A for 1 second)
   * Infrared Remote control (`breach_acknowledged`)
   the debouncer resets and an informational confirmation message is sent:
   `SECURITY ALERT RESOLVED`

---

## 5. Layer 2: ThingsBoard Local Rule Chain Setup

For self-hosted ThingsBoard (`http://localhost:8080`), you can set up the rule chain using the node flow below on the **Root Rule Chain**:

#### Node Flow Diagram
```text
[Post telemetry]
       │
       ├─────────────────────────────────────────┐
       ▼ (Success)                               ▼ (Success)
[Filter: Check Breach]                    [Filter: Check Breach Cleared]
       │                                         │
       ▼ (True)                                  ▼ (True)
[Action: Create Alarm]                    [Action: Clear Alarm]
       │
       ▼ (Created)  <--- CRITICAL: Use 'Created' relation to avoid spam
[Transform: Build Telegram Msg]
       │
       ▼ (Success)
[External: REST API Call Telegram]
```

#### Node 1: Filter Script (Check Breach and Locked)
* **Type:** `Filter - script`
* **Name:** `Check Breach and Locked`
* **Script:**
  ```javascript
  return msg.breach === true && (msg.state === "LOCKED" || msg.state === undefined);
  ```

#### Node 2: Action (Create Security Breach Alarm)
* **Type:** `Action - create alarm`
* **Name:** `Create Security Breach Alarm`
* **Alarm Type:** `SECURITY_BREACH`
* **Alarm Severity:** `CRITICAL`
* **Propagate:** `Checked`
* **Alarm Details Builder Script:**
  ```javascript
  var details = {
      light: msg.light_adc,
      temp: msg.temp,
      state: msg.state,
      audit_event: "Security intrusion detected: light breach while locked!"
  };
  return details;
  ```
* **IMPORTANT LINK RELATION:** Connect this node to Node 3 using the relation `Created` (do **NOT** use `Updated`). This guarantees that only one Telegram message is sent when the alarm is first raised.

#### Node 3: Transformation Script (Format Telegram Alert)
* **Type:** `Transformation - script`
* **Name:** `Format Telegram Alert`
* **Script:**
  ```javascript
  var temp = (msg.temp !== undefined && msg.temp !== null) ? Number(msg.temp).toFixed(1) : "N/A";
  var light = (msg.light_adc !== undefined && msg.light_adc !== null) ? msg.light_adc : "N/A";
  var hum = (msg.hum !== undefined && msg.hum !== null) ? Number(msg.hum).toFixed(1) : "N/A";
  var timeStr = new Date().toLocaleString("vi-VN", {timeZone: "Asia/Ho_Chi_Minh"});

  var alertText = "🚨 *SMART SAFE GUARDIAN - SECURITY BREACH!* 🚨\n\n" +
                  "⚠️ *Status:* Intrusion / Light breach detected while LOCKED!\n" +
                  "💡 *Light Sensor (LDR):* " + light + " ADC\n" +
                  "🌡️ *Temperature:* " + temp + " °C\n" +
                  "💧 *Humidity:* " + hum + " %\n" +
                  "⏰ *Timestamp:* " + timeStr + "\n\n" +
                  "👉 _Please inspect the security vault immediately!_";

  var newMsg = {
      chat_id: "<YOUR_CHAT_ID>",
      text: alertText,
      parse_mode: "Markdown"
  };

  return {
      msg: newMsg,
      metadata: metadata,
      msgType: "POST_TELEMETRY_REQUEST"
  };
  ```

#### Node 4: External REST API Call (Send Telegram Alert)
* **Type:** `External - rest api call`
* **Name:** `Send Telegram Bot Alert`
* **Endpoint URL pattern:**
  `https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/sendMessage`
* **Request method:** `POST`
* **Headers:**
  * `Content-Type`: `application/json`

#### Node 5: Filter Script (Check Breach Cleared)
* **Type:** `Filter - script`
* **Name:** `Check Breach Cleared`
* **Script:**
  ```javascript
  return msg.breach === false;
  ```

#### Node 6: Action (Clear Security Breach Alarm)
* **Type:** `Action - clear alarm`
* **Name:** `Clear Security Breach Alarm`
* **Alarm Type:** `SECURITY_BREACH`

---

## 6. End-to-End Testing & Verification Checklist

| Step | Action | Expected Result | Verified |
| :--- | :--- | :--- | :---: |
| **1. Bot Healthcheck** | Run `gateway/.venv/bin/python gateway/gateway.py --test-telegram` | "Test message successfully delivered" in terminal and message received on phone. | ✅ |
| **2. Mock Intrusion Test** | Run `gateway/.venv/bin/python gateway/gateway.py --mock` | Gateway connects and indicates `Telegram Bot Alert: ENABLED`. | ✅ |
| **3. Hardware Intrusion Test** | Shine flashlight onto internal LDR while vault is in `LOCKED` state. | YoloUNO triggers buzzer/red LED, Gateway displays `[ALARM]`, and Telegram receives alert with live LDR ADC value. | ✅ |
| **4. Anti-Spam Check** | Keep flashlight on LDR continuously for 15 seconds. | Bot receives exactly **1** notification, not repeated every 2 seconds. | ✅ |
| **5. Acknowledgment Check** | Hold Button A on Yolo:Bit Badge for $\ge 1\text{s}$ or click "Acknowledge" on Dashboard. | Alarm clears on ThingsBoard and bot receives `ALARM RESOLVED` notice. | ✅ |
