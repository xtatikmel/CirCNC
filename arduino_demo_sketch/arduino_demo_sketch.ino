/*
=====================================
CÓDIGO ARDUINO - CNC DEMO CONTROL
=====================================
✅ 2 Motores paso a paso con L293D
✅ 1 Servo SG90
✅ Serial communication 9600 baud
✅ Responde comandos desde Python

CONEXIONES:
-----------
Motor X (L293D Canal 1):
  IN1 = Arduino Pin 2
  IN2 = Arduino Pin 3
  EN  = Arduino Pin 4 (PWM)

Motor Y (L293D Canal 2):
  IN3 = Arduino Pin 5
  IN4 = Arduino Pin 6
  EN  = Arduino Pin 7 (PWM)

Servo SG90 (Eje Z):
  Signal = Arduino Pin 9 (PWM)

COMANDOS DESDE PYTHON:
----------------------
INIT                     - Inicializar
MOVE_X_FWD,steps,delay  - Motor X adelante
MOVE_X_REV,steps,delay  - Motor X atrás
MOVE_Y_FWD,steps,delay  - Motor Y adelante
MOVE_Y_REV,steps,delay  - Motor Y atrás
MOVE_Z,angle            - Servo a ángulo
RETURN_HOME             - Retorna a (0,0,90)

*/

#include <Servo.h>

// ===== DEFINICIONES L293D =====
// MOTOR X
#define MOTOR_X_IN1 2
#define MOTOR_X_IN2 3
#define MOTOR_X_EN 4

// MOTOR Y
#define MOTOR_Y_IN3 5
#define MOTOR_Y_IN4 6
#define MOTOR_Y_EN 7

// SERVO
#define SERVO_PIN 9

// Velocidades PWM
#define PWM_SPEED 255  // Máxima velocidad

// ===== VARIABLES GLOBALES =====
Servo servoZ;
int current_x_position = 0;
int current_y_position = 0;
int current_z_angle = 90;

void setup() {
  // Inicializar serial
  Serial.begin(9600);
  delay(500);
  
  // Configurar pines L293D como salidas
  pinMode(MOTOR_X_IN1, OUTPUT);
  pinMode(MOTOR_X_IN2, OUTPUT);
  pinMode(MOTOR_X_EN, OUTPUT);
  
  pinMode(MOTOR_Y_IN3, OUTPUT);
  pinMode(MOTOR_Y_IN4, OUTPUT);
  pinMode(MOTOR_Y_EN, OUTPUT);
  
  // Inicializar servo
  servoZ.attach(SERVO_PIN);
  servoZ.write(90);  // Posición inicial
  
  // Detener motores al inicio
  stop_all();
  
  Serial.println("INIT:OK");
  Serial.println("Sistema listo - Esperando comandos...");
}

void loop() {
  // Leer comandos desde Serial
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    // Log del comando recibido
    Serial.print("Comando recibido: ");
    Serial.println(command);
    
    // Procesar comando
    process_command(command);
  }
  
  delay(10);
}

// ===== FUNCIONES DE CONTROL =====

void process_command(String cmd) {
  if (cmd == "INIT") {
    Serial.println("ACK:INIT");
    stop_all();
  }
  
  else if (cmd.startsWith("MOVE_X_FWD")) {
    // Formato: MOVE_X_FWD,steps,delay
    int steps = extract_param(cmd, 1);
    int delay_ms = extract_param(cmd, 2);
    move_x_forward(steps, delay_ms);
  }
  
  else if (cmd.startsWith("MOVE_X_REV")) {
    int steps = extract_param(cmd, 1);
    int delay_ms = extract_param(cmd, 2);
    move_x_reverse(steps, delay_ms);
  }
  
  else if (cmd.startsWith("MOVE_Y_FWD")) {
    int steps = extract_param(cmd, 1);
    int delay_ms = extract_param(cmd, 2);
    move_y_forward(steps, delay_ms);
  }
  
  else if (cmd.startsWith("MOVE_Y_REV")) {
    int steps = extract_param(cmd, 1);
    int delay_ms = extract_param(cmd, 2);
    move_y_reverse(steps, delay_ms);
  }
  
  else if (cmd.startsWith("MOVE_Z")) {
    // Formato: MOVE_Z,angle
    int angle = extract_param(cmd, 1);
    move_servo(angle);
  }
  
  else if (cmd == "RETURN_HOME") {
    return_home();
  }
  
  else {
    Serial.println("ERROR:Unknown command");
  }
}

// ===== MOVIMIENTO MOTOR X =====

void move_x_forward(int steps, int delay_ms) {
  // Motor X adelante: IN1=HIGH, IN2=LOW
  digitalWrite(MOTOR_X_IN1, HIGH);
  digitalWrite(MOTOR_X_IN2, LOW);
  analogWrite(MOTOR_X_EN, PWM_SPEED);
  
  // Pasos
  for (int i = 0; i < steps; i++) {
    digitalWrite(MOTOR_X_IN1, HIGH);
    delayMicroseconds(5);
    digitalWrite(MOTOR_X_IN1, LOW);
    delayMicroseconds(5);
    delay(delay_ms);
  }
  
  digitalWrite(MOTOR_X_EN, 0);
  current_x_position += steps;
  
  Serial.print("X_FWD:");
  Serial.println(steps);
}

void move_x_reverse(int steps, int delay_ms) {
  // Motor X atrás: IN1=LOW, IN2=HIGH
  digitalWrite(MOTOR_X_IN1, LOW);
  digitalWrite(MOTOR_X_IN2, HIGH);
  analogWrite(MOTOR_X_EN, PWM_SPEED);
  
  // Pasos
  for (int i = 0; i < steps; i++) {
    digitalWrite(MOTOR_X_IN2, HIGH);
    delayMicroseconds(5);
    digitalWrite(MOTOR_X_IN2, LOW);
    delayMicroseconds(5);
    delay(delay_ms);
  }
  
  digitalWrite(MOTOR_X_EN, 0);
  current_x_position -= steps;
  
  Serial.print("X_REV:");
  Serial.println(steps);
}

// ===== MOVIMIENTO MOTOR Y =====

void move_y_forward(int steps, int delay_ms) {
  // Motor Y adelante: IN3=HIGH, IN4=LOW
  digitalWrite(MOTOR_Y_IN3, HIGH);
  digitalWrite(MOTOR_Y_IN4, LOW);
  analogWrite(MOTOR_Y_EN, PWM_SPEED);
  
  // Pasos
  for (int i = 0; i < steps; i++) {
    digitalWrite(MOTOR_Y_IN3, HIGH);
    delayMicroseconds(5);
    digitalWrite(MOTOR_Y_IN3, LOW);
    delayMicroseconds(5);
    delay(delay_ms);
  }
  
  digitalWrite(MOTOR_Y_EN, 0);
  current_y_position += steps;
  
  Serial.print("Y_FWD:");
  Serial.println(steps);
}

void move_y_reverse(int steps, int delay_ms) {
  // Motor Y atrás: IN3=LOW, IN4=HIGH
  digitalWrite(MOTOR_Y_IN3, LOW);
  digitalWrite(MOTOR_Y_IN4, HIGH);
  analogWrite(MOTOR_Y_EN, PWM_SPEED);
  
  // Pasos
  for (int i = 0; i < steps; i++) {
    digitalWrite(MOTOR_Y_IN4, HIGH);
    delayMicroseconds(5);
    digitalWrite(MOTOR_Y_IN4, LOW);
    delayMicroseconds(5);
    delay(delay_ms);
  }
  
  digitalWrite(MOTOR_Y_EN, 0);
  current_y_position -= steps;
  
  Serial.print("Y_REV:");
  Serial.println(steps);
}

// ===== MOVIMIENTO SERVO =====

void move_servo(int angle) {
  // Limitar ángulo (0-180)
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  
  servoZ.write(angle);
  current_z_angle = angle;
  
  Serial.print("SERVO:");
  Serial.print(angle);
  Serial.println("°");
  
  delay(50);  // Tiempo para que el servo se posicione
}

// ===== FUNCIONES AUXILIARES =====

void stop_all() {
  // Detener motor X
  digitalWrite(MOTOR_X_EN, 0);
  digitalWrite(MOTOR_X_IN1, 0);
  digitalWrite(MOTOR_X_IN2, 0);
  
  // Detener motor Y
  digitalWrite(MOTOR_Y_EN, 0);
  digitalWrite(MOTOR_Y_IN3, 0);
  digitalWrite(MOTOR_Y_IN4, 0);
}

void return_home() {
  // Retornar a (0,0,90)
  Serial.println("HOMING...");
  
  // Mover a inicio en X (pasos negativos)
  for (int i = 0; i < current_x_position; i++) {
    move_x_reverse(1, 5);
  }
  
  // Mover a inicio en Y
  for (int i = 0; i < current_y_position; i++) {
    move_y_reverse(1, 5);
  }
  
  // Servo a 90°
  move_servo(90);
  
  current_x_position = 0;
  current_y_position = 0;
  current_z_angle = 90;
  
  Serial.println("HOME:OK");
}

// Extrae parámetro de comando separado por comas
int extract_param(String cmd, int param_num) {
  int count = 0;
  int start = 0;
  
  for (int i = 0; i < cmd.length(); i++) {
    if (cmd[i] == ',') {
      count++;
      if (count == param_num) {
        return cmd.substring(start, i).toInt();
      }
      start = i + 1;
    }
  }
  
  // Último parámetro
  if (count + 1 == param_num) {
    return cmd.substring(start).toInt();
  }
  
  return 0;
}

/*
EJEMPLO DE SESIÓN:

PC → Arduino:  INIT
Arduino → PC:  INIT:OK

PC → Arduino:  MOVE_X_FWD,10,15
Arduino → PC:  X_FWD:10

PC → Arduino:  MOVE_Y_FWD,5,15
Arduino → PC:  Y_FWD:5

PC → Arduino:  MOVE_Z,45
Arduino → PC:  SERVO:45°

PC → Arduino:  RETURN_HOME
Arduino → PC:  HOMING...
Arduino → PC:  HOME:OK

*/
