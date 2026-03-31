# Resumen de Cambios: CNC_code_optimizado.ino

Se ha creado un nuevo firmware (`E:\GIT\CNC-GCTRL-L293\CNC_code_optimizado\CNC_code_optimizado.ino`) partiendo de tu archivo base original, pero introduciendo los cambios necesarios matemáticos y de hardware para que funcione mejor en tu máquina equipada con el Driver L293D, Motores Nema Modelo 9294 (18°) y Servo SG90/MG90.

## ¿Qué se ha cambiado?

### 1. Reescritura del Matemático de Movimiento (Bresenham)
> [!IMPORTANT]
> El antiguo código usaba una lógica de "Mueve todo el motor X y luego todo el motor Y". Se ha reemplazado la función `moveTo` con el **Algoritmo de Bresenham**, el mismo que usa GRBL profesional: avanza un paso un motor, y entrelaza el otro en tiempo real para dibujar diagonales perfectas. 

### 2. Calibración de Hardware Directa
- **`stepsPerRevolution = 20;`**: Tú tienes motores de 18 grados (360º / 18º = 20 pasos para dar una vuelta completa). El código viejo lo calculaba pensando en 4096 pasos.
- **`stepType = SINGLE;`**: Cambiamos la técnica interna de control que usa la librería `AFMotor`. En lugar de tratar de hacer "micro-pasos" (lo cual reduce la fuerza dramáticamente en este tipo de chips y causa que el motor tiemble sin moverse), forzamos tracción completa (`SINGLE`).

### 3. Velocidad Compensada
- Como bajamos de 4096 a apenas 20 pasos de revolución, necesitas que el controlador le pida a los motores andar muchísimo "más rápido" en RPM para moverse la misma distancia milimétrica, por lo que hemos seteado el `setSpeed(350)` por defecto.

## Pasos para probarlo

1. Abre el archivo `E:\GIT\CNC-GCTRL-L293\CNC_code_optimizado\CNC_code_optimizado.ino` en tu **Arduino IDE**.
2. Verifica que las librerías `Servo.h` y `AFMotor.h` sigan compilandose bien (botón Visto Bueno).
3. Súbelo a tu placa Arduino.
4. Conecta en tu Software de Python y manda la orden `G1 X10 Y10` para corroborar que los motores suenan limpios y hacen una recta pura en diagonal en lugar de una escalera.

> [!TIP]
> Si lograste probarlo y sientes que el dibujo es más pequeño o más grande de lo que esperabas, tendrás que afinar la variable matemática: `float StepsPerMillimeterX = 200.0;`. Puedes medir la distancia físicamente, y aplicar una Regla de 3 simple para calcular el valor exacto para tu modelo de varilla roscada/correas.
