/*
=====================================
CNC PLOTTER - OPTIMIZADO PARA PYTHON GUI
Motor Shield L293D + Motores 18° + Servo SG90
=====================================
✅ Compatible con interfaz Python
✅ Respuestas consistentes "ok"
✅ Reporte de posición formato GRBL
✅ Control paso a paso preciso
✅ Buffer optimizado para streaming
*/

#include <AFMotor.h>
#include <Servo.h>

// ===== CONFIGURACIÓN HARDWARE =====
#define STEPS_PER_REV 20        // 18° = 20 pasos/revolución
#define SCREW_PITCH 0.508       // 0.020" = 0.508mm
#define STEPS_PER_MM 39.37      // ~39.37 steps/mm

#define X_LIMIT_MM 40.0         // Límites según Python GUI
#define Y_LIMIT_MM 40.0
#define SERVO_UP 50
#define SERVO_DOWN 30
#define SERVO_PIN 10

// ===== MOTORES Y SERVO =====
AF_Stepper motorX(STEPS_PER_REV, 1);  // Puerto M1/M2
AF_Stepper motorY(STEPS_PER_REV, 2);  // Puerto M3/M4
Servo servoZ;

// ===== VARIABLES GLOBALES =====
float posX = 0.0, posY = 0.0, posZ = 1.0;
float feedrate = 1000.0;        // mm/min
bool absoluteMode = true;
bool motorsPowered = true;

// Buffer de comandos
const int MAX_BUF = 128;
char buffer[MAX_BUF];
int bufIndex = 0;

// ===== SETUP =====
void setup() {
  Serial.begin(9600);
  
  // Configurar velocidad motores
  motorX.setSpeed(80);  // RPM óptimo
  motorY.setSpeed(80);
  
  // Inicializar servo
  servoZ.attach(SERVO_PIN);
  servoZ.write(SERVO_UP);
  delay(500);
  
  // Mensaje de bienvenida (compatible con Python)
  Serial.println(F("CNC Plotter Ready"));
  Serial.println(F("ok"));
}

// ===== LOOP PRINCIPAL =====
void loop() {
  // Leer comandos desde Serial
  while (Serial.available() > 0) {
    char c = Serial.read();
    
    // Procesar al recibir nueva línea
    if (c == '\n' || c == '\r') {
      if (bufIndex > 0) {
        buffer[bufIndex] = '\0';
        processCommand();
        bufIndex = 0;
      }
    }
    // Agregar al buffer
    else if (bufIndex < MAX_BUF - 1) {
      buffer[bufIndex++] = c;
    }
  }
}

// ===== PROCESAMIENTO DE COMANDOS =====
void processCommand() {
  // Limpiar espacios iniciales
  char* cmd = buffer;
  while (*cmd == ' ') cmd++;
  
  // Ignorar líneas vacías o comentarios
  if (*cmd == '\0' || *cmd == ';' || *cmd == '(') {
    Serial.println(F("ok"));
    return;
  }
  
  // Convertir a mayúsculas para parseo
  String command = String(cmd);
  command.toUpperCase();
  command.trim();
  
  // ===== COMANDOS G =====
  if (command.startsWith("G")) {
    int gcode = parseNumber('G', -1);
    
    switch(gcode) {
      case 0:  // Movimiento rápido
      case 1:  // Movimiento lineal
        {
          float targetX = parseFloat('X', absoluteMode ? posX : 0);
          float targetY = parseFloat('Y', absoluteMode ? posY : 0);
          float targetZ = parseFloat('Z', posZ);
          float f = parseFloat('F', feedrate);
          
          // En modo relativo, sumar a posición actual
          if (!absoluteMode) {
            targetX += posX;
            targetY += posY;
            targetZ += posZ;
          }
          
          // Verificar límites
          if (checkLimits(targetX, targetY)) {
            feedrate = f;
            moveTo(targetX, targetY);
            
            // Mover Z si cambió
            if (targetZ != posZ) {
              moveZ(targetZ);
            }
          } else {
            Serial.println(F("error: Position out of bounds"));
            return;
          }
        }
        break;
        
      case 4:  // Dwell (pausa)
        {
          float pauseSec = parseFloat('P', 0);
          delay((long)(pauseSec * 1000));
        }
        break;
        
      case 28:  // Home
        moveTo(0, 0);
        moveZ(1.0);
        posX = 0;
        posY = 0;
        posZ = 1.0;
        break;
        
      case 90:  // Modo absoluto
        absoluteMode = true;
        break;
        
      case 91:  // Modo relativo
        absoluteMode = false;
        break;
        
      case 92:  // Establecer posición
        posX = parseFloat('X', posX);
        posY = parseFloat('Y', posY);
        posZ = parseFloat('Z', posZ);
        break;
    }
    
    Serial.println(F("ok"));
  }
  
  // ===== COMANDOS M =====
  else if (command.startsWith("M")) {
    int mcode = parseNumber('M', -1);
    
    switch(mcode) {
      case 3:    // Spindle ON / Pen DOWN
      case 300:  // Servo control
        {
          int servoPos = (int)parseFloat('S', -1);
          
          if (servoPos == 30 || servoPos < 40) {
            // Pen DOWN
            servoZ.write(SERVO_DOWN);
            posZ = 0.0;
            delay(300);
          } 
          else if (servoPos == 50 || servoPos > 40) {
            // Pen UP
            servoZ.write(SERVO_UP);
            posZ = 1.0;
            delay(300);
          }
          else if (servoPos >= 0 && servoPos <= 180) {
            // Posición específica
            servoZ.write(servoPos);
            delay(300);
          }
        }
        break;
        
      case 5:  // Spindle OFF / Pen UP
        servoZ.write(SERVO_UP);
        posZ = 1.0;
        delay(300);
        break;
        
      case 17:  // Enable motors
        motorsPowered = true;
        break;
        
      case 18:  // Disable motors
        motorX.release();
        motorY.release();
        motorsPowered = false;
        break;
        
      case 114:  // Report position
        reportPosition();
        break;
    }
    
    Serial.println(F("ok"));
  }
  
  // ===== COMANDO ? (Status) =====
  else if (command.startsWith("?")) {
    reportPosition();
    Serial.println(F("ok"));
  }
  
  // ===== OTROS COMANDOS =====
  else {
    Serial.println(F("ok"));
  }
}

// ===== PARSEO DE NÚMEROS =====
int parseNumber(char code, int defaultValue) {
  char* ptr = strchr(buffer, code);
  if (ptr) {
    return atoi(ptr + 1);
  }
  return defaultValue;
}

float parseFloat(char code, float defaultValue) {
  char* ptr = strchr(buffer, code);
  if (ptr) {
    return atof(ptr + 1);
  }
  return defaultValue;
}

// ===== VERIFICAR LÍMITES =====
bool checkLimits(float x, float y) {
  if (x < 0 || x > X_LIMIT_MM) return false;
  if (y < 0 || y > Y_LIMIT_MM) return false;
  return true;
}

// ===== MOVIMIENTO LINEAL CON BRESENHAM =====
void moveTo(float targetX, float targetY) {
  // Calcular diferencias
  float dx = targetX - posX;
  float dy = targetY - posY;
  
  // Convertir a pasos
  long stepsX = (long)(dx * STEPS_PER_MM);
  long stepsY = (long)(dy * STEPS_PER_MM);
  
  // Valores absolutos y dirección
  long absX = abs(stepsX);
  long absY = abs(stepsY);
  int dirX = (stepsX > 0) ? FORWARD : BACKWARD;
  int dirY = (stepsY > 0) ? FORWARD : BACKWARD;
  
  if (absX == 0 && absY == 0) return;
  
  // Calcular delay basado en feedrate
  // feedrate está en mm/min, necesitamos microsegundos/paso
  float distance = sqrt(dx*dx + dy*dy);
  long totalSteps = max(absX, absY);
  
  // delay (us) = (distancia_mm / pasos) * (60_000_000 us/min / feedrate_mm/min)
  long stepDelay = (long)(distance * 60000000.0 / (feedrate * totalSteps));
  
  // Limitar delay para evitar valores extremos
  stepDelay = constrain(stepDelay, 500, 10000);
  
  // Algoritmo de Bresenham para movimiento coordinado
  if (absX >= absY) {
    // Más pasos en X
    long error = 0;
    for (long i = 0; i < absX; i++) {
      motorX.step(1, dirX, MICROSTEP);
      error += absY;
      
      if (error >= absX) {
        error -= absX;
        motorY.step(1, dirY, MICROSTEP);
      }
      
      delayMicroseconds(stepDelay);
    }
  } else {
    // Más pasos en Y
    long error = 0;
    for (long i = 0; i < absY; i++) {
      motorY.step(1, dirY, MICROSTEP);
      error += absX;
      
      if (error >= absY) {
        error -= absY;
        motorX.step(1, dirX, MICROSTEP);
      }
      
      delayMicroseconds(stepDelay);
    }
  }
  
  // Actualizar posición
  posX = targetX;
  posY = targetY;
}

// ===== MOVIMIENTO Z (SERVO) =====
void moveZ(float targetZ) {
  if (targetZ >= 0 && targetZ <= 1) {
    int angle = (targetZ > 0.5) ? SERVO_UP : SERVO_DOWN;
    servoZ.write(angle);
    posZ = targetZ;
    delay(300);
  }
}

// ===== REPORTE DE POSICIÓN (FORMATO GRBL) =====
void reportPosition() {
  // Formato compatible con Python GUI
  Serial.print(F("<Idle|MPos:"));
  Serial.print(posX, 2);
  Serial.print(F(","));
  Serial.print(posY, 2);
  Serial.print(F(","));
  Serial.print(posZ, 2);
  Serial.println(F("|FS:0,0>"));
}

/*
=====================================
COMANDOS SOPORTADOS (PYTHON GUI)
=====================================

MOVIMIENTO:
G0/G1 X## Y## F## - Movimiento lineal
G4 P#             - Pausa (segundos)
G28               - Ir a origen (0,0)

MODOS:
G90               - Modo absoluto
G91               - Modo relativo
G92 X## Y##       - Definir posición actual

SERVO:
M3 / M300 S30     - Pluma ABAJO (dibujar)
M5 / M300 S50     - Pluma ARRIBA (mover)

SISTEMA:
M17               - Activar motores
M18               - Desactivar motores
M114              - Reportar posición
?                 - Estado actual

RESPUESTAS:
- Cada comando responde "ok"
- Estado: <Idle|MPos:X,Y,Z|FS:0,0>

=====================================
CALIBRACIÓN PARA TU HARDWARE
=====================================

1. VERIFICAR STEPS_PER_MM:
   - Enviar: G91 G1 X10 F500
   - Medir distancia real
   - Ajustar: STEPS_PER_MM = 39.37 * (10 / medida_real)

2. VERIFICAR DIRECCIÓN MOTORES:
   Si van al revés, cambiar en moveTo():
   int dirX = (stepsX > 0) ? BACKWARD : FORWARD;
   int dirY = (stepsY > 0) ? BACKWARD : FORWARD;

3. AJUSTAR SERVO:
   - Probar: M300 S30 (debe bajar)
   - Probar: M300 S50 (debe subir)
   - Ajustar SERVO_UP y SERVO_DOWN

4. VELOCIDAD MOTORES:
   - motorX.setSpeed(60-120) RPM
   - Más alto = más rápido pero menos torque

5. CONEXIONES SEGÚN TU MOTOR:
   Rojo    → A+ (Coil 1+)
   Amarillo → A- (Coil 1-)
   Azul    → B+ (Coil 2+)
   Negro   → B- (Coil 2-)

=====================================
PRUEBAS DESDE PYTHON GUI
=====================================

1. Conectar Arduino
2. Control manual:
   - Probar X+, X-, Y+, Y-
   - Ajustar velocidad (Lento/Normal/Rápido)
   - Probar Z+ y Z-

3. Establecer origen:
   - Mover a posición deseada
   - Click "Establecer Origen"

4. Cargar G-code:
   - Verificar visualización
   - Iniciar ejecución
   - Observar progreso

=====================================
SOLUCIÓN DE PROBLEMAS
=====================================

❌ Motor va al revés:
   → Invertir dirección en código

❌ Pasos incorrectos:
   → Ajustar STEPS_PER_MM

❌ Servo no responde:
   → Verificar SERVO_UP/DOWN (rango 0-180)

❌ Python no recibe "ok":
   → Verificar baudrate 9600

❌ Movimientos bruscos:
   → Reducir motorX.setSpeed()
   → Aumentar stepDelay

❌ Pérdida de pasos:
   → Reducir velocidad
   → Verificar alimentación motores
*/
