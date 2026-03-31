/*
=====================================
GRBL-LIKE FIRMWARE para Motor Shield L293D
Implementación de protocolo GRBL simplificado
=====================================
✅ Compatible con GRBL senders (UGS, bCNC, etc)
✅ Comandos $ de configuración
✅ Reporte de estado en tiempo real
✅ Buffer de comandos circular
✅ Soft limits
✅ Homing cycle (sin endstops HW)
⚠️ Limitado por hardware L293D
*/

#include <AFMotor.h>
#include <Servo.h>
#include <EEPROM.h>

// ===== VERSIÓN GRBL =====
#define GRBL_VERSION "1.1f"
#define GRBL_VERSION_BUILD "20250329"

// ===== CONFIGURACIÓN HARDWARE =====
#define STEPS_PER_REV 20
#define SCREW_PITCH 0.508
#define STEPS_PER_MM 39.37

#define X_MAX_TRAVEL 40.0
#define Y_MAX_TRAVEL 40.0
#define Z_MAX_TRAVEL 20.0

#define DEFAULT_X_STEPS_PER_MM 39.37
#define DEFAULT_Y_STEPS_PER_MM 39.37
#define DEFAULT_Z_STEPS_PER_MM 100.0

#define DEFAULT_X_MAX_RATE 500.0  // mm/min
#define DEFAULT_Y_MAX_RATE 500.0
#define DEFAULT_Z_MAX_RATE 300.0

#define DEFAULT_ACCELERATION 50.0  // mm/sec^2
#define DEFAULT_JUNCTION_DEVIATION 0.01

#define SERVO_PIN 10
#define SERVO_UP 50
#define SERVO_DOWN 30

// ===== ESTADOS GRBL =====
enum State {
  STATE_IDLE = 0,
  STATE_RUN,
  STATE_HOLD,
  STATE_HOMING,
  STATE_ALARM,
  STATE_CHECK
};

// ===== VARIABLES GLOBALES =====
AF_Stepper motorX(STEPS_PER_REV, 1);
AF_Stepper motorY(STEPS_PER_REV, 2);
Servo servoZ;

State machineState = STATE_IDLE;

float posX = 0.0, posY = 0.0, posZ = 0.0;
float wco_x = 0.0, wco_y = 0.0, wco_z = 0.0; // Work coordinate offset

float settings_steps_per_mm[3];
float settings_max_rate[3];
float settings_acceleration;

bool absoluteMode = true;
bool inchesMode = false;
float feedrate = 100.0;

// Buffer circular de comandos
#define BLOCK_BUFFER_SIZE 16
char lineBuffer[BLOCK_BUFFER_SIZE][80];
int bufferHead = 0;
int bufferTail = 0;

// Buffer serial
char serialBuffer[128];
int serialIndex = 0;

uint32_t lastStatusReport = 0;
uint32_t statusReportInterval = 200; // ms

bool softLimitsEnabled = true;
bool hardLimitsEnabled = false;

// ===== EEPROM ADDRESSES =====
#define EEPROM_ADDR_SETTINGS 0
#define EEPROM_ADDR_WCO 100

// ===== SETUP =====
void setup() {
  Serial.begin(115200);
  
  // Cargar settings desde EEPROM
  loadSettings();
  
  // Configurar motores
  motorX.setSpeed(60);
  motorY.setSpeed(60);
  
  // Servo
  servoZ.attach(SERVO_PIN);
  servoZ.write(SERVO_UP);
  
  // Mensaje de bienvenida GRBL
  delay(500);
  Serial.println();
  printWelcome();
  
  machineState = STATE_IDLE;
}

// ===== LOOP PRINCIPAL =====
void loop() {
  // Leer comandos seriales
  readSerial();
  
  // Procesar buffer de comandos
  if (machineState == STATE_RUN && bufferTail != bufferHead) {
    processBlock();
  }
  
  // Reporte de estado periódico
  if (millis() - lastStatusReport > statusReportInterval) {
    if (Serial.available() == 0) { // Solo si no hay datos entrantes
      reportStatus();
      lastStatusReport = millis();
    }
  }
}

// ===== LECTURA SERIAL =====
void readSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    // Real-time commands (no requieren '\n')
    if (c == '?') {
      reportStatus();
      continue;
    }
    else if (c == '!') {
      feedHold();
      continue;
    }
    else if (c == '~') {
      cycleStart();
      continue;
    }
    else if (c == 0x18) { // Ctrl-X
      softReset();
      continue;
    }
    
    // Comandos normales
    if (c == '\n' || c == '\r') {
      if (serialIndex > 0) {
        serialBuffer[serialIndex] = '\0';
        processCommand(serialBuffer);
        serialIndex = 0;
      }
    }
    else if (serialIndex < 127) {
      serialBuffer[serialIndex++] = c;
    }
  }
}

// ===== PROCESAMIENTO DE COMANDOS =====
void processCommand(char* line) {
  // Ignorar espacios y comentarios
  while (*line == ' ' || *line == '\t') line++;
  
  if (*line == '\0' || *line == ';' || *line == '(') {
    Serial.println(F("ok"));
    return;
  }
  
  // Comandos de sistema ($)
  if (*line == '$') {
    processSystemCommand(line + 1);
    return;
  }
  
  // Comandos G-code
  if (machineState == STATE_ALARM) {
    Serial.println(F("error:8")); // Alarm lock
    return;
  }
  
  // Agregar al buffer
  if (isBufferFull()) {
    Serial.println(F("error:9")); // Buffer overflow
    return;
  }
  
  strcpy(lineBuffer[bufferHead], line);
  bufferHead = (bufferHead + 1) % BLOCK_BUFFER_SIZE;
  
  if (machineState == STATE_IDLE) {
    machineState = STATE_RUN;
  }
  
  Serial.println(F("ok"));
}

// ===== COMANDOS DE SISTEMA =====
void processSystemCommand(char* cmd) {
  if (*cmd == '\0') {
    // $ solo - mostrar ayuda
    printHelp();
  }
  else if (*cmd == '$') {
    // $$ - mostrar settings
    printSettings();
  }
  else if (*cmd == '#') {
    // $# - mostrar coordinate offsets
    printCoordinateOffsets();
  }
  else if (*cmd == 'G') {
    // $G - mostrar parser state
    printParserState();
  }
  else if (*cmd == 'I') {
    // $I - build info
    printBuildInfo();
  }
  else if (*cmd == 'N') {
    // $N - startup blocks
    Serial.println(F("$N0="));
    Serial.println(F("$N1="));
    Serial.println(F("ok"));
  }
  else if (*cmd == 'X') {
    // $X - unlock (kill alarm)
    if (machineState == STATE_ALARM) {
      machineState = STATE_IDLE;
      Serial.println(F("[MSG:Caution: Unlocked]"));
    }
    Serial.println(F("ok"));
  }
  else if (*cmd == 'H') {
    // $H - run homing cycle
    runHomingCycle();
  }
  else if (isdigit(*cmd)) {
    // $N=val - set setting
    setSetting(cmd);
  }
  else {
    Serial.println(F("error:3")); // Invalid statement
  }
}

// ===== PROCESAMIENTO DE BLOQUE G-CODE =====
void processBlock() {
  char* block = lineBuffer[bufferTail];
  bufferTail = (bufferTail + 1) % BLOCK_BUFFER_SIZE;
  
  // Parser básico de G-code
  float x = parseValue(block, 'X', absoluteMode ? posX : 0);
  float y = parseValue(block, 'Y', absoluteMode ? posY : 0);
  float z = parseValue(block, 'Z', posZ);
  float f = parseValue(block, 'F', feedrate);
  
  if (!absoluteMode) {
    x += posX;
    y += posY;
  }
  
  // Convertir pulgadas a mm si es necesario
  if (inchesMode) {
    x *= 25.4;
    y *= 25.4;
    z *= 25.4;
  }
  
  // Verificar soft limits
  if (softLimitsEnabled) {
    if (x < 0 || x > X_MAX_TRAVEL ||
        y < 0 || y > Y_MAX_TRAVEL ||
        z < 0 || z > Z_MAX_TRAVEL) {
      machineState = STATE_ALARM;
      Serial.println(F("ALARM:2")); // Soft limit
      return;
    }
  }
  
  // Ejecutar movimiento
  if (strstr(block, "G0") || strstr(block, "G1")) {
    feedrate = f;
    moveTo(x, y, z);
  }
  else if (strstr(block, "G4")) {
    // Dwell
    float p = parseValue(block, 'P', 0);
    delay((long)(p * 1000));
  }
  else if (strstr(block, "G20")) {
    inchesMode = true;
  }
  else if (strstr(block, "G21")) {
    inchesMode = false;
  }
  else if (strstr(block, "G28")) {
    moveTo(0, 0, 0);
  }
  else if (strstr(block, "G90")) {
    absoluteMode = true;
  }
  else if (strstr(block, "G91")) {
    absoluteMode = false;
  }
  else if (strstr(block, "G92")) {
    // Set position
    posX = x;
    posY = y;
    posZ = z;
  }
  else if (strstr(block, "M3")) {
    // Spindle CW / Pen down
    servoZ.write(SERVO_DOWN);
    delay(300);
  }
  else if (strstr(block, "M5")) {
    // Spindle off / Pen up
    servoZ.write(SERVO_UP);
    delay(300);
  }
  
  // Volver a IDLE si buffer vacío
  if (bufferTail == bufferHead) {
    machineState = STATE_IDLE;
  }
}

// ===== MOVIMIENTO =====
void moveTo(float targetX, float targetY, float targetZ) {
  float dx = targetX - posX;
  float dy = targetY - posY;
  
  long stepsX = (long)(dx * settings_steps_per_mm[0]);
  long stepsY = (long)(dy * settings_steps_per_mm[1]);
  
  long absX = abs(stepsX);
  long absY = abs(stepsY);
  int dirX = (stepsX > 0) ? FORWARD : BACKWARD;
  int dirY = (stepsY > 0) ? FORWARD : BACKWARD;
  
  if (absX == 0 && absY == 0) return;
  
  // Calcular delay
  float distance = sqrt(dx*dx + dy*dy);
  long totalSteps = max(absX, absY);
  long stepDelay = (long)(distance * 60000000.0 / (feedrate * totalSteps));
  stepDelay = constrain(stepDelay, 500, 10000);
  
  // Bresenham
  if (absX >= absY) {
    long error = 0;
    for (long i = 0; i < absX && machineState == STATE_RUN; i++) {
      motorX.step(1, dirX, MICROSTEP);
      error += absY;
      if (error >= absX) {
        error -= absX;
        motorY.step(1, dirY, MICROSTEP);
      }
      delayMicroseconds(stepDelay);
    }
  } else {
    long error = 0;
    for (long i = 0; i < absY && machineState == STATE_RUN; i++) {
      motorY.step(1, dirY, MICROSTEP);
      error += absX;
      if (error >= absY) {
        error -= absY;
        motorX.step(1, dirX, MICROSTEP);
      }
      delayMicroseconds(stepDelay);
    }
  }
  
  posX = targetX;
  posY = targetY;
  posZ = targetZ;
}

// ===== REPORTES =====
void reportStatus() {
  // Formato GRBL: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
  Serial.print(F("<"));
  
  switch(machineState) {
    case STATE_IDLE: Serial.print(F("Idle")); break;
    case STATE_RUN: Serial.print(F("Run")); break;
    case STATE_HOLD: Serial.print(F("Hold")); break;
    case STATE_HOMING: Serial.print(F("Home")); break;
    case STATE_ALARM: Serial.print(F("Alarm")); break;
    case STATE_CHECK: Serial.print(F("Check")); break;
  }
  
  Serial.print(F("|MPos:"));
  Serial.print(posX, 3);
  Serial.print(F(","));
  Serial.print(posY, 3);
  Serial.print(F(","));
  Serial.print(posZ, 3);
  
  Serial.print(F("|WPos:"));
  Serial.print(posX - wco_x, 3);
  Serial.print(F(","));
  Serial.print(posY - wco_y, 3);
  Serial.print(F(","));
  Serial.print(posZ - wco_z, 3);
  
  Serial.print(F("|FS:"));
  Serial.print((int)feedrate);
  Serial.print(F(",0"));
  
  Serial.println(F(">"));
}

void printWelcome() {
  Serial.println(F("Grbl " GRBL_VERSION " ['$' for help]"));
  Serial.println(F("[MSG:'$H'|'$X' to unlock]"));
}

void printHelp() {
  Serial.println(F("[HLP:$$ $# $G $I $N $x=val $Nx=line $J=line $SLP $C $X $H ~ ! ? ctrl-x]"));
  Serial.println(F("ok"));
}

void printSettings() {
  Serial.print(F("$0=")); Serial.println(settings_steps_per_mm[0], 3);
  Serial.print(F("$1=")); Serial.println(settings_steps_per_mm[1], 3);
  Serial.print(F("$2=")); Serial.println(settings_steps_per_mm[2], 3);
  Serial.print(F("$110=")); Serial.println(settings_max_rate[0], 3);
  Serial.print(F("$111=")); Serial.println(settings_max_rate[1], 3);
  Serial.print(F("$112=")); Serial.println(settings_max_rate[2], 3);
  Serial.print(F("$120=")); Serial.println(settings_acceleration, 3);
  Serial.print(F("$20=")); Serial.println(softLimitsEnabled ? 1 : 0);
  Serial.print(F("$21=")); Serial.println(hardLimitsEnabled ? 1 : 0);
  Serial.println(F("ok"));
}

void printCoordinateOffsets() {
  Serial.print(F("[G54:"));
  Serial.print(wco_x, 3);
  Serial.print(F(","));
  Serial.print(wco_y, 3);
  Serial.print(F(","));
  Serial.print(wco_z, 3);
  Serial.println(F("]"));
  Serial.println(F("ok"));
}

void printParserState() {
  Serial.print(F("[GC:G0 G54 G17 G21 G"));
  Serial.print(absoluteMode ? "90" : "91");
  Serial.print(F(" G94 M5 M9 T0 F"));
  Serial.print(feedrate, 0);
  Serial.println(F(" S0]"));
  Serial.println(F("ok"));
}

void printBuildInfo() {
  Serial.println(F("[VER:" GRBL_VERSION "." GRBL_VERSION_BUILD ":L293D Plotter]"));
  Serial.println(F("[OPT:V,15,128]"));
  Serial.println(F("ok"));
}

// ===== FUNCIONES AUXILIARES =====
float parseValue(char* block, char code, float defaultVal) {
  char* ptr = strchr(block, code);
  if (ptr) {
    return atof(ptr + 1);
  }
  return defaultVal;
}

bool isBufferFull() {
  return ((bufferHead + 1) % BLOCK_BUFFER_SIZE) == bufferTail;
}

void feedHold() {
  if (machineState == STATE_RUN) {
    machineState = STATE_HOLD;
    Serial.println(F("[MSG:Feed hold]"));
  }
}

void cycleStart() {
  if (machineState == STATE_HOLD) {
    machineState = STATE_RUN;
    Serial.println(F("[MSG:Cycle start]"));
  }
}

void softReset() {
  machineState = STATE_IDLE;
  bufferHead = 0;
  bufferTail = 0;
  serialIndex = 0;
  Serial.println();
  printWelcome();
}

void runHomingCycle() {
  machineState = STATE_HOMING;
  Serial.println(F("[MSG:Homing cycle started]"));
  
  // Simular homing (sin endstops físicos)
  moveTo(0, 0, 0);
  
  posX = 0;
  posY = 0;
  posZ = 0;
  
  machineState = STATE_IDLE;
  Serial.println(F("[MSG:Homing cycle complete]"));
  Serial.println(F("ok"));
}

void setSetting(char* cmd) {
  int setting = atoi(cmd);
  char* ptr = strchr(cmd, '=');
  
  if (!ptr) {
    Serial.println(F("error:3"));
    return;
  }
  
  float value = atof(ptr + 1);
  
  switch(setting) {
    case 0: settings_steps_per_mm[0] = value; break;
    case 1: settings_steps_per_mm[1] = value; break;
    case 2: settings_steps_per_mm[2] = value; break;
    case 110: settings_max_rate[0] = value; break;
    case 111: settings_max_rate[1] = value; break;
    case 112: settings_max_rate[2] = value; break;
    case 120: settings_acceleration = value; break;
    case 20: softLimitsEnabled = (value > 0); break;
    case 21: hardLimitsEnabled = (value > 0); break;
    default:
      Serial.println(F("error:3"));
      return;
  }
  
  saveSettings();
  Serial.println(F("ok"));
}

// ===== EEPROM =====
void loadSettings() {
  // Leer o inicializar con valores por defecto
  EEPROM.get(EEPROM_ADDR_SETTINGS, settings_steps_per_mm[0]);
  
  if (isnan(settings_steps_per_mm[0]) || settings_steps_per_mm[0] <= 0) {
    // Primera vez - cargar defaults
    settings_steps_per_mm[0] = DEFAULT_X_STEPS_PER_MM;
    settings_steps_per_mm[1] = DEFAULT_Y_STEPS_PER_MM;
    settings_steps_per_mm[2] = DEFAULT_Z_STEPS_PER_MM;
    settings_max_rate[0] = DEFAULT_X_MAX_RATE;
    settings_max_rate[1] = DEFAULT_Y_MAX_RATE;
    settings_max_rate[2] = DEFAULT_Z_MAX_RATE;
    settings_acceleration = DEFAULT_ACCELERATION;
    saveSettings();
  } else {
    EEPROM.get(EEPROM_ADDR_SETTINGS + 4, settings_steps_per_mm[1]);
    EEPROM.get(EEPROM_ADDR_SETTINGS + 8, settings_steps_per_mm[2]);
    EEPROM.get(EEPROM_ADDR_SETTINGS + 12, settings_max_rate[0]);
    EEPROM.get(EEPROM_ADDR_SETTINGS + 16, settings_max_rate[1]);
    EEPROM.get(EEPROM_ADDR_SETTINGS + 20, settings_max_rate[2]);
    EEPROM.get(EEPROM_ADDR_SETTINGS + 24, settings_acceleration);
  }
}

void saveSettings() {
  EEPROM.put(EEPROM_ADDR_SETTINGS, settings_steps_per_mm[0]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 4, settings_steps_per_mm[1]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 8, settings_steps_per_mm[2]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 12, settings_max_rate[0]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 16, settings_max_rate[1]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 20, settings_max_rate[2]);
  EEPROM.put(EEPROM_ADDR_SETTINGS + 24, settings_acceleration);
}

/*
=====================================
COMANDOS GRBL IMPLEMENTADOS
=====================================

REAL-TIME COMMANDS (no requieren '\n'):
?     - Reporte de estado
!     - Feed hold (pausar)
~     - Cycle start (reanudar)
Ctrl-X - Soft reset

SYSTEM COMMANDS:
$     - Ver ayuda
$$    - Ver configuración
$#    - Ver offsets
$G    - Ver estado parser
$I    - Build info
$H    - Homing cycle
$X    - Desbloquear alarm
$N=val - Cambiar setting

G-CODE:
G0/G1 - Movimiento lineal
G4    - Dwell (pausa)
G20/G21 - Pulgadas/milímetros
G28   - Ir a home
G90/G91 - Absoluto/relativo
G92   - Set position
M3    - Spindle CW / Pen down
M5    - Spindle off / Pen up

SETTINGS ($N):
$0    - Steps/mm eje X
$1    - Steps/mm eje Y
$2    - Steps/mm eje Z
$110  - Max rate X (mm/min)
$111  - Max rate Y
$112  - Max rate Z
$120  - Acceleration (mm/sec^2)
$20   - Soft limits (0/1)
$21   - Hard limits (0/1)

USO CON SENDERS:
- Universal Gcode Sender (UGS)
- bCNC
- Candle
- GrblController
- LaserWeb

LIMITACIONES vs GRBL REAL:
❌ Sin aceleración real (trapezoidal)
❌ Sin lookahead
❌ Sin arcos G2/G3
❌ Sin backlash compensation
❌ Sin tool length offset
❌ Sin coolant control
❌ Movimientos más lentos (L293D)
*/