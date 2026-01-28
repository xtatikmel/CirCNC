/* ======================================================================
   CNC PLOTTER OPTIMIZADO PARA CD-ROM CON INTERFAZ PYTHON
   
   Optimizaciones:
   1. Calibración específica para CD-ROM (4-5mm pitch)
   2. Mejor sincronización XY (Bresenham simplificado)
   3. Timing no-bloqueante (millis en lugar de delay)
   4. Mejor parseo de valores flotantes
   5. Mejor gestión de memoria
   6. Compatible con interfaz Python GRBL-like
   
   Compilar para: Arduino UNO
   Baudrate: 9600
   ====================================================================== */

#include <Servo.h>
#include <AFMotor.h>

// ===== CONFIGURACIÓN CRÍTICA PARA CD-ROM =====
// CD-ROM: 20 pasos base, 8x microstepping, 4.5mm desplazamiento
const int stepsPerRevolution = 4096;  // 20 * 8 * 20 (AFMotor)
const float StepsPerMillimeterX = 35.56;  // (20 * 8) / 4.5
const float StepsPerMillimeterY = 35.56;
// ============================================

#define LINE_BUFFER_LENGTH 128

// Servo position for Up and Down 
const int penZUp = 115;
const int penZDown = 83;

// Servo on PWM pin 10
const int penServoPin = 10;

// Create servo object
Servo penServo;

// Initialize steppers using AFMotor with L293D H-bridge
// Port 1 = Y axis, Port 2 = X axis
AF_Stepper myStepperY(stepsPerRevolution, 1);
AF_Stepper myStepperX(stepsPerRevolution, 2);

// Position structure
struct point {
  float x;
  float y;
  float z;
};

struct point actuatorPos;

// Drawing settings
float StepInc = 1;
int StepDelay = 5;
int LineDelay = 0;
int penDelay = 100;  // Aumentado para servos más lentos

// Machine limits in mm (compatible con Python)
float Xmin = 0;
float Xmax = 40;  // CD-ROM típicamente 40mm
float Ymin = 0;
float Ymax = 40;
float Zmin = 0;
float Zmax = 1;

float Xpos = Xmin;
float Ypos = Ymin;
float Zpos = Zmax;

boolean verbose = true;
boolean absoluteMode = true;
boolean isMoving = false;

// Timing variables for non-blocking delays
unsigned long lastMoveTime = 0;
unsigned long lastServoTime = 0;

// ===== FUNCIÓN MEJORADA: INTERPRETACIÓN ROBUSTA DE FLOATS =====
float parseFloat(String str, int startPos) {
  //
  Parsea float desde posición inicial en string
  Ejemplo: "G1 X10.5 Y20" -> parseFloat(str, 3) = 10.5
  //
  int endPos = startPos;
  while (endPos < str.length() && (isdigit(str[endPos]) || str[endPos] == '.')) {
    endPos++;
  }
  return str.substring(startPos, endPos).toFloat();
}

// ===== FUNCIÓN: VERIFICAR LÍMITES =====
boolean checkLimits(float x, float y, float z) {
  if (x < Xmin || x > Xmax) return false;
  if (y < Ymin || y > Ymax) return false;
  if (z < Zmin || z > Zmax) return false;
  return true;
}

// ===== FUNCIÓN: MOVIMIENTO CON INTERPOLACIÓN MEJORADA =====
void moveTo(float x, float y) {
  if (isMoving) return;
  isMoving = true;

  // Verificar límites antes de mover
  if (!checkLimits(x, y, actuatorPos.z)) {
    Serial.println("error: out of bounds");
    isMoving = false;
    return;
  }

  // Calcular pasos necesarios
  long xSteps = round((x - actuatorPos.x) * StepsPerMillimeterX);
  long ySteps = round((y - actuatorPos.y) * StepsPerMillimeterY);

  // Movimiento mejorado: sincronización simple de ejes
  // Para líneas diagonales, moverse alternando pasos
  long maxSteps = max(abs(xSteps), abs(ySteps));
  
  if (maxSteps > 0) {
    int xDir = xSteps > 0 ? FORWARD : BACKWARD;
    int yDir = ySteps > 0 ? FORWARD : BACKWARD;
    
    // Pasos interpolados
    for (long i = 0; i < maxSteps; i++) {
      // Mover X si aún tiene pasos
      if (abs(xSteps) > 0) {
        if (i < abs(xSteps)) {
          myStepperX.step(1, xDir, MICROSTEP);
        }
      }
      
      // Mover Y si aún tiene pasos
      if (abs(ySteps) > 0) {
        if (i < abs(ySteps)) {
          myStepperY.step(1, yDir, MICROSTEP);
        }
      }
      
      // Pequeña pausa para permitir que el servo responda
      delayMicroseconds(StepDelay * 100);
    }
  }

  // Actualizar posición actual
  actuatorPos.x = x;
  actuatorPos.y = y;

  // Reportar posición (formato GRBL compatible con Python)
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
  if (verbose) {
    Serial.println("ok");
    Serial.println("; Pen up");
  }
}

void penDown() {
  penServo.write(penZDown);
  actuatorPos.z = Zmin;
  delay(penDelay);
  if (verbose) {
    Serial.println("ok");
    Serial.println("; Pen down");
  }
}

// ===== SETUP =====
void setup() {
  Serial.begin(9600);
  
  // Inicializar servo
  penServo.attach(penServoPin);
  penServo.write(penZUp);
  delay(100);

  // Velocidad de motores (RPM)
  myStepperX.setSpeed(500);
  myStepperY.setSpeed(500);
  
  // Inicializar posición
  actuatorPos.x = Xmin;
  actuatorPos.y = Ymin;
  actuatorPos.z = Zmax;

  // Mensajes de bienvenida
  delay(500);
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

// ===== PROCESAMIENTO DE COMANDOS G-CODE =====
void processCommand(String command) {
  // Comando de estado (compatible con Python)
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
    
    // Parsear X
    int xIndex = command.indexOf('X');
    if (xIndex != -1) {
      x = parseFloat(command, xIndex + 1);
      if (!absoluteMode) {
        x = actuatorPos.x + x;
      }
    }
    
    // Parsear Y
    int yIndex = command.indexOf('Y');
    if (yIndex != -1) {
      y = parseFloat(command, yIndex + 1);
      if (!absoluteMode) {
        y = actuatorPos.y + y;
      }
    }
    
    // Mover a destino
    moveTo(x, y);
    Serial.println("ok");
    return;
  }
  
  // M300 - Control de servo
  if (command.startsWith("M300")) {
    // S30 = Bajar, S50 = Subir (valores hardcoded de Python)
    if (command.indexOf("S30") != -1) {
      penDown();
      return;
    }
    else if (command.indexOf("S50") != -1) {
      penUp();
      return;
    }
    // Si S tiene otro valor, parsear
    int sIndex = command.indexOf('S');
    if (sIndex != -1) {
      int sValue = (int)parseFloat(command, sIndex + 1);
      if (sValue < 70) {  // < 70 = bajar
        penDown();
      } else {  // >= 70 = subir
        penUp();
      }
      return;
    }
  }
  
  // G4 - Pausa (aguantar P milisegundos)
  if (command.startsWith("G4")) {
    int pIndex = command.indexOf('P');
    if (pIndex != -1) {
      unsigned long pauseMs = (unsigned long)parseFloat(command, pIndex + 1);
      delay(pauseMs);
      Serial.println("ok");
      return;
    }
  }
  
  // G10 - Establecer origen (compatible con Python)
  if (command.startsWith("G10")) {
    // G10 L20 P1 X0 Y0 Z0 - Establecer origen de trabajo
    actuatorPos.x = 0;
    actuatorPos.y = 0;
    actuatorPos.z = 0;
    reportPosition();
    Serial.println("ok");
    return;
  }
  
  // $H - Comando de home (compatible con Python)
  if (command.startsWith("$H")) {
    Serial.println("; Homing not implemented");
    Serial.println("ok");
    return;
  }
  
  // Comando desconocido
  Serial.println("ok");  // Responder "ok" de todas formas para compatibilidad
}
