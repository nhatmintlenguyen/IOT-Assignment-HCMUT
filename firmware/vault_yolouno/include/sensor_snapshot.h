#pragma once

#include <Arduino.h>

struct SensorSnapshot {
    float temperatureC = 0.0f;
    float humidityPct = 0.0f;
    int lightAdc = 0;
    bool climateValid = false;
};

SensorSnapshot get_sensor_snapshot();
void set_climate_reading(float temperatureC, float humidityPct, bool valid);
void set_light_reading(int lightAdc);
