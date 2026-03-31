# Guía de Pruebas - CNC-GCTRL-L293

## Descripción General

Este documento describe la infraestructura de pruebas implementada para el controlador G-code CNC-GCTRL-L293. Las pruebas están diseñadas para validar la funcionalidad del aplicativo y facilitar su montaje y optimización.

## Estructura de Pruebas

```
tests/
├── __init__.py
├── test_gcode_controller.py    # Pruebas unitarias
└── test_integration.py          # Pruebas de integración
```

## Instalación de Dependencias

Para ejecutar las pruebas, instale las dependencias necesarias:

```bash
pip install -r requirements.txt
```

Las dependencias de prueba incluyen:
- `pytest==7.4.3` - Framework de pruebas
- `pytest-mock==3.12.0` - Extensión para mocking

## Ejecución de Pruebas

### Ejecutar Todas las Pruebas

```bash
pytest
```

o

```bash
python -m pytest
```

### Ejecutar Pruebas Específicas

**Pruebas Unitarias:**
```bash
pytest tests/test_gcode_controller.py
```

**Pruebas de Integración:**
```bash
pytest tests/test_integration.py
```

### Ejecutar con Salida Detallada

```bash
pytest -v
```

### Ejecutar Pruebas Específicas por Nombre

```bash
pytest -k "test_init"
pytest -k "connection"
```

## Cobertura de Pruebas

### Total: 129 Pruebas

**Desglose:**
- **Pruebas Unitarias**: 85 tests
  - Controlador G-code: 30 tests
  - Puerto Arduino: 22 tests
  - Orígenes de motores: 33 tests
- **Pruebas de Integración**: 44 tests
  - Flujos de trabajo generales: 16 tests
  - Integración con Arduino: 28 tests

### Pruebas Unitarias (85 tests)

Las pruebas unitarias validan componentes individuales:

#### Pruebas del Controlador G-code (30 tests)

1. **Inicialización del Controlador** (3 tests)
   - Valores predeterminados
   - Límites de la máquina
   - Estado del origen

2. **Sistema de Logging** (3 tests)
   - Configuración de callback
   - Logging con callback
   - Logging sin callback

3. **Descubrimiento de Puertos Seriales** (2 tests)
   - Windows
   - Linux/Unix

4. **Verificación de Límites** (4 tests)
   - Posiciones dentro de límites
   - Posiciones fuera de límites
   - Valores parciales
   - Límites deshabilitados

5. **Carga de Archivos G-code** (4 tests)
   - Carga exitosa
   - Filtrado de comentarios
   - Filtrado de líneas vacías
   - Manejo de errores

6. **Streaming de G-code** (5 tests)
   - Inicio sin G-code
   - Inicio con G-code
   - Pausa
   - Reanudación
   - Detención

7. **Control de Origen** (3 tests)
   - Establecer origen
   - Establecer sin conexión
   - Retornar a origen

8. **Parada de Emergencia** (1 test)
   - Funcionalidad de emergencia

9. **Envío de Comandos** (3 tests)
   - Sin puerto
   - Agregar nueva línea
   - Comando con nueva línea existente

10. **Desconexión** (2 tests)
    - Con puerto conectado
    - Sin puerto

#### Verificación de Puerto Arduino (22 tests)

11. **Configuración de Puerto** (6 tests)
    - Baudrate (9600)
    - Bits de datos (8 bits)
    - Paridad (ninguna)
    - Bits de parada (1 bit)
    - Timeout de lectura
    - Timeout de escritura

12. **Conexión al Puerto** (5 tests)
    - Reset de buffers
    - Puerto vacío
    - Puerto nulo
    - Comando de prueba
    - Cierre de puerto existente

13. **Reconexión** (2 tests)
    - Después de desconectar
    - Manejo de errores

14. **Disponibilidad de Puerto** (3 tests)
    - Windows COM
    - Linux USB
    - Mac USB

15. **Comunicación** (4 tests)
    - Formato con newline
    - Preservación de newline
    - Codificación UTF-8
    - Hilo de lectura

16. **Timeout** (2 tests)
    - Configuración de timeout
    - Manejo de excepciones

#### Verificación de Orígenes de Motores (33 tests)

17. **Configuración de Motores** (6 tests)
    - Eje X existe
    - Eje Y existe
    - Servo Z existe
    - Rango X (0-40mm)
    - Rango Y (0-40mm)
    - Rango Z (0-5mm)

18. **Orígenes** (5 tests)
    - Origen no establecido inicial
    - Posición origen en cero
    - Comando de establecer origen
    - Guardar posición origen
    - Comando retornar a origen

19. **Homing** (4 tests)
    - Secuencia de comandos
    - Establecer origen
    - Resetear posición
    - Home después de completar

20. **Direcciones de Motores** (6 tests)
    - X positivo
    - X negativo
    - Y positivo
    - Y negativo
    - Z positivo
    - Z negativo

21. **Cálculo de Pasos** (5 tests)
    - Inicialización de posición
    - Actualización en movimiento
    - Velocidad lenta (1mm)
    - Velocidad media (5mm)
    - Velocidad rápida (10mm)

22. **Aplicación de Límites** (7 tests)
    - Límite mínimo X
    - Límite máximo X
    - Límite mínimo Y
    - Límite máximo Y
    - Límite mínimo Z
    - Límite máximo Z
    - Deshabilitar límites

### Pruebas de Integración (44 tests)

#### Integración de Flujos de Trabajo (16 tests)

1. **Flujo de Conexión** (3 tests)
   - Conexión exitosa
   - Fallo de conexión
   - Flujo de desconexión

2. **Flujo de Ejecución de G-code** (3 tests)
   - Cargar y transmitir
   - Pausar y reanudar
   - Detener

3. **Flujo de Control Manual** (3 tests)
   - Movimiento dentro de límites
   - Movimiento en límite
   - Movimiento en todas direcciones

4. **Flujo de Homing** (3 tests)
   - Secuencia de homing
   - Home después de homing completo
   - Flujo de establecer origen

5. **Flujo de Emergencia** (2 tests)
   - Emergencia durante streaming
   - Emergencia durante control manual

6. **Flujo de Prueba de Límites** (1 test)
   - Secuencia de prueba de límites

7. **Flujo Completo** (1 test)
   - Workflow de extremo a extremo

#### Integración con Firmware Arduino (28 tests)

23. **Firmware Arduino** (5 tests)
    - Secuencia de inicialización
    - Comando G1 (movimiento lineal)
    - Comando G90 (modo absoluto)
    - Comando G91 (modo incremental)
    - Comando M300 (control servo)

24. **Precisión de Seguimiento** (3 tests)
    - Actualización desde respuesta Arduino
    - Seguimiento después de movimiento
    - Reset después de homing

25. **Coordinación de Motores** (3 tests)
    - Movimiento simultáneo XY
    - Movimientos secuenciales a origen
    - Ejecución de archivo G-code

26. **Verificación de Límites** (6 tests)
    - Prevenir X negativo
    - Prevenir Y negativo
    - Prevenir exceder máximo X
    - Prevenir exceder máximo Y
    - Permitir posiciones válidas
    - Bloquear movimiento en límite

27. **Validación de Configuración Hardware** (4 tests)
    - Motor X en puerto 2
    - Motor Y en puerto 1
    - Servo en pin 10
    - Baudrate coincide con Arduino

28. **Protocolo de Comunicación Serial** (4 tests)
    - Manejo de respuesta "ok"
    - Error detiene streaming
    - Comando de consulta de estado
    - Comando de parada de emergencia

29. **Flujo Completo de Hardware** (3 tests)
    - Operación CNC completa
    - Flujo de control manual
    - Secuencia de prueba de límites

## Interpretación de Resultados

### Resultado Exitoso
```
===================== 129 passed in X.XXs =====================
```

Todas las pruebas pasaron correctamente. El aplicativo está listo para el montaje.

### Resultado con Fallos
```
===================== X failed, Y passed in Z.ZZs =====================
```

Revise los detalles de las pruebas fallidas para identificar problemas.

## Buenas Prácticas

1. **Ejecutar pruebas antes de commits**
   ```bash
   pytest
   ```

2. **Ejecutar pruebas después de cambios**
   - Siempre ejecute las pruebas después de modificar código
   - Asegúrese de que todas las pruebas pasen

3. **Agregar nuevas pruebas**
   - Al agregar funcionalidad, agregue pruebas correspondientes
   - Mantenga la cobertura de pruebas alta

4. **Depuración de Fallos**
   - Use `-v` para ver detalles
   - Use `-s` para ver salida de print
   - Use `--pdb` para depurador interactivo

## Comandos Útiles

```bash
# Ejecutar con salida detallada
pytest -v

# Mostrar print statements
pytest -s

# Ejecutar solo pruebas fallidas previas
pytest --lf

# Detener en primer fallo
pytest -x

# Ejecutar con depurador en fallos
pytest --pdb

# Ver tiempo de ejecución de cada prueba
pytest --durations=10

# Ejecutar en paralelo (requiere pytest-xdist)
pytest -n auto
```

## Integración Continua

Las pruebas pueden integrarse fácilmente en un sistema de CI/CD:

```yaml
# Ejemplo para GitHub Actions
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest
```

## Próximos Pasos

1. **Cobertura de Código**: Instalar `pytest-cov` para análisis de cobertura
   ```bash
   pip install pytest-cov
   pytest --cov=gctrl --cov-report=html
   ```

2. **Pruebas de Hardware**: Agregar pruebas con hardware real (marcadas con `@pytest.mark.serial`)

3. **Pruebas de GUI**: Considerar pruebas de interfaz gráfica

4. **Pruebas de Rendimiento**: Agregar pruebas de carga y rendimiento

## Solución de Problemas

### Error: ModuleNotFoundError: No module named 'tkinter'
```bash
# En Ubuntu/Debian
sudo apt-get install python3-tk

# En Fedora/RedHat
sudo dnf install python3-tkinter
```

### Error: No tests collected
- Verifique que los archivos de prueba comiencen con `test_`
- Verifique que las funciones de prueba comiencen con `test_`
- Verifique que esté en el directorio correcto

## Contacto y Soporte

Para preguntas o problemas con las pruebas, por favor abra un issue en el repositorio.
