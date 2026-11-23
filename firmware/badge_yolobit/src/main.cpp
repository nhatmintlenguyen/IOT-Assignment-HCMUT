#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_mac.h>
#include <esp_wifi.h>
#include <esp_arduino_version.h>
#include <Preferences.h>
#include <Adafruit_NeoPixel.h>

// Official Yolo:Bit hardware pinout
#define PIN_BUTTON_A 35
#define PIN_BUTTON_B 14
#define PIN_BUZZER   25
#define PIN_RGB_LED  4
#define NUM_LEDS     25

Adafruit_NeoPixel matrix(NUM_LEDS, PIN_RGB_LED, NEO_GRB + NEO_KHZ800);

// NVS Persistent Storage for paired YoloUNO MAC
Preferences badgePrefs;
const uint8_t BROADCAST_MAC[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
uint8_t vaultMacAddress[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
bool isVaultPaired = false;

void load_paired_vault() {
    badgePrefs.begin("badge_auth", false);
    badgePrefs.clear(); // Ephemeral security: wipe NVS on boot so pairing is required on every startup
    isVaultPaired = false;
    memcpy(vaultMacAddress, BROADCAST_MAC, 6);
    Serial.println("[AUTH] Fresh Startup: Pairing cache cleared. Hold A+B (1.5s) to pair with YoloUNO.");
}

// Bidirectional message structures
typedef struct struct_badge_request {
    char cmd[16];        // "UNLOCK", "LOCK", "MASTER_AUTH"
    uint32_t counter;    // Anti-replay sequence counter
} struct_badge_request;

typedef struct struct_vault_response {
    char status[16];     // "OK_UNLOCKED", "OK_LOCKED", "ALREADY_OPEN", "ALREADY_LOCKED", "DENIED_LOCKDOWN", "DENIED_PRESENCE", "DENIED"
    uint32_t counter;    // Echo counter
} struct_vault_response;

struct_badge_request reqMsg;
volatile bool responseReceived = false;
struct_vault_response lastResponse;
uint32_t msgCounter = 0;

// 5x5 Pixel Art Matrix Definitions (Row-Major: y * 5 + x)
const uint8_t ICON_CHECK[5][5] = {
    {0, 0, 0, 0, 0},
    {0, 0, 0, 0, 1},
    {0, 0, 0, 1, 0},
    {1, 0, 1, 0, 0},
    {0, 1, 0, 0, 0}
};

const uint8_t ICON_CROSS[5][5] = {
    {1, 0, 0, 0, 1},
    {0, 1, 0, 1, 0},
    {0, 0, 1, 0, 0},
    {0, 1, 0, 1, 0},
    {1, 0, 0, 0, 1}
};

const uint8_t ICON_LOCK_OPEN[5][5] = {
    {0, 1, 1, 1, 0},
    {0, 1, 0, 0, 0},
    {1, 1, 1, 1, 1},
    {1, 1, 0, 1, 1},
    {1, 1, 1, 1, 1}
};

const uint8_t ICON_LOCK_CLOSED[5][5] = {
    {0, 1, 1, 1, 0},
    {0, 1, 0, 1, 0},
    {1, 1, 1, 1, 1},
    {1, 1, 0, 1, 1},
    {1, 1, 1, 1, 1}
};

const uint8_t ICON_NO_ENTRY[5][5] = {
    {0, 1, 1, 1, 0},
    {1, 0, 0, 0, 1},
    {1, 1, 1, 1, 1},
    {1, 0, 0, 0, 1},
    {0, 1, 1, 1, 0}
};

const uint8_t ICON_WARNING[5][5] = {
    {0, 0, 1, 0, 0},
    {0, 1, 1, 1, 0},
    {1, 0, 1, 0, 1},
    {1, 0, 0, 0, 1},
    {1, 1, 1, 1, 1}
};

const uint8_t ICON_SKULL[5][5] = {
    {0, 1, 1, 1, 0},
    {1, 0, 1, 0, 1},
    {1, 1, 1, 1, 1},
    {0, 1, 0, 1, 0},
    {0, 1, 1, 1, 0}
};

void drawIcon(const uint8_t icon[5][5], uint32_t color) {
    matrix.clear();
    for (int y = 0; y < 5; y++) {
        for (int x = 0; x < 5; x++) {
            if (icon[y][x]) {
                matrix.setPixelColor(y * 5 + x, color);
            }
        }
    }
    matrix.show();
}

void beep(int freq, int durationMs) {
    tone(PIN_BUZZER, freq, durationMs);
    delay(durationMs);
    noTone(PIN_BUZZER);
}

#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void onDataRecv(const esp_now_recv_info_t *recv_info, const uint8_t *data, int len) {
    const uint8_t *srcMac = recv_info->src_addr;
#else
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
    const uint8_t *srcMac = mac;
#endif
    if (len == sizeof(struct_vault_response)) {
        memcpy((void*)&lastResponse, data, sizeof(lastResponse));
        responseReceived = true;

        // If pairing succeeded, persist new YoloUNO MAC to NVS
        if (strcmp(lastResponse.status, "PAIR_OK") == 0) {
            memcpy(vaultMacAddress, srcMac, 6);
            isVaultPaired = true;
            badgePrefs.putBytes("vault_mac", vaultMacAddress, 6);
            badgePrefs.putBool("is_paired", true);
            Serial.printf("[PAIR SUCCESS] YoloUNO Vault paired and saved to NVS: %02X:%02X:%02X:%02X:%02X:%02X\n",
                          srcMac[0], srcMac[1], srcMac[2], srcMac[3], srcMac[4], srcMac[5]);

            if (!esp_now_is_peer_exist(srcMac)) {
                esp_now_peer_info_t peer = {};
                memcpy(peer.peer_addr, srcMac, 6);
                peer.channel = 1;
                peer.encrypt = false;
                esp_now_add_peer(&peer);
            }
        }
    }
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BUTTON_A, INPUT);
    pinMode(PIN_BUTTON_B, INPUT_PULLUP);
    pinMode(PIN_BUZZER, OUTPUT);

    matrix.begin();
    matrix.setBrightness(40);
    matrix.clear();
    matrix.show();

    // Fast multi-color startup sweep & ascending jingle
    const uint32_t startupColors[] = {
        matrix.Color(60, 0, 0),   // Red
        matrix.Color(60, 25, 0),  // Orange
        matrix.Color(60, 50, 0),  // Yellow
        matrix.Color(0, 60, 0),   // Green
        matrix.Color(0, 50, 60),  // Cyan
        matrix.Color(0, 0, 60),   // Blue
        matrix.Color(40, 0, 60)   // Purple
    };

    tone(PIN_BUZZER, 900, 70);
    for (int i = 0; i < NUM_LEDS; i++) {
        matrix.setPixelColor(i, startupColors[i % 7]);
        matrix.show();
        delay(12);
    }
    tone(PIN_BUZZER, 1400, 80);
    delay(80);
    tone(PIN_BUZZER, 2000, 140);
    delay(200);
    matrix.clear();
    matrix.show();

    Serial.println("\n==========================================");
    Serial.println("  Smart Safe Guardian - Yolo:Bit Badge");
    Serial.println("==========================================");

    // Load paired YoloUNO MAC from persistent NVS flash
    load_paired_vault();

    // Initialize Wi-Fi in Station mode on Channel 1
    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    esp_wifi_start();
    esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
    esp_wifi_set_ps(WIFI_PS_NONE);

    uint8_t myMac[6];
    esp_read_mac(myMac, ESP_MAC_WIFI_STA);
    Serial.printf("[INFO] Yolo:Bit MAC: %02X:%02X:%02X:%02X:%02X:%02X (Channel 1)\n",
                  myMac[0], myMac[1], myMac[2], myMac[3], myMac[4], myMac[5]);

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERROR] Failed to initialize ESP-NOW");
        return;
    }

    esp_now_register_recv_cb(onDataRecv);

    // 1. Register Broadcast peer (required for sending PAIR_REQ)
    esp_now_peer_info_t bcastPeer = {};
    memcpy(bcastPeer.peer_addr, BROADCAST_MAC, 6);
    bcastPeer.channel = 1;
    bcastPeer.encrypt = false;
    esp_now_add_peer(&bcastPeer);

    // 2. If already paired, register unicast peer for YoloUNO
    if (isVaultPaired) {
        esp_now_peer_info_t vaultPeer = {};
        memcpy(vaultPeer.peer_addr, vaultMacAddress, 6);
        vaultPeer.channel = 1;
        vaultPeer.encrypt = false;
        esp_now_add_peer(&vaultPeer);
        Serial.println("[OK] Unicast peer for paired YoloUNO registered successfully.");
    } else {
        Serial.println("[INFO] Running in Unpaired mode. Ready to pair (Hold A+B 1.5s).");
    }
}

void executeFeedback(const char* status) {
    Serial.printf("[FEEDBACK] Result: %s\n", status);

    const uint32_t COLOR_GREEN = matrix.Color(0, 50, 0);
    const uint32_t COLOR_BLUE  = matrix.Color(0, 30, 70);
    const uint32_t COLOR_RED   = matrix.Color(60, 0, 0);
    const uint32_t COLOR_AMBER = matrix.Color(60, 30, 0);
    const uint32_t COLOR_WHITE = matrix.Color(60, 60, 60);

    if (strcmp(status, "PAIR_OK") == 0) {
        // Pairing Successful: Green Checkmark -> Open Lock with happy double chime
        drawIcon(ICON_CHECK, COLOR_GREEN);
        beep(1600, 100);
        delay(150);
        beep(2400, 200);
        delay(400);

        drawIcon(ICON_LOCK_CLOSED, COLOR_BLUE);
        beep(2800, 250);
        delay(600);
    }
    else if (strcmp(status, "PAIR_DENIED") == 0) {
        // Pairing Denied (Vault not in pairing mode)
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(400, 300);
        delay(600);
    }
    else if (strcmp(status, "OK_UNLOCKED") == 0) {
        // 1. Green Tick
        drawIcon(ICON_CHECK, COLOR_GREEN);
        beep(1500, 120);
        delay(400);

        // 2. Green Open Padlock
        drawIcon(ICON_LOCK_OPEN, COLOR_GREEN);
        beep(2200, 180);
        delay(800);
    }
    else if (strcmp(status, "OK_LOCKED") == 0) {
        // 1. Green Tick
        drawIcon(ICON_CHECK, COLOR_GREEN);
        beep(1800, 120);
        delay(400);

        // 2. Blue Closed Padlock
        drawIcon(ICON_LOCK_CLOSED, COLOR_BLUE);
        beep(1100, 180);
        delay(800);
    }
    else if (strcmp(status, "OK_ACKED") == 0) {
        // 1. Red Alert Triangle (Intrusion being dismissed)
        drawIcon(ICON_WARNING, COLOR_RED);
        beep(800, 150);
        delay(450);

        // 2. Green Checkmark (Intrusion cleared / Safe is secure)
        drawIcon(ICON_CHECK, COLOR_GREEN);
        beep(1800, 100);
        delay(100);
        beep(2400, 180);
        delay(700);
    }
    else if (strcmp(status, "NO_ALERT_TO_ACK") == 0) {
        // Red Cross: No intrusion breach was active to acknowledge
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(400, 250);
        delay(700);
    }
    else if (strcmp(status, "DENIED_UNAUTHORIZED") == 0) {
        // 1. Red Cross
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(400, 120);
        delay(350);

        // 2. Pirate Skull with ominous low warning buzz
        drawIcon(ICON_SKULL, COLOR_WHITE);
        beep(320, 150);
        delay(80);
        beep(220, 300);
        delay(750);
    }
    else if (strcmp(status, "ALREADY_OPEN") == 0) {
        // 1. Red Cross
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(800, 100);
        delay(400);

        // 2. Amber Open Padlock
        drawIcon(ICON_LOCK_OPEN, COLOR_AMBER);
        beep(800, 100);
        delay(800);
    }
    else if (strcmp(status, "ALREADY_LOCKED") == 0) {
        // 1. Red Cross
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(800, 100);
        delay(400);

        // 2. Amber Closed Padlock
        drawIcon(ICON_LOCK_CLOSED, COLOR_AMBER);
        beep(800, 100);
        delay(800);
    }
    else if (strcmp(status, "DENIED_LOCKDOWN") == 0 ||
             strcmp(status, "DENIED_PRESENCE") == 0 ||
             strcmp(status, "DENIED") == 0) {
        // 1. Red Cross
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(400, 120);
        delay(400);

        // 2. Red No Entry
        drawIcon(ICON_NO_ENTRY, COLOR_RED);
        beep(400, 350);
        delay(800);
    }
    else { // Timeout / Unreachable
        drawIcon(ICON_CROSS, COLOR_RED);
        beep(300, 450);
        delay(900);
    }

    matrix.clear();
    matrix.show();
}

void sendBadgeCommand(const char* cmd) {
    strcpy(reqMsg.cmd, cmd);
    reqMsg.counter = ++msgCounter;
    responseReceived = false;

    // Visual transmission indicator: center pixel cyan/blue
    matrix.clear();
    matrix.setPixelColor(12, matrix.Color(0, 40, 90));
    matrix.show();

    // If pairing request, ALWAYS send to BROADCAST_MAC
    const uint8_t *targetMac = (strcmp(cmd, "PAIR_REQ") == 0) ? BROADCAST_MAC : vaultMacAddress;

    Serial.printf("[ACTION] Sending '%s' (counter: %lu) to %02X:%02X:%02X:%02X:%02X:%02X...\n",
                  cmd, (unsigned long)reqMsg.counter,
                  targetMac[0], targetMac[1], targetMac[2],
                  targetMac[3], targetMac[4], targetMac[5]);

    esp_now_send(targetMac, (uint8_t *)&reqMsg, sizeof(reqMsg));

    // Wait for response up to 1500ms (expanded timeout for reliability)
    const uint32_t startMs = millis();
    constexpr uint32_t TIMEOUT_MS = 1500;
    while (!responseReceived && (millis() - startMs < TIMEOUT_MS)) {
        delay(10);
    }

    // Minimum visual delay (350ms) so transmission state is clearly perceived
    const uint32_t elapsed = millis() - startMs;
    if (elapsed < 350) {
        delay(350 - elapsed);
    }

    if (responseReceived) {
        executeFeedback(lastResponse.status);
    } else {
        Serial.println("[TIMEOUT] No response received from YoloUNO.");
        executeFeedback("TIMEOUT");
    }
}

void loop() {
    static int lastA = HIGH;
    static int lastB = HIGH;

    int readingA = digitalRead(PIN_BUTTON_A);
    int readingB = digitalRead(PIN_BUTTON_B);

    // Combo A+B pressed simultaneously
    // Short Combo (< 1.5s) -> Fake / Rogue Unauthorized Badge
    // Long Combo (>= 1.5s)  -> Send PAIR_REQ to YoloUNO
    if ((readingA == LOW && readingB == LOW) && (lastA == HIGH || lastB == HIGH)) {
        const uint32_t comboStartMs = millis();
        bool isLongCombo = false;

        // Visual animation: center yellow dot while holding
        matrix.setPixelColor(12, matrix.Color(60, 40, 0));
        matrix.show();

        while (digitalRead(PIN_BUTTON_A) == LOW && digitalRead(PIN_BUTTON_B) == LOW) {
            if (!isLongCombo && (millis() - comboStartMs >= 1500)) {
                isLongCombo = true;
                beep(2400, 150); // Feedback beep indicating pairing request armed
                matrix.setPixelColor(12, matrix.Color(0, 80, 80)); // Cyan dot
                matrix.show();
            }
            delay(20);
        }

        if (isLongCombo) {
            Serial.println("[BADGE] Long Combo A+B (>= 1.5s) -> Initiating Secure PAIR_REQ...");
            sendBadgeCommand("PAIR_REQ");
        } else {
            Serial.println("[BADGE] Short Combo A+B (< 1.5s) -> Simulating Rogue FAKE_BADGE...");
            sendBadgeCommand("FAKE_BADGE");
        }
        delay(300);
        lastA = HIGH;
        lastB = HIGH;
        return;
    }
    // Button A pressed (Short press = Unlock, Long press >= 1.0s = Acknowledge Breach)
    else if (readingA == LOW && lastA == HIGH && readingB == HIGH) {
        const uint32_t pressStartMs = millis();
        bool isLongPress = false;

        while (digitalRead(PIN_BUTTON_A) == LOW) {
            // If button B is pressed while holding A -> Combo FAKE_BADGE!
            if (digitalRead(PIN_BUTTON_B) == LOW) {
                sendBadgeCommand("FAKE_BADGE");
                while (digitalRead(PIN_BUTTON_A) == LOW || digitalRead(PIN_BUTTON_B) == LOW) {
                    delay(20);
                }
                delay(200);
                lastA = HIGH;
                lastB = HIGH;
                return;
            }

            if (!isLongPress && (millis() - pressStartMs >= 1000)) {
                isLongPress = true;
                // Immediate feedback tone for long press trigger
                beep(2200, 100);
            }
            delay(20);
        }

        if (isLongPress) {
            // Long press on Button A -> Acknowledge breach alarm
            sendBadgeCommand("ACK_BREACH");
        } else {
            // Short press on Button A -> Unlock
            sendBadgeCommand("UNLOCK");
        }
        delay(200);
    }
    // Button B pressed -> Lock
    else if (readingB == LOW && lastB == HIGH && readingA == HIGH) {
        // Small delay to check if A is also being pressed for combo
        delay(50);
        if (digitalRead(PIN_BUTTON_A) == LOW) {
            sendBadgeCommand("FAKE_BADGE");
            while (digitalRead(PIN_BUTTON_A) == LOW || digitalRead(PIN_BUTTON_B) == LOW) {
                delay(20);
            }
        } else {
            sendBadgeCommand("LOCK");
            while (digitalRead(PIN_BUTTON_B) == LOW) {
                delay(20);
            }
        }
        delay(200);
    }

    lastA = digitalRead(PIN_BUTTON_A);
    lastB = digitalRead(PIN_BUTTON_B);

    // Listen for USB Serial commands (e.g. reboot)
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd == "reboot" || cmd == "restart") {
            Serial.println("[CMD] Rebooting Yolo:Bit Badge...");
            delay(200);
            esp_restart();
        }
    }

    delay(50);
}
