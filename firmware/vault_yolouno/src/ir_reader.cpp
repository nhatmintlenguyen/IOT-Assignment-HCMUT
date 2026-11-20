#include "ir_reader.h"
#include "ir_remote_keys.h"
#include "vault_state.h"
#include "sensor_snapshot.h"
#include "lcd_display.h"

extern void start_pairing_mode();

// Grove socket D6-D5 maps: D5 = GPIO 8, D6 = GPIO 9.
// Grove 1-signal modules use Pin 1 (Yellow) = D5 = GPIO 8.
#define IR_RECEIVE_PIN 8
#define DECODE_NEC // Optimize: handheld remote uses standard NEC protocol
#include <IRremote.hpp>

namespace {
char pinBuffer[5] = "";
char currentPin[5] = "1234";
uint8_t pinLength = 0;
uint8_t pinSubState = 0; // 0=Normal, 1=Prompt, 2=EnterOldPin, 3=EnterNewPin
uint32_t lastDigitMs = 0;
uint32_t pinErrorUntilMs = 0;
uint32_t pinPresenceErrorUntilMs = 0;
uint32_t pinSuccessUntilMs = 0;
constexpr uint32_t PIN_INPUT_TIMEOUT_MS = 10000;
}

void ir_reader_init() {
    IrReceiver.begin(IR_RECEIVE_PIN);
    Serial.println("[IR] Receiver initialized on GPIO 8 (Grove D6-D5).");
}

uint8_t ir_reader_get_pin_count() {
    return pinLength;
}

bool ir_reader_is_pin_error() {
    return millis() < pinErrorUntilMs;
}

bool ir_reader_is_presence_error() {
    return millis() < pinPresenceErrorUntilMs;
}

bool ir_reader_is_pin_success() {
    return millis() < pinSuccessUntilMs;
}

uint8_t ir_reader_get_pin_state() {
    return pinSubState;
}

void ir_reader_tick() {
    const uint32_t now = millis();

    // PIN input timeout: clear buffer if inactive for 10s
    if (pinLength > 0 && (now - lastDigitMs >= PIN_INPUT_TIMEOUT_MS)) {
        pinLength = 0;
        pinBuffer[0] = '\0';
        pinSubState = 0;
        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"timeout_cleared\"}");
    }

    if (IrReceiver.decode()) {
        lcd_display_wake();
        if (!(IrReceiver.decodedIRData.flags & IRDATA_FLAGS_IS_REPEAT)) {
            const uint16_t command = IrReceiver.decodedIRData.command;
            const char key = ir_code_to_char(command);

            const VaultStatus status = get_vault_status();
            const SensorSnapshot sensors = get_sensor_snapshot();
            const bool hasPresence = (sensors.personNear || status.standbyActive);

            // When locked, any IR remote key requires physical presence (<30cm)
            if (status.lockState == LockState::Locked && !status.breachActive && !hasPresence) {
                pinLength = 0;
                pinBuffer[0] = '\0';
                pinSubState = 0;
                pinPresenceErrorUntilMs = now + 2000;
                Serial.printf("{\"type\":\"event\",\"source\":\"ir_remote\",\"key\":\"%c\",\"result\":\"denied_no_presence\"}\n",
                              key ? key : '?');
                IrReceiver.resume();
                return;
            }

            // --- KEY E : TRIGGER SECURE BADGE PAIRING MODE ---
            if (command == IR_KEY_E) {
                extend_standby_if_active();
                start_pairing_mode();
                IrReceiver.resume();
                return;
            }

            // --- SETTINGS KEY : CHANGE PIN INITIATION ---
            if (command == IR_KEY_CONFIG && status.lockState == LockState::Locked && !status.breachActive) {
                pinSubState = 1; // Prompt: "CHANGE PIN? / C:Yes   A:Cancel"
                pinLength = 0;
                pinBuffer[0] = '\0';
                lastDigitMs = now;
                extend_standby_if_active();
                Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"change_prompt\"}");
                IrReceiver.resume();
                return;
            }

            // --- STATE 1 : CHANGE PIN CONFIRMATION PROMPT ---
            if (pinSubState == 1) {
                if (key == 'C') { // User pressed C (Validate) to proceed
                    pinSubState = 2; // Prompt for current PIN
                    pinLength = 0;
                    pinBuffer[0] = '\0';
                    lastDigitMs = now;
                    extend_standby_if_active();
                    Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"enter_old_pin\"}");
                } else if (key == 'A') { // User pressed A (Cancel)
                    pinSubState = 0;
                    pinLength = 0;
                    pinBuffer[0] = '\0';
                    Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"change_canceled\"}");
                }
                IrReceiver.resume();
                return;
            }

            // --- STATE 2 : ENTER OLD PIN ---
            if (pinSubState == 2) {
                if (key >= '0' && key <= '9' && pinLength < 4) {
                    pinBuffer[pinLength++] = key;
                    pinBuffer[pinLength] = '\0';
                    lastDigitMs = now;
                    extend_standby_if_active();
                } else if (key == 'A') {
                    if (pinLength > 0) {
                        pinBuffer[--pinLength] = '\0';
                        lastDigitMs = now;
                    } else {
                        pinSubState = 0; // Cancel back to normal
                    }
                } else if (key == 'C') {
                    if (pinLength == 4 && strcmp(pinBuffer, currentPin) == 0) {
                        pinSubState = 3; // Old PIN correct! Proceed to enter new PIN
                        pinLength = 0;
                        pinBuffer[0] = '\0';
                        lastDigitMs = now;
                        extend_standby_if_active();
                        reset_failed_attempts();
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"old_pin_verified\"}");
                    } else {
                        pinErrorUntilMs = now + 2000;
                        pinSubState = 0;
                        pinLength = 0;
                        pinBuffer[0] = '\0';
                        record_failed_attempt("ir_pin_change");
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"denied_wrong_old_pin\"}");
                    }
                }
                IrReceiver.resume();
                return;
            }

            // --- STATE 3 : ENTER NEW PIN ---
            if (pinSubState == 3) {
                if (key >= '0' && key <= '9' && pinLength < 4) {
                    pinBuffer[pinLength++] = key;
                    pinBuffer[pinLength] = '\0';
                    lastDigitMs = now;
                    extend_standby_if_active();
                } else if (key == 'A') {
                    if (pinLength > 0) {
                        pinBuffer[--pinLength] = '\0';
                        lastDigitMs = now;
                    } else {
                        pinSubState = 0; // Cancel back to normal
                    }
                } else if (key == 'C') {
                    if (pinLength == 4) {
                        strcpy(currentPin, pinBuffer);
                        pinSuccessUntilMs = now + 2000;
                        pinSubState = 0;
                        pinLength = 0;
                        pinBuffer[0] = '\0';
                        Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"pin_changed\",\"new_pin\":\"%s\"}\n",
                                      currentPin);
                    } else {
                        pinErrorUntilMs = now + 2000;
                        pinSubState = 0;
                        pinLength = 0;
                        pinBuffer[0] = '\0';
                    }
                }
                IrReceiver.resume();
                return;
            }

            // --- STATE 0 : NORMAL UNLOCK OPERATION ---

            // 1. Digit key '0'-'9'
            if (key >= '0' && key <= '9') {
                if (pinLength < 4) {
                    pinBuffer[pinLength++] = key;
                    pinBuffer[pinLength] = '\0';
                    lastDigitMs = now;
                    extend_standby_if_active(); // Extend standby ONLY if already active

                    Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"digit\",\"entered\":%d}\n",
                                  pinLength);
                }
            }
            // 2. Key 'A' : Backspace / Delete last digit (or exit if empty)
            else if (key == 'A') {
                if (pinLength > 0) {
                    pinBuffer[--pinLength] = '\0';
                    lastDigitMs = now;
                    extend_standby_if_active();
                    Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"backspace\",\"remaining\":%d}\n", pinLength);
                    if (pinLength == 0) {
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"canceled\"}");
                    }
                }
            }
            // 3. Key 'B' : Acknowledge security breach
            else if (key == 'B') {
                if (status.breachActive) {
                    acknowledge_breach();
                    lcd_show_notification("PIN / IR REMOTE", "Breach Acked");
                    Serial.println("{\"type\":\"event\",\"source\":\"ir_remote\",\"action\":\"breach_acknowledged\"}");
                }
            }
            // 4. Key 'C' : Validate PIN code
            else if (key == 'C') {
                if (pinLength == 4 && strcmp(pinBuffer, currentPin) == 0) {
                    if (status.lockdownActive) {
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"denied_lockdown\"}");
                    } else if (status.breachActive) {
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"breach_acknowledged\"}");
                        reset_failed_attempts();
                        acknowledge_breach();
                        request_unlock();
                        lcd_show_notification("PIN CODE", "Breach Acked");
                    } else if (!sensors.personNear && !status.standbyActive) {
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"denied_no_presence\"}");
                        pinPresenceErrorUntilMs = now + 2000; // Show "ACCESS DENIED / Approach first"
                    } else {
                        Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"granted\"}");
                        reset_failed_attempts();
                        request_unlock();
                        lcd_show_notification("PIN CODE", "Access Granted");
                    }
                } else {
                    Serial.printf("{\"type\":\"event\",\"source\":\"ir_pin\",\"result\":\"denied\",\"digits\":%d}\n", pinLength);
                    record_failed_attempt("ir_pin");
                    pinErrorUntilMs = now + 2000; // Show error state for 2 seconds
                }
                pinLength = 0;
                pinBuffer[0] = '\0';
            }
            // 5. Key 'D' : Clear entire PIN buffer
            else if (key == 'D') {
                pinLength = 0;
                pinBuffer[0] = '\0';
                Serial.println("{\"type\":\"event\",\"source\":\"ir_pin\",\"action\":\"cleared\"}");
            }
            // 6. Key 'F' : Immediate manual lock when unlocked
            else if (key == 'F') {
                if (status.lockState == LockState::Unlocked) {
                    set_lock_state(LockState::Locked);
                    lcd_show_notification("PIN / IR REMOTE", "Vault Locked");
                    Serial.println("{\"type\":\"event\",\"source\":\"ir_remote\",\"action\":\"manual_lock\",\"state\":\"LOCKED\"}");
                }
                pinLength = 0;
                pinBuffer[0] = '\0';
            }
            // 7. Arrow keys: no longer used for page scrolling, wake display if sleeping
            else if (command == IR_KEY_RIGHT || command == IR_KEY_UP || command == IR_KEY_LEFT || command == IR_KEY_DOWN) {
                lcd_display_wake();
                extend_standby_if_active();
            }
            // 7. Other / unhandled key
            else {
                Serial.printf("{\"type\":\"event\",\"source\":\"ir_remote\",\"key\":\"%c\",\"cmd\":\"0x%02X\"}\n",
                              key ? key : '?', command);
            }
        }
        IrReceiver.resume();
    }
}
