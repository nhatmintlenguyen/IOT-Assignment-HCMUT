#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <Adafruit_NeoPixel.h>

// Broches matérielles officielles Yolo:Bit
#define PIN_BUTTON_A 35
#define PIN_BUTTON_B 14
#define PIN_BUZZER   25
#define PIN_RGB_LED  4
#define NUM_LEDS     25

Adafruit_NeoPixel matrix(NUM_LEDS, PIN_RGB_LED, NEO_GRB + NEO_KHZ800);

// Adresse MAC de la YoloUNO cible (relevée sur la carte de prêt)
uint8_t vaultMacAddress[] = {0xA4, 0xCB, 0x8F, 0xF1, 0xF6, 0x60};

// Structure du paquet ESP-NOW (KISS : pas d'overengineering)
typedef struct struct_message {
    char cmd[16];        // "UNLOCK" ou "DURESS"
    uint32_t counter;    // Compteur anti-rejeu simple
} struct_message;

struct_message myData;
uint32_t msgCounter = 0;

void beep(int freq, int durationMs) {
    tone(PIN_BUZZER, freq, durationMs);
    delay(durationMs);
    noTone(PIN_BUZZER);
}

void showColor(uint32_t color) {
    for (int i = 0; i < NUM_LEDS; i++) {
        matrix.setPixelColor(i, color);
    }
    matrix.show();
}

#include <esp_arduino_version.h>
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
void onDataSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
#else
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
#endif
    Serial.print("[ESP-NOW] Statut envoi : ");
    if (status == ESP_NOW_SEND_SUCCESS) {
        Serial.println("SUCCÈS (Reçu par YoloUNO)");
        showColor(matrix.Color(0, 50, 0)); // Vert
        beep(1800, 100);
    } else {
        Serial.println("ÉCHEC (YoloUNO hors de portée ou éteinte)");
        showColor(matrix.Color(50, 0, 0)); // Rouge
        beep(400, 250);
    }
    delay(400);
    matrix.clear();
    matrix.show();
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

    Serial.println("\n==========================================");
    Serial.println("  Smart Safe Guardian - Yolo:Bit Badge");
    Serial.println("==========================================");

    WiFi.mode(WIFI_STA);
    Serial.print("[INFO] Yolo:Bit MAC: ");
    Serial.println(WiFi.macAddress());

    if (esp_now_init() != ESP_OK) {
        Serial.println("[ERREUR] Échec initialisation ESP-NOW");
        return;
    }

    esp_now_register_send_cb(onDataSent);

    // Enregistrement du récepteur (YoloUNO)
    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, vaultMacAddress, 6);
    peerInfo.channel = 0;
    peerInfo.encrypt = false;

    if (esp_now_add_peer(&peerInfo) != ESP_OK) {
        Serial.println("[ERREUR] Échec ajout peer YoloUNO");
    } else {
        Serial.println("[OK] Peer YoloUNO enregistré avec succès.");
    }
}

void loop() {
    static int lastA = HIGH;
    static int lastB = HIGH;

    int readingA = digitalRead(PIN_BUTTON_A);
    int readingB = digitalRead(PIN_BUTTON_B);

    // Bouton A pressé -> Déverrouillage normal
    if (readingA == LOW && lastA == HIGH) {
        Serial.println("[ACTION] Bouton A pressé -> Envoi UNLOCK");
        strcpy(myData.cmd, "UNLOCK");
        myData.counter = ++msgCounter;
        esp_now_send(vaultMacAddress, (uint8_t *)&myData, sizeof(myData));
        delay(300); // Anti-rebond
    }

    // Bouton B pressé -> Alerte Duress (détresse)
    if (readingB == LOW && lastB == HIGH) {
        Serial.println("[ACTION] Bouton B pressé -> Envoi DURESS (alarme silencieuse)");
        strcpy(myData.cmd, "DURESS");
        myData.counter = ++msgCounter;
        esp_now_send(vaultMacAddress, (uint8_t *)&myData, sizeof(myData));
        delay(300); // Anti-rebond
    }

    lastA = readingA;
    lastB = readingB;
    delay(50);
}
