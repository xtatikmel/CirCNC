"""
CIRCNC - CONTROLADOR DE PLOTTER
==============================
Versión: Transformación y Control.

✅ Control manual paso a paso FUNCIONAL
✅ Gráfica completamente visible y redimensionable
✅ Paneles con separadores para cambiar tamaño
✅ Servo funcional
"""

import serial
import threading
import time
import platform
import glob
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.patches as patches
import re
import math
import os
from PIL import Image, ImageTk

# ===== PARSER DE G-CODE =====
class GCodeParser:
    """Parse G-code y extrae trayectorias"""
    
    def __init__(self):
        self.lines = []
        self.x_points = []
        self.y_points = []
        self.current_x = 0
        self.current_y = 0
        self.mode_absolute = True
        self.total_distance = 0.0
    
    def parse(self, filename):
        """Parsea archivo G-code"""
        self.lines = []
        self.x_points = [0]
        self.y_points = [0]
        self.current_x = 0
        self.current_y = 0
        self.mode_absolute = True
        self.total_distance = 0.0
        
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';') or line.startswith('('):
                        continue
                    self.lines.append(line)
                    self._process_line(line)
            return True
        except Exception as e:
            print(f"Error parseando G-code: {e}")
            return False
    
    def _process_line(self, line):
        """Procesa una línea de G-code"""
        line_upper = line.upper()
        
        if 'G90' in line_upper:
            self.mode_absolute = True
        elif 'G91' in line_upper:
            self.mode_absolute = False
        
        x_match = re.search(r'X([-+]?\d+\.?\d*)', line_upper)
        y_match = re.search(r'Y([-+]?\d+\.?\d*)', line_upper)
        
        if x_match or y_match:
            new_x = self.current_x
            new_y = self.current_y
            
            if x_match:
                x_val = float(x_match.group(1))
                new_x = x_val if self.mode_absolute else self.current_x + x_val
            
            if y_match:
                y_val = float(y_match.group(1))
                new_y = y_val if self.mode_absolute else self.current_y + y_val
            
            dist = math.sqrt((new_x - self.current_x)**2 + (new_y - self.current_y)**2)
            self.total_distance += dist
            
            self.current_x = new_x
            self.current_y = new_y
            self.x_points.append(new_x)
            self.y_points.append(new_y)


# ===== CONTROLADOR =====
class GCodeController:
    def __init__(self):
        self.port = None
        self.port_name = None
        self.running = True
        self.streaming = False
        self.paused = False
        self.gcode = []
        self.gcode_index = 0
        
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        self.mpos = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.servo_angle = 50  # Ángulo inicial asumido (arriba)
        
        
        self.machine_limits = {
            'x': {'min': 0, 'max': 80},
            'y': {'min': 0, 'max': 80},
            'z': {'min': 0, 'max': 180}
        }
        
        # Distancia de paso para control manual (en mm por movimiento)
        # No afecta la velocidad real, solo la distancia recorrida por cada paso
        self.STEP_DISTANCES = {
            '0.1mm': 0.1,
            '0.25mm': 0.25,
            '0.5mm': 0.5,
            '1mm': 1.0,
            '5mm': 5.0,
            '10mm': 10.0,
            '25mm': 25.0,
            '50mm': 50.0
        }
        self.current_step = '10mm'  # Valor por defecto
        self.JOG_SPEEDS = {
            'lenta': {'feed': 500, 'delay': 0.20, 'label': 'Lenta'},
            'media': {'feed': 900, 'delay': 0.10, 'label': 'Media'},
            'rapida': {'feed': 1500, 'delay': 0.05, 'label': 'Rápida'}
        }
        self.current_speed = 'media'
        self.STEPS_PER_MM = 35.56
        self.log_callback = None
        self.completion_callback = None
        self.serial_lock = threading.Lock()
    
    def set_machine_limits(self, max_val):
        """Actualiza los límites de la máquina en caliente"""
        self.machine_limits['x']['max'] = max_val
        self.machine_limits['y']['max'] = max_val
        self.log(f"📍 Área de trabajo actualizada: {max_val}x{max_val}mm")
    
    def set_log_callback(self, callback):
        self.log_callback = callback

    def set_completion_callback(self, callback):
        self.completion_callback = callback
    
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
    
    def find_serial_ports(self):
        ports = []
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                ports.append(p.device)
            return ports
        except:
            pass
        
        system = platform.system().lower()
        if "windows" in system:
            for i in range(1, 20):
                port = f"COM{i}"
                try:
                    test = serial.Serial(port, 9600, timeout=0.1)
                    test.close()
                    ports.append(port)
                except:
                    pass
        else:
            patterns = ['/dev/ttyUSB*', '/dev/ttyACM*']
            for pattern in patterns:
                ports.extend(glob.glob(pattern))
        
        return ports
    
    def connect(self, port_name):
        try:
            if self.port and self.port.is_open:
                self.port.close()
            
            self.port = serial.Serial(
                port=port_name,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
            self.port_name = port_name
            
            try:
                self.port.reset_input_buffer()
                self.port.reset_output_buffer()
            except:
                pass
            
            read_thread = threading.Thread(target=self.read_responses, daemon=True)
            read_thread.start()
            
            time.sleep(0.5)
            self.send_command("?")
            
            self.log(f"✅ Conectado a {port_name}")
            return True
        
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False
    
    def read_responses(self):
        while self.running and self.port and self.port.is_open:
            try:
                if self.port.in_waiting > 0:
                    response = self.port.readline().decode().strip()
                    
                    if response:
                        if response.startswith("<"):
                            try:
                                if "WPos:" in response:
                                    pos_str = response.split("WPos:")[1].split("|")[0].split(">")[0]
                                    x, y, z = map(float, pos_str.split(","))
                                    self.position = {'x': x, 'y': y, 'z': z}
                                elif "MPos:" in response:
                                    pos_str = response.split("MPos:")[1].split("|")[0].split(">")[0]
                                    x, y, z = map(float, pos_str.split(","))
                                    self.mpos = {'x': x, 'y': y, 'z': z}
                                    
                                    if "WCO:" in response:
                                        wco_str = response.split("WCO:")[1].split("|")[0].split(">")[0]
                                        ox, oy, oz = map(float, wco_str.split(","))
                                        self.position = {'x': x - ox, 'y': y - oy, 'z': z - oz}
                                    else:
                                        self.position = {
                                            'x': x - self.offset.get('x', 0.0),
                                            'y': y - self.offset.get('y', 0.0),
                                            'z': z - self.offset.get('z', 0.0)
                                        }
                            except:
                                pass
                        else:
                            self.log(f"← {response}")
                
                time.sleep(0.01)
            except Exception as e:
                self.log(f"❌ Error lectura: {e}")
                break
    
    def send_command(self, command, log_it=True):
        if not self.port or not self.port.is_open:
            return False
        
        try:
            with self.serial_lock:
                if not command.endswith('\n'):
                    command = command + '\n'
                
                self.port.write(command.encode())
                if log_it and command.strip() != "?":
                    self.log(f"→ {command.strip()}")
                return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False

    def get_status(self):
        """Solicita estado instantaneo de la controladora."""
        return self.send_command("?", log_it=False)
    
    def check_limits(self, x=None, y=None, z=None):
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
    
    def jog_step(self, axis, direction, step_key=None, speed_key=None):
        """Movimiento paso a paso MEJORADO"""
        if not self.port or not self.port.is_open:
            self.log("❌ Sin conexión a Arduino")
            return False
        
        axis = axis.upper()
        step_key = step_key or self.current_step
        speed_key = speed_key or self.current_speed
        step_distance = self.STEP_DISTANCES.get(step_key, self.STEP_DISTANCES['10mm'])
        speed_profile = self.JOG_SPEEDS.get(speed_key, self.JOG_SPEEDS['media'])
        feedrate = speed_profile['feed']
        step_delay = speed_profile['delay']
        
        # Calcular nueva posición / Control de Servo Z
        if axis == 'Z':
            # Para pasos sub-mm, garantizamos al menos 1 grado de avance.
            step_deg = max(1, int(round(step_distance * 2)))
            if direction == '+':
                self.servo_angle += step_deg
            else:
                self.servo_angle -= step_deg
                
            self.servo_angle = max(0, min(180, self.servo_angle)) # Límite físico del servo
            
            self.send_command(f"M300 S{self.servo_angle}")
            self.log(f"📍 SERVO Z: {direction} ({self.servo_angle}°) Paso {step_key} Vel {speed_profile['label']}")
            return True
        
        new_pos = self.position.copy()
        if direction == '+':
            new_pos[axis.lower()] += step_distance
        else:
            new_pos[axis.lower()] -= step_distance
        
        # Verificar límites (Comentado para permitir control libre al buscar el origen)
        # if not self.check_limits(
        #     x=new_pos['x'] if axis == 'X' else None,
        #     y=new_pos['y'] if axis == 'Y' else None,
        #     z=new_pos['z'] if axis == 'Z' else None
        # ):
        #     self.log(f"❌ Fuera de límites: {axis}={new_pos[axis.lower()]:.2f}mm")
        #     return False
        
        # Enviar comando G-code con feedrate dinámico
        sign = "+" if direction == "+" else ""
        distance = step_distance if direction == "+" else -step_distance
        
        commands = [
            "G91",  # Modo relativo
            f"G1 {axis}{sign}{distance} F{feedrate}",  # Movimiento
            "G90"   # Volver a absoluto
        ]
        
        self.log(f"🔍 DEBUG: paso={step_key}, vel={speed_key}, dist={step_distance}mm, F{feedrate}, delay={step_delay}s")
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(step_delay)  # Delay variable según velocidad
        
        # Solicitar estado
        time.sleep(0.3)
        self.send_command("?")
        
        self.log(f"📍 {axis}{direction} {step_distance}mm ({speed_profile['label']})")
        return True
    
    def set_step(self, step_distance):
        """Configura la distancia de paso para control manual"""
        if step_distance in self.STEP_DISTANCES:
            self.current_step = step_distance
            distance_mm = self.STEP_DISTANCES[step_distance]
            self.log(f"⚙️  Paso: {step_distance.upper()} ({distance_mm}mm por movimiento)")
            self.log(f"🔍 DEBUG: set_step called - step_distance={step_distance}, distance_mm={distance_mm}, current_step={self.current_step}")
            return True
        return False

    def set_speed(self, speed_key):
        """Configura la velocidad de jog (feedrate + delay)."""
        if speed_key in self.JOG_SPEEDS:
            self.current_speed = speed_key
            profile = self.JOG_SPEEDS[speed_key]
            self.log(f"🚀 Velocidad jog: {profile['label']} (F{profile['feed']})")
            return True
        return False
    
    def set_origin(self):
        if not self.port or not self.port.is_open:
            return False
        
        self.log("📌 Estableciendo origen (G92)...")
        commands = [
            "G92 X0 Y0 Z0"  # Establece las coordenadas actuales como 0,0,0
        ]
        
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(0.3)
            
        self.offset = self.mpos.copy()
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        time.sleep(0.2)
        self.send_command("?")
        self.log("✅ Origen establecido")
        return True

    def mark_current_as_origin(self):
        """Marca la posicion actual como 0,0,0 sin mover la maquina."""
        if not self.port or not self.port.is_open:
            return False

        self.log("📍 Marcando la posición actual como origen de trabajo...")
        self.send_command("G92 X0 Y0 Z0")
        self.offset = self.mpos.copy()
        self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.send_command("?")
        self.log("✅ La posición actual quedó definida como (0,0,0)")
        return True

    def verify_origin_offset(self, tolerance=0.30):
        """Verifica que la posicion de trabajo sea cercana a 0,0,0."""
        if not self.port or not self.port.is_open:
            return False, self.position.copy()

        self.get_status()
        time.sleep(0.25)
        x = abs(self.position.get('x', 0.0))
        y = abs(self.position.get('y', 0.0))
        z = abs(self.position.get('z', 0.0))
        ok = x <= tolerance and y <= tolerance and z <= tolerance
        return ok, self.position.copy()

    def test_limits(self):
        """Prueba corta de limites por software dentro del area de trabajo."""
        if not self.port or not self.port.is_open:
            self.log("❌ Sin conexión para probar límites")
            return False

        max_x = float(self.machine_limits['x']['max'])
        max_y = float(self.machine_limits['y']['max'])

        if max_x <= 0 or max_y <= 0:
            self.log("❌ Límites inválidos")
            return False

        target_x = min(max_x, 10.0)
        target_y = min(max_y, 10.0)

        self.log(f"🧪 Probar límites (zona segura): X<= {max_x:.1f}, Y<= {max_y:.1f}")
        commands = [
            "G90",
            f"G1 X{target_x:.2f} Y0 F900",
            f"G1 X0 Y{target_y:.2f} F900",
            "G1 X0 Y0 F900",
        ]

        for cmd in commands:
            if not self.send_command(cmd):
                self.log("❌ Falló prueba de límites")
                return False
            time.sleep(0.25)

        self.get_status()
        self.log("✅ Prueba de límites finalizada")
        return True
    
    def load_gcode(self, filename):
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            
            self.gcode = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(';') and not line.startswith('('):
                    self.gcode.append(line)
            
            self.log(f"✅ Cargado: {len(self.gcode)} líneas")
            return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False
    
    def start_streaming(self):
        if not self.gcode:
            messagebox.showwarning("Advertencia", "Sin G-code")
            return
        
        self.streaming = True
        self.paused = False
        self.gcode_index = 0
        
        def _stream():
            try:
                self.send_command("G90")
                time.sleep(0.2)
                
                while self.gcode_index < len(self.gcode) and self.streaming:
                    if self.paused:
                        time.sleep(0.1)
                        continue
                    
                    line = self.gcode[self.gcode_index]
                    
                    # Notificar a la GUI qué línea estamos procesando
                    self.log(f"[L{self.gcode_index + 1}] → {line}")
                    
                    # Extraemos y actualizamos M300 si el gcode maneja el servo directamente
                    if "M300" in line.upper():
                        match = re.search(r'S(\d+)', line.upper())
                        if match:
                            self.servo_angle = int(match.group(1))
                            
                    self.send_command(line, log_it=False)
                    self.gcode_index += 1
                    
                    # Pedir actualización de posición (estado) cada 2 líneas para la UI
                    if self.gcode_index % 2 == 0:
                        self.send_command("?", log_it=False)
                        
                    time.sleep(0.3)
                
                if self.streaming:
                    self.log("🏁 G-code enviado completamente al puerto serial")
                    self.return_to_origin()
                    if self.completion_callback:
                        self.completion_callback()
            except Exception as e:
                self.log(f"💥 Error crítico en streaming: {e}")
            finally:
                self.streaming = False
        
        threading.Thread(target=_stream, daemon=True).start()
    
    def pause_streaming(self):
        self.paused = not self.paused
    
    def stop_streaming(self):
        self.streaming = False
        self.return_to_origin()
    
    def return_to_origin(self):
        if not self.port or not self.port.is_open:
            return
        
        commands = [
            "M300 S50",  # Servo arriba
            "G90",
            "G1 X0 Y0",
            "G1 Z1"
        ]
        
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(0.3)
        
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        self.log("✅ En origen")
    
    def disconnect(self):
        self.running = False
        if self.port and self.port.is_open:
            self.return_to_origin()
            time.sleep(1)
            self.port.close()
        self.log("Desconectado")


# ===== INTERFAZ GRÁFICA =====
class GCodeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CirCNC - Control Avanzado - Paradoja Devs V2.0")
        self.root.geometry("1600x1000")
        
        self.controller = GCodeController()
        self.controller.set_log_callback(self.log)
        self.controller.set_completion_callback(self.on_job_completed)
        self.parser = GCodeParser()
        
        # Configurar icono de la aplicación
        try:
            icon_path = os.path.join("images", "Logo.png")
            if os.path.exists(icon_path):
                self.icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.root.iconphoto(False, self.icon_img)
        except Exception as e:
            print(f"Error cargando icono: {e}")
            
        self.create_widgets()
        self.update_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_position()
        self.update_progress()
        
        # Mensaje de bienvenida con Arte ASCII (usando raw strings para evitar SyntaxWarning)
        self.log(r"  _____ _       _____ _   _  _____ ")
        self.log(r" / ____(_)     / ____| \ | |/ ____|")
        self.log(r"| |     _ _ __| |    |  \| | |     ")
        self.log(r"| |    | | '__| |    | . ` | |     ")
        self.log(r"| |____| | |  | |____| |\  | |____ ")
        self.log(r" \_____|_|_|   \_____|_| \_|\_____|")
        self.log("-" * 42)
        self.log("🪄 CirCNC: El Poder de la Transformación")
        self.log("🔄 Versión 2.0 - Actualización de Funcionalidades")
        
        # Estado del cronómetro
        self.job_seconds = 0
        self.update_timer()
    
    def create_widgets(self):
        """Crea interfaz con paneles redimensionables"""
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # === FILA 0: CONEXIÓN ===
        control_frame = ttk.LabelFrame(main_frame, text="Control y Conexión", padding="5")
        control_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(control_frame, textvariable=self.port_var, width=15)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="Refrescar", command=self.update_ports).grid(row=0, column=2, padx=2)
        self.connect_btn = ttk.Button(control_frame, text="Conectar", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        # Perfiles de Máquina
        ttk.Label(control_frame, text="Perfil Motor:").grid(row=0, column=4, padx=5)
        self.profile_var = tk.StringVar(value="80mm (Nema 9294)")
        self.profile_combo = ttk.Combobox(control_frame, textvariable=self.profile_var, 
                                          values=["80mm (Nema 9294)", "40mm (DVD Stepper)"], 
                                          state="readonly", width=18)
        self.profile_combo.grid(row=0, column=5, padx=5)
        self.profile_combo.bind("<<ComboboxSelected>>", self.on_profile_change)
        
        # Distancia de paso para control manual
        speed_frame = ttk.LabelFrame(control_frame, text="Distancia de Paso", padding="5")
        speed_frame.grid(row=0, column=6, columnspan=3, sticky=(tk.W, tk.E), padx=10)
        step_buttons = ['0.1mm', '0.25mm', '0.5mm', '1mm', '5mm', '10mm', '25mm', '50mm']
        for idx, step_name in enumerate(step_buttons):
            ttk.Button(
                speed_frame,
                text=step_name,
                command=lambda s=step_name: self.set_step(s),
                width=8
            ).grid(row=idx // 4, column=idx % 4, padx=2, pady=2)
        
        self.speed_label = ttk.Label(control_frame, text="Paso: 10mm", font=("Arial", 10, "bold"))
        self.speed_label.grid(row=1, column=6, columnspan=3)

        jog_speed_frame = ttk.LabelFrame(control_frame, text="Velocidad Jog", padding="5")
        jog_speed_frame.grid(row=1, column=0, columnspan=6, sticky=(tk.W, tk.E), padx=5)
        self.jog_speed_var = tk.StringVar(value=self.controller.current_speed)
        ttk.Radiobutton(jog_speed_frame, text="Lenta", value='lenta', variable=self.jog_speed_var,
                        command=self.on_speed_change).grid(row=0, column=0, padx=6)
        ttk.Radiobutton(jog_speed_frame, text="Media", value='media', variable=self.jog_speed_var,
                        command=self.on_speed_change).grid(row=0, column=1, padx=6)
        ttk.Radiobutton(jog_speed_frame, text="Rápida", value='rapida', variable=self.jog_speed_var,
                        command=self.on_speed_change).grid(row=0, column=2, padx=6)
        self.jog_speed_label = ttk.Label(jog_speed_frame, text="Velocidad: Media", font=("Arial", 10, "bold"))
        self.jog_speed_label.grid(row=0, column=3, padx=10)
        
        # === ISOLOGOTIPO (Top Right) ===
        try:
            logo_path = os.path.join("images", "isologotipo.png")
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                # Redimensionar manteniendo proporción (altura de 60px para el header)
                aspect_ratio = logo_img.width / logo_img.height
                logo_img = logo_img.resize((int(60 * aspect_ratio), 60), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                self.logo_label = ttk.Label(control_frame, image=self.logo_photo)
                self.logo_label.grid(row=0, column=9, rowspan=2, padx=20, sticky=tk.E)
        except Exception as e:
            print(f"Error cargando logotipo: {e}")
            
        # === FILA 1: PANELES PRINCIPALES CON PANED WINDOW ===
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # PANEL IZQUIERDO: CONTROL
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        # Control manual
        jog_frame = ttk.LabelFrame(left_frame, text="Control Manual (Paso a Paso)", padding="10")
        jog_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Botones directivos
        tk.Button(jog_frame, text="Y+", command=lambda: self.jog_step('y', '+'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=0, column=1, padx=3, pady=2)
        
        tk.Button(jog_frame, text="X-", command=lambda: self.jog_step('x', '-'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=1, column=0, padx=3, pady=2)
        tk.Button(jog_frame, text="X+", command=lambda: self.jog_step('x', '+'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=1, column=2, padx=3, pady=2)
        
        tk.Button(jog_frame, text="Y-", command=lambda: self.jog_step('y', '-'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=2, column=1, padx=3, pady=2)
        
        tk.Button(jog_frame, text="Z+", command=lambda: self.jog_step('z', '+'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=3, column=0, padx=3, pady=2)
        tk.Button(jog_frame, text="Z-", command=lambda: self.jog_step('z', '-'), 
                  width=5, height=1, font=("Arial", 11, "bold")).grid(row=3, column=2, padx=3, pady=2)
        
        ttk.Button(jog_frame, text="🏠 Establecer Origen", command=self.set_origin, 
                   width=25).grid(row=4, column=0, columnspan=3, pady=8, sticky=(tk.W, tk.E))
        ttk.Button(jog_frame, text="🧭 Buscar Origen Asistido", command=self.run_origin_wizard,
               width=25).grid(row=5, column=0, columnspan=3, pady=2, sticky=(tk.W, tk.E))
        
        # G-code list
        gcode_label = ttk.Label(left_frame, text="Lista G-code", font=("Arial", 10, "bold"))
        gcode_label.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.gcode_area = scrolledtext.ScrolledText(left_frame, width=30, height=15, font=("Courier", 9))
        self.gcode_area.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Botón cargar
        self.load_btn = ttk.Button(left_frame, text="📂 Cargar G-code", command=self.open_file, width=30)
        self.load_btn.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Tag para resaltar línea actual
        self.gcode_area.tag_configure("current_line", background="#ffffcf", foreground="black", font=("Courier", 9, "bold"))
        
        # Botón centrar en origen
        self.normalize_btn = ttk.Button(left_frame, text="🎯 Centrar diseño en Origen (0,0)", command=self.normalize_gcode, state=tk.DISABLED, width=30)
        self.normalize_btn.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # PANEL CENTRAL: VISUALIZACIÓN
        center_frame = ttk.Frame(paned)
        paned.add(center_frame, weight=3) # Un poco más de peso pero con figura inicial menor
        
        viz_label = ttk.Label(center_frame, text="Visualización de Trayectoria", font=("Arial", 10, "bold"))
        viz_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.fig = Figure(figsize=(5, 5), dpi=100) # Tamaño inicial reducido para dar espacio
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, 95)
        self.ax.set_ylim(-5, 95)
        self.ax.set_aspect('equal', adjustable='box')
        
        # Límites del área de trabajo (inicial 80x80)
        self.work_area_rect = patches.Rectangle((0, 0), 80, 80, linewidth=1.5, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(self.work_area_rect)
        self.work_area_text = self.ax.text(40, 81, 'Área de Trabajo: 80×80mm', ha='center', fontsize=8, color='red', weight='bold')
        
        # Inicializar punto cruz
        self.machine_dot, = self.ax.plot([0], [0], 'xc', markersize=14, markeredgewidth=3, label='Posición CNC', zorder=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=center_frame)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # PANEL DERECHO: INFORMACIÓN
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # Streaming
        stream_frame = ttk.LabelFrame(right_frame, text="Ejecución", padding="5")
        stream_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.start_btn = tk.Button(stream_frame, text="▶️ INICIAR", command=self.start_stream, 
                                    state=tk.DISABLED, width=11, height=1, bg="#4CAF50", fg="white", 
                                    font=("Arial", 9, "bold"), padx=4, pady=2)
        self.start_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.pause_btn = tk.Button(stream_frame, text="⏸️ PAUSAR", command=self.pause_stream, 
                                    state=tk.DISABLED, width=11, height=1, bg="#FFC107", 
                                    font=("Arial", 9, "bold"), padx=4, pady=2)
        self.pause_btn.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.stop_btn = tk.Button(stream_frame, text="⏹️ DETENER", command=self.stop_stream, 
                                   state=tk.DISABLED, width=11, height=1, bg="#F44336", fg="white", 
                                   font=("Arial", 9, "bold"), padx=4, pady=2)
        self.stop_btn.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3)
        
        # Posición
        pos_frame = ttk.LabelFrame(right_frame, text="Posición Actual", padding="5")
        pos_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(pos_frame, text="X:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W)
        self.x_label = ttk.Label(pos_frame, text="0.00 mm", font=("Arial", 11, "bold"), foreground="blue")
        self.x_label.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(pos_frame, text="Y:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W)
        self.y_label = ttk.Label(pos_frame, text="0.00 mm", font=("Arial", 11, "bold"), foreground="blue")
        self.y_label.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(pos_frame, text="Z:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W)
        self.z_label = ttk.Label(pos_frame, text="1.00", font=("Arial", 11, "bold"), foreground="blue")
        self.z_label.grid(row=2, column=1, sticky=tk.W, padx=10)

        ttk.Button(pos_frame, text="Actualizar", command=self.refresh_status, width=18).grid(row=3, column=0, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(pos_frame, text="Marcar aquí como 0,0", command=self.mark_here_as_origin, width=18).grid(row=3, column=1, pady=5, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(pos_frame, text="Probar Límites", command=self.test_limits, width=18).grid(row=4, column=0, columnspan=2, pady=3, sticky=(tk.W, tk.E))
        
        # Progreso
        progress_frame = ttk.LabelFrame(right_frame, text="Progreso", padding="5")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.time_label = ttk.Label(progress_frame, text="⏱️ Tiempo Estimado:\nF1000: --m --s  |  F2000: --m --s", 
                                   font=("Arial", 9, "bold"), foreground="green", justify=tk.CENTER)
        self.time_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=200)
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        status_inner = ttk.Frame(progress_frame)
        status_inner.grid(row=2, column=0, sticky=(tk.W, tk.E))
        self.progress_label = ttk.Label(status_inner, text="0 / 0 líneas (0%)", font=("Arial", 9, "bold"))
        self.progress_label.pack(side=tk.LEFT)
        self.elapsed_time_label = ttk.Label(status_inner, text="⏳: 00:00", font=("Arial", 9, "bold"), foreground="blue")
        self.elapsed_time_label.pack(side=tk.RIGHT)
        
        # === FILA 2: LOG Y TERMINAL MANUAL ===
        log_frame = ttk.LabelFrame(main_frame, text="Log de Comandos", padding="5")
        log_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, width=200, height=8, font=("Courier", 8))
        self.log_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Terminal Manual
        terminal_frame = ttk.Frame(log_frame)
        terminal_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5,0))
        ttk.Label(terminal_frame, text="Terminal Manual:", font=("Arial", 9, "bold")).pack(side=tk.LEFT)
        self.manual_cmd_var = tk.StringVar()
        self.manual_cmd_entry = ttk.Entry(terminal_frame, textvariable=self.manual_cmd_var, width=50)
        self.manual_cmd_entry.pack(side=tk.LEFT, padx=5)
        self.manual_cmd_entry.bind('<Return>', lambda e: self.send_manual_command())
        ttk.Button(terminal_frame, text="Enviar Comandos (Enter)", command=self.send_manual_command).pack(side=tk.LEFT)
        
        # Configurar pesos
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        left_frame.rowconfigure(2, weight=1)
        center_frame.rowconfigure(1, weight=1)
    
    def jog_step(self, axis, direction):
        """Llama al controlador con velocidad actual"""
        self.controller.jog_step(
            axis,
            direction,
            step_key=self.controller.current_step,
            speed_key=self.controller.current_speed
        )

    def on_speed_change(self):
        speed_key = self.jog_speed_var.get()
        self.controller.set_speed(speed_key)
        profile = self.controller.JOG_SPEEDS.get(speed_key, self.controller.JOG_SPEEDS['media'])
        self.jog_speed_label.configure(text=f"Velocidad: {profile['label']}")

    def refresh_status(self):
        self.controller.get_status()

    def test_limits(self):
        if not self.controller.port or not self.controller.port.is_open:
            messagebox.showwarning("Límites", "Conecta la placa para ejecutar la prueba.")
            return
        self.controller.test_limits()
        
    def send_manual_command(self):
        cmd = self.manual_cmd_var.get().strip()
        if cmd:
            if not self.controller.port or not self.controller.port.is_open:
                messagebox.showwarning("Terminal", "Conecta la placa primero para enviar comandos.")
                return
            self.log(f"Teclado: {cmd}")
            self.controller.send_command(cmd)
            self.manual_cmd_var.set("")
            
    def on_profile_change(self, event=None):
        """Maneja el cambio de perfil de máquina (80mm o 40mm)"""
        profile = self.profile_var.get()
        if "80mm" in profile:
            limit = 80
        else:
            limit = 40
            
        self.controller.set_machine_limits(limit)
        
        # Actualizar visualización (solo si ya se ha renderizado)
        try:
            self.ax.set_xlim(-5, 95)
            self.ax.set_ylim(-5, 95)
            self.plot_gcode() # Redibuja todo incluyendo los nuevos límites
        except:
            pass
            
    def update_time_estimation(self):
        """Calcula el tiempo estimado basado en distintas velocidades (F) y retrasos del software/hardware"""
        # +0.5s por comando de servo (constante)
        sec_servo = sum(1 for line in self.controller.gcode if "M300" in line.upper()) * 0.5
        
        # En el bucle de envío (start_stream), hay un time.sleep(0.3) forzado por cada comando
        sec_software_delay = len(self.controller.gcode) * 0.3
        
        # Tiempo a F1000 (1000 mm/min = 16.66 mm/seg)
        sec_move_1000 = self.parser.total_distance / 16.66
        total_sec_1000 = sec_move_1000 + sec_servo + sec_software_delay
        mins_1000 = int(total_sec_1000 // 60)
        secs_1000 = int(total_sec_1000 % 60)
        
        # Tiempo a F2000 (2000 mm/min = 33.33 mm/seg)
        sec_move_2000 = self.parser.total_distance / 33.33
        total_sec_2000 = sec_move_2000 + sec_servo + sec_software_delay
        mins_2000 = int(total_sec_2000 // 60)
        secs_2000 = int(total_sec_2000 % 60)
        
        self.time_label.configure(text=f"⏱️ Tiempo Estimado:\nF1000: {mins_1000}m {secs_1000}s  |  F2000: {mins_2000}m {secs_2000}s")
    
    def set_step(self, step_distance):
        self.controller.set_step(step_distance)
        self.speed_label.configure(text=f"Paso: {step_distance.upper()}")

    def mark_here_as_origin(self):
        if not self.controller.port or not self.controller.port.is_open:
            messagebox.showwarning("Origen", "Conecta la placa antes de marcar el origen.")
            return

        if self.controller.mark_current_as_origin():
            self.log("✅ GUI actualizada: la posición actual fue marcada como (0,0,0)")

    def run_origin_wizard(self):
        """Abre un asistente no modal para fijar el origen sin bloquear X/Y."""
        if not self.controller.port or not self.controller.port.is_open:
            self.log("⚠️ Conecta la placa antes de iniciar el asistente de origen")
            return

        if getattr(self, 'origin_wizard_window', None) and self.origin_wizard_window.winfo_exists():
            self.origin_wizard_window.lift()
            self.origin_wizard_window.focus_force()
            return

        self.origin_wizard_prev_step = self.controller.current_step
        self.origin_wizard_prev_speed = self.controller.current_speed
        self.origin_wizard_stage = 'intro'

        window = tk.Toplevel(self.root)
        window.title("Origen asistido")
        window.geometry("520x320")
        window.transient(self.root)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", self.close_origin_wizard)
        self.origin_wizard_window = window

        container = ttk.Frame(window, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        self.origin_wizard_title = ttk.Label(container, text="Asistente de origen", font=("Arial", 13, "bold"))
        self.origin_wizard_title.pack(anchor=tk.W)

        self.origin_wizard_text = ttk.Label(
            container,
            text=(
                "Usa esta ventana como guía.\n"
                "Los botones X/Y siguen disponibles mientras el asistente está abierto.\n\n"
                "1) Aproximación gruesa con 5mm\n"
                "2) Ajuste fino con 0.1mm\n"
                "3) Fijar origen y verificar offset"
            ),
            justify=tk.LEFT
        )
        self.origin_wizard_text.pack(anchor=tk.W, pady=(10, 12))

        self.origin_wizard_status = ttk.Label(container, text="Estado: espera inicial", foreground="#0B5CAD")
        self.origin_wizard_status.pack(anchor=tk.W, pady=(0, 12))

        button_row = ttk.Frame(container)
        button_row.pack(fill=tk.X, pady=4)

        ttk.Button(button_row, text="Aproximación gruesa", command=self.origin_wizard_set_coarse).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Ajuste fino", command=self.origin_wizard_set_fine).pack(side=tk.LEFT, padx=4)
        ttk.Button(button_row, text="Fijar y verificar", command=self.origin_wizard_commit).pack(side=tk.LEFT, padx=4)

        bottom_row = ttk.Frame(container)
        bottom_row.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(bottom_row, text="Cerrar", command=self.close_origin_wizard).pack(side=tk.RIGHT)

        self.origin_wizard_update_status("Asistente listo. Puedes mover X/Y sin bloquear la interfaz.")

    def origin_wizard_update_status(self, message):
        if getattr(self, 'origin_wizard_status', None):
            self.origin_wizard_status.configure(text=f"Estado: {message}")

    def origin_wizard_set_coarse(self):
        self.set_step('5mm')
        self.jog_speed_var.set('media')
        self.on_speed_change()
        self.origin_wizard_stage = 'coarse'
        self.origin_wizard_update_status("Aproximación gruesa activa. Usa X/Y para acercarte a la esquina de referencia.")

    def origin_wizard_set_fine(self):
        self.set_step('0.1mm')
        self.jog_speed_var.set('lenta')
        self.on_speed_change()
        self.origin_wizard_stage = 'fine'
        self.origin_wizard_update_status("Ajuste fino activo. Haz micro-movimientos y luego fija el origen.")

    def origin_wizard_commit(self):
        if not self.controller.port or not self.controller.port.is_open:
            self.origin_wizard_update_status("No hay conexión con la placa.")
            return

        self.origin_wizard_update_status("Fijando origen...")
        self.controller.set_origin()
        self.root.after(350, self.origin_wizard_finish)

    def origin_wizard_finish(self):
        ok_origin, pos = self.controller.verify_origin_offset(tolerance=0.30)

        self.set_step(self.origin_wizard_prev_step)
        self.jog_speed_var.set(self.origin_wizard_prev_speed)
        self.on_speed_change()

        if ok_origin:
            self.origin_wizard_update_status(
                f"Origen verificado OK. X={pos['x']:.3f}, Y={pos['y']:.3f}, Z={pos['z']:.3f}"
            )
            self.log("✅ Origen asistido completado con verificación OK")
        else:
            self.origin_wizard_update_status(
                f"Desviación detectada. X={pos['x']:.3f}, Y={pos['y']:.3f}, Z={pos['z']:.3f}. Repite el ajuste fino."
            )
            self.log("⚠️ Origen asistido finalizó con desviación en verificación")

    def close_origin_wizard(self):
        if getattr(self, 'origin_wizard_window', None) and self.origin_wizard_window.winfo_exists():
            self.origin_wizard_window.destroy()
        self.origin_wizard_window = None
        self.origin_wizard_stage = None
        if getattr(self, 'origin_wizard_prev_step', None):
            self.set_step(self.origin_wizard_prev_step)
        if getattr(self, 'origin_wizard_prev_speed', None):
            self.jog_speed_var.set(self.origin_wizard_prev_speed)
            self.on_speed_change()
    
    def update_ports(self):
        ports = self.controller.find_serial_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        self.log(f"🔌 Puertos encontrados: {ports if ports else 'Ninguno'}")
    
    def toggle_connection(self):
        if not self.controller.port or not self.controller.port.is_open:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Selecciona un puerto")
                return
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="Desconectar")
                self.start_btn.configure(state=tk.NORMAL)
                # Forzar actualización de límites al conectar
                self.on_profile_change()
                self.offer_origin_wizard_on_connect()
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="Conectar")
            self.start_btn.configure(state=tk.DISABLED)

    def offer_origin_wizard_on_connect(self):
        """Abre el asistente de origen sin bloquear el control manual."""
        self.run_origin_wizard()
    
    def open_file(self):
        """Abre diálogo para cargar G-code"""
        fn = filedialog.askopenfilename(
            title="Seleccionar archivo G-code",
            filetypes=[("G-code", "*.gcode *.nc *.g"), ("Todos", "*.*")]
        )
        if fn:
            self.log(f"📂 Cargando: {fn}")
            if self.controller.load_gcode(fn):
                self.gcode_area.delete(1.0, tk.END)
                for i, line in enumerate(self.controller.gcode, 1):
                    self.gcode_area.insert(tk.END, f"{i:4d}: {line}\n")
                
                if self.parser.parse(fn):
                    self.plot_gcode()
                    self.update_time_estimation()
                    self.log(f"✅ Visualización actualizada: {len(self.parser.x_points)} puntos")
                
                self.start_btn.configure(state=tk.NORMAL)
                self.normalize_btn.configure(state=tk.NORMAL)
    
    def plot_gcode(self):
        """Dibuja trayectoria de G-code"""
        self.ax.clear()
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, 95)
        self.ax.set_ylim(-5, 95)
        self.ax.set_aspect('equal', adjustable='box')
        
        # Límites del área de trabajo
        limit = self.controller.machine_limits['x']['max']
        self.work_area_rect = patches.Rectangle((0, 0), limit, limit, linewidth=1.5, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(self.work_area_rect)
        self.work_area_text = self.ax.text(limit/2, limit+1, f'Área de Trabajo: {limit}×{limit}mm', ha='center', fontsize=8, color='red', weight='bold')
        
        # Trayectoria
        if self.parser.x_points and self.parser.y_points:
            self.ax.plot(self.parser.x_points, self.parser.y_points, 'b-', linewidth=2.5, label='Trayectoria')
            self.ax.plot(self.parser.x_points[0], self.parser.y_points[0], 'go', markersize=10, label='Inicio')
            if len(self.parser.x_points) > 1:
                self.ax.plot(self.parser.x_points[-1], self.parser.y_points[-1], 'rs', markersize=10, label='Final')
            
            # Leyenda fuera del dibujo (arriba)
            self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=9, frameon=False)
        
        # Re-crear punto de rastreo ya que ax.clear() lo destruyó
        self.machine_dot, = self.ax.plot([self.controller.position['x']], [self.controller.position['y']], 'xc', markersize=14, markeredgewidth=3, label='Posición CNC', zorder=5)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def normalize_gcode(self):
        """Traslada las coordenadas de todo el Gcode para que el punto más bajo/izquierdo toque el origen (0,0)"""
        if not self.parser.x_points or not self.controller.gcode:
            return
            
        min_x = min(self.parser.x_points)
        min_y = min(self.parser.y_points)
        
        # Si ya está alineado (con margen de 0.1mm), no hacemos nada
        if abs(min_x) < 0.1 and abs(min_y) < 0.1:
            self.log("✅ El G-code ya está alineado al origen (0,0)")
            return
            
        self.log(f"🔧 Desplazando diseño... Offset aplicado: X {-min_x:.2f}mm, Y {-min_y:.2f}mm")
        
        # Modificar las líneas de G-code virtualmente en memoria
        new_gcode = []
        for line in self.controller.gcode:
            new_line = line
            
            # Buscamos y reemplazamos coord X
            x_match = re.search(r'X([-+]?\d+\.?\d*)', new_line)
            if x_match:
                x_val = float(x_match.group(1))
                new_x = x_val - min_x
                new_line = new_line[:x_match.start(1)] + f"{new_x:.3f}" + new_line[x_match.end(1):]
                
            # Buscamos y reemplazamos coord Y
            y_match = re.search(r'Y([-+]?\d+\.?\d*)', new_line)
            if y_match:
                y_val = float(y_match.group(1))
                new_y = y_val - min_y
                new_line = new_line[:y_match.start(1)] + f"{new_y:.3f}" + new_line[y_match.end(1):]
                
            new_gcode.append(new_line)
            
        self.controller.gcode = new_gcode
        
        # Actualizar puntos matemáticos del parser instantáneamente
        self.parser.x_points = [x - min_x for x in self.parser.x_points]
        self.parser.y_points = [y - min_y for y in self.parser.y_points]
        
        # Actualizar área de texto para mostrar las nuevas coordenadas
        self.gcode_area.delete(1.0, tk.END)
        for i, line in enumerate(self.controller.gcode[:40], 1):
            self.gcode_area.insert(tk.END, f"{i:3d}: {line}\n")
            
        # Repintar la UI
        self.plot_gcode()
        self.log("✅ Diseño re-centrado con éxito en (0,0)")

    def set_origin(self):
        self.controller.set_origin()
    
    def start_stream(self):
        self.controller.start_streaming()
        self.start_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
        
        # Reiniciar cronómetro si es inicio limpio
        if self.controller.gcode_index == 0:
            self.job_seconds = 0
    
    def pause_stream(self):
        self.controller.pause_streaming()
        state_text = "Reanudado" if not self.controller.paused else "Pausado"
        self.log(f"⏸️  Streaming {state_text}")
    
    def stop_stream(self):
        self.controller.stop_streaming()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
    
    def on_job_completed(self):
        # Se llama desde el hilo de streaming, lo pasamos al hilo principal
        self.root.after(0, self._show_completion_alert)

    def _show_completion_alert(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        
        mins = self.job_seconds // 60
        secs = self.job_seconds % 60
        
        self.log(f"🔔 NOTIFICACIÓN: Trabajo completado en {mins:02d}:{secs:02d}")
        
        # Mostrar caja de diálogo asegurando que esté en frente
        messagebox.showinfo("Proceso Finalizado", 
                             f"¡El archivo G-code ha terminado de ejecutarse!\n\n"
                             f"⏱️ Tiempo total: {mins:02d}:{secs:02d}\n"
                             f"📍 La máquina ha retornado al origen.",
                             parent=self.root)
        
    def log(self, message):
        """Añade un mensaje al log de forma segura para hilos"""
        self.root.after(0, self._append_to_log, message)
        
    def _append_to_log(self, message):
        """Método interno ejecutado en el hilo principal"""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
    
    def update_position(self):
        limit = self.controller.machine_limits['x']['max']
        self.x_label.configure(text=f"{self.controller.position['x']:.2f} / {limit:.2f} mm")
        self.y_label.configure(text=f"{self.controller.position['y']:.2f} / {limit:.2f} mm")
        # Mostramos el ángulo real del servo para Z
        self.z_label.configure(text=f"{self.controller.servo_angle}° / 180°")
        
        # Animación del punto cruz rastreador
        if hasattr(self, 'machine_dot'):
            self.machine_dot.set_data([self.controller.position['x']], [self.controller.position['y']])
            if self.controller.streaming or getattr(self.controller, 'mpos', None):
                self.canvas.draw_idle()
                
        self.root.after(200, self.update_position)
        
    def update_timer(self):
        if self.controller.streaming and not self.controller.paused:
            self.job_seconds += 1
            mins = self.job_seconds // 60
            secs = self.job_seconds % 60
            self.elapsed_time_label.configure(text=f"⏳ Transcurrido: {mins:02d}:{secs:02d}")
        self.root.after(1000, self.update_timer)
    
    def update_progress(self):
        if self.controller.gcode:
            total = len(self.controller.gcode)
            current = self.controller.gcode_index
            percent = int((current / total) * 100) if total > 0 else 0
            
            self.progress_var.set(percent)
            self.progress_label.configure(text=f"{current} / {total} líneas ({percent}%)")
            
            # Resaltar la línea actual en el área de G-code (ajustando a 1-indexed de Tkinter)
            if self.controller.streaming:
                self.highlight_gcode_line(current + 1)
        
        self.root.after(100, self.update_progress)

    def highlight_gcode_line(self, line_num):
        """Resalta la línea actual y hace scroll para mantenerla visible"""
        self.gcode_area.tag_remove("current_line", "1.0", tk.END)
        if line_num > 0:
            pos = f"{line_num}.0"
            end = f"{line_num}.end"
            self.gcode_area.tag_add("current_line", pos, end)
            self.gcode_area.see(pos)
    
    def on_closing(self):
        if messagebox.askokcancel("Salir", "¿Cerrar aplicación?"):
            self.controller.disconnect()
            self.root.destroy()

def main():
    root = tk.Tk()
    app = GCodeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
