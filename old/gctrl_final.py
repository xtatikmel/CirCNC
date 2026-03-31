"""
CNC PLOTTER CONTROLLER - VERSIÓN AVANZADA CON VISUALIZACIÓN (FINAL)
====================================================================
✅ Botón CARGAR G-CODE visible
✅ SIN ERRORES DE TKINTER
✅ Control manual con 3 velocidades
✅ Visualización en tiempo real
✅ Indicador de progreso
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
        
        self.machine_limits = {
            'x': {'min': 0, 'max': 50},
            'y': {'min': 0, 'max': 50},
            'z': {'min': 0, 'max': 1}
        }
        
        self.SPEEDS = {
            'lento': 0.5,
            'normal': 1.0,
            'rapido': 2.0
        }
        self.current_speed = 'normal'
        
        self.STEPS_PER_MM = 35.56
        self.log_callback = None
        self.serial_lock = threading.Lock()
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
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
                        self.log(f"← {response}")
                        
                        if response.startswith("<"):
                            try:
                                pos_str = response.split("MPos:")[1].split("|")[0]
                                x, y, z = map(float, pos_str.split(","))
                                self.position = {'x': x, 'y': y, 'z': z}
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
    
    def jog(self, direction, speed_type='normal'):
        if not self.port or not self.port.is_open:
            return False
        
        def _jog_thread():
            axis = direction[0].upper()
            sign = "+" if direction[1] == "+" else "-"
            
            speed_mm = self.SPEEDS.get(speed_type, 1.0)
            
            new_position = self.position.copy()
            move_distance = speed_mm if sign == "+" else -speed_mm
            new_position[axis.lower()] += move_distance
            
            if not self.check_limits(**new_position):
                self.log(f"❌ Fuera de límites: {axis}={new_position[axis.lower()]:.2f}")
                return
            
            if sign == "+":
                command = f"G91\nG1 {axis}+{speed_mm} F1000"
            else:
                command = f"G91\nG1 {axis}{speed_mm} F1000"
            
            self.log(f"📍 {speed_type.upper()}: {axis} {speed_mm}mm ({direction})")
            
            if self.send_command(command):
                time.sleep(0.8)
                self.send_command("G90")
                time.sleep(0.2)
                self.send_command("?")
        
        threading.Thread(target=_jog_thread, daemon=True).start()
        return True
    
    def set_speed(self, speed_type):
        if speed_type in self.SPEEDS:
            self.current_speed = speed_type
            self.log(f"⚙️  Velocidad: {speed_type.upper()} ({self.SPEEDS[speed_type]}mm)")
            return True
        return False
    
    def set_origin(self):
        if not self.port or not self.port.is_open:
            return False
        
        self.log("📌 Estableciendo origen...")
        self.send_command("G90")
        time.sleep(0.2)
        self.send_command("G1 X0 Y0")
        time.sleep(1)
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        time.sleep(0.2)
        self.send_command("?")
        self.log("✅ Origen establecido")
        return True
    
    def load_gcode(self, filename):
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            
            self.gcode = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(';'):
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
        
        self.send_command("M300 S50")
        time.sleep(0.5)
        self.send_command("G90")
        time.sleep(0.2)
        self.send_command("G1 X0 Y0")
        time.sleep(1)
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
        self.root.title("CNC Plotter - Control Avanzado con Visualización")
        self.root.geometry("1500x900")
        
        self.controller = GCodeController()
        self.controller.set_log_callback(self.log)
        self.parser = GCodeParser()
        
        self.create_widgets()
        self.update_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_position()
        self.update_progress()
    
    def create_widgets(self):
        """Crea interfaz gráfica - USANDO tk.Button CON HEIGHT"""
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # === FILA 0: CONEXIÓN ===
        control_frame = ttk.LabelFrame(main_frame, text="Control", padding="5")
        control_frame.grid(row=0, column=0, columnspan=5, sticky=(tk.W, tk.E))
        
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(control_frame, textvariable=self.port_var, width=20)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="Refrescar", command=self.update_ports).grid(row=0, column=2)
        self.connect_btn = ttk.Button(control_frame, text="Conectar", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        # === FILA 0b: VELOCIDADES ===
        speed_frame = ttk.LabelFrame(main_frame, text="Velocidad Manual", padding="5")
        speed_frame.grid(row=0, column=5, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Button(speed_frame, text="🐢 LENTO\n(0.5mm)", 
                   command=lambda: self.set_speed('lento'),
                   width=12).grid(row=0, column=0, padx=2)
        
        ttk.Button(speed_frame, text="🚗 NORMAL\n(1.0mm)",
                   command=lambda: self.set_speed('normal'),
                   width=12).grid(row=0, column=1, padx=2)
        
        ttk.Button(speed_frame, text="🚀 RÁPIDO\n(2.0mm)",
                   command=lambda: self.set_speed('rapido'),
                   width=12).grid(row=0, column=2, padx=2)
        
        self.speed_label = ttk.Label(speed_frame, text="Velocidad: NORMAL")
        self.speed_label.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E))
        
        # === FILA 1: PANEL PRINCIPAL (3 COLUMNAS) ===
        
        # COLUMNA IZQUIERDA: CONTROL MANUAL + G-CODE
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Control manual
        jog_frame = ttk.LabelFrame(left_frame, text="Control Manual", padding="10")
        jog_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # ✅ USAR tk.Button CON HEIGHT (no ttk.Button)
        tk.Button(jog_frame, text="Y+", command=lambda: self.jog_with_speed('y+'), width=8, height=2).grid(row=0, column=1, padx=2, pady=2)
        tk.Button(jog_frame, text="X-", command=lambda: self.jog_with_speed('x-'), width=8, height=2).grid(row=1, column=0, padx=2, pady=2)
        tk.Button(jog_frame, text="X+", command=lambda: self.jog_with_speed('x+'), width=8, height=2).grid(row=1, column=2, padx=2, pady=2)
        tk.Button(jog_frame, text="Y-", command=lambda: self.jog_with_speed('y-'), width=8, height=2).grid(row=2, column=1, padx=2, pady=2)
        
        tk.Button(jog_frame, text="Z+", command=lambda: self.send_cmd("M300 S30"), width=8, height=2).grid(row=3, column=0, padx=2, pady=2)
        tk.Button(jog_frame, text="Z-", command=lambda: self.send_cmd("M300 S50"), width=8, height=2).grid(row=3, column=2, padx=2, pady=2)
        
        ttk.Button(jog_frame, text="Establecer Origen", command=self.set_origin, width=24).grid(row=4, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E))
        
        # G-code list
        gcode_label = ttk.Label(left_frame, text="Lista G-code (primeras 30 líneas)")
        gcode_label.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.gcode_area = scrolledtext.ScrolledText(left_frame, width=30, height=20)
        self.gcode_area.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # ✅ BOTÓN CARGAR (VISIBLE)
        self.load_btn = ttk.Button(left_frame, text="📂 Cargar G-code", command=self.open_file, width=30)
        self.load_btn.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # COLUMNA CENTRAL: VISUALIZACIÓN
        viz_frame = ttk.LabelFrame(main_frame, text="Visualización de Trayectoria", padding="5")
        viz_frame.grid(row=1, column=2, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        self.fig = Figure(figsize=(6, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, 45)
        self.ax.set_ylim(-5, 45)
        
        # Dibujar límites
        rect = patches.Rectangle((0, 0), 40, 40, linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(rect)
        self.ax.text(20, -3, 'Límites: 40×40mm', ha='center', fontsize=9, color='red')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=viz_frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # COLUMNA DERECHA: STREAMING + ESTADO
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=1, column=4, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Streaming
        stream_frame = ttk.LabelFrame(right_frame, text="Streaming", padding="5")
        stream_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.start_btn = ttk.Button(stream_frame, text="▶️  Iniciar", command=self.start_stream, state=tk.DISABLED, width=20)
        self.start_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.pause_btn = ttk.Button(stream_frame, text="⏸️  Pausar", command=self.pause_stream, state=tk.DISABLED, width=20)
        self.pause_btn.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)
        
        self.stop_btn = ttk.Button(stream_frame, text="⏹️  Detener", command=self.stop_stream, state=tk.DISABLED, width=20)
        self.stop_btn.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=3)
        
        # Posición
        pos_frame = ttk.LabelFrame(right_frame, text="Posición Actual", padding="5")
        pos_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(pos_frame, text="X:").grid(row=0, column=0, sticky=tk.W)
        self.x_label = ttk.Label(pos_frame, text="0.00 mm", font=("Arial", 12, "bold"))
        self.x_label.grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(pos_frame, text="Y:").grid(row=1, column=0, sticky=tk.W)
        self.y_label = ttk.Label(pos_frame, text="0.00 mm", font=("Arial", 12, "bold"))
        self.y_label.grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(pos_frame, text="Z:").grid(row=2, column=0, sticky=tk.W)
        self.z_label = ttk.Label(pos_frame, text="1.00", font=("Arial", 12, "bold"))
        self.z_label.grid(row=2, column=1, sticky=tk.W)
        
        # Progreso
        progress_frame = ttk.LabelFrame(right_frame, text="Progreso", padding="5")
        progress_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_var = tk.IntVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=200)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="0 / 0 líneas", font=("Arial", 10))
        self.progress_label.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # === FILA 2: LOG ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=2, column=0, columnspan=7, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, width=200, height=7)
        self.log_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(1, weight=1)
        left_frame.rowconfigure(2, weight=1)
    
    def jog_with_speed(self, direction):
        self.controller.jog(direction, self.controller.current_speed)
    
    def set_speed(self, speed_type):
        self.controller.set_speed(speed_type)
        self.speed_label.configure(text=f"Velocidad: {speed_type.upper()}")
    
    def update_ports(self):
        ports = self.controller.find_serial_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
        self.log(f"Puertos encontrados: {ports if ports else 'Ninguno'}")
    
    def toggle_connection(self):
        if not self.controller.port or not self.controller.port.is_open:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Selecciona un puerto")
                return
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="Desconectar")
                self.start_btn.configure(state=tk.NORMAL)
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="Conectar")
            self.start_btn.configure(state=tk.DISABLED)
    
    def open_file(self):
        """✅ ABRE DIÁLOGO DE ARCHIVO"""
        fn = filedialog.askopenfilename(
            title="Seleccionar archivo G-code",
            filetypes=[("G-code", "*.gcode *.nc *.g"), ("Todos", "*.*")]
        )
        if fn:
            self.log(f"📂 Cargando: {fn}")
            if self.controller.load_gcode(fn):
                self.gcode_area.delete(1.0, tk.END)
                for i, line in enumerate(self.controller.gcode[:30], 1):
                    self.gcode_area.insert(tk.END, f"{i:3d}: {line}\n")
                
                if self.parser.parse(fn):
                    self.plot_gcode()
                    self.log(f"✅ Visualización actualizada: {len(self.parser.x_points)} puntos")
                
                self.start_btn.configure(state=tk.NORMAL)
    
    def plot_gcode(self):
        """Dibuja trayectoria de G-code"""
        self.ax.clear()
        self.ax.set_xlabel('X (mm)', fontsize=10)
        self.ax.set_ylabel('Y (mm)', fontsize=10)
        self.ax.set_title('Trayectoria CNC', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.set_xlim(-5, 45)
        self.ax.set_ylim(-5, 45)
        
        # Dibujar límites
        rect = patches.Rectangle((0, 0), 40, 40, linewidth=2, edgecolor='red', facecolor='none', linestyle='--')
        self.ax.add_patch(rect)
        self.ax.text(20, -3, 'Límites: 40×40mm', ha='center', fontsize=9, color='red')
        
        # Dibujar trayectoria
        if self.parser.x_points and self.parser.y_points:
            self.ax.plot(self.parser.x_points, self.parser.y_points, 'b-', linewidth=2, label='Trayectoria')
            self.ax.plot(self.parser.x_points[0], self.parser.y_points[0], 'go', markersize=10, label='Inicio')
            if len(self.parser.x_points) > 1:
                self.ax.plot(self.parser.x_points[-1], self.parser.y_points[-1], 'rs', markersize=10, label='Final')
            self.ax.legend(loc='upper right', fontsize=9)
        
        self.canvas.draw()
    
    def set_origin(self):
        self.controller.set_origin()
    
    def send_cmd(self, cmd):
        self.controller.send_command(cmd)
    
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
        self.x_label.configure(text=f"{self.controller.position['x']:.2f} mm")
        self.y_label.configure(text=f"{self.controller.position['y']:.2f} mm")
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
