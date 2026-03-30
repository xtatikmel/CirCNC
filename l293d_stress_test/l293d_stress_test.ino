/*
=====================================
TEST DE LÍMITES - Motor Shield L293D
Descubre las limitaciones reales
=====================================
*/

#include <AFMotor.h>

AF_Stepper motorX(20, 1);
AF_Stepper motorY(20, 2);

void setup() {
  Serial.begin(115200);
  Serial.println(F("=== L293D STRESS TEST ==="));
  Serial.println();
  
  // Test 1: Velocidad máxima
  Serial.println(F("TEST 1: Velocidad máxima"));
  testMaxSpeed();
  
  delay(2000);
  
  // Test 2: Temperatura
  Serial.println(F("\nTEST 2: Temperatura (60 seg)"));
  Serial.println(F("TOCA el L293D cada 10 segundos"));
  testTemperature();
  
  delay(2000);
  
  // Test 3: Pérdida de pasos
  Serial.println(F("\nTEST 3: Pérdida de pasos"));
  testStepLoss();
  
  Serial.println(F("\n=== TESTS COMPLETOS ==="));
  printRecommendations();
}

void loop() {
  // Nada
}

void testMaxSpeed() {
  Serial.println(F("Probando velocidades (RPM):"));
  
  int speeds[] = {10, 30, 60, 100, 150, 200};
  
  for (int i = 0; i < 6; i++) {
    int rpm = speeds[i];
    motorX.setSpeed(rpm);
    
    Serial.print(F("  "));
    Serial.print(rpm);
    Serial.print(F(" RPM: "));
    
    unsigned long start = millis();
    motorX.step(100, FORWARD, MICROSTEP);
    unsigned long duration = millis() - start;
    
    Serial.print(duration);
    Serial.print(F(" ms para 100 pasos"));
    
    if (duration > 5000) {
      Serial.println(F(" - LENTO"));
    } else if (duration > 2000) {
      Serial.println(F(" - OK"));
    } else {
      Serial.println(F(" - RÁPIDO (posible pérdida)"));
    }
    
    delay(1000);
  }
}

void testTemperature() {
  motorX.setSpeed(80);
  motorY.setSpeed(80);
  
  for (int sec = 0; sec < 60; sec++) {
    motorX.step(10, FORWARD, MICROSTEP);
    motorY.step(10, FORWARD, MICROSTEP);
    delay(100);
    motorX.step(10, BACKWARD, MICROSTEP);
    motorY.step(10, BACKWARD, MICROSTEP);
    delay(100);
    
    if (sec % 10 == 0) {
      Serial.print(F("  "));
      Serial.print(sec);
      Serial.println(F(" seg - Toca el chip AHORA"));
    }
  }
  
  Serial.println(F("\n¿Cómo está la temperatura?"));
  Serial.println(F("  Tibio (40°C) = OK"));
  Serial.println(F("  Caliente (60°C) = Límite"));
  Serial.println(F("  MUY caliente (80°C+) = PELIGRO"));
}

void testStepLoss() {
  Serial.println(F("Moviendo 1000 pasos ida y vuelta..."));
  Serial.println(F("MARCA la posición inicial con lápiz"));
  
  delay(5000);
  
  motorX.setSpeed(80);
  
  // Ir
  for (int i = 0; i < 10; i++) {
    motorX.step(100, FORWARD, MICROSTEP);
    delay(100);
  }
  
  delay(2000);
  
  // Volver
  for (int i = 0; i < 10; i++) {
    motorX.step(100, BACKWARD, MICROSTEP);
    delay(100);
  }
  
  Serial.println(F("\n¿Volvió EXACTAMENTE a la marca?"));
  Serial.println(F("  SÍ = Sin pérdida de pasos"));
  Serial.println(F("  NO = Ajustar velocidad/corriente"));
}

void printRecommendations() {
  Serial.println(F("\n============================="));
  Serial.println(F("RECOMENDACIONES PARA L293D:"));
  Serial.println(F("============================="));
  Serial.println(F("✅ Velocidad segura: 60-80 RPM"));
  Serial.println(F("✅ Uso continuo: <30 minutos"));
  Serial.println(F("✅ Aplicaciones: Plotter papel"));
  Serial.println(F("⚠️  NO usar para mecanizado"));
  Serial.println(F("⚠️  Agregar disipador si >60°C"));
  Serial.println(F(""));
  Serial.println(F("UPGRADE PATH:"));
  Serial.println(F("1. Software GRBL-like ($0)"));
  Serial.println(F("2. CNC Shield + DRV8825 ($15)"));
  Serial.println(F("3. NEMA 17 motors ($40)"));
}

/*
RESULTADOS ESPERABLES:

L293D con motores DVD:
━━━━━━━━━━━━━━━━━━━━
✅ 60 RPM: Perfecto
⚠️ 100 RPM: Posible pérdida
❌ 150+ RPM: Definitivamente pierde pasos

Temperatura:
━━━━━━━━━━━━━━━━━━━━
10 min: ~45°C (OK)
30 min: ~65°C (Límite)
60 min: ~85°C (Apagar)

CONCLUSIÓN:
L293D es suficiente para PLOTTER
NO es suficiente para CNC de mecanizado
*/