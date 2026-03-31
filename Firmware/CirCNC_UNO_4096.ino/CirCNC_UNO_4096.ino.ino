/* 
  CirCNC - Firmware Optimizado (Bresenham)
  Motores: 18° (Modelo 9294) | Servo: MG90
  Concepto: Transformación y Control.
*/

#include <Servo.h>
#include <AFMotor.h>

#define LINE_BUFFER_LENGTH 1024

// Motores de 18° tienen 20 pasos por revolución (360/18 = 20)
// Originalmente estaba en 4096 (motores tipo DVD)
const int stepsPerRevolution = 20; 

// Cambiamos a SINGLE para maximizar el torque en motores Nema 9294.
// MICROSTEP los haría perder fuerza.
int stepType = SINGLE; 

// Posiciones del Servo MG90 (Up and Down)
const int penZUp = 115;
const int penZDown = 83;

// Servo on PWM pin 10
const int penServoPin = 10;

// Initialize steppers for X- and Y-axis using AFMotor
AF_Stepper myStepperY(stepsPerRevolution, 1);            
AF_Stepper myStepperX(stepsPerRevolution, 2);  

Servo penServo;  

struct point { 
  float x; 
  float y; 
  float z; 
};

// Current position of plothead
struct point actuatorPos;

// Motor steps to go 1 millimeter.
// Dejamos 200.0 como en el original, pero SI LA MÁQUINA CORTA MÁS DISTANCIA 
// de la indicada, DEBES REDUCIR ESTE VALOR. (Ej: 39.37 es común en motores 18°)
float StepsPerMillimeterX = 35.56;
float StepsPerMillimeterY = 35.56;

// Drawing robot limits, in mm
float Xmin = 0;
float Xmax = 40;
float Ymin = 0;
float Ymax = 40;
float Zmin = 0;
float Zmax = 1;

int penDelay = 50;

// Mode flags
boolean absoluteMode = true;  // G90/G91 mode
boolean isMoving = false;     // Track if motors are moving

/**********************
 * void setup() - Initialisations
 ***********************/
void setup() {
  Serial.begin(9600);
  
  penServo.attach(penServoPin);
  penServo.write(penZUp);
  delay(100);

  // Set motor speeds - Las RPM (revoluciones por minuto)
  // Como bajamos los stepsPerRevolution a 20, necesitamos un RPM alto para 
  // que gire apropiadamente. 350 es un buen equilibrio para torque/velocidad media.
  myStepperX.setSpeed(350);
  myStepperY.setSpeed(350);  
  
  // Initialize position
  actuatorPos.x = Xmin;
  actuatorPos.y = Ymin;
  actuatorPos.z = Zmax;

  //  Notifications!!!
  Serial.println("🪄 CirCNC (Bresenham Optimized) ready!");
  Serial.print("X range: "); 
  Serial.print(Xmin); Serial.print(" to "); Serial.print(Xmax); Serial.println(" mm"); 
  Serial.print("Y range: "); 
  Serial.print(Ymin); Serial.print(" to "); Serial.print(Ymax); Serial.println(" mm"); 
}

/**********************
 * void loop() - Main loop
 ***********************/
void loop() 
{
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.length() > 0) {
      processCommand(command);
    }
  }
}

void processCommand(String command) {
  if (command.startsWith("G90")) {
    absoluteMode = true;
    Serial.println("ok");
    return;
  }
  else if (command.startsWith("G91")) {
    absoluteMode = false;
    Serial.println("ok");
    return;
  }
  else if (command.startsWith("G1") || command.startsWith("G0")) {
    float x = actuatorPos.x;
    float y = actuatorPos.y;
    
    // Parse X coordinate
    int xIndex = command.indexOf('X');
    if (xIndex != -1) {
      float xValue = command.substring(xIndex + 1).toFloat();
      if (absoluteMode) {
        x = xValue;
      } else {
        x += xValue;
      }
    }
    
    // Parse Y coordinate
    int yIndex = command.indexOf('Y');
    if (yIndex != -1) {
      float yValue = command.substring(yIndex + 1).toFloat();
      if (absoluteMode) {
        y = yValue;
      } else {
        y += yValue;
      }
    }
    
    // Check limits
    if (x >= Xmin && x <= Xmax && y >= Ymin && y <= Ymax) {
      moveTo(x, y);
      Serial.println("ok");
    } else {
      Serial.println("error: Position out of bounds");
    }
  }
  else if (command.startsWith("M300")) {
    // Handle pen up/down commands
    if (command.indexOf("S30") != -1) {
      penDown();
      Serial.println("ok");
    }
    else if (command.indexOf("S50") != -1) {
      penUp();
      Serial.println("ok");
    }
    else {
      // Si mandan un M300 S<angulo> distinto
      int sIndex = command.indexOf('S');
      if (sIndex != -1) {
        int angle = command.substring(sIndex + 1).toInt();
        penServo.write(angle);
        delay(penDelay);
        Serial.println("ok");
      }
    }
  }
  else {
    Serial.println("ok"); // Acknowledge other commands
  }
}

/**********************
 * void moveTo() - ALGORITMO BRESENHAM
 * (Matemática real para sincronía y cero efecto escalera)
 ***********************/
void moveTo(float x, float y) {
  if (isMoving) return; 
  isMoving = true;
  
  // Calcular los pasos requeridos para cada eje
  long stepsX = (x - actuatorPos.x) * StepsPerMillimeterX;
  long stepsY = (y - actuatorPos.y) * StepsPerMillimeterY;
  
  long absX = abs(stepsX);
  long absY = abs(stepsY);
  
  int dirX = stepsX > 0 ? FORWARD : BACKWARD;
  int dirY = stepsY > 0 ? FORWARD : BACKWARD;
  
  long over = 0; // Error / acumlador
  
  // MOTOR X DOMINA EL BRESENHAM
  if (absX >= absY) {
    for (long i = 0; i < absX; i++) {
        myStepperX.onestep(dirX, stepType); // Eje X avanza +1
        over += absY;
        if (over >= absX) {
            over -= absX;
            myStepperY.onestep(dirY, stepType); // Eje Y acompaña cuanda sea momento
        }
        delayMicroseconds(2000); // Pequeñisma pausa (sin bloquear) que AFmotor no incluye y evita tirones
    }
  } 
  // MOTOR Y DOMINA EL BRESENHAM
  else {
    for (long i = 0; i < absY; i++) {
        myStepperY.onestep(dirY, stepType); // Eje Y avanza +1
        over += absX;
        if (over >= absY) {
            over -= absY;
            myStepperX.onestep(dirX, stepType); // Eje X acompaña cuanda sea momento
        }
        delayMicroseconds(2000); 
    }
  }
  
  // Update position actual
  actuatorPos.x = x;
  actuatorPos.y = y;
  
  // Send position report FORMATO GRBL para máxima compatibilidad
  Serial.print("<Idle|MPos:");
  Serial.print(actuatorPos.x);
  Serial.print(",");
  Serial.print(actuatorPos.y);
  Serial.print(",");
  Serial.print(actuatorPos.z);
  Serial.println("|FS:0,0>");
  
  isMoving = false;
}

//  Raises pen
void penUp() { 
  penServo.write(penZUp); 
  actuatorPos.z = Zmax;
  delay(penDelay); 
}

//  Lowers pen
void penDown() { 
  penServo.write(penZDown); 
  actuatorPos.z = Zmin;
  delay(penDelay); 
}
