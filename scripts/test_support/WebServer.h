#pragma once
#include "Arduino.h"
#include <functional>
#include <map>
enum HTTPMethod{HTTP_GET,HTTP_POST};
class WebServer {
public:
  std::map<std::pair<std::string,int>,std::function<void()>> routes;
  std::map<std::string,String> args,headers;
  std::function<void()> notFound;
  int code=0;String body;
  WebServer(int){} void begin(){} void handleClient(){}
  void collectHeaders(const char**,size_t){}
  String arg(const char *k){return args[k];}String header(const char *k){return headers[k];}
  void sendHeader(const char*,const char*){}
  void send(int status,const char*,const String &s){code=status;body=s;}
  void send_P(int status,const char *type,const char *s){send(status,type,s);}
  void on(const char *path,HTTPMethod method,std::function<void()> fn){routes[{path,method}]=fn;}
  void onNotFound(std::function<void()> fn){notFound=fn;}
  int request(const char *path,HTTPMethod method,const std::map<std::string,String> &a={},const String &key="") {
    args=a;headers={{"X-Control-Key",key}};code=0;body="";
    auto it=routes.find({path,method});if(it==routes.end())notFound();else it->second();return code;
  }
};
