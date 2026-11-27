"""
Unit tests for the Edge AI anomaly detector (T09). No hardware required.
Run:  gateway/.venv/bin/python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gateway"))
from anomaly_detector import VaultAnomalyDetector  # noqa: E402

NORMAL_DAY_LOCKED = dict(hour=14, temp=28.0, hum=60.0, light_adc=150, distance_cm=80.0, state="LOCKED", breach=False)
NORMAL_NIGHT_LOCKED = dict(hour=3, temp=27.0, hum=65.0, light_adc=120, distance_cm=120.0, state="LOCKED", breach=False)
LEGIT_ACCESS_10H = dict(hour=10, temp=28.0, hum=60.0, light_adc=1500, distance_cm=25.0, state="UNLOCKED", breach=False)
NIGHT_OPENING_03H = dict(hour=3, temp=28.0, hum=60.0, light_adc=3600, distance_cm=20.0, state="UNLOCKED", breach=False)


class TestVaultAnomalyDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = VaultAnomalyDetector()

    def test_normal_frames_are_not_anomalies(self):
        for frame in (NORMAL_DAY_LOCKED, NORMAL_NIGHT_LOCKED, LEGIT_ACCESS_10H):
            r = self.d.evaluate_detailed(frame)
            self.assertFalse(r["is_anomaly"], frame)
            self.assertLess(r["anomaly_score"], 0.50)

    def test_ml_alone_detects_night_opening(self):
        """Every physical value is normal; only the Isolation Forest can flag it."""
        r = self.d.evaluate_detailed(NIGHT_OPENING_03H)
        self.assertEqual(r["rule_flags"], [])
        self.assertTrue(r["ml_anomaly"])
        self.assertEqual(r["source"], "ML")
        self.assertTrue(r["is_anomaly"])
        self.assertGreaterEqual(r["anomaly_score"], 0.50)

    def test_rules_flag_physical_attacks(self):
        cases = {
            "LIGHT_WHILE_LOCKED": dict(NORMAL_DAY_LOCKED, light_adc=800),
            "THERMAL_HOT": dict(NORMAL_DAY_LOCKED, temp=36.0),
            "THERMAL_COLD": dict(NORMAL_DAY_LOCKED, temp=10.0),
            "HUMIDITY_HIGH": dict(NORMAL_DAY_LOCKED, hum=90.0),
            "BREACH_FLAG": dict(NORMAL_DAY_LOCKED, breach=True),
        }
        for flag, frame in cases.items():
            r = self.d.evaluate_detailed(frame)
            self.assertIn(flag, r["rule_flags"])
            self.assertTrue(r["is_anomaly"])
            self.assertGreaterEqual(r["anomaly_score"], 0.50, flag)

    def test_score_threshold_consistency(self):
        """RuleChain alarms on anomaly_score >= 0.50: must match the anomaly flag."""
        for frame in (NORMAL_DAY_LOCKED, LEGIT_ACCESS_10H, NIGHT_OPENING_03H,
                      dict(NORMAL_DAY_LOCKED, temp=35.5), dict(NORMAL_DAY_LOCKED, light_adc=701)):
            ok, score, _ = self.d.evaluate(frame)
            self.assertEqual(ok, score >= 0.50, frame)

    def test_backward_compatible_api(self):
        result = self.d.evaluate({"temp": 28.0, "hum": 60.0, "light_adc": 150,
                                  "distance_cm": 80.0, "state": "LOCKED", "breach": False})
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
