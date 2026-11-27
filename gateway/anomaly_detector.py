"""
Smart Safe Guardian - Edge AI Anomaly Detection (T09)
Runs on local IoT Gateway (PC / Raspberry Pi Zero 2W).

Two kinds of detectors are combined:
  1. ML (scikit-learn Isolation Forest), able to raise an anomaly ON ITS OWN:
       a. Environment model : 7 features (hour, temp, hum, is_unlocked, light_adc,
                              distance_cm, is_breach) over all telemetry frames.
       b. Access-time model : trained on legitimate unlocked frames only, feature =
                              time of day (fractional hour). Flags a door opened
                              outside the usual working hours (e.g. 03:00).
     ml_score >= 0.50  <=>  IsolationForest.predict() == -1 for at least one model.
  2. Rule flags: explicit physical security rules (breach flag, light while locked,
     thermal attack, flooding) giving an explainable diagnosis.

Published values (unchanged keys for dashboard / RuleChain compatibility):
  anomaly (bool), anomaly_score (0.0-1.0, anomaly <=> score >= 0.50), anomaly_reason (str)
Additional keys:
  ml_score (0.0-1.0), rule_flags (comma-separated rule identifiers, "" if none)

Each telemetry frame is evaluated individually (no temporal window). The models are
retrained from the synthetic baseline at every gateway start; nothing is persisted.
"""

import datetime
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Physical rule thresholds (see README "Multi-level thresholds")
LIGHT_LOCKED_RULE_ADC = 700      # light seen inside the locked enclosure
TEMP_HOT_RULE_C = 35.0           # thermal attack / fire
TEMP_COLD_RULE_C = 14.0          # cryogenic tampering
HUMIDITY_RULE_PCT = 85.0         # flooding
ANOMALY_THRESHOLD = 0.50

# Legitimate access schedule used to build the baseline
ACCESS_HOUR_MEAN = 13.5
ACCESS_HOUR_STD = 2.5
ACCESS_HOUR_RANGE = (8.0, 20.0)  # [08:00, 20:00)

FEATURES = ["hour", "temp", "hum", "is_unlocked", "light_adc", "distance_cm", "is_breach"]


def truncated_normal(rng, mean, std, low, high, n):
    """Normal distribution truncated (re-sampled, not clipped) to [low, high)."""
    out = np.empty(0)
    while out.size < n:
        x = rng.normal(mean, std, 2 * n)
        out = np.concatenate([out, x[(x >= low) & (x < high)]])
    return out[:n]


def _ml_score(model, scale, x_scaled):
    """Maps IsolationForest.decision_function to [0, 1]; decision boundary -> 0.50."""
    raw = float(model.decision_function(x_scaled)[0])
    return float(np.clip(0.5 - raw / (2.0 * scale), 0.0, 1.0))


class VaultAnomalyDetector:
    def __init__(self, n_samples=4000, random_state=42):
        self.scaler = StandardScaler()
        self.model = IsolationForest(n_estimators=100, contamination=0.02, random_state=random_state)
        self.access_scaler = StandardScaler()
        self.access_model = IsolationForest(n_estimators=100, contamination=0.01, random_state=random_state)
        self._train_baseline_model(n_samples, random_state)

    @staticmethod
    def generate_baseline(n_samples=4000, random_state=42):
        """
        Synthetic baseline of NORMAL vault behaviour (realistic sensor ranges):
        - Locked frames (80%): any time of day (the vault is locked 24/7), dark
          enclosure (LDR ~150 ADC), distance log-normal around 80 cm.
        - Legitimate access frames (20%): door unlocked during working hours only,
          time of day ~ N(13.5 h, 2.5 h) truncated to [08:00, 20:00), ambient light in
          the open vault (LDR log-normal ~1500 ADC, 300-4095), operator at ~25 cm.
        - Ambient climate (Ho Chi Minh City lab): 22-34 C, 40-80 %RH.
        """
        rng = np.random.default_rng(random_state)
        n_access = int(n_samples * 0.20)
        n_idle = n_samples - n_access

        idle = np.column_stack([
            rng.uniform(0.0, 24.0, n_idle),
            np.clip(rng.normal(28.0, 2.5, n_idle), 22.0, 34.0),
            np.clip(rng.normal(62.0, 8.0, n_idle), 40.0, 80.0),
            np.zeros(n_idle),
            np.clip(rng.normal(150.0, 60.0, n_idle), 30.0, 450.0),
            np.clip(rng.lognormal(np.log(80.0), 0.5, n_idle), 12.0, 400.0),
            np.zeros(n_idle),
        ])
        access = np.column_stack([
            truncated_normal(rng, ACCESS_HOUR_MEAN, ACCESS_HOUR_STD, *ACCESS_HOUR_RANGE, n_access),
            np.clip(rng.normal(28.0, 2.5, n_access), 22.0, 34.0),
            np.clip(rng.normal(62.0, 8.0, n_access), 40.0, 80.0),
            np.ones(n_access),
            np.clip(rng.lognormal(np.log(1500.0), 0.6, n_access), 300.0, 4095.0),
            np.clip(rng.normal(25.0, 6.0, n_access), 8.0, 45.0),
            np.zeros(n_access),
        ])
        return np.vstack([idle, access])

    def _train_baseline_model(self, n_samples, random_state):
        X = self.generate_baseline(n_samples, random_state)

        Z = self.scaler.fit_transform(X)
        self.model.fit(Z)
        self._scale = float(max(np.max(self.model.decision_function(Z)), 1e-6))

        A = X[X[:, 3] == 1][:, [0]]
        Za = self.access_scaler.fit_transform(A)
        self.access_model.fit(Za)
        self._access_scale = float(max(np.max(self.access_model.decision_function(Za)), 1e-6))

    @staticmethod
    def _features(telemetry):
        hour = telemetry.get("hour")
        if hour is None:
            now = datetime.datetime.now()
            hour = now.hour + now.minute / 60.0
        return np.array([[
            float(hour),
            float(telemetry.get("temp", 28.0)),
            float(telemetry.get("hum", 62.0)),
            1.0 if telemetry.get("state") == "UNLOCKED" else 0.0,
            float(telemetry.get("light_adc", 150)),
            float(telemetry.get("distance_cm", 80.0)),
            1.0 if telemetry.get("breach", False) else 0.0,
        ]])

    def evaluate_detailed(self, telemetry: dict) -> dict:
        """Full diagnosis: ML scores, rule flags, combined score and reason."""
        x = self._features(telemetry)
        hour, temp, hum, is_unlocked, light, _dist, is_breach = x[0]

        env_score = _ml_score(self.model, self._scale, self.scaler.transform(x))
        access_score = 0.0
        if is_unlocked:
            access_score = _ml_score(self.access_model, self._access_scale,
                                     self.access_scaler.transform(x[:, [0]]))
        ml_score = max(env_score, access_score)
        ml_anomaly = ml_score >= ANOMALY_THRESHOLD

        flags, reasons, penalty = [], [], 0.0
        if is_breach:
            flags.append("BREACH_FLAG"); penalty += 0.85
            reasons.append("Security breach alarm active")
        if not is_unlocked and light > LIGHT_LOCKED_RULE_ADC:
            flags.append("LIGHT_WHILE_LOCKED"); penalty += min(0.80, (light - LIGHT_LOCKED_RULE_ADC) / 1200.0)
            reasons.append(f"Internal light detected while locked ({int(light)} ADC)")
        if temp > TEMP_HOT_RULE_C:
            flags.append("THERMAL_HOT"); penalty += min(0.85, (temp - TEMP_HOT_RULE_C) / 15.0)
            reasons.append(f"High thermal vector ({temp:.1f}°C)")
        elif temp < TEMP_COLD_RULE_C:
            flags.append("THERMAL_COLD"); penalty += 0.40
            reasons.append(f"Abnormally low temperature ({temp:.1f}°C)")
        if hum > HUMIDITY_RULE_PCT:
            flags.append("HUMIDITY_HIGH"); penalty += 0.40
            reasons.append(f"Excessive humidity ({hum:.1f}%)")

        if ml_anomaly:
            if access_score >= ANOMALY_THRESHOLD:
                reasons.append(f"Isolation Forest: access at unusual time ({int(hour):02d}h{int(round((hour % 1) * 60)) % 60:02d}, ml_score {ml_score:.2f})")
            else:
                reasons.append(f"Isolation Forest: outlier sensor vector (ml_score {ml_score:.2f})")

        # Any rule flag is an anomaly by itself: its score starts at the 0.50 threshold.
        rule_score = float(np.clip(0.5 + penalty / 2.0, 0.5, 1.0)) if flags else 0.0
        is_anomaly = bool(ml_anomaly or flags)
        score = round(max(ml_score, rule_score), 2)
        # Keep "anomaly <=> anomaly_score >= 0.50" exact after rounding (RuleChain threshold).
        score = max(score, ANOMALY_THRESHOLD) if is_anomaly else min(score, 0.49)

        if not is_anomaly:
            source = "NONE"
        elif ml_anomaly and flags:
            source = "ML+RULES"
        else:
            source = "ML" if ml_anomaly else "RULES"

        return {
            "is_anomaly": is_anomaly,
            "anomaly_score": score,
            "ml_score": round(ml_score, 2),
            "ml_anomaly": ml_anomaly,
            "rule_flags": flags,
            "source": source,
            "reason": ", ".join(reasons) if reasons else "Normal",
        }

    def evaluate(self, telemetry: dict):
        """
        Backward-compatible API used by gateway.py and system_benchmark.py.
        Returns (is_anomaly, anomaly_score, reason).
        """
        d = self.evaluate_detailed(telemetry)
        return d["is_anomaly"], d["anomaly_score"], d["reason"]
