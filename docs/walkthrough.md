# Guía de Evolución: CirCNC 🪄

El proyecto ha completado su fase de transformación, adoptando el nombre definitivo de **CirCNC** y añadiendo capacidades de configuración dinámica para diferentes tipos de hardware.

## Cambios Clave Realizados

### 1. Identidad Visual (CirCNC)
- **Branding**: Se actualizó el nombre en todas las interfaces de usuario, logs de terminal y archivos de documentación.
- **Logotipo**: Integración del isologotipo en la esquina superior derecha y configuración del icono de la aplicación.
- **Arte ASCII**: Limpieza de errores de sintaxis y actualización del mensaje de bienvenida.

### 2. Control de Perfiles de Motor (Nuevo)
> [!TIP]
> Ahora puedes alternar entre diferentes máquinas sin tocar el código.
- **Selector de Perfiles**: Añadido un menú desplegable en la interfaz para elegir entre:
    - **80mm (Nema 9294)**: Para desplazamientos largos y precisos.
    - **40mm (DVD Stepper)**: Para el prototipo mini basado en lectoras de CD/DVD.
- **Límites Dinámicos**: Al cambiar el perfil, el software actualiza automáticamente los límites de movimiento y la visualización en el gráfico (recuadro rojo).

### 3. Firmware Optimizado (V1.1)
- **Límites por Defecto**: Actualizados a 80x80mm para coincidir con el hardware principal.
- **Respuesta Serial**: Mensaje de inicio actualizado a "CirCNC ready!".
- **Algoritmo de Bresenham**: Movimientos diagonales suaves y sincronizados.

## Verificación del Sistema

### Software (Python)
1. Inicia `gctrl_redimensionable.py`.
2. Observa el título "**CirCNC**" y el logotipo.
3. Cambia el **Perfil Motor** y verifica que el recuadro rojo en el gráfico se ajuste (80mm o 40mm).
4. El log confirmará: `📍 Área de trabajo actualizada: XxXmm`.

### Hardware (Arduino)
1. Carga `CNC_code_optimizado.ino`.
2. Abre el Monitor Serial (9600 baudios).
3. Verás el mensaje: `🪄 CirCNC (Bresenham Optimized) ready!`.

---
**Próximo Paso**: Con los perfiles funcionando, el sistema está listo para pruebas de campo intensivas antes de generar el instalador final (.exe).
