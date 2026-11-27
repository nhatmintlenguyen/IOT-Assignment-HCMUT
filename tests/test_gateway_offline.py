"""
Offline tests for gateway.py / web_server.py (no hardware, no network: MQTT clients are fakes).
Run:  gateway/.venv/bin/python -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gateway"))
import gateway as gw_module  # noqa: E402
from web_server import LogCaptureTee  # noqa: E402


class FakeInfo:
    def __init__(self, rc):
        self.rc = rc


class FakeClient:
    def __init__(self, connected=True):
        self.connected = connected
        self.published = []

    def publish(self, topic, payload, qos=0):
        if not self.connected:
            return FakeInfo(gw_module.mqtt.MQTT_ERR_NO_CONN)
        self.published.append((topic, json.loads(payload)))
        return FakeInfo(gw_module.mqtt.MQTT_ERR_SUCCESS)


class FakeMsg:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = json.dumps(payload).encode()


def make_gateway():
    g = gw_module.SmartSafeGateway(
        tb_host="127.0.0.1", tb_port=1883, tb_token="LOCALTOKEN123456", serial_port="auto",
        baudrate=115200, mock=False, gw_token=None, disable_telegram=True, disable_web=True)
    g.coreiot_host, g.coreiot_token = "cloud.example", "CLOUDTOKEN987654"
    return g


class TestCoreIotBuffer(unittest.TestCase):
    def test_buffer_then_replay_with_original_timestamps(self):
        g = make_gateway()
        local = FakeClient()
        g.mqtt_client, g.mqtt_connected = local, True
        g.coreiot_client, g.coreiot_connected = FakeClient(connected=False), False

        for i in range(3):
            g._publish_mqtt("v1/devices/me/telemetry", json.dumps({"temp": 28 + i}))
            time.sleep(0.005)
        self.assertEqual(len(local.published), 3)            # local ThingsBoard unaffected
        self.assertEqual(len(g.coreiot_buffer), 3)
        ts_list = [e["ts"] for e in g.coreiot_buffer]
        self.assertEqual(ts_list, sorted(ts_list))

        cloud = FakeClient(connected=True)
        g.coreiot_client, g.coreiot_connected = cloud, True
        g._replay_coreiot_buffer()
        for _ in range(100):
            if not g._coreiot_replaying:
                break
            time.sleep(0.02)
        self.assertEqual(len(g.coreiot_buffer), 0)
        self.assertEqual([p["ts"] for _, p in cloud.published], ts_list)
        self.assertEqual([p["values"]["temp"] for _, p in cloud.published], [28, 29, 30])

    def test_buffer_is_bounded(self):
        g = make_gateway()
        g.coreiot_buffer = gw_module.collections.deque(maxlen=5)
        for i in range(12):
            g._publish_mqtt("v1/devices/me/telemetry", json.dumps({"n": i}))
        self.assertEqual([e["values"]["n"] for e in g.coreiot_buffer], [7, 8, 9, 10, 11])

    def test_no_buffer_without_coreiot_config(self):
        g = make_gateway()
        g.coreiot_token = ""
        g._publish_mqtt("v1/devices/me/telemetry", json.dumps({"temp": 28}))
        self.assertEqual(len(g.coreiot_buffer), 0)


class TestRpcAndTelemetry(unittest.TestCase):
    def test_get_state_uses_real_telemetry(self):
        g = make_gateway()
        g.last_telemetry = {"state": "UNLOCKED", "lockdown": True}
        client = FakeClient()
        g._on_mqtt_message(client, None, FakeMsg("v1/devices/me/rpc/request/7", {"method": "getState", "params": {}}))
        g._on_mqtt_message(client, None, FakeMsg("v1/devices/me/rpc/request/8", {"method": "getLockdown", "params": {}}))
        self.assertEqual(client.published[0], ("v1/devices/me/rpc/response/7", {"status": "ok", "method": "getState", "value": True}))
        self.assertTrue(client.published[1][1]["value"])

    def test_telemetry_keeps_existing_keys_and_adds_ml_fields(self):
        g = make_gateway()
        local = FakeClient()
        g.mqtt_client, g.mqtt_connected = local, True
        g._connection_start_time = time.time() - 60
        line = json.dumps({"type": "telemetry", "temp": 28.0, "hum": 60.0, "climate_valid": True,
                           "light_adc": 150, "distance_cm": 80.0, "state": "LOCKED",
                           "breach": False, "lockdown": False})
        out = io.StringIO()
        old, sys.stdout = sys.stdout, out
        try:
            g.process_incoming_line(line)
        finally:
            sys.stdout = old
        payload = local.published[0][1]
        for key in ("temp", "hum", "light_adc", "distance_cm", "state", "breach", "lockdown",
                    "anomaly", "anomaly_score", "ml_score", "rule_flags"):
            self.assertIn(key, payload)


class TestLogRedaction(unittest.TestCase):
    def test_secrets_and_pin_are_masked_in_web_buffer(self):
        g = make_gateway()
        g.telegram_chat_ids = ["1234567890"]
        tee = LogCaptureTee(io.StringIO(), secrets_provider=g.secrets)
        tee.write("Device Access Token : LOCALTOKEN123456 chat 1234567890\n")
        tee.write('{"type":"event","source":"ir_pin","action":"pin_changed","new_pin":"4321"}\n')
        joined = "\n".join(tee.buffer)
        self.assertNotIn("LOCALTOKEN123456", joined)
        self.assertNotIn("1234567890", joined)
        self.assertNotIn("4321", joined)

    def test_mask_helper(self):
        self.assertEqual(gw_module.SmartSafeGateway._mask("6EzRR6gcTvnOcgVF53hP"), "6EzR…")
        self.assertEqual(gw_module.SmartSafeGateway._mask(""), "(none)")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    unittest.main()
