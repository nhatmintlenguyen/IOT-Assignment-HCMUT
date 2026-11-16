#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_arduino_version.h>
#include <Adafruit_NeoPixel.h>

// Official Yolo:Bit hardware pinout
#define PIN_BUTTON_A 35
#define PIN_BUTTON_B 14
#define PIN_BUZZER   25
#define PIN_RGB_LED  4
#define NUM_LEDS     25

Adafruit_NeoPixel matrix(NUM_LEDS, PIN_RGB_LED, NEO_GRB + NEO_KHZ800);

// Target YoloUNO MAC address
uint8_t vaultMacAddress[] = {0xA4, 0xCB, 0x8F, 0xF1, 0xF6, 0x60};

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
#else
void onDataRecv(const uint8_t *mac, const uint8_t *data, int len) {
#endif
    if (len == sizeof(struct_vault_response)) {
        memcpy((void*)&lastResponse, data, sizeof(lastResponse));
        responseReceived = true;
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

    WiFi.mode(WIFI_STA);
    Serial.print("[INFO] Yolo:Bit MAC: ");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERROR] Failed to initialize ESP-NOW");
        return;
    }

    esp_now_register_recv_cb(onDataRecv);

    // Register target peer (YoloUNO)
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, vaultMacAddress, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[ERROR] Failed to add YoloUNO peer");
    } else {
        Serial.println("[OK] YoloUNO peer registered successfully.");
    }
}

void executeFeedback(const char* status) {
    Serial.printf("[FEEDBACK] Result: %s\n", status);

    const uint32_t COLOR_GREEN = matrix.Color(0, 50, 0);
    const uint32_t COLOR_BLUE  = matrix.Color(0, 30, 70);
    const uint32_t COLOR_RED   = matrix.Color(60, 0, 0);
    const uint32_t COLOR_AMBER = matrix.Color(60, 30, 0);
    const uint32_t COLOR_WHITE = matrix.Color(60, 60, 60);

    if (strcmp(status, "OK_UNLOCKED") == 0) {
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

    Serial.printf("[ACTION] Sending '%s' (counter: %lu)...\n", cmd, (unsigned long)reqMsg.counter);
    esp_now_send(vaultMacAddress, (uint8_t *)&reqMsg, sizeof(reqMsg));

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

    // Combo A+B pressed simultaneously -> Simulate Fake / Rogue Unauthorized Badge
    if ((readingA == LOW && readingB == LOW) && (lastA == HIGH || lastB == HIGH)) {
        sendBadgeCommand("FAKE_BADGE");
        while (digitalRead(PIN_BUTTON_A) == LOW || digitalRead(PIN_BUTTON_B) == LOW) {
            delay(20);
        }
        delay(200);
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
    delay(50);
}
