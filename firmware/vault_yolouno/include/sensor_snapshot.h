#pragma once

#include <Arduino.h>

struct SensorSnapshot {
    float temperatureC = 0.0f;
    float humidityPct = 0.0f;
    int lightAdc = 0;
    float distanceCm = 0.0f;
    bool climateValid = false;
    bool distanceValid = false;
    bool personNear = false;
};

SensorSnapshot get_sensor_snapshot();
void set_climate_reading(float temperatureC, float humidityPct, bool valid);
void set_light_reading(int lightAdc);
void set_proximity_reading(float distanceCm, bool valid, bool personNear);
