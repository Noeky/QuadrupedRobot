#pragma once
// Host-only doubles. No serial port, Wi-Fi adapter, flash or servo is accessed.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cctype>
#include <sstream>
#include <iomanip>
#include <string>
#include <type_traits>
#define PROGMEM
#define HEX 16
class String:public std::string {
public:
  using std::string::string;
  using std::string::operator=;
  String()=default;
  String(const std::string &s):std::string(s){}
  template<class T,typename std::enable_if<std::is_integral<T>::value,int>::type=0>
  String(T n,int base=10) { std::ostringstream s;if(base==16)s<<std::hex;s<<+n;assign(s.str()); }
  String(float n,int digits=2) { std::ostringstream s;s<<std::fixed<<std::setprecision(digits)<<n;assign(s.str()); }
  bool startsWith(const char *s)const{return rfind(s,0)==0;}
  void trim(){auto a=find_first_not_of(" \t\r\n");if(a==npos){clear();return;}auto b=find_last_not_of(" \t\r\n");assign(substr(a,b-a+1));}
};
uint32_t fakeMillis=0;
inline uint32_t millis(){return fakeMillis;}
inline void delay(unsigned n){fakeMillis+=n;}
inline uint32_t esp_random(){static uint32_t n=100;return ++n;}
struct FakeESP{uint64_t getEfuseMac(){return 0x123456;}} ESP;
struct FakeSerial {
  void begin(int){} void setTimeout(int){}
  void println(const String&){} void println(){}
  template<class... T> void printf(const char*,T...){}
  bool available(){return false;} char read(){return 0;}
} Serial;
