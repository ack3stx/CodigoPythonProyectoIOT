from Padre import Padre
import serial
import platform
import json
from datetime import datetime,timedelta
import time
import requests
from Monitor import Monitor


BAUDRATE = 9600

class Sensores(Padre):
    def __init__(self):
        super().__init__()
        self.monitor = Monitor()  
        self.lista = False
        
        self.api_url = "http://192.168.137.242:8000/api/pruba"

    def validar_sensores_monitor(self, ultimo_dato):
        """
        Valida que el monitor tenga sensores válidos (cualquier combinación del 1 al 5)
        """
        if not ultimo_dato or 'sensor' not in ultimo_dato[0]:
            return False
        
        sensores_validos = [1, 2, 3, 4, 5]  # TEM, PIR, SON, GAS, LUZ
        sensores_monitor = ultimo_dato[0]['sensor']
        
        return all(sensor in sensores_validos for sensor in sensores_monitor)

    def transformar_datos_serial(self, datos_serial):
        """
        Transforma los datos del serial al formato JSON requerido
        """
        try:
            ultimo_dato = self.leerJson("ultimodato.json")
            if not self.validar_sensores_monitor(ultimo_dato):
                print("El monitor tiene sensores no válidos")
                return None
                    
            id_monitor = ultimo_dato[0]['id_monitor']
            sensores_disponibles = ultimo_dato[0]['sensor']
        except (FileNotFoundError, json.JSONDecodeError):
            print("Error al leer ultimodato.json")
            return None

        datos_formateados = {
            "id_monitor": id_monitor,
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        mapeo_sensores = {
            1: "TEM",
            2: "PIR",
            3: "SON",
            4: "GAS",
            5: "LUZ"
        }
        
        for num_sensor in sensores_disponibles:
            if num_sensor in mapeo_sensores:
                datos_formateados[f"{mapeo_sensores[num_sensor]}{id_monitor}"] = "0"
        
        datos_dict = {}
        for linea in datos_serial:
            if ':' in linea:
                sensor, valor = linea.split(':')
                datos_dict[sensor.strip()] = valor.strip()
        
        for num_sensor in sensores_disponibles:
            sensor_nombre = mapeo_sensores[num_sensor]
            for dato_sensor, valor in datos_dict.items():
                if sensor_nombre in dato_sensor:
                    datos_formateados[f"{sensor_nombre}{id_monitor}"] = valor
        
        try:
            datos_existentes = self.leerJson("datos_transformados.json")
        except (FileNotFoundError, json.JSONDecodeError):
            datos_existentes = []
        
        datos_existentes.append(datos_formateados)
        self.escribirJson("datos_transformados.json", datos_existentes)
        return datos_formateados

    def crear_monitor_offline(self):
            """
            Crea un monitor ficticio para usar cuando no hay conexión a internet
            """
            monitor_offline = [
                {
                    "id_monitor": 0,
                    "sensor": [1, 2, 3, 4, 5],
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "FechaObj": {
                        "$date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    }
                }
            ]
            self.escribirJson("ultimodato.json", monitor_offline)
            print("Monitor offline creado con ID 0")
            return monitor_offline[0]

    def leer_serial(self):
        ser = self.conectar_serial()
        tiene_conexion = self.verificar_conexcion_internet()

        if tiene_conexion:
            self.monitor.obtenerultimodato_Monitor()
            self.verificar_y_enviar_datos_sincronizados()  
        else:
            self.crear_monitor_offline()
        
        try:
            while True:
                datos_actuales = []
                if ser.in_waiting:
                    for _ in range(4):
                        linea = ser.readline().decode('utf-8').strip()
                        datos_actuales.append(linea)
                        print(linea)
                    
                    # Verificar conexión actual
                    conexion_anterior = tiene_conexion
                    tiene_conexion = self.verificar_conexcion_internet()
                    
                    if not conexion_anterior and tiene_conexion:
                        print("Conexión recuperada. Actualizando datos del monitor...")
                        self.monitor.obtenerultimodato_Monitor()
                        self.monitor.guardatosultimos10RegistrosJson()
                        self.sincronizar_datos_offline()
                        self.verificar_y_enviar_datos_sincronizados()  
                    
                    if conexion_anterior and not tiene_conexion:
                        print("Conexión perdida. Usando monitor offline...")
                        self.crear_monitor_offline()
                    
                    datos_json = self.transformar_datos_serial(datos_actuales)
                    if datos_json:
                        if tiene_conexion:
                            self.enviar_datos_api(datos_json)
                            self.verificar_y_enviar_datos_sincronizados() 
                        else:
                            self.guardar_datos_offline(datos_json)
                    
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\nLectura interrumpida por el usuario")
        except serial.SerialException:
            print("\nConexión serial terminada")
        finally:
            ser.close()

    def conectar_serial(self):
        if platform.system() == 'Windows':
            puerto = 'COM5'
        else:
            puerto = '/dev/ttyUSB0'
        ser = serial.Serial(puerto, baudrate=BAUDRATE)
        return ser

    def enviar_datos_api(self, datos_sensor):
        """
        Envía los datos del sensor a la API
        """
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(self.api_url, json=datos_sensor, headers=headers)
            
            if response.status_code == 201:
                print(f"Datos enviados a API - ID Monitor: {datos_sensor['id_monitor']}")
                return True
            else:
                print(f"Error al enviar datos: Status code {response.status_code}")
                return False
        except Exception as e:
            print(f"Error al enviar datos a la API: {e}")
            return False

    def guardar_datos_offline(self, datos):
        """
        Guarda los datos cuando no hay conexión
        """
        try:
            datos_offline = self.leerJson("usuariosinconexion.json")
        except (FileNotFoundError, json.JSONDecodeError):
            datos_offline = []
        
        datos_offline.append(datos)
        self.escribirJson("usuariosinconexion.json", datos_offline)
        print("Datos guardados en modo sin conexión")


    def sincronizar_datos_offline(self):
        """
        Sincroniza los datos guardados sin conexión con los últimos registros
        de monitores, comparando por fechas.
        """
        try:
            datos_offline = self.leerJson("usuariosinconexion.json")
            if not datos_offline:
                print("No hay datos offline para sincronizar")
                return
            
            ultimos_registros = self.leerJson("ultimos10Registros.json")
            if not ultimos_registros:
                print("No hay registros de monitores para comparar")
                return
            
            print(f"Sincronizando {len(datos_offline)} registros offline...")
            
            for registro in ultimos_registros:
                if 'Fecha' in registro:
                    registro['datetime'] = datetime.strptime(registro['Fecha'], "%Y-%m-%d %H:%M:%S")
            
            datos_sincronizados = []
            datos_no_sincronizados = []
            
            for dato_offline in datos_offline:
                if 'Fecha' in dato_offline and dato_offline['id_monitor'] == 0:
                    fecha_offline = datetime.strptime(dato_offline['Fecha'], "%Y-%m-%d %H:%M:%S")
                    
                    mejor_registro = None
                    menor_diferencia = timedelta(hours=24)
                    
                    for registro in ultimos_registros:
                        diferencia = abs(registro['datetime'] - fecha_offline)
                        
                        if diferencia < menor_diferencia:
                            menor_diferencia = diferencia
                            mejor_registro = registro
                    
                    if mejor_registro and menor_diferencia < timedelta(minutes=30):
                        dato_sincronizado = dato_offline.copy()
                        
                        id_monitor_real = mejor_registro['id_monitor']
                        dato_sincronizado['id_monitor'] = id_monitor_real
                        
                        mapeo_sensores = {1: "TEM", 2: "PIR", 3: "SON", 4: "GAS", 5: "LUZ"}
                        
                        nuevo_dato = {
                            "id_monitor": id_monitor_real,
                            "Fecha": dato_offline['Fecha']
                        }
                        
                        for sensor_id in mejor_registro.get('sensor', []):
                            if sensor_id in mapeo_sensores:
                                sensor_nombre = mapeo_sensores[sensor_id]
                                sensor_key_old = f"{sensor_nombre}0" 
                                sensor_key_new = f"{sensor_nombre}{id_monitor_real}" 
                                
                                if sensor_key_old in dato_offline:
                                    nuevo_dato[sensor_key_new] = dato_offline[sensor_key_old]
                        
                        datos_sincronizados.append(nuevo_dato)
                        print(f"Registro sincronizado: {dato_offline['Fecha']} -> Monitor {id_monitor_real}")
                    else:
                        datos_no_sincronizados.append(dato_offline)
                        print(f"No se encontró monitor cercano para: {dato_offline['Fecha']}")
                else:
                    datos_no_sincronizados.append(dato_offline)
            
            if datos_sincronizados:
                try:
                    datos_existentes = self.leerJson("datos_sincronizados.json")
                except (FileNotFoundError, json.JSONDecodeError):
                    datos_existentes = []
                
                datos_existentes.extend(datos_sincronizados)
                self.escribirJson("datos_sincronizados.json", datos_existentes)
                print(f"Se sincronizaron {len(datos_sincronizados)} registros")
            
            if datos_no_sincronizados:
                self.escribirJson("usuariosinconexion.json", datos_no_sincronizados)
                print(f"Quedan {len(datos_no_sincronizados)} registros por sincronizar")
            else:
                self.escribirJson("usuariosinconexion.json", [])
                print("Todos los datos fueron sincronizados")
            
            return datos_sincronizados
            
        except Exception as e:
            print(f"Error al sincronizar datos offline: {e}")
            return []
        
    def verificar_y_enviar_datos_sincronizados(self):
        """
        Verifica si hay datos sincronizados para enviar y los envía a la API
        """
        try:
            try:
                datos_sincronizados = self.leerJson("datos_sincronizados.json")
            except (FileNotFoundError, json.JSONDecodeError):
                return  
            
            if not datos_sincronizados:
                return  
            
            print(f"Enviando {len(datos_sincronizados)} registros sincronizados a la API...")
            
            datos_pendientes = []
            
            for dato in datos_sincronizados:
                if self.enviar_datos_api(dato):
                    print(f"Dato sincronizado enviado - ID Monitor: {dato['id_monitor']}")
                else:
                    datos_pendientes.append(dato)
            
            self.escribirJson("datos_sincronizados.json", datos_pendientes)
            
            if not datos_pendientes:
                print("Todos los datos sincronizados fueron enviados correctamente")
            else:
                print(f"Quedan {len(datos_pendientes)} datos pendientes de enviar")
        
        except Exception as e:
            print(f"Error al enviar datos sincronizados: {e}")

if __name__ == "__main__":
    sensores = Sensores()
    sensores.leer_serial()