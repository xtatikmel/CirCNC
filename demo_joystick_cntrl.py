"""
CirCNC - DEMO INTERACTIVO - JOYSTICK
=======================================
Versión: Transformación y Control.
✅ Control en tiempo real con joystick/teclado
✅ 2 Motores paso a paso (Eje X e Y)
✅ 1 Servo motor SG90 (Eje Z)
✅ Driver L293D (Puente H)
✅ Visualización de posición
✅ Velocidad variable
✅ Calibración en vivo
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import time
from datetime import datetime
import math

# ===== CONSTANTES DEL MOTOR =====
STEP_ANGLE = 18
PHASES = 2
MICROSTEPS = 4
STEPS_PER_REV = 360 / STEP_ANGLE
MICROSTEPS_PER_REV = STEPS_PER_REV * MICROSTEPS
SCREW_PITCH = 0.020  # pulgadas
SCREW_PITCH_MM = SCREW_PITCH * 25.4  # 0.508 mm
DISTANCE_PER_MICROSTEP = (SCREW_PITCH / MICROSTEPS) * 25.4  # 0.127 mm
EFFECTIVE_STROKE_MM = 80.0  # 80.00 mm

# ===== PARÁMETROS L293D =====
# Motor X: IN1=2, IN2=3, EN=4
# Motor Y: IN3=5, IN4=6, EN=7
# Servo: Pin 9 (PWM)


class MotorController:
    """Controlador de motores con Arduino"""
    
    def __init__(self):
        self.port = None
        self.connected = False
        self.running = True
        
        # Posición actual
        self.position = {'x': 0.0, 'y': 0.0, 'z': 50}
        self.mpos = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self.offset = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        
        # Velocidades (mm por evento de joystick)
        self.speed_modes = {
            'muy_lento': 0.1,    
            'lento': 0.5,
            'normal': 1.0,
            'rapido': 2.0,
            'muy_rapido': 5.0
        }
        self.current_speed = 'normal'
        self.step_delay = self.speed_modes[self.current_speed]
        
        # Estado de movimiento
        self.moving_x = False
        self.moving_y = False
        self.x_direction = 0   
        self.y_direction = 0
        self.z_direction = 0   
        
        # Límites visuales sueltos
        self.limits = {
            'x_min': -100,
            'x_max': 200,
            'y_min': -100,
            'y_max': 200,
            'z_min': 0,
            'z_max': 180
        }
        
        self.log_callback = None
        self.position_callback = None
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def set_position_callback(self, callback):
        self.position_callback = callback
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        msg = f"[{timestamp}] {message}"
        if self.log_callback:
            self.log_callback(msg)
        print(msg)
    
    def find_serial_ports(self):
        """Encuentra puertos seriales disponibles"""
        try:
            from serial.tools import list_ports
            ports = []
            for p in list_ports.comports():
                ports.append(p.device)
            return ports
        except:
            return []
    
    def connect(self, port_name, baudrate=9600):
        """Conecta con Arduino"""
        try:
            if self.port and self.port.is_open:
                self.port.close()
            
            self.port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5
            )
            
            time.sleep(0.5)
            self.port.reset_input_buffer()
            self.port.reset_output_buffer()
            
            # Enviar comando de prueba (estado de GRBL)
            self.send_command("?")
            time.sleep(0.2)
            
            self.connected = True
            self.log(f"✅ Conectado a {port_name}")
            
            # Iniciar thread de lectura
            read_thread = threading.Thread(target=self._read_responses, daemon=True)
            read_thread.start()
            
            return True
        except Exception as e:
            self.log(f"❌ Error de conexión: {e}")
            self.connected = False
            return False
    
    def _read_responses(self):
        """Lee respuestas del Arduino y calcula WPos"""
        while self.running and self.connected and self.port:
            try:
                if self.port.in_waiting > 0:
                    response = self.port.readline().decode().strip()
                    if response:
                        if response.startswith("<"):
                            try:
                                if "WPos:" in response:
                                    pos_str = response.split("WPos:")[1].split("|")[0].split(">")[0]
                                    x, y, z = map(float, pos_str.split(","))
                                    self.position = {'x': x, 'y': y, 'z': self.position['z']}
                                elif "MPos:" in response:
                                    pos_str = response.split("MPos:")[1].split("|")[0].split(">")[0]
                                    x, y, z = map(float, pos_str.split(","))
                                    self.mpos = {'x': x, 'y': y, 'z': z}
                                    if "WCO:" in response:
                                        wco_str = response.split("WCO:")[1].split("|")[0].split(">")[0]
                                        ox, oy, oz = map(float, wco_str.split(","))
                                        self.position = {'x': x - ox, 'y': y - oy, 'z': self.position['z']}
                                    else:
                                        self.position = {
                                            'x': x - self.offset.get('x', 0.0),
                                            'y': y - self.offset.get('y', 0.0),
                                            'z': self.position['z']
                                        }
                                self._update_position()
                            except:
                                pass
                        else:
                            if response != "ok":
                                self.log(f"← {response}")
                time.sleep(0.01)
            except:
                pass
    
    def send_command(self, command):
        """Envía comando a Arduino"""
        if not self.port or not self.port.is_open:
            return False
        
        try:
            if not command.endswith('\n'):
                command += '\n'
            
            self.port.write(command.encode())
            if command.strip() != "?":
                self.log(f"→ {command.strip()}")
            return True
        except Exception as e:
            self.log(f"❌ Error: {e}")
            return False
    
    def move_x(self, steps, direction):
        if not self.connected: return False
        
        dist = abs(steps) * self.step_delay
        sign = "" if direction > 0 else "-"
        
        self.send_command("G91")
        self.send_command(f"G1 X{sign}{dist:.2f} F1500")
        self.send_command("G90")
        self.send_command("?")
        return True
    
    def move_y(self, steps, direction):
        if not self.connected: return False
        
        dist = abs(steps) * self.step_delay
        sign = "" if direction > 0 else "-"
        
        self.send_command("G91")
        self.send_command(f"G1 Y{sign}{dist:.2f} F1500")
        self.send_command("G90")
        self.send_command("?")
        return True
    
    def move_z(self, angle_change):
        if not self.connected: return False
        
        new_z = self.position['z'] + (angle_change * 5)  # 5 grados por tick
        new_z = max(0, min(180, new_z))
        
        self.position['z'] = new_z
        self.send_command(f"M300 S{int(new_z)}")
        self._update_position()
        return True
    
    def set_speed(self, speed_mode):
        if speed_mode in self.speed_modes:
            self.current_speed = speed_mode
            self.step_delay = self.speed_modes[speed_mode]
            self.log(f"⚙️ Velocidad (Resolución): {speed_mode.upper()} ({self.step_delay} mm/movimiento)")
            return True
        return False
    
    def return_to_origin(self):
        """Establece origen como en gctrl"""
        if not self.connected: return False
        self.log("📍 Estableciendo Origen en Posición Actual (G92)...")
        
        self.send_command("G92 X0 Y0 Z0")
        time.sleep(0.3)
        self.offset = self.mpos.copy()
        
        self.send_command("?")
        self.log("✅ Origen Cero establecido y coordenadas limpias")
        return True
    
    def calibrate_x_min(self):
        """Calibra límite mínimo X en posición actual"""
        self.limits['x_min'] = self.position['x']
        self.log(f"📍 Límite X-MIN calibrado: {self.position['x']:.2f}mm")
    
    def calibrate_x_max(self):
        """Calibra límite máximo X en posición actual"""
        self.limits['x_max'] = self.position['x']
        self.log(f"📍 Límite X-MAX calibrado: {self.position['x']:.2f}mm")
    
    def calibrate_y_min(self):
        """Calibra límite mínimo Y en posición actual"""
        self.limits['y_min'] = self.position['y']
        self.log(f"📍 Límite Y-MIN calibrado: {self.position['y']:.2f}mm")
    
    def calibrate_y_max(self):
        """Calibra límite máximo Y en posición actual"""
        self.limits['y_max'] = self.position['y']
        self.log(f"📍 Límite Y-MAX calibrado: {self.position['y']:.2f}mm")
    
    def reset_limits(self):
        """Reinicia límites a valores por defecto"""
        self.limits = {
            'x_min': 0,
            'x_max': EFFECTIVE_STROKE_MM,
            'y_min': 0,
            'y_max': EFFECTIVE_STROKE_MM,
            'z_min': 0,
            'z_max': 180
        }
        self.log("🔄 Límites reiniciados")
    
    def _update_position(self):
        """Callback para actualizar posición en GUI"""
        if self.position_callback:
            self.position_callback(self.position)
    
    def disconnect(self):
        """Desconecta del Arduino"""
        self.running = False
        if self.port and self.port.is_open:
            self.port.close()
        self.connected = False
        self.log("Desconectado")


class JoystickGUI:
    """Interfaz gráfica con control de joystick"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 CirCNC - Control con Joystick Virtual")
        self.root.geometry("1200x900")
        self.root.configure(bg="#1e1e1e")
        
        self.controller = MotorController()
        self.controller.set_log_callback(self.log)
        self.controller.set_position_callback(self.update_position)
        
        # Controlar movimiento continuo
        self.moving = {'x': 0, 'y': 0, 'z': 0}  # -1, 0, 1
        
        self.create_widgets()
        self.update_ports()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        self.continuous_move()
        
        # Mensaje de bienvenida con Arte ASCII
        self.log("  _____ _                _   _  _____ ")
        self.log(" / ____(_)              | \ | |/ ____|")
        self.log("| |     _ _ __ ___ ___  |  \| | |     ")
        self.log("| |    | | '__/ __/ _ \ | . ` | |     ")
        self.log("| |____| | | | (_|  __/ | |\  | |____ ")
        self.log(" \\_____|_|_|  \\___\\___| |_| \\_|\\_____|")
        self.log("-" * 40)
        self.log("🪄 CirCNC: El poder de la transformación.")
    
    def create_widgets(self):
        """Crea la interfaz gráfica"""
        
        # === FILA 0: CONEXIÓN ===
        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header, text="🔌 Puerto Serial:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.port_var = tk.StringVar()
        port_combo = ttk.Combobox(header, textvariable=self.port_var, width=15, state="readonly")
        port_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(header, text="🔄 Refrescar", command=self.update_ports).pack(side=tk.LEFT, padx=2)
        
        self.connect_btn = ttk.Button(header, text="🔗 Conectar", command=self.toggle_connection)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(header, text="❌ Desconectado", font=("Arial", 10, "bold"), foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # === FILA 1: CONTENIDO PRINCIPAL ===
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === PANEL IZQUIERDO: JOYSTICK ===
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        joystick_frame = ttk.LabelFrame(left_frame, text="🎮 Control Joystick", padding="20")
        joystick_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Canvas para dibujar joystick
        self.joystick_canvas = tk.Canvas(joystick_frame, width=300, height=300, bg="black", highlightthickness=2, highlightbackground="cyan")
        self.joystick_canvas.pack()
        
        self.draw_joystick()
        
        # Instrucciones
        instr_frame = ttk.LabelFrame(left_frame, text="⌨️ Controles", padding="10")
        instr_frame.pack(fill=tk.X, pady=5)
        
        instructions = """
MOVIMIENTO:
  W/↑ = Y+    S/↓ = Y-
  A/← = X-    D/→ = X+
  Q = Z-      E = Z+

VELOCIDAD:
  1=Muy Lento, 2=Lento
  3=Normal, 4=Rápido, 5=Muy Rápido

CONTROL:
  H = Home (0,0,90°)
  C = Calibrar límites
  R = Reset límites
  ESPACIO = Parar
        """
        
        instr_text = tk.Text(instr_frame, height=16, width=35, font=("Courier", 9), bg="#2a2a2a", fg="#00ff00")
        instr_text.pack(fill=tk.BOTH, expand=True)
        instr_text.insert(1.0, instructions)
        instr_text.config(state=tk.DISABLED)
        
        # === PANEL CENTRAL: INFORMACIÓN ===
        center_frame = ttk.Frame(main_paned)
        main_paned.add(center_frame, weight=2)
        
        # Monitor de posición
        pos_frame = ttk.LabelFrame(center_frame, text="📍 Posición Actual", padding="15")
        pos_frame.pack(fill=tk.X, pady=5)
        
        # X Position
        x_inner = ttk.Frame(pos_frame)
        x_inner.pack(fill=tk.X, pady=5)
        ttk.Label(x_inner, text="X:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.x_label = ttk.Label(x_inner, text="0.000 mm", font=("Arial", 16, "bold"), foreground="cyan")
        self.x_label.pack(side=tk.LEFT, padx=10)
        
        # Y Position
        y_inner = ttk.Frame(pos_frame)
        y_inner.pack(fill=tk.X, pady=5)
        ttk.Label(y_inner, text="Y:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.y_label = ttk.Label(y_inner, text="0.000 mm", font=("Arial", 16, "bold"), foreground="lime")
        self.y_label.pack(side=tk.LEFT, padx=10)
        
        # Z Position
        z_inner = ttk.Frame(pos_frame)
        z_inner.pack(fill=tk.X, pady=5)
        ttk.Label(z_inner, text="Z:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.z_label = ttk.Label(z_inner, text="90°", font=("Arial", 16, "bold"), foreground="yellow")
        self.z_label.pack(side=tk.LEFT, padx=10)
        ttk.Label(z_inner, text="(Servo PWM)", font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        
        # Límites
        limits_frame = ttk.LabelFrame(center_frame, text="📏 Límites Calibrados (mm)", padding="10")
        limits_frame.pack(fill=tk.X, pady=5)
        
        limits_inner = ttk.Frame(limits_frame)
        limits_inner.pack(fill=tk.X)
        
        ttk.Label(limits_inner, text="X:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        self.x_limit_label = ttk.Label(limits_inner, text="0.00 → 80.00", font=("Arial", 10), foreground="cyan")
        self.x_limit_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(limits_inner, text="Y:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=20)
        self.y_limit_label = ttk.Label(limits_inner, text="0.00 → 80.00", font=("Arial", 10), foreground="lime")
        self.y_limit_label.pack(side=tk.LEFT, padx=5)
        
        # Velocidad
        speed_frame = ttk.LabelFrame(center_frame, text="⚡ Velocidad", padding="10")
        speed_frame.pack(fill=tk.X, pady=5)
        
        speed_inner = ttk.Frame(speed_frame)
        speed_inner.pack(fill=tk.X)
        
        self.speed_label = ttk.Label(speed_inner, text="NORMAL (3=15ms)", font=("Arial", 12, "bold"), foreground="magenta")
        self.speed_label.pack(side=tk.LEFT, padx=10)
        
        # Botones de calibración
        calib_frame = ttk.LabelFrame(center_frame, text="🔧 Calibración", padding="10")
        calib_frame.pack(fill=tk.X, pady=5)
        
        calib_buttons = ttk.Frame(calib_frame)
        calib_buttons.pack(fill=tk.X)
        
        ttk.Button(calib_buttons, text="X-MIN", command=self.calibrate_x_min, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(calib_buttons, text="X-MAX", command=self.calibrate_x_max, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(calib_buttons, text="Y-MIN", command=self.calibrate_y_min, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(calib_buttons, text="Y-MAX", command=self.calibrate_y_max, width=10).pack(side=tk.LEFT, padx=2)
        
        calib_buttons2 = ttk.Frame(calib_frame)
        calib_buttons2.pack(fill=tk.X, pady=5)
        
        ttk.Button(calib_buttons2, text="🏠 Home", command=self.return_to_origin, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Button(calib_buttons2, text="🔄 Reset Límites", command=self.reset_limits, width=15).pack(side=tk.LEFT, padx=2)
        
        # === PANEL DERECHO: LOG ===
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        log_frame = ttk.LabelFrame(right_frame, text="📋 Log de Comandos", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_area = tk.Text(log_frame, width=35, height=40, font=("Courier", 8), bg="#2a2a2a", fg="#00ff00")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_area.config(yscrollcommand=scrollbar.set)
        
        self.log("🚀 Sistema listo. Conecta Arduino para comenzar...")
        self.log("⌨️  Presiona las teclas mostradas para controlar")
    
    def draw_joystick(self):
        """Dibuja representación visual del joystick"""
        self.joystick_canvas.delete("all")
        
        # Background
        self.joystick_canvas.create_rectangle(0, 0, 300, 300, fill="black", outline="cyan", width=2)
        
        # Grid
        for i in range(1, 3):
            x = 150 * i
            y = 150 * i
            self.joystick_canvas.create_line(x, 0, x, 300, fill="gray", dash=(4, 4))
            self.joystick_canvas.create_line(0, y, 300, y, fill="gray", dash=(4, 4))
        
        # Centro
        self.joystick_canvas.create_oval(140, 140, 160, 160, fill="red", outline="yellow", width=2)
        
        # Etiquetas
        self.joystick_canvas.create_text(150, 20, text="Y+", fill="lime", font=("Arial", 12, "bold"))
        self.joystick_canvas.create_text(150, 280, text="Y-", fill="lime", font=("Arial", 12, "bold"))
        self.joystick_canvas.create_text(20, 150, text="X-", fill="cyan", font=("Arial", 12, "bold"))
        self.joystick_canvas.create_text(280, 150, text="X+", fill="cyan", font=("Arial", 12, "bold"))
        
        # Z Control
        self.joystick_canvas.create_text(80, 280, text="Z- (Q)", fill="yellow", font=("Arial", 9))
        self.joystick_canvas.create_text(220, 280, text="Z+ (E)", fill="yellow", font=("Arial", 9))
        
        # Indicador de movimiento
        x_move = 150 + (self.moving['x'] * 50)
        y_move = 150 - (self.moving['y'] * 50)
        
        self.joystick_canvas.create_oval(x_move - 15, y_move - 15, x_move + 15, y_move + 15, 
                                         fill="cyan", outline="white", width=2)
        
        # Info
        self.joystick_canvas.create_text(150, 5, text="JOYSTICK VIRTUAL", fill="white", font=("Arial", 10, "bold"))
    
    def on_key_press(self, event):
        """Maneja presión de teclas"""
        key = event.keysym.lower()
        
        # Movimiento
        if key in ['w', 'up']:
            self.moving['y'] = 1
        elif key in ['s', 'down']:
            self.moving['y'] = -1
        elif key in ['a', 'left']:
            self.moving['x'] = -1
        elif key in ['d', 'right']:
            self.moving['x'] = 1
        elif key == 'q':
            self.moving['z'] = -1
        elif key == 'e':
            self.moving['z'] = 1
        
        # Velocidad
        elif key == '1':
            self.controller.set_speed('muy_lento')
            self.update_speed_label()
        elif key == '2':
            self.controller.set_speed('lento')
            self.update_speed_label()
        elif key == '3':
            self.controller.set_speed('normal')
            self.update_speed_label()
        elif key == '4':
            self.controller.set_speed('rapido')
            self.update_speed_label()
        elif key == '5':
            self.controller.set_speed('muy_rapido')
            self.update_speed_label()
        
        # Especiales
        elif key == 'space':
            self.moving = {'x': 0, 'y': 0, 'z': 0}
        elif key == 'h':
            self.return_to_origin()
        elif key == 'c':
            self.calibrate_menu()
        elif key == 'r':
            self.reset_limits()
        
        self.draw_joystick()
    
    def on_key_release(self, event):
        """Maneja liberación de teclas"""
        key = event.keysym.lower()
        
        if key in ['w', 'up', 's', 'down']:
            self.moving['y'] = 0
        elif key in ['a', 'left', 'd', 'right']:
            self.moving['x'] = 0
        elif key in ['q', 'e']:
            self.moving['z'] = 0
        
        self.draw_joystick()
    
    def continuous_move(self):
        """Ejecuta movimiento continuo basado en input"""
        if self.controller.connected:
            if self.moving['x'] != 0:
                self.controller.move_x(1, self.moving['x'])
            if self.moving['y'] != 0:
                self.controller.move_y(1, self.moving['y'])
            if self.moving['z'] != 0:
                self.controller.move_z(self.moving['z'])
        # Mantenemos a 200 milisegundos para no ahogar el puerto serial con comandos G-Code
        self.root.after(200, self.continuous_move)
    
    def update_position(self, pos):
        """Actualiza display de posición"""
        self.x_label.configure(text=f"{pos['x']:.3f} mm")
        self.y_label.configure(text=f"{pos['y']:.3f} mm")
        self.z_label.configure(text=f"{pos['z']:.0f}°")
        
        # Actualizar límites
        limits = self.controller.limits
        self.x_limit_label.configure(text=f"{limits['x_min']:.2f} → {limits['x_max']:.2f}")
        self.y_limit_label.configure(text=f"{limits['y_min']:.2f} → {limits['y_max']:.2f}")
    
    def update_speed_label(self):
        speed = self.controller.current_speed
        dist = self.controller.step_delay
        self.speed_label.configure(text=f"{speed.upper()} ({dist:.1f} mm/pulso)")
    
    def log(self, message):
        """Agrega mensaje al log"""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
    
    def update_ports(self):
        """Actualiza lista de puertos disponibles"""
        ports = self.controller.find_serial_ports()
        self.port_combo_widget = self.root.winfo_children()[0].winfo_children()[2]
        # Buscar el combobox
        for child in self.root.winfo_children()[0].winfo_children():
            if isinstance(child, ttk.Combobox):
                child['values'] = ports
                if ports:
                    child.set(ports[0])
                break
    
    def toggle_connection(self):
        """Conecta/Desconecta del Arduino"""
        if not self.controller.connected:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Selecciona un puerto")
                return
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="🔌 Desconectar")
                self.status_label.configure(text="✅ Conectado", foreground="green")
                self.log("✅ Listo para usar. Presiona teclas para controlar.")
            else:
                self.status_label.configure(text="❌ Error de conexión", foreground="red")
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="🔗 Conectar")
            self.status_label.configure(text="❌ Desconectado", foreground="red")
    
    def calibrate_x_min(self):
        if self.controller.connected:
            self.controller.calibrate_x_min()
    
    def calibrate_x_max(self):
        if self.controller.connected:
            self.controller.calibrate_x_max()
    
    def calibrate_y_min(self):
        if self.controller.connected:
            self.controller.calibrate_y_min()
    
    def calibrate_y_max(self):
        if self.controller.connected:
            self.controller.calibrate_y_max()
    
    def calibrate_menu(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibración")
        dialog.geometry("300x200")
        
        ttk.Label(dialog, text="¿Qué deseas calibrar?", font=("Arial", 12, "bold")).pack(pady=20)
        
        ttk.Button(dialog, text="X-MIN", command=lambda: [self.calibrate_x_min(), dialog.destroy()]).pack(pady=5, fill=tk.X, padx=20)
        ttk.Button(dialog, text="X-MAX", command=lambda: [self.calibrate_x_max(), dialog.destroy()]).pack(pady=5, fill=tk.X, padx=20)
        ttk.Button(dialog, text="Y-MIN", command=lambda: [self.calibrate_y_min(), dialog.destroy()]).pack(pady=5, fill=tk.X, padx=20)
        ttk.Button(dialog, text="Y-MAX", command=lambda: [self.calibrate_y_max(), dialog.destroy()]).pack(pady=5, fill=tk.X, padx=20)
    
    def return_to_origin(self):
        if self.controller.connected:
            self.controller.return_to_origin()
    
    def reset_limits(self):
        if self.controller.connected:
            self.controller.reset_limits()
    
    def on_closing(self):
        if messagebox.askokcancel("Salir", "¿Cerrar aplicación?"):
            self.controller.disconnect()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = JoystickGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
