#include <cassert>
#include <cstdio>
#include "../firmware/servo_control/walk_math.h"

int main() {
  constexpr float rad=0.01745329252f;
  float h0,k0;
  assert(legIK(0,65,h0,k0));
  float maxH=0,maxK=0;
  // Full-cycle reachability, inverse/forward kinematics agreement, command domain,
  // and the promised single swing leg. Uses the actual firmware math header.
  for (int n=0;n<=10000;++n) {
    float phase=n/10000.f;
    unsigned raised=0;
    for (unsigned leg=0;leg<4;++leg) {
      float x,z,h,k;
      footPath(phase,leg,x,z);
      assert(legIK(x,z,h,k));
      float xr=40*sinf(h*rad)+45*sinf((h-k)*rad);
      float zr=40*cosf(h*rad)+45*cosf((h-k)*rad);
      assert(fabsf(x-xr)<0.001f && fabsf(z-zr)<0.001f);
      assert(x>=-14.001f && x<=14.001f && z>=52.999f && z<=65.001f);
      if (z<64.999f) ++raised;
      maxH=fmaxf(maxH,fabsf(h-h0)); maxK=fmaxf(maxK,fabsf(k-k0));
      assert(90-fabsf(h-h0)>=0 && 90+fabsf(h-h0)<=180);
      assert(90-fabsf(k-k0)>=0 && 90+fabsf(k-k0)<=180);
      float x2,z2; footPath(phase+0.00001f,leg,x2,z2);
      assert(fabsf(x2-x)<0.01f && fabsf(z2-z)<0.01f);
    }
    assert(raised<=1);
  }
  // During ground contact the foot moves backward, which drives the body forward.
  for (int n=0;n<799;++n) {
    float x,z,x2,z2;
    footPath(.2f+n*.001f,0,x,z);
    footPath(.2f+(n+1)*.001f,0,x2,z2);
    assert(x2<x && fabsf(z-65)<0.001f);
  }
  float h,k;
  assert(!legIK(0,100,h,k)); assert(!legIK(0,0,h,k));
  printf("PASS: 40004 leg samples; reference hip %.3f knee %.3f; max deltas %.3f/%.3f deg\n",h0,k0,maxH,maxK);
}
