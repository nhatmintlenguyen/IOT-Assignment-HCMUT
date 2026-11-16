#include "vault_state.h"
#include "servo_control.h"

namespace {
// Provisional values based on initial readings (dark ~= 101, illuminated ~= 3609).
// Recalibrate with the sensor installed inside the closed enclosure.
constexpr int LIGHT_BREACH_THRESHOLD = 1200;
constexpr int LIGHT_BREACH_RESET_THRESHOLD = 800;
constexpr uint8_t REQUIRED_BRIGHT_SAMPLES = 3;
constexpr uint32_t AUTO_RELOCK_DURATION_MS = 10000;  // 10s auto-relock per requirements
constexpr uint32_t STANDBY_DURATION_MS = 10000;      // 10s approach standby window

LockState lockState = LockState::Locked;
bool breachActive = false;
uint8_t consecutiveBrightSamples = 0;
uint32_t unlockedAtMs = 0;
uint32_t standbyUntilMs = 0;
portMUX_TYPE statusMux = portMUX_INITIALIZER_UNLOCKED;
}

VaultStatus get_vault_status() {
    VaultStatus copy;
    const uint32_t now = millis();
    portENTER_CRITICAL(&statusMux);
    const bool isStandby = (lockState == LockState::Locked) && (now < standbyUntilMs);
    copy = {lockState, breachActive, isStandby};
    portEXIT_CRITICAL(&statusMux);
    return copy;
}

void trigger_approach_standby() {
    portENTER_CRITICAL(&statusMux);
    standbyUntilMs = millis() + STANDBY_DURATION_MS;
    portEXIT_CRITICAL(&statusMux);
}

void set_lock_state(LockState state) {
    portENTER_CRITICAL(&statusMux);
    lockState = state;
    consecutiveBrightSamples = 0;
    if (state == LockState::Unlocked) {
        unlockedAtMs = millis();
        standbyUntilMs = 0; // Cancel standby once unlocked
    }
    portEXIT_CRITICAL(&statusMux);

    if (state == LockState::Unlocked) {
        servo_set_unlocked();
    } else {
        servo_set_locked();
    }
}

void request_unlock() {
    set_lock_state(LockState::Unlocked);
    Serial.println("{\"type\":\"event\",\"event\":\"access\",\"status\":\"granted\"}");
}

void vault_state_tick() {
    bool shouldRelock = false;
    portENTER_CRITICAL(&statusMux);
    if (lockState == LockState::Unlocked && (millis() - unlockedAtMs >= AUTO_RELOCK_DURATION_MS)) {
        lockState = LockState::Locked;
        shouldRelock = true;
    }
    portEXIT_CRITICAL(&statusMux);

    if (shouldRelock) {
        servo_set_locked();
        Serial.println("{\"type\":\"event\",\"event\":\"auto_locked\",\"state\":\"LOCKED\"}");
    }
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
