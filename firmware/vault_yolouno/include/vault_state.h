#pragma once

#include <Arduino.h>

enum class LockState : uint8_t {
    Locked,
    Unlocked,
};

struct VaultStatus {
    LockState lockState;
    bool breachActive;
};

VaultStatus get_vault_status();
void set_lock_state(LockState state);
void request_unlock();
void vault_state_tick();

// Returns true once when a sustained light increase is detected while locked.
bool observe_light_level(int lightAdc);
