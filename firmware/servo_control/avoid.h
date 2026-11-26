#pragma once
// Forward-obstacle avoidance with the HC-SR04 in ultrasonic.h.
// Policy chosen by the user: only a valid reading in 0..threshold stops the
// robot; -1 (no echo) is ignored. If -1 persists at the recheck, it is treated
// as clear and the robot resumes forward, as requested.
#include "ultrasonic.h"

bool avoidEnabled=false;
int avoidDistanceCm=20;
int avoidDistanceMm=200;
float avoidTurnSign=1.f;        // +1 left, -1 right
uint32_t avoidTurnMs=2000;
float avoidTurnStrideMm=18.f;
uint8_t avoidMaxTurns=8;
uint8_t avoidTurns=0, avoidLowCount=0;

enum AvoidPhase : uint8_t {
  AVOID_IDLE=0, AVOID_STAND, AVOID_TURN, AVOID_RECHECK, AVOID_HOLD
};
AvoidPhase avoidPhase=AVOID_IDLE;
uint32_t avoidPhaseAt=0;

const char *avoidPhaseName() {
  switch (avoidPhase) {
    case AVOID_IDLE: return "idle";
    case AVOID_STAND: return "standing";
    case AVOID_TURN: return "turning";
    case AVOID_RECHECK: return "recheck";
    case AVOID_HOLD: return "hold";
  }
  return "?";
}

bool avoidNear() {
  const int mm=usDistanceMm;
  return mm>=0 && mm<=avoidDistanceMm;
}

void avoidReset() {
  avoidPhase=AVOID_IDLE;
  avoidTurns=0;
  avoidLowCount=0;
}

void avoidTick() {
  if (!avoidEnabled) return;
  const uint32_t now=millis();
  switch (avoidPhase) {
    case AVOID_IDLE: {
      if (!walking || transitioning || turning) { avoidLowCount=0; break; }
      static uint32_t lastCheck=0;
      if (now-lastCheck<100) break;
      lastCheck=now;
      if (avoidNear()) {
        if (++avoidLowCount>=2) {
          stopWalk();
          float target[SERVO_COUNT];
          if (buildStandTarget(target)) beginTransition(target);
          avoidPhase=AVOID_STAND;
          avoidPhaseAt=now;
          avoidTurns=0;
          avoidLowCount=0;
          reply("Avoid: obstacle <= "+String(avoidDistanceCm)+" cm; standing.");
        }
      } else {
        avoidLowCount=0;
      }
      break;
    }
    case AVOID_STAND:
      if (!transitioning && now-avoidPhaseAt>=1600) {
        if (avoidTurns>=avoidMaxTurns) {
          avoidPhase=AVOID_HOLD;
          reply("Avoid: max turns reached; holding.",false);
          break;
        }
        startTurnInPlace(avoidTurnSign,avoidTurnMs,avoidTurnStrideMm);
        if (turning) {
          ++avoidTurns;
          avoidPhase=AVOID_TURN;
          avoidPhaseAt=now;
        } else {
          avoidPhase=AVOID_HOLD;
        }
      }
      break;
    case AVOID_TURN:
      if (!turning && !transitioning) {
        avoidPhase=AVOID_RECHECK;
        avoidPhaseAt=now;
      }
      break;
    case AVOID_RECHECK:
      if (now-avoidPhaseAt>=250) {
        if (avoidNear()) {
          if (avoidTurns>=avoidMaxTurns) {
            avoidPhase=AVOID_HOLD;
            reply("Avoid: still blocked; max turns reached; holding.",false);
          } else {
            startTurnInPlace(avoidTurnSign,avoidTurnMs,avoidTurnStrideMm);
            if (turning) {
              ++avoidTurns;
              avoidPhase=AVOID_TURN;
              avoidPhaseAt=now;
            } else {
              avoidPhase=AVOID_HOLD;
            }
          }
        } else {
          // The chosen policy ignores -1 and treats it as clear.
          startWalk(1.f,0.f);
          if (walking) {
            avoidReset();
            reply("Avoid: clear; resuming forward.");
          } else {
            avoidPhase=AVOID_HOLD;
            reply("Avoid: clear but start failed; holding.",false);
          }
        }
      }
      break;
    case AVOID_HOLD:
      break;
  }
}

void avoidStatus() {
  Serial.printf("avoid=%d phase=%s dist=%d cm us=%d mm turns=%u/%u turn=%s ms=%lu stride=%.1f\n",
                avoidEnabled, avoidPhaseName(), avoidDistanceCm, (int)usDistanceMm,
                avoidTurns, avoidMaxTurns, avoidTurnSign>0 ? "left" : "right",
                (unsigned long)avoidTurnMs, avoidTurnStrideMm);
}

bool avoidCommand(const String &cmd) {
  if (cmd=="turn left" || cmd.startsWith("turn left ") ||
      cmd=="turn right" || cmd.startsWith("turn right ")) {
    const bool left=cmd.startsWith("turn left");
    float ms=float(avoidTurnMs);
    char tail;
    if (sscanf(cmd.c_str(), left ? "turn left %f %c" : "turn right %f %c", &ms, &tail)!=1 &&
        cmd!="turn left" && cmd!="turn right") {
      reply("Use turn left|right [300..8000 ms].",false); return true;
    }
    startTurnInPlace(left ? 1.f : -1.f, uint32_t(ms+0.5f), avoidTurnStrideMm);
    return true;
  }
  if (cmd=="avoid on") {
    avoidEnabled=true; avoidReset();
    reply("Avoid on: only 0.."+String(avoidDistanceCm)+" mm stops; -1 ignored.");
    return true;
  }
  if (cmd=="avoid off") {
    avoidEnabled=false; avoidReset();
    reply("Avoid off; current motion continues.");
    return true;
  }
  if (cmd=="avoid" || cmd=="avoid status") {
    avoidStatus();
    reply("Avoid status printed.");
    return true;
  }
  if (cmd.startsWith("avoid dist ")) {
    float cm; char tail;
    if (sscanf(cmd.c_str(),"avoid dist %f %c",&cm,&tail)!=1 ||
        !isfinite(cm) || cm<5.f || cm>100.f) {
      reply("Use avoid dist CM (5..100).",false); return true;
    }
    avoidDistanceCm=int(cm+0.5f);
    avoidDistanceMm=avoidDistanceCm*10;
    reply("Avoid threshold: "+String(avoidDistanceCm)+" cm; valid 0.."+String(avoidDistanceMm)+" mm.");
    return true;
  }
  if (cmd=="avoid turn left" || cmd=="avoid turn right") {
    avoidTurnSign=(cmd=="avoid turn left") ? 1.f : -1.f;
    reply(String("Avoid turn: ")+(avoidTurnSign>0 ? "left" : "right")+".");
    return true;
  }
  if (cmd.startsWith("avoid turnms ")) {
    long ms; char tail;
    if (sscanf(cmd.c_str(),"avoid turnms %ld %c",&ms,&tail)!=1 || ms<300 || ms>8000) {
      reply("Use avoid turnms 300..8000.",false); return true;
    }
    avoidTurnMs=uint32_t(ms);
    reply("Avoid turn duration: "+String(ms)+" ms (gait part; stand transitions add ~3 s).");
    return true;
  }
  if (cmd.startsWith("avoid stride ")) {
    float mm; char tail;
    if (sscanf(cmd.c_str(),"avoid stride %f %c",&mm,&tail)!=1 ||
        !isfinite(mm) || mm<TURN_STRIDE_MIN || mm>TURN_STRIDE_MAX) {
      reply("Use avoid stride 5..30 mm.",false); return true;
    }
    avoidTurnStrideMm=mm;
    reply("Avoid turn stride: "+String(mm,1)+" mm.");
    return true;
  }
  if (cmd.startsWith("avoid max ")) {
    long n; char tail;
    if (sscanf(cmd.c_str(),"avoid max %ld %c",&n,&tail)!=1 || n<1 || n>12) {
      reply("Use avoid max 1..12.",false); return true;
    }
    avoidMaxTurns=uint8_t(n);
    reply("Avoid max turns: "+String(n)+".");
    return true;
  }
  return false;
}