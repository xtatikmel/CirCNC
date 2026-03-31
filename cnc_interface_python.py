"""
=====================================
CIRCE CNC - CONTROLADOR PROFESIONAL
=====================================
Versión: Transformación y Control.
✅ Comunicación serial optimizada
✅ Control en tiempo real
✅ Interface gráfica profesional
✅ Joystick virtual
✅ Monitor de posición
✅ Calibración dinámica
✅ Log de comandos completo

Requisitos:
pip install pyserial tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import threading
import time
from datetime import datetime
import platform

# ===== CONSTANTES =====
DISTANCE_PER_STEP = 0.127  # mm
EFFECTIVE_STROKE = 80.01   # mm
MAX_POSITION = int(EFFECTIVE_STROKE / DISTANCE_PER_STEP)

class CNController:
    """Controlador CNC profesional"""
    
    def __init__(self):
        self.port = None
        self.connected = False
        self.running = True
        
        self.position = {
            'x': 0.0,
            'y': 0.0,
            'z': 90,
            'x_steps': 0,
            'y_steps': 0
        }
        
        self.limits = {
            'x_min': 0,
            'x_max': MAX_POSITION,
            'y_min': 0,
            'y_max': MAX_POSITION,
            'z_min': 0,
            'z_max': 180
        }
        
        self.speed_modes = {
            '1': 'SPD1',  # Muy lento
            '2': 'SPD2',  # Lento
            '3': 'SPD3',  # Normal
            '4': 'SPD4',  # Rápido
            '5': 'SPD5'   # Muy rápido
        }
        
        self.current_speed = '3'  # Normal por defecto
        self.log_callback = None
        self.position_callback = None
    
    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def set_position_callback(self, callback):
        self.position_callback = callback
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        if self.log_callback:
            self.log_callback(msg)
    
    def find_serial_ports(self):
        """Encuentra puertos seriales disponibles"""
        ports = []
        try:
            from serial.tools import list_ports
            for p in list_ports.comports():
                ports.append(p.device)
        except:
            pass
        
        # Fallback para Linux/Mac
        if not ports:
            if platform.system() == 'Linux':
                import glob
                ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        
        return ports if ports else ['COM1', 'COM3', 'COM4']  # Sugerencias
    
    def connect(self, port_name, baudrate=9600):
        """Conecta con Arduino"""
        try:
            if self.port and self.port.is_open:
                self.port.close()
            
            self.port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                timeout=0.5
            )
            
            time.sleep(0.5)
            self.connected = True
            self.log(f"✅ Conectado a {port_name}")
            
            # Iniciar thread de lectura
            read_thread = threading.Thread(target=self._read_responses, daemon=True)
            read_thread.start()
            
            # Solicitar información
            time.sleep(0.5)
            self.send_command("INFO")
            
            return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False
    
    def _read_responses(self):
        """Lee respuestas del Arduino"""
        while self.running and self.connected and self.port:
            try:
                if self.port.in_waiting > 0:
                    response = self.port.readline().decode().strip()
                    if response:
                        self.log(f"← {response}")
                        self._parse_response(response)
                time.sleep(0.01)
            except:
                pass
    
    def _parse_response(self, response):
        """Parsea respuestas del Arduino para actualizar posición"""
        if response.startswith("POS X:"):
            try:
                # Formato: "POS X:20.150mm Y:15.320mm Z:90°"
                parts = response.replace("POS ", "").split()
                for part in parts:
                    if part.startswith("X:"):
                        self.position['x'] = float(part.split(":")[1].replace("mm", ""))
                    elif part.startswith("Y:"):
                        self.position['y'] = float(part.split(":")[1].replace("mm", ""))
                    elif part.startswith("Z:"):
                        self.position['z'] = int(part.split(":")[1].replace("°", ""))
                
                if self.position_callback:
                    self.position_callback(self.position)
            except:
                pass
    
    def send_command(self, command):
        """Envía comando a Arduino"""
        if not self.port or not self.port.is_open:
            self.log("❌ No conectado")
            return False
        
        try:
            cmd = command + '\n'
            self.port.write(cmd.encode())
            self.log(f"→ {command}")
            return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False
    
    def move_x(self, direction):
        """Mueve motor X"""
        cmd = "X+" if direction > 0 else "X-"
        return self.send_command(cmd)
    
    def move_y(self, direction):
        """Mueve motor Y"""
        cmd = "Y+" if direction > 0 else "Y-"
        return self.send_command(cmd)
    
    def move_z(self, direction):
        """Mueve servo Z"""
        cmd = "Z+" if direction > 0 else "Z-"
        return self.send_command(cmd)
    
    def set_speed(self, speed):
        """Cambia velocidad"""
        if speed in self.speed_modes:
            self.current_speed = speed
            return self.send_command(self.speed_modes[speed])
        return False
    
    def stop(self):
        """Detiene todo"""
        return self.send_command("STOP")
    
    def home(self):
        """Retorna a origen"""
        return self.send_command("HOME")
    
    def calibrate_x_min(self):
        """Calibra X mínimo"""
        return self.send_command("CALIB_X_MIN")
    
    def calibrate_x_max(self):
        """Calibra X máximo"""
        return self.send_command("CALIB_X_MAX")
    
    def calibrate_y_min(self):
        """Calibra Y mínimo"""
        return self.send_command("CALIB_Y_MIN")
    
    def calibrate_y_max(self):
        """Calibra Y máximo"""
        return self.send_command("CALIB_Y_MAX")
    
    def reset_limits(self):
        """Reset de límites"""
        return self.send_command("RESET_LIMITS")
    
    def get_status(self):
        """Solicita estado actual"""
        return self.send_command("STATUS")
    
    def disconnect(self):
        """Desconecta"""
        self.running = False
        if self.port and self.port.is_open:
            self.port.close()
        self.connected = False


class CNCInterface:
    """Interfaz gráfica profesional"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("🪄 CIRCE CNC - CONTROL PROFESIONAL - Mini Plotter")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")
        
        self.controller = CNController()
        self.controller.set_log_callback(self.log)
        self.controller.set_position_callback(self.update_position_display)
        
        self.create_widgets()
        self.update_ports()
        
        # Mensaje de bienvenida con Arte ASCII
        self.log("  _____ _                _   _  _____ ")
        self.log(" / ____(_)              | \ | |/ ____|")
        self.log("| |     _ _ __ ___ ___  |  \| | |     ")
        self.log("| |    | | '__/ __/ _ \ | . ` | |     ")
        self.log("| |____| | | | (_|  __/ | |\  | |____ ")
        self.log(" \\_____|_|_|  \\___\\___| |_| \\_|\\_____|")
        self.log("-" * 40)
        self.log("🪄 Circe CNC: El poder de la transformación.")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind('<Key>', self.on_key_press)
        self.root.bind('<KeyRelease>', self.on_key_release)
        
        # Estado de teclas presionadas
        self.keys_pressed = set()
        
        # Actualizar posición periódicamente
        self.update_position()
    
    def create_widgets(self):
        """Crea interfaz gráfica"""
        
        # === HEADER ===
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
        
        # === CONTENIDO PRINCIPAL ===
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === PANEL IZQUIERDO ===
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Control manual
        control_frame = ttk.LabelFrame(left_frame, text="🎮 Control Manual", padding="10")
        control_frame.pack(fill=tk.X, pady=5)
        
        # Joystick visual
        tk.Button(control_frame, text="Y+", command=lambda: self.controller.move_y(1), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=0, column=1, padx=5, pady=5)
        
        tk.Button(control_frame, text="X-", command=lambda: self.controller.move_x(-1), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=1, column=0, padx=5, pady=5)
        
        tk.Button(control_frame, text="X+", command=lambda: self.controller.move_x(1), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=1, column=2, padx=5, pady=5)
        
        tk.Button(control_frame, text="Y-", command=lambda: self.controller.move_y(-1), 
                  width=6, height=2, font=("Arial", 12, "bold")).grid(row=2, column=1, padx=5, pady=5)
        
        # Servo
        servo_frame = ttk.LabelFrame(left_frame, text="🔧 Servo (Z)", padding="10")
        servo_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(servo_frame, text="Z- Arriba\n(0°)", command=lambda: self.controller.move_z(-1), 
                  width=10, height=2, bg="#4CAF50", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(servo_frame, text="Z+ Abajo\n(180°)", command=lambda: self.controller.move_z(1), 
                  width=10, height=2, bg="#FF5722", fg="white", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        
        # Velocidad
        speed_frame = ttk.LabelFrame(left_frame, text="⚡ Velocidad", padding="10")
        speed_frame.pack(fill=tk.X, pady=5)
        
        for i in range(1, 6):
            speed_labels = {
                '1': 'Muy Lento',
                '2': 'Lento',
                '3': 'Normal ⭐',
                '4': 'Rápido',
                '5': 'Muy Rápido'
            }
            ttk.Button(speed_frame, text=f"{i}\n{speed_labels[str(i)]}", 
                      command=lambda s=str(i): self.set_speed(s), width=10).grid(row=0, column=i-1, padx=2)
        
        # Calibración
        calib_frame = ttk.LabelFrame(left_frame, text="🔧 Calibración", padding="10")
        calib_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(calib_frame, text="X-MIN", command=self.controller.calibrate_x_min, 
                  width=12).grid(row=0, column=0, padx=2, pady=3)
        ttk.Button(calib_frame, text="X-MAX", command=self.controller.calibrate_x_max, 
                  width=12).grid(row=0, column=1, padx=2, pady=3)
        
        ttk.Button(calib_frame, text="Y-MIN", command=self.controller.calibrate_y_min, 
                  width=12).grid(row=1, column=0, padx=2, pady=3)
        ttk.Button(calib_frame, text="Y-MAX", command=self.controller.calibrate_y_max, 
                  width=12).grid(row=1, column=1, padx=2, pady=3)
        
        ttk.Button(calib_frame, text="🏠 Home", command=self.controller.home, 
                  width=25).grid(row=2, column=0, columnspan=2, padx=2, pady=5, sticky=(tk.W, tk.E))
        
        ttk.Button(calib_frame, text="🔄 Reset Límites", command=self.controller.reset_limits, 
                  width=25).grid(row=3, column=0, columnspan=2, padx=2, pady=5, sticky=(tk.W, tk.E))
        
        # === PANEL CENTRAL ===
        center_frame = ttk.Frame(main_paned)
        main_paned.add(center_frame, weight=2)
        
        # Posición
        pos_frame = ttk.LabelFrame(center_frame, text="📍 Posición Actual", padding="15")
        pos_frame.pack(fill=tk.X, pady=5)
        
        x_row = ttk.Frame(pos_frame)
        x_row.pack(fill=tk.X, pady=5)
        ttk.Label(x_row, text="X:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.x_label = ttk.Label(x_row, text="0.000 mm", font=("Arial", 14, "bold"), foreground="cyan")
        self.x_label.pack(side=tk.LEFT, padx=10)
        
        y_row = ttk.Frame(pos_frame)
        y_row.pack(fill=tk.X, pady=5)
        ttk.Label(y_row, text="Y:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.y_label = ttk.Label(y_row, text="0.000 mm", font=("Arial", 14, "bold"), foreground="lime")
        self.y_label.pack(side=tk.LEFT, padx=10)
        
        z_row = ttk.Frame(pos_frame)
        z_row.pack(fill=tk.X, pady=5)
        ttk.Label(z_row, text="Z:", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=10)
        self.z_label = ttk.Label(z_row, text="90°", font=("Arial", 14, "bold"), foreground="yellow")
        self.z_label.pack(side=tk.LEFT, padx=10)
        
        # Información
        info_frame = ttk.LabelFrame(center_frame, text="ℹ️ Información del Sistema", padding="10")
        info_frame.pack(fill=tk.X, pady=5)
        
        info_text = """Motor: 18° Stepper (Modelo 9294)
Resolución: 0.127 mm/paso
Carrera máxima: 80.01 mm (630 pasos)
Servo: SG90 (0-180°)
Driver: L293D Optimizado
Comunicación: Serial 9600 baud"""
        
        for line in info_text.split('\n'):
            ttk.Label(info_frame, text=line, font=("Courier", 9)).pack(anchor=tk.W)
        
        # === PANEL DERECHO ===
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        log_frame = ttk.LabelFrame(right_frame, text="📋 Log de Comandos", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, width=40, height=35, 
                                                   font=("Courier", 8), bg="#2a2a2a", fg="#00ff00")
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.config(state=tk.DISABLED)
    
    def update_ports(self):
        """Actualiza lista de puertos"""
        ports = self.controller.find_serial_ports()
        self.port_var.set('')
        combo = self.root.nametowidget(self.root.winfo_children()[0]).winfo_children()[2]
        combo['values'] = ports
        if ports:
            combo.set(ports[0])
    
    def toggle_connection(self):
        """Conecta/desconecta"""
        if not self.controller.connected:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Selecciona un puerto")
                return
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="🔌 Desconectar")
                self.status_label.configure(text="✅ Conectado", foreground="green")
            else:
                self.status_label.configure(text="❌ Error", foreground="red")
        else:
            self.controller.disconnect()
            self.connect_btn.configure(text="🔗 Conectar")
            self.status_label.configure(text="❌ Desconectado", foreground="red")
    
    def set_speed(self, speed):
        """Cambia velocidad"""
        if self.controller.connected:
            self.controller.set_speed(speed)
    
    def log(self, message):
        """Agrega mensaje al log"""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state=tk.DISABLED)
    
    def update_position_display(self, pos):
        """Actualiza display de posición"""
        self.x_label.configure(text=f"{pos['x']:.3f} mm")
        self.y_label.configure(text=f"{pos['y']:.3f} mm")
        self.z_label.configure(text=f"{pos['z']}°")
    
    def update_position(self):
        """Solicita posición periódicamente"""
        if self.controller.connected:
            self.controller.get_status()
        self.root.after(1000, self.update_position)
    
    def on_key_press(self, event):
        """Tecla presionada"""
        key = event.keysym.lower()
        
        if key in ['w', 'up']:
            if self.controller.connected:
                self.controller.move_y(1)
        elif key in ['s', 'down']:
            if self.controller.connected:
                self.controller.move_y(-1)
        elif key in ['a', 'left']:
            if self.controller.connected:
                self.controller.move_x(-1)
        elif key in ['d', 'right']:
            if self.controller.connected:
                self.controller.move_x(1)
        elif key == 'q':
            if self.controller.connected:
                self.controller.move_z(-1)
        elif key == 'e':
            if self.controller.connected:
                self.controller.move_z(1)
        elif key in ['1', '2', '3', '4', '5']:
            self.set_speed(key)
        elif key == 'space':
            if self.controller.connected:
                self.controller.stop()
        elif key == 'h':
            if self.controller.connected:
                self.controller.home()
    
    def on_key_release(self, event):
        """Tecla liberada"""
        pass
    
    def on_closing(self):
        """Cerrar aplicación"""
        if messagebox.askokcancel("Salir", "¿Cerrar aplicación?"):
            self.controller.disconnect()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = CNCInterface(root)
    root.mainloop()


if __name__ == "__main__":
    main()
