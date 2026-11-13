#pragma once
#include <Preferences.h>
#include "walk_math.h"

Preferences walkPrefs;
int standAngles[SERVO_COUNT];
int jointDirection[SERVO_COUNT] = {}; // Set each sign from actual assembly.
bool standCaptured=false, walking=false, transitioning=false;
float fromAngles[SERVO_COUNT], toAngles[SERVO_COUNT];
uint32_t transitionStart=0, phaseUpdatedAt=0, lastFrame=0;
constexpr uint32_t WALK_FRAME_MS=20;

float walkSpeed=1.f, walkPhase=0.f;
float walkDeadband=1.f; // Nominal command degrees. Adjust for the fitted servos.
LegTuning legTuning[4];
String commandMessage;
bool commandOK=true;
void reply(const String &message, bool ok=true) {
  commandMessage=message; commandOK=ok; Serial.println(message);
}

void stopWalk() { walking=false; transitioning=false; }

bool walkReady() {
  if (!standCaptured) return false;
  for (uint8_t i=0; i<SERVO_COUNT; ++i)
    if (!servos[i].attached() || abs(jointDirection[i])!=1) return false;
  return true;
}

struct CalibrationProfile {
  int angles[SERVO_COUNT];
  int dirs[SERVO_COUNT];
};

void loadWalkCalibration() {
  CalibrationProfile profile;
  if (walkPrefs.getBytes("profile-v2",&profile,sizeof profile)!=sizeof profile &&
      (walkPrefs.getUInt("version",0)!=1 ||
       walkPrefs.getBytes("stand",profile.angles,sizeof profile.angles)!=sizeof profile.angles ||
       walkPrefs.getBytes("dirs",profile.dirs,sizeof profile.dirs)!=sizeof profile.dirs)) {
    reply("No readable saved calibration; current calibration kept.",false); return;
  }
  for (unsigned i=0;i<SERVO_COUNT;++i) {
    if (profile.angles[i]<0 || profile.angles[i]>180 || (profile.dirs[i]!=1 && profile.dirs[i]!=-1)) {
      reply("Invalid saved calibration; current calibration kept.",false); return;
    }
  }
  for (unsigned i=0;i<SERVO_COUNT;++i) {
    standAngles[i]=profile.angles[i]; jointDirection[i]=profile.dirs[i];
  }
  standCaptured=true;
  reply("Calibration loaded into RAM.");
}

bool legTarget(unsigned leg, float x, float z, float *target) {
  float h,k,h0,k0;
  if (!legIK(x,z,h,k) || !legIK(0,CALIBRATION_HEIGHT_MM,h0,k0)) return false;
  const unsigned hip=2*leg, knee=hip+1;
  target[hip]=standAngles[hip]+jointDirection[hip]*(h-h0);
  target[knee]=standAngles[knee]+jointDirection[knee]*(k-k0);
  return target[hip]>=0 && target[hip]<=180 && target[knee]>=0 && target[knee]<=180;
}

bool calculateWalk(float phase, float *target, const LegTuning *settings) {
  for (uint8_t leg=0; leg<4; ++leg) {
    float x,z;
    footPath(phase,leg,x,z,settings[leg]);
    if (!legTarget(leg,x,z,target)) return false;
  }
  return true;
}

// Validate geometry without calibration; also validate servo commands when ready.
bool validateGait(const LegTuning *settings) {
  for (unsigned leg=0;leg<4;++leg) if (!validLegTuning(settings[leg])) return false;
  const bool calibrated=walkReady();
  float target[SERVO_COUNT];
  for (int n=0;n<=1000;++n) {
    float phase=n/1000.f;
    if (calibrated) {
      if (!calculateWalk(phase,target,settings)) return false;
      continue;
    }
    for (unsigned leg=0;leg<4;++leg) {
      float x,z,h,k; footPath(phase,leg,x,z,settings[leg]);
      if (!legIK(x,z,h,k)) return false;
    }
  }
  return true;
}
bool loadGaitSettings() {
  Preferences prefs;
  if (!prefs.begin("quad-gait",true)) return false;
  LegTuning candidate[4];
  const bool ok=prefs.getBytes("legs-v2",candidate,sizeof candidate)==sizeof candidate ||
    (prefs.getUInt("version",0)==1 && prefs.getBytes("legs",candidate,sizeof candidate)==sizeof candidate);
  prefs.end();
  if (!ok || !validateGait(candidate)) return false;
  for (unsigned i=0;i<4;++i) legTuning[i]=candidate[i];
  return true;
}

void advancePhaseTo(uint32_t now) {
  if (walking && !transitioning) {
    const uint32_t elapsed=now-phaseUpdatedAt;
    // After a delayed loop, resume nearby instead of jumping ahead in the gait.
    const uint32_t maxStep=2*WALK_FRAME_MS;
    walkPhase=advanceWalkPhase(walkPhase,elapsed>maxStep ? maxStep : elapsed,walkSpeed);
  }
  phaseUpdatedAt=now;
}

void beginTransition(const float *target) {
  for (uint8_t i=0; i<SERVO_COUNT; ++i) {
    fromAngles[i]=(commandPulses[i]-SERVO_MIN_US)*180.f/(SERVO_MAX_US-SERVO_MIN_US);
    toAngles[i]=target[i];
  }
  transitionStart=millis(); transitioning=true;
}

void updateWalk() {
  uint32_t now=millis();
  if (now-lastFrame<WALK_FRAME_MS || (!walking && !transitioning)) return;
  lastFrame=now;
  const bool finalTransitionFrame=transitioning && now-transitionStart>=1500;
  float target[SERVO_COUNT];
  if (transitioning) {
    float t=fminf(1.f,(now-transitionStart)/1500.f), u=smoothStep(t);
    for (uint8_t i=0; i<SERVO_COUNT; ++i) target[i]=fromAngles[i]+u*(toAngles[i]-fromAngles[i]);
    if (t>=1.f) { transitioning=false; walkPhase=0; phaseUpdatedAt=now; }
  } else {
    advancePhaseTo(now);
    if (!calculateWalk(walkPhase,target,legTuning)) {
      stopWalk(); reply("Invalid gait target; stopped.",false); return;
    }
  }
  const int minChangeUs=walking && !finalTransitionFrame && walkDeadband>0.f
    ? int(ceilf(walkDeadband*(SERVO_MAX_US-SERVO_MIN_US)/180.f))
    : 1;
  for (uint8_t i=0; i<SERVO_COUNT; ++i) writeServoAngle(i,target[i],minChangeUs);
}

void walkHelp() {
  Serial.println("walk set LEG LIFT DEPTH STRIDE LIFT_PERCENT LOWER_PERCENT: LEG 1=FL 2=FR 3=RL 4=RR; stopped only");
  Serial.println("walk save / walk load / walk reset: save, load or reset RAM defaults");
  reply("walk speed 0.05..4: any decimal gait multiplier, default 1; RAM only");
  reply("walk deadband 0..5: minimum gait change in command degrees, default 1; RAM only");
  reply("stand record: record stand commands, foot x=0 z=65mm; stand direction ID +1/-1 for ALL 8 joints");
  reply("stand save / stand load: save or load stand and directions; ws: working settings");
  reply("stand: return to stand in 1.5s; walk: forward; stop: hold last pose");
}

bool calibrationCommand(const String &cmd) {
  if (cmd=="stand load") {
    if (walking || transitioning) reply("Stop before loading calibration.",false);
    else loadWalkCalibration();
    return true;
  }
  if (cmd=="stand record") {
    if (walking || transitioning) { reply("Stop and position legs first.",false); return true; }
    for (uint8_t i=0;i<SERVO_COUNT;++i) if (!servos[i].attached()) { reply("A servo is not attached.",false); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) standAngles[i]=commandAngles[i];
    standCaptured=true; reply("Standing commands captured, not measured."); return true;
  }
  if (cmd=="stand save") {
    if (!walkReady() || walking || transitioning) { reply("Need stopped, captured stand and all 8 dir signs.",false); return true; }
    CalibrationProfile profile;
    for (unsigned i=0;i<SERVO_COUNT;++i) {
      profile.angles[i]=standAngles[i]; profile.dirs[i]=jointDirection[i];
    }
    const bool ok=walkPrefs.putBytes("profile-v2",&profile,sizeof profile)==sizeof profile;
    reply(ok ? "Walking calibration saved." : "ERROR saving.",ok); return true;
  }
  long id,d; char extra;
  if (sscanf(cmd.c_str(),"stand direction %ld %ld %c",&id,&d,&extra)==2) {
    if (id<1 || id>SERVO_COUNT || (d!=1 && d!=-1)) reply("Use stand direction ID +1 or -1.",false);
    else if (walking || transitioning) reply("Stop before changing calibration.",false);
    else { jointDirection[id-1]=d; reply("Direction updated in RAM."); }
    return true;
  }
  return false;
}

bool gaitSettingsCommand(const String &cmd) {
  if (cmd=="walk save" || cmd=="walk load" || cmd=="walk reset") {
    if (walking || transitioning) { reply("Stop before changing/saving gait settings.",false); return true; }
    if (cmd=="walk load") { bool ok=loadGaitSettings(); reply(ok ? "Gait loaded." : "No valid saved gait; unchanged.",ok); return true; }
    if (cmd=="walk reset") { for (auto &v:legTuning) v=LegTuning(); reply("Default gait in RAM; calibration unchanged."); return true; }
    if (!validateGait(legTuning)) { reply("Invalid gait settings.",false); return true; }
    Preferences prefs; bool ok=prefs.begin("quad-gait",false);
    if (ok) {
      ok=prefs.putBytes("legs-v2",legTuning,sizeof legTuning)==sizeof legTuning;
      prefs.end();
    }
    reply(ok ? "Gait saved; calibration unchanged." : "Error saving gait.",ok); return true;
  }
  if (cmd=="walk set" || cmd.startsWith("walk set ")) {
    long leg; float lift,depth,stride,lp,rp; char tail;
    if (sscanf(cmd.c_str(),"walk set %ld %f %f %f %f %f %c",&leg,&lift,&depth,&stride,&lp,&rp,&tail)!=6 || leg<1 || leg>4) {
      reply("Use walk set LEG LIFT DEPTH STRIDE LIFT_PERCENT LOWER_PERCENT.",false); return true;
    }
    if (walking || transitioning) { reply("Stop before applying tuning.",false); return true; }
    LegTuning candidate[4]; for (unsigned i=0;i<4;++i) candidate[i]=legTuning[i];
    auto &v=candidate[leg-1]; v.lift=lift; v.depth=depth; v.stride=stride; v.liftPart=lp/100; v.lowerPart=rp/100;
    if (!validateGait(candidate)) { reply("Rejected: bounds, unreachable geometry or command limits.",false); return true; }
    legTuning[leg-1]=v; reply("Leg tuning applied in RAM; no movement. Use walk save to persist."); return true;
  }
  return false;
}

bool walkCommand(const String &cmd) {
  if (cmd=="stop") { stopWalk(); reply("Stopped; holding last commanded pose."); return true; }
  if (calibrationCommand(cmd) || gaitSettingsCommand(cmd)) return true;
  if (cmd=="ws") {
    Serial.printf("walking=%d standCaptured=%d ready=%d speed=%.2f deadband=%.2f deg nominal support=65mm\n",
                  walking,standCaptured,walkReady(),walkSpeed,walkDeadband);
    for (uint8_t i=0; i<SERVO_COUNT; ++i)
      Serial.printf("%u stand=%d dir=%d\n",i+1,standAngles[i],jointDirection[i]);
    for (uint8_t i=0;i<4;++i) Serial.printf("leg %u lift=%.3f depth=%.3f stride=%.3f lift%%=%.2f lower%%=%.2f\n",
      i+1,legTuning[i].lift,legTuning[i].depth,legTuning[i].stride,100*legTuning[i].liftPart,100*legTuning[i].lowerPart);
    reply("Status updated."); return true;
  }
  float speed; char trailing;
  if (cmd=="walk speed" || cmd.startsWith("walk speed ")) {
    if (sscanf(cmd.c_str(),"walk speed %f %c",&speed,&trailing)!=1 || !isfinite(speed) || speed<.05f || speed>4.f)
      reply("Use walk speed MULTIPLIER (0.05..4).",false);
    else { advancePhaseTo(millis()); walkSpeed=speed; reply("Speed applied; cycle "+String(4.f/walkSpeed,3)+" seconds."); }
    return true;
  }
  if (cmd=="walk deadband" || cmd.startsWith("walk deadband ")) {
    float degrees;
    if (sscanf(cmd.c_str(),"walk deadband %f %c",&degrees,&trailing)!=1 ||
        !isfinite(degrees) || degrees<0.f || degrees>5.f)
      reply("Use walk deadband DEGREES (0..5).",false);
    else { walkDeadband=degrees; reply("Walk deadband applied: "+String(degrees,2)+" deg."); }
    return true;
  }
  if (cmd=="stand") {
    if (!standCaptured) { reply("Capture stand first.",false); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) if (!servos[i].attached()) { reply("Servo not attached.",false); return true; }
    stopWalk(); float target[SERVO_COUNT];
    for (uint8_t i=0; i<SERVO_COUNT; ++i) target[i]=standAngles[i];
    beginTransition(target); reply("Returning to current calibrated stand."); return true;
  }
  if (cmd=="walk") {
    if (walking) { reply("Already walking."); return true; }
    if (!walkReady()) { reply("Capture stand and set ALL 8 direction signs before walking.",false); return true; }
    float target[SERVO_COUNT];
    if (!validateGait(legTuning) || !calculateWalk(0,target,legTuning)) {
      reply("Gait unreachable or outside command limits.",false); return true;
    }
    beginTransition(target); walking=true;
    reply("Forward started; stop to hold.");
    return true;
  }
  return false;
}
