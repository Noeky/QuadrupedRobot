#pragma once
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "phone_page.h"
#if __has_include("wifi_config.h")
#include "wifi_config.h"
#endif
#ifndef ROBOT_WIFI_SSID
#define ROBOT_WIFI_SSID ""
#endif
#ifndef ROBOT_WIFI_PASSWORD
#define ROBOT_WIFI_PASSWORD ""
#endif
#ifndef ROBOT_AP_PASSWORD
#define ROBOT_AP_PASSWORD "quadrobot"
#endif

WebServer phoneServer(80);
String phoneKey,phoneOwner,apName;
uint32_t lastPhoneBeat=0;
constexpr uint32_t PHONE_TIMEOUT_MS=2500;
bool wifiPending=false;
String pendingSSID,pendingPassword;
int previousWiFiStatus=-1;

String jsonQuote(const String &value) {
  String out="\"";
  for (unsigned i=0;i<value.length();++i) {
    unsigned char c=value[i];
    if (c=='"' || c=='\\') { out+='\\'; out+=char(c); }
    else if (c<32) { char b[7]; snprintf(b,sizeof b,"\\u%04x",c); out+=b; }
    else out+=char(c);
  }
  return out+'"';
}
void sendJSON(int code,const String &json) {
  phoneServer.sendHeader("Cache-Control","no-store");
  phoneServer.send(code,"application/json; charset=utf-8",json);
}
void apiReply(int code,const String &message) {
  sendJSON(code,String("{\"ok\":")+(code<400 ? "true" : "false")+",\"message\":"+jsonQuote(message)+"}");
}
void releasePhoneControl() { phoneOwner=""; }
void checkPhoneTimeout() {
  if (phoneOwner.length() && uint32_t(millis()-lastPhoneBeat)>PHONE_TIMEOUT_MS) {
    const bool avoidActive=avoidEnabled && avoidPhase!=AVOID_IDLE;
    if (walking || transitioning || turning || avoidActive) {
      stopWalk(); avoidReset();
      reply("Phone heartbeat lost; stopped, holding last pose.",false);
    }
    releasePhoneControl();
  }
}
bool allowPhoneWrite() {
  // Custom header blocks cross-origin form submissions; no CORS is enabled.
  if (phoneServer.header("X-Control-Key")!=phoneKey) { apiReply(403,"Reload the control page."); return false; }
  return true;
}
bool phoneClient(String &client) {
  client=phoneServer.arg("client");
  if (client.length()<8 || client.length()>64) { apiReply(400,"Invalid controller ID."); return false; }
  for (unsigned i=0;i<client.length();++i) if (!isalnum(static_cast<unsigned char>(client[i])) && client[i]!='-') {
    apiReply(400,"Invalid controller ID."); return false;
  }
  checkPhoneTimeout();
  return true;
}
void phoneState() {
  String s="{\"ok\":true,\"key\":"+jsonQuote(phoneKey)+",\"owner\":"+jsonQuote(phoneOwner)+
    ",\"walking\":"+(walking ? "true" : "false")+",\"transitioning\":"+(transitioning ? "true" : "false")+
    ",\"captured\":"+(standCaptured ? "true" : "false")+",\"ready\":"+(walkReady() ? "true" : "false")+
    ",\"speed\":"+String(walkSpeed,5)+",\"deadband\":"+String(walkDeadband,3)+
    ",\"motion\":"+jsonQuote(motionName())+
    ",\"turnGain\":"+String(walkTurnGain,3)+",\"footOffset\":"+String(walkFootOffsetX,1)+
    ",\"walkCenter\":"+String(walkCenterX,1)+",\"walkBias\":"+String(walkBias,3)+
    ",\"turning\":"+(turning ? "true" : "false")+
    ",\"avoid\":"+(avoidEnabled ? "true" : "false")+
    ",\"avoidPhase\":"+jsonQuote(avoidPhaseName())+
    ",\"avoidDist\":"+String(avoidDistanceCm)+",\"avoidTurn\":"+String(avoidTurnSign>0 ? "left" : "right")+
    ",\"avoidTurnMs\":"+String((unsigned long)avoidTurnMs)+",\"avoidMax\":"+String(avoidMaxTurns)+
    ",\"avoidTurns\":"+String(avoidTurns)+
    ",\"usMm\":"+String((int)usDistanceMm)+
    ",\"waving\":"+(waving ? "true" : "false")+",\"waveLeg\":"+String(waveLeg+1)+
    ",\"direction\":"+String(walkDirectionTarget,3)+
    ",\"turn\":"+String(walkTurnTarget,3)+",\"message\":"+jsonQuote(commandMessage)+
    ",\"connected\":"+(WiFi.status()==WL_CONNECTED ? "true" : "false")+
    ",\"ip\":"+jsonQuote(WiFi.localIP().toString())+",\"ap\":"+jsonQuote(apName)+
    ",\"apIP\":"+jsonQuote(WiFi.softAPIP().toString())+",\"servos\":[";
  for (unsigned i=0;i<SERVO_COUNT;++i) {
    if (i) s+=',';
    s+="{\"id\":"+String(i+1)+",\"pin\":"+String(SERVO_PINS[i])+",\"angle\":"+String(commandAngles[i])+
      ",\"stand\":"+String(standAngles[i])+",\"dir\":"+String(jointDirection[i])+
      ",\"attached\":"+(servos[i].attached() ? "true" : "false")+"}";
  }
  s+="],\"legs\":[";
  for (unsigned i=0;i<4;++i) {
    if (i) s+=',';
    const auto &v=legTuning[i];
    s+="{\"lift\":"+String(v.lift,3)+",\"depth\":"+String(v.depth,3)+",\"stride\":"+String(v.stride,3)+
      ",\"liftPercent\":"+String(v.liftPart*100,3)+",\"lowerPercent\":"+String(v.lowerPart*100,3)+"}";
  }
  sendJSON(200,s+"]}");
}
void phoneCommand() {
  if (!allowPhoneWrite()) return;
  String client; if (!phoneClient(client)) return;
  String cmd=phoneServer.arg("cmd"); cmd.trim();
  bool readOnly=cmd=="s" || cmd=="list" || cmd=="ws" || cmd=="h" || cmd=="help";
  if (!readOnly && cmd!="stop" && phoneOwner.length() && phoneOwner!=client) {
    apiReply(409,"Another phone controls the robot. Stop or wait for its timeout."); return;
  }
  bool ok=executeCommand(cmd);
  if (ok && !readOnly) {
    if (cmd=="stop") releasePhoneControl();
    else { phoneOwner=client; lastPhoneBeat=millis(); }
  }
  apiReply(ok ? 200 : 422,commandMessage);
}
void phoneHeartbeat() {
  if (!allowPhoneWrite()) return;
  String client; if (!phoneClient(client)) return;
  if (phoneOwner!=client) { apiReply(409,"This page does not own control."); return; }
  lastPhoneBeat=millis(); phoneState();
}
void phoneWiFi() {
  if (!allowPhoneWrite()) return;
  if (walking || transitioning) { apiReply(409,"Stop before changing Wi-Fi."); return; }
  String ssid=phoneServer.arg("ssid"),password=phoneServer.arg("password");
  if (!ssid.length() || ssid.length()>32 || password.length()>63 || (password.length() && password.length()<8)) {
    apiReply(400,"SSID 1..32 bytes; password empty or 8..63 bytes."); return;
  }
  Preferences prefs; bool ok=prefs.begin("quad-net",false);
  if (ok) {
    prefs.putBool("valid",false);
    ok=prefs.putString("ssid",ssid)==ssid.length();
    ok=(prefs.putString("pass",password)==password.length()) && ok;
    if (ok) ok=prefs.putBool("valid",true)==sizeof(bool);
    prefs.end();
  }
  if (!ok) { apiReply(500,"Could not save Wi-Fi settings."); return; }
  pendingSSID=ssid; pendingPassword=password; wifiPending=true;
  apiReply(200,"Wi-Fi saved; reconnecting. Hotspot remains available.");
}
void setupPhoneControl() {
  phoneKey=String(esp_random(),HEX)+String(esp_random(),HEX);
  WiFi.persistent(false); WiFi.setHostname("quadruped"); WiFi.mode(WIFI_AP_STA);
  apName="Quadruped-"+String(uint32_t(ESP.getEfuseMac())&0xffffff,HEX);
  if (!WiFi.softAP(apName.c_str(),ROBOT_AP_PASSWORD)) Serial.println("ERROR starting robot hotspot.");
  WiFi.setAutoReconnect(true);
  String ssid=ROBOT_WIFI_SSID,password=ROBOT_WIFI_PASSWORD;
  Preferences prefs;
  if (prefs.begin("quad-net",true)) {
    if (prefs.getBool("valid",false)) { ssid=prefs.getString("ssid",ssid); password=prefs.getString("pass",password); }
    prefs.end();
  }
  if (ssid.length()) WiFi.begin(ssid.c_str(),password.c_str()); // Never block waiting for a router.
  if (MDNS.begin("quadruped")) MDNS.addService("http","tcp",80);
  const char *headers[]={"X-Control-Key"}; phoneServer.collectHeaders(headers,1);
  phoneServer.on("/",HTTP_GET,[]() {
    phoneServer.sendHeader("Cache-Control","no-store");
    phoneServer.send_P(200,"text/html; charset=utf-8",PHONE_PAGE);
  });
  phoneServer.on("/api/state",HTTP_GET,phoneState);
  phoneServer.on("/api/command",HTTP_POST,phoneCommand);
  phoneServer.on("/api/heartbeat",HTTP_POST,phoneHeartbeat);
  phoneServer.on("/api/wifi",HTTP_POST,phoneWiFi);
  phoneServer.onNotFound([](){ apiReply(404,"Not found."); });
  phoneServer.begin();
  Serial.printf("Phone hotspot: %s; http://%s\n",apName.c_str(),WiFi.softAPIP().toString().c_str());
}
void updatePhoneControl() {
  checkPhoneTimeout();
  phoneServer.handleClient();
  checkPhoneTimeout();
  if (wifiPending) {
    wifiPending=false; WiFi.disconnect(false,false);
    WiFi.begin(pendingSSID.c_str(),pendingPassword.c_str()); pendingPassword="";
  }
  int status=WiFi.status();
  if (status!=previousWiFiStatus) {
    previousWiFiStatus=status;
    if (status==WL_CONNECTED) Serial.printf("Phone LAN: http://%s or http://quadruped.local\n",WiFi.localIP().toString().c_str());
  }
}
