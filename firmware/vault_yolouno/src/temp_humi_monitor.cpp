#include "temp_humi_monitor.h"

DHT20 dht20;
LiquidCrystal_I2C lcd(33, 16, 2);

// Maximum plausible change during the five-second sampling interval.
const float MAX_TEMP_JUMP = 1.5;
const float MAX_HUMI_JUMP = 5.0;

void temp_humi_monitor(void *pvParameters) {
    Wire.begin(11, 12);
    Serial.begin(115200);
    dht20.begin();
    lcd.begin();
    lcd.backlight();

    bool first_run = true;

    while (1) {
        int status = dht20.read();
        float raw_temperature = dht20.getTemperature();
        float raw_humidity = dht20.getHumidity();

        // Check if any reads failed and exit early.
        if (status != DHT20_OK || isnan(raw_temperature) || isnan(raw_humidity) ||
            (raw_temperature == 0.0 && raw_humidity == 0.0)) {
            Serial.println("Failed to read from DHT sensor!");
            glob_temperature = -1;
            glob_humidity = -1;
            first_run = true;
        } else if (first_run) {
            // The first valid reading becomes the initial reference value.
            glob_temperature = raw_temperature;
            glob_humidity = raw_humidity;
            first_run = false;
        } else {
            // Reject a temperature spike that is physically implausible.
            if (abs(raw_temperature - glob_temperature) <= MAX_TEMP_JUMP) {
                glob_temperature = raw_temperature;
            } else {
                Serial.println("Warning: Temperature glitch rejected!");
            }

            // Reject a humidity spike that is physically implausible.
            if (abs(raw_humidity - glob_humidity) <= MAX_HUMI_JUMP) {
                glob_humidity = raw_humidity;
            } else {
                Serial.println("Warning: Humidity glitch rejected!");
            }
        }

        // Print the validated results.
        Serial.print("Humidity: ");
        Serial.print(glob_humidity);
        Serial.print("%  Temperature: ");
        Serial.print(glob_temperature);
        Serial.println("°C");

        lcd.setCursor(0, 0);
        lcd.print("Temp: ");
        lcd.print(glob_temperature, 2);
        lcd.write((uint8_t)223);
        lcd.print("C   ");

        lcd.setCursor(0, 1);
        lcd.print("Hum:  ");
        lcd.print(glob_humidity, 2);
        lcd.print("%   ");

        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}
