#include "sensor_monitor.h"

#include <Wire.h>
#include <math.h>

#include "DHT20.h"
#include "lcd_display.h"
#include "sensor_snapshot.h"
#include "vault_state.h"

namespace {
constexpr uint8_t LIGHT_SENSOR_PIN = 1; // YoloUNO analog A0 maps to GPIO1.
constexpr uint32_t LIGHT_SAMPLE_INTERVAL_MS = 500;
constexpr uint32_t CLIMATE_SAMPLE_INTERVAL_MS = 5000;
constexpr float MAX_TEMP_JUMP_C = 1.5f;
constexpr float MAX_HUMIDITY_JUMP_PCT = 5.0f;

DHT20 dht20;
}

void task_sensor_monitor(void *pvParameters) {
    (void)pvParameters;

    Wire.begin(11, 12);
    pinMode(LIGHT_SENSOR_PIN, INPUT);
    dht20.begin();
    lcd_display_begin();

    bool haveClimateReference = false;
    float lastTemperatureC = 0.0f;
    float lastHumidityPct = 0.0f;
    uint32_t lastClimateSampleMs = millis() - CLIMATE_SAMPLE_INTERVAL_MS;
    uint32_t lastLightSampleMs = millis() - LIGHT_SAMPLE_INTERVAL_MS;

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
                    Serial.printf("Humidity: %.2f%%  Temperature: %.2f C\n",
                                  humidityPct, temperatureC);
                }
            }
        }

        const SensorSnapshot sensors = get_sensor_snapshot();
        const VaultStatus status = get_vault_status();
        lcd_display_update(sensors, status);

        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
