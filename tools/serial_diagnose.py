#!/usr/bin/env python3
"""Herramienta de diagnóstico serial mínima.

- Lista puertos detectados por pyserial.
- Intenta abrir un puerto dado, enviar un texto de prueba y leer respuesta breve.

Uso:
  python tools/serial_diagnose.py --list
  python tools/serial_diagnose.py --port COM10 --baud 9600 --send "?"

Diseñado para ser seguro: captura excepciones y muestra mensajes legibles.
"""
import sys
import time
import argparse

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print("ERROR: no se puede importar pyserial. Asegúrate de tener instalado pyserial.")
    print("Detalle:", e)
    sys.exit(2)


def list_ports_cmd():
    ports = [p.device for p in list_ports.comports()]
    if not ports:
        print("No se encontraron puertos seriales.")
    else:
        print("Puertos detectados:")
        for p in ports:
            print(" -", p)
    return ports


def test_open(port, baud=9600, timeout=1.0, send=None):
    print(f"Intentando abrir {port} @ {baud} (timeout={timeout})...")
    try:
        ser = serial.Serial(port=port, baudrate=baud, timeout=timeout, write_timeout=timeout)
    except Exception as e:
        print(f"Error abriendo {port}: {e}")
        return False

    try:
        print(f"Puerto abierto: is_open={getattr(ser, 'is_open', False)}")
        # Limpiar buffers si existen
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        try:
            ser.reset_output_buffer()
        except Exception:
            pass

        if send is not None:
            s = send if send.endswith('\n') else send + '\n'
            print(f"Enviando: {s!r}")
            try:
                ser.write(s.encode())
            except Exception as e:
                print("Error escribiendo al puerto:", e)
            # esperar respuesta corta
            time.sleep(0.2)
            try:
                n = getattr(ser, 'in_waiting', 0)
            except Exception:
                n = 0
            if n:
                try:
                    resp = ser.readline().decode(errors='replace').strip()
                    print("Respuesta:", resp)
                except Exception as e:
                    print("Error leyendo respuesta:", e)
            else:
                print("No hay datos entrantes (in_waiting=0).")

    finally:
        try:
            ser.close()
            print("Puerto cerrado.")
        except Exception as e:
            print("Error cerrando puerto:", e)
    return True


def main():
    parser = argparse.ArgumentParser(description='Diagnóstico simple de puertos seriales')
    parser.add_argument('--list', action='store_true', help='Listar puertos detectados')
    parser.add_argument('--port', '-p', help='Puerto a probar (ej: COM10 o /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=9600, help='Baudrate para la prueba (default: 9600)')
    parser.add_argument('--send', help='Cadena a enviar como prueba (se añade \n si falta)')
    parser.add_argument('--timeout', type=float, default=1.0, help='Timeout para apertura/escritura (s)')

    args = parser.parse_args()

    if args.list:
        list_ports_cmd()

    if args.port:
        ok = test_open(args.port, baud=args.baud, timeout=args.timeout, send=args.send)
        if not ok:
            sys.exit(1)

    if not args.list and not args.port:
        parser.print_help()


if __name__ == '__main__':
    main()
