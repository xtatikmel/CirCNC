/*
=====================================
CÓDIGO ARDUINO - MOTOR SHIELD V1
=====================================
✅ Motor Shield V1 de Prometec/Adafruit
✅ Driver L293D/L298N (depende de la versión)
✅ Motores paso a paso 4 líneas (bipolar)
✅ Control 74HC595 Shift Register
✅ Servo SG90 PWM
✅ Basado en mejores prácticas IARJSET 2025

HARDWARE ESPECÍFICO:
- Arduino UNO
- Motor Shield V1 (Prometec/Adafruit compatible)
- 2x Motor paso 4 líneas (bipolar) 1.8°
- 1x Servo SG90
- Fuente 6V 2A estabilizada (EXT_PWR)

PINES USADOS:
D3  - (disponible - no usado en shield)
D4  - DIR_CLK (Shift Register Clock)
D5  - (disponible - no usado en shield)
D6  - (disponible - no usado en shield)
D7  - DIR_EN (Shift Register Enable)
D8  - DIR_SER (Shift Register Serial Data)
D9  - Motor B Enable PWM (MOTOR 2)
D10 - Motor A Enable PWM (MOTOR 1)
D11 - IN2 (Control Motor 1 dirección 2)
D12 - DIR_LATCH (Shift Register Latch)
D13 - IN4 (Control Motor 2 dirección 2)

NOTA: El shield NO usa D2 para shift register normalmente.
      Verificar tu versión exacta.

CONEXIÓN DE MOTORES (Motor Shield V1):
Motor X → M1/M2 (Puertos Motor 1)
Motor Y → M3/M4 (Puertos Motor 2)

SERVO: D10 (pero D10 es Enable Motor 1)
       → Usar D6 o D3 alternativamente
       → O usar SER1 header (D10) si no usas ese motor

OPERACIÓN SHIFT REGISTER (74HC595):
- D8  (SER)   : Serial Data
- D4  (SRCLK) : Shift Clock
- D12 (RCLK)  : Latch Clock / Storage Clock
- D7  (OE)    : Output Enable (activo bajo)

BITS DEL SHIFT REGISTER (OUTPUT):
Q0: M1A (Motor 1 Phase A - OUT1)
Q1: M1B (Motor 1 Phase B - OUT2)
Q2: M2A (Motor 2 Phase A - OUT3)
Q3: M2B (Motor 2 Phase B - OUT4)
Q4-Q7: No usados (disponibles)
*/

#include <Servo.h>

// ===== PINES ESPECÍFICOS DEL SHIELD V1 =====
#define DIR_SER     8    // Shift Register Serial Data (SER)
#define DIR_CLK     4    // Shift Register Clock (SRCLK)
#define DIR_LATCH   12   // Shift Register Latch (RCLK)
#define DIR_EN      7    // Shift Register Output Enable (OE)

#define MOTOR_1_PWM 10   // Motor 1 Speed (D10) - PWM
#define MOTOR_2_PWM 9    // Motor 2 Speed (D9)  - PWM

#define IN2         11   // Motor 1 Direction bit (IN2)
#define IN4         13   // Motor 2 Direction bit (IN4)

// ===== SERVO =====
// OPCIÓN 1: Usar D6 (disponible)
// OPCIÓN 2: Usar D3 (disponible)
// OPCIÓN 3: Usar D5 (disponible)
#define SERVO_PIN   6    // Servo Signal (D6 - disponible)

Servo servoZ;

// ===== CONSTANTES DEL MOTOR =====
#define STEP_ANGLE 1.8                  // Motor bipolar 1.8°
#define STEPS_PER_REV (360 / STEP_ANGLE) // 200 pasos por revolución
#define DISTANCE_PER_STEP 0.254         // 0.254mm por paso
#define MAX_STROKE 80.01                // Carrera máxima en mm

// ===== VELOCIDADES OPTIMIZADAS =====
#define SPEED_VERY_SLOW 50   // ms (20 Hz)   - Precisión máxima
#define SPEED_SLOW      30   // ms (33 Hz)   - Trabajo fino
#define SPEED_NORMAL    15   // ms (67 Hz)   - RECOMENDADO ⭐
#define SPEED_FAST      8    // ms (125 Hz)  - Rápido
#define SPEED_VERY_FAST 5    // ms (200 Hz)  - Límite seguro

// ===== PWM PARA CORRIENTE LIMITADA =====
#define PWM_CURRENT_LIMIT 200  // 78% of 255 (reduce heat)

// ===== VARIABLES GLOBALES =====
volatile long pos_x = 0;       // Posición X en pasos
volatile long pos_y = 0;       // Posición Y en pasos
volatile int pos_z = 90;       // Ángulo servo

int current_speed = SPEED_NORMAL;
unsigned long last_step_time = 0;
unsigned long last_display_time = 0;

volatile int move_x = 0;       // -1, 0, 1
volatile int move_y = 0;       // -1, 0, 1
volatile int move_z = 0;       // -1, 0, 1

// Secuencias de stepping para motor bipolar 4 hilos
// Bits: [Q3:M2B, Q2:M2A, Q1:M1B, Q0:M1A]
// Half-stepping (8 pasos suave) en lugar de full-stepping (4 pasos)

const byte step_sequence[8] = {
  0b0001,  // 0: M1A ON,  M1B OFF,  M2A OFF,  M2B OFF
  0b0011,  // 1: M1A ON,  M1B ON,   M2A OFF,  M2B OFF
  0b0010,  // 2: M1A OFF, M1B ON,   M2A OFF,  M2B OFF
  0b0110,  // 3: M1A OFF, M1B ON,   M2A ON,   M2B OFF
  0b0100,  // 4: M1A OFF, M1B OFF,  M2A ON,   M2B OFF
  0b1100,  // 5: M1A OFF, M1B OFF,  M2A ON,   M2B ON
  0b1000,  // 6: M1A OFF, M1B OFF,  M2A OFF,  M2B ON
  0b1001   // 7: M1A ON,  M1B OFF,  M2A OFF,  M2B ON
};

byte step_index = 0;

// Límites calibrados
long x_min = 0;
long x_max = (long)(MAX_STROKE / DISTANCE_PER_STEP);  // ~315 pasos
long y_min = 0;
long y_max = (long)(MAX_STROKE / DISTANCE_PER_STEP);  // ~315 pasos

// ===== SETUP =====
void setup() {
  // Serial comunicación
  Serial.begin(9600);
  delay(100);
  
  // Configurar pines como OUTPUT
  pinMode(DIR_SER, OUTPUT);
  pinMode(DIR_CLK, OUTPUT);
  pinMode(DIR_LATCH, OUTPUT);
  pinMode(DIR_EN, OUTPUT);
  
  pinMode(MOTOR_1_PWM, OUTPUT);
  pinMode(MOTOR_2_PWM, OUTPUT);
  
  pinMode(IN2, OUTPUT);
  pinMode(IN4, OUTPUT);
  
  // Inicializar shift register
  digitalWrite(DIR_SER, LOW);
  digitalWrite(DIR_CLK, LOW);
  digitalWrite(DIR_LATCH, LOW);
  digitalWrite(DIR_EN, LOW);    // Enable shift register (activo bajo)
  
  // PWM para control de corriente
  analogWrite(MOTOR_1_PWM, PWM_CURRENT_LIMIT);
  analogWrite(MOTOR_2_PWM, PWM_CURRENT_LIMIT);
  
  // Detener motores
  stop_motors();
  
  // Configurar servo
  servoZ.attach(SERVO_PIN);
  servoZ.write(90);
  delay(200);
  
  // Mensaje inicial
  Serial.println("===== CNC SYSTEM INITIALIZED =====");
  Serial.println("Shield: Motor Shield V1");
  Serial.println("Motors: 4-Wire Bipolar (1.8°)");
  Serial.println("Driver: L293D + 74HC595");
  Serial.println("Ready for commands...");
  Serial.print("Speed: ");
  print_speed_mode();
  Serial.println("=================================\n");
}

// ===== LOOP PRINCIPAL =====
void loop() {
  unsigned long now = millis();
  
  // Control de timing (crítico para precisión)
  if (now - last_step_time >= current_speed) {
    last_step_time = now;
    
    // Procesar movimiento XY
    if (move_x != 0 || move_y != 0) {
      
      // Verificar límites
      if ((move_x != 0 && can_move_x(move_x)) || 
          (move_y != 0 && can_move_y(move_y))) {
        
        // Avanzar o retroceder en la secuencia
        if (move_x > 0) {
          step_index++;
          pos_x++;
        }
        else if (move_x < 0) {
          step_index--;
          pos_x--;
        }
        
        if (move_y > 0) {
          step_index++;
          pos_y++;
        }
        else if (move_y < 0) {
          step_index--;
          pos_y--;
        }
        
        // Mantener dentro del rango 0-7
        step_index = step_index % 8;
        
        // Enviar comando al shift register
        shift_register_write(step_sequence[step_index]);
        
      } else {
        // Límite alcanzado
        if (move_x != 0) {
          Serial.print("❌ LIMIT X: ");
          Serial.println(pos_x * DISTANCE_PER_STEP, 3);
          move_x = 0;
        }
        if (move_y != 0) {
          Serial.print("❌ LIMIT Y: ");
          Serial.println(pos_y * DISTANCE_PER_STEP, 3);
          move_y = 0;
        }
      }
    }
    
    // Procesar movimiento Z (servo)
    if (move_z != 0) {
      move_servo_smooth(move_z);
    }
  }
  
  // Procesar comandos serial
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command.length() > 0) {
      process_command(command);
    }
  }
  
  // Mostrar posición cada segundo
  if (now - last_display_time > 1000) {
    last_display_time = now;
    print_status();
  }
}

// ===== ESCRIBIR EN 74HC595 =====
void shift_register_write(byte data) {
  // Protocolo: RCLK bajo → shift data → RCLK alto
  
  digitalWrite(DIR_LATCH, LOW);  // Preparar latch
  
  // Enviar 8 bits (LSB primero)
  for (int i = 0; i < 8; i++) {
    // Poner bit en la línea de datos
    if (data & (1 << i)) {
      digitalWrite(DIR_SER, HIGH);
    } else {
      digitalWrite(DIR_SER, LOW);
    }
    
    // Clock pulse para desplazar el bit
    digitalWrite(DIR_CLK, HIGH);
    delayMicroseconds(5);
    digitalWrite(DIR_CLK, LOW);
    delayMicroseconds(5);
  }
  
  // Latch pulse para actualizar outputs
  digitalWrite(DIR_LATCH, HIGH);
  delayMicroseconds(5);
  digitalWrite(DIR_LATCH, LOW);
  delayMicroseconds(5);
  
  // Limpiar línea de datos
  digitalWrite(DIR_SER, LOW);
}

// ===== MOVIMIENTO SERVO SUAVE =====
void move_servo_smooth(int dir) {
  static unsigned long last_servo_move = 0;
  
  if (millis() - last_servo_move >= 20) {  // Actualizar cada 20ms
    last_servo_move = millis();
    
    int new_z = pos_z + (dir * 1);  // 1 grado por movimiento
    
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

// ===== FUNCIONES DE CONTROL =====
void stop_motors() {
  shift_register_write(0b0000);  // Todas las fases OFF
  move_x = 0;
  move_y = 0;
  Serial.println("⏹ Motors stopped");
}

void return_to_home() {
  Serial.println("🏠 Returning to home position...");
  
  unsigned long home_step_time = millis();
  
  // Retornar X a origen
  while (pos_x > 0) {
    if (millis() - home_step_time >= current_speed) {
      home_step_time = millis();
      step_index = (step_index - 1 + 8) % 8;
      shift_register_write(step_sequence[step_index]);
      pos_x--;
    }
  }
  
  // Retornar Y a origen
  while (pos_y > 0) {
    if (millis() - home_step_time >= current_speed) {
      home_step_time = millis();
      step_index = (step_index - 1 + 8) % 8;
      shift_register_write(step_sequence[step_index]);
      pos_y--;
    }
  }
  
  // Servo a posición central
  servoZ.write(90);
  pos_z = 90;
  
  Serial.println("✅ Home position reached (0,0,90°)");
}

// ===== PROCESAMIENTO DE COMANDOS =====
void process_command(String cmd) {
  
  if (cmd == "X+") {
    move_x = 1;
    move_y = 0;
    Serial.println("→ X+ : Moving right");
  }
  else if (cmd == "X-") {
    move_x = -1;
    move_y = 0;
    Serial.println("→ X- : Moving left");
  }
  else if (cmd == "Y+") {
    move_y = 1;
    move_x = 0;
    Serial.println("→ Y+ : Moving forward");
  }
  else if (cmd == "Y-") {
    move_y = -1;
    move_x = 0;
    Serial.println("→ Y- : Moving backward");
  }
  else if (cmd == "Z+") {
    move_z = 1;
    Serial.println("→ Z+ : Servo moving down (180°)");
  }
  else if (cmd == "Z-") {
    move_z = -1;
    Serial.println("→ Z- : Servo moving up (0°)");
  }
  
  else if (cmd == "STOP") {
    stop_motors();
  }
  
  else if (cmd == "SPD1") {
    current_speed = SPEED_VERY_SLOW;
    Serial.println("⚙️  SPD1: VERY SLOW (50ms - 20Hz)");
  }
  else if (cmd == "SPD2") {
    current_speed = SPEED_SLOW;
    Serial.println("⚙️  SPD2: SLOW (30ms - 33Hz)");
  }
  else if (cmd == "SPD3") {
    current_speed = SPEED_NORMAL;
    Serial.println("⚙️  SPD3: NORMAL (15ms - 67Hz) ⭐");
  }
  else if (cmd == "SPD4") {
    current_speed = SPEED_FAST;
    Serial.println("⚙️  SPD4: FAST (8ms - 125Hz)");
  }
  else if (cmd == "SPD5") {
    current_speed = SPEED_VERY_FAST;
    Serial.println("⚙️  SPD5: VERY FAST (5ms - 200Hz)");
  }
  
  else if (cmd == "HOME") {
    return_to_home();
  }
  
  else if (cmd == "CALIB_X_MIN") {
    x_min = pos_x;
    Serial.print("📍 X-MIN calibrated at ");
    Serial.print(pos_x * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_X_MAX") {
    x_max = pos_x;
    Serial.print("📍 X-MAX calibrated at ");
    Serial.print(pos_x * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_Y_MIN") {
    y_min = pos_y;
    Serial.print("📍 Y-MIN calibrated at ");
    Serial.print(pos_y * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  else if (cmd == "CALIB_Y_MAX") {
    y_max = pos_y;
    Serial.print("📍 Y-MAX calibrated at ");
    Serial.print(pos_y * DISTANCE_PER_STEP, 3);
    Serial.println(" mm");
  }
  
  else if (cmd == "RESET_LIMITS") {
    x_min = 0;
    x_max = (long)(MAX_STROKE / DISTANCE_PER_STEP);
    y_min = 0;
    y_max = (long)(MAX_STROKE / DISTANCE_PER_STEP);
    Serial.println("🔄 Limits reset to default (80mm x 80mm)");
  }
  
  else if (cmd == "INFO") {
    print_info();
  }
  
  else if (cmd == "STATUS") {
    print_status();
  }
  
  else if (cmd == "TEST_MOTOR_1") {
    Serial.println("🧪 Testing Motor 1...");
    for (int i = 0; i < 20; i++) {
      step_index++;
      step_index = step_index % 8;
      shift_register_write(step_sequence[step_index]);
      delay(50);
    }
    stop_motors();
  }
  
  else if (cmd == "TEST_MOTOR_2") {
    Serial.println("🧪 Testing Motor 2...");
    for (int i = 0; i < 20; i++) {
      step_index++;
      step_index = step_index % 8;
      shift_register_write(step_sequence[step_index]);
      delay(50);
    }
    stop_motors();
  }
  
  else if (cmd == "TEST_SERVO") {
    Serial.println("🧪 Testing Servo...");
    servoZ.write(0);
    delay(500);
    servoZ.write(90);
    delay(500);
    servoZ.write(180);
    delay(500);
    servoZ.write(90);
  }
  
  else {
    Serial.print("❌ Unknown command: ");
    Serial.println(cmd);
    Serial.println("   Try: X+, X-, Y+, Y-, Z+, Z-, SPD1-5, HOME, INFO, STATUS");
  }
}

// ===== FUNCIONES DE INFORMACIÓN =====
void print_status() {
  Serial.print("📍 POS: X=");
  Serial.print(pos_x * DISTANCE_PER_STEP, 3);
  Serial.print("mm Y=");
  Serial.print(pos_y * DISTANCE_PER_STEP, 3);
  Serial.print("mm Z=");
  Serial.print(pos_z);
  Serial.println("°");
  
  Serial.print("⚙️  Limits: X=(");
  Serial.print(x_min * DISTANCE_PER_STEP, 1);
  Serial.print("-");
  Serial.print(x_max * DISTANCE_PER_STEP, 1);
  Serial.print(") Y=(");
  Serial.print(y_min * DISTANCE_PER_STEP, 1);
  Serial.print("-");
  Serial.print(y_max * DISTANCE_PER_STEP, 1);
  Serial.println(")");
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
      Serial.println("NORMAL (15ms) ⭐");
      break;
    case SPEED_FAST:
      Serial.println("FAST (8ms)");
      break;
    case SPEED_VERY_FAST:
      Serial.println("VERY FAST (5ms)");
      break;
  }
}

void print_info() {
  Serial.println("\n╔═════════════════════════════════════╗");
  Serial.println("║      CNC MOTOR SHIELD V1 SYSTEM    ║");
  Serial.println("╚═════════════════════════════════════╝\n");
  
  Serial.println("🔧 HARDWARE:");
  Serial.println("   Motor: 4-Wire Bipolar Stepper (1.8°)");
  Serial.println("   Driver: Motor Shield V1 (L293D/L298N)");
  Serial.println("   Resolution: 0.254mm per step");
  Serial.println("   Max Stroke: ~80mm per axis");
  Serial.println("   Servo: SG90 (0-180°)");
  
  Serial.println("\n⌨️  COMMANDS:");
  Serial.println("   X+/X- : Move X axis (left/right)");
  Serial.println("   Y+/Y- : Move Y axis (fwd/back)");
  Serial.println("   Z+/Z- : Move servo (down/up)");
  Serial.println("   SPD1-5 : Speed (1=slow, 5=fast)");
  Serial.println("   HOME   : Return to origin");
  Serial.println("   CALIB_X_MIN/MAX : Calibrate X limits");
  Serial.println("   CALIB_Y_MIN/MAX : Calibrate Y limits");
  Serial.println("   RESET_LIMITS    : Reset to 80x80mm");
  Serial.println("   STATUS : Show current position");
  Serial.println("   TEST_MOTOR_1 : Test Motor 1");
  Serial.println("   TEST_MOTOR_2 : Test Motor 2");
  Serial.println("   TEST_SERVO   : Test Servo");
  Serial.println("   INFO   : Show this info");
  Serial.println("   STOP   : Stop all motors\n");
}

/*
NOTAS IMPORTANTES SOBRE MOTOR SHIELD V1:
═════════════════════════════════════════

1. PINES DEL SHIELD:
   - D4:  DIR_CLK  (Shift Register Clock)
   - D7:  DIR_EN   (Shift Register Enable - activo bajo)
   - D8:  DIR_SER  (Shift Register Serial Data)
   - D9:  Motor 2 PWM (Enable Motor 2 / Servo 2)
   - D10: Motor 1 PWM (Enable Motor 1 / Servo 1)
   - D11: IN2 (Dirección Motor 1)
   - D12: DIR_LATCH (Shift Register Latch)
   - D13: IN4 (Dirección Motor 2)

2. MOTOR CONEXIÓN:
   - Motor 1: M1 y M2 (OUT1 y OUT2 del L293D)
   - Motor 2: M3 y M4 (OUT3 y OUT4 del L293D)
   - Con 4 líneas (sin común) cada motor usa 2 líneas

3. SERVO CONEXIÓN:
   - Opción 1: Usar D10 (si no usas Motor 1 PWM)
   - Opción 2: Usar D9  (si no usas Motor 2 PWM)
   - Opción 3: Usar D6, D5, D3 (pines libres con PWM)
   - NOTA: En este código usamos D6

4. SHIFT REGISTER:
   - Q0: M1A (OUT1)
   - Q1: M1B (OUT2)
   - Q2: M2A (OUT3)
   - Q3: M2B (OUT4)
   - Protocolo: bit a bit, LSB primero

5. VELOCIDADES RECOMENDADAS:
   - SPD3 (15ms) es el mejor balance
   - Motor bipolar 1.8° = 200 pasos/revolución
   - Half-stepping (8 secuencias) = suave

6. CALIBRACIÓN:
   - Mover manual a X-MIN, ejecutar CALIB_X_MIN
   - Mover manual a X-MAX, ejecutar CALIB_X_MAX
   - Mismo para Y-MIN y Y-MAX
   - RESET_LIMITS vuelve a 80mm x 80mm

7. TROUBLESHOOTING:
   - Motor no se mueve: Verificar D4, D7, D8, D12
   - Motor muy débil: Aumentar corriente (PWM > 200)
   - Servo no responde: Verificar que D6 sea PWM capaz
   - Posición incorrecta: Revisar limitaciones de pasos
*/
