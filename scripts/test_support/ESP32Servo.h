#pragma once
#include "Arduino.h"
struct Servo {
  bool active=false; int angle=-1,pulse=-1,writes=0;
  void setPeriodHertz(int){} void attach(int,int,int){active=true;}
  bool attached()const{return active;}
  void writeMicroseconds(int v){pulse=v;angle=int(lroundf((v-500)*180.f/2000.f));++writes;}
};
struct ESP32PWM {static void allocateTimer(int){}};
