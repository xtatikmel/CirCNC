# Plan de Implementación: Mejoras Visuales e Interfaz

Has solicitado dos excelentes características que le darán a tu controlador un aspecto más robusto y profesional: la inclusión de todas las opciones de velocidad y el **"Live Tracking"** (Seguimiento en vivo) de la trayectoria de corte/dibujo de la máquina en el simulador gráfico.

## User Review Required
> [!IMPORTANT]
> A continuación te detallo las herramientas exactas con las que modificaré el código. Revisa el plan y confírmame si estás de acuerdo con proceder.
> Toma en consideración que el "Live Tracking" usa la respuesta `MPos` o `WPos` (Posición actual) que manda el Arduino a la laptop. Si el Arduino se retrasa en contestar, verás el punto moverse de a saltos en vez de fluido.

## Proposed Changes

### Componente gctrl_redimensionable.py

#### [MODIFY] [gctrl_redimensionable.py](file:///e:/GIT/CNC-GCTRL-L293/gctrl_redimensionable.py)

Se modificarán tres secciones clave del script:

**1. Ampliación del Control de Velocidades:**
- Se actualizará el diccionario `SPEEDS` en el `GCodeController` para incluir las llaves `'muy_lento': 0.1` y `'muy_rapido': 5.0`.
- En la clase `GCodeGUI`, se modificarán y añadirán los botones faltantes en el `speed_frame` para que contenga 5 opciones en lugar de 3.

**2. Marcador Gráfico Interactivo (Punto de Tracking):**
- En `plot_gcode()`, se añadirá la instanciación de un nuevo elemento visual: un gran punto o cruz (ej. de color Magenta o Cyan) que guardaremos como la variable `self.machine_dot`.
- En el método `update_position()` que se corre en bucle cada 200 ms, se extraerán las posiciones `x` y `y` actualizadas del motor (`self.controller.position['x']`), y se usarán para mover matemáticamente a `self.machine_dot`.
- Se llamará a `self.canvas.draw_idle()` para que la pantalla refresque su posición de forma animada suave y en "Background" sin congelar tu interfaz.

## Open Questions

- Para la interfaz de velocidades, si ponemos 5 botones en fila horizontal tal vez se vea un poco apretado en la pantalla de Windows. ¿Te parece bien condensarlos juntos modificando el margen (`padx`), o prefieres que los ordene en 2 filas pequeñas?
- ¿Qué estilo quieres para el puntero de seguimiento? Te ofrezco:
  1. Un círculo Magenta grueso 🔴
  2. Una cruz Cyan brillante ❌
  (Usaremos el círculo si no especificas nada distinto).

## Verification Plan
1. Iniciar la aplicación en Python.
2. Hacer click en los nuevos botones de velocidad y verificar que el control manual (`X+`) avanza lo requerido.
3. Al enviar las coordenadas, comprobar que aparezca el punto y reaccione trazando la línea del gráfico.
