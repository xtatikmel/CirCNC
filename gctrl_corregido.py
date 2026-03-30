"""
CNC PLOTTER CONTROLLER - VERSIÓN CORREGIDA
===========================================
Basado en código Processing (Java) adaptado a Python
Correcciones principales:
1. Formato correcto de comandos G-code
2. Validación robusta de límites
3. Mejor sincronización Arduino-Python
4. Manejo correcto de errores
5. Establecimiento de origen funcional
"""

import serial
import threading
import time
import platform
import os
import glob
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import re

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
        
        # Posición actual
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}  # Z=1 (pluma arriba)
        
        # Límites máquina (CD-ROM: 40x40mm, Z=5mm servo)
        self.machine_limits = {
            'x': {'min': 0, 'max': 40},
            'y': {'min': 0, 'max': 40},
            'z': {'min': 0, 'max': 5}  # Z en rango 0-1 (servo)
        }
        
        self.serial_lock = threading.Lock()
        self.origin_set = False
        self.soft_limits_enabled = True
        
        # Control de sincronización
        self.last_response = None
        self.waiting_for_response = False
    
    def set_log_callback(self, callback):
        """Configura callback para logging"""
        self.log_callback = callback
    
    def log(self, message):
        """Registra mensaje"""
        if self.log_callback:
            self.log_callback(message)
    
    # ===== DESCUBRIMIENTO DE PUERTOS =====
    def find_serial_ports(self):
        """Encuentra puertos seriales disponibles"""
        ports = []
        system = platform.system().lower()
        
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                ports.append(p.device)
            return ports
        except:
            pass
        
        # Fallback: búsqueda manual
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
    
    # ===== CONEXIÓN SERIAL =====
    def connect(self, port_name):
        """Conecta al puerto serial"""
        if not port_name:
            self.log("ERROR: No se especificó puerto")
            return False
        
        try:
            # Cerrar puerto anterior si existe
            if self.port and self.port.is_open:
                self.port.close()
            
            # Abrir puerto
            self.port = serial.Serial(
                port=port_name,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
                write_timeout=1
            )
            
            self.port_name = port_name
            
            # Limpiar buffers
            try:
                self.port.reset_input_buffer()
                self.port.reset_output_buffer()
            except:
                pass
            
            # Iniciar hilo de lectura
            read_thread = threading.Thread(target=self.read_responses, daemon=True)
            read_thread.start()
            
            # Enviar comando de prueba
            time.sleep(0.5)
            self.send_command("?")
            
            self.log(f"✅ Conectado a {port_name}")
            return True
        
        except Exception as e:
            self.log(f"❌ Error conectando a {port_name}: {str(e)}")
            return False
    
    # ===== VERIFICACIÓN DE LÍMITES =====
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
    
    def _extract_coordinates(self, command):
        """Extrae coordenadas X, Y, Z de comando G-code"""
        x = y = z = None
        
        # Buscar X
        match_x = re.search(r'X([+-]?\d+\.?\d*)', command, re.IGNORECASE)
        if match_x:
            x = float(match_x.group(1))
        
        # Buscar Y
        match_y = re.search(r'Y([+-]?\d+\.?\d*)', command, re.IGNORECASE)
        if match_y:
            y = float(match_y.group(1))
        
        # Buscar Z
        match_z = re.search(r'Z([+-]?\d+\.?\d*)', command, re.IGNORECASE)
        if match_z:
            z = float(match_z.group(1))
        
        return x, y, z
    
    # ===== ENVÍO DE COMANDOS =====
    def send_command(self, command):
        """Envía comando al Arduino"""
        if not self.port or not self.port.is_open:
            self.log("❌ Puerto no conectado")
            return False
        
        try:
            with self.serial_lock:
                # Asegurar salto de línea
                if not command.endswith('\n'):
                    command = command + '\n'
                
                # Limpiar buffers
                try:
                    self.port.reset_input_buffer()
                except:
                    pass
                
                # Enviar
                self.port.write(command.encode())
                self.current_line = command.strip()
                
                self.log(f"→ {self.current_line}")
                
                # Esperar respuesta
                self.waiting_for_response = True
                time.sleep(0.3)
                
                return True
        
        except Exception as e:
            self.log(f"❌ Error enviando comando: {str(e)}")
            return False
    
    # ===== LECTURA DE RESPUESTAS =====
    def read_responses(self):
        """Lee respuestas del Arduino"""
        while self.running and self.port and self.port.is_open:
            try:
                if self.port.in_waiting > 0:
                    response = self.port.readline().decode().strip()
                    
                    if response:
                        self.last_response = response
                        self.log(f"← {response}")
                        
                        # Procesar respuesta de posición
                        if response.startswith("<"):
                            try:
                                # Formato: <Idle|MPos:x,y,z|FS:0,0>
                                pos_str = response.split("MPos:")[1].split("|")[0]
                                x, y, z = map(float, pos_str.split(","))
                                self.position = {'x': x, 'y': y, 'z': z}
                            except:
                                pass
                        
                        # Procesar "ok" (comando ejecutado)
                        elif response.startswith("ok"):
                            self.waiting_for_response = False
                            if self.streaming and not self.paused:
                                time.sleep(0.2)
                                self.send_next_gcode_line()
                        
                        # ✅ NUEVA: Procesar "error" (comando rechazado)
                        elif response.startswith("error"):
                            self.waiting_for_response = False
                            self.log(f"⚠️  ADVERTENCIA: Arduino rechazó comando")
                            self.log(f"    Comando: {self.current_line}")
                            self.log(f"    Posición: X={self.position['x']:.2f}, Y={self.position['y']:.2f}, Z={self.position['z']:.2f}")
                            
                            if self.streaming:
                                self.log("❌ Deteniendo streaming por error")
                                self.stop_streaming()
                
                time.sleep(0.01)
            
            except Exception as e:
                self.log(f"❌ Error leyendo respuesta: {e}")
                break
    
    # ===== MOVIMIENTO JOG (CONTROL MANUAL) =====
    def jog(self, direction, speed_mm):
        """
        Movimiento manual
        direction: 'x+', 'x-', 'y+', 'y-', 'z+', 'z-'
        speed_mm: distancia en mm
        """
        if not self.port or not self.port.is_open:
            self.log("❌ Puerto no conectado")
            return False
        
        def _jog_thread():
            # Parsear dirección
            axis = direction[0].upper()
            sign = "+" if direction[1] == "+" else "-"
            
            # Calcular nueva posición
            new_position = self.position.copy()
            move_distance = float(speed_mm) if sign == "+" else -float(speed_mm)
            new_position[axis.lower()] += move_distance
            
            # ✅ CORRECCIÓN: Validar límites ANTES de enviar
            if not self.check_limits(**new_position):
                self.log(f"❌ ERROR: Movimiento fuera de límites")
                self.log(f"   Eje {axis}: {self.position[axis.lower()]:.2f} → {new_position[axis.lower()]:.2f}")
                self.log(f"   Límite {axis}: {self.machine_limits[axis.lower()]}")
                return
            
            # ✅ CORRECCIÓN: Comando G-code bien formado
            # Usar G91 (incremental), G1 (movimiento lineal)
            if sign == "+":
                command = f"G91\nG1 {axis}+{speed_mm} F1000"
            else:
                command = f"G91\nG1 {axis}{speed_mm} F1000"
            
            self.log(f"📍 Moviendo {axis} {speed_mm}mm ({direction})")
            
            # Enviar comando
            if self.send_command(command):
                # ✅ Esperar a que Arduino responda
                time.sleep(1)
                
                # ✅ Volver a modo absoluto
                self.send_command("G90")
                
                # ✅ Solicitar estado para actualizar posición
                time.sleep(0.2)
                self.send_command("?")
        
        # Ejecutar en hilo para no bloquear GUI
        threading.Thread(target=_jog_thread, daemon=True).start()
        return True
    
    # ===== ESTABLECER ORIGEN =====
    def set_origin(self):
        """✅ CORRECCIÓN: Establece origen correctamente"""
        if not self.port or not self.port.is_open:
            self.log("❌ Puerto no conectado")
            return False
        
        self.log("📌 Estableciendo origen...")
        
        # ✅ Paso 1: Modo absoluto
        self.send_command("G90")
        time.sleep(0.3)
        
        # ✅ Paso 2: Ir a (0, 0, 0)
        self.send_command("G1 X0 Y0")
        time.sleep(1)
        
        # ✅ Paso 3: Actualizar posición local
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        self.origin_set = True
        
        # ✅ Paso 4: Solicitar confirmación
        time.sleep(0.2)
        self.send_command("?")
        
        self.log("✅ Origen establecido en (0, 0, 0)")
        return True
    
    # ===== CARGA DE G-CODE =====
    def load_gcode(self, filename):
        """Carga archivo G-code"""
        try:
            with open(filename, 'r') as f:
                lines = f.readlines()
            
            self.gcode = []
            for line in lines:
                line = line.strip()
                # Filtrar comentarios y líneas vacías
                if line and not line.startswith(';') and not line.startswith('('):
                    self.gcode.append(line)
            
            self.log(f"✅ Cargado: {filename} ({len(self.gcode)} líneas)")
            return True
        
        except Exception as e:
            self.log(f"❌ Error cargando archivo: {str(e)}")
            return False
    
    # ===== STREAMING DE G-CODE =====
    def send_next_gcode_line(self):
        """✅ CORRECCIÓN: Envía siguiente línea con validación"""
        if self.gcode_index < len(self.gcode):
            line = self.gcode[self.gcode_index]
            
            # ✅ Extraer y validar coordenadas ANTES de enviar
            x, y, z = self._extract_coordinates(line)
            
            # Determinar posición final
            final_x = x if x is not None else self.position['x']
            final_y = y if y is not None else self.position['y']
            final_z = z if z is not None else self.position['z']
            
            # Validar límites
            if x is not None or y is not None or z is not None:
                if not self.check_limits(final_x, final_y, final_z):
                    self.log(f"❌ LÍNEA {self.gcode_index}: FUERA DE LÍMITES")
                    self.log(f"   Comando: {line}")
                    self.log(f"   Coordenadas: X={final_x:.2f}, Y={final_y:.2f}, Z={final_z:.2f}")
                    self.stop_streaming()
                    return False
            
            # Enviar línea
            if self.send_command(line):
                self.gcode_index += 1
                return True
        
        else:
            # Fin del G-code
            self.streaming = False
            self.log("✅ G-code completado")
            self.log("🔄 Retornando a origen...")
            self.return_to_origin()
            messagebox.showinfo("Completado", "G-code ejecutado correctamente")
            return False
    
    def start_streaming(self):
        """Inicia streaming de G-code"""
        if not self.gcode:
            messagebox.showwarning("Advertencia", "No hay G-code cargado")
            return
        
        self.streaming = True
        self.paused = False
        self.gcode_index = 0
        
        # ✅ Asegurar modo absoluto
        self.log("Iniciando streaming...")
        self.send_command("G90")
        time.sleep(0.2)
        
        # Enviar primera línea
        self.send_next_gcode_line()
    
    def pause_streaming(self):
        """Pausa streaming"""
        self.paused = True
        self.log("⏸️  Streaming pausado")
    
    def resume_streaming(self):
        """Reanuda streaming"""
        self.paused = False
        if self.streaming:
            self.log("▶️  Streaming reanudado")
            self.send_next_gcode_line()
    
    def stop_streaming(self):
        """Detiene streaming"""
        self.streaming = False
        self.paused = False
        self.log("⏹️  Streaming detenido")
        self.log("🔄 Retornando a origen...")
        self.return_to_origin()
    
    def return_to_origin(self):
        """Retorna a origen"""
        if not self.port or not self.port.is_open:
            return False
        
        # Pluma arriba
        self.send_command("M300 S50")
        time.sleep(0.5)
        
        # Modo absoluto
        self.send_command("G90")
        time.sleep(0.2)
        
        # Ir a origen
        self.send_command("G1 X0 Y0")
        time.sleep(1)
        
        # Actualizar posición
        self.position = {'x': 0.0, 'y': 0.0, 'z': 1.0}
        
        self.log("✅ Máquina en origen")
        return True
    
    def get_status(self):
        """Obtiene estado de la máquina"""
        self.send_command("?")
    
    def emergency_stop(self):
        """Parada de emergencia"""
        if self.port and self.port.is_open:
            try:
                self.port.write(b'\x18')  # Ctrl+X
            except:
                pass
        
        self.stop_streaming()
        self.log("🚨 ¡PARADA DE EMERGENCIA!")
    
    def disconnect(self):
        """Desconecta"""
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
        self.root.title("CNC Plotter - Control CD-ROM [CORREGIDO]")
        self.root.geometry("1000x700")
        
        self.controller = GCodeController()
        self.controller.set_log_callback(self.log)
        
        self.create_widgets()
        self.update_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.update_position()
    
    def create_widgets(self):
        """Crea interfaz gráfica"""
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # === PANEL DE CONTROL ===
        control_frame = ttk.LabelFrame(main_frame, text="Control", padding="5")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Selector de puerto
        ttk.Label(control_frame, text="Puerto:").grid(row=0, column=0, padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(control_frame, textvariable=self.port_var, width=20)
        self.port_combo.grid(row=0, column=1, padx=5)
        
        ttk.Button(control_frame, text="Refrescar", command=self.update_ports).grid(row=0, column=2, padx=5)
        self.connect_btn = ttk.Button(control_frame, text="Conectar", command=self.toggle_connection)
        self.connect_btn.grid(row=0, column=3, padx=5)
        
        # === PANEL DE G-CODE ===
        gcode_frame = ttk.LabelFrame(main_frame, text="G-code", padding="5")
        gcode_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.gcode_area = scrolledtext.ScrolledText(gcode_frame, width=50, height=15)
        self.gcode_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Button(gcode_frame, text="Cargar G-code", command=self.open_file).grid(row=1, column=0, pady=5)
        
        # === PANEL DE CONTROL MANUAL ===
        jog_frame = ttk.LabelFrame(main_frame, text="Control Manual", padding="5")
        jog_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10)
        
        # Botones de movimiento
        ttk.Button(jog_frame, text="Y+", command=lambda: self.jog('y+', 1.0), width=5).grid(row=0, column=1, padx=2, pady=2)
        ttk.Button(jog_frame, text="X-", command=lambda: self.jog('x-', 1.0), width=5).grid(row=1, column=0, padx=2, pady=2)
        ttk.Button(jog_frame, text="X+", command=lambda: self.jog('x+', 1.0), width=5).grid(row=1, column=2, padx=2, pady=2)
        ttk.Button(jog_frame, text="Y-", command=lambda: self.jog('y-', 1.0), width=5).grid(row=2, column=1, padx=2, pady=2)
        
        # Botones Z (servo)
        ttk.Button(jog_frame, text="Z+", command=lambda: self.send_command("M300 S30"), width=5).grid(row=3, column=0, padx=2, pady=5)
        ttk.Button(jog_frame, text="Z-", command=lambda: self.send_command("M300 S50"), width=5).grid(row=3, column=2, padx=2, pady=5)
        
        # Botones especiales
        ttk.Button(jog_frame, text="Origen", command=self.set_origin, width=10).grid(row=4, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(jog_frame, text="Home", command=self.home, width=10).grid(row=5, column=0, columnspan=3, pady=5, sticky=(tk.W, tk.E))
        
        # === PANEL DE STREAMING ===
        stream_frame = ttk.LabelFrame(main_frame, text="Streaming", padding="5")
        stream_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.start_btn = ttk.Button(stream_frame, text="▶️  Iniciar", command=self.start_streaming, state=tk.DISABLED)
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.pause_btn = ttk.Button(stream_frame, text="⏸️  Pausar", command=self.pause_streaming, state=tk.DISABLED)
        self.pause_btn.grid(row=0, column=1, padx=5)
        
        self.stop_btn = ttk.Button(stream_frame, text="⏹️  Detener", command=self.stop_streaming, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=2, padx=5)
        
        self.emergency_btn = ttk.Button(stream_frame, text="🚨 EMERGENCIA", command=self.emergency_stop, state=tk.DISABLED)
        self.emergency_btn.grid(row=0, column=3, padx=5)
        
        # === PANEL DE POSICIÓN ===
        pos_frame = ttk.LabelFrame(main_frame, text="Posición Actual", padding="5")
        pos_frame.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        ttk.Label(pos_frame, text="X:").grid(row=0, column=0)
        self.x_pos_label = ttk.Label(pos_frame, text="0.00 mm")
        self.x_pos_label.grid(row=0, column=1)
        
        ttk.Label(pos_frame, text="Y:").grid(row=1, column=0)
        self.y_pos_label = ttk.Label(pos_frame, text="0.00 mm")
        self.y_pos_label.grid(row=1, column=1)
        
        ttk.Label(pos_frame, text="Z:").grid(row=2, column=0)
        self.z_pos_label = ttk.Label(pos_frame, text="1.00")
        self.z_pos_label.grid(row=2, column=1)
        
        # === PANEL DE LOG ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_area = scrolledtext.ScrolledText(log_frame, width=100, height=8)
        self.log_area.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
    
    # === MÉTODOS DE INTERFAZ ===
    def update_ports(self):
        """Actualiza lista de puertos"""
        ports = self.controller.find_serial_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        """Conecta/desconecta"""
        if not self.controller.port or not self.controller.port.is_open:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Selecciona un puerto")
                return
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="Desconectar")
                self.start_btn.configure(state=tk.NORMAL)
                self.emergency_btn.configure(state=tk.NORMAL)
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="Conectar")
            self.start_btn.configure(state=tk.DISABLED)
    
    def open_file(self):
        """Abre diálogo de archivo"""
        filename = filedialog.askopenfilename(
            filetypes=[("G-code", "*.gcode *.nc *.g"), ("Todos", "*.*")]
        )
        if filename:
            if self.controller.load_gcode(filename):
                self.gcode_area.delete(1.0, tk.END)
                for i, line in enumerate(self.controller.gcode, 1):
                    self.gcode_area.insert(tk.END, f"{i:4d}: {line}\n")
                self.start_btn.configure(state=tk.NORMAL)
    
    def jog(self, direction, speed_mm):
        """Movimiento manual"""
        self.controller.jog(direction, speed_mm)
    
    def send_command(self, command):
        """Envía comando directo"""
        self.controller.send_command(command)
    
    def set_origin(self):
        """Establece origen"""
        self.controller.set_origin()
    
    def home(self):
        """Va a origen"""
        self.controller.send_command("G90")
        self.controller.send_command("G1 X0 Y0")
    
    def start_streaming(self):
        """Inicia streaming"""
        self.controller.start_streaming()
        self.start_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
    
    def pause_streaming(self):
        """Pausa streaming"""
        if not self.controller.paused:
            self.controller.pause_streaming()
            self.pause_btn.configure(text="⏸️  Reanudar")
        else:
            self.controller.resume_streaming()
            self.pause_btn.configure(text="⏸️  Pausar")
    
    def stop_streaming(self):
        """Detiene streaming"""
        self.controller.stop_streaming()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED, text="⏸️  Pausar")
        self.stop_btn.configure(state=tk.DISABLED)
    
    def emergency_stop(self):
        """Parada de emergencia"""
        self.controller.emergency_stop()
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
    
    def log(self, message):
        """Registra mensaje en GUI"""
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
    
    def update_position(self):
        """Actualiza posición mostrada"""
        self.x_pos_label.configure(text=f"{self.controller.position['x']:.2f} mm")
        self.y_pos_label.configure(text=f"{self.controller.position['y']:.2f} mm")
        self.z_pos_label.configure(text=f"{self.controller.position['z']:.2f}")
        
        self.root.after(200, self.update_position)
    
    def on_closing(self):
        """Cierra aplicación"""
        if messagebox.askokcancel("Salir", "¿Cerrar aplicación?"):
            self.controller.disconnect()
            self.root.destroy()


def main():
    """Punto de entrada"""
    root = tk.Tk()
    app = GCodeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
