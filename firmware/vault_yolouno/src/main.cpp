#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
#include <Adafruit_NeoPixel.h>
#include "temp_humi_monitor.h"

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

bool sensor_error() {
  return (glob_temperature == 0.0 && glob_humidity == 0.0) ||
         (glob_temperature == -1.0 && glob_humidity == -1.0);
}

void task_neopixel(void *pvParameters) {
  Adafruit_NeoPixel strip(LED_COUNT, NEO_PIN, NEO_GRB + NEO_KHZ800);
  strip.begin();
  strip.clear();
  strip.show();

  while(1) {
    if (sensor_error()) {
      strip.setPixelColor(0, strip.Color(255, 255, 0));
      strip.show();
      vTaskDelay(250);
      strip.clear();
      strip.show();
      vTaskDelay(250);
      continue;
    }

    if (glob_temperature < 20.0) {
      strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue
    } else if (glob_temperature >= 20.0 && glob_temperature < 28.0) {
      strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
    } else {
      strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red
    }

    strip.show();
    vTaskDelay(5000);
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
    // Émission télémétrie JSON périodique sur UART pour le Gateway
    if (!sensor_error()) {
      Serial.printf("{\"type\":\"telemetry\",\"temp\":%.2f,\"hum\":%.2f,\"state\":\"LOCKED\"}\n",
                    glob_temperature, glob_humidity);
    }
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
  xTaskCreate(temp_humi_monitor, "Temp & Humi Monitor", 4096, NULL, 2, NULL);
  xTaskCreate(task_neopixel, "NeoPixel Control", 2048, NULL, 2, NULL);
  xTaskCreate(task_led_blink, "LED Heartbeat Control", 2048, NULL, 1, NULL);
  xTaskCreate(task_telemetry_uart, "UART Telemetry", 3072, NULL, 1, NULL);
}

void loop() {
  // FreeRTOS gère toutes les tâches
  vTaskDelay(pdMS_TO_TICKS(1000));
}
