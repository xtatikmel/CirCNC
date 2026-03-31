# Optimización de CNC_code.ino

El firmware actual de `CNC_code.ino` es funcional porque utiliza la famosa y robusta librería `AF_Stepper` de Adafruit que asegura compatibilidad eléctrica con tu Motor Shield. Sin embargo, su limitación principal es que genera cortes con forma de "escalera" y está configurado de fábrica para otro modelo de motores (tipo DVD / Nema de 4096 pasos).

## User Review Required
> [!IMPORTANT]
> - Se reemplazará la función `moveTo` que se mueve de a "un eje a la vez" por el algoritmo matemático **Bresenham**, que permitirá a la máquina dibujar esquinas suaves y curvas exactas, ya que entrelazará un paso del motor X con un paso del motor Y en diagonales al mismo tiempo.
> - Voy a ajustar la escala para Motores Paso a Paso de 18°. Originalmente el código los consideraba de 4096 y ahora pasarán a **20 pasos por revolución** (360/18=20). 
> - ¿Estás de acuerdo con aplicar estos ajustes matemáticos y reemplazar tus valores actuales de `StepsPerMillimeterX / Y` (200.0) correspondientemente?

## Proposed Changes

### Componente CNC_code

#### [MODIFY] [CNC_code.ino](file:///E:/GIT/CNC-GCTRL-L293/CNC_code/CNC_code.ino)

Se harán 3 cambios puntuales:
1. **Ajustar Constantes:** Actualizar `stepsPerRevolution` a 20.
2. **Ajustar Macro de Paso:** Cambiar de `MICROSTEP` temporalmente a `SINGLE` o `DOUBLE` (los motores de 18° tipo CD/DVD sufren usando MICROSTEP porque pierden mucho torque y a veces no se mueven).
3. **Optimizar Trazado (MoveTo):** Reescribir por completo la función `moveTo` para aplicar el algoritmo interpolador de Bresenham: calcular la diferencia `X` e `Y`, y enviar pulsos de a 1 step compartidos equitativamente para no perder simultaneidad.
4. **Simplificar buffer Serial:** Se optimizará el retraso en la lectura del comando.

## Open Questions

- Tu servo actual está conectado al pin 10 (`penServoPin = 10`), las alturas son `Up = 115` y `Down = 83`. ¿Mantenemos estas configuraciones inalteradas para el Servo MG90?
- La librería AFMotor a veces es un poco lenta. Con motores de 18° querrás que avance suficientemente rápido, ¿te parece bien que cambiemos el modo de movimiento de `MICROSTEP` (que resta potencia en motores modelo 9294) a `SINGLE` (puro y con máximo torque)?

## Verification Plan

### Automated Tests
- Compilar el código para garantizar la sintaxis en C++.

### Manual Verification
- Cargar `.ino` modificado en tu Arduino UNO.
- Enviar un G-Code que dibuje una diagonal, ejemplo: `G1 X10 Y10`.
- Observar que **ambos motores (X e Y) suenen y se activen al mismo tiempo**, terminando en el punto exacto deseado.
