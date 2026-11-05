#pragma once
#include <Preferences.h>
#include "walk_math.h"

Preferences walkPrefs;
int standAngles[SERVO_COUNT];
int jointDirection[SERVO_COUNT] = {}; // Set each sign from actual assembly.
bool standCaptured=false, walking=false, transitioning=false;
float fromAngles[SERVO_COUNT], toAngles[SERVO_COUNT];
uint32_t transitionStart=0, cycleStart=0, lastFrame=0;

void stopWalk() { walking=false; transitioning=false; }

bool walkReady() {
  if (!standCaptured) return false;
  for (uint8_t i=0; i<SERVO_COUNT; ++i)
    if (!servos[i].attached() || abs(jointDirection[i])!=1) return false;
  return true;
}

void loadWalkCalibration() {
  stopWalk(); standCaptured=false;
  if (walkPrefs.getUInt("version",0)!=1) { Serial.println("No saved walking calibration."); return; }
  if (walkPrefs.getBytes("stand",standAngles,sizeof standAngles)!=sizeof standAngles ||
      walkPrefs.getBytes("dirs",jointDirection,sizeof jointDirection)!=sizeof jointDirection) return;
  for (uint8_t i=0; i<SERVO_COUNT; ++i)
    if (standAngles[i]<0 || standAngles[i]>180 || abs(jointDirection[i])!=1) return;
  standCaptured=true;
  Serial.println("Walking calibration loaded; no movement commanded.");
}

bool calculateWalk(float phase, float *target) {
  float h0,k0;
  if (!legIK(0,65,h0,k0)) return false;
  for (uint8_t leg=0; leg<4; ++leg) {
    float x,z,h,k;
    footPath(phase,leg,x,z);
    if (!legIK(x,z,h,k)) return false;
    target[2*leg]=standAngles[2*leg]+jointDirection[2*leg]*(h-h0);
    target[2*leg+1]=standAngles[2*leg+1]+jointDirection[2*leg+1]*(k-k0);
  }
  for (uint8_t i=0; i<SERVO_COUNT; ++i)
    if (!isfinite(target[i]) || target[i]<0 || target[i]>180) return false;
  return true;
}

void beginTransition(const float *target) {
  for (uint8_t i=0; i<SERVO_COUNT; ++i) {
    fromAngles[i]=commandAngles[i]; toAngles[i]=target[i];
  }
  transitionStart=millis(); transitioning=true;
}

void updateWalk() {
  uint32_t now=millis();
  if (now-lastFrame<20 || (!walking && !transitioning)) return;
  lastFrame=now;
  float target[SERVO_COUNT];
  if (transitioning) {
    float t=fminf(1.f,(now-transitionStart)/1500.f), u=smoothStep(t);
    for (uint8_t i=0; i<SERVO_COUNT; ++i) target[i]=fromAngles[i]+u*(toAngles[i]-fromAngles[i]);
    if (t>=1.f) { transitioning=false; cycleStart=now; }
  } else if (!calculateWalk(((now-cycleStart)%4000)/4000.f,target)) {
    stopWalk(); Serial.println("Invalid gait target; stopped."); return;
  }
  for (uint8_t i=0; i<SERVO_COUNT; ++i) {
    commandAngles[i]=int(lroundf(target[i]));
    servos[i].write(commandAngles[i]);
  }
}

void walkHelp() {
  Serial.println("capture: record stand commands, foot x=0 z=65mm; dir ID +1/-1 for ALL 8 joints");
  Serial.println("save/load: calibration in flash, load never moves joints; ws: calibration status");
  Serial.println("stand: return to stand in 1.5s; f: forward crawl; stop: immediately hold last pose");
}

bool walkCommand(const String &cmd) {
  if (cmd=="stop") { stopWalk(); Serial.println("Stopped; holding last commanded pose."); return true; }
  if (cmd=="load") { loadWalkCalibration(); return true; }
  if (cmd=="ws") {
    Serial.printf("walking=%d standCaptured=%d ready=%d\n",walking,standCaptured,walkReady());
    for (uint8_t i=0; i<SERVO_COUNT; ++i)
      Serial.printf("%u stand=%d dir=%d\n",i+1,standAngles[i],jointDirection[i]);
    return true;
  }
  if (cmd=="capture") {
    if (walking || transitioning) { Serial.println("Stop and position legs first."); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) standAngles[i]=commandAngles[i];
    standCaptured=true; Serial.println("Standing commands captured, not measured."); return true;
  }
  if (cmd=="save") {
    if (!walkReady() || walking || transitioning) { Serial.println("Need stopped, captured stand and all 8 dir signs."); return true; }
    walkPrefs.putUInt("version",0);
    bool ok=walkPrefs.putBytes("stand",standAngles,sizeof standAngles)==sizeof standAngles;
    ok=(walkPrefs.putBytes("dirs",jointDirection,sizeof jointDirection)==sizeof jointDirection) && ok;
    if (ok) ok=walkPrefs.putUInt("version",1)==sizeof(uint32_t);
    Serial.println(ok ? "Walking calibration saved." : "ERROR saving."); return true;
  }
  long id,d; char extra;
  if (sscanf(cmd.c_str(),"dir %ld %ld %c",&id,&d,&extra)==2) {
    if (id<1 || id>SERVO_COUNT || (d!=1 && d!=-1)) Serial.println("Use dir ID 1 or dir ID -1.");
    else { stopWalk(); jointDirection[id-1]=d; Serial.printf("Direction %ld = %ld\n",id,d); }
    return true;
  }
  if (cmd=="stand") {
    if (!standCaptured) { Serial.println("Capture stand first."); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) if (!servos[i].attached()) return true;
    stopWalk(); float target[SERVO_COUNT];
    for (uint8_t i=0; i<SERVO_COUNT; ++i) target[i]=standAngles[i];
    beginTransition(target); return true;
  }
  if (cmd=="f") {
    if (walking) return true;
    if (!walkReady()) { Serial.println("Capture stand and set ALL 8 direction signs before f."); return true; }
    float target[SERVO_COUNT];
    for (int n=0; n<=1000; ++n) if (!calculateWalk(n/1000.f,target)) {
      Serial.println("Gait exceeds 0..180 or is unreachable; fix calibration."); return true;
    }
    stopWalk(); calculateWalk(0,target); beginTransition(target); walking=true;
    Serial.println("Forward crawl started; stop to hold."); return true;
  }
  return false;
}
