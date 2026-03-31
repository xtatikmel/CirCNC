/* 
CNC optimizado 
  */

#include <Servo.h>
#include <AFMotor.h>

#define LINE_BUFFER_LENGTH 1024

char STEP = MICROSTEP ;

// Servo position for Up and Down 
const int penZUp = 115;
const int penZDown = 83;

// Servo on PWM pin 10
const int penServoPin =10 ;

// Should be right for DVD steppers, but is not too important here
const int stepsPerRevolution = 4096; 

// create servo object to control a servo 
Servo penServo;  

// Initialize steppers for X- and Y-axis using this Arduino pins for the L293D H-bridge
AF_Stepper myStepperY(stepsPerRevolution,1);            
AF_Stepper myStepperX(stepsPerRevolution,2);  

/* Structures, global variables    */
struct point { 
  float x; 
  float y; 
  float z; 
};

// Current position of plothead
struct point actuatorPos;

// Drawing settings, should be OK
float StepInc = 1;
int StepDelay = 0;
int LineDelay =0;
int penDelay = 50;

// Motor steps to go 1 millimeter.
// Use test sketch to go 100 steps. Measure the length of line. 
// Calculate steps per mm. Enter here.
float StepsPerMillimeterX = 200.0;
float StepsPerMillimeterY = 200.0;

// Drawing robot limits, in mm
// OK to start with. Could go up to 50 mm if calibrated well. 
float Xmin = 0;
float Xmax = 80;
float Ymin = 0;
float Ymax = 80;
float Zmin = 0;
float Zmax = 1;

float Xpos = Xmin;
float Ypos = Ymin;
float Zpos = Zmax; 

// Set to true to get debug output.
boolean verbose = true;

// Mode flags
boolean absoluteMode = true;  // G90/G91 mode
boolean isMoving = false;     // Track if motors are moving

//  Needs to interpret 
//  G1 for moving
//  G4 P300 (wait 150ms)
//  M300 S30 (pen down)
//  M300 S50 (pen up)
//  Discard anything with a (
//  Discard any other command!

/**********************
 * void setup() - Initialisations
 ***********************/
void setup() {
  //  Setup
  Serial.begin(9600);
  
  penServo.attach(penServoPin);
  penServo.write(penZUp);
  delay(100);

  // Set motor speeds - reduced for better control
  myStepperX.setSpeed(500);
  myStepperY.setSpeed(500);  
  
  // Initialize position
  actuatorPos.x = Xmin;
  actuatorPos.y = Ymin;
  actuatorPos.z = Zmax;

  //  Notifications!!!
  Serial.println("Mini CNC Plotter ready!");
  Serial.print("X range: "); 
  Serial.print(Xmin); 
  Serial.print(" to "); 
  Serial.print(Xmax); 
  Serial.println(" mm"); 
  Serial.print("Y range: "); 
  Serial.print(Ymin); 
  Serial.print(" to "); 
  Serial.print(Ymax); 
  Serial.println(" mm"); 
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
      Serial.println("ok");
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
  }
  else {
    Serial.println("ok"); // Acknowledge other commands
  }
}

void moveTo(float x, float y) {
  if (isMoving) return; // Prevent multiple movements
  isMoving = true;
  
  // Calculate steps needed
  long xSteps = (x - actuatorPos.x) * StepsPerMillimeterX;
  long ySteps = (y - actuatorPos.y) * StepsPerMillimeterY;
  
  // Move X axis
  if (xSteps != 0) {
    if (xSteps > 0) {
      myStepperX.step(xSteps, FORWARD, MICROSTEP);
    } else {
      myStepperX.step(-xSteps, BACKWARD, MICROSTEP);
    }
    delay(10); // Small delay between axes
  }
  
  // Move Y axis
  if (ySteps != 0) {
    if (ySteps > 0) {
      myStepperY.step(ySteps, FORWARD, MICROSTEP);
    } else {
      myStepperY.step(-ySteps, BACKWARD, MICROSTEP);
    }
  }
  
  // Update position
  actuatorPos.x = x;
  actuatorPos.y = y;
  
  // Send position report
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
  if (verbose) { 
    Serial.println("Pen up!"); 
  } 
}
//  Lowers pen
void penDown() { 
  penServo.write(penZDown); 
  actuatorPos.z = Zmin;
  delay(penDelay); 
  if (verbose) { 
    Serial.println("Pen down."); 
  } 
}
