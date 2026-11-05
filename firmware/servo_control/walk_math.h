#pragma once
#include <math.h>

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

// Crawl order FL, RR, FR, RL. Swing 20%, stance 80%: no overlapping swings.
// 28 mm stride, 12 mm lift, 4 second cycle; stance foot travels backward.
inline void footPath(float phase, unsigned leg, float &x, float &z) {
  const float offset[4] = {0.f, .5f, .75f, .25f};
  float p = phase - offset[leg];
  p -= floorf(p);
  z = 65.f;
  if (p < .2f) {
    float t = p / .2f;
    x = -14.f + 28.f*smoothStep(t);
    z -= 12.f*16.f*t*t*(1.f-t)*(1.f-t);
  } else {
    x = 14.f - 28.f*(p-.2f)/.8f;
  }
}
