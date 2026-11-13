#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "../firmware/servo_control/walk_math.h"

int main() {
  constexpr float rad=0.01745329252f;
  float h0,k0;
  assert(legIK(0,65,h0,k0));
  for (float speed : {.05f,.731f,1.f,2.137f,4.f}) {
    float phase=.37f;
    assert(fabsf(advanceWalkPhase(phase,0,speed)-phase)<1e-6f);
    float expected=.37f+.25f*speed;expected-=floorf(expected);
    assert(fabsf(advanceWalkPhase(phase,1000,speed)-expected)<1e-6f);
  }
  assert(fabsf(advanceWalkPhase(.9f,800,1.f)-.1f)<1e-6f);
  // Ground travel starts and ends with near-zero horizontal velocity.
  for (float boundary : {0.f,.5f,1.f}) {
    float x,z,beforeX,beforeZ,afterX,afterZ;
    footPath(boundary,0,x,z);
    footPath(boundary-.0005f,0,beforeX,beforeZ);
    footPath(boundary+.0005f,0,afterX,afterZ);
    assert(fabsf(x-beforeX)<.001f && fabsf(afterX-x)<.001f);
  }
  for (int n=0;n<=2000;++n) {
    const float phase=n/2000.f;
    for (unsigned leg=0;leg<4;++leg) {
      float x,z,h,k,nextX,nextZ;
      footPath(phase,leg,x,z);
      assert(legIK(x,z,h,k));
      const bool firstPair=leg==0 || leg==3;
      const bool swinging=firstPair ? phase<.5f : phase>=.5f && phase<1.f;
      if (!swinging) assert(fabsf(z-65.f)<.001f);
      if (n==250 || n==1250) assert(fabsf(z-(swinging ? 50.f : 65.f))<.001f);
      footPath(phase+.00001f,leg,nextX,nextZ);
      assert(fabsf(nextX-x)<.01f && fabsf(nextZ-z)<.01f);
    }
  }
  float maxH=0,maxK=0;
  // Full-cycle reachability, inverse/forward kinematics agreement, command domain,
  // and the maximum two swing legs. Uses the actual firmware math header.
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
      assert(x>=-14.001f && x<=14.001f && z>=49.999f && z<=65.001f);
      if (z<64.999f) ++raised;
      maxH=fmaxf(maxH,fabsf(h-h0)); maxK=fmaxf(maxK,fabsf(k-k0));
      assert(90-fabsf(h-h0)>=0 && 90+fabsf(h-h0)<=180);
      assert(90-fabsf(k-k0)>=0 && 90+fabsf(k-k0)<=180);
      float x2,z2; footPath(phase+0.00001f,leg,x2,z2);
      assert(fabsf(x2-x)<0.01f && fabsf(z2-z)<0.01f);
    }
    assert(raised<=2);
  }
  // During ground contact the foot moves backward, which drives the body forward.
  for (int n=0;n<499;++n) {
    float x,z,x2,z2;
    footPath(.5f+n*.001f,0,x,z);
    footPath(.5f+(n+1)*.001f,0,x2,z2);
    assert(x2<x && fabsf(z-65)<0.001f);
  }
  float h,k;
  assert(!legIK(0,100,h,k)); assert(!legIK(0,0,h,k));
  // Regression: forward transfer must happen ONLY with the foot fully raised
  // and knee flexed. Lift/lower keep x fixed; verify actual IK knee behavior.
  float previousK=0;
  for (int n=0;n<=1000;++n) {
    float t=n/1000.f, x,z,h,k;
    footPath(.5f*t,0,x,z);
    assert(legIK(x,z,h,k));
    if (t<.25f) {
      assert(fabsf(x+14.f)<.001f);
      if (n) assert(k>=previousK-.001f);
    } else if (t<=.75f) {
      assert(fabsf(z-50.f)<.001f);
      assert(k>k0+15.f);
    } else {
      assert(fabsf(x-14.f)<.001f);
      assert(k<=previousK+.001f);
    }
    previousK=k;
  }
  printf("PASS: 40004 leg samples; reference hip %.3f knee %.3f; max deltas %.3f/%.3f deg\n",h0,k0,maxH,maxK);
  // User-adjustable extremes: validate actual FK, plane, continuity and timing.
  unsigned tunedSamples=0;
  for(float lift:{0.f,15.f,30.f}) for(float depth:{-10.f,0.f,10.f})
  for(float stride:{0.f,28.f,50.f}) for(float lp:{.1f,.25f,.45f}) for(float rp:{.1f,.25f,.45f}) {
    LegTuning v;v.lift=lift;v.depth=depth;v.stride=stride;v.liftPart=lp;v.lowerPart=rp;
    if(!validLegTuning(v))continue;
    for(unsigned leg=0;leg<4;++leg) for(int n=0;n<=2000;++n) {
      float x,z,h,k,x2,z2;float phase=n/2000.f;
      footPath(phase,leg,x,z,v);assert(legIK(x,z,h,k));
      assert(fabsf(40*sinf(h*rad)+45*sinf((h-k)*rad)-x)<.001f);
      assert(fabsf(40*cosf(h*rad)+45*cosf((h-k)*rad)-z)<.001f);
      assert(z<=65+depth+.001f && z>=65+depth-lift-.001f);
      footPath(phase+.000001f,leg,x2,z2,v);
      assert(fabsf(x2-x)<.01f && fabsf(z2-z)<.01f);
      ++tunedSamples;
    }
    float x,z;footPath(.5f,0,x,z,v);
    assert(fabsf(x-stride/2)<.001f && fabsf(z-(65+depth))<.001f);
    footPath(.5f*(lp+(1-lp-rp)/2),0,x,z,v);
    assert(fabsf(z-(65+depth-lift))<.001f);
  }
  LegTuning bad;bad.lift=NAN;assert(!validLegTuning(bad));
  printf("PASS: %u tuned samples, parameter extremes and arbitrary decimal speeds\n",tunedSamples);
}
