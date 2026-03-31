/*
=====================================
TEST DE LÍMITES COMPLETO - Motor Shield L293D
Descubre las limitaciones reales de X, Y y del Servo Z
=====================================
*/

#include <AFMotor.h>
#include <Servo.h>

// Definición de Motores y Pines
AF_Stepper motorX(20, 1);    // Eje X en M1 y M2 (20 pasos por rev)
AF_Stepper motorY(20, 2);    // Eje Y en M3 y M4 (20 pasos por rev)

Servo servoZ;
Servo servoZ2;               // Segundo conector del shield
int SERVO_PIN = 10;          // Pin 10 (SERVO_1)
int SERVO2_PIN = 9;          // Pin 9 (SERVO_2)

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== L293D FULL STRESS TEST ==="));
  Serial.println(F("Asegúrate de no tener conectada temporalmente la app de Python."));
  Serial.println();
  
  servoZ.attach(SERVO_PIN);
  servoZ2.attach(SERVO2_PIN);
  
  // Test 1: Mapeo de Ambos Servos
  Serial.println(F("TEST 1: Mapeo de Motores Servo (Ambos Canales)"));
  testServo();
  
  delay(3000);
  
  // Test 2: Velocidad Máxima X e Y
  Serial.println(F("\nTEST 2: Velocidad Máxima Eje X"));
  testMaxSpeed(motorX, "X");
  
  delay(2000);
  
  Serial.println(F("\nTEST 3: Velocidad Máxima Eje Y"));
  testMaxSpeed(motorY, "Y");
  
  delay(2000);
  
  // Test 4: Pérdida de Pasos
  Serial.println(F("\nTEST 4: Pérdida de Pasos Eje X"));
  testStepLoss(motorX, "X");
  
  delay(2000);

  Serial.println(F("\nTEST 5: Pérdida de Pasos Eje Y"));
  testStepLoss(motorY, "Y");
  
  delay(2000);
  
  // Test 6: Temperatura simulando movimiento diagonal
  Serial.println(F("\nTEST 6: Autodiagnóstico de Temperatura (60 seg)"));
  Serial.println(F("TOCA el chip negro L293D del CNC Shield cada 10 segundos.\n(No toques los reguladores de voltaje, toca el cuadrado con muchas patas)"));
  testTemperature();
  
  Serial.println(F("\n=== DIAGNÓSTICO COMPLETO ==="));
}

void loop() {
  // El test corre una sola vez en setup()
}

// -------------------------------------------------------------
// FUNCIONES DE TESTEO
// -------------------------------------------------------------

void testServo() {
  Serial.println(F("Moviendo SERVO_1 (Pin 10) y SERVO_2 (Pin 9) de 0 a 180 grados..."));
  
  int testAngles[] = {0, 30, 60, 90, 120, 150, 180};
  
  for(int i = 0; i < 7; i++) {
    int angle = testAngles[i];
    Serial.print(F("  Acomodando ambos a "));
    Serial.print(angle);
    Serial.println(F(" grados..."));
    
    servoZ.write(angle);
    servoZ2.write(angle);
    delay(1500); 
  }
  
  Serial.println(F("\n-- Prueba de Movimiento Típico --"));
  Serial.println(F("  Posición Baja (40 grados)"));
  servoZ.write(40);
  servoZ2.write(40);
  delay(2000);
  Serial.println(F("  Posición Alta (90 grados)"));
  servoZ.write(90);
  servoZ2.write(90);
  delay(2000);
  
  Serial.println(F("\n¿Ambos funcionaron correctamente sin tironear en exceso la corriente de la placa?"));
}

void testMaxSpeed(AF_Stepper &motor, String motorName) {
  Serial.println(F("Probando escalada de velocidades (RPM):"));
  
  // Rango típico de prueba para motores DVD de pasos pequeños
  int speeds[] = {20, 60, 100, 150, 250}; 
  
  for (int i = 0; i < 5; i++) {
    int rpm = speeds[i];
    motor.setSpeed(rpm);
    
    Serial.print(F("  "));
    Serial.print(rpm);
    Serial.print(F(" RPM: "));
    
    unsigned long start = millis();
    motor.step(100, FORWARD, MICROSTEP);
    motor.step(100, BACKWARD, MICROSTEP);
    unsigned long duration = millis() - start;
    
    Serial.print(duration);
    Serial.print(F(" ms total "));
    
    if (duration > 6000) {
      Serial.println(F(" - LENTO (Buen torque)"));
    } else if (duration > 2000) {
      Serial.println(F(" - ÓPTIMO (Balance vel/torque)"));
    } else {
      Serial.println(F(" - RÁPIDO (Precaución: Motor puede patinar)"));
    }
    
    delay(1000);
  }
} 

void testStepLoss(AF_Stepper &motor, String motorName) {
  Serial.print(F("Moviendo Eje "));
  Serial.print(motorName);
  Serial.println(F(" 1000 pasos ida y 1000 pasos vuelta..."));
  Serial.println(F("--> MARCA LA POSICIÓN DEL LÁPIZ AHORA CON TU DEDO O UN MARCADOR (Tienes 5 segundos)..."));
  
  delay(5000);
  
  motor.setSpeed(80); // Velocidad segura
  
  // Ir
  Serial.println(F("  Ida..."));
  for (int i = 0; i < 10; i++) {
    motor.step(100, FORWARD, MICROSTEP);
    delay(100);
  }
  
  delay(1000);
  
  // Volver
  Serial.println(F("  Vuelta..."));
  for (int i = 0; i < 10; i++) {
    motor.step(100, BACKWARD, MICROSTEP);
    delay(100);
  }
  
  Serial.println(F("\n¿Volvió EXACTAMENTE a tu marca inicial?"));
  Serial.println(F("  SÍ = Motores bien calibrados, cero pérdida"));
  Serial.println(F("  NO = Patina. Debes lubricar la varilla roscada o bajar la velocidad (RPM) de este eje."));
}

void testTemperature() {
  motorX.setSpeed(60);
  motorY.setSpeed(60);
  
  for (int sec = 0; sec < 60; sec++) {
    // Simula imprimir un pequeño cuadrado o diagonal constantemente
    motorX.step(10, FORWARD, MICROSTEP);
    motorY.step(10, FORWARD, MICROSTEP);
    delay(50);
    motorX.step(10, BACKWARD, MICROSTEP);
    motorY.step(10, BACKWARD, MICROSTEP);
    delay(50);
    
    if (sec % 10 == 0) {
      Serial.print(F("  "));
      Serial.print(sec);
      Serial.println(F(" seg - Toca el chip AHORA"));
    }
  }
  
  Serial.println(F("\n¿Cómo se siente de caliente el chip negro?"));
  Serial.println(F("  Tibio (40C) = Excelente."));
  Serial.println(F("  Quema un poco al par de segundos = Límite (Común en los L293D)."));
  Serial.println(F("  Hierve al instante = PELIGRO, te sugiero pegar un mini disipador de aluminio al chip."));
}