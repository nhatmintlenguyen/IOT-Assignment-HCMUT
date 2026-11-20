#include "lcd_display.h"
#include "LiquidCrystal_I2C.h"
#include "ir_reader.h"
#include "vault_state.h"

namespace {
// Address 33 (0x21) is retained from the existing firmware.
LiquidCrystal_I2C lcd(33, 16, 2);

constexpr uint8_t TOTAL_PAGES = 3;
constexpr uint32_t PAGE_DURATION_MS = 4000; // 4 seconds auto-scroll per user request
constexpr uint32_t DISPLAY_REFRESH_INTERVAL_MS = 200;
constexpr uint32_t BACKLIGHT_TIMEOUT_MS = 60000; // 1 minute auto-sleep timeout

uint8_t currentPage = 1; // 0 = Welcome, 1 = Climate, 2 = Light/State
uint32_t lastPageChangeMs = 0;
uint32_t lastDisplayUpdateMs = 0;
uint32_t lastActivityMs = 0;
uint32_t bootUntilMs = 0;
bool wasStandby = false;
bool manualNav = false;
bool backlightEnabled = true;
char notifyLine0[17] = "";
char notifyLine1[17] = "";
uint32_t notifyUntilMs = 0;

void set_backlight(bool on) {
    if (backlightEnabled != on) {
        backlightEnabled = on;
        if (on) {
            lcd.backlight();
        } else {
            lcd.noBacklight();
        }
    }
}

void print_padded_line(uint8_t row, const char* text) {
    lcd.setCursor(0, row);
    lcd.print(text);
    size_t length = strlen(text);
    while (length++ < 16) {
        lcd.print(' ');
    }
}
}

void lcd_display_wake() {
    lastActivityMs = millis();
    if (!backlightEnabled) {
        set_backlight(true);
        lastDisplayUpdateMs = 0; // Force immediate LCD redraw
    }
}

void lcd_display_begin() {
    lcd.begin();
    lcd.backlight();
    lcd.clear();
    bootUntilMs = millis() + 2000; // Keep startup splash screen visible for 2 seconds
    lastActivityMs = millis();
    backlightEnabled = true;
    print_padded_line(0, "Smart Safe");
    print_padded_line(1, "Guardian v1.0");
}

void lcd_display_next_page() {
    lcd_display_wake();
}

void lcd_display_prev_page() {
    lcd_display_wake();
}

void lcd_show_notification(const char* line0, const char* line1, uint32_t durationMs) {
    lcd_display_wake();
    snprintf(notifyLine0, sizeof(notifyLine0), "%s", line0 ? line0 : "");
    snprintf(notifyLine1, sizeof(notifyLine1), "%s", line1 ? line1 : "");
    notifyUntilMs = millis() + durationMs;
    lastDisplayUpdateMs = 0; // Force immediate LCD redraw
}

void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status) {
    const uint32_t now = millis();

    // Keep startup splash screen on display during initial 2 seconds
    if (now < bootUntilMs) {
        return;
    }

    const bool isStandby = (status.standbyActive || sensors.personNear);
    const uint8_t pinCount = ir_reader_get_pin_count();

    // Any physical or security event wakes up the screen and keeps it active
    const bool activeEvent = isStandby ||
                             status.breachActive ||
                             status.lockdownActive ||
                             (status.lockState == LockState::Unlocked) ||
                             is_pairing_mode_active() ||
                             (pinCount > 0) ||
                             ir_reader_is_pin_error() ||
                             ir_reader_is_presence_error() ||
                             ir_reader_is_pin_success() ||
                             (now < notifyUntilMs);

    if (activeEvent) {
        lastActivityMs = now;
        if (!backlightEnabled) {
            set_backlight(true);
            lastDisplayUpdateMs = 0; // Immediate redraw on wake
        }
    } else {
        // Auto sleep after 1 minute of complete inactivity
        if (backlightEnabled && (now - lastActivityMs >= BACKLIGHT_TIMEOUT_MS)) {
            set_backlight(false);
        }
    }

    // 1. Transition into detected proximity / standby -> IMMEDIATELY PAGE 0!
    if (isStandby && !wasStandby) {
        wasStandby = true;
        manualNav = false;
        currentPage = 0; // Immediate Welcome / Interaction screen without delay!
        lastDisplayUpdateMs = 0;
    } 
    // 2. Transition to person departure / exit standby
    else if (!isStandby && wasStandby) {
        wasStandby = false;
        manualNav = false;
        currentPage = 1; // Return to default metrics cycle
        lastPageChangeMs = now;
        lastDisplayUpdateMs = 0;
    }

    // Auto-scroll ONLY in normal idle mode (no proximity/standby active)
    bool pageChanged = false;
    if (!isStandby) {
        if (now - lastPageChangeMs >= PAGE_DURATION_MS) {
            currentPage = (currentPage == 1) ? 2 : 1; // Cycles between Climate (1) and Security/Light (2)
            lastPageChangeMs = now;
            pageChanged = true;
        }
    }

    if (!pageChanged && (now - lastDisplayUpdateMs < DISPLAY_REFRESH_INTERVAL_MS)) {
        return;
    }
    lastDisplayUpdateMs = now;

    // While backlight is sleeping and safe is idle, avoid writing to I2C bus
    if (!backlightEnabled) {
        return;
    }

    // --- TRANSIENT NOTIFICATION (Method / Action feedback for ~1.2s) ---
    if (now < notifyUntilMs) {
        print_padded_line(0, notifyLine0);
        print_padded_line(1, notifyLine1);
        return;
    }

    // --- ABSOLUTE PRIORITIES ---

    // 0. Active Secure Pairing Window (Prioritaire sur Welcome et toutes les pages)
    if (is_pairing_mode_active()) {
        char line1[17];
        snprintf(line1, sizeof(line1), "Hold A+B | %2lus", (unsigned long)get_remaining_pairing_sec());
        print_padded_line(0, "[PAIRING MODE]");
        print_padded_line(1, line1);
        return;
    }

    // 1. Remote security lockdown from ThingsBoard / Supervisor
    if (status.lockdownActive) {
        print_padded_line(0, "VAULT LOCKDOWN");
        print_padded_line(1, "Access Disabled");
        return;
    }

    // 2. Active PIN entry error feedback
    if (ir_reader_is_pin_error()) {
        print_padded_line(0, "PIN INCORRECT");
        print_padded_line(1, "Try again");
        return;
    }

    // 3. PIN successfully changed confirmation
    if (ir_reader_is_pin_success()) {
        print_padded_line(0, "PIN CHANGED");
        print_padded_line(1, "Success!");
        return;
    }

    const uint8_t pinState = ir_reader_get_pin_state();
    // pinCount already fetched above

    // 4. Change PIN Prompts (prioritaire si en cours)
    if (pinState == 1 && status.lockState == LockState::Locked) {
        print_padded_line(0, "CHANGE PIN?");
        print_padded_line(1, "C:Yes   A:Cancel");
        return;
    }
    if (pinState == 2 && status.lockState == LockState::Locked) {
        print_padded_line(0, "ENTER OLD PIN");
        char pinDisplay[17] = "";
        for (int i = 0; i < 4; i++) {
            if (i < pinCount) strcat(pinDisplay, "* ");
            else strcat(pinDisplay, "_ ");
        }
        print_padded_line(1, pinDisplay);
        return;
    }
    if (pinState == 3 && status.lockState == LockState::Locked) {
        print_padded_line(0, "ENTER NEW PIN");
        char pinDisplay[17] = "";
        for (int i = 0; i < 4; i++) {
            if (i < pinCount) strcat(pinDisplay, "* ");
            else strcat(pinDisplay, "_ ");
        }
        print_padded_line(1, pinDisplay);
        return;
    }

    // 5. Standard masked PIN entry in progress (PRIORITAIRE sur l'alarme breach!)
    if (pinCount > 0 && status.lockState == LockState::Locked) {
        print_padded_line(0, "ENTER PIN (C=OK)");
        char pinDisplay[17] = "";
        for (int i = 0; i < 4; i++) {
            if (i < pinCount) strcat(pinDisplay, "* ");
            else strcat(pinDisplay, "_ ");
        }
        print_padded_line(1, pinDisplay);
        return;
    }

    // 6. Security breach alert (affiché si aucune saisie PIN en cours)
    if (status.breachActive) {
        print_padded_line(0, "SECURITY BREACH");
        print_padded_line(1, "Waiting for ACK");
        return;
    }

    // 7. Active vault unlocked state (live countdown + manual lock reminder)
    if (status.lockState == LockState::Unlocked) {
        char line1[17];
        snprintf(line1, sizeof(line1), "F: Lock | %2lus", (unsigned long)get_remaining_unlock_time_sec());
        print_padded_line(0, "DOOR UNLOCKED");
        print_padded_line(1, line1);
        return;
    }

    // 8. Presence error (remote unlock attempt without physical approach)
    if (ir_reader_is_presence_error()) {
        print_padded_line(0, "ACCESS DENIED");
        print_padded_line(1, "Approach first");
        return;
    }

    // --- STANDARD PAGES / MANUAL INSPECTION ---

    // Page 0: Interactive Welcome + Real-time Distance
    if (currentPage == 0) {
        char line0[17];
        if (sensors.distanceValid) {
            char distStr[7];
            if (sensors.distanceCm < 100.0f) {
                snprintf(distStr, sizeof(distStr), "%4.1fcm", sensors.distanceCm);
            } else {
                snprintf(distStr, sizeof(distStr), "%4.0fcm", sensors.distanceCm);
            }
            snprintf(line0, sizeof(line0), "Welcome | %-6s", distStr);
        } else {
            snprintf(line0, sizeof(line0), "Welcome | --.-cm");
        }
        print_padded_line(0, line0);
        print_padded_line(1, "Badge or IR PIN");
        return;
    }

    // Page 1: Climate (Temperature & Humidity)
    if (currentPage == 1) {
        if (sensors.climateValid) {
            char line[17];
            snprintf(line, sizeof(line), "Temp: %.1f C", sensors.temperatureC);
            print_padded_line(0, line);
            snprintf(line, sizeof(line), "Hum:  %.1f %%", sensors.humidityPct);
            print_padded_line(1, line);
        } else {
            print_padded_line(0, "DHT20 unavailable");
            print_padded_line(1, "Check I2C sensor");
        }
        return;
    }

    // Page 2: Ambient Light & Lock Status
    if (currentPage == 2) {
        char line[17];
        snprintf(line, sizeof(line), "Light: %d ADC", sensors.lightAdc);
        print_padded_line(0, line);
        print_padded_line(1, status.lockState == LockState::Locked ? "State: LOCKED" : "State: UNLOCKED");
        return;
    }
}
