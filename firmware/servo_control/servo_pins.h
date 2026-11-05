#pragma once
#include <Arduino.h>

// Canonical wiring: hardware/引脚分配.md. Left/right are the robot's own sides.
// Front is the ultrasonic-bracket end (+X in the CAD assembly).
constexpr uint8_t SERVO_COUNT = 8;
constexpr uint8_t SERVO_PINS[SERVO_COUNT] = {4, 5, 13, 14, 16, 17, 18, 19};
const char *const SERVO_NAMES[SERVO_COUNT] = {
  "front_left_hip", "front_left_knee",
  "front_right_hip", "front_right_knee",
  "rear_left_hip", "rear_left_knee",
  "rear_right_hip", "rear_right_knee"
};
constexpr int SERVO_MIN_US = 500;
constexpr int SERVO_MAX_US = 2500;
constexpr int INIT_ANGLE = 90;  // Electrical midpoint, not a standing pose.
