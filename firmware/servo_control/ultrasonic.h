#pragma once
// HC-SR04 front-facing ultrasonic, Trig=GPIO33, Echo=GPIO27.
// Echo is 5 V: use a divider (e.g. 1k series + 2k to GND) before GPIO27.
// The sensor runs in a FreeRTOS task so pulseIn() never stalls the 50 Hz gait.
#ifdef ESP32
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

constexpr int US_TRIG_PIN = 33;
constexpr int US_ECHO_PIN = 27;
volatile int usDistanceMm = -1;       // -1 = no echo/timeout
volatile uint32_t usStampMs = 0;
bool usStream = true;                 // periodic serial output, default on
uint32_t usLastPrintMs = 0;

static int usMedian3(int a, int b, int c) {
  if (a > b) { int t = a; a = b; b = t; }
  if (b > c) { int t = b; b = c; c = t; }
  if (a > b) { int t = a; a = b; b = t; }
  return b;
}

static void usTask(void *) {
  pinMode(US_TRIG_PIN, OUTPUT);
  pinMode(US_ECHO_PIN, INPUT);
  digitalWrite(US_TRIG_PIN, LOW);
  int samples[3] = {-1, -1, -1};
  uint8_t index = 0;
  for (;;) {
    digitalWrite(US_TRIG_PIN, LOW);
    delayMicroseconds(3);
    digitalWrite(US_TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(US_TRIG_PIN, LOW);
    const unsigned long echoUs = pulseIn(US_ECHO_PIN, HIGH, 30000UL);
    const int mm = echoUs ? int(echoUs * 0.1715f + 0.5f) : -1;
    samples[index++ % 3] = mm;
    usDistanceMm = usMedian3(samples[0], samples[1], samples[2]);
    usStampMs = millis();
    vTaskDelay(pdMS_TO_TICKS(100));  // 10 Hz sampling
  }
}

void usBegin() {
  pinMode(US_TRIG_PIN, OUTPUT);
  pinMode(US_ECHO_PIN, INPUT);
  digitalWrite(US_TRIG_PIN, LOW);
  xTaskCreatePinnedToCore(usTask, "us", 2048, nullptr, 1, nullptr, 0);
}

void usPrint() {
  Serial.printf("US,%lu,%d\n", (unsigned long)usStampMs, usDistanceMm);
}

void usStreamTick() {
  if (!usStream) return;
  const uint32_t now = millis();
  if (now - usLastPrintMs >= 200) {  // 5 Hz serial stream
    usLastPrintMs = now;
    usPrint();
  }
}

bool usCommand(const String &cmd) {
  if (cmd == "us" || cmd == "dist") {
    usPrint();
    reply(usDistanceMm < 0 ? "US: no echo." : "US printed.");
    return true;
  }
  if (cmd == "us stream on") { usStream = true; reply("US stream on."); return true; }
  if (cmd == "us stream off") { usStream = false; reply("US stream off."); return true; }
  if (cmd == "us stream") { reply(usStream ? "US stream on." : "US stream off."); return true; }
  return false;
}

#else
// Host-test stubs: no hardware, no FreeRTOS.
constexpr int US_TRIG_PIN = 33;
constexpr int US_ECHO_PIN = 27;
static int usDistanceMm = -1;
static uint32_t usStampMs = 0;
static bool usStream = false;
inline void usSetMockMm(int mm) { usDistanceMm = mm; usStampMs = millis(); }
inline void usBegin() {}
inline void usPrint() {}
inline void usStreamTick() {}
inline bool usCommand(const String &) { return false; }
#endif