#include "lcd_display.h"
#include "LiquidCrystal_I2C.h"

namespace {
// Address 33 (0x21) is retained from the existing firmware. Confirm with an I2C scan
// if the display has a backlight but does not show characters.
LiquidCrystal_I2C lcd(33, 16, 2);
constexpr uint32_t PAGE_DURATION_MS = 3000;
constexpr uint32_t DISPLAY_REFRESH_INTERVAL_MS = 500;
uint8_t currentPage = 0;
uint32_t lastPageChangeMs = 0;
uint32_t lastDisplayUpdateMs = 0;

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

void lcd_display_update(const SensorSnapshot& sensors, const VaultStatus& status) {
    const uint32_t now = millis();
    bool pageChanged = false;
    if (now - lastPageChangeMs >= PAGE_DURATION_MS) {
        currentPage = (currentPage + 1) % 3;
        lastPageChangeMs = now;
        pageChanged = true;
    }
    if (!pageChanged && now - lastDisplayUpdateMs < DISPLAY_REFRESH_INTERVAL_MS) {
        return;
    }
    lastDisplayUpdateMs = now;

    if (status.breachActive) {
        print_padded_line(0, "SECURITY BREACH");
        print_padded_line(1, "Check enclosure");
        return;
    }

    if (status.lockState == LockState::Unlocked) {
        print_padded_line(0, "DOOR UNLOCKED");
        print_padded_line(1, "Auto-lock in 10s");
        return;
    }

    if (status.lockState == LockState::Locked && sensors.personNear) {
        print_padded_line(0, "Welcome");
        print_padded_line(1, "Badge or IR PIN");
        return;
    }

    if (currentPage == 0) {
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

    if (currentPage == 1) {
        char line[17];
        snprintf(line, sizeof(line), "Light: %d ADC", sensors.lightAdc);
        print_padded_line(0, line);
        print_padded_line(1, status.lockState == LockState::Locked ? "State: LOCKED" : "State: UNLOCKED");
        return;
    }

    char line[17];
    if (sensors.distanceValid) {
        snprintf(line, sizeof(line), "Distance: %.1fcm", sensors.distanceCm);
    } else {
        snprintf(line, sizeof(line), "Distance: --.-cm");
    }
    print_padded_line(0, line);
    print_padded_line(1, sensors.personNear ? "Person: NEAR" : "Person: away");
}
