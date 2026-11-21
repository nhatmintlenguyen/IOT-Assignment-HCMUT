#!/usr/bin/env python3
"""
Smart Safe Guardian - IoT Gateway Daemon (T08 & T15)
Author: Smart Safe Guardian Team (HCMUT CO3037 - Semester 261)
Runs on: PC / Raspberry Pi Zero 2W

Bridges physical YoloUNO (USB Serial CDC) <--> ThingsBoard / CoreIOT (MQTT).
Integrates Edge AI Anomaly Detection (T09) via Scikit-Learn Isolation Forest.
"""

import argparse
import glob
import json
import os
import socket
import sys
import time
import threading
import urllib.error
import urllib.request
import paho.mqtt.client as mqtt

# Ensure unbuffered output for logging and service daemons
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

def load_dotenv_fallback():
    """Loads environment variables from .env if present in root or search paths."""
    search_dirs = [
        os.getcwd(),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ]
    seen_files = set()
    for d in search_dirs:
        env_file = os.path.abspath(os.path.join(d, ".env"))
        if env_file in seen_files or not os.path.isfile(env_file):
            continue
        seen_files.add(env_file)
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass

load_dotenv_fallback()

# Local AI Anomaly Detector
try:
    from anomaly_detector import VaultAnomalyDetector
except ImportError:
    from gateway.anomaly_detector import VaultAnomalyDetector


def discover_thingsboard_server(beacon_port=50051, timeout=5.0):
    """
    Listens on UDP beacon_port for ThingsBoard broadcast announcements.
    Returns (server_ip, mqtt_port, device_token, gw_token) or (None, None, None, None).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass

    try:
        sock.bind(('0.0.0.0', beacon_port))
    except Exception as e:
        print(f"[DISCOVERY] Could not bind UDP socket on port {beacon_port}: {e}")
        return None, None, None, None

    sock.settimeout(0.5)
    start_time = time.time()
    discovered = (None, None, None, None)

    try:
        while (time.time() - start_time) < timeout:
            try:
                data, addr = sock.recvfrom(2048)
                msg = json.loads(data.decode("utf-8"))
                if msg.get("service") in ("SMART_SAFE_THINGSBOARD", "thingsboard", "THINGSBOARD"):
                    sender_ip = addr[0]
                    # If sender is loopback, prefer the announced LAN IP if present
                    if sender_ip.startswith("127.") and msg.get("ip"):
                        server_ip = msg.get("ip")
                    else:
                        server_ip = sender_ip
                    mqtt_port = int(msg.get("mqtt_port", 1883))
                    dev_token = msg.get("device_token")
                    gw_token = msg.get("gateway_token")
                    discovered = (server_ip, mqtt_port, dev_token, gw_token)
                    break
            except (socket.timeout, TimeoutError):
                continue
            except Exception:
                continue
    finally:
        sock.close()

    return discovered


class SmartSafeGateway:
    def __init__(self, tb_host, tb_port, tb_token, serial_port, baudrate, mock=False, gw_token=None,
                 beacon_port=50051, fallback_host="127.0.0.1", debug=False,
                 telegram_token=None, telegram_chat_id=None, disable_telegram=False):
        self.raw_tb_host = tb_host
        self.tb_host = tb_host
        self.tb_port = tb_port
        self.tb_token = tb_token
        self.gw_token = gw_token
        self.beacon_port = beacon_port
        self.fallback_host = fallback_host
        self.auto_discovery = (not tb_host or tb_host.strip().lower() == "auto")
        self.serial_port_name = serial_port
        self.baudrate = baudrate
        self.mock_mode = mock
        self.debug_mode = debug

        # Telegram Intrusion Notification Configuration (T13)
        self.telegram_token = (telegram_token or os.getenv("TELEGRAM_TOKEN", "")).strip()
        self.telegram_chat_id = (telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "")).strip()
        self.telegram_enabled = bool(self.telegram_token and self.telegram_chat_id and not disable_telegram)
        self._telegram_breach_notified = False

        # CoreIOT Cloud Mirroring Configuration (Optional Dual-Broker T15)
        self.coreiot_host = (os.getenv("COREIOT_HOST", "")).strip()
        self.coreiot_port = int(os.getenv("COREIOT_PORT", "1883"))
        self.coreiot_token = (os.getenv("COREIOT_TOKEN", "")).strip()
        self.coreiot_client = None
        self.coreiot_connected = False

        self.serial_conn = None
        self.mqtt_client = None
        self.gw_client = None
        self.mqtt_connected = False
        self._last_gw_ping = 0
        self._last_unlock_event_time = 0
        self._last_lock_event_time = 0
        self._last_rogue_badge_time = 0
        self._last_bruteforce_time = 0
        self._pending_operator_unlock = 0
        self._pending_operator_lock = 0
        self._pending_operator_ack = 0
        self._pending_operator_lockdown = 0
        self._recent_events = {}
        self.running = True
        self.last_breach_state = False
        self.last_known_state = None
        self.detector = VaultAnomalyDetector()

        # Simulated mock state
        self.mock_state = {
            "temp": 28.4,
            "hum": 64.5,
            "light_adc": 135,
            "distance_cm": 45.0,
            "state": "LOCKED",
            "breach": False,
            "lockdown": False,
            "last_badge": "AUTHORIZED BADGE",
            "espnow_link": "ACTIVE (-58 dBm)",
            "vault_hardware": "USB CDC ONLINE",
            "gateway_status": "ONLINE (Wi-Fi MQTT)"
        }

    # --------------------------------------------------------------------------
    # TELEGRAM NOTIFICATIONS (T13)
    # --------------------------------------------------------------------------
    def send_telegram_message(self, text, parse_mode="HTML"):
        """Dispatches an asynchronous Telegram alert in a daemon background thread."""
        if not self.telegram_enabled:
            return

        def _worker():
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = json.dumps({
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": parse_mode
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "SmartSafeGuardian/1.0"}
            )
            try:
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    if resp.status == 200:
                        if self.debug_mode:
                            print(f"{self._ts()} \033[92m[TELEGRAM] Alert delivered successfully to chat {self.telegram_chat_id}!\033[0m")
                    else:
                        print(f"{self._ts()} \033[93m[TELEGRAM] Non-200 response from Telegram API: {resp.status}\033[0m")
            except Exception as e:
                print(f"{self._ts()} \033[91m[TELEGRAM] Failed to send Telegram alert: {e}\033[0m")

        t = threading.Thread(target=_worker, name="telegram-alert-worker", daemon=True)
        t.start()

    def notify_telegram_breach(self, telemetry):
        """Dispatches a formatted physical breach alert to Telegram."""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        light_val = telemetry.get("light_adc", "N/A")
        temp_val = telemetry.get("temp", "N/A")
        state_val = telemetry.get("state", self.last_known_state or "LOCKED")
        msg = (
            "🚨 <b>SMART SAFE GUARDIAN - SECURITY ALERT</b> 🚨\n\n"
            "<b>Event:</b> Physical Breach Detected!\n"
            "<b>Status:</b> INTERNAL SENSOR TRIPPED\n"
            f"<b>Vault State:</b> <code>{state_val}</code>\n"
            f"<b>Light Level:</b> <code>{light_val}</code> ADC\n"
            f"<b>Temperature:</b> <code>{temp_val}</code>°C\n"
            f"<b>Timestamp:</b> <code>{now_str}</code>\n\n"
            "⚠️ <i>Immediate physical inspection required!</i>"
        )
        self.send_telegram_message(msg, parse_mode="HTML")

    def notify_telegram_breach_cleared(self, source="Authorized Operator"):
        """Dispatches a breach resolution notice to Telegram."""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        msg = (
            "✅ <b>SMART SAFE GUARDIAN - ALERT RESOLVED</b>\n\n"
            "<b>Status:</b> Breach Alarm Acknowledged\n"
            f"<b>Authorized by:</b> <code>{source}</code>\n"
            f"<b>Timestamp:</b> <code>{now_str}</code>\n\n"
            "🔒 <i>Vault security perimeter re-armed and monitored.</i>"
        )
        self.send_telegram_message(msg, parse_mode="HTML")

    def test_telegram_connection(self):
        """Sends a verification ping to Telegram and checks API response synchronously."""
        if not self.telegram_enabled:
            print("[ERROR] Telegram is not configured. Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env.")
            return False
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = json.dumps({
            "chat_id": self.telegram_chat_id,
            "text": "🔐 <b>Smart Safe Guardian</b>: Telegram bot connectivity test successful!",
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SmartSafeGuardian/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    print(f"\033[92m[SUCCESS] Test message successfully delivered to Telegram chat {self.telegram_chat_id}!\033[0m")
                    return True
                else:
                    print(f"\033[91m[ERROR] Telegram API returned HTTP status {resp.status}\033[0m")
                    return False
        except Exception as e:
            print(f"\033[91m[ERROR] Telegram connection failed: {e}\033[0m")
            return False

    def _ts(self):
        """Returns current local time formatted as [HH:MM:SS]."""
        return time.strftime("[%H:%M:%S]")

    # --------------------------------------------------------------------------
    # SERIAL COMMUNICATION (YoloUNO <--> Gateway)
    # --------------------------------------------------------------------------
    def _find_serial_port(self):
        """Auto-detects YoloUNO USB serial port, avoiding capturing Yolo:Bit badge."""
        if self.serial_port_name and self.serial_port_name.lower() != "auto":
            return self.serial_port_name

        # 1. Prefer /dev/serial/by-id on Linux to accurately differentiate YoloUNO vs Badge
        by_id_dir = "/dev/serial/by-id"
        if os.path.isdir(by_id_dir):
            for entry in sorted(os.listdir(by_id_dir)):
                low = entry.lower()
                # YoloUNO is ESP32-S3 (Espressif / ACM)
                if any(k in low for k in ("espressif", "acm", "jtag", "yolo_uno")):
                    real_path = os.path.realpath(os.path.join(by_id_dir, entry))
                    return real_path

        # 2. Check /dev/ttyACM* (native USB CDC for ESP32-S3 YoloUNO)
        acm_candidates = sorted(glob.glob("/dev/ttyACM*"))
        if acm_candidates:
            return acm_candidates[0]

        # 3. If there are USB serial ports, check that they are not known badges
        for p in sorted(glob.glob("/dev/ttyUSB*")):
            if os.path.isdir(by_id_dir):
                is_badge = False
                for entry in os.listdir(by_id_dir):
                    target_real = os.path.realpath(os.path.join(by_id_dir, entry))
                    if p == target_real or p.endswith(os.path.basename(target_real)):
                        if any(k in entry.lower() for k in ("1a86", "ch34", "cp21", "usb_serial")):
                            is_badge = True
                            break
                if is_badge:
                    continue  # Skip badge port, wait for YoloUNO
            return p

        # 4. macOS / Windows fallback
        for pattern in ("/dev/cu.usbmodem*", "/dev/cu.wch*"):
            candidates = sorted(glob.glob(pattern))
            if candidates:
                return candidates[0]

        return None

    def connect_serial(self):
        """Attempts to open serial connection with retry loop."""
        if self.mock_mode:
            print("[INFO] Running in MOCK SERIAL mode. Simulating YoloUNO telemetry.")
            return True

        import serial
        while self.running:
            port = self._find_serial_port()
            if not port:
                print("[WARN] No YoloUNO USB serial port detected. Waiting 3s... (Run with --mock to test without hardware)")
                time.sleep(3)
                continue

            try:
                print(f"[SERIAL] Connecting to YoloUNO on {port} @ {self.baudrate} baud...")
                self.serial_conn = serial.Serial(port, self.baudrate, timeout=1.5)
                time.sleep(1.0) # Settle USB CDC
                print(f"[SERIAL] Successfully connected to {port}!")
                return True
            except Exception as e:
                print(f"[ERROR] Failed to open {port}: {e}. Retrying in 3s...")
                time.sleep(3)

        return False

    def write_serial(self, command_str):
        """Sends command line to physical or mock YoloUNO."""
        command_clean = command_str.strip()
        if self.debug_mode:
            print(f"{self._ts()} [DEBUG SERIAL TX] Command: '{command_clean}'")

        if self.mock_mode:
            if command_clean == "unlock":
                self.mock_state["state"] = "UNLOCKED"
                self.process_incoming_line('{"type":"event","source":"system","action":"unlock","state":"UNLOCKED"}')
            elif command_clean == "lock":
                self.mock_state["state"] = "LOCKED"
                self.process_incoming_line('{"type":"event","source":"system","action":"manual_lock","state":"LOCKED"}')
            elif command_clean in ("ack", "reset"):
                self.mock_state["breach"] = False
                self.process_incoming_line('{"type":"event","event":"breach_acknowledged"}')
            elif command_clean == "lockdown 1":
                self.mock_state["lockdown"] = True
                self.mock_state["state"] = "LOCKED"
                self.process_incoming_line('{"type":"event","event":"lockdown_enabled"}')
            elif command_clean == "lockdown 0":
                self.mock_state["lockdown"] = False
                self.process_incoming_line('{"type":"event","event":"lockdown_disabled"}')
            return

        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((command_clean + "\n").encode("utf-8"))
                self.serial_conn.flush()
            except Exception as e:
                print(f"[ERROR] Serial write error: {e}")

    # --------------------------------------------------------------------------
    # MQTT & DISCOVERY (Gateway <--> ThingsBoard)
    # --------------------------------------------------------------------------
    def resolve_target_host(self):
        """Resolves ThingsBoard host either via manual config or UDP beacon discovery."""
        if not self.auto_discovery:
            print(f"[HOST] Using manually configured ThingsBoard host: {self.tb_host}:{self.tb_port}")
            return True

        print(f"[DISCOVERY] Auto-detecting ThingsBoard on local network (UDP port {self.beacon_port})...")
        ip, port, dev_token, gw_token = discover_thingsboard_server(self.beacon_port, timeout=5.0)

        if ip:
            print(f"\033[92m[DISCOVERY] >>> Discovered ThingsBoard at {ip}:{port} via UDP Beacon! <<<\033[0m")
            self.tb_host = ip
            if port:
                self.tb_port = port
            if dev_token and (not self.tb_token or self.tb_token == "6EzRR6gcTvnOcgVF53hP"):
                self.tb_token = dev_token
            if gw_token and not self.gw_token:
                self.gw_token = gw_token
            return True

        print(f"[DISCOVERY] No ThingsBoard beacon heard within 5s.")
        if self.fallback_host:
            print(f"[DISCOVERY] Falling back to host: {self.fallback_host}:{self.tb_port}")
            self.tb_host = self.fallback_host
            return True

        return False

    def connect_mqtt(self):
        """Initializes and connects MQTT client to ThingsBoard."""
        # Check Paho MQTT version compatibility
        try:
            self.mqtt_client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id="smart-safe-gateway"
            )
        except AttributeError:
            self.mqtt_client = mqtt.Client(client_id="smart-safe-gateway")

        # ThingsBoard uses the Device Access Token as the MQTT username
        self.mqtt_client.username_pw_set(self.tb_token)
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        self.mqtt_client.on_disconnect = self._on_mqtt_disconnect

        print(f"[MQTT] Connecting to ThingsBoard at {self.tb_host}:{self.tb_port}...")
        try:
            self.mqtt_client.connect(self.tb_host, self.tb_port, keepalive=60)
            self.mqtt_client.loop_start()

            # Connect optional gateway heartbeat client so both Gateway and Vault remain Active
            if self.gw_token:
                try:
                    try:
                        self.gw_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smart-safe-gw-link")
                    except AttributeError:
                        self.gw_client = mqtt.Client(client_id="smart-safe-gw-link")
                    self.gw_client.username_pw_set(self.gw_token)
                    self.gw_client.connect(self.tb_host, self.tb_port, keepalive=60)
                    self.gw_client.loop_start()
                    self.gw_client.publish("v1/devices/me/telemetry", json.dumps({"gateway_status": "online"}), qos=1)
                    self._last_gw_ping = time.time()
                    print(f"[MQTT] Gateway link connected (token: {self.gw_token})")
                except Exception as ge:
                    print(f"[WARN] Gateway link warning: {ge}")

            # Connect optional CoreIOT cloud mirror (T15 dual-platform support)
            if self.coreiot_token and self.coreiot_host:
                self._connect_coreiot()

            return True
        except Exception as e:
            print(f"[ERROR] Could not connect to ThingsBoard MQTT broker ({self.tb_host}:{self.tb_port}): {e}")
            self.mqtt_connected = False
            return False

    def _connect_coreiot(self):
        """Connects secondary MQTT client to CoreIOT cloud platform for dual-cloud mirroring (T15)."""
        try:
            try:
                self.coreiot_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="smart-safe-coreiot-mirror")
            except AttributeError:
                self.coreiot_client = mqtt.Client(client_id="smart-safe-coreiot-mirror")

            self.coreiot_client.username_pw_set(self.coreiot_token)
            self.coreiot_client.on_connect = self._on_coreiot_connect
            self.coreiot_client.on_message = self._on_mqtt_message
            self.coreiot_client.on_disconnect = lambda c, u, d, p=None: setattr(self, "coreiot_connected", False)
            print(f"[COREIOT] Connecting to Cloud Platform at {self.coreiot_host}:{self.coreiot_port}...")
            self.coreiot_client.connect(self.coreiot_host, self.coreiot_port, keepalive=60)
            self.coreiot_client.loop_start()
        except Exception as ce:
            print(f"[WARN] Could not connect to CoreIOT cloud ({self.coreiot_host}): {ce}")
            self.coreiot_connected = False

    def _on_coreiot_connect(self, client, userdata, flags, rc, properties=None):
        rc_code = rc if isinstance(rc, int) else getattr(rc, "value", rc)
        if rc_code == 0:
            self.coreiot_connected = True
            print(f"\033[92m[COREIOT] Connected successfully to Cloud Platform ({self.coreiot_host})!\033[0m")
            client.subscribe("v1/devices/me/rpc/request/+")
            print("[COREIOT] Subscribed to remote Cloud RPC requests!")
        else:
            self.coreiot_connected = False
            print(f"[COREIOT] Connection refused with code {rc_code}")

    def _publish_mqtt(self, topic, payload_str):
        """Publishes a payload to Local ThingsBoard and CoreIOT Cloud if connected."""
        if self.mqtt_client and self.mqtt_connected:
            self.mqtt_client.publish(topic, payload_str)
        if self.coreiot_client and self.coreiot_connected:
            self.coreiot_client.publish(topic, payload_str)

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        rc_code = rc if isinstance(rc, int) else getattr(rc, "value", rc)
        if rc_code == 0:
            self.mqtt_connected = True
            print("[MQTT] Connected to ThingsBoard successfully!")
            # Subscribe to remote RPC commands from Dashboard widgets
            client.subscribe("v1/devices/me/rpc/request/+")
            print("[MQTT] Subscribed to RPC requests: 'v1/devices/me/rpc/request/+'")
        else:
            self.mqtt_connected = False
            print(f"[MQTT] Connection refused with code {rc_code}")

    def _on_mqtt_disconnect(self, client, userdata, disconnect_flags_or_rc, properties=None):
        self.mqtt_connected = False
        print("[MQTT] Disconnected from ThingsBoard broker. Reconnecting...")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handles incoming RPC calls from ThingsBoard dashboard."""
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8")
        if self.debug_mode:
            print(f"{self._ts()} [DEBUG MQTT RX RPC] Topic: {topic} | Payload: {payload_str}")

        # Extract request id from: v1/devices/me/rpc/request/{requestId}
        req_id = topic.split("/")[-1]

        try:
            data = json.loads(payload_str)
            method = data.get("method", "")
            params = data.get("params", {})
        except Exception:
            method = payload_str
            params = {}

        # Route RPC method to YoloUNO serial protocol
        response_payload = {"status": "ok", "method": method}

        if method == "unlock" or (method == "setLockState" and params is True):
            print(f"{self._ts()} [RPC] Operator commanded: UNLOCK SAFE")
            self._pending_operator_unlock = time.time()
            self.write_serial("unlock")
            response_payload["state"] = "UNLOCKED"
        elif method == "lock" or (method == "setLockState" and params is False):
            print(f"{self._ts()} [RPC] Operator commanded: LOCK SAFE")
            self._pending_operator_lock = time.time()
            self.write_serial("lock")
            response_payload["state"] = "LOCKED"
        elif method in ("ack", "ackBreach", "reset"):
            is_breach_active = self.mock_state.get("breach", False) if self.mock_mode else self.last_breach_state
            if not is_breach_active:
                print(f"{self._ts()} [RPC] Ignored 'ack': No active security breach.")
                response_payload["status"] = "ignored"
                response_payload["message"] = "No active breach to acknowledge"
            else:
                print(f"{self._ts()} [RPC] Operator commanded: ACKNOWLEDGE ALARM")
                self._pending_operator_ack = time.time()
                self.write_serial("ack")
                self.last_breach_state = False
                response_payload["breach"] = False
        elif method == "setLockdown":
            is_active = bool(params) if isinstance(params, bool) else (str(params).lower() in ("true", "1"))
            print(f"{self._ts()} [RPC] Operator commanded: {'ENGAGE' if is_active else 'CLEAR'} LOCKDOWN")
            self._pending_operator_lockdown = time.time()
            self.write_serial(f"lockdown {1 if is_active else 0}")
            response_payload["lockdown"] = is_active
        elif method in ("getState", "getLockState"):
            response_payload["value"] = (self.mock_state["state"] == "UNLOCKED")
        elif method in ("getLockdown",):
            response_payload["value"] = bool(self.mock_state["lockdown"])
        else:
            print(f"{self._ts()} [RPC] Unknown RPC method: '{method}'")
            response_payload["status"] = "unknown_method"

        # Reply to ThingsBoard/CoreIOT RPC response topic
        resp_topic = f"v1/devices/me/rpc/response/{req_id}"
        client.publish(resp_topic, json.dumps(response_payload))
        if self.debug_mode:
            print(f"{self._ts()} [DEBUG MQTT TX RPC] Response sent to {resp_topic}: {response_payload}")

    # --------------------------------------------------------------------------
    # PROCESSING LOOPS
    # --------------------------------------------------------------------------
    def process_incoming_line(self, line):
        """Parses a single JSON line received from YoloUNO."""
        line = line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            if self.debug_mode and line:
                print(f"{self._ts()} [DEBUG SERIAL RAW] {line}")
            return

        if self.debug_mode:
            print(f"{self._ts()} [DEBUG SERIAL RX] {line}")

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return

        msg_type = obj.get("type", "")

        # 1. Telemetry streaming frame (emitted every 2 seconds by YoloUNO)
        if msg_type == "telemetry":
            if "breach" in obj:
                self.last_breach_state = bool(obj["breach"])

            # Run Edge AI anomaly evaluation (T09)
            is_anomaly, anomaly_score, reason = self.detector.evaluate(obj)
            obj["anomaly"] = is_anomaly
            obj["anomaly_score"] = anomaly_score
            # Only include anomaly_reason when an anomaly is actually active
            if is_anomaly:
                obj["anomaly_reason"] = reason

            payload = json.dumps(obj)
            self._publish_mqtt("v1/devices/me/telemetry", payload)
            if self.debug_mode:
                print(f"{self._ts()} [DEBUG MQTT TX] v1/devices/me/telemetry -> {payload}")

            # Audit logging: record door state transitions (LOCKED <-> UNLOCKED)
            current_state = obj.get("state")
            if current_state in ("LOCKED", "UNLOCKED"):
                if self.last_known_state is not None and current_state != self.last_known_state:
                    action_time = self._last_unlock_event_time if current_state == "UNLOCKED" else self._last_lock_event_time
                    if (time.time() - action_time) >= 2.0:
                        self._publish_mqtt("v1/devices/me/telemetry", json.dumps({
                            "audit_state": current_state,
                            "audit_event": f"Door State Changed to {current_state.title()}"
                        }))
                self.last_known_state = current_state

            # Periodic Gateway heartbeat
            if self.gw_client and (time.time() - self._last_gw_ping > 15):
                self.gw_client.publish("v1/devices/me/telemetry", json.dumps({"gateway_status": "online"}), qos=0)
                self._last_gw_ping = time.time()

            status_color = "\033[92m" if obj.get("state") == "UNLOCKED" else "\033[94m"
            breach_alert = " \033[91;1m[BREACH!]\033[0m" if obj.get("breach") else ""
            lockdown_tag = " \033[95;1m[LOCKDOWN]\033[0m" if obj.get("lockdown") else ""
            score_color = "\033[91;1m" if anomaly_score >= 0.5 else ("\033[93m" if anomaly_score >= 0.2 else "\033[92m")

            print(f"{self._ts()} [TELEMETRY] Temp: {obj.get('temp', 0.0):.1f}°C | Hum: {obj.get('hum', 0.0):.1f}% | "
                  f"Light: {obj.get('light_adc', 0)} | Dist: {obj.get('distance_cm', 0.0):.1f}cm | "
                  f"State: {status_color}{obj.get('state')}\033[0m | AI Score: {score_color}{anomaly_score:.2f}\033[0m"
                  f"{breach_alert}{lockdown_tag}")

        # 2. Asynchronous Security Events (Access granted, bad PIN, auto-lock, badge, etc.)
        elif msg_type == "event":
            source = obj.get("source", "system")
            action = obj.get("action")
            result = obj.get("result")
            event_name = obj.get("event")
            cmd = obj.get("cmd")

            event_desc = None
            audit_state = "LOCKED"
            is_significant = True
            log_category = "EVENT"

            # Case 0: Security Auth Failed (Suppress if rogue badge or bad pin was already logged within 2.0s)
            if event_name == "auth_failed":
                if (time.time() - self._last_rogue_badge_time) < 2.0:
                    is_significant = False
                else:
                    att = obj.get("attempt", 1)
                    max_att = obj.get("max", 3)
                    event_desc = f"Security Alert: Failed Authentication ({att}/{max_att})"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"

            # Case A: ESP-NOW Badge events
            elif source in ("badge_espnow", "badge"):
                if obj.get("alert") == "ROGUE_BADGE_DETECTED" or cmd == "FAKE_BADGE" or result == "denied_unauthorized":
                    rogue_mac = obj.get("rogue_mac", "")
                    mac_info = f" ({rogue_mac})" if rogue_mac else ""
                    event_desc = f"Rogue Badge Rejected{mac_info}"
                    audit_state = "LOCKED"
                    self._last_rogue_badge_time = time.time()
                    self.mock_state["last_badge"] = "ROGUE BADGE (DENIED)"
                    self.mock_state["espnow_link"] = "ACTIVE (Unauthorized RX)"
                    log_category = "SECURITY"
                elif cmd == "UNLOCK":
                    if result == "already_open":
                        event_desc = "Badge Unlock Denied: Already Unlocked"
                        audit_state = "UNLOCKED"
                        log_category = "ACCESS"
                    elif result == "denied_no_presence":
                        event_desc = "Badge Denied: Approach Vault First"
                        audit_state = "LOCKED"
                        log_category = "SECURITY"
                    elif result == "denied_lockdown":
                        event_desc = "Badge Denied: System in Lockdown"
                        audit_state = "LOCKED"
                        log_category = "SECURITY"
                    else:
                        event_desc = "Door Unlocked via Badge"
                        audit_state = "UNLOCKED"
                        self.last_known_state = "UNLOCKED"
                        self._last_unlock_event_time = time.time()
                        self.mock_state["last_badge"] = "AUTHORIZED BADGE"
                        self.mock_state["espnow_link"] = "ACTIVE (-58 dBm)"
                        log_category = "ACCESS"
                elif cmd == "LOCK":
                    if result == "already_locked":
                        event_desc = "Badge Lock Denied: Already Locked"
                        audit_state = "LOCKED"
                        log_category = "LOCK"
                    else:
                        event_desc = "Door Locked via Badge"
                        audit_state = "LOCKED"
                        self.last_known_state = "LOCKED"
                        self._last_lock_event_time = time.time()
                        self.mock_state["last_badge"] = "AUTHORIZED BADGE"
                        self.mock_state["espnow_link"] = "ACTIVE (-58 dBm)"
                        log_category = "LOCK"
                elif cmd == "ACK_BREACH":
                    event_desc = "Breach Alarm Acknowledged (Badge)"
                    audit_state = "LOCKED"
                    self.last_breach_state = False
                    self.mock_state["last_badge"] = "AUTHORIZED BADGE"
                    log_category = "SECURITY"
                    if self._telegram_breach_notified:
                        self.notify_telegram_breach_cleared(source="Badge Button")
                        self._telegram_breach_notified = False
                elif cmd == "PAIR_REQ":
                    event_desc = "Pairing Request Received (Badge)"
                    audit_state = "LOCKED"
                    log_category = "PAIRING"
                else:
                    act_name = cmd or action or result or event_name
                    if not act_name or str(act_name).strip().lower() in ("none", "", "no_alert_to_ack"):
                        is_significant = False
                    else:
                        clean_name = str(act_name).replace('_', ' ').strip().title()
                        event_desc = f"Badge Action: {clean_name}"
                        audit_state = "LOCKED"
                        log_category = "BADGE"

            # Case B: Hardware / NVS Pairing events
            elif source in ("pairing", "vault") and action in ("pairing_mode_started", "badge_paired", "pair_denied_window_closed"):
                if action == "pairing_mode_started":
                    sec = obj.get("window_sec", 15)
                    event_desc = f"Pairing Mode Active ({sec}s Window)"
                    audit_state = "LOCKED"
                    log_category = "PAIRING"
                elif action == "badge_paired":
                    mac = obj.get("mac", "")
                    event_desc = f"Badge Paired Successfully (MAC: {mac})"
                    audit_state = "LOCKED"
                    log_category = "PAIRING"
                elif action == "pair_denied_window_closed":
                    event_desc = "Pairing Denied: Timeout Window Expired"
                    audit_state = "LOCKED"
                    log_category = "PAIRING"

            # Case C: IR PIN Keypad events
            elif source == "ir_pin":
                if action == "digit":
                    ent = obj.get("entered", 1)
                    if self.debug_mode:
                        print(f"{self._ts()} [KEYPAD] IR PIN: Digit entered ({ent}/4)")
                    is_significant = False
                elif action == "backspace":
                    rem = obj.get("remaining", 0)
                    if self.debug_mode:
                        print(f"{self._ts()} [KEYPAD] IR PIN: Backspace pressed ({rem}/4 remaining)")
                    is_significant = False
                elif result == "granted":
                    event_desc = "Door Unlocked via PIN Code (IR Remote)"
                    audit_state = "UNLOCKED"
                    self.last_known_state = "UNLOCKED"
                    self._last_unlock_event_time = time.time()
                    log_category = "ACCESS"
                elif result == "denied":
                    event_desc = "PIN Access Denied: Incorrect Code"
                    audit_state = "LOCKED"
                    self._last_rogue_badge_time = time.time()
                    log_category = "SECURITY"
                elif result == "denied_lockdown":
                    event_desc = "PIN Access Denied: System in Lockdown"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"
                elif result == "denied_no_presence":
                    event_desc = "PIN Access Denied: Approach Vault First"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"
                elif action == "canceled":
                    event_desc = "PIN Entry Canceled by User"
                    audit_state = "LOCKED"
                    log_category = "KEYPAD"
                elif action == "timeout_cleared":
                    event_desc = "PIN Entry Timeout (Cleared)"
                    audit_state = "LOCKED"
                    log_category = "KEYPAD"
                elif action == "pin_changed":
                    event_desc = "Master PIN Code Updated"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"
                elif result == "denied_wrong_old_pin":
                    event_desc = "PIN Change Denied: Incorrect Current PIN"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"
                elif action == "change_canceled":
                    event_desc = "PIN Change Canceled"
                    audit_state = "LOCKED"
                    log_category = "KEYPAD"
                else:
                    is_significant = False

            # Case D: IR Remote general events
            elif source == "ir_remote":
                if action == "manual_lock":
                    event_desc = "Door Locked via IR Remote"
                    audit_state = "LOCKED"
                    self.last_known_state = "LOCKED"
                    self._last_lock_event_time = time.time()
                    log_category = "LOCK"
                elif action == "breach_acknowledged":
                    event_desc = "Breach Alarm Acknowledged (IR Remote)"
                    audit_state = "LOCKED"
                    self.last_breach_state = False
                    log_category = "SECURITY"
                    if self._telegram_breach_notified:
                        self.notify_telegram_breach_cleared(source="IR Remote")
                        self._telegram_breach_notified = False
                elif result == "denied_no_presence":
                    event_desc = "IR Command Denied: Approach Vault First"
                    audit_state = "LOCKED"
                    log_category = "SECURITY"
                else:
                    is_significant = False

            # Case E: Generic System / Vault State events
            elif event_name == "approach":
                dist = obj.get("distance_cm", 0.0)
                if self.debug_mode:
                    print(f"{self._ts()} [RADAR] Person detected approaching ({dist:.1f} cm) -> Safe Armed")
                is_significant = False

            elif (event_name == "access" and obj.get("status") == "granted") or (not event_name and source == "system" and action == "unlock"):
                if (time.time() - self._last_unlock_event_time) < 2.0:
                    is_significant = False
                elif (time.time() - self._pending_operator_unlock) < 2.5:
                    event_desc = "Door Unlocked (Web / Cloud)"
                    audit_state = "UNLOCKED"
                    self.last_known_state = "UNLOCKED"
                    self._last_unlock_event_time = time.time()
                    log_category = "ACCESS"
                elif action == "unlock":
                    event_desc = "Door Unlocked (USB CLI)"
                    audit_state = "UNLOCKED"
                    self.last_known_state = "UNLOCKED"
                    self._last_unlock_event_time = time.time()
                    log_category = "ACCESS"
                else:
                    is_significant = False

            elif source == "system" and action == "manual_lock":
                if (time.time() - self._pending_operator_lock) < 2.5:
                    event_desc = "Door Locked (Web / Cloud)"
                else:
                    event_desc = "Door Locked (USB CLI)"
                audit_state = "LOCKED"
                self.last_known_state = "LOCKED"
                self._last_lock_event_time = time.time()
                log_category = "LOCK"

            elif event_name == "auto_locked":
                event_desc = "Auto-Lock Timer Expired (Door Locked)"
                audit_state = "LOCKED"
                self.last_known_state = "LOCKED"
                self._last_lock_event_time = time.time()
                log_category = "LOCK"

            elif event_name == "breach":
                sensor = obj.get("source", "ldr").upper()
                light_adc = obj.get("light_adc", 0)
                event_desc = f"Security Breach: Internal {sensor} Sensor Tripped (ADC={light_adc})"
                audit_state = "LOCKED"
                self.last_breach_state = True
                log_category = "ALARM"
                if not self._telegram_breach_notified:
                    self.notify_telegram_breach(obj)
                    self._telegram_breach_notified = True

            elif event_name == "breach_acknowledged":
                if (time.time() - self._pending_operator_ack) < 2.5:
                    event_desc = "Breach Alarm Acknowledged (Web / Cloud)"
                    ack_source = "Web / Cloud Dashboard"
                else:
                    event_desc = "Breach Alarm Acknowledged"
                    ack_source = "System Event"
                audit_state = "LOCKED"
                self.last_breach_state = False
                log_category = "SECURITY"
                if self._telegram_breach_notified:
                    self.notify_telegram_breach_cleared(source=ack_source)
                    self._telegram_breach_notified = False

            elif event_name == "lockdown_enabled":
                # Suppress if triggered within 2.0s of bruteforce alarm (bruteforce already logged the incident)
                if (time.time() - self._last_bruteforce_time) < 2.0:
                    is_significant = False
                elif (time.time() - self._pending_operator_lockdown) < 2.5:
                    event_desc = "Emergency Lockdown Armed (Web / Cloud)"
                    audit_state = "LOCKED"
                    self.last_known_state = "LOCKED"
                    log_category = "LOCKDOWN"
                else:
                    event_desc = "Emergency Lockdown Armed"
                    audit_state = "LOCKED"
                    self.last_known_state = "LOCKED"
                    log_category = "LOCKDOWN"

            elif event_name == "lockdown_disabled":
                if (time.time() - self._pending_operator_lockdown) < 2.5:
                    event_desc = "Emergency Lockdown Cleared (Web / Cloud)"
                else:
                    event_desc = "Emergency Lockdown Cleared"
                audit_state = "LOCKED"
                self.last_known_state = "LOCKED"
                log_category = "SECURITY"

            elif event_name == "lockdown_blocked":
                if (time.time() - self._pending_operator_unlock) < 2.5:
                    event_desc = "Unlock Denied: System in Lockdown (Web / Cloud)"
                else:
                    event_desc = "Unlock Denied: System in Lockdown"
                audit_state = "LOCKED"
                log_category = "SECURITY"

            else:
                raw_act = action or result or event_name or cmd
                if not raw_act or str(raw_act).strip().lower() in ("none", "", "no_alert_to_ack", "change_prompt", "enter_old_pin", "cleared"):
                    is_significant = False
                else:
                    clean_name = str(raw_act).replace('_', ' ').strip().title()
                    event_desc = f"System Event: {clean_name}"
                    audit_state = "LOCKED"

            if is_significant and event_desc:
                now_t = time.time()
                last_t = self._recent_events.get(event_desc, 0)
                if (now_t - last_t) < 1.5:
                    if self.debug_mode:
                        print(f"{self._ts()} [DEBUG DEDUP] Ignored duplicate event within 1.5s: '{event_desc}'")
                    return

                self._recent_events[event_desc] = now_t
                if len(self._recent_events) > 30:
                    self._recent_events = {k: v for k, v in self._recent_events.items() if (now_t - v) < 5.0}

                # Guarantee strict binary Door State (LOCKED or UNLOCKED)
                if audit_state not in ("LOCKED", "UNLOCKED"):
                    audit_state = "UNLOCKED" if (self.last_known_state == "UNLOCKED") else "LOCKED"

                print(f"{self._ts()} [{log_category}] {event_desc} | State: {audit_state}")
                event_payload = {
                    "audit_state": audit_state,
                    "audit_event": event_desc
                }
                try:
                    p_json = json.dumps(event_payload)
                    self._publish_mqtt("v1/devices/me/telemetry", p_json)
                    if self.debug_mode:
                        print(f"{self._ts()} [DEBUG MQTT TX] v1/devices/me/telemetry -> {p_json}")
                except Exception as pe:
                    print(f"[WARN] Failed to publish audit event: {pe}")

        # 3. Critical Security Alarms (Bruteforce detected, Light breach)
        elif msg_type == "alarm":
            alarm_name = obj.get("alarm", "unknown_alarm")
            action = obj.get("action", "")
            if alarm_name == "bruteforce_detected":
                self._last_bruteforce_time = time.time()
                event_desc = "Security Alarm: Bruteforce Lockout Engaged (60s)"
                if not self._telegram_breach_notified:
                    self.notify_telegram_breach({
                        "state": "LOCKED",
                        "light_adc": "CRITICAL (Bruteforce Lockout)",
                        "temp": "N/A"
                    })
                    self._telegram_breach_notified = True
            else:
                clean_name = str(alarm_name).replace('_', ' ').strip().title()
                event_desc = f"Security Alarm: {clean_name}"

            audit_state = "LOCKED"
            print(f"{self._ts()} [ALARM] {event_desc} | State: {audit_state}")
            alarm_payload = {
                "critical_alarm": alarm_name,
                "alarm_active": True,
                "audit_state": audit_state,
                "audit_event": event_desc
            }
            p_json = json.dumps(alarm_payload)
            self._publish_mqtt("v1/devices/me/telemetry", p_json)
            if self.debug_mode:
                print(f"{self._ts()} [DEBUG MQTT TX] v1/devices/me/telemetry -> {p_json}")

    def run_mock_loop(self):
        """Simulates periodic YoloUNO telemetry for standalone testing."""
        while self.running:
            time.sleep(2.0)
            mock_line = json.dumps({
                "type": "telemetry",
                "temp": self.mock_state["temp"],
                "hum": self.mock_state["hum"],
                "climate_valid": True,
                "light_adc": self.mock_state["light_adc"],
                "distance_cm": self.mock_state["distance_cm"],
                "distance_valid": True,
                "person_near": self.mock_state["distance_cm"] < 30.0,
                "state": self.mock_state["state"],
                "breach": self.mock_state["breach"],
                "lockdown": self.mock_state["lockdown"],
                "last_badge": self.mock_state["last_badge"],
                "espnow_link": self.mock_state["espnow_link"],
                "vault_hardware": self.mock_state["vault_hardware"],
                "gateway_status": self.mock_state["gateway_status"]
            })
            self.process_incoming_line(mock_line)

    def run(self):
        """Main gateway execution lifecycle."""
        print("=========================================================")
        print("    Smart Safe Guardian - IoT Gateway Daemon (T08/T15)   ")
        print("=========================================================")

        # 1. Resolve ThingsBoard server (UDP Beacon discovery or manual IP)
        self.resolve_target_host()

        print(f"Target ThingsBoard Host : {self.tb_host}:{self.tb_port}")
        print(f"Device Access Token     : {self.tb_token}")
        if self.coreiot_token and self.coreiot_host:
            print(f"CoreIOT Cloud Mirror    : \033[92mENABLED\033[0m ({self.coreiot_host}:{self.coreiot_port})")
        else:
            print("CoreIOT Cloud Mirror    : DISABLED (Set COREIOT_TOKEN in .env to mirror to HCMUT CoreIOT)")
        if self.telegram_enabled:
            print(f"Telegram Bot Alert      : \033[92mENABLED\033[0m (Chat ID: {self.telegram_chat_id})")
        else:
            print("Telegram Bot Alert      : DISABLED (Configure TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env)")

        # 2. Connect to ThingsBoard MQTT Broker
        connected = self.connect_mqtt()

        # If auto-discovery is enabled and broker connection failed, retry discovery loop
        if not connected and self.auto_discovery:
            print("[INFO] Waiting for ThingsBoard server to become reachable on LAN...")
            while self.running and not connected:
                time.sleep(2.0)
                ip, port, dev_token, gw_token = discover_thingsboard_server(self.beacon_port, timeout=3.0)
                if ip:
                    print(f"\033[92m[DISCOVERY] Discovered ThingsBoard at {ip}:{port}!\033[0m")
                    self.tb_host = ip
                    if port:
                        self.tb_port = port
                    if dev_token:
                        self.tb_token = dev_token
                    connected = self.connect_mqtt()

        if self.mock_mode:
            try:
                self.run_mock_loop()
            except KeyboardInterrupt:
                pass
        else:
            while self.running:
                if not self.serial_conn or not self.serial_conn.is_open:
                    self.connect_serial()

                try:
                    if self.serial_conn and self.serial_conn.in_waiting:
                        raw_line = self.serial_conn.readline().decode("utf-8", errors="replace")
                        self.process_incoming_line(raw_line)
                    else:
                        time.sleep(0.05)
                except Exception as e:
                    print(f"[ERROR] Serial read failure: {e}. Reconnecting...")
                    if self.serial_conn:
                        try:
                            self.serial_conn.close()
                        except Exception:
                            pass
                    self.serial_conn = None
                    time.sleep(2.0)

        print("\n[INFO] Gateway stopping...")
        if self.gw_client:
            self.gw_client.loop_stop()
            self.gw_client.disconnect()
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        print("[INFO] Gateway terminated cleanly.")


# ------------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Smart Safe Guardian - Local IoT Gateway Daemon")
    parser.add_argument("--host", default=os.getenv("THINGSBOARD_HOST", "auto"),
                        help="ThingsBoard MQTT Broker host IP, or 'auto' for UDP LAN beacon discovery (default: auto)")
    parser.add_argument("--port", type=int, default=int(os.getenv("THINGSBOARD_PORT", "1883")),
                        help="ThingsBoard MQTT port (default: 1883)")
    parser.add_argument("--token", default=os.getenv("THINGSBOARD_TOKEN", "6EzRR6gcTvnOcgVF53hP"),
                        help="ThingsBoard Device Access Token (default: 6EzRR6gcTvnOcgVF53hP)")
    parser.add_argument("--gateway-token", default=os.getenv("GATEWAY_TOKEN", "GATEWAY_SECRET_TOKEN"),
                        help="ThingsBoard Gateway Access Token (default: GATEWAY_SECRET_TOKEN)")
    parser.add_argument("--beacon-port", type=int, default=int(os.getenv("BEACON_PORT", "50051")),
                        help="UDP Beacon port for automatic ThingsBoard discovery (default: 50051)")
    parser.add_argument("--fallback-host", default=os.getenv("THINGSBOARD_FALLBACK_HOST", "127.0.0.1"),
                        help="Fallback IP if UDP beacon discovery times out (default: 127.0.0.1)")
    parser.add_argument("--serial-port", default=os.getenv("SERIAL_PORT", "auto"),
                        help="Serial port for YoloUNO (default: auto)")
    parser.add_argument("--baudrate", type=int, default=int(os.getenv("SERIAL_BAUDRATE", "115200")),
                        help="Serial baudrate (default: 115200)")
    parser.add_argument("--mock", action="store_true",
                        help="Run with mock telemetry (no hardware required)")
    parser.add_argument("--debug", "--verbose", "-v", action="store_true",
                        help="Enable verbose debug logging (displays raw serial packets and MQTT traffic)")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_TOKEN", ""),
                        help="Telegram Bot Token for security alerts (default: read from .env)")
    parser.add_argument("--telegram-chat-id", default=os.getenv("TELEGRAM_CHAT_ID", ""),
                        help="Telegram Chat ID for security alerts (default: read from .env)")
    parser.add_argument("--disable-telegram", action="store_true",
                        help="Disable Telegram intrusion alerts even if tokens are configured")
    parser.add_argument("--test-telegram", action="store_true",
                        help="Send a test notification to Telegram to verify bot connectivity and exit")

    args = parser.parse_args()

    gateway = SmartSafeGateway(
        tb_host=args.host,
        tb_port=args.port,
        tb_token=args.token,
        gw_token=args.gateway_token,
        beacon_port=args.beacon_port,
        fallback_host=args.fallback_host,
        serial_port=args.serial_port,
        baudrate=args.baudrate,
        mock=args.mock,
        debug=args.debug,
        telegram_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id,
        disable_telegram=args.disable_telegram
    )

    if args.test_telegram:
        success = gateway.test_telegram_connection()
        sys.exit(0 if success else 1)

    gateway.run()


if __name__ == "__main__":
    main()
