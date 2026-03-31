/*
=====================================
CÓDIGO ARDUINO - MOTOR SHIELD V1
VERSIÓN OPTIMIZADA (Bajo Consumo de Memoria)
=====================================
✅ Optimizado para Arduino UNO (2KB RAM)
✅ Motor Shield V1
✅ Motores paso a paso 4 líneas
✅ Servo SG90
✅ MÍNIMA HUELLA DE MEMORIA
*/

#include <Servo.h>

// ===== PINES =====
#define DIR_SER     8
#define DIR_CLK     4
#define DIR_LATCH   12
#define DIR_EN      7
#define MOTOR_1_PWM 10
#define MOTOR_2_PWM 9
#define SERVO_PIN   6

Servo servoZ;

// ===== CONSTANTES =====
#define SPEED_VERY_SLOW 50
#define SPEED_SLOW      30
#define SPEED_NORMAL    15
#define SPEED_FAST      8
#define SPEED_VERY_FAST 5
#define PWM_CURRENT_LIMIT 200

// ===== VARIABLES GLOBALES (MÍNIMAS) =====
volatile long pos_x = 0;
volatile long pos_y = 0;
volatile int pos_z = 90;

int current_speed = SPEED_NORMAL;
unsigned long last_step_time = 0;
unsigned long last_display_time = 0;

volatile int move_x = 0;
volatile int move_y = 0;
volatile int move_z = 0;

// Secuencias: Solo 8 bytes
const byte step_sequence[8] = {
  0b0001, 0b0011, 0b0010, 0b0110,
  0b0100, 0b1100, 0b1000, 0b1001
};

byte step_index = 0;
long x_min = 0, x_max = 315;
long y_min = 0, y_max = 315;

// ===== FORWARD DECLARATIONS =====
void shift_register_write(byte data);
void move_servo_smooth(int dir);
bool can_move_x(int dir);
bool can_move_y(int dir);
void stop_motors();
void process_command(byte cmd);
void print_status();
void print_info();
void reset_limits();
void test_motor_1();
void test_motor_2();
void test_servo();
void return_to_home();

// ===== SETUP =====
void setup() {
  Serial.begin(9600);
  delay(100);
  
  pinMode(DIR_SER, OUTPUT);
  pinMode(DIR_CLK, OUTPUT);
  pinMode(DIR_LATCH, OUTPUT);
  pinMode(DIR_EN, OUTPUT);
  pinMode(MOTOR_1_PWM, OUTPUT);
  pinMode(MOTOR_2_PWM, OUTPUT);
  
  digitalWrite(DIR_SER, LOW);
  digitalWrite(DIR_CLK, LOW);
  digitalWrite(DIR_LATCH, LOW);
  digitalWrite(DIR_EN, LOW);
  
  analogWrite(MOTOR_1_PWM, PWM_CURRENT_LIMIT);
  analogWrite(MOTOR_2_PWM, PWM_CURRENT_LIMIT);
  
  stop_motors();
  
  servoZ.attach(SERVO_PIN);
  servoZ.write(90);
  delay(200);
  
  // Mensaje inicial compacto
  Serial.println(F("CNC v1.0"));
}

// ===== LOOP PRINCIPAL =====
void loop() {
  unsigned long now = millis();
  
  if (now - last_step_time >= current_speed) {
    last_step_time = now;
    
    if (move_x != 0 || move_y != 0) {
      if ((move_x != 0 && can_move_x(move_x)) || 
          (move_y != 0 && can_move_y(move_y))) {
        
        if (move_x > 0) { step_index++; pos_x++; }
        else if (move_x < 0) { step_index--; pos_x--; }
        
        if (move_y > 0) { step_index++; pos_y++; }
        else if (move_y < 0) { step_index--; pos_y--; }
        
        step_index = step_index % 8;
        shift_register_write(step_sequence[step_index]);
      }
    }
    
    if (move_z != 0) {
      move_servo_smooth(move_z);
    }
  }
  
  if (Serial.available() > 0) {
    process_command(Serial.read());
  }
  
  if (now - last_display_time > 2000) {
    last_display_time = now;
    print_status();
  }
}

// ===== SHIFT REGISTER =====
void shift_register_write(byte data) {
  digitalWrite(DIR_LATCH, LOW);
  
  for (int i = 0; i < 8; i++) {
    digitalWrite(DIR_SER, (data & (1 << i)) ? HIGH : LOW);
    digitalWrite(DIR_CLK, HIGH);
    delayMicroseconds(5);
    digitalWrite(DIR_CLK, LOW);
  }
  
  digitalWrite(DIR_LATCH, HIGH);
  delayMicroseconds(5);
  digitalWrite(DIR_LATCH, LOW);
}

// ===== SERVO =====
void move_servo_smooth(int dir) {
  static unsigned long last_servo_move = 0;
  
  if (millis() - last_servo_move >= 20) {
    last_servo_move = millis();
    int new_z = pos_z + (dir * 1);
    
    if (new_z >= 0 && new_z <= 180) {
      servoZ.write(new_z);
      pos_z = new_z;
    } else {
      move_z = 0;
    }
  }
}

// ===== LÍMITES =====
bool can_move_x(int dir) {
  long new_pos = pos_x + dir;
  return (new_pos >= x_min && new_pos <= x_max);
}

bool can_move_y(int dir) {
  long new_pos = pos_y + dir;
  return (new_pos >= y_min && new_pos <= y_max);
}

// ===== CONTROL =====
void stop_motors() {
  shift_register_write(0b0000);
  move_x = 0;
  move_y = 0;
}

void reset_limits() {
  x_min = 0; x_max = 315;
  y_min = 0; y_max = 315;
  Serial.println(F("RST"));
}

void test_motor_1() {
  for (int i = 0; i < 20; i++) {
    step_index++;
    step_index %= 8;
    shift_register_write(step_sequence[step_index]);
    delay(50);
  }
  stop_motors();
}

void test_motor_2() {
  for (int i = 0; i < 20; i++) {
    step_index++;
    step_index %= 8;
    shift_register_write(step_sequence[step_index]);
    delay(50);
  }
  stop_motors();
}

void test_servo() {
  servoZ.write(0);
  delay(500);
  servoZ.write(90);
  delay(500);
  servoZ.write(180);
  delay(500);
  servoZ.write(90);
}

void return_to_home() {
  Serial.println(F("HOME"));
  
  unsigned long home_step_time = millis();
  
  while (pos_x > 0) {
    if (millis() - home_step_time >= current_speed) {
      home_step_time = millis();
      step_index = (step_index - 1 + 8) % 8;
      shift_register_write(step_sequence[step_index]);
      pos_x--;
    }
  }
  
  while (pos_y > 0) {
    if (millis() - home_step_time >= current_speed) {
      home_step_time = millis();
      step_index = (step_index - 1 + 8) % 8;
      shift_register_write(step_sequence[step_index]);
      pos_y--;
    }
  }
  
  servoZ.write(90);
  pos_z = 90;
}

// ===== DISPLAY =====
void print_status() {
  Serial.print(F("X:"));
  Serial.print(pos_x);
  Serial.print(F(" Y:"));
  Serial.print(pos_y);
  Serial.print(F(" Z:"));
  Serial.println(pos_z);
}

void print_info() {
  Serial.println(F("CNC v1.0"));
  Serial.println(F("a/b: X-/X+"));
  Serial.println(F("c/d: Y-/Y+"));
  Serial.println(F("e/f: Z-/Z+"));
  Serial.println(F("1-5: Speed"));
  Serial.println(F("s:STOP h:HOME"));
  Serial.println(F("x/X:Xmin/max"));
  Serial.println(F("y/Y:Ymin/max"));
  Serial.println(F("r:RESET p:POS"));
  Serial.println(F("i:INFO t/u/v:TEST"));
}

// ===== COMANDOS (ULTRA-COMPACTO) =====
void process_command(byte cmd) {
  
  switch(cmd) {
    // Movimiento
    case 'a': move_x = -1; move_y = 0; break;
    case 'b': move_x = 1; move_y = 0; break;
    case 'c': move_y = -1; move_x = 0; break;
    case 'd': move_y = 1; move_x = 0; break;
    case 'e': move_z = -1; break;
    case 'f': move_z = 1; break;
    
    // Velocidad
    case '1': current_speed = SPEED_VERY_SLOW; break;
    case '2': current_speed = SPEED_SLOW; break;
    case '3': current_speed = SPEED_NORMAL; break;
    case '4': current_speed = SPEED_FAST; break;
    case '5': current_speed = SPEED_VERY_FAST; break;
    
    // Control
    case 's': stop_motors(); break;
    case 'h': return_to_home(); break;
    case 'i': print_info(); break;
    case 'p': print_status(); break;
    case 'r': reset_limits(); break;
    
    // Calibración
    case 'x': x_min = pos_x; break;
    case 'X': x_max = pos_x; break;
    case 'y': y_min = pos_y; break;
    case 'Y': y_max = pos_y; break;
    
    // Pruebas
    case 't': test_motor_1(); break;
    case 'u': test_motor_2(); break;
    case 'v': test_servo(); break;
  }
}

/*
COMANDOS COMPACTOS:
═══════════════════

MOVIMIENTO:
a     → X- (izquierda)
b     → X+ (derecha)
c     → Y- (atrás)
d     → Y+ (adelante)
e     → Z- (servo arriba)
f     → Z+ (servo abajo)

VELOCIDAD:
1-5   → Velocidades

CONTROL:
s     → STOP
h     → HOME
p     → Posición
i     → Info
r     → Reset límites

CALIBRACIÓN:
x     → Calibrar X mínimo
X     → Calibrar X máximo
y     → Calibrar Y mínimo
Y     → Calibrar Y máximo

PRUEBAS:
t     → Test Motor 1
u     → Test Motor 2
v     → Test Servo

EJEMPLO DE USO (Serial Monitor):
================================
1. Enviar: i (ver info)
2. Enviar: t (probar motor 1)
3. Enviar: u (probar motor 2)
4. Enviar: v (probar servo)
5. Enviar: b (mover X+)
6. Enviar: d (mover Y+)
7. Enviar: 2 (cambiar a velocidad 2)
8. Enviar: h (volver a home)
*/
