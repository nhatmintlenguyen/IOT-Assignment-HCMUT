"""
Smart Safe Guardian - Comprehensive System Benchmark & Testing Harness
Supports two execution modes:
  1. --live : Real hardware test (connects to the physical YoloUNO over USB CDC serial,
              measures the telemetry frame interval and the serial command round-trip
              gateway -> YoloUNO -> gateway).
  2. --mock : Software-in-the-loop (SIL) run without hardware (default).

Every row of Table 4.1 carries a "Source" label:
  LIVE       measured on the physical hardware / real network service
  MEASURED   measured on the host running this script (AI model, synthetic test set)
  SIMULATED  produced by a statistical simulation (NOT a measurement)
  N/A        not measured in this run
Verdicts (PASS / FAIL) are computed from the value and the target; rows without a
measurement get "N/A".

  --rebuild FILE : recompute the table (sources + verdicts) of an existing result
                   file from its "detailed_metrics" section, without re-running tests.
"""

import sys
import os
import time
import json
import argparse
import platform
import urllib.request
import urllib.parse
from pathlib import Path
import numpy as np

# Ensure gateway modules can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "gateway"))

from anomaly_detector import VaultAnomalyDetector

try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except ImportError:
    HAS_SERIAL = False


VECTOR_NAMES = ["optical_drill", "heat_torch", "cryogenic_freeze", "flooding", "loitering", "breach_flag"]


class BenchmarkHarness:
    def __init__(self, mode="mock", serial_port="auto", baudrate=115200):
        self.mode = mode
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.detector = VaultAnomalyDetector()
        self.results = {}

    def find_serial_port(self):
        """Auto-detects YoloUNO USB CDC serial port."""
        if not HAS_SERIAL:
            return None

        if self.serial_port and self.serial_port != "auto":
            if os.path.exists(self.serial_port):
                return self.serial_port

        # Scan system serial ports
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            dev = p.device
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            if "acm" in dev.lower() or "espressif" in desc or "usb jtag" in desc or "303a:" in hwid:
                return dev

        # Fallback to direct device paths
        for path in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]:
            if os.path.exists(path):
                return path

        return None

    # =========================================================================
    # 1. Edge AI Model Benchmark (T09) - Both Live & Mock
    # =========================================================================
    def benchmark_edge_ai(self, n_normal=2000, n_anomaly=500):
        print("\n" + "=" * 70)
        print("  1. BENCHMARK: Edge AI Anomaly Detector (Isolation Forest - T09)")
        print("=" * 70)

        np.random.seed(101)

        normal_samples = []
        for _ in range(n_normal):
            is_unlocked = np.random.choice([0, 1], p=[0.75, 0.25])
            light_adc = (
                np.random.normal(140.0, 30.0) if is_unlocked == 0
                else np.random.normal(450.0, 100.0)
            )
            # Access (unlocked) happens during working hours, mostly around midday;
            # a locked vault is normal at any hour.
            # (same schedule as the training baseline: N(13.5 h, 2.5 h) truncated to [8 h, 20 h)).
            if is_unlocked == 1:
                hour = np.random.normal(13.5, 2.5)
                while not (8.0 <= hour < 20.0):
                    hour = np.random.normal(13.5, 2.5)
            else:
                hour = np.random.uniform(0.0, 24.0)
            hour = round(float(hour), 2)
            normal_samples.append({
                "hour": hour,
                "temp": round(float(np.random.normal(26.5, 2.0)), 1),
                "hum": round(float(np.random.normal(62.0, 5.0)), 1),
                "light_adc": int(np.clip(light_adc, 30, 800)),
                "distance_cm": round(float(np.random.normal(50.0, 12.0)), 1),
                "state": "UNLOCKED" if is_unlocked == 1 else "LOCKED",
                "breach": False,
                "ground_truth": 0
            })

        anomaly_samples = []
        for i in range(n_anomaly):
            vector = i % 6
            if vector == 0:
                sample = {
                    "temp": round(float(np.random.normal(27.0, 1.5)), 1),
                    "hum": round(float(np.random.normal(60.0, 4.0)), 1),
                    "light_adc": int(np.random.uniform(750, 2200)),
                    "distance_cm": round(float(np.random.normal(45.0, 10.0)), 1),
                    "state": "LOCKED",
                    "breach": False,
                    "ground_truth": 1
                }
            elif vector == 1:
                sample = {
                    "temp": round(float(np.random.uniform(37.5, 68.0)), 1),
                    "hum": round(float(np.random.uniform(30.0, 55.0)), 1),
                    "light_adc": int(np.random.uniform(50, 300)),
                    "distance_cm": round(float(np.random.normal(40.0, 10.0)), 1),
                    "state": "LOCKED",
                    "breach": False,
                    "ground_truth": 1
                }
            elif vector == 2:
                sample = {
                    "temp": round(float(np.random.uniform(-5.0, 11.5)), 1),
                    "hum": round(float(np.random.uniform(60.0, 85.0)), 1),
                    "light_adc": int(np.random.uniform(50, 250)),
                    "distance_cm": round(float(np.random.normal(45.0, 10.0)), 1),
                    "state": "LOCKED",
                    "breach": False,
                    "ground_truth": 1
                }
            elif vector == 3:
                sample = {
                    "temp": round(float(np.random.normal(25.0, 2.0)), 1),
                    "hum": round(float(np.random.uniform(87.0, 99.0)), 1),
                    "light_adc": int(np.random.uniform(50, 300)),
                    "distance_cm": round(float(np.random.normal(50.0, 10.0)), 1),
                    "state": "LOCKED",
                    "breach": False,
                    "ground_truth": 1
                }
            elif vector == 4:
                sample = {
                    "temp": round(float(np.random.normal(26.5, 1.5)), 1),
                    "hum": round(float(np.random.normal(62.0, 4.0)), 1),
                    "light_adc": int(np.random.uniform(50, 300)),
                    "distance_cm": round(float(np.random.uniform(2.0, 8.5)), 1),
                    "state": "LOCKED",
                    "breach": False,
                    "ground_truth": 1
                }
            else:
                sample = {
                    "temp": round(float(np.random.normal(26.5, 2.0)), 1),
                    "hum": round(float(np.random.normal(62.0, 5.0)), 1),
                    "light_adc": int(np.random.uniform(300, 1500)),
                    "distance_cm": round(float(np.random.normal(20.0, 5.0)), 1),
                    "state": "LOCKED",
                    "breach": True,
                    "ground_truth": 1
                }
            sample["hour"] = round(float(np.random.uniform(0.0, 24.0)), 2)  # attacks can happen at any time
            sample["vector"] = VECTOR_NAMES[vector]
            anomaly_samples.append(sample)

        all_samples = normal_samples + anomaly_samples
        y_true = [s["ground_truth"] for s in all_samples]

        y_pred = []
        source_counts = {"ML": 0, "RULES": 0, "ML+RULES": 0}
        per_vector = {}
        for s in all_samples:
            det = self.detector.evaluate_detailed(s)
            y_pred.append(1 if det["is_anomaly"] else 0)
            if det["is_anomaly"]:
                source_counts[det["source"]] += 1
            if s["ground_truth"] == 1:
                v = per_vector.setdefault(s["vector"], {"n": 0, "detected": 0})
                v["n"] += 1
                v["detected"] += int(det["is_anomaly"])

        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
        tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

        total = len(y_true)
        accuracy = (tp + tn) / total * 100.0
        precision = (tp / (tp + fp) * 100.0) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn) * 100.0) if (tp + fn) > 0 else 0.0
        f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        specificity = (tn / (tn + fp) * 100.0) if (tn + fp) > 0 else 0.0

        latencies_ms = []
        test_payload = {
            "temp": 26.5, "hum": 62.0, "light_adc": 135,
            "distance_cm": 48.0, "state": "LOCKED", "breach": False
        }
        for _ in range(1000):
            t0 = time.perf_counter()
            self.detector.evaluate(test_payload)
            latencies_ms.append((time.perf_counter() - t0) * 1000.0)

        lat_mean = float(np.mean(latencies_ms))
        lat_min = float(np.min(latencies_ms))
        lat_max = float(np.max(latencies_ms))
        lat_p95 = float(np.percentile(latencies_ms, 95))

        print(f"  Total Test Samples   : {total} ({n_normal} normal, {n_anomaly} anomalous)")
        print(f"  Confusion Matrix     : TP={tp}, TN={tn}, FP={fp}, FN={fn}")
        print(f"  Accuracy             : {accuracy:.2f}% (Target: > 95.0%)")
        print(f"  Precision            : {precision:.2f}%")
        print(f"  Recall (Sensitivity) : {recall:.2f}%")
        print(f"  F1-Score             : {f1_score:.2f}%")
        print(f"  Specificity          : {specificity:.2f}%")
        print(f"  Inference Latency    : Mean {lat_mean:.2f} ms | P95 {lat_p95:.2f} ms | Min/Max {lat_min:.2f}/{lat_max:.2f} ms")
        print(f"  Detections by source : ML only={source_counts['ML']}, rules only={source_counts['RULES']}, both={source_counts['ML+RULES']}")
        for name, v in per_vector.items():
            print(f"    - {name:<17}: {v['detected']}/{v['n']} detected")

        # Separate scenario (NOT part of the 2500-sample set): door opened outside working
        # hours with otherwise normal values. No rule can see it; only the ML model can.
        n_night, ml_hits = 100, 0
        for _ in range(n_night):
            night_hour = float(np.random.uniform(-3.5, 7.0)) % 24.0  # 20:30 -> 07:00
            det = self.detector.evaluate_detailed({
                "hour": round(night_hour, 2),
                "temp": round(float(np.random.normal(27.0, 1.5)), 1),
                "hum": round(float(np.random.normal(62.0, 4.0)), 1),
                "light_adc": int(np.random.uniform(800, 3800)),
                "distance_cm": round(float(np.random.uniform(15.0, 35.0)), 1),
                "state": "UNLOCKED", "breach": False})
            ml_hits += int(det["source"] == "ML")
        print(f"  ML-only scenario     : night opening (20:30-07:00) detected by ML alone {ml_hits}/{n_night}")
        print("                         (separate scenario, not included in the 2500-sample metrics)")

        self.results["ai_benchmark"] = {
            "n_samples": total,
            "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "accuracy_pct": round(accuracy, 2),
            "precision_pct": round(precision, 2),
            "recall_pct": round(recall, 2),
            "f1_score_pct": round(f1_score, 2),
            "specificity_pct": round(specificity, 2),
            "latency_mean_ms": round(lat_mean, 2),
            "latency_min_ms": round(lat_min, 2),
            "latency_max_ms": round(lat_max, 2),
            "latency_p95_ms": round(lat_p95, 2),
            "n_latency_trials": len(latencies_ms),
            "detections_by_source": source_counts,
            "recall_by_vector": per_vector,
            "ml_only_night_opening": {"n": n_night, "detected_by_ml_alone": ml_hits},
            "test_set": "synthetic (seed 101): 2000 normal + 500 attack vectors",
            "host": platform.platform()
        }

    # =========================================================================
    # 2. Live Hardware Benchmark Protocol (--live)
    # =========================================================================
    def benchmark_live_hardware(self, port, n_telemetry=20):
        print("\n" + "=" * 70)
        print("  2. LIVE HARDWARE BENCHMARK: Physical Microcontroller Testing")
        print(f"     Target Serial Port: {port} @ {self.baudrate} baud")
        print("=" * 70)

        try:
            ser = serial.Serial(port, self.baudrate, timeout=1.5)
            time.sleep(1.0)
            ser.reset_input_buffer()
        except Exception as e:
            print(f"  [ERROR] Failed to open physical serial port {port}: {e}")
            return False

        # Phase A: Real Telemetry Reading & Sensor Timing
        print(f"\n  [PHASE A] Sampling {n_telemetry} real telemetry frames from sensors...")
        telemetry_samples = []
        frame_intervals_ms = []
        last_frame_time = None

        start_wait = time.time()
        while len(telemetry_samples) < n_telemetry and (time.time() - start_wait < (n_telemetry * 3 + 5)):
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            now = time.perf_counter()
            if last_frame_time is not None:
                frame_intervals_ms.append((now - last_frame_time) * 1000.0)
            last_frame_time = now

            if line.startswith("{") and "telemetry" in line:
                try:
                    payload = json.loads(line)
                    telemetry_samples.append(payload)
                    t = payload.get("temp", 0)
                    h = payload.get("hum", 0)
                    l = payload.get("light_adc", 0)
                    d = payload.get("distance_cm", 0)
                    st = payload.get("state", "UNKNOWN")
                    print(f"    Frame #{len(telemetry_samples):02d}: Temp={t:.1f}°C, Hum={h:.1f}%, Light={l} ADC, Dist={d:.1f}cm, State={st}")
                except Exception:
                    pass

        if not telemetry_samples:
            print("  [ERROR] No valid JSON telemetry frames received from YoloUNO.")
            ser.close()
            return False

        mean_interval = float(np.mean(frame_intervals_ms)) if frame_intervals_ms else 2000.0
        print(f"  --> Real Telemetry Streaming Rate: Mean {mean_interval:.1f} ms (~0.5 Hz)")

        # Phase B: Real Serial RPC Round-Trip to Servomotor & Buzzer
        print("\n  [PHASE B] Testing real hardware RPC round-trip commands...")
        rpc_commands = [
            ("lock", b"lock\n", ["LOCKED", "ALREADY_LOCKED"]),
            ("unlock", b"unlock\n", ["UNLOCKED", "ALREADY_UNLOCKED"]),
            ("lock", b"lock\n", ["LOCKED", "ALREADY_LOCKED"]),
            ("lockdown_on", b"lockdown 1\n", ["LOCKDOWN"]),
            ("lockdown_off", b"lockdown 0\n", ["LOCKDOWN"]),
            ("ack_alarm", b"ack\n", ["ACK", "CLEARED"])
        ]

        live_rpc_latencies = []
        for name, cmd_bytes, expected_keywords in rpc_commands:
            ser.reset_input_buffer()
            t0 = time.perf_counter()
            ser.write(cmd_bytes)
            ser.flush()

            # Wait for physical microcontroller response
            resp_line = ""
            resp_deadline = time.time() + 2.0
            matched = False
            while time.time() < resp_deadline:
                l = ser.readline().decode("utf-8", errors="ignore").strip()
                if any(kw in l.upper() for kw in expected_keywords):
                    resp_line = l
                    matched = True
                    break

            rtt_ms = (time.perf_counter() - t0) * 1000.0
            live_rpc_latencies.append(rtt_ms)
            status = "PASS" if matched else "TIMEOUT/WARN"
            print(f"    RPC '{name:<9}': {rtt_ms:6.2f} ms | Microcontroller Response: '{resp_line[:40]}' [{status}]")
            time.sleep(0.5)

        ser.close()

        rpc_mean = float(np.mean(live_rpc_latencies))
        rpc_min = float(np.min(live_rpc_latencies))
        rpc_max = float(np.max(live_rpc_latencies))

        self.results["live_hardware"] = {
            "n_telemetry_frames": len(telemetry_samples),
            "n_rpc_trials": len(live_rpc_latencies),
            "telemetry_interval_ms": round(mean_interval, 1),
            "rpc_latency_mean_ms": round(rpc_mean, 2),
            "rpc_latency_min_ms": round(rpc_min, 2),
            "rpc_latency_max_ms": round(rpc_max, 2)
        }
        return True

    # =========================================================================
    # 3. Simulated Gateway & Remote Benchmarks (for SIL or network)
    # =========================================================================
    def benchmark_gateway_pipeline(self, n_trials=1000):
        print("\n" + "=" * 70)
        print("  3. BENCHMARK: Gateway Serialization & Pipeline (T08, T15)")
        print("=" * 70)

        raw_serial_line = '{"type":"telemetry","temp":27.3,"hum":63.1,"light_adc":145,"distance_cm":42.5,"state":"LOCKED","breach":false,"lockdown":false}'

        latencies_us = []
        for _ in range(n_trials):
            t0 = time.perf_counter()
            data = json.loads(raw_serial_line)
            is_anomaly, score, reason = self.detector.evaluate(data)
            data["anomaly"] = is_anomaly
            data["anomaly_score"] = score
            if is_anomaly:
                data["anomaly_reason"] = reason
            _ = json.dumps(data)
            latencies_us.append((time.perf_counter() - t0) * 1_000_000.0)

        mean_ms = float(np.mean(latencies_us)) / 1000.0
        min_ms = float(np.min(latencies_us)) / 1000.0
        max_ms = float(np.max(latencies_us)) / 1000.0
        throughput = 1000.0 / mean_ms

        print(f"  Trials               : {n_trials}")
        print(f"  Pipeline Latency     : Mean {mean_ms:.3f} ms | Min {min_ms:.3f} ms | Max {max_ms:.3f} ms")
        print(f"  Processing Capacity  : {throughput:.0f} frames/sec")

        self.results["gateway_pipeline"] = {
            "n_trials": n_trials,
            "mean_ms": round(mean_ms, 3),
            "min_ms": round(min_ms, 3),
            "max_ms": round(max_ms, 3),
            "throughput_fps": round(throughput, 1)
        }

    def benchmark_telegram_alert(self):
        print("\n" + "=" * 70)
        print("  4. BENCHMARK: Telegram Alert Notification Dispatch (T13)")
        print("=" * 70)

        env_path = PROJECT_ROOT / ".env"
        bot_token = None
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_TOKEN=") or line.startswith("TELEGRAM_BOT_TOKEN="):
                    bot_token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

        dispatch_latencies = []
        if bot_token and len(bot_token) > 20 and not bot_token.startswith("your_"):
            print("  [LIVE TEST] Querying Telegram Bot API endpoint...")
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            for _ in range(5):
                t0 = time.perf_counter()
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "SmartSafeGuardian/1.0"})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        _ = response.read()
                    dispatch_latencies.append((time.perf_counter() - t0) * 1000.0)
                except Exception as e:
                    print(f"  [WARN] Telegram ping warning: {e}")
                    break

        telegram_source = "LIVE" if dispatch_latencies else "SIMULATED"
        if not dispatch_latencies:
            print("  [SIMULATED] No Telegram token: simulating a WAN round-trip (NOT a measurement)...")
            for _ in range(10):
                t0 = time.perf_counter()
                alert_html = "<b>🚨 SECURITY ALERT: Vault Breach Detected!</b>"
                _ = urllib.parse.urlencode({"chat_id": 123456789, "text": alert_html, "parse_mode": "HTML"})
                time.sleep(np.random.normal(0.240, 0.030))
                dispatch_latencies.append((time.perf_counter() - t0) * 1000.0)

        mean_ms = float(np.mean(dispatch_latencies))
        min_ms = float(np.min(dispatch_latencies))
        max_ms = float(np.max(dispatch_latencies))

        print(f"  Trials               : {len(dispatch_latencies)}")
        print(f"  Telegram Latency     : Mean {mean_ms:.1f} ms | Min {min_ms:.1f} ms | Max {max_ms:.1f} ms")
        print(f"  Target Latency       : < 1500 ms")

        self.results["telegram_alert"] = {
            "source": telegram_source,
            "method": "Bot API getMe HTTPS round-trip" if telegram_source == "LIVE" else "time.sleep(N(240 ms, 30 ms)) simulation",
            "n_trials": len(dispatch_latencies),
            "mean_ms": round(mean_ms, 1),
            "min_ms": round(min_ms, 1),
            "max_ms": round(max_ms, 1)
        }

    def benchmark_esp_now(self, n_packets=1000):
        """
        SIMULATION ONLY (Monte-Carlo with a 1.2 % raw loss rate and 3 retries).
        The ESP-NOW link is not instrumented by this harness, so this is NOT a measurement,
        even in --live mode. It is labelled SIMULATED in Table 4.1.
        """
        print("\n" + "=" * 70)
        print("  5. SIMULATION: ESP-NOW Wireless Transmission Reliability (T06) [SIMULATED]")
        print("=" * 70)

        np.random.seed(42)
        raw_loss_rate = 0.012
        max_retries = 3

        delivered = 0
        latencies_ms = []

        for _ in range(n_packets):
            attempt = 0
            success = False
            base_latency = np.random.normal(2.4, 0.4)

            while attempt < max_retries and not success:
                attempt += 1
                if np.random.rand() > raw_loss_rate:
                    success = True
                    latencies_ms.append(base_latency + (attempt - 1) * 3.5)

            if success:
                delivered += 1

        effective_loss_pct = (n_packets - delivered) / n_packets * 100.0
        pdr_pct = delivered / n_packets * 100.0
        mean_lat = float(np.mean(latencies_ms))
        min_lat = float(np.min(latencies_ms))
        max_lat = float(np.max(latencies_ms))

        print(f"  Transmitted Packets  : {n_packets}")
        print(f"  Packets Delivered    : {delivered} ({pdr_pct:.2f}% Delivery Ratio)")
        print(f"  Effective Loss Rate  : {effective_loss_pct:.2f}% (Target: < 2.0%)")
        print(f"  Transmission Latency : Mean {mean_lat:.2f} ms | Min {min_lat:.2f} ms | Max {max_lat:.2f} ms")

        self.results["esp_now"] = {
            "source": "SIMULATED",
            "n_packets": n_packets,
            "delivered": delivered,
            "pdr_pct": round(pdr_pct, 2),
            "loss_pct": round(effective_loss_pct, 2),
            "mean_latency_ms": round(mean_lat, 2),
            "min_latency_ms": round(min_lat, 2),
            "max_latency_ms": round(max_lat, 2)
        }

    # =========================================================================
    # 4. Summary Table 4.1
    # =========================================================================
    def generate_report_table(self, out_path=None):
        rows = build_table_rows(self.results, self.mode)
        print_table(rows, self.mode)
        out_path = Path(out_path) if out_path else DEFAULT_OUTPUT
        write_results(out_path, self.mode, rows, self.results)


# =========================================================================
# Table 4.1 construction (shared by live/mock runs and --rebuild)
# =========================================================================
DEFAULT_OUTPUT = PROJECT_ROOT / "docs" / "benchmarks" / "benchmark_results.json"
TABLE_HEADER = ["No.", "Metric", "Trials", "Mean", "Min / Max", "Target", "Source", "Status"]


def _verdict(value, op, target, source="MEASURED"):
    # A simulation is not evidence: no PASS/FAIL verdict for simulated rows.
    if value is None or str(source).startswith("SIMULATED"):
        return "N/A"
    ok = value < target if op == "<" else value > target
    return "PASS" if ok else "FAIL"


def _wilson_ci(p_hat, n, z=1.96):
    """95 % Wilson confidence interval for a proportion (returned in %)."""
    if n == 0:
        return 0.0, 0.0
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    half = z * ((p_hat * (1 - p_hat) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (centre - half) * 100.0, (centre + half) * 100.0


def build_table_rows(results, mode):
    rows = []
    live = results.get("live_hardware") if mode == "live" else None

    # 1. Sensor -> dashboard latency: requires timestamps on the ThingsBoard side,
    #    which this harness does not collect. Never estimated.
    rows.append(["1", "Sensor -> dashboard latency (ms)", "-", "-", "-", "< 200 ms", "N/A", "N/A"])

    # 2. ESP-NOW packet loss (Monte-Carlo simulation)
    esp = results.get("esp_now")
    if esp:
        rows.append(["2", "ESP-NOW packet loss (%)", str(esp["n_packets"]), f"{esp['loss_pct']:.2f}", "-",
                     "< 2.0 %", esp.get("source", "SIMULATED"), _verdict(esp["loss_pct"], "<", 2.0, esp.get("source", "SIMULATED"))])
    else:
        rows.append(["2", "ESP-NOW packet loss (%)", "-", "-", "-", "< 2.0 %", "N/A", "N/A"])

    # 3-4. AI model (measured on the host, synthetic test set)
    ai = results["ai_benchmark"]
    acc = ai["accuracy_pct"]
    lo, hi = _wilson_ci(acc / 100.0, ai["n_samples"])
    rows.append(["3", "AI model accuracy (%) [95% CI]", str(ai["n_samples"]), f"{acc:.2f}", f"{lo:.2f} / {hi:.2f}",
                 "> 95.0 %", "MEASURED (synthetic set)", _verdict(acc, ">", 95.0)])
    rows.append(["4", "AI inference latency (ms)", str(ai.get("n_latency_trials", 1000)), f"{ai['latency_mean_ms']:.2f}",
                 f"{ai['latency_min_ms']:.2f} / {ai['latency_max_ms']:.2f}", "< 10 ms", "MEASURED (host)",
                 _verdict(ai["latency_mean_ms"], "<", 10.0)])

    # 5. Serial command round-trip gateway -> YoloUNO -> gateway (live only)
    if live:
        rows.append(["5", "Serial command round-trip (ms)", str(live["n_rpc_trials"]), f"{live['rpc_latency_mean_ms']:.1f}",
                     f"{live['rpc_latency_min_ms']:.1f} / {live['rpc_latency_max_ms']:.1f}", "< 150 ms",
                     "LIVE (USB serial)", _verdict(live["rpc_latency_mean_ms"], "<", 150.0)])
    else:
        rows.append(["5", "Serial command round-trip (ms)", "-", "-", "-", "< 150 ms", "N/A", "N/A"])

    # 6. Telegram Bot API round-trip
    tg = results.get("telegram_alert")
    if tg:
        rows.append(["6", "Telegram API round-trip (ms)", str(tg["n_trials"]), f"{tg['mean_ms']:.1f}",
                     f"{tg['min_ms']:.1f} / {tg['max_ms']:.1f}", "< 1500 ms",
                     "LIVE (getMe)" if tg.get("source", "LIVE") == "LIVE" else tg["source"],
                     _verdict(tg["mean_ms"], "<", 1500.0, tg.get("source", "LIVE"))])
    return rows


def print_table(rows, mode):
    mode_label = "PHYSICAL HARDWARE" if mode == "live" else "SOFTWARE-IN-THE-LOOP (no hardware)"
    print("\n" + "=" * 70)
    print(f"  SUMMARY: Table 4.1 System Measurement Data [{mode_label}]")
    print("=" * 70)
    widths = [3, 32, 6, 8, 15, 10, 24, 6]
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in widths) + " |"
    print(fmt.format(*TABLE_HEADER))
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for r in rows:
        print(fmt.format(*r))


def write_results(out_path, mode, rows, results):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_mode": mode,
            "table_4_1_header": TABLE_HEADER,
            "table_4_1_rows": rows,
            "detailed_metrics": results
        }, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Benchmark results written to: {out_path}")


def rebuild(path):
    """Recompute Table 4.1 (sources + verdicts) of an existing result file."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    results = data["detailed_metrics"]
    results.setdefault("esp_now", {}).setdefault("source", "SIMULATED")
    if "telegram_alert" in results:
        results["telegram_alert"].setdefault("source", "LIVE")
    rows = build_table_rows(results, data.get("test_mode", "mock"))
    print_table(rows, data.get("test_mode", "mock"))
    write_results(path, data.get("test_mode", "mock"), rows, results)


def main():
    parser = argparse.ArgumentParser(description="Smart Safe Guardian System Benchmark")
    parser.add_argument("--live", action="store_true", help="Run benchmark with physical hardware connected over USB")
    parser.add_argument("--mock", action="store_true", help="Run software-in-the-loop (SIL) simulation benchmark (default)")
    parser.add_argument("--port", default="auto", help="Serial port for physical YoloUNO (default: auto)")
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate (default: 115200)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Result JSON path (default: docs/benchmarks/benchmark_results.json)")
    parser.add_argument("--rebuild", metavar="FILE", help="Recompute Table 4.1 of an existing result file and exit")
    args = parser.parse_args()

    if args.rebuild:
        rebuild(args.rebuild)
        return

    mode = "live" if args.live else "mock"
    harness = BenchmarkHarness(mode=mode, serial_port=args.port, baudrate=args.baudrate)

    if mode == "live":
        port = harness.find_serial_port()
        if not port:
            print("\n" + "=" * 70)
            print("  [ERROR] No physical microcontroller detected!")
            print("=" * 70)
            print("  Could not find any USB CDC device on /dev/ttyACM* or /dev/ttyUSB*.")
            print("  Please connect the YoloUNO board via USB and verify with 'make ports'.")
            print("  You can also specify the port manually, e.g.:")
            print("    make benchmark ARGS=\"--live --port /dev/ttyACM0\"")
            print("\n  Falling back to simulated/mock mode for this run.")
            print("=" * 70)
            harness.mode = "mock"

    harness.benchmark_edge_ai()

    if harness.mode == "live":
        harness.benchmark_live_hardware(port)
    else:
        harness.benchmark_gateway_pipeline()

    harness.benchmark_telegram_alert()
    harness.benchmark_esp_now()
    harness.generate_report_table(args.output)


if __name__ == "__main__":
    main()
