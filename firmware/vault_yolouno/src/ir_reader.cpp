#include "ir_reader.h"
#include "ir_remote_keys.h"
#include "vault_state.h"

// Grove socket D6-D5 maps: D5 = GPIO 8, D6 = GPIO 9.
// Grove 1-signal modules use Pin 1 (Yellow) = D5 = GPIO 8.
#define IR_RECEIVE_PIN 8
#define DECODE_NEC // Optimize: handheld remote uses standard NEC protocol
#include <IRremote.hpp>

namespace {
char pinBuffer[5] = "";
uint8_t pinLength = 0;
uint32_t lastDigitMs = 0;
uint32_t pinErrorUntilMs = 0;
constexpr uint32_t PIN_INPUT_TIMEOUT_MS = 10000;
}

void ir_reader_init() {
    IrReceiver.begin(IR_RECEIVE_PIN);
    Serial.println("[IR] Receiver initialisé sur GPIO 8 (Grove D6-D5).");
}

uint8_t ir_reader_get_pin_count() {
    return pinLength;
}

bool ir_reader_is_pin_error() {
    return millis() < pinErrorUntilMs;
}

void ir_reader_tick() {
    const uint32_t now = millis();

    // Timeout de saisie : si inactif pendant 10s, effacer la saisie
    if (pinLength > 0 && (now - lastDigitMs >= PIN_INPUT_TIMEOUT_MS)) {
        pinLength = 0;
        pinBuffer[0] = '\0';
        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"timeout_cleared\"}");
    }

    if (IrReceiver.decode()) {
        if (!(IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT)) {
            const uint16_t command = IrReceiver.decodedIRData.command;
            const char key = ir_code_to_char(command);

            // 1. Touche chiffre '0'-'9'
            if (key >= '0' && key <= '9') {
                if (pinLength < 4) {
                    pinBuffer[pinLength++] = key;
                    pinBuffer[pinLength] = '\0';
                    lastDigitMs = now;
                    trigger_approach_standby(); // Réveille ou prolonge la veille active

                    Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"digit\",\"entered\":%d}\n",
                                  pinLength);
                }
            }
            // 2. Touche 'C' : Valider le code PIN
            else if (key == 'C') {
                if (pinLength == 4 && strcmp(pinBuffer, "1234") == 0) {
                    Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"granted\"}");
                    request_unlock();
                } else {
                    Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"denied\",\"digits\":%d}\n", pinLength);
                    pinErrorUntilMs = now + 2000; // Afficher erreur pendant 2 secondes
                }
                pinLength = 0;
                pinBuffer[0] = '\0';
            }
            // 3. Touche 'D' : Effacer la saisie
            else if (key == 'D') {
                pinLength = 0;
                pinBuffer[0] = '\0';
                Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"cleared\"}");
            }
            // 4. Autre touche non gérée
            else {
                Serial.printf("{\"type\":\"event\",\"source\":\"ir_remote\",\"key\":\"%c\",\"cmd\":\"0x%02X\"}\n",
                              key ? key : '?', command);
            }
        }
        IrReceiver.resume();
    }
}
