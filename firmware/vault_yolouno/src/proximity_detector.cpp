#include "proximity_detector.h"

#include <Arduino.h>

namespace {
constexpr float APPROACH_DISTANCE_CM = 30.0f;
constexpr float LEAVE_DISTANCE_CM = 35.0f;
constexpr uint8_t REQUIRED_NEAR_SAMPLES = 2;
constexpr uint8_t REQUIRED_AWAY_SAMPLES = 2;

bool personNear = false;
uint8_t consecutiveNearSamples = 0;
uint8_t consecutiveAwaySamples = 0;
}

ProximityResult update_proximity(float distanceCm, bool readingValid) {
    bool enteredRange = false;

    // Si pas d'écho (hors de portée) ou distance >= seuil de départ -> personne absente
    const bool isAway = (!readingValid || distanceCm >= LEAVE_DISTANCE_CM);
    // Présence confirmée seulement si mesure valide et < 30 cm
    const bool isNear = (readingValid && distanceCm > 1.0f && distanceCm < APPROACH_DISTANCE_CM);

    if (isNear) {
        consecutiveAwaySamples = 0;
        if (!personNear) {
            if (++consecutiveNearSamples >= REQUIRED_NEAR_SAMPLES) {
                personNear = true;
                enteredRange = true;
            }
        }
    } else if (isAway) {
        consecutiveNearSamples = 0;
        if (personNear) {
            if (++consecutiveAwaySamples >= REQUIRED_AWAY_SAMPLES) {
                personNear = false;
            }
        }
    }

    return {personNear, enteredRange};
}
