@echo off
REM Script para ejecutar las pruebas del CNC-GCTRL-L293 en Windows

echo ========================================
echo CNC-GCTRL-L293 Test Runner
echo ========================================
echo.

REM Check if pytest is installed
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo X pytest no esta instalado.
    echo Por favor ejecute: pip install -r requirements.txt
    pause
    exit /b 1
)

echo + pytest encontrado
echo.

REM Run tests
echo Ejecutando pruebas...
echo.

python -m pytest -v --tb=short

REM Check exit code
if errorlevel 1 (
    echo.
    echo ========================================
    echo X Algunas pruebas fallaron
    echo ========================================
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo + Todas las pruebas pasaron exitosamente
    echo ========================================
    pause
    exit /b 0
)
