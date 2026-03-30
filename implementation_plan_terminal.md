# Plan de Implementación: Predicción de Tiempo y Terminal G-Code

Agregar funcionalidades de predicción del tiempo de ploteo y enviar comandos manuales (tipo consola) elevará la capacidad de tu software a un verdadero "Gcode Sender". Dado que es un cambio de estructura e interfaz, he preparado el plan.

## User Review Required
> [!IMPORTANT]
> Revisa el plan a continuación para confirmar dónde colocaré el cuadro de texto para comandos manuales y cómo calcularé el tiempo. Confírmame si el diseño te agrada.

## Proposed Changes

### 1. Sistema de Terminal Serial (Manual G-Code Entry)

#### [MODIFY] [gctrl_redimensionable.py](file:///e:/GIT/CNC-GCTRL-L293/gctrl_redimensionable.py)
**Panel de Logs:**
- Dentro del `log_frame` (que abarca la parte inferior de la ventana), debajo del gran cuadro de texto negro, añadiré un pequeño panel llamado `terminal_frame`.
- Dicho panel contendrá una barra de entrada (Entry) llamada `"Mandar comando:"` y un botón `"Enviar"`. Lo configuraré para que también escuche la tecla **[Enter]**.
- Se creará un método `send_manual_command(self)` que tomará el texto, lo enviará a `self.controller.send_command(cmd)` e imprimirá en el Log si se envió con éxito, limpiando el cuadro automáticamente.


### 2. Predictor de Tiempo de Trabajo

#### [MODIFY] [gctrl_redimensionable.py](file:///e:/GIT/CNC-GCTRL-L293/gctrl_redimensionable.py)
**Motor Matemático (`GCodeParser`):**
- Modificaré la clase para que, en lugar de calcular solo posiciones, calcule además la **distancia euclidiana** de cada línea de G-code: `√(Δx² + Δy²)`.
- Dividiré esa distancia acumulada entre la velocidad estándar del hardware de tu Arduino. Por defecto, asumiré que la máquina dibuja a `F1000` (1000 mm por minuto / 16.6 mm/segundo). 
- Añadiré una pequeña penalización de tiempo de medio segundo fijo (0.5s) por cada levantamiento de lápiz del Servo (Comandos `M300` o cambios de altura Z).

**Visualización Gráfica:**
- Añadiré un nuevo texto descriptivo en la sección inferior del panel de visualización del GCode (debajo de `Progreso`), un label verde o celeste brillante interactivo: `⏱️ Tiempo Estimado: 5 mins 30 segs`.
- Al hacer clic en "Cargar GCode", este valor se recalculará instantáneamente.

## Open Questions
- ¿A qué velocidad aproximada mueve físicamente tu máquina el lápiz cuando hace trazos rectos (en mm por minuto)? Asumiré `1000.0` si no estás seguro y podrás corregirlo más tarde si la máquina resulta ser más rápida/lenta.
- ¿Estás de acuerdo con poner la barra de entrada de manual de comandos directamente abajo del recuadro de texto del Log?

## Verification Plan
1. Abrir aplicación e insertar un pequeño G-code de prueba.
2. Comprobar que el sistema de predicción reporta el tiempo en Minutos/Segundos.
3. Ingresar comandos directos (e.g. `G1 X10 Y10`) en la barra inferior y comprobar actividad y visualización en el log de conexión.
