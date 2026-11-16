#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
#include <Adafruit_NeoPixel.h>
#include "sensor_monitor.h"
#include "sensor_snapshot.h"
#include "vault_state.h"

#define NEO_PIN 45
#define LED_COUNT 1

typedef struct struct_message {
    char cmd[16];        // "UNLOCK" ou "DURESS"
    uint32_t counter;    // Compteur anti-rejeu simple
} struct_message;

struct_message incomingBadgeMsg;

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
#else
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
#endif
    if (len == sizeof(struct_message)) {
        memcpy(&incomingBadgeMsg, data, sizeof(incomingBadgeMsg));
        Serial.printf("{\"type\":\"event\",\"source\":\"badge_espnow\",\"cmd\":\"%s\",\"counter\":%lu}\n",
                      incomingBadgeMsg.cmd, (unsigned long)incomingBadgeMsg.counter);
    }
}

void task_neopixel(void *pvParameters) {
  Adafruit_NeoPixel strip(LED_COUNT, NEO_PIN, NEO_GRB + NEO_KHZ800);
  strip.begin();
  strip.clear();
  strip.show();

  while(1) {
    const SensorSnapshot sensors = get_sensor_snapshot();
    const VaultStatus status = get_vault_status();

    if (status.breachActive) {
      strip.setPixelColor(0, strip.Color(255, 0, 0));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      strip.clear();
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      continue;
    }

    if (!sensors.climateValid) {
      strip.setPixelColor(0, strip.Color(255, 255, 0));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      strip.clear();
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      continue;
    }

    if (sensors.temperatureC < 20.0f) {
      strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue
    } else if (sensors.temperatureC < 28.0f) {
      strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
    } else {
      strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red
    }

    strip.show();
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

void task_led_blink(void *pvParameters) {
  pinMode(GPIO_NUM_48, OUTPUT);

  while(1) {
    digitalWrite(GPIO_NUM_48, HIGH);
    vTaskDelay(500);
    digitalWrite(GPIO_NUM_48, LOW);
    vTaskDelay(500);
  }
}

void task_telemetry_uart(void *pvParameters) {
  while(1) {
    const SensorSnapshot sensors = get_sensor_snapshot();
    const VaultStatus status = get_vault_status();
    Serial.printf(
        "{\"type\":\"telemetry\",\"temp\":%.2f,\"hum\":%.2f,\"climate_valid\":%s,\"light_adc\":%d,\"distance_cm\":%.1f,\"distance_valid\":%s,\"person_near\":%s,\"state\":\"%s\",\"breach\":%s}\n",
        sensors.temperatureC,
        sensors.humidityPct,
        sensors.climateValid ? "true" : "false",
        sensors.lightAdc,
        sensors.distanceCm,
        sensors.distanceValid ? "true" : "false",
        sensors.personNear ? "true" : "false",
        status.lockState == LockState::Locked ? "LOCKED" : "UNLOCKED",
        status.breachActive ? "true" : "false");
    vTaskDelay(pdMS_TO_TICKS(2000));
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500); // Laisse le temps à l'USB CDC de se stabiliser

  Serial.println("\n==========================================");
  Serial.println("  Smart Safe Guardian - YoloUNO (Vault)");
  Serial.println("==========================================");

  // Initialisation ESP-NOW
  WiFi.mode(WIFI_STA);
  Serial.print("[INFO] YoloUNO MAC: ");
  Serial.println(WiFi.macAddress());

  if (esp_now_init() == ESP_OK) {
    esp_now_register_recv_cb(onDataRecv);
    Serial.println("[OK] ESP-NOW Receiver initialisé.");
  } else {
    Serial.println("[ERREUR] Échec initialisation ESP-NOW sur YoloUNO.");
  }

  // Tâches FreeRTOS
  xTaskCreate(task_sensor_monitor, "Sensor Monitor", 4096, NULL, 2, NULL);
  xTaskCreate(task_neopixel, "NeoPixel Control", 2048, NULL, 2, NULL);
  xTaskCreate(task_led_blink, "LED Heartbeat Control", 2048, NULL, 1, NULL);
  xTaskCreate(task_telemetry_uart, "UART Telemetry", 3072, NULL, 1, NULL);
}

void loop() {
  // FreeRTOS gère toutes les tâches
  vTaskDelay(pdMS_TO_TICKS(1000));
}
