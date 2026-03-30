"""
CNC PLOTTER CONTROLLER - OPTIMIZADO PARA MOTORES LINEALES PASO A PASO
=====================================================================
✅ Motores: 2 Fase 4 Tornillo (Ángulo 18°, Paso 0.020in)
✅ Voltaje: 4-9V DC, 500mA por fase
✅ Velocidad máxima: 0.984 in/s (25mm/s)
✅ Resolución: 0.001in por micro-paso
✅ Cálculos optimizados para estos motores específicos
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

# ===== CONSTANTES DEL MOTOR =====
# Motor: 2 Fase 4, Ángulo 18°
STEP_ANGLE = 18  # grados
PHASES = 2  # fases
MICROSTEPS = 4  # microstepping (1/4 stepping)

# Cálculo de pasos por revolución
# 360° / 18° = 20 pasos por revolución
# Con 4x microstepping = 80 micropasos por revolución
STEPS_PER_REV = 360 / STEP_ANGLE  # 20 pasos
MICROSTEPS_PER_REV = STEPS_PER_REV * MICROSTEPS  # 80 micropasos

# Tornillo
SCREW_PITCH = 0.020  # pulgadas (0.508mm)
SCREW_PITCH_MM = SCREW_PITCH * 25.4  # convertir a mm = 0.508mm

# Distancia por paso completo (sin microstepping)
DISTANCE_PER_STEP = SCREW_PITCH  # 0.020 in = 0.508 mm
DISTANCE_PER_STEP_MM = DISTANCE_PER_STEP * 25.4  # mm

# Distancia por microstep (1/4 del paso)
DISTANCE_PER_MICROSTEP = DISTANCE_PER_STEP / MICROSTEPS  # 0.005 in = 0.127 mm
DISTANCE_PER_MICROSTEP_MM = DISTANCE_PER_MICROSTEP * 25.4  # mm

# Carrera efectiva
EFFECTIVE_STROKE_IN = 3.150  # pulgadas
EFFECTIVE_STROKE_MM = EFFECTIVE_STROKE_IN * 25.4  # mm = 80.01 mm

# Velocidad máxima
MAX_SPEED_IN_S = 0.984  # pulgadas/segundo
MAX_SPEED_MM_S = MAX_SPEED_IN_S * 25.4  # mm/s = 25 mm/s

# Voltaje
MIN_VOLTAGE = 4  # Volts
MAX_VOLTAGE = 9  # Volts
DEFAULT_VOLTAGE = 6  # Volts (seguro)

print(f"""
=== ESPECIFICACIONES DEL MOTOR ===
Tipo: 2 Fase 4, Motor Paso a Paso Híbrido
Ángulo de Paso: {STEP_ANGLE}°
Pasos por Revolución: {int(STEPS_PER_REV)}
Micropasos por Revolución: {int(MICROSTEPS_PER_REV)}
Paso de Tornillo: {SCREW_PITCH} in = {SCREW_PITCH_MM:.3f} mm
Distancia por Paso: {DISTANCE_PER_STEP} in = {DISTANCE_PER_STEP_MM:.3f} mm
Distancia por Microstep: {DISTANCE_PER_MICROSTEP} in = {DISTANCE_PER_MICROSTEP_MM:.3f} mm
Carrera Efectiva: {EFFECTIVE_STROKE_IN} in = {EFFECTIVE_STROKE_MM:.2f} mm
Velocidad Máxima: {MAX_SPEED_IN_S} in/s = {MAX_SPEED_MM_S:.2f} mm/s
Voltaje: {MIN_VOLTAGE}-{MAX_VOLTAGE}V DC, 500mA/fase
====================================
""")

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
    
    def parse(self, filename):
        """Parsea archivo G-code"""
        self.lines = []
        self.x_points = [0]
        self.y_points = [0]
        self.current_x = 0
        self.current_y = 0
        self.mode_absolute = True
        
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
            
            self.current_x = new_x
            self.current_y = new_y
            self.x_points.append(new_x)
            self.y_points.append(new_y)


# ===== CONTROLADOR OPTIMIZADO =====
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
        
        # Límites calibrados en mm (basados en carrera efectiva)
        self.calibrated_limits = {
            'x': {'min': 0, 'max': EFFECTIVE_STROKE_MM},
            'y': {'min': 0, 'max': EFFECTIVE_STROKE_MM},
            'z': {'min': 0, 'max': 1}
        }
        
        # Velocidades en mm/s (respetando velocidad máxima del motor)
        self.SPEEDS = {
            'lento': 2.0,      # 2 mm/s = 16 pasos/s
            'normal': 5.0,     # 5 mm/s = 40 pasos/s
            'rapido': 10.0     # 10 mm/s = 80 pasos/s (conservador)
        }
        # Nota: Máx teórico es 25 mm/s, pero 10 mm/s es más seguro
        
        self.current_speed = 'normal'
        
        # Cálculo de STEPS_PER_MM para este motor
        # Distancia por microstep = 0.127 mm
        # Entonces: 1 mm = 1/0.127 = 7.87 micropasos ≈ 8 micropasos
        self.STEPS_PER_MM = 1.0 / DISTANCE_PER_MICROSTEP_MM  # ≈ 7.87 pasos/mm
        
        self.log_callback = None
        self.limits_callback = None
        self.serial_lock = threading.Lock()
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def set_limits_callback(self, callback):
        self.limits_callback = callback
    
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
    
    def update_limits_display(self):
        if self.limits_callback:
            self.limits_callback()
    
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
            self.log(f"📊 Motor: Paso {STEP_ANGLE}°, {int(MICROSTEPS_PER_REV)} micropasos/rev")
            self.log(f"📊 Resolución: {DISTANCE_PER_MICROSTEP_MM:.4f}mm por microstep")
            self.log(f"📊 Velocidad máxima configurada: {self.SPEEDS['rapido']:.1f}mm/s")
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
                        self.log(f"← {response}")
                        
                        if response.startswith("<"):
                            try:
                                pos_str = response.split("MPos:")[1].split("|")[0]
                                x, y, z = map(float, pos_str.split(","))
                                self.position = {'x': x, 'y': y, 'z': z}
                                self.update_limits_display()
                            except:
                                pass
                
                time.sleep(0.01)
            except Exception as e:
                self.log(f"❌ Error lectura: {e}")
                break
    
    def send_command(self, command):
        if not self.port or not self.port.is_open:
            return False
        
        try:
            with self.serial_lock:
                if not command.endswith('\n'):
                    command = command + '\n'
                
                self.port.write(command.encode())
                self.log(f"→ {command.strip()}")
                return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False
    
    def check_limits(self, x=None, y=None, z=None):
        """Verifica límites calibrados"""
        if x is not None:
            if x < self.calibrated_limits['x']['min'] or x > self.calibrated_limits['x']['max']:
                return False
        if y is not None:
            if y < self.calibrated_limits['y']['min'] or y > self.calibrated_limits['y']['max']:
                return False
        if z is not None:
            if z < self.calibrated_limits['z']['min'] or z > self.calibrated_limits['z']['max']:
                return False
        return True
    
    def calculate_feedrate(self, speed_mm_s):
        """Calcula feedrate en pasos/segundo para G-code"""
        # F en G-code es típicamente en mm/min
        # Convertir mm/s a mm/min: mm/s * 60
        feedrate_mm_min = speed_mm_s * 60
        return feedrate_mm_min
    
    def jog_step(self, axis, direction, speed_type='normal'):
        """Movimiento paso a paso mejorado"""
        if not self.port or not self.port.is_open:
            self.log("❌ Sin conexión a Arduino")
            return False
        
        axis = axis.upper()
        speed_mm_s = self.SPEEDS.get(speed_type, 5.0)
        
        # Distancia por paso = 1 microstep = 0.127 mm (aproximado)
        distance_mm = DISTANCE_PER_MICROSTEP_MM
        
        # Calcular nueva posición
        new_pos = self.position.copy()
        if direction == '+':
            new_pos[axis.lower()] += distance_mm
        else:
            new_pos[axis.lower()] -= distance_mm
        
        # Verificar límites
        if not self.check_limits(
            x=new_pos['x'] if axis == 'X' else None,
            y=new_pos['y'] if axis == 'Y' else None,
            z=new_pos['z'] if axis == 'Z' else None
        ):
            current_val = new_pos[axis.lower()]
            self.log(f"❌ LÍMITE alcanzado: {axis}={current_val:.3f}mm")
            return False
        
        # Calcular feedrate
        feedrate = self.calculate_feedrate(speed_mm_s)
        
        # Enviar comando
        sign = "+" if direction == "+" else ""
        dist = distance_mm if direction == "+" else -distance_mm
        
        commands = [
            "G91",
            f"G1 {axis}{sign}{dist:.4f} F{feedrate:.0f}",
            "G90"
        ]
        
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(0.05)
        
        time.sleep(0.2)
        self.send_command("?")
        
        self.log(f"📍 {speed_type.upper()}: {axis}{direction} {distance_mm:.4f}mm")
        return True
    
    def record_limit(self, axis, direction):
        """Registra un límite manual"""
        axis = axis.upper()
        current_pos = self.position[axis.lower()]
        
        if direction == '+':
            self.calibrated_limits[axis.lower()]['max'] = current_pos
            self.log(f"📍 Límite MAX {axis}: {current_pos:.3f}mm registrado")
        else:
            self.calibrated_limits[axis.lower()]['min'] = current_pos
            self.log(f"📍 Límite MIN {axis}: {current_pos:.3f}mm registrado")
        
        self.update_limits_display()
    
    def reset_limits(self):
        """Resetea límites a valores por defecto"""
        self.calibrated_limits = {
            'x': {'min': 0, 'max': EFFECTIVE_STROKE_MM},
            'y': {'min': 0, 'max': EFFECTIVE_STROKE_MM},
            'z': {'min': 0, 'max': 1}
        }
        self.log("🔄 Límites reiniciados a carrera efectiva del motor")
        self.update_limits_display()
    
    def set_speed(self, speed_type):
        if speed_type in self.SPEEDS:
            self.current_speed = speed_type
            self.log(f"⚙️  Velocidad: {speed_type.upper()} ({self.SPEEDS[speed_type]:.1f}mm/s)")
            return True
        return False
    
    def set_origin(self):
        """Establece origen (0,0,1)"""
        if not self.port or not self.port.is_open:
            return False
        
        self.log("📌 Estableciendo origen (0,0,1)...")
        commands = [
            "G90",
            "G1 X0 Y0",
            "M300 S50"
        ]
        
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(0.3)
        
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        time.sleep(0.2)
        self.send_command("?")
        self.log("✅ Origen establecido: (0,0,1)")
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
            self.send_command("G90")
            time.sleep(0.2)
            
            while self.gcode_index < len(self.gcode) and self.streaming:
                if self.paused:
                    time.sleep(0.1)
                    continue
                
                line = self.gcode[self.gcode_index]
                self.send_command(line)
                self.gcode_index += 1
                time.sleep(0.3)
            
            if self.streaming:
                self.log("✅ G-code completado")
                self.return_to_origin()
        
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
            "M300 S50",
            "G90",
            "G1 X0 Y0"
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
        self.root.title("CNC Plotter - Motores Paso a Paso Lineales (18°)")
        self.root.geometry("1700x1000")
        
        self.controller = GCodeController()
        self.controller.set_log_callback(self.log)
        self.controller.set_limits_callback(self.update_limits_info)
        self.parser = GCodeParser()
        
        self.create_widgets()
        self.update_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_position()
        self.update_progress()
    
    def create_widgets(self):
        """Crea interfaz gráfica"""
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
        
        # Velocidades
        speed_frame = ttk.LabelFrame(control_frame, text="Velocidad", padding="5")
        speed_frame.grid(row=0, column=4, columnspan=3, sticky=(tk.W, tk.E), padx=10)
        
        ttk.Button(speed_frame, text="🐢 LENTO\n2mm/s", 
                   command=lambda: self.set_speed('lento'), width=10).grid(row=0, column=0, padx=2)
        ttk.Button(speed_frame, text="🚗 NORMAL\n5mm/s", 
                   command=lambda: self.set_speed('normal'), width=10).grid(row=0, column=1, padx=2)
        ttk.Button(speed_frame, text="🚀 RÁPIDO\n10mm/s", 
                   command=lambda: self.set_speed('rapido'), width=10).grid(row=0, column=2, padx=2)
        
        self.speed_label = ttk.Label(control_frame, text="Velocidad: NORMAL (5mm/s)", font=("Arial", 10, "bold"))
        self.speed_label.grid(row=1, column=4, columnspan=3)
        
        # === INFORMACIÓN DEL MOTOR ===
        motor_info_frame = ttk.LabelFrame(control_frame, text="Especificaciones del Motor", padding="5")
        motor_info_frame.grid(row=0, column=7, columnspan=2, sticky=(tk.W, tk.E), padx=10)
        
        motor_info = f"""Tipo: 2 Fase 4, Híbrido
Ángulo: {STEP_ANGLE}° | Pasos/Rev: {int(STEPS_PER_REV)}
Micropasos: {int(MICROSTEPS_PER_REV)}/Rev
Resolución: {DISTANCE_PER_MICROSTEP_MM:.4f}mm
Carrera: {EFFECTIVE_STROKE_MM:.2f}mm
Voltaje: {MIN_VOLTAGE}-{MAX_VOLTAGE}V DC"""
        
        ttk.Label(motor_info_frame, text=motor_info, font=("Courier", 8)).grid(row=0, column=0, padx=5)
        
        # === FILA 1: PANELES PRINCIPALES ===
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # PANEL IZQUIERDO: CONTROL
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        
        # Control manual
        jog_frame = ttk.LabelFrame(left_frame, text="Control Manual XY", padding="10")
        jog_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        tk.Button(jog_frame, text="Y+", command=lambda: self.jog_step('y', '+'), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Button(jog_frame, text="X-", command=lambda: self.jog_step('x', '-'), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=5)
        tk.Button(jog_frame, text="X+", command=lambda: self.jog_step('x', '+'), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=1, column=2, padx=5, pady=5)
        
        tk.Button(jog_frame, text="Y-", command=lambda: self.jog_step('y', '-'), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Button(jog_frame, text="🏠 Establecer Origen (0,0,1)", command=self.set_origin, 
                   width=25).grid(row=3, column=0, columnspan=3, pady=15, sticky=(tk.W, tk.E))
        
        # Servo
        servo_frame = ttk.LabelFrame(left_frame, text="Control Servo (Z)", padding="10")
        servo_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        tk.Button(servo_frame, text="Z- Arriba\n(50°)", command=lambda: self.jog_step('z', '-'), 
                  width=10, height=2, font=("Arial", 10, "bold"), bg="#4CAF50", fg="white").grid(row=0, column=0, padx=5, pady=5)
        tk.Button(servo_frame, text="Z+ Abajo\n(30°)", command=lambda: self.jog_step('z', '+'), 
                  width=10, height=2, font=("Arial", 10, "bold"), bg="#FF5722", fg="white").grid(row=0, column=1, padx=5, pady=5)
        
        # Calibración
        calib_frame = ttk.LabelFrame(left_frame, text="Calibración de Límites", padding="8")
        calib_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(calib_frame, text="Mueve a límite y presiona:", font=("Arial", 9, "bold")).grid(row=0, column=0, columnspan=2, pady=5)
        
        tk.Button(calib_frame, text="📍 Límite X-MIN", command=lambda: self.record_limit('x', '-'), 
                  width=14, font=("Arial", 9)).grid(row=1, column=0, padx=2, pady=3)
        tk.Button(calib_frame, text="📍 Límite X-MAX", command=lambda: self.record_limit('x', '+'), 
                  width=14, font=("Arial", 9)).grid(row=1, column=1, padx=2, pady=3)
        
        tk.Button(calib_frame, text="📍 Límite Y-MIN", command=lambda: self.record_limit('y', '-'), 
                  width=14, font=("Arial", 9)).grid(row=2, column=0, padx=2, pady=3)
        tk.Button(calib_frame, text="📍 Límite Y-MAX", command=lambda: self.record_limit('y', '+'), 
                  width=14, font=("Arial", 9)).grid(row=2, column=1, padx=2, pady=3)
        
        tk.Button(calib_frame, text="🔄 Resetear Límites", command=self.reset_limits, 
                  width=30, font=("Arial", 9, "bold"), bg="#FFC107").grid(row=3, column=0, columnspan=2, padx=2, pady=5, sticky=(tk.W, tk.E))
        
        # Información de límites
        self.limits_frame = ttk.LabelFrame(left_frame, text="Límites Actuales (mm)", padding="8")
        self.limits_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.limits_info = tk.Text(self.limits_frame, width=30, height=8, font=("Courier", 9), bg="#f0f0f0")
        self.limits_info.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        self.limits_info.config(state=tk.DISABLED)
        
        # G-code
        gcode_label = ttk.Label(left_frame, text="Lista G-code", font=("Arial", 10, "bold"))
        gcode_label.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.gcode_area = scrolledtext.ScrolledText(left_frame, width=30, height=10, font=("Courier", 8))
        self.gcode_area.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.load_btn = ttk.Button(left_frame, text="📂 Cargar G-code", command=self.open_file, width=30)
        self.load_btn.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # PANEL CENTRAL: VISUALIZACIÓN
        center_frame = ttk.Frame(paned)
        paned.add(center_frame, weight=2)
        
        viz_label = ttk.Label(center_frame, text="Visualización de Trayectoria", font=("Arial", 10, "bold"))
        viz_label.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC - Motores Paso a Paso', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, EFFECTIVE_STROKE_MM + 5)
        self.ax.set_ylim(-5, EFFECTIVE_STROKE_MM + 5)
        
        rect = patches.Rectangle((0, 0), EFFECTIVE_STROKE_MM, EFFECTIVE_STROKE_MM, linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(rect)
        self.ax.text(EFFECTIVE_STROKE_MM/2, -3, f'Límites: {EFFECTIVE_STROKE_MM:.1f}×{EFFECTIVE_STROKE_MM:.1f}mm', ha='center', fontsize=9, color='red')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=center_frame)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # PANEL DERECHO: INFORMACIÓN
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        stream_frame = ttk.LabelFrame(right_frame, text="Ejecución", padding="5")
        stream_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.start_btn = tk.Button(stream_frame, text="▶️ INICIAR", command=self.start_stream, 
                                    state=tk.DISABLED, width=15, height=2, bg="#4CAF50", fg="white", 
                                    font=("Arial", 10, "bold"))
        self.start_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.pause_btn = tk.Button(stream_frame, text="⏸️ PAUSAR", command=self.pause_stream, 
                                    state=tk.DISABLED, width=15, height=2, bg="#FFC107", 
                                    font=("Arial", 10, "bold"))
        self.pause_btn.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.stop_btn = tk.Button(stream_frame, text="⏹️ DETENER", command=self.stop_stream, 
                                   state=tk.DISABLED, width=15, height=2, bg="#F44336", fg="white", 
                                   font=("Arial", 10, "bold"))
        self.stop_btn.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3)
        
        pos_frame = ttk.LabelFrame(right_frame, text="Posición Actual (mm)", padding="5")
        pos_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(pos_frame, text="X:", font=("Arial", 10)).grid(row=0, column=0, sticky=tk.W)
        self.x_label = ttk.Label(pos_frame, text="0.000 mm", font=("Arial", 11, "bold"), foreground="blue")
        self.x_label.grid(row=0, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(pos_frame, text="Y:", font=("Arial", 10)).grid(row=1, column=0, sticky=tk.W)
        self.y_label = ttk.Label(pos_frame, text="0.000 mm", font=("Arial", 11, "bold"), foreground="blue")
        self.y_label.grid(row=1, column=1, sticky=tk.W, padx=10)
        
        ttk.Label(pos_frame, text="Z:", font=("Arial", 10)).grid(row=2, column=0, sticky=tk.W)
        self.z_label = ttk.Label(pos_frame, text="1.00", font=("Arial", 11, "bold"), foreground="blue")
        self.z_label.grid(row=2, column=1, sticky=tk.W, padx=10)
        
        progress_frame = ttk.LabelFrame(right_frame, text="Progreso", padding="5")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=200)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="0 / 0 líneas (0%)", font=("Arial", 9, "bold"))
        self.progress_label.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # === FILA 2: LOG ===
        log_frame = ttk.LabelFrame(main_frame, text="Log de Comandos", padding="5")
        log_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, width=200, height=8, font=("Courier", 8))
        self.log_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar pesos
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        left_frame.rowconfigure(5, weight=1)
        center_frame.rowconfigure(1, weight=1)
    
    def jog_step(self, axis, direction):
        self.controller.jog_step(axis, direction, self.controller.current_speed)
    
    def record_limit(self, axis, direction):
        self.controller.record_limit(axis, direction)
    
    def reset_limits(self):
        self.controller.reset_limits()
    
    def update_limits_info(self):
        """Actualiza información de límites"""
        self.limits_info.config(state=tk.NORMAL)
        self.limits_info.delete(1.0, tk.END)
        
        limits = self.controller.calibrated_limits
        pos = self.controller.position
        
        info = f"""X: {limits['x']['min']:.2f}→{limits['x']['max']:.2f}mm
  Pos: {pos['x']:.3f}mm

Y: {limits['y']['min']:.2f}→{limits['y']['max']:.2f}mm
  Pos: {pos['y']:.3f}mm

Z: {limits['z']['min']:.1f}→{limits['z']['max']:.1f}
  Pos: {pos['z']:.2f}

Rango X: {limits['x']['max']-limits['x']['min']:.2f}mm
Rango Y: {limits['y']['max']-limits['y']['min']:.2f}mm

Res: {DISTANCE_PER_MICROSTEP_MM:.4f}mm/paso
"""
        
        self.limits_info.insert(1.0, info)
        self.limits_info.config(state=tk.DISABLED)
    
    def set_speed(self, speed_type):
        self.controller.set_speed(speed_type)
        speed_val = self.controller.SPEEDS[speed_type]
        self.speed_label.configure(text=f"Velocidad: {speed_type.upper()} ({speed_val:.1f}mm/s)")
    
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
                self.update_limits_info()
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="Conectar")
            self.start_btn.configure(state=tk.DISABLED)
    
    def open_file(self):
        fn = filedialog.askopenfilename(
            title="Seleccionar archivo G-code",
            filetypes=[("G-code", "*.gcode *.nc *.g"), ("Todos", "*.*")]
        )
        if fn:
            self.log(f"📂 Cargando: {fn}")
            if self.controller.load_gcode(fn):
                self.gcode_area.delete(1.0, tk.END)
                for i, line in enumerate(self.controller.gcode[:40], 1):
                    self.gcode_area.insert(tk.END, f"{i:3d}: {line}\n")
                
                if self.parser.parse(fn):
                    self.plot_gcode()
                    self.log(f"✅ Visualización: {len(self.parser.x_points)} puntos")
                
                self.start_btn.configure(state=tk.NORMAL)
    
    def plot_gcode(self):
        self.ax.clear()
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC - Motores Paso a Paso', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, EFFECTIVE_STROKE_MM + 5)
        self.ax.set_ylim(-5, EFFECTIVE_STROKE_MM + 5)
        
        rect = patches.Rectangle((0, 0), EFFECTIVE_STROKE_MM, EFFECTIVE_STROKE_MM, linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(rect)
        self.ax.text(EFFECTIVE_STROKE_MM/2, -3, f'Límites: {EFFECTIVE_STROKE_MM:.1f}×{EFFECTIVE_STROKE_MM:.1f}mm', ha='center', fontsize=9, color='red')
        
        if self.parser.x_points and self.parser.y_points:
            self.ax.plot(self.parser.x_points, self.parser.y_points, 'b-', linewidth=2.5, label='Trayectoria')
            self.ax.plot(self.parser.x_points[0], self.parser.y_points[0], 'go', markersize=12, label='Inicio')
            if len(self.parser.x_points) > 1:
                self.ax.plot(self.parser.x_points[-1], self.parser.y_points[-1], 'rs', markersize=12, label='Final')
            self.ax.legend(loc='upper right', fontsize=10)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def set_origin(self):
        self.controller.set_origin()
    
    def start_stream(self):
        self.controller.start_streaming()
        self.start_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
    
    def pause_stream(self):
        self.controller.pause_streaming()
        state_text = "Reanudado" if not self.controller.paused else "Pausado"
        self.log(f"⏸️  Streaming {state_text}")
    
    def stop_stream(self):
        self.controller.stop_streaming()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
    
    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
    
    def update_position(self):
        self.x_label.configure(text=f"{self.controller.position['x']:.3f} mm")
        self.y_label.configure(text=f"{self.controller.position['y']:.3f} mm")
        self.z_label.configure(text=f"{self.controller.position['z']:.2f}")
        self.root.after(200, self.update_position)
    
    def update_progress(self):
        if self.controller.gcode:
            total = len(self.controller.gcode)
            current = self.controller.gcode_index
            percent = int((current / total) * 100) if total > 0 else 0
            
            self.progress_var.set(percent)
            self.progress_label.configure(text=f"{current} / {total} líneas ({percent}%)")
        
        self.root.after(100, self.update_progress)
    
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
