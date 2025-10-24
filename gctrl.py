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
        self.log_callback = None  # Callback para logging
        self.position = {'x': 0, 'y': 0, 'z': 0}  # Posición actual
        self.machine_limits = {'x': 0, 'y': 0, 'z': 0}  # Límites de la máquina
        
    def set_log_callback(self, callback):
        self.log_callback = callback
        
    def log(self, message):
        if self.log_callback:
            self.log_callback(message)
        
    def find_serial_ports(self):
        """Encuentra puertos seriales disponibles"""
        ports = []
        system = platform.system().lower()
        
        if "windows" in system:
            for i in range(1, 21):
                try:
                    port = f"COM{i}"
                    test_serial = serial.Serial(port, 9600, timeout=0.1)
                    test_serial.close()
                    ports.append(port)
                except:
                    pass
        else:
            patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/tty.usb*', '/dev/cu.usb*']
            for pattern in patterns:
                for port in glob.glob(pattern):
                    try:
                        test_serial = serial.Serial(port, 9600, timeout=0.1)
                        test_serial.close()
                        ports.append(port)
                    except:
                        pass
        
        return ports
    
    def connect(self, port_name):
        """Conecta al puerto serial"""
        if not port_name:
            return False
        
        try:
            if self.port:
                self.port.close()
            
            self.port = serial.Serial(port_name, 9600, timeout=1)
            self.port_name = port_name
            
            # Iniciar hilo de lectura
            read_thread = threading.Thread(target=self.read_responses, daemon=True)
            read_thread.start()
            
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Error conectando a {port_name}: {e}")
            return False
    
    def send_command(self, command):
        """Envía un comando al puerto serial"""
        if self.port and self.port.is_open:
            try:
                # Asegurar que el comando termina con \n
                if not command.endswith('\n'):
                    command = command + '\n'
                # Enviar el comando como bytes
                self.port.write(command.encode())
                self.current_line = command.strip()
                self.log(f"→ {self.current_line}")
                # Esperar un momento para asegurar que el Arduino procesa el comando
                time.sleep(0.1)
                return True
            except Exception as e:
                self.log(f"Error enviando comando: {e}")
                return False
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
                                self.position = {'x': x, 'y': y, 'z': z}
                            except:
                                pass
                        elif response.startswith("ok"):
                            if self.streaming and not self.paused:
                                time.sleep(0.1)
                                self.send_next_gcode_line()
                        elif response.startswith("error"):
                            self.log(f"Error en comando: {self.current_line}")
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
            messagebox.showinfo("Completado", "G-code ejecutado completamente")
        return False
    
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
    
    def emergency_stop(self):
        """Parada de emergencia"""
        if self.port and self.port.is_open:
            self.port.write(b'\x18')  # Ctrl+X
            self.stop_streaming()
    
    def disconnect(self):
        """Desconecta el puerto serial"""
        self.running = False
        if self.port and self.port.is_open:
            self.port.close()
    
    def get_status(self):
        """Obtiene el estado actual de la máquina"""
        self.send_command("?")
    
    def set_origin(self):
        """Establece la posición actual como origen"""
        self.send_command("G92X0Y0Z0")
        self.position = {'x': 0, 'y': 0, 'z': 0}
    
    def test_limits(self):
        """Prueba los límites de la máquina"""
        # Secuencia de prueba
        commands = [
            "G90",  # Modo absoluto
            "G0X0Y0Z0",  # Ir a origen
            "G0X10",  # Mover X
            "G0X0",   # Volver
            "G0Y10",  # Mover Y
            "G0Y0",   # Volver
            "G0Z10",  # Mover Z
            "G0Z0"    # Volver
        ]
        for cmd in commands:
            self.send_command(cmd)
            time.sleep(0.5)  # Esperar entre movimientos

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
        
        position_frame = ttk.LabelFrame(left_frame, text="Posición Actual", padding="5")
        position_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))
        ttk.Label(position_frame, text="X:").grid(row=0, column=0, padx=5)
        self.x_pos_label = ttk.Label(position_frame, text="0.000")
        self.x_pos_label.grid(row=0, column=1, padx=5)
        ttk.Label(position_frame, text="Y:").grid(row=0, column=2, padx=5)
        self.y_pos_label = ttk.Label(position_frame, text="0.000")
        self.y_pos_label.grid(row=0, column=3, padx=5)
        ttk.Label(position_frame, text="Z:").grid(row=0, column=4, padx=5)
        self.z_pos_label = ttk.Label(position_frame, text="0.000")
        self.z_pos_label.grid(row=0, column=5, padx=5)
        ttk.Button(position_frame, text="Actualizar", command=self.controller.get_status).grid(row=0, column=6, padx=5)
        ttk.Button(position_frame, text="Establecer Origen", command=self.set_origin).grid(row=0, column=7, padx=5)
        ttk.Button(position_frame, text="Probar Límites", command=self.test_limits).grid(row=0, column=8, padx=5)
        
        manual_frame = ttk.LabelFrame(left_frame, text="Control Manual", padding="5")
        manual_frame.grid(row=3, column=0, sticky=(tk.W, tk.E))
        ttk.Button(manual_frame, text="Origen", command=self.home).grid(row=0, column=0, padx=5)
        ttk.Button(manual_frame, text="Motor X +", command=lambda: self.jog('x+')).grid(row=0, column=1, padx=5)
        ttk.Button(manual_frame, text="Motor X -", command=lambda: self.jog('x-')).grid(row=0, column=2, padx=5)
        ttk.Button(manual_frame, text="Motor Y +", command=lambda: self.jog('y+')).grid(row=0, column=3, padx=5)
        ttk.Button(manual_frame, text="Motor Y -", command=lambda: self.jog('y-')).grid(row=0, column=4, padx=5)
        ttk.Button(manual_frame, text="Servo +", command=lambda: self.jog('z+')).grid(row=0, column=5, padx=5)
        ttk.Button(manual_frame, text="Servo -", command=lambda: self.jog('z-')).grid(row=0, column=6, padx=5)
        
        speed_frame = ttk.LabelFrame(left_frame, text="Velocidad", padding="5")
        speed_frame.grid(row=4, column=0, sticky=(tk.W, tk.E))
        self.speed_var = tk.StringVar(value="1")
        ttk.Radiobutton(speed_frame, text="Lenta", variable=self.speed_var, value="1").grid(row=0, column=0, padx=5)
        ttk.Radiobutton(speed_frame, text="Media", variable=self.speed_var, value="2").grid(row=0, column=1, padx=5)
        ttk.Radiobutton(speed_frame, text="Rápida", variable=self.speed_var, value="3").grid(row=0, column=2, padx=5)
        
        control_frame = ttk.Frame(left_frame, padding="5")
        control_frame.grid(row=5, column=0, sticky=(tk.W, tk.E))
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
        """Actualiza la lista de puertos disponibles"""
        ports = self.controller.find_serial_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        """Conecta/desconecta el puerto serial"""
        if not self.controller.port or not self.controller.port.is_open:
            if self.controller.connect(self.port_var.get()):
                self.connect_btn.configure(text="Desconectar")
                self.start_btn.configure(state=tk.NORMAL)
                self.emergency_btn.configure(state=tk.NORMAL)
                self.log("Conectado a " + self.controller.port_name)
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
            self.controller.send_command("$H")
            self.log("Enviando comando de origen")
            # Esperar un momento y actualizar posición
            self.root.after(1000, self.controller.get_status)

    def jog(self, direction):
        """Movimiento manual"""
        if self.controller.port and self.controller.port.is_open:
            # Obtener velocidad según selección
            speed = {
                "1": "0.001",  # Lenta
                "2": "0.01",   # Media
                "3": "0.1"     # Rápida
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
            self.x_pos_label.configure(text=f"{self.controller.position['x']:.3f}")
            self.y_pos_label.configure(text=f"{self.controller.position['y']:.3f}")
            self.z_pos_label.configure(text=f"{self.controller.position['z']:.3f}")
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
