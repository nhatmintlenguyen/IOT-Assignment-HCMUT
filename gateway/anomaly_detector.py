"""
Smart Safe Guardian - Edge AI Anomaly Detection (T09)
Runs on local IoT Gateway (PC / Raspberry Pi Zero 2W).
Uses Scikit-Learn Isolation Forest to detect abnormal vault sensor patterns.
"""

import datetime
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class VaultAnomalyDetector:
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.02,
            random_state=42
        )
        self._train_baseline_model()

    def _train_baseline_model(self):
        """
        Trains Isolation Forest on synthetic baseline of normal vault behavior:
        - Safe can be locked or legitimately accessed (unlocked)
        - Internal safe is pitch dark when locked (light ADC 50 - 350)
        - Safe internal sensor sees ambient room light when unlocked (light ADC 200 - 900)
        - Ambient laboratory temperature (22°C - 31°C) and humidity (45% - 75%)
        - Distance clear when idle (> 40 cm) or normal approach (15 - 45 cm)
        """
        np.random.seed(42)
        n_samples = 2000

        # Feature 0: Hour of the day (spread across day and evening)
        hours = np.random.randint(0, 24, size=n_samples)

        # Feature 1: Temperature (mean ~26.5°C, std ~2.0)
        temps = np.random.normal(26.5, 2.0, n_samples)
        temps = np.clip(temps, 20.0, 33.0)

        # Feature 2: Humidity (mean ~62%, std ~5.0)
        hums = np.random.normal(62.0, 5.0, n_samples)
        hums = np.clip(hums, 45.0, 75.0)

        # Feature 3: Safe state (0 = Locked, 1 = Unlocked; 75% locked, 25% legitimate unlock)
        states = np.random.choice([0, 1], size=n_samples, p=[0.75, 0.25])

        # Feature 4: Internal Light ADC (depends on door state)
        lights = np.where(
            states == 0,
            np.random.normal(130.0, 35.0, n_samples),
            np.random.normal(450.0, 120.0, n_samples)
        )
        lights = np.clip(lights, 30.0, 850.0)

        # Feature 5: Approach Distance in cm (mean ~50cm, std ~12)
        distances = np.random.normal(50.0, 12.0, n_samples)
        distances = np.clip(distances, 15.0, 95.0)

        # Feature 6: Breach flag (always 0 in baseline)
        breaches = np.zeros(n_samples)

        X_train = np.column_stack([hours, temps, hums, states, lights, distances, breaches])
        X_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_scaled)

    def evaluate(self, telemetry: dict):
        """
        Evaluates a live telemetry sample.
        Returns:
            is_anomaly (bool): True if flagged as anomalous
            score (float): Normalized anomaly score (0.0 normal, 1.0 extreme outlier)
            reason (str): Human-readable diagnosis
        """
        now = datetime.datetime.now()
        hour = now.hour

        temp = float(telemetry.get("temp", 26.0))
        hum = float(telemetry.get("hum", 62.0))
        light = float(telemetry.get("light_adc", 140))
        dist = float(telemetry.get("distance_cm", 45.0))
        is_unlocked = 1 if telemetry.get("state") == "UNLOCKED" else 0
        is_breach = 1 if telemetry.get("breach", False) else 0

        features = np.array([[hour, temp, hum, is_unlocked, light, dist, is_breach]])
        features_scaled = self.scaler.transform(features)

        # Statistical isolation score (decision_function measures normality distance)
        raw_score = self.model.decision_function(features_scaled)[0]

        # Physical domain risk assessment
        reasons = []
        domain_penalty = 0.0

        if is_breach:
            domain_penalty += 0.85
            reasons.append("Security breach alarm active")

        # Casing drilled or opened without unlock command
        if is_unlocked == 0 and light > 700:
            severity = min(0.80, (light - 700) / 1200.0)
            domain_penalty += severity
            reasons.append(f"Internal light detected while locked ({int(light)} ADC)")

        # Fire / thermal attack (> 35.0°C aligned with Telegram & RuleChain)
        if temp > 35.0:
            severity = min(0.85, (temp - 35.0) / 15.0)
            domain_penalty += severity
            reasons.append(f"High thermal vector ({temp:.1f}°C)")
        elif temp < 14.0:
            domain_penalty += 0.40
            reasons.append(f"Abnormally low temperature ({temp:.1f}°C)")

        # Excessive moisture
        if hum > 85.0:
            domain_penalty += 0.40
            reasons.append(f"Excessive humidity ({hum:.1f}%)")

        # Baseline normalized anomaly score (0.00 to 0.40 under normal conditions)
        base_score = float(np.clip((0.14 - raw_score) / 0.45, 0.0, 0.40))
        total_score = float(np.clip(base_score + domain_penalty, 0.0, 1.0))

        # Anomaly threshold: total score >= 0.50 or physical breach
        is_anomaly = bool(total_score >= 0.50 or is_breach == 1 or len(reasons) > 0)
        reason_str = ", ".join(reasons) if reasons else ("Outlier vector" if is_anomaly else "Normal")

        return is_anomaly, round(total_score, 2), reason_str
