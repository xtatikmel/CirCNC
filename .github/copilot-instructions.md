## Propósito

Estas instrucciones ayudan a un agente de codificación (Copilot/AGENT) a ser productivo en el repo CNC-GCTRL-L293.
Incluyen el panorama general, flujos de trabajo de desarrollo y pruebas, patrones de código y puntos críticos a revisar.

## Panorama general (big picture)
- Proyecto Python que implementa un controlador G-code con UI en `gctrl.py` (Tkinter) y la lógica central en la clase `GCodeController`.
- Flujo principal: descubrimiento de puertos seriales -> conectar puerto -> cargar G-code -> hacer streaming de líneas -> recibir respuestas (parsing de MPos).
- Interacciones clave: UI (clase `GCodeGUI`) <-> `GCodeController` (callbacks de logging y control).

## Archivos y lugares importantes
- `gctrl.py` — implementación única: GUI + `GCodeController`. Lea esta file para entender: conexión serial, descubrimiento de puertos (`find_serial_ports`), envío/recepción y parsing de respuestas.
- `tests/` — pruebas unitarias y de integración; usan `pytest` y `pytest-mock`. Observa cómo se parchcean/mokean `serial`, `tkinter.messagebox`, y `glob`.
- `requirements.txt` — dependencias (ej. `pyserial==3.5`, `pytest==7.4.3`).
- `run_tests.bat`, `run_tests.sh` — runners de pruebas para Windows/Linux; útiles para comandos reproducibles.
- `.github/workflows/tests.yml` — configuración CI (ubuntu-latest, instala `python3-tk`, ejecuta `pytest`).

## Flujo de desarrollo y comandos esenciales
- Instalar dependencias: `pip install -r requirements.txt` (se usa en README, TESTING.md y CI).
- Ejecutar pruebas localmente (Windows PowerShell):
  - `python -m pytest -v --tb=short`
  - o ejecutar `.
un_tests.bat` en Windows para una experiencia guiada.
- Comprobar CI: revisar `.github/workflows/tests.yml` para la versión de Python (3.12) y pasos de sistema (instala `python3-tk`).

## Patrones y convenciones específicas del proyecto
- Serial discovery: `GCodeController.find_serial_ports()` prueba COM1..COM20 en Windows. Nota: si tu dispositivo tiene un COM > 20, no será detectado por ese bucle.
- Envío de comandos: `send_command` siempre añade `\n` si hace falta y llama a `self.port.reset_input_buffer()` antes de escribir.
- Lectura: `read_responses` mira `in_waiting` y parsea respuestas que empiezan por `<` para extraer `MPos:`. Esto es central para actualizar `position`.
- GUI y lógica están en un mismo archivo (`gctrl.py`): al modificar la lógica central, actualizar mocks en `tests/*` y cuidar side-effects de `tkinter.messagebox`.

## Pruebas y cómo mockear hardware
- Tests ya parchean/Mockean `serial.Serial`, `platform.system`, `glob.glob` y usan `MagicMock` para `port`.
- Marca especial: `pytest.ini` define `markers` incluyendo `serial` — usa estos markers si agregas tests que interactúan con hardware real.
- Para pruebas locales, evita hardware real; usa `pytest-mock` para simular `serial.Serial` y `in_waiting`/`readline`.

## Problemas conocidos y debugging rápido
- Si no ves el puerto COM en Windows: revisar `find_serial_ports()` (limitado a COM1..COM20), Device Manager (controladores), puerto ocupado por otra aplicación, permisos o cable defectuoso.
- En código, buscar excepciones silenciosas en `connect()` (usa `messagebox.showerror`) — algunos `except` comentan el logging; habilitar logs para diagnóstico.
- Si las pruebas fallan por `tkinter` en CI -> la workflow ya instala `python3-tk` en Ubuntu; localmente en Windows asegúrate de tener tkinter disponible o patchéalo en tests.

## Qué revisar antes de proponer cambios
- Cambios en la lógica serial: actualizar mocks de tests y añadir un test que cubra `find_serial_ports` para el nuevo patrón.
- Cambios en interfaz: validar que `GCodeGUI` sigue llamando a los métodos públicos del controller y que `set_log_callback` sigue funcionando.
- Dependencias: si requiere versión distinta de `pyserial`, actualizar `requirements.txt` y el workflow CI.

## Ejemplo rápido (cómo arreglar problemas de detección COM)
- Recomendación para PR: ampliar `find_serial_ports()` en Windows para usar `serial.tools.list_ports.comports()` en lugar de iterar COM1..20. Añadir test que parchee `serial.tools.list_ports.comports`.

Si algo en estas instrucciones no está claro o quieres que incluya ejemplos de PR/patches automáticos, dime y lo actualizo.
