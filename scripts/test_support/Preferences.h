#pragma once
#include "Arduino.h"
#include <map>
#include <vector>
class Preferences {
  String ns;bool readonly=false;
public:
  static std::map<std::string,std::map<std::string,std::vector<uint8_t>>> data;
  bool begin(const char *name,bool ro=false){ns=name;readonly=ro;return !ro || data.count(ns);}
  void end(){}
  size_t putBytes(const char *key,const void *p,size_t n){if(readonly)return 0;auto b=static_cast<const uint8_t*>(p);data[ns][key]=std::vector<uint8_t>(b,b+n);return n;}
  size_t getBytes(const char *key,void *p,size_t n){auto &v=data[ns][key];if(v.size()!=n)return 0;memcpy(p,v.data(),n);return n;}
  unsigned getUInt(const char *key,unsigned fallback=0){unsigned n;return getBytes(key,&n,sizeof n)==sizeof n?n:fallback;}
  size_t putUInt(const char *key,unsigned n){return putBytes(key,&n,sizeof n);}
  float getFloat(const char *key,float fallback=0){float n;return getBytes(key,&n,sizeof n)==sizeof n?n:fallback;}
  size_t putFloat(const char *key,float n){return putBytes(key,&n,sizeof n);}
  bool getBool(const char *key,bool fallback=false){bool n;return getBytes(key,&n,sizeof n)==sizeof n?n:fallback;}
  size_t putBool(const char *key,bool n){return putBytes(key,&n,sizeof n);}
  String getString(const char *key,const String &fallback=""){auto &v=data[ns][key];return v.empty()?fallback:String(std::string(v.begin(),v.end()));}
  size_t putString(const char *key,const String &s){return putBytes(key,s.data(),s.size());}
};
std::map<std::string,std::map<std::string,std::vector<uint8_t>>> Preferences::data;
