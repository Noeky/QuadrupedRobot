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
// Motion state: direction +1 forward / -1 backward, turn +1 left / -1 right.
// These are RAM-only; the saved stand, directions and LegTuning are unchanged.
float walkDirection=1.f, walkTurn=0.f, walkTurnGain=.5f;
float walkDirectionTarget=1.f, walkTurnTarget=0.f;
// Common fore/aft trim for stand and gait, in mm. Negative = feet backward.
// RAM-only; it does not change the saved stand or LegTuning.
float walkFootOffsetX=0.f;
// Gait-only fore/aft center, in mm. Negative = gait feet backward. This does
// NOT move the stand; use it to center the walking support without tilting the
// calibrated standing body.
float walkCenterX=0.f;
// Small heading trim applied only to the straight gait (turn target 0).
// Positive = left bias. It is an effective turn, so the same 0.09 value found
// with `walk turn 0.09` + `walk left` can be used directly. RAM until saved.
float walkBias=0.f;
constexpr float WALK_MOTION_RATE=2.f; // direction/turn units per second
constexpr float FOOT_OFFSET_MAX=20.f;
constexpr float WALK_CENTER_MAX=25.f;
constexpr float WALK_BIAS_MAX=.4f;
// Greeting wave: lift one rear leg while the three support feet hold the stand.
// Default leg index 0 = leg 1 (front left). Front waves use a 20 mm lift and
// a support pose that shifts the body rear/right; rear waves are more stable.
bool waving=false;
uint32_t waveStart=0;
float waveFrom[SERVO_COUNT], waveSupport[SERVO_COUNT], waveStand[SERVO_COUNT];
uint8_t waveLeg=0; // 0-based; default 0=FL (leg 1). Front 0/1 use a small lift.
constexpr uint32_t WAVE_PREPARE_MS=1200;
constexpr uint32_t WAVE_MOTION_MS=3000;
constexpr uint32_t WAVE_RETURN_MS=1200;
constexpr float WAVE_FREQ_HZ=1.f;
constexpr float WAVE_LIFT_MM=25.f;       // rear-leg lift
constexpr float WAVE_FRONT_LIFT_MM=25.f; // front-leg lift; approx 30 deg hip at x=10mm
constexpr float WAVE_X_CENTER_MM=10.f;
constexpr float WAVE_X_AMPLITUDE_MM=8.f;
// Front-wave balance pose: support feet forward (body moves rear) and support
// leg heights biased to roll the body right / pitch it up. FL is the default
// waving leg; indices are FL,FR,RL,RR. The FL entry is unused when FL waves.
constexpr float WAVE_FRONT_SUPPORT_X_MM=8.f;
constexpr float WAVE_FRONT_SUPPORT_DEPTH[4]={0.f, 6.f, 6.f, -4.f};
float waveLiftMm=WAVE_FRONT_LIFT_MM;
LegTuning legTuning[4];
String commandMessage;
bool commandOK=true;
void reply(const String &message, bool ok=true) {
  commandMessage=message; commandOK=ok; Serial.println(message);
}

void stopWalk() {
  walking=false;
  transitioning=false;
  waving=false;
  // Direction is a runtime mode; reset it so a later stop/start always begins
  // from a known forward/straight request. The last commanded pose is held.
  walkDirection=1.f;
  walkTurn=0.f;
  walkDirectionTarget=1.f;
  walkTurnTarget=0.f;
}

bool walkReady() {
  if (!standCaptured) return false;
  for (uint8_t i=0; i<SERVO_COUNT; ++i)
    if (!servos[i].attached() || abs(jointDirection[i])!=1) return false;
  return true;
}

const char *motionName() {
  if (waving) return "wave";
  if (!walking) return "stopped";
  if (walkTurnTarget>.05f) return "left";
  if (walkTurnTarget<-.05f) return "right";
  if (walkDirectionTarget<0.f) return "back";
  return "forward";
}
const char *motionLabel(float direction, float turn) {
  if (turn>.05f) return direction<0.f ? "Back-left turn" : "Left turn";
  if (turn<-.05f) return direction<0.f ? "Back-right turn" : "Right turn";
  if (direction<0.f) return "Backward";
  return "Forward";
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
  walkFootOffsetX=0.f;
  reply("Calibration loaded into RAM; foot offset reset to 0.");
}

bool legTarget(unsigned leg, float x, float z, float *target) {
  float h,k,h0,k0;
  if (!legIK(x,z,h,k) || !legIK(0,CALIBRATION_HEIGHT_MM,h0,k0)) return false;
  const unsigned hip=2*leg, knee=hip+1;
  target[hip]=standAngles[hip]+jointDirection[hip]*(h-h0);
  target[knee]=standAngles[knee]+jointDirection[knee]*(k-k0);
  return target[hip]>=0 && target[hip]<=180 && target[knee]>=0 && target[knee]<=180;
}

bool standOffsetValid() {
  if (!standCaptured) return true;
  float target[SERVO_COUNT];
  for (uint8_t leg=0; leg<4; ++leg)
    if (!legTarget(leg,walkFootOffsetX,CALIBRATION_HEIGHT_MM,target)) return false;
  return true;
}

float straightTurn(float turn, float turnGain) {
  if (fabsf(turn)<.05f && turnGain>.01f) return turn+walkBias/turnGain;
  return turn;
}

bool calculateWalk(float phase, float *target, const LegTuning *settings,
                   float direction=1.f, float turn=0.f, float turnGain=.5f) {
  turn=straightTurn(turn,turnGain);
  for (uint8_t leg=0; leg<4; ++leg) {
    float x,z;
    footPath(phase,leg,x,z,settings[leg],direction,turn,turnGain);
    x += walkFootOffsetX + walkCenterX;
    if (!legTarget(leg,x,z,target)) return false;
  }
  return true;
}

// Validate geometry without calibration; also validate servo commands when ready.
bool validateGait(const LegTuning *settings, float direction=1.f, float turn=0.f,
                  float turnGain=.5f) {
  const float effectiveTurn=straightTurn(turn,turnGain);
  for (unsigned leg=0;leg<4;++leg)
    if (!validLegTuning(settings[leg]) || !validTurn(settings[leg],effectiveTurn,turnGain)) return false;
  const bool calibrated=walkReady();
  float target[SERVO_COUNT];
  for (int n=0;n<=1000;++n) {
    float phase=n/1000.f;
    if (calibrated) {
      if (!calculateWalk(phase,target,settings,direction,turn,turnGain)) return false;
      continue;
    }
    for (unsigned leg=0;leg<4;++leg) {
      float x,z,h,k; footPath(phase,leg,x,z,settings[leg],direction,effectiveTurn,turnGain);
      x += walkFootOffsetX + walkCenterX;
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
  const float savedCenter=prefs.getFloat("center",0.f);
  const float savedBias=prefs.getFloat("bias",0.f);
  prefs.end();
  if (!ok || !isfinite(savedCenter) || fabsf(savedCenter)>WALK_CENTER_MAX ||
      !isfinite(savedBias) || fabsf(savedBias)>WALK_BIAS_MAX) return false;
  const float previousCenter=walkCenterX, previousBias=walkBias;
  walkCenterX=savedCenter;
  walkBias=savedBias;
  if (!validateGait(candidate)) {
    walkCenterX=previousCenter; walkBias=previousBias; return false;
  }
  for (unsigned i=0;i<4;++i) legTuning[i]=candidate[i];
  return true;
}

void advanceMotion(uint32_t elapsedMs) {
  const float dt=elapsedMs/1000.f;
  walkDirection=moveToward(walkDirection,walkDirectionTarget,WALK_MOTION_RATE*dt);
  walkTurn=moveToward(walkTurn,walkTurnTarget,WALK_MOTION_RATE*dt);
}

void advancePhaseTo(uint32_t now) {
  if (walking && !transitioning) {
    const uint32_t elapsed=now-phaseUpdatedAt;
    // After a delayed loop, resume nearby instead of jumping ahead in the gait.
    const uint32_t maxStep=2*WALK_FRAME_MS;
    const uint32_t dt=elapsed>maxStep ? maxStep : elapsed;
    walkPhase=advanceWalkPhase(walkPhase,dt,walkSpeed);
    advanceMotion(dt);
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

void updateWave(uint32_t now) {
  const uint32_t elapsed=now-waveStart;
  float target[SERVO_COUNT];
  if (elapsed<WAVE_PREPARE_MS) {
    const float u=smoothStep(elapsed/(float)WAVE_PREPARE_MS);
    for (uint8_t i=0;i<SERVO_COUNT;++i) target[i]=waveFrom[i]+u*(waveSupport[i]-waveFrom[i]);
  } else if (elapsed<WAVE_PREPARE_MS+WAVE_MOTION_MS) {
    for (uint8_t i=0;i<SERVO_COUNT;++i) target[i]=waveSupport[i];
    const float t=(elapsed-WAVE_PREPARE_MS)/1000.f;
    const float x=walkFootOffsetX+WAVE_X_CENTER_MM+
      WAVE_X_AMPLITUDE_MM*sinf(2.f*3.14159265f*WAVE_FREQ_HZ*t);
    if (!legTarget(waveLeg,x,
                   CALIBRATION_HEIGHT_MM+legTuning[waveLeg].depth-waveLiftMm,target)) {
      waving=false; reply("Wave target unreachable; stopped.",false); return;
    }
  } else if (elapsed<WAVE_PREPARE_MS+WAVE_MOTION_MS+WAVE_RETURN_MS) {
    const float u=smoothStep(
      (elapsed-WAVE_PREPARE_MS-WAVE_MOTION_MS)/(float)WAVE_RETURN_MS);
    for (uint8_t i=0;i<SERVO_COUNT;++i) target[i]=waveSupport[i]+u*(waveStand[i]-waveSupport[i]);
  } else {
    for (uint8_t i=0;i<SERVO_COUNT;++i) target[i]=waveStand[i];
    waving=false;
  }
  for (uint8_t i=0;i<SERVO_COUNT;++i) writeServoAngle(i,target[i],1);
}

void updateWalk() {
  uint32_t now=millis();
  if (now-lastFrame<WALK_FRAME_MS || (!walking && !transitioning && !waving)) return;
  lastFrame=now;
  if (waving) { updateWave(now); return; }
  const bool finalTransitionFrame=transitioning && now-transitionStart>=1500;
  float target[SERVO_COUNT];
  if (transitioning) {
    float t=fminf(1.f,(now-transitionStart)/1500.f), u=smoothStep(t);
    for (uint8_t i=0; i<SERVO_COUNT; ++i) target[i]=fromAngles[i]+u*(toAngles[i]-fromAngles[i]);
    if (t>=1.f) { transitioning=false; walkPhase=0; phaseUpdatedAt=now; }
  } else {
    advancePhaseTo(now);
    if (!calculateWalk(walkPhase,target,legTuning,walkDirection,walkTurn,walkTurnGain)) {
      stopWalk(); reply("Invalid gait target; stopped.",false); return;
    }
  }
  const int minChangeUs=walking && !finalTransitionFrame && walkDeadband>0.f
    ? int(ceilf(walkDeadband*(SERVO_MAX_US-SERVO_MIN_US)/180.f))
    : 1;
  for (uint8_t i=0; i<SERVO_COUNT; ++i) writeServoAngle(i,target[i],minChangeUs);
}

bool startWalk(float direction, float turn) {
  if (!walkReady()) {
    reply("Capture stand and set ALL 8 direction signs before walking.",false);
    return true;
  }
  if (waving) {
    reply("Stop the wave first.",false);
    return true;
  }
  if (transitioning) {
    reply("Wait for the stand transition to finish.",false);
    return true;
  }
  if (!validateGait(legTuning,direction,turn,walkTurnGain)) {
    reply("Gait unreachable for this direction/turn; lower walk turn.",false);
    return true;
  }
  if (walking) {
    walkDirectionTarget=direction;
    walkTurnTarget=turn;
    reply(String(motionLabel(direction,turn))+" requested; direction will ramp.");
    return true;
  }
  float target[SERVO_COUNT];
  if (!calculateWalk(0,target,legTuning,direction,turn,walkTurnGain)) {
    reply("Gait unreachable for this direction/turn; lower walk turn.",false);
    return true;
  }
  walkDirection=direction;
  walkTurn=turn;
  walkDirectionTarget=direction;
  walkTurnTarget=turn;
  beginTransition(target);
  walking=true;
  reply(String(motionLabel(direction,turn))+" started.");
  return true;
}

bool startWave() {
  if (!walkReady()) {
    reply("Capture stand and set ALL 8 direction signs before waving.",false);
    return true;
  }
  if (walking || transitioning) {
    reply("Stop before waving.",false);
    return true;
  }
  if (waving) {
    reply("Already waving.",false);
    return true;
  }
  waveLiftMm=(waveLeg<2) ? WAVE_FRONT_LIFT_MM : WAVE_LIFT_MM;
  for (uint8_t leg=0; leg<4; ++leg)
    if (!legTarget(leg,walkFootOffsetX,CALIBRATION_HEIGHT_MM,waveStand)) {
      reply("Stand target unreachable; lower foot offset.",false); return true;
    }
  // The support legs use the current walking support plane (65 + per-leg depth),
  // so the wave starts from the same height the gait uses. For a front wave,
  // also move the support feet forward (body rear) and bias their heights to
  // shift the body right/up. The wave leg is raised from its own support plane.
  const bool frontWave=waveLeg<2;
  for (uint8_t leg=0; leg<4; ++leg) {
    float x=walkFootOffsetX;
    float z=CALIBRATION_HEIGHT_MM+legTuning[leg].depth;
    if (frontWave) {
      x+=WAVE_FRONT_SUPPORT_X_MM;
      z+=WAVE_FRONT_SUPPORT_DEPTH[leg];
    }
    if (!legTarget(leg,x,z,waveSupport)) {
      reply("Wave support unreachable; lower depth/foot offset.",false); return true;
    }
  }
  if (!legTarget(waveLeg,walkFootOffsetX+WAVE_X_CENTER_MM,
                 CALIBRATION_HEIGHT_MM+legTuning[waveLeg].depth-waveLiftMm,
                 waveSupport)) {
    reply("Wave target unreachable; lower wave lift.",false); return true;
  }
  for (uint8_t i=0;i<SERVO_COUNT;++i)
    waveFrom[i]=(commandPulses[i]-SERVO_MIN_US)*180.f/(SERVO_MAX_US-SERVO_MIN_US);
  waveStart=millis();
  waving=true;
  reply("Greeting with "+(waveLeg<2 ? String("front") : String("rear"))+
        " leg "+String(waveLeg+1)+".");
  return true;
}

void walkHelp() {
  Serial.println("walk / walk back / walk left / walk right / walk straight: forward, reverse, curve, cancel turn; aliases back/left/right/straight");
  Serial.println("walk set LEG LIFT DEPTH STRIDE LIFT_PERCENT LOWER_PERCENT: LEG 1=FL 2=FR 3=RL 4=RR; stopped only");
  Serial.println("walk save / walk load / walk reset: save, load or reset RAM defaults");
  reply("walk speed 0.05..4: any decimal gait multiplier, default 1; RAM only");
  reply("walk deadband 0..5: minimum gait change in command degrees, default 1; RAM only");
  reply("walk turn 0..0.8: left/right stride difference gain, default 0.5; stopped only; RAM only");
  reply("walk center -10: gait-only fore/aft center in mm, -25..25; negative=feet back; stand unchanged; walk save persists");
  reply("walk bias 0.09: straight-line heading trim, -0.4..0.4, positive=left; only when turn target is 0; walk save persists");
  reply("foot offset -5: shift all foot targets in mm, -20..20; negative=backward, positive=forward; stopped only; RAM only");
  reply("wave: raise one leg and wave for ~5.4s; wave leg 1..4 selects FL/FR/RL/RR (default FL); stop cancels");
  reply("stand record: record stand commands, foot x=0 z=65mm; stand direction ID +1/-1 for ALL 8 joints");
  reply("stand save / stand load: save or load stand and directions; ws: working settings");
  reply("stand: return to stand in 1.5s; walk directions can change while walking; stop: hold pose, next start forward");
}

bool calibrationCommand(const String &cmd) {
  if (cmd=="stand load") {
    if (walking || transitioning || waving) reply("Stop before loading calibration.",false);
    else loadWalkCalibration();
    return true;
  }
  if (cmd=="stand record") {
    if (walking || transitioning || waving) { reply("Stop and position legs first.",false); return true; }
    for (uint8_t i=0;i<SERVO_COUNT;++i) if (!servos[i].attached()) { reply("A servo is not attached.",false); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) standAngles[i]=commandAngles[i];
    standCaptured=true;
    walkFootOffsetX=0.f;
    reply("Standing commands captured, not measured; foot offset reset to 0."); return true;
  }
  if (cmd=="stand save") {
    if (!walkReady() || walking || transitioning || waving) { reply("Need stopped, captured stand and all 8 dir signs.",false); return true; }
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
    else if (walking || transitioning || waving) reply("Stop before changing calibration.",false);
    else { jointDirection[id-1]=d; reply("Direction updated in RAM."); }
    return true;
  }
  return false;
}

bool gaitSettingsCommand(const String &cmd) {
  if (cmd=="walk save" || cmd=="walk load" || cmd=="walk reset") {
    if (walking || transitioning || waving) { reply("Stop before changing/saving gait settings.",false); return true; }
    if (cmd=="walk load") { bool ok=loadGaitSettings(); reply(ok ? "Gait loaded." : "No valid saved gait; unchanged.",ok); return true; }
    if (cmd=="walk reset") {
      for (auto &v:legTuning) v=LegTuning();
      walkCenterX=0.f;
      walkBias=0.f;
      reply("Default gait, center and bias in RAM; calibration unchanged."); return true;
    }
    if (!validateGait(legTuning)) { reply("Invalid gait settings.",false); return true; }
    Preferences prefs; bool ok=prefs.begin("quad-gait",false);
    if (ok) {
      ok=prefs.putBytes("legs-v2",legTuning,sizeof legTuning)==sizeof legTuning;
      if (ok) ok=prefs.putFloat("center",walkCenterX)==sizeof(float);
      if (ok) ok=prefs.putFloat("bias",walkBias)==sizeof(float);
      prefs.end();
    }
    reply(ok ? "Gait, center and bias saved; calibration unchanged." : "Error saving gait.",ok); return true;
  }
  if (cmd=="walk bias" || cmd.startsWith("walk bias ")) {
    float bias; char tail;
    if (sscanf(cmd.c_str(),"walk bias %f %c",&bias,&tail)!=1 ||
        !isfinite(bias) || fabsf(bias)>WALK_BIAS_MAX) {
      reply("Use walk bias -0.4..0.4; positive=left. Use walk save to persist.",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before changing walk bias.",false); return true; }
    if (walkTurnGain<.01f) { reply("Set walk turn gain >0 before walk bias.",false); return true; }
    const float previous=walkBias;
    walkBias=bias;
    if (!validateGait(legTuning,walkDirectionTarget,walkTurnTarget,walkTurnGain)) {
      walkBias=previous;
      reply("Rejected: walk bias makes the gait unreachable.",false); return true;
    }
    reply("Walk bias applied in RAM; use walk save to persist.");
    return true;
  }
  if (cmd=="walk center" || cmd.startsWith("walk center ")) {
    float mm; char tail;
    if (sscanf(cmd.c_str(),"walk center %f %c",&mm,&tail)!=1 ||
        !isfinite(mm) || mm<-WALK_CENTER_MAX || mm>WALK_CENTER_MAX) {
      reply("Use walk center MM (-25..25; negative=gait feet back).",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before changing walk center.",false); return true; }
    const float previous=walkCenterX;
    walkCenterX=mm;
    if (!validateGait(legTuning,walkDirectionTarget,walkTurnTarget,walkTurnGain)) {
      walkCenterX=previous;
      reply("Rejected: walk center makes the gait unreachable.",false); return true;
    }
    reply("Walk center applied in RAM; use walk save to persist.");
    return true;
  }
  if (cmd=="walk turn" || cmd.startsWith("walk turn ")) {
    float gain; char tail;
    if (sscanf(cmd.c_str(),"walk turn %f %c",&gain,&tail)!=1 ||
        !isfinite(gain) || gain<0.f || gain>TURN_GAIN_MAX) {
      reply("Use walk turn GAIN (0..0.8).",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before changing turn gain.",false); return true; }
    const float previous=walkTurnGain;
    walkTurnGain=gain;
    if (!validateGait(legTuning,walkDirectionTarget,walkTurnTarget,walkTurnGain)) {
      walkTurnGain=previous;
      reply("Rejected: turn gain makes the gait unreachable.",false); return true;
    }
    reply("Turn gain applied in RAM; no movement."); return true;
  }
  if (cmd=="walk set" || cmd.startsWith("walk set ")) {
    long leg; float lift,depth,stride,lp,rp; char tail;
    if (sscanf(cmd.c_str(),"walk set %ld %f %f %f %f %f %c",&leg,&lift,&depth,&stride,&lp,&rp,&tail)!=6 || leg<1 || leg>4) {
      reply("Use walk set LEG LIFT DEPTH STRIDE LIFT_PERCENT LOWER_PERCENT.",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before applying tuning.",false); return true; }
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
    Serial.printf("motion=%s dir=%.2f turn=%.2f gain=%.2f targetDir=%.2f targetTurn=%.2f footOffset=%.1f mm walkCenter=%.1f mm walkBias=%.3f waving=%d waveLeg=%u\n",
                  motionName(),walkDirection,walkTurn,walkTurnGain,walkDirectionTarget,walkTurnTarget,walkFootOffsetX,
                  walkCenterX,walkBias,waving,waveLeg+1);
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
  if (cmd=="wave leg" || cmd.startsWith("wave leg ")) {
    long id; char tail;
    if (sscanf(cmd.c_str(),"wave leg %ld %c",&id,&tail)!=1 || id<1 || id>4) {
      reply("Use wave leg 1..4: 1 FL, 2 FR, 3 RL, 4 RR. Front uses a 20mm lift.",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before changing the wave leg.",false); return true; }
    waveLeg=id-1;
    reply("Wave leg set to "+String(id)+" ("+(waveLeg<2 ? String("front") : String("rear"))+"); RAM only.");
    return true;
  }
  if (cmd=="wave") return startWave();
  if (cmd=="foot offset" || cmd.startsWith("foot offset ")) {
    float mm; char tail;
    if (sscanf(cmd.c_str(),"foot offset %f %c",&mm,&tail)!=1 ||
        !isfinite(mm) || mm<-FOOT_OFFSET_MAX || mm>FOOT_OFFSET_MAX) {
      reply("Use foot offset MM (-20..20; negative=backward).",false); return true;
    }
    if (walking || transitioning || waving) { reply("Stop before changing foot offset.",false); return true; }
    const float previous=walkFootOffsetX;
    walkFootOffsetX=mm;
    if (!standOffsetValid() ||
        !validateGait(legTuning,walkDirectionTarget,walkTurnTarget,walkTurnGain)) {
      walkFootOffsetX=previous;
      reply("Rejected: foot offset makes stand or gait unreachable.",false); return true;
    }
    reply("Foot offset applied in RAM: "+String(mm,1)+" mm; negative = backward; affects stand and walk.");
    return true;
  }
  if (cmd=="stand") {
    if (!standCaptured) { reply("Capture stand first.",false); return true; }
    for (uint8_t i=0; i<SERVO_COUNT; ++i) if (!servos[i].attached()) { reply("Servo not attached.",false); return true; }
    stopWalk(); float target[SERVO_COUNT];
    for (uint8_t leg=0; leg<4; ++leg)
      if (!legTarget(leg,walkFootOffsetX,CALIBRATION_HEIGHT_MM,target)) {
        reply("Offset stand unreachable; lower foot offset.",false); return true;
      }
    beginTransition(target);
    reply("Returning to stand; foot offset "+String(walkFootOffsetX,1)+" mm."); return true;
  }
  if (cmd=="walk") return startWalk(1.f,0.f);
  if (cmd=="walk straight" || cmd=="straight") {
    const float direction=walking ? walkDirectionTarget : 1.f;
    return startWalk(direction,0.f);
  }
  if (cmd=="walk back" || cmd=="back") return startWalk(-1.f,0.f);
  if (cmd=="walk left" || cmd=="left") {
    const float direction=walking ? walkDirectionTarget : 1.f;
    return startWalk(direction,1.f);
  }
  if (cmd=="walk right" || cmd=="right") {
    const float direction=walking ? walkDirectionTarget : 1.f;
    return startWalk(direction,-1.f);
  }
  return false;
}
