#include "lcd_display.h"
#include "LiquidCrystal_I2C.h"
#include "ir_reader.h"

namespace {
// Address 33 (0x21) is retained from the existing firmware.
LiquidCrystal_I2C lcd(33, 16, 2);

constexpr uint8_t TOTAL_PAGES = 4;
constexpr uint32_t PAGE_DURATION_MS = 4000; // 4 seconds auto-scroll per user request
constexpr uint32_t DISPLAY_REFRESH_INTERVAL_MS = 200;

uint8_t currentPage = 1; // 0 = Welcome, 1 = Climate, 2 = Light/State, 3 = Distance
uint32_t lastPageChangeMs = 0;
uint32_t lastDisplayUpdateMs = 0;
uint32_t approachDetectedMs = 0;
bool wasStandby = false;
bool manualNav = false;

void print_padded_line(uint8_t row, const char* text) {
    lcd.setCursor(0, row);
    lcd.print(text);
    size_t length = strlen(text);
    while (length++ < 16) {
        lcd.print(' ');
    }
}
}

void lcd_display_begin() {
    lcd.begin();
    lcd.backlight();
    lcd.clear();
    print_padded_line(0, "Smart Safe");
    print_padded_line(1, "Starting...");
}

void lcd_display_next_page() {
    manualNav = true;
    currentPage = (currentPage + 1) % TOTAL_PAGES;
    lastDisplayUpdateMs = 0; // Force immediate LCD redraw
}

void lcd_display_prev_page() {
    manualNav = true;
    currentPage = (currentPage + TOTAL_PAGES - 1) % TOTAL_PAGES;
    lastDisplayUpdateMs = 0; // Force immediate LCD redraw
}

void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status) {
    const uint32_t now = millis();
    const bool isStandby = (status.standbyActive || sensors.personNear);

    // 1. Transition vers présence détectée
    if (isStandby && !wasStandby) {
        wasStandby = true;
        manualNav = false;
        approachDetectedMs = now;
        currentPage = 3; // Afficher l'écran distance/présence d'abord !
        lastDisplayUpdateMs = 0;
    } 
    // 2. Transition vers fin de présence / fin de veille
    else if (!isStandby && wasStandby) {
        wasStandby = false;
        manualNav = false;
        currentPage = 1; // Retour direct au défilement des métriques
        lastPageChangeMs = now;
        lastDisplayUpdateMs = 0;
    }

    // Basculement automatique après 2s sur "Welcome / Badge or IR PIN" (si pas de nav manuelle)
    if (isStandby && !manualNav && currentPage == 3 && (now - approachDetectedMs >= 2000)) {
        currentPage = 0; // Page Welcome
        lastDisplayUpdateMs = 0;
    }

    // Défilement automatique UNIQUEMENT en mode veille normale (pas de présence/standby)
    bool pageChanged = false;
    if (!isStandby) {
        if (now - lastPageChangeMs >= PAGE_DURATION_MS) {
            currentPage = (currentPage % 3) + 1; // Défile entre page 1, 2, 3
            lastPageChangeMs = now;
            pageChanged = true;
        }
    }

    if (!pageChanged && (now - lastDisplayUpdateMs < DISPLAY_REFRESH_INTERVAL_MS)) {
        return;
    }
    lastDisplayUpdateMs = now;

    // --- PRIORITÉS ABSOLUES ---

    // 1. Alerte intrusion
    if (status.breachActive) {
        print_padded_line(0, "SECURITY BREACH");
        print_padded_line(1, "Check enclosure");
        return;
    }

    // 2. Déverrouillage actif
    if (status.lockState == LockState::Unlocked) {
        print_padded_line(0, "DOOR UNLOCKED");
        print_padded_line(1, "Auto-lock in 10s");
        return;
    }

    // 3. Erreur code PIN
    if (ir_reader_is_pin_error()) {
        print_padded_line(0, "PIN INCORRECT");
        print_padded_line(1, "Try again");
        return;
    }

    // 4. Saisie en cours d'un code PIN (masqué)
    const uint8_t pinCount = ir_reader_get_pin_count();
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

    // --- PAGES STANDARDS / CONSULTATION MANUELLE ---

    // Page 0 : Accueil / Invitation à badger ou taper le PIN
    if (currentPage == 0) {
        print_padded_line(0, "Welcome");
        print_padded_line(1, "Badge or IR PIN");
        return;
    }

    // Page 1 : Climat (Température & Humidité)
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

    // Page 2 : Lumière & État de verrouillage
    if (currentPage == 2) {
        char line[17];
        snprintf(line, sizeof(line), "Light: %d ADC", sensors.lightAdc);
        print_padded_line(0, line);
        print_padded_line(1, status.lockState == LockState::Locked ? "State: LOCKED" : "State: UNLOCKED");
        return;
    }

    // Page 3 : Distance & Proximité
    if (currentPage == 3) {
        char line[17];
        if (sensors.distanceValid) {
            snprintf(line, sizeof(line), "Distance: %.1fcm", sensors.distanceCm);
        } else {
            snprintf(line, sizeof(line), "Distance: --.-cm");
        }
        print_padded_line(0, line);
        print_padded_line(1, sensors.personNear ? "Person: NEAR" : "Person: away");
        return;
    }
}
