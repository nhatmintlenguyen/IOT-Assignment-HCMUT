#pragma once

#include <Arduino.h>

enum class LockState : uint8_t {
    Locked,
    Unlocked,
};

struct VaultStatus {
    LockState lockState;
    bool breachActive;
    bool standbyActive;
    bool lockdownActive;
};

VaultStatus get_vault_status();
void set_lock_state(LockState state);
void request_unlock();
void trigger_approach_standby();
void extend_standby_if_active();
void vault_state_tick();
uint32_t get_remaining_unlock_time_sec();

// Breach management
void trigger_breach();
void acknowledge_breach();

// Lockdown management
void set_lockdown(bool active);
bool is_lockdown_active();

// Anti-bruteforce protection
void record_failed_attempt(const char* source);
void reset_failed_attempts();

// Returns true once when a sustained light increase is detected while locked.
bool observe_light_level(int lightAdc);
