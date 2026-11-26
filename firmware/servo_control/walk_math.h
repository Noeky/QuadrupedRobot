#pragma once
#include <math.h>

constexpr float CALIBRATION_HEIGHT_MM = 65.f;
constexpr float SUPPORT_HEIGHT_MM = 65.f;
constexpr float FOOT_LIFT_MM = 15.f;
constexpr float BASE_CYCLE_MS = 4000.f;
constexpr float MAX_STRIDE_MM = 50.f;
constexpr float TURN_GAIN_MAX = .8f;
// Flip to -1 only if the physical left/right turn comes out reversed.
constexpr float TURN_SIGN = 1.f;
struct LegTuning {
  float lift=15.f, depth=0.f, stride=28.f;
  float liftPart=.25f, lowerPart=.25f;
};
inline bool validLegTuning(const LegTuning &v) {
  return isfinite(v.lift) && isfinite(v.depth) && isfinite(v.stride) &&
    isfinite(v.liftPart) && isfinite(v.lowerPart) &&
    v.lift>=0 && v.lift<=30 && v.depth>=-10 && v.depth<=10 &&
    v.stride>=0 && v.stride<=MAX_STRIDE_MM && v.liftPart>=.1f && v.lowerPart>=.1f &&
    v.liftPart<=.45f && v.lowerPart<=.45f && v.liftPart+v.lowerPart<=.8f;
}
// A turn scales the left/right stride differentially. Reject combinations
// whose effective stride would leave the 0..50 mm software envelope.
inline bool validTurn(const LegTuning &v, float turn, float gain) {
  if (!isfinite(turn) || !isfinite(gain) || fabsf(turn)>1.f) return false;
  if (gain<0.f || gain>TURN_GAIN_MAX) return false;
  const float k=fabsf(turn*gain);
  return v.stride*(1.f+k)<=MAX_STRIDE_MM+1e-3f &&
         v.stride*(1.f-k)>=-1e-3f;
}
inline float moveToward(float value, float target, float maxDelta) {
  if (value<target) return fminf(target,value+maxDelta);
  return fmaxf(target,value-maxDelta);
}
inline float advanceWalkPhase(float phase, unsigned long elapsedMs, float speed) {
  float next = phase + elapsedMs * speed / BASE_CYCLE_MS;
  return next - floorf(next);
}

// Sagittal 2-link leg: x forward, z down; CAD axis distances in mm.
// Hip positive: thigh rotates forward from vertical-down.
// Knee positive: lower leg bends backward relative to thigh.
inline bool legIK(float x, float z, float &hip, float &knee) {
  constexpr float a = 40.f, b = 45.f, deg = 57.295779513f;
  float c = (x*x + z*z - a*a - b*b) / (2*a*b);
  if (c < -1.f || c > 1.f || z <= 0.f) return false;
  float k = acosf(c);
  hip = (atan2f(x, z) + atan2f(b*sinf(k), a+b*cosf(k))) * deg;
  knee = k * deg;
  return true;
}

inline float smoothStep(float t) { return t*t*(3.f-2.f*t); }

// Ease into and out of ground travel while keeping the middle at constant speed.
inline float stanceProgress(float t) {
  constexpr float ramp = .15f;
  if (t < ramp) return t*t/(2.f*ramp*(1.f-ramp));
  if (t > 1.f-ramp) {
    const float remaining=1.f-t;
    return 1.f-remaining*remaining/(2.f*ramp*(1.f-ramp));
  }
  return (t-ramp/2.f)/(1.f-ramp);
}

// Diagonal pairs alternate. Swing and stance each occupy half a cycle.
// 28 mm stride, 15 mm lift, nominal 4 second cycle; stance foot travels backward.
// direction=+1 forward, -1 backward. turn=+1 left, -1 right; turnGain scales
// the left/right stride difference. The base LegTuning is never modified.
// Draw the swing/stance path for an already-chosen (possibly signed) stride.
// Signed stride is used by the in-place turn: left/right sides get opposite
// signs, so the average forward push cancels and the body yaws.
inline void footPathForStride(float phase, unsigned leg, float &x, float &z,
                              const LegTuning &v, float stride) {
  const float diagonalOffset[4] = {0.f, .5f, .5f, 0.f};
  constexpr float swing = .5f;
  float p = phase - diagonalOffset[leg];
  p -= floorf(p);
  z = SUPPORT_HEIGHT_MM+v.depth;
  if (p < swing) {
    float s = p / swing;
    // Lift first, then advance with the foot kept raised, then lower.
    // IK flexes the knee during lift and keeps it flexed through the advance.
    if (s < v.liftPart) {
      x = -stride/2;
      z -= v.lift*smoothStep(s/v.liftPart);
    } else if (s < 1-v.lowerPart) {
      x = -stride/2 + stride*smoothStep((s-v.liftPart)/(1-v.liftPart-v.lowerPart));
      z -= v.lift;
    } else {
      x = stride/2;
      z -= v.lift*(1.f-smoothStep((s-(1-v.lowerPart))/v.lowerPart));
    }
  } else {
    x = stride/2 - stride*stanceProgress((p-swing)/(1.f-swing));
  }
}

inline void footPath(float phase, unsigned leg, float &x, float &z,
                     const LegTuning &v=LegTuning(),
                     float direction=1.f, float turn=0.f, float turnGain=.5f) {
  // Sesame-inspired exchange: left-front/right-rear, then right-front/left-rear.
  const float side[4] = {1.f, -1.f, 1.f, -1.f}; // FL, FR, RL, RR: left +
  const float t = turn * TURN_SIGN;
  float stride = v.stride * (1.f - t * direction * side[leg] * turnGain);
  stride = fmaxf(0.f, fminf(MAX_STRIDE_MM, stride));
  footPathForStride(phase,leg,x,z,v,stride);
  x *= direction;
}
