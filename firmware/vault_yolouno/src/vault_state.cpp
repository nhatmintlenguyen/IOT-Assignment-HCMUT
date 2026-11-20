#include "vault_state.h"
#include "servo_control.h"

namespace {
// Provisional values based on initial readings (dark ~= 101, illuminated ~= 3609).
// Recalibrate with the sensor installed inside the closed enclosure.
constexpr int LIGHT_BREACH_THRESHOLD = 1200;
constexpr int LIGHT_BREACH_RESET_THRESHOLD = 800;
constexpr uint8_t REQUIRED_BRIGHT_SAMPLES = 3;
constexpr uint32_t AUTO_RELOCK_DURATION_MS = 30000;  // 30s auto-relock per requirements
constexpr uint32_t STANDBY_DURATION_MS = 10000;      // 10s approach standby window

LockState lockState = LockState::Locked;
bool breachActive = false;
bool breachLatched = false;
bool lockdownActive = false;
uint8_t failedAttemptsCount = 0;
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
    copy = {lockState, breachActive, isStandby, lockdownActive};
    portEXIT_CRITICAL(&statusMux);
    return copy;
}

void trigger_approach_standby() {
    portENTER_CRITICAL(&statusMux);
    if (!lockdownActive) {
        standbyUntilMs = millis() + STANDBY_DURATION_MS;
    }
    portEXIT_CRITICAL(&statusMux);
}

void extend_standby_if_active() {
    portENTER_CRITICAL(&statusMux);
    if (!lockdownActive && (lockState == LockState::Locked) && (millis() < standbyUntilMs)) {
        standbyUntilMs = millis() + STANDBY_DURATION_MS;
    }
    portEXIT_CRITICAL(&statusMux);
}

void set_lock_state(LockState state) {
    portENTER_CRITICAL(&statusMux);
    if (lockdownActive && state == LockState::Unlocked) {
        portEXIT_CRITICAL(&statusMux);
        Serial.println("{\"type\":\"event\",\"event\":\"lockdown_blocked\",\"action\":\"unlock\"}");
        return;
    }

    lockState = state;
    consecutiveBrightSamples = 0;
    if (state == LockState::Unlocked) {
        unlockedAtMs = millis();
        standbyUntilMs = 0; // Cancel standby once unlocked
        breachLatched = false;
        breachActive = false;
    }
    portEXIT_CRITICAL(&statusMux);

    if (state == LockState::Unlocked) {
        servo_set_unlocked();
    } else {
        servo_set_locked();
    }
}

void request_unlock() {
    reset_failed_attempts();
    set_lock_state(LockState::Unlocked);
}

void trigger_breach() {
    portENTER_CRITICAL(&statusMux);
    breachLatched = true;
    breachActive = true;
    portEXIT_CRITICAL(&statusMux);
}

void acknowledge_breach() {
    portENTER_CRITICAL(&statusMux);
    breachLatched = false;
    breachActive = false;
    consecutiveBrightSamples = 0;
    portEXIT_CRITICAL(&statusMux);
    Serial.println("{\"type\":\"event\",\"event\":\"breach_acknowledged\"}");
}

void set_lockdown(bool active) {
    portENTER_CRITICAL(&statusMux);
    lockdownActive = active;
    if (active) {
        lockState = LockState::Locked;
        standbyUntilMs = 0;
    } else {
        failedAttemptsCount = 0;
    }
    portEXIT_CRITICAL(&statusMux);

    if (active) {
        servo_set_locked();
        Serial.println("{\"type\":\"event\",\"event\":\"lockdown_enabled\"}");
    } else {
        Serial.println("{\"type\":\"event\",\"event\":\"lockdown_disabled\"}");
    }
}

bool is_lockdown_active() {
    portENTER_CRITICAL(&statusMux);
    const bool active = lockdownActive;
    portEXIT_CRITICAL(&statusMux);
    return active;
}

void reset_failed_attempts() {
    portENTER_CRITICAL(&statusMux);
    failedAttemptsCount = 0;
    portEXIT_CRITICAL(&statusMux);
}

void record_failed_attempt(const char* source) {
    portENTER_CRITICAL(&statusMux);
    failedAttemptsCount++;
    const uint8_t count = failedAttemptsCount;
    portEXIT_CRITICAL(&statusMux);

    Serial.printf("{\"type\":\"event\",\"source\":\"%s\",\"event\":\"auth_failed\",\"attempt\":%u,\"max\":3}\n",
                  source ? source : "unknown", count);

    if (count >= 3) {
        Serial.println("{\"type\":\"alarm\",\"alarm\":\"bruteforce_detected\",\"action\":\"lockdown_engaged\"}");
        set_lockdown(true);
        reset_failed_attempts();
    }
}

uint32_t get_remaining_unlock_time_sec() {
    uint32_t remainingSec = 0;
    portENTER_CRITICAL(&statusMux);
    if (lockState == LockState::Unlocked) {
        const uint32_t elapsed = millis() - unlockedAtMs;
        if (elapsed < AUTO_RELOCK_DURATION_MS) {
            remainingSec = (AUTO_RELOCK_DURATION_MS - elapsed + 999) / 1000;
        }
    }
    portEXIT_CRITICAL(&statusMux);
    return remainingSec;
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
    if (lockState == LockState::Locked && lightAdc >= LIGHT_BREACH_THRESHOLD) {
        if (consecutiveBrightSamples < REQUIRED_BRIGHT_SAMPLES) {
            ++consecutiveBrightSamples;
        }

        if (consecutiveBrightSamples >= REQUIRED_BRIGHT_SAMPLES && !breachLatched) {
            breachLatched = true;
            breachActive = true;
            triggerBreach = true;
        }
    } else if (lightAdc <= LIGHT_BREACH_RESET_THRESHOLD) {
        consecutiveBrightSamples = 0;
        // Keep breachLatched active until manual acknowledgment or authorized unlock!
    } else {
        consecutiveBrightSamples = 0;
    }
    breachActive = breachLatched;
    portEXIT_CRITICAL(&statusMux);

    return triggerBreach;
}
