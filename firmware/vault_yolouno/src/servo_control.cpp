#include "servo_control.h"
#include <ESP32Servo.h>

namespace {
// YoloUNO GVS header D11 maps to GPIO 38
constexpr int SERVO_PIN = 38;

// Calibrated 180-degree sweep for full mechanical travel
constexpr int ANGLE_LOCKED = 180;
constexpr int ANGLE_UNLOCKED = 0;

Servo deadbolt;
}

void servo_control_init() {
    deadbolt.setPeriodHertz(50); // 50 Hz standard servo PWM
    deadbolt.attach(SERVO_PIN, 500, 2500);
    deadbolt.write(ANGLE_LOCKED);
}

void servo_set_locked() {
    deadbolt.write(ANGLE_LOCKED);
}

void servo_set_unlocked() {
    deadbolt.write(ANGLE_UNLOCKED);
}
