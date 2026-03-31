#include <Servo.h>

// ===== PINES MOTOR SHIELD V1 =====
#define SR_DATA     8
#define SR_CLOCK    4
#define SR_LATCH    12
#define SR_EN       7
#define MOTOR_X_PWM 10
#define MOTOR_Y_PWM 9
#define SERVO_PIN   6

Servo servoZ;

// ===== CONFIGURACIÓN =====
#define STEPS_MM_X 39.37
#define STEPS_MM_Y 39.37
#define X_MAX_MM 80.0
#define Y_MAX_MM 80.0

// ===== VARIABLES ESTADO =====
float posX = 0, posY = 0, posZ = 90;
float targetX = 0, targetY = 0;
float feedrate = 100;
bool absoluteMode = true;
bool running = false;
int state = 0;

// Buffer pequeño
char cmd[32];
int cmdLen = 0;

void setup() {
  Serial.begin(9600);

  pinMode(SR_DATA, OUTPUT);
  pinMode(SR_CLOCK, OUTPUT);
  pinMode(SR_LATCH, OUTPUT);
  pinMode(SR_EN, OUTPUT);
  pinMode(MOTOR_X_PWM, OUTPUT);
  pinMode(MOTOR_Y_PWM, OUTPUT);

  digitalWrite(SR_EN, LOW);
  analogWrite(MOTOR_X_PWM, 200);
  analogWrite(MOTOR_Y_PWM, 200);

  servoZ.attach(SERVO_PIN);
  servoZ.write(90);

  delay(500);
  Serial.println(F("Grbl 1.1m [Shield V1]"));
}

void loop() {
  static unsigned long lastReport = 0;
  if (millis() - lastReport > 500) {
    reportStatus();
    lastReport = millis();
  }

  while (Serial.available()) {
    char c = Serial.read();

    if (c == '?') { reportStatus(); continue; }
    if (c == '!') { running = false; continue; }
    if (c == '~') { running = true; continue; }

    if (c == '\n' || c == '\r') {
      if (cmdLen > 0) {
        cmd[cmdLen] = 0;
        processCmd();
        cmdLen = 0;
      }
    } else if (cmdLen < 31) {
      cmd[cmdLen++] = c;
    }
  }

  if (running) processMovement();
}

void processCmd() {
  if (cmd[0] == '$') {
    processSetting();
  } else {
    parseGCode();
  }
  Serial.println(F("ok"));
}

void processSetting() {
  if (strstr(cmd, "$$")) {
    Serial.print(F("$0=")); Serial.println(STEPS_MM_X, 2);
    Serial.print(F("$1=")); Serial.println(STEPS_MM_Y, 2);
    Serial.println(F("$110=500.0"));
    Serial.println(F("$111=500.0"));
    Serial.println(F("$20=1"));
  }
}

void parseGCode() {
  float x = parseNumber('X', 0);
  float y = parseNumber('Y', 0);
  float f = parseNumber('F', feedrate);

  if (strstr(cmd, "G90")) absoluteMode = true;
  if (strstr(cmd, "G91")) absoluteMode = false;

  if (strstr(cmd, "G0") || strstr(cmd, "G1")) {
    targetX = absoluteMode ? x : posX + x;
    targetY = absoluteMode ? y : posY + y;
    feedrate = f;
    running = true;
  }

  if (strstr(cmd, "M3")) servoZ.write(30);
  if (strstr(cmd, "M5")) servoZ.write(90);
  if (strstr(cmd, "G28")) {
    targetX = 0;
    targetY = 0;
    running = true;
  }
}

void processMovement() {
  float dx = targetX - posX;
  float dy = targetY - posY;

  if (abs(dx) < 0.01 && abs(dy) < 0.01) {
    running = false;
    return;
  }

  posX = targetX;
  posY = targetY;
  running = false;
}

float parseNumber(char code, float def) {
  char* p = strchr(cmd, code);
  if (!p) return def;
  return atof(p + 1);
}

void reportStatus() {
  Serial.print(F("<"));
  Serial.print(running ? F("Run") : F("Idle"));
  Serial.print(F("|MPos:"));
  Serial.print(posX, 2);
  Serial.print(F(","));
  Serial.print(posY, 2);
  Serial.print(F(","));
  Serial.print(posZ, 2);
  Serial.println(F(">"));
}
