#include "sensor_monitor.h"

#include <Wire.h>
#include <math.h>

#include "DHT20.h"
#include "lcd_display.h"
#include "proximity_detector.h"
#include "sensor_snapshot.h"
#include "vault_state.h"

namespace {
constexpr uint8_t LIGHT_SENSOR_PIN = 1; // YoloUNO analog A0 maps to GPIO1.
constexpr uint8_t ULTRASONIC_TRIG_PIN = 6; // YoloUNO Grove D3 maps to GPIO6 (Trigger).
constexpr uint8_t ULTRASONIC_ECHO_PIN = 7; // YoloUNO Grove D4 maps to GPIO7 (Echo).
constexpr uint32_t LIGHT_SAMPLE_INTERVAL_MS = 200;
constexpr uint32_t DISTANCE_SAMPLE_INTERVAL_MS = 200;
constexpr uint32_t CLIMATE_SAMPLE_INTERVAL_MS = 5000;
constexpr uint32_t ULTRASONIC_ECHO_TIMEOUT_US = 25000;
constexpr float MAX_TEMP_JUMP_C = 1.5f;
constexpr float MAX_HUMIDITY_JUMP_PCT = 5.0f;

DHT20 dht20;

float read_distance_cm(bool& readingValid) {
    digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

    const uint32_t echoDurationUs = pulseIn(
        ULTRASONIC_ECHO_PIN, HIGH, ULTRASONIC_ECHO_TIMEOUT_US);
    readingValid = echoDurationUs > 0;
    if (!readingValid) {
        return 0.0f;
    }

    return static_cast<float>(echoDurationUs) * 0.0343f / 2.0f;
}
}

void task_sensor_monitor(void *pvParameters) {
    (void)pvParameters;

    Wire.begin(11, 12);
    Wire.setTimeOut(50);
    pinMode(LIGHT_SENSOR_PIN, INPUT);
    pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
    pinMode(ULTRASONIC_ECHO_PIN, INPUT);
    digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
    dht20.begin();
    lcd_display_begin();

    bool haveClimateReference = false;
    float lastTemperatureC = 0.0f;
    float lastHumidityPct = 0.0f;
    uint32_t lastClimateSampleMs = millis() - CLIMATE_SAMPLE_INTERVAL_MS;
    uint32_t lastLightSampleMs = millis() - LIGHT_SAMPLE_INTERVAL_MS;
    uint32_t lastDistanceSampleMs = millis() - DISTANCE_SAMPLE_INTERVAL_MS;

    while (true) {
        const uint32_t now = millis();

        if (now - lastLightSampleMs >= LIGHT_SAMPLE_INTERVAL_MS) {
            lastLightSampleMs = now;
            const int lightAdc = analogRead(LIGHT_SENSOR_PIN);
            set_light_reading(lightAdc);

            if (observe_light_level(lightAdc)) {
                Serial.printf(
                    "{\"type\":\"event\",\"event\":\"breach\",\"source\":\"ldr\",\"light_adc\":%d,\"state\":\"LOCKED\"}\n",
                    lightAdc);
            }
        }

        if (now - lastDistanceSampleMs >= DISTANCE_SAMPLE_INTERVAL_MS) {
            lastDistanceSampleMs = now;
            bool distanceValid = false;
            const float distanceCm = read_distance_cm(distanceValid);
            const ProximityResult proximity = update_proximity(distanceCm, distanceValid);
            set_proximity_reading(distanceCm, distanceValid, proximity.personNear);

            const VaultStatus status = get_vault_status();
            if (proximity.personNear && status.lockState == LockState::Locked) {
                trigger_approach_standby();
            }
            if (proximity.enteredRange && status.lockState == LockState::Locked) {
                Serial.printf(
                    "{\"type\":\"event\",\"event\":\"approach\",\"distance_cm\":%.1f,\"state\":\"LOCKED\",\"standby_sec\":10}\n",
                    distanceCm);
            }
        }

        if (now - lastClimateSampleMs >= CLIMATE_SAMPLE_INTERVAL_MS) {
            lastClimateSampleMs = now;
            const int readStatus = dht20.read();
            const float temperatureC = dht20.getTemperature();
            const float humidityPct = dht20.getHumidity();
            const bool readingValid = readStatus == DHT20_OK &&
                                      isfinite(temperatureC) &&
                                      isfinite(humidityPct) &&
                                      !(temperatureC == 0.0f && humidityPct == 0.0f);

            if (!readingValid) {
                set_climate_reading(0.0f, 0.0f, false);
                Serial.println("[WARN] DHT20 reading failed.");
            } else {
                bool acceptReading = true;
                if (haveClimateReference &&
                    fabsf(temperatureC - lastTemperatureC) > MAX_TEMP_JUMP_C) {
                    Serial.println("[WARN] Temperature spike rejected.");
                    acceptReading = false;
                }
                if (haveClimateReference &&
                    fabsf(humidityPct - lastHumidityPct) > MAX_HUMIDITY_JUMP_PCT) {
                    Serial.println("[WARN] Humidity spike rejected.");
                    acceptReading = false;
                }

                if (acceptReading) {
                    lastTemperatureC = temperatureC;
                    lastHumidityPct = humidityPct;
                    haveClimateReference = true;
                    set_climate_reading(temperatureC, humidityPct, true);
                }
            }
        }

        const SensorSnapshot sensors = get_sensor_snapshot();
        const VaultStatus status = get_vault_status();
        lcd_display_update(sensors, status);

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
