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
import sys
import time
import threading
import paho.mqtt.client as mqtt

# Ensure unbuffered output for logging and service daemons
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# Local AI Anomaly Detector
try:
    from anomaly_detector import VaultAnomalyDetector
except ImportError:
    from gateway.anomaly_detector import VaultAnomalyDetector


class SmartSafeGateway:
    def __init__(self, tb_host, tb_port, tb_token, serial_port, baudrate, mock=False):
        self.tb_host = tb_host
        self.tb_port = tb_port
        self.tb_token = tb_token
        self.serial_port_name = serial_port
        self.baudrate = baudrate
        self.mock_mode = mock

        self.serial_conn = None
        self.mqtt_client = None
        self.running = True
        self.detector = VaultAnomalyDetector()

        # Simulated mock state
        self.mock_state = {
            "temp": 28.4,
            "hum": 64.5,
            "light_adc": 135,
            "distance_cm": 45.0,
            "state": "LOCKED",
            "breach": False,
            "lockdown": False
        }

    # --------------------------------------------------------------------------
    # SERIAL COMMUNICATION (YoloUNO <--> Gateway)
    # --------------------------------------------------------------------------
    def _find_serial_port(self):
        """Auto-detects USB serial ports on Linux, macOS, and Windows."""
        if self.serial_port_name and self.serial_port_name.lower() != "auto":
            return self.serial_port_name

        candidates = (
            glob.glob("/dev/ttyACM*") +
            glob.glob("/dev/ttyUSB*") +
            glob.glob("/dev/cu.usb*") +
            glob.glob("/dev/cu.wch*")
        )
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
        print(f"[TX -> YoloUNO] Command: '{command_clean}'")

        if self.mock_mode:
            if command_clean == "unlock":
                self.mock_state["state"] = "UNLOCKED"
            elif command_clean == "lock":
                self.mock_state["state"] = "LOCKED"
            elif command_clean in ("ack", "reset"):
                self.mock_state["breach"] = False
            elif command_clean == "lockdown 1":
                self.mock_state["lockdown"] = True
                self.mock_state["state"] = "LOCKED"
            elif command_clean == "lockdown 0":
                self.mock_state["lockdown"] = False
            return

        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((command_clean + "\n").encode("utf-8"))
                self.serial_conn.flush()
            except Exception as e:
                print(f"[ERROR] Serial write error: {e}")

    # --------------------------------------------------------------------------
    # MQTT COMMUNICATION (Gateway <--> ThingsBoard)
    # --------------------------------------------------------------------------
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
            return True
        except Exception as e:
            print(f"[ERROR] Could not connect to ThingsBoard MQTT broker: {e}")
            return False

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        rc_code = rc if isinstance(rc, int) else getattr(rc, "value", rc)
        if rc_code == 0:
            print("[MQTT] Connected to ThingsBoard successfully!")
            # Subscribe to remote RPC commands from Dashboard widgets
            client.subscribe("v1/devices/me/rpc/request/+")
            print("[MQTT] Subscribed to RPC requests: 'v1/devices/me/rpc/request/+'")
        else:
            print(f"[MQTT] Connection refused with code {rc_code}")

    def _on_mqtt_disconnect(self, client, userdata, disconnect_flags_or_rc, properties=None):
        print("[MQTT] Disconnected from ThingsBoard broker. Reconnecting...")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handles incoming RPC calls from ThingsBoard dashboard."""
        topic = msg.topic
        payload_str = msg.payload.decode("utf-8")
        print(f"\n[RX <- ThingsBoard RPC] Topic: {topic} | Payload: {payload_str}")

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
            self.write_serial("unlock")
            response_payload["state"] = "UNLOCKED"
        elif method == "lock" or (method == "setLockState" and params is False):
            self.write_serial("lock")
            response_payload["state"] = "LOCKED"
        elif method in ("ack", "ackBreach", "reset"):
            self.write_serial("ack")
            response_payload["breach"] = False
        elif method == "setLockdown":
            is_active = bool(params) if isinstance(params, bool) else (str(params).lower() in ("true", "1"))
            self.write_serial(f"lockdown {1 if is_active else 0}")
            response_payload["lockdown"] = is_active
        else:
            print(f"[WARN] Unknown RPC method: '{method}'")
            response_payload["status"] = "unknown_method"

        # Reply to ThingsBoard RPC response topic
        resp_topic = f"v1/devices/me/rpc/response/{req_id}"
        self.mqtt_client.publish(resp_topic, json.dumps(response_payload))
        print(f"[TX -> ThingsBoard RPC] Response sent to {resp_topic}: {response_payload}")

    # --------------------------------------------------------------------------
    # PROCESSING LOOPS
    # --------------------------------------------------------------------------
    def process_incoming_line(self, line):
        """Parses a single JSON line received from YoloUNO."""
        line = line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            return

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return

        msg_type = obj.get("type", "")

        # 1. Telemetry streaming frame (emitted every 2 seconds by YoloUNO)
        if msg_type == "telemetry":
            # Run Edge AI anomaly evaluation (T09)
            is_anomaly, anomaly_score, reason = self.detector.evaluate(obj)
            obj["anomaly"] = is_anomaly
            obj["anomaly_score"] = anomaly_score
            obj["anomaly_reason"] = reason

            payload = json.dumps(obj)
            self.mqtt_client.publish("v1/devices/me/telemetry", payload)

            status_color = "\033[92m" if obj.get("state") == "UNLOCKED" else "\033[94m"
            breach_alert = " \033[91m[BREACH ALERT!]\033[0m" if obj.get("breach") else ""
            lockdown_tag = " \033[95m[LOCKDOWN]\033[0m" if obj.get("lockdown") else ""
            anomaly_tag = f" \033[93m[AI ANOMALY: {reason} ({anomaly_score})]\033[0m" if is_anomaly else ""

            print(f"[TELEMETRY] Temp: {obj.get('temp'):.1f}°C | Hum: {obj.get('hum'):.1f}% | "
                  f"Light: {obj.get('light_adc')} | Dist: {obj.get('distance_cm'):.1f}cm | "
                  f"State: {status_color}{obj.get('state')}\033[0m{breach_alert}{lockdown_tag}{anomaly_tag}")

        # 2. Asynchronous Security Events (Access granted, bad PIN, auto-lock, etc.)
        elif msg_type == "event":
            source = obj.get("source", "system")
            action = obj.get("action") or obj.get("result") or obj.get("event")
            print(f"\033[96m[EVENT] Source: {source} | Action: {action}\033[0m")
            self.mqtt_client.publish("v1/devices/me/telemetry", json.dumps({"event": action, "source": source}))

        # 3. Critical Security Alarms (Bruteforce detected, Light breach)
        elif msg_type == "alarm":
            alarm_name = obj.get("alarm", "unknown_alarm")
            action = obj.get("action", "")
            print(f"\033[91;1m[CRITICAL ALARM] {alarm_name.upper()} | Action: {action}\033[0m")
            self.mqtt_client.publish("v1/devices/me/telemetry", json.dumps({
                "critical_alarm": alarm_name,
                "alarm_active": True
            }))

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
                "lockdown": self.mock_state["lockdown"]
            })
            self.process_incoming_line(mock_line)

    def run(self):
        """Main gateway execution lifecycle."""
        print("=========================================================")
        print("    Smart Safe Guardian - IoT Gateway Daemon (T08/T15)   ")
        print("=========================================================")
        print(f"Target ThingsBoard Host : {self.tb_host}:{self.tb_port}")
        print(f"Device Access Token     : {self.tb_token}")

        self.connect_mqtt()

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
    parser.add_argument("--host", default=os.getenv("THINGSBOARD_HOST", "127.0.0.1"),
                        help="ThingsBoard MQTT Broker host IP (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("THINGSBOARD_PORT", "1883")),
                        help="ThingsBoard MQTT port (default: 1883)")
    parser.add_argument("--token", default=os.getenv("THINGSBOARD_TOKEN", "6EzRR6gcTvnOcgVF53hP"),
                        help="ThingsBoard Device Access Token")
    parser.add_argument("--serial-port", default=os.getenv("SERIAL_PORT", "auto"),
                        help="Serial port for YoloUNO (default: auto)")
    parser.add_argument("--baudrate", type=int, default=int(os.getenv("SERIAL_BAUDRATE", "115200")),
                        help="Serial baudrate (default: 115200)")
    parser.add_argument("--mock", action="store_true",
                        help="Run with mock telemetry (no hardware required)")

    args = parser.parse_args()

    gateway = SmartSafeGateway(
        tb_host=args.host,
        tb_port=args.port,
        tb_token=args.token,
        serial_port=args.serial_port,
        baudrate=args.baudrate,
        mock=args.mock
    )
    gateway.run()


if __name__ == "__main__":
    main()
