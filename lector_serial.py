import serial
import time

# Configuración del puerto serial
BAUDRATE = 9600
PUERTO = '/dev/ttyUSB0'  # Cambia esto según tu sistema (Windows: 'COM5', Linux: '/dev/ttyUSB0')

def mostrar_datos_serial():
    try:
        # Intenta diferentes puertos si no encuentra el principal
        puertos_posibles = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
        
        # Para Windows, añade los puertos COM
        puertos_posibles.extend([f'COM{i}' for i in range(1, 10)])
        
        # Intenta conectarse a cada puerto
        ser = None
        for puerto in puertos_posibles:
            try:
                print(f"Intentando conectar a {puerto}...")
                ser = serial.Serial(puerto, baudrate=BAUDRATE, timeout=1)
                print(f"¡Conexión exitosa en {puerto}!")
                break
            except (serial.SerialException, OSError):
                pass
        
        if ser is None:
            print("No se pudo conectar a ningún puerto serial. Verifica la conexión.")
            return
            
        print("Mostrando datos del puerto serial. Presiona Ctrl+C para detener.")
        
        # Leer y mostrar datos
        while True:
            if ser.in_waiting:
                linea = ser.readline().decode('utf-8', errors='replace').strip()
                if linea:
                    print(f"Recibido: {linea}")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nLectura interrumpida por el usuario")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser is not None:
            ser.close()
            print("Puerto serial cerrado")

if __name__ == "__main__":
    mostrar_datos_serial()