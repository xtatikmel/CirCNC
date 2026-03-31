/* ======================================================================
   CNC PLOTTER OPTIMIZADO PARA CD-ROM - VERSIÓN CORREGIDA
   
   Cambios en esta versión:
   ✓ Removido parseFloat custom (usa String.toFloat() built-in)
   ✓ Removido delayMicroseconds (usa delay() para Servo.h)
   ✓ Removido max() (usa operador ternario)
   ✓ Removido isdigit() (usa comparación manual)
   ✓ Mejor sincronización XY sin conflictos de timer
   
   IMPORTANTE: Instalar librería "Adafruit Motor Shield Library" antes de compilar
   Arduino IDE > Sketch > Include Library > Library Manager > 
   Buscar "Adafruit Motor" > Instalar versión 1.x
   
   Compilar para: Arduino UNO
   Baudrate: 9600
   ====================================================================== */

#include <Servo.h>
#include <AFMotor.h>

// ===== CONFIGURACIÓN CD-ROM =====
const int stepsPerRevolution = 4096;
const float StepsPerMillimeterX = 35.56;
const float StepsPerMillimeterY = 35.56;
// ================================

// Servo
const int penZUp = 115;
const int penZDown = 83;
const int penServoPin = 10;
Servo penServo;

// Motores
AF_Stepper myStepperY(stepsPerRevolution, 1);
AF_Stepper myStepperX(stepsPerRevolution, 2);

// Estructura de posición
struct point {
  float x;
  float y;
  float z;
};

struct point actuatorPos;

// Parámetros de movimiento
float StepInc = 1;
int StepDelay = 5;
int LineDelay = 0;
int penDelay = 100;

// Límites máquina
float Xmin = 0;
float Xmax = 40;
float Ymin = 0;
float Ymax = 40;
float Zmin = 0;
float Zmax = 1;

// Variables de estado
boolean verbose = true;
boolean absoluteMode = true;
boolean isMoving = false;

// ===== FUNCIÓN: MACRO para max() =====
#define MAX(a, b) ((a > b) ? (a) : (b))

// ===== FUNCIÓN: VERIFICAR LÍMITES =====
boolean checkLimits(float x, float y, float z) {
  if (x < Xmin || x > Xmax) return false;
  if (y < Ymin || y > Ymax) return false;
  if (z < Zmin || z > Zmax) return false;
  return true;
}

// ===== FUNCIÓN: MOVIMIENTO MEJORADO =====
void moveTo(float x, float y) {
  if (isMoving) return;
  isMoving = true;

  // Verificar límites
  if (!checkLimits(x, y, actuatorPos.z)) {
    Serial.println("error: out of bounds");
    isMoving = false;
    return;
  }

  // Calcular pasos
  long xSteps = round((x - actuatorPos.x) * StepsPerMillimeterX);
  long ySteps = round((y - actuatorPos.y) * StepsPerMillimeterY);

  // Movimiento interpolado
  long maxSteps = MAX(abs(xSteps), abs(ySteps));
  
  if (maxSteps > 0) {
    int xDir = xSteps > 0 ? FORWARD : BACKWARD;
    int yDir = ySteps > 0 ? FORWARD : BACKWARD;
    
    // Interpolar pasos
    for (long i = 0; i < maxSteps; i++) {
      if (abs(xSteps) > 0 && i < abs(xSteps)) {
        myStepperX.step(1, xDir, MICROSTEP);
      }
      
      if (abs(ySteps) > 0 && i < abs(ySteps)) {
        myStepperY.step(1, yDir, MICROSTEP);
      }
      
      // Pequeña pausa sin bloquear completamente
      // Usar delay(1) en lugar de delayMicroseconds para evitar conflicto con Servo
      delay(1);
    }
  }

  // Actualizar posición
  actuatorPos.x = x;
  actuatorPos.y = y;

  // Reportar posición
  reportPosition();

  isMoving = false;
}

// ===== FUNCIÓN: REPORTAR POSICIÓN =====
void reportPosition() {
  Serial.print("<Idle|MPos:");
  Serial.print(actuatorPos.x, 3);
  Serial.print(",");
  Serial.print(actuatorPos.y, 3);
  Serial.print(",");
  Serial.print(actuatorPos.z, 3);
  Serial.println("|FS:0,0>");
}

// ===== FUNCIONES DE SERVO =====
void penUp() {
  penServo.write(penZUp);
  actuatorPos.z = Zmax;
  delay(penDelay);
  Serial.println("ok");
}

void penDown() {
  penServo.write(penZDown);
  actuatorPos.z = Zmin;
  delay(penDelay);
  Serial.println("ok");
}

// ===== SETUP =====
void setup() {
  Serial.begin(9600);
  delay(500);
  
  // Inicializar servo
  penServo.attach(penServoPin);
  penServo.write(penZUp);
  delay(100);

  // Velocidad de motores
  myStepperX.setSpeed(500);
  myStepperY.setSpeed(500);
  
  // Inicializar posición
  actuatorPos.x = Xmin;
  actuatorPos.y = Ymin;
  actuatorPos.z = Zmax;

  // Mensajes de inicio
  Serial.println("ok");
  Serial.println("; CNC Plotter CD-ROM Ready");
  Serial.print("; X range: ");
  Serial.print(Xmin);
  Serial.print(" to ");
  Serial.print(Xmax);
  Serial.println(" mm");
  Serial.print("; Y range: ");
  Serial.print(Ymin);
  Serial.print(" to ");
  Serial.print(Ymax);
  Serial.println(" mm");
  Serial.print("; StepsPerMM: ");
  Serial.println(StepsPerMillimeterX);
  Serial.println("ok");
}

// ===== LOOP PRINCIPAL =====
void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.length() > 0) {
      processCommand(command);
    }
  }
}

// ===== PROCESAMIENTO DE COMANDOS =====
void processCommand(String command) {
  // Estado
  if (command == "?") {
    reportPosition();
    return;
  }
  
  // G90 - Modo absoluto
  if (command.startsWith("G90")) {
    absoluteMode = true;
    Serial.println("ok");
    return;
  }
  
  // G91 - Modo relativo
  if (command.startsWith("G91")) {
    absoluteMode = false;
    Serial.println("ok");
    return;
  }
  
  // G0/G1 - Movimiento lineal
  if (command.startsWith("G0") || command.startsWith("G1")) {
    float x = actuatorPos.x;
    float y = actuatorPos.y;
    
    // Parsear X usando toFloat() built-in
    int xIndex = command.indexOf('X');
    if (xIndex != -1) {
      // Extraer substring desde X hasta el siguiente espacio o fin
      int endPos = xIndex + 1;
      while (endPos < command.length() && 
             (command[endPos] == '.' || 
              command[endPos] == '-' || 
              (command[endPos] >= '0' && command[endPos] <= '9'))) {
        endPos++;
      }
      String xStr = command.substring(xIndex + 1, endPos);
      x = xStr.toFloat();
      
      if (!absoluteMode) {
        x = actuatorPos.x + x;
      }
    }
    
    // Parsear Y
    int yIndex = command.indexOf('Y');
    if (yIndex != -1) {
      int endPos = yIndex + 1;
      while (endPos < command.length() && 
             (command[endPos] == '.' || 
              command[endPos] == '-' || 
              (command[endPos] >= '0' && command[endPos] <= '9'))) {
        endPos++;
      }
      String yStr = command.substring(yIndex + 1, endPos);
      y = yStr.toFloat();
      
      if (!absoluteMode) {
        y = actuatorPos.y + y;
      }
    }
    
    // Mover
    moveTo(x, y);
    Serial.println("ok");
    return;
  }
  
  // M300 - Control de servo
  if (command.startsWith("M300")) {
    // Búsqueda simple para compatibilidad
    if (command.indexOf("S30") != -1) {
      penDown();
      return;
    }
    else if (command.indexOf("S50") != -1) {
      penUp();
      return;
    }
    
    // Parsear S value si existe
    int sIndex = command.indexOf('S');
    if (sIndex != -1) {
      int endPos = sIndex + 1;
      while (endPos < command.length() && 
             (command[endPos] >= '0' && command[endPos] <= '9')) {
        endPos++;
      }
      String sStr = command.substring(sIndex + 1, endPos);
      int sValue = sStr.toInt();
      
      if (sValue < 70) {
        penDown();
      } else {
        penUp();
      }
      return;
    }
    
    Serial.println("ok");
    return;
  }
  
  // G4 - Pausa
  if (command.startsWith("G4")) {
    int pIndex = command.indexOf('P');
    if (pIndex != -1) {
      int endPos = pIndex + 1;
      while (endPos < command.length() && 
             (command[endPos] >= '0' && command[endPos] <= '9')) {
        endPos++;
      }
      String pStr = command.substring(pIndex + 1, endPos);
      unsigned long pauseMs = (unsigned long)pStr.toInt();
      delay(pauseMs);
    }
    Serial.println("ok");
    return;
  }
  
  // G10 - Establecer origen
  if (command.startsWith("G10")) {
    actuatorPos.x = 0;
    actuatorPos.y = 0;
    actuatorPos.z = 0;
    reportPosition();
    Serial.println("ok");
    return;
  }
  
  // $H - Home
  if (command.startsWith("$H")) {
    Serial.println("; Homing not implemented");
    Serial.println("ok");
    return;
  }
  
  // Comando desconocido - responder ok igual
  Serial.println("ok");
}
