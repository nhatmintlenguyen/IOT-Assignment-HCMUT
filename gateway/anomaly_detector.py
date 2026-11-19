"""
Smart Safe Guardian - Edge AI Anomaly Detection (T09)
Runs on local IoT Gateway (PC / Raspberry Pi Zero 2W).
Uses Scikit-Learn Isolation Forest to detect abnormal vault sensor patterns.
"""

import datetime
import numpy as np
from sklearn.ensemble import IsolationForest


class VaultAnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(
            n_estimators=50,
            contamination=0.05,
            random_state=42
        )
        self._train_baseline_model()

    def _train_baseline_model(self):
        """
        Trains Isolation Forest on synthetic baseline of normal vault behavior:
        - Normal business hours (07:00 - 20:00) with occasional night checks
        - Internal safe is pitch dark when locked (light ADC 50 - 350)
        - Ambient laboratory temperature (22°C - 31°C) and humidity (45% - 75%)
        - Distance clear when idle (> 40 cm) or normal approach (10 - 30 cm)
        """
        np.random.seed(42)
        n_samples = 1000

        # Feature 0: Hour of the day (mostly 7 to 20)
        hour_probs = np.array([
            0.01, 0.01, 0.01, 0.01, 0.01, 0.02, 0.03, # 0h-6h
            0.08, 0.09, 0.10, 0.10, 0.09, 0.08, 0.07, # 7h-13h
            0.07, 0.07, 0.06, 0.05, 0.02, 0.01, 0.01, # 14h-20h
            0.01, 0.01, 0.01                         # 21h-23h
        ], dtype=np.float64)
        hour_probs /= hour_probs.sum()
        hours = np.random.choice(range(24), size=n_samples, p=hour_probs)

        # Feature 1: Temperature (mean ~26.5°C, std ~2.0)
        temps = np.random.normal(26.5, 2.0, n_samples)
        temps = np.clip(temps, 20.0, 33.0)

        # Feature 2: Humidity (mean ~62%, std ~6.0)
        hums = np.random.normal(62.0, 6.0, n_samples)
        hums = np.clip(hums, 40.0, 80.0)

        # Feature 3: Internal Light ADC when door closed (mean ~150, std ~40)
        lights = np.random.normal(150.0, 40.0, n_samples)
        lights = np.clip(lights, 30.0, 400.0)

        # Feature 4: Approach Distance in cm (mean ~55cm, std ~15)
        distances = np.random.normal(55.0, 15.0, n_samples)
        distances = np.clip(distances, 5.0, 120.0)

        # Feature 5: Safe state (0 = Locked, 1 = Unlocked; 92% locked)
        states = np.random.choice([0, 1], size=n_samples, p=[0.92, 0.08])

        # Feature 6: Breach flag (0 = normal, baseline is always 0)
        breaches = np.zeros(n_samples)

        X_train = np.column_stack([hours, temps, hums, lights, distances, states, breaches])
        self.model.fit(X_train)

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

        temp = float(telemetry.get("temp", 25.0))
        hum = float(telemetry.get("hum", 60.0))
        light = float(telemetry.get("light_adc", 150))
        dist = float(telemetry.get("distance_cm", 50.0))
        is_unlocked = 1 if telemetry.get("state") == "UNLOCKED" else 0
        is_breach = 1 if telemetry.get("breach", False) else 0

        features = np.array([[hour, temp, hum, light, dist, is_unlocked, is_breach]])

        # IsolationForest decision_function: lower means more anomalous (negative = anomaly)
        raw_score = self.model.decision_function(features)[0]
        prediction = self.model.predict(features)[0]  # -1 = anomaly, 1 = normal

        # Normalize score into a friendly 0.0 - 1.0 range
        # raw_score typically ranges from ~ -0.3 (extreme anomaly) to +0.25 (typical normal)
        normalized_anomaly = float(np.clip((0.2 - raw_score) / 0.5, 0.0, 1.0))
        is_anomaly = bool(prediction == -1 or is_breach == 1 or normalized_anomaly > 0.65)

        # Diagnosing the primary anomaly factor
        reasons = []
        if is_breach or (is_unlocked == 0 and light > 1000):
            reasons.append("Light breach detected while vault locked")
        if hour < 6 or hour > 22:
            if is_unlocked or dist < 30:
                reasons.append("Physical activity during non-working hours")
        if temp > 35.0:
            reasons.append(f"High thermal vector ({temp:.1f}°C)")
        elif temp < 15.0:
            reasons.append(f"Abnormally low temperature ({temp:.1f}°C)")
        if hum > 85.0:
            reasons.append(f"Excessive humidity ({hum:.1f}%)")

        reason_str = ", ".join(reasons) if reasons else ("Outlier vector" if is_anomaly else "Normal")

        return is_anomaly, round(normalized_anomaly, 2), reason_str
