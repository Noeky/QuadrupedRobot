// Compile with -Iscripts/test_support. Runs real firmware handlers on host doubles.
#include <cassert>
#include "../firmware/servo_control/servo_control.ino"

int main(){
  setup();
  assert(!walking && !standCaptured);
  int initialWrites=servos[0].writes;
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"ready\":false")!=String::npos);
  assert(phoneServer.body.find("\"motion\":\"stopped\"")!=String::npos);
  assert(phoneServer.body.find("\"turnGain\":0.500")!=String::npos);
  assert(phoneServer.body.find("\"footOffset\":0.0")!=String::npos);
  assert(servos[0].writes==initialWrites); // Opening/refreshing never moves a joint.
  auto command=[](const String &s,const String &client="phone-1234"){
    return phoneServer.request("/api/command",HTTP_POST,{{"client",client},{"cmd",s}},phoneKey);
  };
  assert(phoneServer.request("/api/command",HTTP_POST,{{"client","phone-1234"},{"cmd","init"}})==403);
  assert(command("walk")==422 && !walking);
  assert(command("stand record")==200);
  for(unsigned i=0;i<8;++i) assert(command("stand direction "+String(i+1)+(i%2?" 1":" -1"))==200);
  assert(walkReady());
  assert(command("stand load")==422 && walkReady()); // Failed load keeps the working copy.
  walkPrefs.putBytes("stand",standAngles,sizeof standAngles);
  walkPrefs.putBytes("dirs",jointDirection,sizeof jointDirection);
  walkPrefs.putUInt("version",1);
  assert(command("stand load")==200 && servos[0].writes==initialWrites);
  assert(command("stand save")==200);
  auto calibration=Preferences::data["quad-walk"];
  assert(command("foot offset -5")==200 && walkFootOffsetX==-5.f);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"footOffset\":-5.0")!=String::npos);
  assert(command("foot offset -25")==422 && walkFootOffsetX==-5.f);
  assert(command("stand")==200);fakeMillis+=1500;updateWalk();
  assert(!transitioning && commandAngles[0]!=standAngles[0]); // Stand shifted.
  assert(command("foot offset -2.5")==200 && walkFootOffsetX==-2.5f);
  assert(command("foot offset 0")==200 && walkFootOffsetX==0.f);
  assert(command("wave leg 1")==200 && waveLeg==0);
  assert(command("wave")==200 && waving && !walking && !transitioning);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"waving\":true")!=String::npos);
  assert(phoneServer.body.find("\"motion\":\"wave\"")!=String::npos);
  assert(command("walk")==422 && waving); // Stop the wave first.
  fakeMillis+=WAVE_PREPARE_MS+WAVE_MOTION_MS+WAVE_RETURN_MS+100;
  updateWalk();
  assert(!waving);
  assert(command("wave leg 4")==200 && waveLeg==3);
  assert(command("wave leg 3")==200 && waveLeg==2);
  assert(command("wave")==200 && waving && !walking && !transitioning);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"waving\":true")!=String::npos);
  assert(phoneServer.body.find("\"motion\":\"wave\"")!=String::npos);
  assert(command("wave")==422 && waving); // Already waving.
  assert(command("walk")==422 && waving);
  fakeMillis+=WAVE_PREPARE_MS+WAVE_MOTION_MS+WAVE_RETURN_MS+100;
  updateWalk();
  assert(!waving);
  assert(command("walk center -10")==200 && walkCenterX==-10.f);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"walkCenter\":-10.0")!=String::npos);
  assert(command("walk center -30")==422 && walkCenterX==-10.f);
  assert(command("walk center 0")==200 && walkCenterX==0.f);
  assert(command("walk bias 0.09")==200 && fabsf(walkBias-.09f)<1e-6f);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"walkBias\":0.090")!=String::npos);
  assert(command("walk bias 0.5")==422 && fabsf(walkBias-.09f)<1e-6f);
  assert(command("walk bias 0")==200 && walkBias==0.f);
  assert(command("walk speed 0.731")==200 && fabsf(walkSpeed-.731f)<1e-6f);
  assert(command("walk speed 2.137")==200 && fabsf(walkSpeed-2.137f)<1e-6f);
  assert(command("walk deadband 1.25")==200 && walkDeadband==1.25f);
  assert(command("walk deadband nan")==422 && command("walk deadband 5.1")==422);
  for(const char *bad:{"walk speed 0","walk speed nan","walk speed inf","walk speed 4.1","walk speed 1 junk","set 1 181","set 0 90","set 1 90 junk"})assert(command(bad)==422);
  assert(command("walk set 3 18 2 27 20 35")==200);
  assert(legTuning[2].lift==18 && legTuning[2].depth==2 && legTuning[0].lift==15);
  float target[8];assert(calculateWalk(.7f,target,legTuning));
  Preferences legacyGait;
  legacyGait.begin("quad-gait",false);
  legacyGait.putBytes("legs",legTuning,sizeof legTuning);
  legacyGait.putUInt("version",1);
  legacyGait.end();
  assert(command("walk reset")==200 && legTuning[2].lift==15);
  assert(command("walk load")==200 && legTuning[2].lift==18);
  assert(command("walk center -8")==200 && walkCenterX==-8.f);
  assert(command("walk bias 0.09")==200 && fabsf(walkBias-.09f)<1e-6f);
  assert(command("walk save")==200 && Preferences::data["quad-walk"]==calibration);
  assert(command("walk reset")==200 && legTuning[2].lift==15 && walkCenterX==0.f && walkBias==0.f);
  assert(command("walk load")==200 && legTuning[2].lift==18 && walkCenterX==-8.f && fabsf(walkBias-.09f)<1e-6f);
  assert(command("walk set 3 40 0 28 25 25")==422 && legTuning[2].lift==18);
  assert(command("walk set 3 15 0 28 45 45")==422);
  assert(command("walk set 5 15 0 28 25 25")==422);
  assert(command("walk")==200 && walking && transitioning);
  assert(command("walk back")==422 && walkDirectionTarget==1.f); // Wait for transition.
  assert(phoneServer.request("/api/heartbeat",HTTP_POST,{{"client","phone-1234"}},phoneKey)==200);
  assert(phoneServer.body.find("\"ok\":true")!=String::npos);
  assert(phoneServer.body.find("\"walking\":true")!=String::npos);
  for(const char *cmd:{"stand load","stand direction 1 1","stand save","walk load","walk save","walk reset","foot offset 0","wave","wave leg 3","walk center 0","walk bias 0"})
    assert(command(cmd)==422 && walking);
  assert(command("stand record")==422);
  assert(command("walk set 3 15 0 28 25 25")==422);
  assert(command("stand","phone-9999")==409); // Another page cannot silently take over.
  fakeMillis+=1500; updateWalk();assert(!transitioning);
  assert(command("walk left")==200 && walkTurnTarget==1.f);
  assert(phoneServer.request("/api/state",HTTP_GET)==200);
  assert(phoneServer.body.find("\"motion\":\"left\"")!=String::npos);
  assert(command("walk right")==200 && walkTurnTarget==-1.f);
  assert(command("walk straight")==200 && walkTurnTarget==0.f);
  assert(command("walk back")==200 && walkDirectionTarget==-1.f);
  assert(command("walk")==200 && walkDirectionTarget==1.f && walkTurnTarget==0.f);
  assert(command("walk turn 0.6")==422 && walking); // Gain changes need a stop.
  fakeMillis+=100;updateWalk();float phase=walkPhase;
  assert(command("walk speed 0.789")==200 && fabsf(walkPhase-phase)<1e-6f);
  fakeMillis+=300;updateWalk();
  assert(fabsf(walkPhase-advanceWalkPhase(phase,40,.789f))<1e-6f);
  for(auto &servo:servos) assert(servo.pulse>500 && servo.pulse<2500);
  assert(command("stop","phone-9999")==200 && !walking && walkDirectionTarget==1.f && walkTurnTarget==0.f);
  assert(command("stand")==200);fakeMillis+=1500;updateWalk();
  for(unsigned i=0;i<8;++i)assert(commandAngles[i]==standAngles[i]); // Tuning does not alter stand.
  assert(command("walk turn 0.6")==200 && walkTurnGain==0.6f);
  assert(command("walk turn 1.0")==422 && walkTurnGain==0.6f);
  assert(command("walk turn 0.5")==200 && walkTurnGain==0.5f);
  assert(command("crawl")==422 && !walking);
  assert(command("f")==422 && !walking);
  assert(command("walk")==200 && walking);
  unsigned writes=servos[0].writes;
  fakeMillis+=PHONE_TIMEOUT_MS+1;updatePhoneControl();updateWalk();
  assert(!walking && !transitioning && phoneOwner.empty() && servos[0].writes==int(writes));
  assert(phoneServer.request("/api/heartbeat",HTTP_POST,{{"client","phone-1234"}},phoneKey)==409);
  assert(command("walk")==200);fakeMillis+=1000;
  assert(phoneServer.request("/api/heartbeat",HTTP_POST,{{"client","phone-9999"}},phoneKey)==409);
  fakeMillis+=1501;updatePhoneControl();assert(!walking);
  assert(command("stand load")==200 && standCaptured && !walking);
  assert(Preferences::data["quad-walk"]==calibration);
  assert(command("walk set 1 15 0 28 25 25")==200);
  standAngles[0]=0;jointDirection[0]=-1;
  assert(command("walk")==422); // Valid geometry can still exceed actual calibrated command limits.
  assert(phoneServer.request("/api/wifi",HTTP_POST,{{"ssid","test"},{"password","short"}},phoneKey)==400);
  assert(phoneServer.request("/api/wifi",HTTP_POST,{{"ssid","test"},{"password","testpassword"}},phoneKey)==200);
  assert(Preferences::data["quad-walk"]==calibration);
  assert(jsonQuote("a\"\\\n")=="\"a\\\"\\\\\\u000a\"");
  assert(command("stand load")==200);
  for(unsigned i=0;i<8;++i) assert(command("set "+String(i+1)+" "+String(82+i))==200);
  assert(command("stand record")==200 && command("stand save")==200);
  standCaptured=false;
  for(auto &servo:servos) servo=Servo();
  setup();
  assert(walkReady() && !walking && !transitioning);
  for(unsigned i=0;i<8;++i)
    assert(servos[i].writes==1 && servos[i].angle==82+int(i) && commandAngles[i]==servos[i].angle);
  int priorPulse=servos[0].pulse;
  writeServoAngle(0,82.2f,12);
  assert(servos[0].pulse==priorPulse && commandAngles[0]==82);
  writeServoAngle(0,83.2f,12);
  assert(servos[0].pulse>=priorPulse+12 && commandAngles[0]==83);
  writeServoAngle(0,82.f,1);
  writeServoAngle(0,82.2f,1);
  assert(servos[0].pulse>priorPulse && commandAngles[0]==82);

  // Avoid settings and timed in-place turn.
  assert(command("avoid dist 20")==200 && avoidDistanceMm==200);
  assert(command("avoid dist 4")==422 && avoidDistanceMm==200);
  assert(command("avoid turn right")==200 && avoidTurnSign<0);
  assert(command("avoid turn left")==200 && avoidTurnSign>0);
  assert(command("avoid turnms 2000")==200 && avoidTurnMs==2000);
  assert(command("avoid stride 18")==200 && fabsf(avoidTurnStrideMm-18.f)<1e-6f);
  assert(command("avoid max 2")==200 && avoidMaxTurns==2);
  assert(command("avoid on")==200 && avoidEnabled);
  assert(command("avoid off")==200 && !avoidEnabled);
  assert(command("turn left 2000")==200 && turning);
  fakeMillis+=1500; updateWalk(); assert(!transitioning && turning);
  fakeMillis+=2000; updateWalk(); assert(!turning && transitioning);
  fakeMillis+=1500; updateWalk(); assert(!transitioning);

  // Only 0..200 mm triggers; -1 is ignored/taken as clear at recheck.
  usSetMockMm(150);
  assert(command("avoid on")==200 && avoidEnabled);
  assert(command("walk")==200 && walking);
  fakeMillis+=1500; updateWalk();
  avoidTick(); fakeMillis+=120; avoidTick();
  assert(!walking && avoidPhase==AVOID_STAND && transitioning);
  fakeMillis+=1600; updateWalk(); avoidTick();
  assert(avoidPhase==AVOID_TURN && turning);
  fakeMillis+=1500; updateWalk();
  fakeMillis+=2000; updateWalk();
  assert(!turning && transitioning);
  fakeMillis+=1500; updateWalk(); avoidTick();
  assert(avoidPhase==AVOID_RECHECK);
  usSetMockMm(-1); fakeMillis+=300; avoidTick();
  assert(walking && avoidPhase==AVOID_IDLE);
  assert(command("stop")==200 && !walking);
  assert(command("avoid off")==200 && !avoidEnabled);
  puts("PASS: shared executor, forward/back/turn, bias, wave, ultrasonic avoid, in-place turn, calibration isolation, persistence and ownership");
}
