from Padre import Padre
import serial
import platform
import json
from datetime import datetime, timedelta
import time
import requests
from Monitor import Monitor


BAUDRATE = 9600

class Sensores(Padre):
    def __init__(self):
        super().__init__()
        self.monitor = Monitor()  
        self.lista = False
        
        self.api_url = "http://127.0.0.1:8000/api/prueba"
        self.bocina_api_url = "http://192.168.137.181:8000/api/bocina/estado"
        
        self.ultimo_tiempo_temp_alta = None
        self.contador_pir = 0
        self.tiempo_primer_pir = None
        self.buzzer_activado = False
        
        self.ultimo_alerta_sonido = None
        self.ultimo_alerta_gas = None
        self.ultimo_alerta_luz = None
        self.ultimo_alerta_temp_mov = None
        self.tiempo_entre_alertas = 300 

    def validar_sensores_monitor(self, ultimo_dato):
        if not ultimo_dato or 'sensor' not in ultimo_dato[0]:
            return False
        
        sensores_validos = [1, 2, 3, 4, 5]
        sensores_monitor = ultimo_dato[0]['sensor']
        
        return all(sensor in sensores_validos for sensor in sensores_monitor)

    def transformar_datos_serial(self, datos_serial):
        try:
            ultimo_dato = self.leerJson("ultimodato.json")
            if not self.validar_sensores_monitor(ultimo_dato):
                print("El monitor tiene sensores no válidos")
                return None
                    
            id_monitor = ultimo_dato[0]['id_monitor']
            user_id = ultimo_dato[0].get('user_id', 1)
            sensores_disponibles = ultimo_dato[0]['sensor']
        except (FileNotFoundError, json.JSONDecodeError):
            print("Error al leer ultimodato.json")
            return None

        datos_formateados = {
            "user_id": user_id,
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

    def verificar_condiciones_alerta(self, datos, id_monitor, user_id):
        tiempo_actual = datetime.now()
        
        ultimo_dato = self.leerJson("ultimodato.json")
        if not ultimo_dato or 'sensor' not in ultimo_dato[0]:
            print("No se pueden verificar alertas: datos del monitor no disponibles")
            return
        
        sensores_disponibles = ultimo_dato[0]['sensor']
        
        if 1 in sensores_disponibles:
            temp_key = f"TEM{id_monitor}"
            if temp_key in datos:
                try:
                    temp_valor = float(datos[temp_key])
                    if temp_valor > 40:
                        print(f"¡ALERTA! Temperatura alta: {temp_valor}")
                        self.ultimo_tiempo_temp_alta = tiempo_actual
                        
                        if 2 in sensores_disponibles:
                            self.verificar_buzzer_por_temperatura(id_monitor, user_id)
                except (ValueError, TypeError):
                    pass
        
        if 2 in sensores_disponibles:
            pir_key = f"PIR{id_monitor}"
            if pir_key in datos:
                try:
                    pir_valor = int(datos[pir_key])
                    if pir_valor > 0:
                        if self.tiempo_primer_pir is None:
                            self.tiempo_primer_pir = tiempo_actual
                        
                        self.contador_pir += 1
                        
                        if (tiempo_actual - self.tiempo_primer_pir).total_seconds() > 60:
                            self.contador_pir = 1
                            self.tiempo_primer_pir = tiempo_actual
                        
                        if self.contador_pir >= 15:
                            print("¡ALERTA! 15 movimientos detectados en menos de 1 minuto")
                            
                            if (1 in sensores_disponibles and 
                                self.ultimo_tiempo_temp_alta and 
                                (tiempo_actual - self.ultimo_tiempo_temp_alta).total_seconds() < 60):
                                
                                if (self.ultimo_alerta_temp_mov is None or 
                                    (tiempo_actual - self.ultimo_alerta_temp_mov).total_seconds() > self.tiempo_entre_alertas):
                                    
                                    print("¡ALERTA CRÍTICA! Temperatura alta y exceso de movimientos detectados")
                                    self.ultimo_alerta_temp_mov = tiempo_actual
                                    self.activar_buzzer(id_monitor, user_id)
                                else:
                                    tiempo_pasado = (tiempo_actual - self.ultimo_alerta_temp_mov).total_seconds()
                                    print(f"Alerta temperatura+movimiento suprimida (última hace {tiempo_pasado:.0f} segundos)")
                            
                            self.contador_pir = 0
                            self.tiempo_primer_pir = None
                except (ValueError, TypeError):
                    pass
        
        sensores_ambiente_disponibles = [sensor for sensor in [3, 4, 5] if sensor in sensores_disponibles]
        
        if sensores_ambiente_disponibles:
            try:
                son_valor = 0
                gas_valor = 0
                luz_valor = 0
                
                if 3 in sensores_disponibles:
                    son_key = f"SON{id_monitor}"
                    son_valor = float(datos.get(son_key, 0))
                    
                if 4 in sensores_disponibles:
                    gas_key = f"GAS{id_monitor}"
                    gas_valor = float(datos.get(gas_key, 0))
                    
                if 5 in sensores_disponibles:
                    luz_key = f"LUZ{id_monitor}"
                    luz_valor = float(datos.get(luz_key, 0))
                
                son_alerta = son_valor > 650
                gas_alerta = gas_valor > 400
                luz_alerta = luz_valor > 200
                
                alerta_enviada = False
                mensaje_alerta = "¡ALERTA!"
                
                if son_alerta:
                    mensaje_alerta += f" Sonido: {son_valor}"
                    if (self.ultimo_alerta_sonido is None or 
                        (tiempo_actual - self.ultimo_alerta_sonido).total_seconds() > self.tiempo_entre_alertas):
                        self.ultimo_alerta_sonido = tiempo_actual
                        alerta_enviada = True
                    else:
                        tiempo_pasado = (tiempo_actual - self.ultimo_alerta_sonido).total_seconds()
                        print(f"Alerta de sonido suprimida (última hace {tiempo_pasado:.0f} segundos)")
                
                if gas_alerta:
                    mensaje_alerta += f" Gas: {gas_valor}"
                    if (self.ultimo_alerta_gas is None or 
                        (tiempo_actual - self.ultimo_alerta_gas).total_seconds() > self.tiempo_entre_alertas):
                        self.ultimo_alerta_gas = tiempo_actual
                        alerta_enviada = True
                    else:
                        tiempo_pasado = (tiempo_actual - self.ultimo_alerta_gas).total_seconds()
                        print(f"Alerta de gas suprimida (última hace {tiempo_pasado:.0f} segundos)")
                
                if luz_alerta:
                    mensaje_alerta += f" Luz: {luz_valor}"
                    if (self.ultimo_alerta_luz is None or 
                        (tiempo_actual - self.ultimo_alerta_luz).total_seconds() > self.tiempo_entre_alertas):
                        self.ultimo_alerta_luz = tiempo_actual
                        alerta_enviada = True
                    else:
                        tiempo_pasado = (tiempo_actual - self.ultimo_alerta_luz).total_seconds()
                        print(f"Alerta de luz suprimida (última hace {tiempo_pasado:.0f} segundos)")
                
                if alerta_enviada and (son_alerta or gas_alerta or luz_alerta):
                    print(mensaje_alerta)
                    self.enviar_alerta_bocina(id_monitor, user_id)
            except (ValueError, TypeError):
                pass

    def verificar_buzzer_por_temperatura(self, id_monitor, user_id):
        ultimo_dato = self.leerJson("ultimodato.json")
        if not ultimo_dato or 'sensor' not in ultimo_dato[0]:
            return
        
        sensores_disponibles = ultimo_dato[0]['sensor']
        
        if 1 in sensores_disponibles and 2 in sensores_disponibles:
            if self.contador_pir >= 5 and self.tiempo_primer_pir and \
               (datetime.now() - self.tiempo_primer_pir).total_seconds() < 60:
                
                tiempo_actual = datetime.now()
                if (self.ultimo_alerta_temp_mov is None or 
                    (tiempo_actual - self.ultimo_alerta_temp_mov).total_seconds() > self.tiempo_entre_alertas):
                    
                    print("¡ALERTA CRÍTICA! Temperatura alta y exceso de movimientos detectados")
                    self.ultimo_alerta_temp_mov = tiempo_actual
                    self.activar_buzzer(id_monitor, user_id)
                else:
                    tiempo_pasado = (tiempo_actual - self.ultimo_alerta_temp_mov).total_seconds()
                    print(f"Alerta temperatura+movimiento suprimida (última hace {tiempo_pasado:.0f} segundos)")

    def activar_buzzer(self, id_monitor, user_id):
        if not self.buzzer_activado:
            print("Activando buzzer...")
            self.buzzer_activado = True
            
            self.enviar_alerta_bocina(id_monitor, user_id)
            
            time.sleep(10)
            self.buzzer_activado = False
            print("Buzzer desactivado")

    def enviar_alerta_bocina(self, id_monitor, user_id):
        try:
            ultimo_dato = self.leerJson("ultimodato.json")
            if not ultimo_dato:
                print("No se puede enviar alerta: datos del monitor no disponibles")
                return False
            
            datos_alerta = {
                "estado": "1",
                "id_monitor": str(id_monitor),
                "id_user": str(user_id)
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            print(f"Enviando alerta a bocina: {datos_alerta}")
            response = requests.post(self.bocina_api_url, json=datos_alerta, headers=headers)
            
            if response.status_code == 200 or response.status_code == 201:
                print("Alerta de bocina enviada correctamente")
                return True
            else:
                print(f"Error al enviar alerta de bocina: Status code {response.status_code}")
                return False
        except Exception as e:
            print(f"Error al enviar alerta de bocina: {e}")
            return False

    def crear_monitor_offline(self):
        monitor_offline = [
            {
                "user_id": 1,
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
        
        buffer_datos = []
        ultimo_envio = datetime.now()
        
        try:
            while True:
                datos_actuales = []
                if ser.in_waiting:
                    for _ in range(5):
                        linea = ser.readline().decode('utf-8').strip()
                        datos_actuales.append(linea)
                        print(linea)
                    
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
                        ultimo_dato = self.leerJson("ultimodato.json")
                        if ultimo_dato:
                            id_monitor = ultimo_dato[0]['id_monitor']
                            user_id = ultimo_dato[0].get('user_id', 1)
                            self.verificar_condiciones_alerta(datos_json, id_monitor, user_id)
                        
                        buffer_datos.append(datos_json)
                        
                        tiempo_actual = datetime.now()
                        if (tiempo_actual - ultimo_envio).total_seconds() >= 10 and buffer_datos:
                            datos_promediados = self.promediar_datos(buffer_datos)
                            
                            if tiene_conexion:
                                self.enviar_datos_api(datos_promediados)
                                self.verificar_y_enviar_datos_sincronizados() 
                            else:
                                self.guardar_datos_offline(datos_promediados)
                            
                            buffer_datos = []
                            ultimo_envio = tiempo_actual
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\nLectura interrumpida por el usuario")
        except serial.SerialException:
            print("\nConexión serial terminada")
        finally:
            ser.close()

    def promediar_datos(self, buffer_datos):
        if not buffer_datos:
            return None
        
        primer_dato = buffer_datos[0]
        datos_promediados = {
            "user_id": primer_dato["user_id"],
            "id_monitor": primer_dato["id_monitor"],
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        ultimo_dato = self.leerJson("ultimodato.json")
        sensores_disponibles = ultimo_dato[0]['sensor'] if ultimo_dato else []
        id_monitor = primer_dato["id_monitor"]
        
        mapeo_sensores = {
            1: "TEM",
            2: "PIR",
            3: "SON",
            4: "GAS",
            5: "LUZ"
        }
        
        for num_sensor in sensores_disponibles:
            if num_sensor in mapeo_sensores:
                sensor_key = f"{mapeo_sensores[num_sensor]}{id_monitor}"
                
                valores = []
                for dato in buffer_datos:
                    if sensor_key in dato:
                        try:
                            valores.append(float(dato[sensor_key]))
                        except (ValueError, TypeError):
                            pass
                
                if valores:
                    if num_sensor == 2:
                        datos_promediados[sensor_key] = "1" if any(v > 0 for v in valores) else "0"
                    else:
                        valor_promedio = sum(valores) / len(valores)
                        datos_promediados[sensor_key] = str(round(valor_promedio, 2))
                else:
                    datos_promediados[sensor_key] = "0"
        
        return datos_promediados

    def conectar_serial(self):
        if platform.system() == 'Windows':
            puerto = 'COM5'
        else:
            puerto = '/dev/ttyUSB0'
        ser = serial.Serial(puerto, baudrate=BAUDRATE)
        return ser

    def enviar_datos_api(self, datos_sensor):
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
        try:
            datos_offline = self.leerJson("usuariosinconexion.json")
        except (FileNotFoundError, json.JSONDecodeError):
            datos_offline = []
        
        datos_offline.append(datos)
        self.escribirJson("usuariosinconexion.json", datos_offline)
        print("Datos guardados en modo sin conexión")

    def sincronizar_datos_offline(self):
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
                            "user_id": mejor_registro.get('user_id', 1),
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