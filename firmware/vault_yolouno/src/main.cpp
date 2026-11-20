#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_mac.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <Preferences.h>
#include <Adafruit_NeoPixel.h>
#include "sensor_monitor.h"
#include "sensor_snapshot.h"
#include "vault_state.h"
#include "servo_control.h"
#include "ir_reader.h"
#include "lcd_display.h"

#define NEO_PIN 45
#define LED_COUNT 1
#define PIN_BOOT_BUTTON 0

// NVS Persistent Storage for authorized Badge MAC
Preferences authPrefs;
uint8_t authorizedBadgeMac[6] = {0};
bool hasAuthorizedBadge = false;
volatile uint32_t pairingWindowUntilMs = 0;

void load_paired_badge() {
    authPrefs.begin("vault_auth", false);
    hasAuthorizedBadge = authPrefs.getBool("has_badge", false);
    if (hasAuthorizedBadge) {
        authPrefs.getBytes("badge_mac", authorizedBadgeMac, 6);
        Serial.printf("[AUTH] Authorized Badge MAC loaded from NVS: %02X:%02X:%02X:%02X:%02X:%02X\n",
                      authorizedBadgeMac[0], authorizedBadgeMac[1], authorizedBadgeMac[2],
                      authorizedBadgeMac[3], authorizedBadgeMac[4], authorizedBadgeMac[5]);
    } else {
        Serial.println("[AUTH] No Badge paired yet. Press BOOT button or IR Key 'E' to pair.");
    }
}

void start_pairing_mode() {
    pairingWindowUntilMs = millis() + 15000; // 15 seconds pairing window
    Serial.println("{\"type\":\"event\",\"source\":\"vault\",\"action\":\"pairing_mode_started\",\"window_sec\":15}");
}

bool is_pairing_mode_active() {
    return (millis() < pairingWindowUntilMs);
}

uint32_t get_remaining_pairing_sec() {
    const uint32_t now = millis();
    if (now >= pairingWindowUntilMs) return 0;
    return (pairingWindowUntilMs - now + 999) / 1000;
}

typedef struct struct_badge_request {
    char cmd[16];        // "UNLOCK", "LOCK", "MASTER_AUTH"
    uint32_t counter;    // Anti-replay sequence counter
} struct_badge_request;

typedef struct struct_vault_response {
    char status[16];     // "OK_UNLOCKED", "OK_LOCKED", "ALREADY_OPEN", "ALREADY_LOCKED", "DENIED_LOCKDOWN", "DENIED_PRESENCE", "DENIED"
    uint32_t counter;    // Echo counter
} struct_vault_response;

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
    const uint8_t *srcMac = recv_info->src_addr;
#else
void onDataRecv(const uint8_t *srcMac, const uint8_t *data, int len) {
#endif
    if (len == sizeof(struct_badge_request)) {
        struct_badge_request req;
        memcpy(&req, data, sizeof(req));
        Serial.printf("[ESP-NOW RX] From %02X:%02X:%02X:%02X:%02X:%02X | Cmd: '%s' (counter: %lu)\n",
                      srcMac[0], srcMac[1], srcMac[2], srcMac[3], srcMac[4], srcMac[5],
                      req.cmd, (unsigned long)req.counter);

        struct_vault_response resp;
        resp.counter = req.counter;
        strcpy(resp.status, "DENIED");

        const uint32_t now = millis();
        const bool inPairingWindow = (now < pairingWindowUntilMs);

        // --- 1. PAIRING REQUEST ---
        if (strcmp(req.cmd, "PAIR_REQ") == 0) {
            if (inPairingWindow) {
                memcpy(authorizedBadgeMac, srcMac, 6);
                hasAuthorizedBadge = true;
                authPrefs.putBytes("badge_mac", authorizedBadgeMac, 6);
                authPrefs.putBool("has_badge", true);
                pairingWindowUntilMs = 0; // Close pairing window immediately

                strcpy(resp.status, "PAIR_OK");
                lcd_show_notification("BADGE PAIRED!", "Authorized OK");
                Serial.printf("{\"type\":\"event\",\"source\":\"pairing\",\"action\":\"badge_paired\",\"mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\"}\n",
                              srcMac[0], srcMac[1], srcMac[2], srcMac[3], srcMac[4], srcMac[5]);
            } else {
                strcpy(resp.status, "PAIR_DENIED");
                Serial.println("{\"type\":\"event\",\"source\":\"pairing\",\"action\":\"pair_denied_window_closed\"}");
            }

            // Register peer and reply
            if (!esp_now_is_peer_exist(srcMac)) {
                esp_now_peer_info_t peer = {};
                memcpy(peer.peer_addr, srcMac, 6);
                peer.channel = 1;
                peer.encrypt = false;
                esp_now_add_peer(&peer);
            }
            esp_now_send(srcMac, (uint8_t *)&resp, sizeof(resp));
            return;
        }

        // --- 2. SECURITY WHITELIST CHECK ---
        // If a badge has been paired and incoming MAC doesn't match -> Rogue Badge!
        if (hasAuthorizedBadge && memcmp(srcMac, authorizedBadgeMac, 6) != 0) {
            Serial.printf("{\"type\":\"event\",\"source\":\"badge_espnow\",\"cmd\":\"%s\",\"result\":\"denied_unauthorized\",\"alert\":\"ROGUE_BADGE_DETECTED\",\"rogue_mac\":\"%02X:%02X:%02X:%02X:%02X:%02X\"}\n",
                          req.cmd, srcMac[0], srcMac[1], srcMac[2], srcMac[3], srcMac[4], srcMac[5]);
            record_failed_attempt("badge_espnow");
            strcpy(resp.status, "DENIED_UNAUTHORIZED");
            lcd_show_notification("ROGUE BADGE", "Access Denied");

            if (!esp_now_is_peer_exist(srcMac)) {
                esp_now_peer_info_t peer = {};
                memcpy(peer.peer_addr, srcMac, 6);
                peer.channel = 1;
                peer.encrypt = false;
                esp_now_add_peer(&peer);
            }
            esp_now_send(srcMac, (uint8_t *)&resp, sizeof(resp));
            return;
        }

        // --- 3. AUTHORIZED COMMAND PROCESSING ---
        Serial.printf("{\"type\":\"event\",\"source\":\"badge_espnow\",\"cmd\":\"%s\",\"counter\":%lu}\n",
                      req.cmd, (unsigned long)req.counter);

        const VaultStatus status = get_vault_status();
        const SensorSnapshot sensors = get_sensor_snapshot();

        if (strcmp(req.cmd, "UNLOCK") == 0) {
            if (status.lockdownActive) {
                strcpy(resp.status, "DENIED_LOCKDOWN");
            } else if (status.lockState == LockState::Unlocked) {
                strcpy(resp.status, "ALREADY_OPEN");
            } else if (!sensors.personNear && !status.standbyActive) {
                strcpy(resp.status, "DENIED_PRESENCE");
                lcd_show_notification("BADGE DENIED", "Approach first");
            } else {
                if (status.breachActive) {
                    acknowledge_breach();
                    lcd_show_notification("BADGE", "Breach Acked");
                } else {
                    lcd_show_notification("BADGE", "Access Granted");
                }
                request_unlock();
                strcpy(resp.status, "OK_UNLOCKED");
            }
        } else if (strcmp(req.cmd, "LOCK") == 0) {
            if (status.breachActive) {
                acknowledge_breach();
                strcpy(resp.status, "OK_ACKED");
                lcd_show_notification("BADGE", "Breach Acked");
            } else if (status.lockState == LockState::Locked) {
                strcpy(resp.status, "ALREADY_LOCKED");
            } else {
                set_lock_state(LockState::Locked);
                strcpy(resp.status, "OK_LOCKED");
                lcd_show_notification("BADGE", "Vault Locked");
            }
        } else if (strcmp(req.cmd, "FAKE_BADGE") == 0) {
            Serial.println("{\"type\":\"event\",\"source\":\"badge_espnow\",\"cmd\":\"FAKE_BADGE\",\"result\":\"denied_unauthorized\",\"alert\":\"ROGUE_BADGE_DETECTED\"}");
            record_failed_attempt("badge_espnow");
            strcpy(resp.status, "DENIED_UNAUTHORIZED");
            lcd_show_notification("ROGUE BADGE", "Access Denied");
        } else if (strcmp(req.cmd, "ACK_BREACH") == 0) {
            if (status.breachActive) {
                acknowledge_breach();
                strcpy(resp.status, "OK_ACKED");
                lcd_show_notification("BADGE", "Breach Acked");
            } else {
                strcpy(resp.status, "NO_ALERT_TO_ACK");
            }
        }

        // Register peer if not already present
        if (!esp_now_is_peer_exist(srcMac)) {
            esp_now_peer_info_t peer = {};
            memcpy(peer.peer_addr, srcMac, 6);
            peer.channel = 1;
            peer.encrypt = false;
            if (esp_now_add_peer(&peer) == ESP_OK) {
                Serial.printf("[ESP-NOW] Peer registered: %02X:%02X:%02X:%02X:%02X:%02X\n",
                              srcMac[0], srcMac[1], srcMac[2], srcMac[3], srcMac[4], srcMac[5]);
            }
        }

        // Send response back to the badge
        esp_err_t sendResult = esp_now_send(srcMac, (uint8_t *)&resp, sizeof(resp));
        Serial.printf("[ESP-NOW TX] Reply '%s' sent to Badge (res: %d)\n", resp.status, sendResult);
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

    // 0. Pairing mode active: rapid cyan strobe (120ms cycle)
    if (millis() < pairingWindowUntilMs) {
      strip.setPixelColor(0, strip.Color(0, 180, 220));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(120));
      strip.clear();
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(120));
      continue;
    }

    // 0. Remote security lockdown: solid purple/magenta
    if (status.lockdownActive) {
      strip.setPixelColor(0, strip.Color(180, 0, 180));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }

    // 1. Security breach alert: rapid 80ms red strobe
    if (status.breachActive) {
      strip.setPixelColor(0, strip.Color(255, 0, 0));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(80));
      strip.clear();
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(80));
      continue;
    }

    // 2. Vault unlocked: solid green
    if (status.lockState == LockState::Unlocked) {
      strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(500));
      continue;
    }

    // 3. Sensor fault: blinking yellow
    if (!sensors.climateValid) {
      strip.setPixelColor(0, strip.Color(255, 255, 0));
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      strip.clear();
      strip.show();
      vTaskDelay(pdMS_TO_TICKS(250));
      continue;
    }

    // 4. Normal locked state: blue / cyan / red gradient based on temperature
    if (sensors.temperatureC < 20.0f) {
      strip.setPixelColor(0, strip.Color(0, 0, 255)); // Blue (Cold)
    } else if (sensors.temperatureC < 28.0f) {
      strip.setPixelColor(0, strip.Color(0, 150, 150)); // Cyan (Comfortable)
    } else {
      strip.setPixelColor(0, strip.Color(255, 0, 0)); // Red (Warm)
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
        "{\"type\":\"telemetry\",\"temp\":%.2f,\"hum\":%.2f,\"climate_valid\":%s,\"light_adc\":%d,\"distance_cm\":%.1f,\"distance_valid\":%s,\"person_near\":%s,\"state\":\"%s\",\"breach\":%s,\"lockdown\":%s}\n",
        sensors.temperatureC,
        sensors.humidityPct,
        sensors.climateValid ? "true" : "false",
        sensors.lightAdc,
        sensors.distanceCm,
        sensors.distanceValid ? "true" : "false",
        sensors.personNear ? "true" : "false",
        status.lockState == LockState::Locked ? "LOCKED" : "UNLOCKED",
        status.breachActive ? "true" : "false",
        status.lockdownActive ? "true" : "false");
    vTaskDelay(pdMS_TO_TICKS(2000));
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500); // Allow USB CDC time to stabilize

  Serial.println("\n==========================================");
  Serial.println("  Smart Safe Guardian - YoloUNO (Vault)");
  Serial.println("==========================================");

  // Initialize deadbolt servo motor
  servo_control_init();

  // Initialize IR remote receiver (Grove D6-D5, pin D5 = GPIO 8)
  ir_reader_init();

  // Initialize ESP-NOW on Wi-Fi STA (Channel 1)
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  esp_wifi_start();
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);

  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_WIFI_STA);
  Serial.printf("[INFO] YoloUNO MAC: %02X:%02X:%02X:%02X:%02X:%02X (Channel 1)\n",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

  if (esp_now_init() == ESP_OK) {
    esp_now_register_recv_cb(onDataRecv);
    Serial.println("[OK] ESP-NOW Receiver initialized successfully.");
  } else {
    Serial.println("[ERROR] Failed to initialize ESP-NOW on YoloUNO.");
  }

  // Initialize physical BOOT button (GPIO 0) for Pairing Trigger
  pinMode(PIN_BOOT_BUTTON, INPUT_PULLUP);

  // Load authorized badge MAC from persistent NVS flash
  load_paired_badge();

  // FreeRTOS Tasks
  xTaskCreate(task_sensor_monitor, "Sensor Monitor", 4096, NULL, 2, NULL);
  xTaskCreate(task_neopixel, "NeoPixel Control", 2048, NULL, 2, NULL);
  xTaskCreate(task_led_blink, "LED Heartbeat Control", 2048, NULL, 1, NULL);
  xTaskCreate(task_telemetry_uart, "UART Telemetry", 3072, NULL, 1, NULL);
}

void loop() {
  // 1. Vault state machine tick (handles 30s auto-relock)
  vault_state_tick();

  // 2. Decode infrared remote commands
  ir_reader_tick();

  // 3. Physical BOOT Button on YoloUNO -> Trigger Secure Pairing Mode
  static int lastBootState = HIGH;
  const int bootReading = digitalRead(PIN_BOOT_BUTTON);
  if (bootReading == LOW && lastBootState == HIGH) {
    Serial.println("[BUTTON] BOOT button pressed on YoloUNO -> Entering Pairing Mode!");
    start_pairing_mode();
  }
  lastBootState = bootReading;

  // 4. Listen for serial USB commands (Gateway or manual CLI testing)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd == "pair" || cmd == "pairing") {
      Serial.println("[CMD] 'pair' command received via USB -> Entering Pairing Mode!");
      start_pairing_mode();
    } else if (cmd == "unlock" || cmd.indexOf("unlock") >= 0) {
      Serial.println("[CMD] 'unlock' command received via USB");
      request_unlock();
      lcd_show_notification("WEB / CLOUD", "Access Granted");
    } else if (cmd == "lock" || (cmd.indexOf("lock") >= 0 && cmd.indexOf("lockdown") < 0)) {
      Serial.println("[CMD] 'lock' command received via USB");
      set_lock_state(LockState::Locked);
      lcd_show_notification("WEB / CLOUD", "Vault Locked");
    } else if (cmd == "ack" || cmd.indexOf("ack") >= 0 || cmd == "reset") {
      Serial.println("[CMD] 'ack' command received via USB");
      acknowledge_breach();
      lcd_show_notification("WEB / CLOUD", "Breach Acked");
    } else if (cmd == "lockdown 1" || cmd == "lockdown on" || cmd == "lockdown:1" || cmd.indexOf("\"lockdown\":true") >= 0 || (cmd.indexOf("lockdown") >= 0 && cmd.indexOf("true") >= 0)) {
      Serial.println("[CMD] Enabling security lockdown via USB");
      set_lockdown(true);
      lcd_show_notification("WEB / CLOUD", "Lockdown ON");
    } else if (cmd == "lockdown 0" || cmd == "lockdown off" || cmd == "lockdown:0" || cmd.indexOf("\"lockdown\":false") >= 0 || (cmd.indexOf("lockdown") >= 0 && cmd.indexOf("false") >= 0)) {
      Serial.println("[CMD] Disabling security lockdown via USB");
      set_lockdown(false);
      lcd_show_notification("WEB / CLOUD", "Lockdown OFF");
    } else if (cmd == "reboot" || cmd == "restart") {
      Serial.println("[CMD] Rebooting YoloUNO Vault Controller...");
      delay(200);
      esp_restart();
    }
  }

  delay(50);
}
