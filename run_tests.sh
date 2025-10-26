#!/bin/bash
# Script para ejecutar las pruebas del CNC-GCTRL-L293

echo "========================================"
echo "CNC-GCTRL-L293 Test Runner"
echo "========================================"
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest no está instalado."
    echo "Por favor ejecute: pip install -r requirements.txt"
    exit 1
fi

echo "✓ pytest encontrado"
echo ""

# Run tests
echo "Ejecutando pruebas..."
echo ""

pytest -v --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "✅ Todas las pruebas pasaron exitosamente"
    echo "========================================"
    exit 0
else
    echo ""
    echo "========================================"
    echo "❌ Algunas pruebas fallaron"
    echo "========================================"
    exit 1
fi
