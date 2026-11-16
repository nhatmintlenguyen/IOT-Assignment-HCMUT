#include "sensor_snapshot.h"

namespace {
SensorSnapshot currentSnapshot;
portMUX_TYPE snapshotMux = portMUX_INITIALIZER_UNLOCKED;
}

SensorSnapshot get_sensor_snapshot() {
    SensorSnapshot copy;
    portENTER_CRITICAL(&snapshotMux);
    copy = currentSnapshot;
    portEXIT_CRITICAL(&snapshotMux);
    return copy;
}

void set_climate_reading(float temperatureC, float humidityPct, bool valid) {
    portENTER_CRITICAL(&snapshotMux);
    currentSnapshot.climateValid = valid;
    if (valid) {
        currentSnapshot.temperatureC = temperatureC;
        currentSnapshot.humidityPct = humidityPct;
    }
    portEXIT_CRITICAL(&snapshotMux);
}

void set_light_reading(int lightAdc) {
    portENTER_CRITICAL(&snapshotMux);
    currentSnapshot.lightAdc = lightAdc;
    portEXIT_CRITICAL(&snapshotMux);
}
