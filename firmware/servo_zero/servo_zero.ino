#include <ESP32Servo.h>

Servo servo;
const int SERVO_PIN = 4;  // 扩展板1路 = GPIO4 / D4

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(100);
  servo.setPeriodHertz(50);
  servo.attach(SERVO_PIN, 500, 2500);  // 扩大映射行程；两端仍需空载逐步验证
  servo.write(90);  // 先保持中位，方便安装舵臂
  Serial.println("Ready: GPIO4, command 90 deg. Enter an integer angle + newline.");
}

void loop() {
  if (!Serial.available()) return;

  String text = Serial.readStringUntil('\n');
  text.trim();
  if (text.length() == 0) return;

  char *end;
  long angle = strtol(text.c_str(), &end, 10);
  if (*end != '\0') {
    Serial.println("Please enter an integer angle, e.g. 90.");
    return;
  }

  servo.write((int)angle);  // 不额外设置机械角度上限，也不做自动扫描
  Serial.printf("Input: %ld; library command: %d deg (not measured).\n",
                angle, servo.read());
}
