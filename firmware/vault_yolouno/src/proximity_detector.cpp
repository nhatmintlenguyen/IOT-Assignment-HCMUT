#include "proximity_detector.h"

#include <Arduino.h>

namespace {
constexpr float APPROACH_DISTANCE_CM = 30.0f;
constexpr float LEAVE_DISTANCE_CM = 35.0f;
constexpr uint8_t REQUIRED_NEAR_SAMPLES = 2;

bool personNear = false;
uint8_t consecutiveNearSamples = 0;
}

ProximityResult update_proximity(float distanceCm, bool readingValid) {
    bool enteredRange = false;
    if (!readingValid) {
        return {personNear, false};
    }

    if (personNear) {
        if (distanceCm >= LEAVE_DISTANCE_CM) {
            personNear = false;
            consecutiveNearSamples = 0;
        }
        return {personNear, false};
    }

    if (distanceCm < APPROACH_DISTANCE_CM) {
        if (consecutiveNearSamples < REQUIRED_NEAR_SAMPLES) {
            ++consecutiveNearSamples;
        }
        if (consecutiveNearSamples >= REQUIRED_NEAR_SAMPLES) {
            personNear = true;
            enteredRange = true;
        }
    } else {
        consecutiveNearSamples = 0;
    }

    return {personNear, enteredRange};
}
