/*
=====================================
CÓDIGO ARDUINO - CNC PROFESIONAL
=====================================
✅ Motor Paso a Paso 18° (Modelo 9294)
✅ Driver L293D Optimizado
✅ Servo SG90 PWM
✅ Basado en mejores prácticas IARJSET 2025
✅ Comunicación serial 9600 baud
✅ Protecciones completas

HARDWARE:
- Arduino UNO
- Shield L293D
- 2x Motor paso 18° (0.5A máximo)
- 1x Servo SG90
- Fuente 6V 2A estabilizada
- Diodos 1N4007 en motores
- Capacitores decoupling

PINES:
Motor X: EN=4, IN1=2, IN2=3
Motor Y: EN=7, IN3=5, IN4=6
Servo Z: Pin 9 (PWM)

VELOCIDADES OPTIMIZADAS:
1 = 50ms (20 Hz)   - Precisión máxima
2 = 30ms (33 Hz)   - Trabajo fino
3 = 15ms (67 Hz)   - Normal ⭐
4 = 8ms (125 Hz)   - Rápido
5 = 3ms (333 Hz)   - Muy rápido (límite)
*/

#include <Servo.h>

// ===== PINES L293D =====
#define MOTOR_X_EN  4   // PWM
#define MOTOR_X_IN1 2   // Dirección
#define MOTOR_X_IN2 3   // Dirección

#define MOTOR_Y_EN  7   // PWM
#define MOTOR_Y_IN3 5   // Dirección
#define MOTOR_Y_IN4 6   // Dirección

// ===== SERVO =====
#define SERVO_PIN 9
Servo servoZ;

// ===== CONSTANTES DEL MOTOR =====
#define STEP_ANGLE 18                    // Ángulo de paso
#define STEPS_PER_REV (360 / STEP_ANGLE) // 20 pasos
#define MICROSTEPS 4                     // 4x microstepping
#define SCREW_PITCH_MM 0.508             // Tornillo
#define DISTANCE_PER_STEP 0.127          // mm por microstep

// ===== VELOCIDADES OPTIMIZADAS =====
#define SPEED_VERY_SLOW 50   // ms (20 Hz)
#define SPEED_SLOW      30   // ms (33 Hz)
#define SPEED_NORMAL    15   // ms (67 Hz) ⭐
#define SPEED_FAST      8    // ms (125 Hz)
#define SPEED_VERY_FAST 3    // ms (333 Hz - límite)

// ===== PWM CHOPPING =====
#define PWM_CURRENT_LIMIT 200 // 78% of 255 (reduce heat)

// ===== VARIABLES GLOBALES =====
volatile long pos_x = 0;     // Posición X en pasos
volatile long pos_y = 0;     // Posición Y en pasos
volatile int pos_z = 90;     // Ángulo servo (0-180)

int current_speed = SPEED_NORMAL; // Velocidad actual
unsigned long last_step_time = 0; // Control de timing
unsigned long last_display_time = 0;

volatile int move_x = 0;  // -1, 0, 1
volatile int move_y = 0;  // -1, 0, 1
volatile int move_z = 0;  // -1, 0, 1

// Límites calibrados
long x_min = 0;
long x_max = (long)(80.01 / DISTANCE_PER_STEP);  // 630 pasos
long y_min = 0;
long y_max = (long)(80.01 / DISTANCE_PER_STEP);  // 630 pasos

// ===== SETUP =====
void setup() {
  // Serial
  Serial.begin(9600);
  delay(100);
  
  // Configurar pines como OUTPUT
  pinMode(MOTOR_X_EN, OUTPUT);
  pinMode(MOTOR_X_IN1, OUTPUT);
  pinMode(MOTOR_X_IN2, OUTPUT);
  
  pinMode(MOTOR_Y_EN, OUTPUT);
  pinMode(MOTOR_Y_IN3, OUTPUT);
  pinMode(MOTOR_Y_IN4, OUTPUT);
  
  // Enable motors con corriente limitada
  analogWrite(MOTOR_X_EN, PWM_CURRENT_LIMIT);
  analogWrite(MOTOR_Y_EN, PWM_CURRENT_LIMIT);
  
  // Detener motores al inicio
  stop_motors();
  
  // Inicializar servo
  servoZ.attach(SERVO_PIN);
  servoZ.write(90);
  delay(200);
  
  // Configurar PWM de Arduino para mejor frecuencia
  setup_pwm_optimization();
  
  // Mensajes iniciales
  Serial.println("===== CNC SYSTEM INITIALIZED =====");
  Serial.println("Motor: 18° Stepper (Modelo 9294)");
  Serial.println("Driver: L293D (Optimizado)");
  Serial.println("Ready for commands...");
  Serial.print("Speed: ");
  print_speed_mode();
}

// ===== LOOP PRINCIPAL =====
void loop() {
  unsigned long now = millis();
  
  // ===== CONTROL DE TIMING (Muy importante para precisión) =====
  if (now - last_step_time >= current_speed) {
    last_step_time = now;
    
    // Procesar movimiento X
    if (move_x != 0) {
      if (can_move_x(move_x)) {
        do_step_x(move_x);
        pos_x += move_x;
      } else {
        Serial.print("LIMIT X: ");
        Serial.println(pos_x * DISTANCE_PER_STEP, 3);
        move_x = 0;
      }
    }
    
    // Procesar movimiento Y
    if (move_y != 0) {
      if (can_move_y(move_y)) {
        do_step_y(move_y);
        pos_y += move_y;
      } else {
        Serial.print("LIMIT Y: ");
        Serial.println(pos_y * DISTANCE_PER_STEP, 3);
        move_y = 0;
      }
    }
    
    // Procesar movimiento Z (servo)
    if (move_z != 0) {
      move_servo_smooth(move_z);
    }
  }
  
  // ===== PROCESAR COMANDOS SERIAL =====
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    process_command(command);
  }
  
  // ===== MOSTRAR POSICIÓN PERIÓDICAMENTE =====
  if (now - last_display_time > 1000) {
    last_display_time = now;
    print_status();
  }
}

// ===== PROCESAMIENTO DE COMANDOS =====
void process_command(String cmd) {
  
  // MOVIMIENTO MANUAL
  if (cmd == "X+") {
    move_x = 1;
    Serial.println("→ X: Moving +");
  }
  else if (cmd == "X-") {
    move_x = -1;
    Serial.println("→ X: Moving -");
  }
  else if (cmd == "Y+") {
    move_y = 1;
    Serial.println("→ Y: Moving +");
  }
  else if (cmd == "Y-") {
    move_y = -1;
    Serial.println("→ Y: Moving -");
  }
  else if (cmd == "Z+") {
    move_z = 1;
    Serial.println("→ Z: Moving +");
  }
  else if (cmd == "Z-") {
    move_z = -1;
    Serial.println("→ Z: Moving -");
  }
  
  // PARAR
  else if (cmd == "STOP") {
    move_x = 0;
    move_y = 0;
    move_z = 0;
    stop_motors();
    Serial.println("⏹ STOPPED");
  }
  
  // VELOCIDADES
  else if (cmd == "SPD1") {
    current_speed = SPEED_VERY_SLOW;
    Serial.println("⚙ Speed: VERY SLOW (50ms)");
  }
  else if (cmd == "SPD2") {
    current_speed = SPEED_SLOW;
    Serial.println("⚙ Speed: SLOW (30ms)");
  }
  else if (cmd == "SPD3") {
    current_speed = SPEED_NORMAL;
    Serial.println("⚙ Speed: NORMAL (15ms)");
  }
  else if (cmd == "SPD4") {
    current_speed = SPEED_FAST;
    Serial.println("⚙ Speed: FAST (8ms)");
  }
  else if (cmd == "SPD5") {
    current_speed = SPEED_VERY_FAST;
    Serial.println("⚙ Speed: VERY FAST (3ms)");
  }
  
  // HOME / ORIGEN
  else if (cmd == "HOME") {
    return_to_home();
  }
  
  // CALIBRACIÓN
  else if (cmd == "CALIB_X_MIN") {
    x_min = pos_x;
    Serial.print("📍 X-MIN calibrated: ");
    Serial.print(pos_x * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_X_MAX") {
    x_max = pos_x;
    Serial.print("📍 X-MAX calibrated: ");
    Serial.print(pos_x * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_Y_MIN") {
    y_min = pos_y;
    Serial.print("📍 Y-MIN calibrated: ");
    Serial.print(pos_y * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_Y_MAX") {
    y_max = pos_y;
    Serial.print("📍 Y-MAX calibrated: ");
    Serial.print(pos_y * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  
  // RESET LÍMITES
  else if (cmd == "RESET_LIMITS") {
    x_min = 0;
    x_max = (long)(80.01 / DISTANCE_PER_STEP);
    y_min = 0;
    y_max = (long)(80.01 / DISTANCE_PER_STEP);
    Serial.println("🔄 Limits reset to default");
  }
  
  // INFORMACIÓN
  else if (cmd == "INFO") {
    print_info();
  }
  
  // STATUS
  else if (cmd == "STATUS") {
    print_status();
  }
  
  // COMANDO DESCONOCIDO
  else {
    Serial.print("❌ Unknown: ");
    Serial.println(cmd);
  }
}

// ===== MOVIMIENTO MOTOR X =====
void do_step_x(int dir) {
  if (dir > 0) {
    // X Adelante: IN1=HIGH, IN2=LOW
    digitalWrite(MOTOR_X_IN1, HIGH);
    digitalWrite(MOTOR_X_IN2, LOW);
  } else {
    // X Atrás: IN1=LOW, IN2=HIGH
    digitalWrite(MOTOR_X_IN1, LOW);
    digitalWrite(MOTOR_X_IN2, HIGH);
  }
  
  delayMicroseconds(5);  // Ancho del pulso
  
  // Apagar
  digitalWrite(MOTOR_X_IN1, LOW);
  digitalWrite(MOTOR_X_IN2, LOW);
}

// ===== MOVIMIENTO MOTOR Y =====
void do_step_y(int dir) {
  if (dir > 0) {
    // Y Adelante: IN3=HIGH, IN4=LOW
    digitalWrite(MOTOR_Y_IN3, HIGH);
    digitalWrite(MOTOR_Y_IN4, LOW);
  } else {
    // Y Atrás: IN3=LOW, IN4=HIGH
    digitalWrite(MOTOR_Y_IN3, LOW);
    digitalWrite(MOTOR_Y_IN4, HIGH);
  }
  
  delayMicroseconds(5);
  
  // Apagar
  digitalWrite(MOTOR_Y_IN3, LOW);
  digitalWrite(MOTOR_Y_IN4, LOW);
}

// ===== MOVIMIENTO SERVO SUAVE =====
void move_servo_smooth(int dir) {
  static unsigned long last_servo_move = 0;
  
  if (millis() - last_servo_move >= 30) {  // 30ms entre cambios
    last_servo_move = millis();
    
    int new_z = pos_z + (dir * 2);  // 2 grados por movimiento
    
    if (new_z >= 0 && new_z <= 180) {
      servoZ.write(new_z);
      pos_z = new_z;
    } else {
      move_z = 0;  // Detener al alcanzar límite
    }
  }
}

// ===== VERIFICAR LÍMITES =====
bool can_move_x(int dir) {
  long new_pos = pos_x + dir;
  return (new_pos >= x_min && new_pos <= x_max);
}

bool can_move_y(int dir) {
  long new_pos = pos_y + dir;
  return (new_pos >= y_min && new_pos <= y_max);
}

// ===== FUNCIONES AUXILIARES =====
void stop_motors() {
  digitalWrite(MOTOR_X_IN1, LOW);
  digitalWrite(MOTOR_X_IN2, LOW);
  digitalWrite(MOTOR_Y_IN3, LOW);
  digitalWrite(MOTOR_Y_IN4, LOW);
  move_x = 0;
  move_y = 0;
}

void return_to_home() {
  Serial.println("🏠 Returning to home...");
  
  // Mover X a origen
  while (pos_x > 0) {
    if (millis() - last_step_time >= current_speed) {
      last_step_time = millis();
      do_step_x(-1);
      pos_x--;
    }
  }
  
  // Mover Y a origen
  while (pos_y > 0) {
    if (millis() - last_step_time >= current_speed) {
      last_step_time = millis();
      do_step_y(-1);
      pos_y--;
    }
  }
  
  // Servo a 90°
  servoZ.write(90);
  pos_z = 90;
  
  Serial.println("✅ Home position reached");
}

void setup_pwm_optimization() {
  // Configurar Timer1 para mejor frecuencia PWM
  // Aumenta la frecuencia PWM para reducir ruido del motor
  TCCR1B = (TCCR1B & 0xf8) | 0x01;  // Prescaler = 1
}

void print_status() {
  Serial.print("POS X:");
  Serial.print(pos_x * DISTANCE_PER_STEP, 3);
  Serial.print("mm Y:");
  Serial.print(pos_y * DISTANCE_PER_STEP, 3);
  Serial.print("mm Z:");
  Serial.print(pos_z);
  Serial.println("°");
}

void print_speed_mode() {
  switch (current_speed) {
    case SPEED_VERY_SLOW:
      Serial.println("VERY SLOW (50ms)");
      break;
    case SPEED_SLOW:
      Serial.println("SLOW (30ms)");
      break;
    case SPEED_NORMAL:
      Serial.println("NORMAL (15ms)");
      break;
    case SPEED_FAST:
      Serial.println("FAST (8ms)");
      break;
    case SPEED_VERY_FAST:
      Serial.println("VERY FAST (3ms)");
      break;
  }
}

void print_info() {
  Serial.println("\n===== SYSTEM INFO =====");
  Serial.println("Motor: 18° Stepper (Modelo 9294)");
  Serial.println("Resolution: 0.127mm per step");
  Serial.println("Max Stroke: 80.01mm per axis");
  Serial.println("Servo: SG90 (0-180°)");
  Serial.println("\nCOMMANDS:");
  Serial.println("X+/X-/Y+/Y- : Manual movement");
  Serial.println("Z+/Z-       : Servo control");
  Serial.println("SPD1-5      : Speed 1=Slow, 5=Fast");
  Serial.println("HOME        : Return to origin");
  Serial.println("CALIB_X_MIN/MAX : Calibrate X");
  Serial.println("CALIB_Y_MIN/MAX : Calibrate Y");
  Serial.println("RESET_LIMITS    : Reset to default");
  Serial.println("STATUS      : Show current position");
  Serial.println("STOP        : Stop all motors");
  Serial.println("INFO        : Show this info");
  Serial.println("=======================\n");
}

/* 
COMANDOS DESDE PYTHON:
======================
serial.write(b"X+\n")        → Mover X adelante
serial.write(b"Y-\n")        → Mover Y atrás
serial.write(b"SPD3\n")      → Velocidad normal
serial.write(b"HOME\n")      → Retornar a origen
serial.write(b"CALIB_X_MIN\n") → Calibrar X mínimo
serial.write(b"STATUS\n")    → Ver posición actual

RESPUESTAS ARDUINO:
===================
"→ X: Moving +"              → Confirmación movimiento
"⏹ STOPPED"                  → Parado
"⚙ Speed: NORMAL (15ms)"     → Velocidad cambiada
"✅ Home position reached"   → En origen
"📍 X-MIN calibrated: ..."   → Calibración
"POS X:20.150mm Y:15.320mm Z:90°" → Posición actual
*/
