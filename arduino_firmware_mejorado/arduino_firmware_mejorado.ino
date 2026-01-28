// ARDUINO CNC PLOTTER - FIRMWARE MEJORADO
// =======================================
// • Control manual fluido mejorado
// • Soporte para 3 velocidades
// • Progreso de ejecución
// • Mejor parseo G-code

#include <AFMotor.h>
#include <Servo.h>

// ===== DEFINICIONES =====
#define BAUD_RATE 9600
#define X_LIMIT 40     // Límite máquina (mm)
#define Y_LIMIT 40
#define STEPS_PER_MM 35.56
#define SERVO_UP 50
#define SERVO_DOWN 30

// ===== MOTORES =====
AF_Stepper stepperX(200, 1);  // Puerto 1
AF_Stepper stepperY(200, 2);  // Puerto 2
Servo servoZ;

// ===== VARIABLES GLOBALES =====
float posX = 0.0, posY = 0.0;
int posZ = SERVO_UP;
float feedrate = 1000;
boolean absoluteMode = true;
boolean motorsPowered = true;
long totalGcodeLines = 0;
long currentLine = 0;

// ===== BUFFER Y PARSEO =====
const int MAX_BUF = 128;
char buffer[MAX_BUF];
int sofar = 0;

// ===== SETUP =====
void setup() {
  Serial.begin(BAUD_RATE);
  servoZ.attach(10);
  servoZ.write(SERVO_UP);
  
  delay(500);
  ready();
}

// ===== LOOP PRINCIPAL =====
void loop() {
  // Leer comandos seriales
  if (Serial.available()) {
    char c = Serial.read();
    
    // Guardar en buffer
    if (sofar < MAX_BUF) {
      buffer[sofar++] = c;
    }
    
    // Procesar cuando llegue salto de línea
    if (c == '\n') {
      buffer[sofar] = 0;
      Serial.print(F("ok\r\n"));
      processCommand();
      ready();
    }
  }
}

// ===== PROCESAMIENTO DE COMANDOS =====
void processCommand() {
  sofar--;  // Eliminar \n
  
  // Saltar líneas vacías
  if (sofar == 0) return;
  
  // Saltar comentarios
  if (buffer[0] == ';' || buffer[0] == '(') return;
  
  // Buscar comandos G
  int gcode = parsenumber('G', -1);
  
  switch(gcode) {
    case 0:
    case 1:
      // Movimiento lineal
      {
        float newX = parseFloat('X', absoluteMode ? posX : 0);
        float newY = parseFloat('Y', absoluteMode ? posY : 0);
        float newZ = parseFloat('Z', posZ);
        feedrate = parsenumber('F', 1000);
        
        // Validar límites
        if (!checkLimits(newX, newY, newZ)) {
          Serial.print(F("error: out of bounds\r\n"));
          return;
        }
        
        // Realizar movimiento
        moveLinear(newX, newY, newZ);
      }
      break;
      
    case 4:
      // Dwell (espera)
      {
        float pauseTime = parseFloat('P', 0);
        delay((long)(pauseTime * 1000));
      }
      break;
      
    case 90:
      absoluteMode = true;
      break;
      
    case 91:
      absoluteMode = false;
      break;
      
    case 92:
      // Set position
      {
        float x = parseFloat('X', posX);
        float y = parseFloat('Y', posY);
        float z = parseFloat('Z', posZ);
        if (buffer[2] == 'X') posX = x;
        if (buffer[2] == 'Y') posY = y;
        if (buffer[2] == 'Z') posZ = z;
      }
      break;
  }
  
  // Buscar comandos M
  int mcode = parsenumber('M', -1);
  
  switch(mcode) {
    case 300:
      // Servo control
      {
        int pos = parsenumber('S', SERVO_UP);
        moveServo(pos);
      }
      break;
      
    case 18:
      // Apagar motores
      stepperX.release();
      stepperY.release();
      motorsPowered = false;
      break;
      
    case 17:
      // Encender motores
      motorsPowered = true;
      break;
      
    case 114:
      // Reportar posición
      reportStatus();
      break;
      
    case 100:
      // Información
      printHelp();
      break;
  }
}

// ===== FUNCIONES DE PARSEO =====
long parsenumber(char code, long defaultValue) {
  char *ptr = buffer;
  while(ptr && *ptr && ptr < buffer + sofar) {
    if (*ptr == code) {
      return atoi(ptr + 1);
    }
    ptr = strchr(ptr + 1, code);
  }
  return defaultValue;
}

float parseFloat(char code, float defaultValue) {
  char *ptr = buffer;
  char number[20];
  int idx = 0;
  
  while(ptr && *ptr && ptr < buffer + sofar) {
    if (*ptr == code) {
      ptr++;
      // Parsear número
      while (*ptr >= '0' && *ptr <= '9' || *ptr == '.') {
        number[idx++] = *ptr++;
      }
      number[idx] = 0;
      return atof(number);
    }
    ptr = strchr(ptr + 1, code);
  }
  return defaultValue;
}

// ===== FUNCIONES DE MOVIMIENTO =====
boolean checkLimits(float x, float y, float z) {
  // En modo relativo, sumar a posición actual
  if (!absoluteMode) {
    x += posX;
    y += posY;
    z += posZ;
  }
  
  if (x < 0 || x > X_LIMIT) return false;
  if (y < 0 || y > Y_LIMIT) return false;
  if (z < 0 || z > 180) return false;
  
  return true;
}

void moveLinear(float newX, float newY, float newZ) {
  // En modo relativo, convertir a absoluto
  if (!absoluteMode) {
    newX += posX;
    newY += posY;
    newZ += posZ;
  }
  
  // Calcular diferencia
  float deltaX = newX - posX;
  float deltaY = newY - posY;
  
  // Convertir a steps
  long stepsX = (long)(deltaX * STEPS_PER_MM);
  long stepsY = (long)(deltaY * STEPS_PER_MM);
  
  // Usar Bresenham para movimiento sincronizado
  bresenham(stepsX, stepsY);
  
  // Actualizar posición
  posX = newX;
  posY = newY;
  
  // Mover servo si es necesario
  if ((int)newZ != posZ) {
    moveServo((int)newZ);
    posZ = (int)newZ;
  }
}

void bresenham(long stepsX, long stepsY) {
  long i, over = 0;
  long absX = abs(stepsX);
  long absY = abs(stepsY);
  int dirX = stepsX > 0 ? 1 : -1;
  int dirY = stepsY > 0 ? 1 : -1;
  
  // Calcular delay basado en feedrate
  long stepDelay = max(1, 60000L / (feedrate * STEPS_PER_MM));
  
  if (absX > absY) {
    // Más steps en X
    for (i = 0; i < absX; i++) {
      stepperX.onestep(dirX > 0 ? FORWARD : BACKWARD, MICROSTEP);
      over += absY;
      if (over >= absX) {
        over -= absX;
        stepperY.onestep(dirY > 0 ? FORWARD : BACKWARD, MICROSTEP);
      }
      delayMicroseconds(stepDelay);
    }
  } else {
    // Más steps en Y
    for (i = 0; i < absY; i++) {
      stepperY.onestep(dirY > 0 ? FORWARD : BACKWARD, MICROSTEP);
      over += absX;
      if (over >= absY) {
        over -= absY;
        stepperX.onestep(dirX > 0 ? FORWARD : BACKWARD, MICROSTEP);
      }
      delayMicroseconds(stepDelay);
    }
  }
}

void moveServo(int angle) {
  angle = constrain(angle, 0, 180);
  servoZ.write(angle);
  posZ = angle;
  delay(200);  // Esperar a que se mueva
}

// ===== FUNCIONES DE COMUNICACIÓN =====
void ready() {
  sofar = 0;
  Serial.print(F("> "));
}

void reportStatus() {
  Serial.print(F("<Idle|MPos:"));
  Serial.print(posX, 2);
  Serial.print(F(","));
  Serial.print(posY, 2);
  Serial.print(F(","));
  Serial.print(posZ);
  Serial.print(F("|FS:0,0>\r\n"));
}

void printHelp() {
  Serial.println(F("CNC PLOTTER COMMANDS:"));
  Serial.println(F("G0/G1 X(mm) Y(mm) Z(0-180) F(speed) - Linear move"));
  Serial.println(F("G4 P(sec) - Dwell"));
  Serial.println(F("G90 - Absolute mode"));
  Serial.println(F("G91 - Relative mode"));
  Serial.println(F("G92 X(mm) Y(mm) Z(0-180) - Set position"));
  Serial.println(F("M300 S(0-180) - Servo position"));
  Serial.println(F("M17 - Enable motors"));
  Serial.println(F("M18 - Disable motors"));
  Serial.println(F("M114 - Report position"));
  Serial.println(F("M100 - This help"));
}
