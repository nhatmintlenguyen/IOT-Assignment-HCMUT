#include "vault_state.h"

namespace {
// Provisional values based on initial readings (dark ~= 101, illuminated ~= 3609).
// Recalibrate with the sensor installed inside the closed enclosure.
constexpr int LIGHT_BREACH_THRESHOLD = 1200;
constexpr int LIGHT_BREACH_RESET_THRESHOLD = 800;
constexpr uint8_t REQUIRED_BRIGHT_SAMPLES = 3;

LockState lockState = LockState::Locked;
bool breachActive = false;
uint8_t consecutiveBrightSamples = 0;
portMUX_TYPE statusMux = portMUX_INITIALIZER_UNLOCKED;
}

VaultStatus get_vault_status() {
    VaultStatus copy;
    portENTER_CRITICAL(&statusMux);
    copy = {lockState, breachActive};
    portEXIT_CRITICAL(&statusMux);
    return copy;
}

void set_lock_state(LockState state) {
    portENTER_CRITICAL(&statusMux);
    lockState = state;
    consecutiveBrightSamples = 0;
    portEXIT_CRITICAL(&statusMux);
}

bool observe_light_level(int lightAdc) {
    bool triggerBreach = false;

    portENTER_CRITICAL(&statusMux);
    if (lightAdc <= LIGHT_BREACH_RESET_THRESHOLD) {
        consecutiveBrightSamples = 0;
        breachActive = false;
    } else if (lockState == LockState::Locked && lightAdc >= LIGHT_BREACH_THRESHOLD) {
        if (consecutiveBrightSamples < REQUIRED_BRIGHT_SAMPLES) {
            ++consecutiveBrightSamples;
        }

        if (consecutiveBrightSamples >= REQUIRED_BRIGHT_SAMPLES && !breachActive) {
            breachActive = true;
            triggerBreach = true;
        }
    } else {
        consecutiveBrightSamples = 0;
    }
    portEXIT_CRITICAL(&statusMux);

    return triggerBreach;
}
