#include <ESP32Servo.h>
#include "servo_pins.h"

Servo servos[SERVO_COUNT];
int commandAngles[SERVO_COUNT];
int commandPulses[SERVO_COUNT];

void writeServoAngle(unsigned joint, float angle, int minChangeUs) {
  const int pulse=SERVO_MIN_US+int(lroundf(angle*(SERVO_MAX_US-SERVO_MIN_US)/180.f));
  if (abs(pulse-commandPulses[joint])<minChangeUs) return;
  servos[joint].writeMicroseconds(pulse);
  commandPulses[joint]=pulse;
  commandAngles[joint]=int(lroundf(angle));
}

#include "walk_control.h"
#include "ultrasonic.h"
#include "avoid.h"

bool setServo(long id, long angle) {
  // API angle-domain validation only; no extra joint working limits.
  // Reject >=500 so ESP32Servo cannot interpret an angle as microseconds.
  if (id < 1 || id > SERVO_COUNT || angle < 0 || angle > 180) {
    reply("Use servo ID 1..8 and angle 0..180.",false);
    return false;
  }
  const uint8_t i = uint8_t(id - 1);
  if (!servos[i].attached()) {
    reply("Servo is not attached.",false);
    return false;
  }
  writeServoAngle(i,angle,1);
  reply("Servo "+String(id)+" commanded to "+String(angle)+" degrees (not measured).");
  Serial.printf("%ld %s GPIO%u -> %ld deg (command, not measured)\n",
                id, SERVO_NAMES[i], SERVO_PINS[i], angle);
  return true;
}

void setAll(long angle) {
  if (angle < 0 || angle > 180) {
    reply("Use angle 0..180.",false);
    return;
  }
  for (uint8_t i=0;i<SERVO_COUNT;++i) if (!servos[i].attached()) {
    reply("A servo is not attached; all-angle command rejected.",false); return;
  }
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) setServo(i + 1, angle);
}

void printStatus() {
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
    Serial.printf("%u %s GPIO%u: %s, last command %d deg / %d us\n", i + 1,
                  SERVO_NAMES[i], SERVO_PINS[i],
                  servos[i].attached() ? "attached" : "NOT ATTACHED",
                  commandAngles[i],commandPulses[i]);
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

// Shared executor: HTTP and Serial have identical validation and effects.
bool executeCommand(String text) {
  text.trim(); commandMessage=""; commandOK=true;
  if (!text.length() || text.length()>95) { reply("Empty or oversized command.",false); return false; }
  if (text=="s" || text=="list") { printStatus(); reply("Status updated."); return true; }
  if (text=="h" || text=="help") { printHelp(); reply("Help printed; all controls are also on the phone page."); return true; }
  if (usCommand(text)) return commandOK;
  if (avoidCommand(text)) return commandOK;
  // Any manual motion/stop command cancels the current avoid phase (the
  // avoid on/off switch itself stays as set; use `avoid off` to disable).
  if (text=="stop" || text=="stand" || text=="walk" || text=="walk back" ||
      text.startsWith("walk left") || text.startsWith("walk right") ||
      text.startsWith("walk straight") || text=="init" ||
      text.startsWith("all ") || text.startsWith("set ")) avoidReset();
  if (walkCommand(text)) return commandOK;
  if (text=="init") { stopWalk(); setAll(INIT_ANGLE); return commandOK; }
  long id,angle; char extra;
  if (sscanf(text.c_str(),"all %ld %c",&angle,&extra)==1) {
    if (angle<0 || angle>180) { reply("Use angle 0..180.",false); return false; }
    stopWalk(); setAll(angle); return commandOK;
  }
  if (sscanf(text.c_str(),"set %ld %ld %c",&id,&angle,&extra)==2 ||
      sscanf(text.c_str(),"%ld %ld %c",&id,&angle,&extra)==2) {
    if (id<1 || id>SERVO_COUNT || angle<0 || angle>180) { reply("Use ID 1..8, angle 0..180.",false); return false; }
    stopWalk(); return setServo(id,angle);
  }
  reply("Invalid command.",false); return false;
}

#include "wifi_control.h"

void setup() {
  Serial.begin(115200);
  usBegin();
  walkPrefs.begin("quad-walk", false);
  loadWalkCalibration();
  Serial.setTimeout(100);
  for (uint8_t t = 0; t < 4; ++t) ESP32PWM::allocateTimer(t);
  for (uint8_t i = 0; i < SERVO_COUNT; ++i) {
    commandAngles[i] = standCaptured ? standAngles[i] : INIT_ANGLE;
    commandPulses[i] = 0;
    servos[i].setPeriodHertz(50);
    servos[i].attach(SERVO_PINS[i], SERVO_MIN_US, SERVO_MAX_US);
    if (servos[i].attached()) writeServoAngle(i,commandAngles[i],1);
    else Serial.printf("ERROR attaching port %u / GPIO%u\n", i + 1, SERVO_PINS[i]);
    delay(150);  // Stagger initial commands; this is not feedback or a power guarantee.
  }
  Serial.println(standCaptured ? "Ready. Startup pose: saved stand." :
                                "Ready. No saved stand; startup uses 90 deg midpoint.");
  loadGaitSettings();
  printStatus();
  printHelp();
  setupPhoneControl();
}

void loop() {
  updatePhoneControl();
  updateWalk();
  avoidTick();
  usStreamTick();
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
  if (!text.length()) return;
  if (executeCommand(text) && text!="s" && text!="list" && text!="ws" && text!="h" && text!="help")
    releasePhoneControl(); // Explicit successful serial command takes control.
}
