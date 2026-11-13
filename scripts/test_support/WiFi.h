#pragma once
#include "Arduino.h"
constexpr int WIFI_AP_STA=3,WL_CONNECTED=3;
struct FakeIP{String value;String toString(){return value;}};
struct FakeWiFi {
  int connection=0;
  void persistent(bool){} void setHostname(const char*){} void mode(int){}
  bool softAP(const char*,const char*){return true;}
  void setAutoReconnect(bool){} void begin(const char*,const char*){} void disconnect(bool,bool){}
  int status(){return connection;}
  FakeIP localIP(){return {"0.0.0.0"};} FakeIP softAPIP(){return {"192.168.4.1"};}
} WiFi;
