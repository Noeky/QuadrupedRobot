#include <ESP32Servo.h>
#include "servo_pins.h"

Servo servos[SERVO_COUNT];
int commandAngles[SERVO_COUNT];
#include "walk_control.h"

bool setServo(long id, long angle) {
  // API angle-domain validation only; no extra joint working limits.
  // Reject >=500 so ESP32Servo cannot interpret an angle as microseconds.
  if (id < 1 || id > SERVO_COUNT || angle < 0 || angle > 180) {
    Serial.println("Use servo ID 1..8 and angle 0..180.");
    return false;
  }
  const uint8_t i = uint8_t(id - 1);
  if (!servos[i].attached()) {
    Serial.printf("ERROR: servo %ld is not attached.\n", id);
    return false;
  }
  servos[i].write(int(angle));
  commandAngles[i] = int(angle);
  Serial.printf("%ld %s GPIO%u -> %ld deg (command, not measured)\n",
                id, SERVO_NAMES[i], SERVO_PINS[i], angle);
  return true;
}

void setAll(long angle) {
  if (angle < 0 || angle > 180) {
    Serial.println("Use angle 0..180.");
    return;
  }
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) setServo(i + 1, angle);
}

void printStatus() {
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
    Serial.printf("%u %s GPIO%u: %s, last command %d deg\n", i + 1,
                  SERVO_NAMES[i], SERVO_PINS[i],
                  servos[i].attached() ? "attached" : "NOT ATTACHED",
                  commandAngles[i]);
  }
}

void printHelp() {
  Serial.println("1 90       -> port 1 / front-left hip to 90 deg");
  Serial.println("set 2 100  -> port 2 / front-left knee to 100 deg");
  Serial.println("all 90     -> all 8 servos to 90 deg");
  Serial.println("init       -> all 8 servos back to 90 deg");
  Serial.println("s or list  -> wiring and last commanded angles");
  Serial.println("h or help  -> commands");
  walkHelp();
}

void setup() {
  Serial.begin(115200);
  walkPrefs.begin("quad-walk", false);
  Serial.setTimeout(100);
  for (uint8_t t = 0; t < 4; ++t) ESP32PWM::allocateTimer(t);
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
    commandAngles[i] = INIT_ANGLE;
    servos[i].setPeriodHertz(50);
    servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    if (servos[i].attached()) servos[i].write(INIT_ANGLE);
    else Serial.printf("ERROR attaching port %u / GPIO%u\n", i + 1, SERVO_PINS[i]);
    delay(150);  // Stagger initial commands; this is not feedback or a power guarantee.
  }
  Serial.println("Ready. All attached servos commanded to 90 deg; NOT a standing pose.");
  loadWalkCalibration();
  printStatus();
  printHelp();
}

void loop() {
  updateWalk();
  // Bounded nonblocking line input keeps stop responsive during the gait.
  static char buffer[96];
  static uint8_t length = 0;
  static bool overflow = false;
  if (!Serial.available()) return;
  char c = Serial.read();
  if (c != '\n' && c != '\r') {
    if (!overflow && length < sizeof(buffer)-1) buffer[length++] = c;
    else overflow = true;
    return;
  }
  if (overflow) { length=0; overflow=false; Serial.println("Line too long; ignored."); return; }
  buffer[length]=0;
  String text(buffer);
  length=0;
  text.trim();
  if (text.length() == 0) return;
  if (text == "s" || text == "list") { printStatus(); return; }
  if (text == "h" || text == "help") { printHelp(); return; }
  if (walkCommand(text)) return;
  if (text == "init") { stopWalk(); setAll(INIT_ANGLE); return; }

  long id, angle;
  char extra;
  const char *line = text.c_str();
  if (sscanf(line, "all %ld %c", &angle, &extra) == 1) {
    stopWalk();
    setAll(angle);
  } else if (sscanf(line, "set %ld %ld %c", &id, &angle, &extra) == 2 ||
             sscanf(line, "%ld %ld %c", &id, &angle, &extra) == 2) {
    stopWalk();
    setServo(id, angle);
  } else {
    Serial.println("Invalid command. Example: 1 90, all 90, init, s.");
  }
}
