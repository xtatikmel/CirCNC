import serial
import threading
import time
import platform
import os
import glob
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from tkinter import messagebox

class GCodeController:
    def __init__(self):
        self.port = None
        self.port_name = None
        self.running = True
        self.streaming = False
        self.paused = False
        self.gcode = []
        self.gcode_index = 0
        self.current_line = ""
        self.log_callback = None
        self.position = {'x': 0, 'y': 0, 'z': 0}
        # Límites de la máquina en mm
        self.machine_limits = {
            'x': {'min': 0, 'max': 40},  # Límite X: 40mm
            'y': {'min': 0, 'max': 40},  # Límite Y: 40mm
            'z': {'min': 0, 'max': 5}    # Límite Z: 5mm
        }
        self.serial_lock = threading.Lock()
        self.origin_set = False
        self.origin_position = {'x': 0, 'y': 0, 'z': 0}
        self.homing_complete = False
        self.soft_limits_enabled = True
        self.last_command_time = 0
        self.command_timeout = 1.0  # 1 segundo de timeout
        # Compatibilidad con instalaciones donde "serial" no es pyserial
        # Guardamos un alias seguro para SerialException y comprobamos si
        # serial.tools.list_ports está disponible.
        try:
            self._SerialException = getattr(serial, 'SerialException', Exception)
        except Exception:
            # Si 'serial' es un paquete distinto que lanza al inspeccionarlo,
            # establecemos valores por defecto y evitamos usarlo directamente.
            self._SerialException = Exception

        # Comprobar de forma robusta si serial.tools.list_ports está disponible
        try:
            # Intentar importar list_ports directamente; esto funciona aunque
            # `serial.tools` no aparezca como atributo en el módulo `serial`.
            from serial.tools import list_ports  # type: ignore
            self._has_list_ports = True
        except Exception:
            self._has_list_ports = False
        
    def set_log_callback(self, callback):
        self.log_callback = callback
        
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        
    def find_serial_ports(self):
        """Encuentra puertos seriales disponibles"""
        ports = []
        system = platform.system().lower()
        # Preferir serial.tools.list_ports.comports() si está disponible
        try:
            if self._has_list_ports:
                for p in serial.tools.list_ports.comports():
                    try:
                        ports.append(p.device)
                    except Exception:
                        # objeto inesperado, ignorar
                        pass
                return ports

            # Si no hay list_ports, intentar sondear puertos probando abrilos
            if hasattr(serial, 'Serial'):
                if "windows" in system:
                    # Probar COM1..COM256 (más seguro que sólo 1..20)
                    for i in range(1, 257):
                        port = f"COM{i}"
                        try:
                            test_serial = serial.Serial(port, 9600, timeout=0.1)
                            test_serial.close()
                            ports.append(port)
                        except Exception:
                            # ignorar fallos al abrir
                            pass
                else:
                    patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/tty.usb*', '/dev/cu.usb*']
                    for pattern in patterns:
                        for port in glob.glob(pattern):
                            try:
                                test_serial = serial.Serial(port, 9600, timeout=0.1)
                                test_serial.close()
                                ports.append(port)
                            except Exception:
                                pass
            else:
                # No hay pyserial ni list_ports: intentar heurística pasiva
                if "windows" in system:
                    # Añadir nombres COM sin intentar abrirlos
                    for i in range(1, 257):
                        ports.append(f"COM{i}")
                else:
                    patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/tty.usb*', '/dev/cu.usb*']
                    for pattern in patterns:
                        for port in glob.glob(pattern):
                            ports.append(port)
        except Exception as e:
            # Capturar errores inesperados (por ejemplo, si 'serial' es un paquete extraño)
            if self.log_callback:
                self.log_callback(f"Error buscando puertos: {str(e)}")
        
        return ports
    
    def connect(self, port_name):
        """Conecta al puerto serial"""
        if not port_name:
            if self.log_callback:
                self.log_callback("No se especificó puerto")
            return False
        
        try:
            # Cerrar puerto existente si está abierto
            if self.port and self.port.is_open:
                try:
                    self.port.close()
                    if self.log_callback:
                        self.log_callback(f"Puerto anterior cerrado")
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"Error al cerrar puerto anterior: {str(e)}")
                self.port = None

            # Intentar abrir el puerto con diferentes configuraciones
            try:
                # Configurar el puerto serial con los parámetros requeridos
                self.port = serial.Serial(
                    port=port_name,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                    write_timeout=1
                )
                
                # Guardar nombre de puerto
                self.port_name = port_name

                # Limpiar buffers si están disponibles
                try:
                    self.port.reset_input_buffer()
                    self.port.reset_output_buffer()
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"Error al limpiar buffers: {str(e)}")
                
                # Enviar comando de prueba al Arduino
                try:
                    self.port.write(b"G90\n")  # Usar G90 como comando de prueba
                    if self.log_callback:
                        self.log_callback("Comando de prueba enviado (G90)")
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"Error al enviar comando de prueba: {str(e)}")
                
            except serial.SerialException as e:
                if "PermissionError" in str(e) or "Acceso denegado" in str(e):
                    if self.log_callback:
                        self.log_callback(f"Error de permisos al abrir puerto {port_name}. Asegúrate de que no esté siendo usado por otro programa.")
                    return False
                elif "FileNotFoundError" in str(e):
                    if self.log_callback:
                        self.log_callback(f"Puerto {port_name} no encontrado. Verifica la conexión.")
                    return False
                else:
                    if self.log_callback:
                        self.log_callback(f"Error al abrir puerto {port_name}: {str(e)}")
                    return False
            except Exception as e:
                # Si pyserial no está correctamente instalado, informar
                if self.log_callback:
                    self.log_callback(f"Error al abrir puerto {port_name}: {str(e)}")
                return False
            
            # Iniciar hilo de lectura
            read_thread = threading.Thread(target=self.read_responses, daemon=True)
            read_thread.start()

            # Enviar comando de prueba para verificar comunicación
            self.send_command("?")
            time.sleep(0.5)

            if self.log_callback:
                self.log_callback(f"Conectado a {port_name}")
            return True
            
        except Exception as e:
            # Registrar y mostrar el error, devolver False para que los tests puedan comprobar el fallo
            if self.log_callback:
                self.log_callback(f"Error conectando a {port_name}: {str(e)}")
            try:
                messagebox.showerror("Error", f"Error conectando a {port_name}: {e}")
            except Exception:
                # En entornos sin GUI, messagebox puede fallar
                pass
            return False
    def check_limits(self, x=None, y=None, z=None):
        """Verifica si una posición está dentro de los límites"""
        if not self.soft_limits_enabled:
            return True
            
        if x is not None:
            if x < self.machine_limits['x']['min'] or x > self.machine_limits['x']['max']:
                return False
        if y is not None:
            if y < self.machine_limits['y']['min'] or y > self.machine_limits['y']['max']:
                return False
        if z is not None:
            if z < self.machine_limits['z']['min'] or z > self.machine_limits['z']['max']:
                return False
        return True

    def send_command(self, command):
        """Envía un comando al puerto serial"""
        if not self.port or not self.port.is_open:
            if self.log_callback:
                self.log_callback("Puerto no conectado")
            return False
            
        try:
            with self.serial_lock:
                # Asegurar que el comando termina con \n
                if not command.endswith('\n'):
                    command = command + '\n'
                
                # Limpiar buffer antes de enviar
                self.port.reset_input_buffer()
                
                # Enviar el comando
                self.port.write(command.encode())
                self.current_line = command.strip()
                
                if self.log_callback:
                    self.log_callback(f"→ {self.current_line}")
                
                # Esperar respuesta
                time.sleep(0.2)
                return True
                
        except serial.SerialException as e:
            if self.log_callback:
                self.log_callback(f"Error enviando comando: {str(e)}")
            return False
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Error inesperado: {str(e)}")
            return False
    
    def read_responses(self):
        """Lee respuestas del puerto serial"""
        while self.running and self.port and self.port.is_open:
            try:
                if self.port.in_waiting > 0:
                    response = self.port.readline().decode().strip()
                    if response:
                        self.log(f"← {response}")
                        # Procesar respuesta de estado
                        if response.startswith("<"):
                            # Ejemplo: <Idle|MPos:0.000,0.000,0.000|FS:0,0>
                            try:
                                pos_str = response.split("MPos:")[1].split("|")[0]
                                x, y, z = map(float, pos_str.split(","))
                                # Actualizar posición
                                self.position = {'x': x, 'y': y, 'z': z}
                                # Forzar actualización de la interfaz
                                if self.log_callback:
                                    self.log_callback("Posición actualizada")
                            except:
                                pass
                        elif response.startswith("ok"):
                            if self.streaming and not self.paused:
                                time.sleep(0.1)
                                self.send_next_gcode_line()
                        elif response.startswith("error"):
                            self.log(f"Error en comando: {self.current_line}")
                            # Detener streaming si hay error
                            self.stop_streaming()
            except Exception as e:
                self.log(f"Error leyendo respuesta: {e}")
                break
            time.sleep(0.01)
    
    def load_gcode(self, filename):
        """Carga archivo G-code"""
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            
            # Filtrar líneas vacías y comentarios
            self.gcode = []
            current_x, current_y = 0, 0
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith(';') and not line.startswith('('):
                    self.gcode.append(line)
                    # Procesar coordenadas para la trayectoria
                    if 'X' in line or 'Y' in line:
                        try:
                            # Extraer coordenadas X e Y
                            x = current_x
                            y = current_y
                            if 'X' in line:
                                x = float(line[line.find('X')+1:].split()[0])
                            if 'Y' in line:
                                y = float(line[line.find('Y')+1:].split()[0])
                            current_x, current_y = x, y
                        except:
                            pass
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error cargando archivo: {e}")
            return False
    
    def send_next_gcode_line(self):
        """Envía la siguiente línea de G-code"""
        if self.gcode_index < len(self.gcode):
            line = self.gcode[self.gcode_index]
            if self.send_command(line):
                self.gcode_index += 1
                return True
        else:
            self.streaming = False
            if self.log_callback:
                self.log_callback("G-code ejecutado completamente")
                self.log_callback("Retornando a origen...")
            # Volver a origen después de completar
            self.return_to_origin()
            messagebox.showinfo("Completado", "G-code ejecutado completamente")
        return False
    
    def return_to_origin(self):
        """Retorna la máquina al origen"""
        if not self.port or not self.port.is_open:
            return False
            
        if self.log_callback:
            self.log_callback("Iniciando retorno a origen...")
        
        # Primero subir el lápiz
        self.send_command("M300 S50")  # Pen up
        time.sleep(0.5)
        
        # Mover a origen en modo absoluto
        self.send_command("G90")  # Modo absoluto
        self.send_command("G1 X0 Y0 Z0 F1000")
        
        # Esperar a que llegue
        time.sleep(2)
        
        # Actualizar posición
        self.position = {'x': 0, 'y': 0, 'z': 0}
        
        if self.log_callback:
            self.log_callback("Retorno a origen completado")
        
        return True
    
    def start_streaming(self):
        """Inicia el streaming de G-code"""
        if not self.gcode:
            messagebox.showwarning("Advertencia", "No hay G-code cargado")
            return
        
        if not self.streaming:
            self.streaming = True
            self.paused = False
            self.gcode_index = 0
            self.send_next_gcode_line()
    
    def pause_streaming(self):
        """Pausa el streaming"""
        self.paused = True
    
    def resume_streaming(self):
        """Reanuda el streaming"""
        self.paused = False
        if self.streaming:
            self.send_next_gcode_line()
    
    def stop_streaming(self):
        """Detiene el streaming"""
        self.streaming = False
        self.paused = False
        self.gcode_index = 0
        if self.log_callback:
            self.log_callback("Ejecución detenida")
            self.log_callback("Retornando a origen...")
        # Volver a origen después de detener
        self.return_to_origin()
    
    def emergency_stop(self):
        """Parada de emergencia"""
        if self.port and self.port.is_open:
            self.port.write(b'\x18')  # Ctrl+X
            self.stop_streaming()
            if self.log_callback:
                self.log_callback("¡PARADA DE EMERGENCIA!")
            # Esperar un momento antes de volver a origen
            time.sleep(1)
            self.return_to_origin()
    
    def disconnect(self):
        """Desconecta el puerto serial"""
        self.running = False
        if self.port and self.port.is_open:
            # Volver a origen antes de desconectar
            self.return_to_origin()
            time.sleep(1)  # Esperar a que termine el movimiento
            self.port.close()
    
    def get_status(self):
        """Obtiene el estado actual de la máquina"""
        self.send_command("?")
    
    def set_origin(self):
        """Establece la posición actual como origen"""
        if self.port and self.port.is_open:
            self.send_command("G92 X0 Y0 Z0")
            self.origin_position = self.position.copy()
            self.origin_set = True
            if self.log_callback:
                self.log_callback("Origen establecido en la posición actual")
            return True
        return False
    
    def test_limits(self):
        """Prueba los límites de la máquina"""
        # Secuencia de prueba más completa
        commands = [
            "G90",           # Modo absoluto
            "G1 X0 Y0 Z0 F1000",   # Ir a origen
            "G1 X50 F1000",        # Mover X a 50mm
            "G1 X0 F1000",         # Volver a X=0
            "G1 Y50 F1000",        # Mover Y a 50mm
            "G1 Y0 F1000",         # Volver a Y=0
            "G1 Z20 F1000",        # Mover Z a 20mm
            "G1 Z0 F1000",         # Volver a Z=0
            "G1 X25 Y25 F1000",    # Mover a punto intermedio
            "G1 Z10 F1000",        # Subir Z
            "G1 X0 Y0 F1000",      # Volver a origen
            "G1 Z0 F1000"          # Bajar Z
        ]
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(1)  # Esperar más tiempo entre movimientos

    def perform_homing_sequence(self):
        """Realiza la secuencia de homing para todos los ejes"""
        if not self.port or not self.port.is_open:
            return False

        if self.log_callback:
            self.log_callback("Iniciando secuencia de homing...")

        # Secuencia de homing paso a paso
        homing_sequence = [
            "G90",           # Modo absoluto
            "G21",           # Unidades en milímetros
            "G91",           # Cambiar a modo incremental para homing
            "$H",            # Comando de homing
            "G90",           # Volver a modo absoluto
            "G1X0Y0Z0F1000", # Mover a origen
            "G92X0Y0Z0"      # Establecer origen en 0,0,0
        ]

        for cmd in homing_sequence:
            if self.log_callback:
                self.log_callback(f"Enviando comando: {cmd}")
            if not self.send_command(cmd):
                if self.log_callback:
                    self.log_callback("Error en secuencia de homing")
                return False
            time.sleep(1)  # Esperar entre comandos

        self.homing_complete = True
        self.origin_set = True
        self.origin_position = {'x': 0, 'y': 0, 'z': 0}
        self.position = {'x': 0, 'y': 0, 'z': 0}  # Resetear posición actual
        
        if self.log_callback:
            self.log_callback("Secuencia de homing completada")
        return True

    def home(self):
        """Mover a posición de origen"""
        if self.port and self.port.is_open:
            if not self.homing_complete:
                # Si no se ha realizado el homing, hacerlo ahora
                return self.perform_homing_sequence()
            else:
                # Si ya se realizó el homing, solo mover a origen
                self.send_command("G90")  # Modo absoluto
                self.send_command("G1 X0 Y0 Z0 F1000")  # Mover a origen con velocidad especificada
                if self.log_callback:
                    self.log_callback("Retornando a origen")
                return True
        return False

    def jog(self, direction):
        """Movimiento manual"""
        if not self.port or not self.port.is_open:
            if self.log_callback:
                self.log_callback("Puerto no conectado")
            return False

        # Obtener velocidad según selección
        speed = {
            "1": "1",    # Lenta: 1mm
            "2": "5",    # Media: 5mm
            "3": "10"    # Rápida: 10mm
        }[self.speed_var.get()]
        
        # Enviar comando de movimiento
        axis = direction[0].upper()  # X, Y o Z
        sign = "+" if direction[1] == "+" else "-"
        
        # Calcular nueva posición
        new_position = self.position.copy()
        move_distance = float(speed) if sign == "+" else -float(speed)
        new_position[axis.lower()] += move_distance
        
        # Verificar límites
        if not self.check_limits(**new_position):
            if self.log_callback:
                self.log_callback("Movimiento cancelado: fuera de límites")
            return False
        
        # Enviar comando de movimiento
        command = f"G91G1{axis}{sign}{speed}F1000"
        
        if self.log_callback:
            self.log_callback(f"Enviando comando de movimiento: {command}")
        
        # Enviar comando
        if self.send_command(command):
            # Actualizar posición
            self.position = new_position
            time.sleep(0.5)  # Esperar a que el movimiento se complete
            return True
        return False

class GCodeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Controlador G-code by 'Paradoja Developers'")
        self.controller = GCodeController()
        self.controller.set_log_callback(self.log)
        
        self.create_widgets()
        self.update_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_position()
    
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame izquierdo para controles
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame superior para puerto y archivo
        top_frame = ttk.Frame(left_frame, padding="5")
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Label(top_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top_frame, textvariable=self.port_var)
        self.port_combo.grid(row=0, column=1, padx=5)
        ttk.Button(top_frame, text="Actualizar", command=self.update_ports).grid(row=0, column=2, padx=5)
        self.connect_btn = ttk.Button(top_frame, text="Conectar", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        ttk.Button(top_frame, text="Abrir G-code", command=self.open_file).grid(row=0, column=4, padx=5)
        
        # Frame central para áreas de texto
        text_frame = ttk.Frame(left_frame, padding="5")
        text_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        gcode_frame = ttk.LabelFrame(text_frame, text="G-code", padding="5")
        gcode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.gcode_area = scrolledtext.ScrolledText(gcode_frame, width=40, height=20)
        self.gcode_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        serial_frame = ttk.LabelFrame(text_frame, text="Comunicación Serial", padding="5")
        serial_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.serial_area = scrolledtext.ScrolledText(serial_frame, width=40, height=20)
        self.serial_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame para barra de progreso
        progress_frame = ttk.LabelFrame(left_frame, text="Progreso", padding="5")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.grid(row=0, column=2, padx=5)
        
        # Frame para posición actual con más detalle
        position_frame = ttk.LabelFrame(left_frame, text="Posición Actual", padding="5")
        position_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
        # X position
        ttk.Label(position_frame, text="X:").grid(row=0, column=0, padx=5)
        self.x_pos_label = ttk.Label(position_frame, text="0.000")
        self.x_pos_label.grid(row=0, column=1, padx=5)
        ttk.Label(position_frame, text="mm").grid(row=0, column=2, padx=2)
        
        # Y position
        ttk.Label(position_frame, text="Y:").grid(row=0, column=3, padx=5)
        self.y_pos_label = ttk.Label(position_frame, text="0.000")
        self.y_pos_label.grid(row=0, column=4, padx=5)
        ttk.Label(position_frame, text="mm").grid(row=0, column=5, padx=2)
        
        # Z position
        ttk.Label(position_frame, text="Z:").grid(row=0, column=6, padx=5)
        self.z_pos_label = ttk.Label(position_frame, text="0.000")
        self.z_pos_label.grid(row=0, column=7, padx=5)
        ttk.Label(position_frame, text="mm").grid(row=0, column=8, padx=2)
        
        # Botones de control de posición
        ttk.Button(position_frame, text="Actualizar", command=self.controller.get_status).grid(row=0, column=9, padx=5)
        ttk.Button(position_frame, text="Establecer Origen", command=self.set_origin).grid(row=0, column=10, padx=5)
        ttk.Button(position_frame, text="Probar Límites", command=self.test_limits).grid(row=0, column=11, padx=5)
        
        manual_frame = ttk.LabelFrame(left_frame, text="Control Manual", padding="5")
        manual_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        ttk.Button(manual_frame, text="Origen", command=self.home).grid(row=0, column=0, padx=5)
        ttk.Button(manual_frame, text="Motor X +", command=lambda: self.jog('x+')).grid(row=0, column=1, padx=5)
        ttk.Button(manual_frame, text="Motor X -", command=lambda: self.jog('x-')).grid(row=0, column=2, padx=5)
        ttk.Button(manual_frame, text="Motor Y +", command=lambda: self.jog('y+')).grid(row=0, column=3, padx=5)
        ttk.Button(manual_frame, text="Motor Y -", command=lambda: self.jog('y-')).grid(row=0, column=4, padx=5)
        ttk.Button(manual_frame, text="Servo +", command=lambda: self.jog('z+')).grid(row=0, column=5, padx=5)
        ttk.Button(manual_frame, text="Servo -", command=lambda: self.jog('z-')).grid(row=0, column=6, padx=5)
        
        speed_frame = ttk.LabelFrame(left_frame, text="Velocidad", padding="5")
        speed_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
        self.speed_var = tk.StringVar(value="1")
        ttk.Radiobutton(speed_frame, text="Lenta", variable=self.speed_var, value="1").grid(row=0, column=0, padx=5)
        ttk.Radiobutton(speed_frame, text="Media", variable=self.speed_var, value="2").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(speed_frame, text="Rápida", variable=self.speed_var, value="3").grid(row=0, column=2, padx=5)
        
        control_frame = ttk.Frame(left_frame, padding="5")
        control_frame.grid(row=6, column=0, sticky=(tk.W, tk.E))
        self.start_btn = ttk.Button(control_frame, text="Iniciar", command=self.start_streaming, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = ttk.Button(control_frame, text="Pausar", command=self.pause_streaming, state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        self.stop_btn = ttk.Button(control_frame, text="Detener", command=self.stop_streaming, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=2, padx=5)
        self.emergency_btn = ttk.Button(control_frame, text="¡EMERGENCIA!", command=self.emergency_stop, state=tk.DISABLED)
        self.emergency_btn.grid(row=0, column=3, padx=5)
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
    
    def update_ports(self):
        """Actualiza la lista de puertos disponibles en la GUI usando el controller."""
        ports = self.controller.find_serial_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        else:
            self.log("No se encontraron puertos disponibles. Verifica la conexión del dispositivo.")

    def toggle_connection(self):
        """Conecta/desconecta el puerto serial desde la GUI"""
        if not self.controller.port or not getattr(self.controller.port, 'is_open', False):
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error de conexión", "No se ha seleccionado ningún puerto. Por favor, selecciona un puerto válido.")
                return
                
            if self.controller.connect(port):
                self.connect_btn.configure(text="Desconectar")
                self.start_btn.configure(state=tk.NORMAL)
                self.emergency_btn.configure(state=tk.NORMAL)
                self.log("Conectado a " + (self.controller.port_name or ""))
            else:
                # Si la conexión falla, mostrar un diálogo con opciones para solucionar el problema
                respuesta = messagebox.askretrycancel(
                    "Error de conexión", 
                    f"No se pudo conectar al puerto {port}.\n\n"
                    "Posibles soluciones:\n"
                    "1. Cierra otros programas que puedan estar usando el puerto\n"
                    "2. Desconecta y vuelve a conectar el dispositivo\n"
                    "3. Ejecuta el programa como administrador\n"
                    "4. Selecciona un puerto diferente\n\n"
                    "¿Quieres intentar conectar de nuevo?"
                )
                if respuesta:
                    # Actualizar puertos y reintentar
                    self.update_ports()
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="Conectar")
            self.start_btn.configure(state=tk.DISABLED)
            self.pause_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
            self.emergency_btn.configure(state=tk.DISABLED)
            self.log("Desconectado")

    def open_file(self):
        """Abre diálogo para seleccionar archivo G-code"""
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo G-code",
            filetypes=[("G-code files", "*.gcode *.nc *.g"), ("All files", "*.*")]
        )
        if filename:
            if self.controller.load_gcode(filename):
                self.log(f"Archivo cargado: {filename}")
                # Mostrar contenido del G-code
                self.gcode_area.delete(1.0, tk.END)
                for i, line in enumerate(self.controller.gcode, 1):
                    self.gcode_area.insert(tk.END, f"{i:4d}: {line}\n")
                self.start_btn.configure(state=tk.NORMAL)
    
    def start_streaming(self):
        """Inicia el streaming de G-code"""
        self.controller.start_streaming()
        self.start_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
        self.progress_var.set(0)  # Resetear barra de progreso
        self.progress_label.configure(text="0%")
        self.log("Iniciando ejecución")
    
    def pause_streaming(self):
        """Pausa/reanuda el streaming"""
        if not self.controller.paused:
            self.controller.pause_streaming()
            self.pause_btn.configure(text="Reanudar")
            self.log("Pausado")
        else:
            self.controller.resume_streaming()
            self.pause_btn.configure(text="Pausar")
            self.log("Reanudado")
    
    def stop_streaming(self):
        """Detiene el streaming"""
        self.controller.stop_streaming()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self.log("Detenido")
    
    def emergency_stop(self):
        """Parada de emergencia"""
        self.controller.emergency_stop()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self.log("¡PARADA DE EMERGENCIA!")
    
    def log(self, message):
        """Añade mensaje al área de texto"""
        self.serial_area.insert(tk.END, message + "\n")
        self.serial_area.see(tk.END)
    
    def on_closing(self):
        """Maneja el cierre de la ventana"""
        if messagebox.askokcancel("Salir", "¿Desea salir?"):
            self.controller.disconnect()
            self.root.destroy()

    def home(self):
        """Mover a posición de origen"""
        if self.controller.port and self.controller.port.is_open:
            if self.controller.origin_set:
                # Si hay un origen establecido, ir a esa posición
                self.controller.send_command("G90")  # Modo absoluto
                self.controller.send_command(f"G1 X{self.controller.origin_position['x']} Y{self.controller.origin_position['y']} Z{self.controller.origin_position['z']} F1000")
                if self.controller.log_callback:
                    self.controller.log_callback("Retornando a origen establecido")
            else:
                # Si no hay origen establecido, usar el comando de home
                self.controller.send_command("$H")
                if self.controller.log_callback:
                    self.controller.log_callback("Enviando comando de home")
            # Esperar un momento y actualizar posición
            self.root.after(1000, self.controller.get_status)

    def jog(self, direction):
        """Movimiento manual"""
        if self.controller.port and self.controller.port.is_open:
            # Obtener velocidad según selección
            speed = {
                "1": "1",    # Lenta: 1mm
                "2": "5",    # Media: 5mm
                "3": "10"    # Rápida: 10mm
            }[self.speed_var.get()]
            
            # Extraer el eje y la dirección
            axis = direction[0].upper()
            is_positive = direction[1] == '+'
            distance = speed if is_positive else f"-{speed}"
            
            # Enviar comando en formato compatible con el Arduino
            command = f"G0 {axis}{distance}"
            self.controller.send_command(command)
            self.log(f"Movimiento manual: {axis} {distance}")

    def update_position(self):
        """Actualiza la posición mostrada en la interfaz"""
        if self.controller.port and self.controller.port.is_open:
            # Formatear números con 3 decimales
            x_str = f"{self.controller.position['x']:.3f}"
            y_str = f"{self.controller.position['y']:.3f}"
            z_str = f"{self.controller.position['z']:.3f}"
            
            # Actualizar etiquetas
            self.x_pos_label.configure(text=x_str)
            self.y_pos_label.configure(text=y_str)
            self.z_pos_label.configure(text=z_str)
            
            # Actualizar barra de progreso si hay G-code cargado
            if self.controller.gcode:
                progress = (self.controller.gcode_index / len(self.controller.gcode)) * 100
                self.progress_var.set(progress)
                self.progress_label.configure(text=f"{progress:.1f}%")
            
            # Forzar actualización de la interfaz
            self.root.update_idletasks()
            
        self.root.after(100, self.update_position)  # Actualizar cada 100ms

    def set_origin(self):
        """Establece la posición actual como origen"""
        if self.controller.port and self.controller.port.is_open:
            self.controller.set_origin()
            self.log("Estableciendo posición actual como origen")

    def test_limits(self):
        """Prueba los límites de la máquina"""
        if self.controller.port and self.controller.port.is_open:
            self.log("Iniciando prueba de límites...")
            self.controller.test_limits()
            self.log("Prueba de límites completada")

def main():
    root = tk.Tk()
    app = GCodeGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
