from Padre import Padre
from bson import json_util
import time

class Monitor(Padre):
    def __init__(self):
        super().__init__()
        self.lista = False
        self.lista_objetos = []
        self.id = None   

    def observar_cambios(self):
        while True: 
            try:
                if not self.verificar_conexcion_internet():
                    print("No hay conexión a internet. Esperando conexión...")
                    while not self.verificar_conexcion_internet():
                        time.sleep(5)
                    print("Conexión recuperada.")
                
                coleccion = self.conexion_Mongo("DatosMonitores")
                
                change_stream = coleccion.watch([
                    {'$match': {'operationType': 'insert'}}
                ])
                
                print("Observando cambios en la colección...")
                
                while True:
                    try:
                        change = change_stream.next()
                        doc_insertado = change['fullDocument']
                        print(f"Nuevo documento insertado - ID Monitor: {doc_insertado.get('id_monitor')}")
                        self.guardatosultimos10RegistrosJson()
                        self.obtenerultimodato_Monitor()
                    except Exception as e:
                        print(f"Error durante la observación: {e}")
                        # Si hay error durante la observación, salir del bucle interno
                        # para verificar conexión nuevamente
                        break
                        
            except KeyboardInterrupt:
                print("\nObservación de cambios interrumpida por el usuario")
                if 'change_stream' in locals():
                    change_stream.close()
                return  # Salir completamente
                
            except Exception as e:
                print(f"Error de conexión: {e}")
                print("Intentando reconectar en 10 segundos...")
                time.sleep(10)
                
            # Si llegamos aquí, el bucle interno se rompió, intentamos reconectar
            if 'change_stream' in locals():
                try:
                    change_stream.close()
                except:
                    pass
            
            print("Reconectando...")
            time.sleep(5)

        print("Observando cambios en la colección...")
        try:
            while True:
                change = change_stream.next()
                doc_insertado = change['fullDocument']
                print(f"Nuevo documento insertado - ID Monitor: {doc_insertado.get('id_monitor')}")
                self.guardatosultimos10RegistrosJson()
                self.obtenerultimodato_Monitor()
        except KeyboardInterrupt:
            print("\nObservación de cambios interrumpida")
            change_stream.close()

    def obtener_Ultimo(self):
        coleccion = self.conexion_Mongo("DatosMonitores")
        
        pipeline = [
            {
                "$addFields": {
                    "FechaObj": {
                        "$dateFromString": {
                            "dateString": "$Fecha",
                            "format": "%Y-%m-%d %H:%M:%S"
                        }
                    }
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 1},
            {
                "$project": {
                    "_id": 0,
                    "id_monitor": 1,
                    "sensor": 1,
                    "Fecha": 1,
                    "FechaObj": 1
                }
            }
        ]
        
        registros = list(coleccion.aggregate(pipeline))
        return registros

    def obtener_Ultimos10_RegistrosMongo(self):
        coleccion = self.conexion_Mongo("DatosMonitores")
        
        pipeline = [
            {
                "$addFields": {
                    "FechaObj": {
                        "$dateFromString": {
                            "dateString": "$Fecha",
                            "format": "%Y-%m-%d %H:%M:%S"
                        }
                    }
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 10},
            {
                "$project": {
                    "_id": 0,
                    "id_monitor": 1,
                    "sensor": 1,
                    "Fecha": 1,
                    "FechaObj": 1
                }
            }
        ]
        
        registros = list(coleccion.aggregate(pipeline))
        return registros

    def obtenerultimodato_Monitor(self):
        """
        Obtiene el último registro y lo guarda en ultimodato.json
        """
        registros = self.obtener_Ultimo()
        if registros:  # Verificar si hay registros
            datos = []
            for registro in registros:
                datos.append(json_util.loads(json_util.dumps(registro)))
            self.escribirJson("ultimodato.json", datos)
            print(f"Último registro guardado: {datos}")

    def guardatosultimos10RegistrosJson(self):
        """
        Guarda los últimos 10 registros en ultimos10Registros.json
        """
        registros = self.obtener_Ultimos10_RegistrosMongo()
        datos = []
        for registro in registros:
            datos.append(json_util.loads(json_util.dumps(registro)))
        self.escribirJson("ultimos10Registros.json", datos)

    def insertarInfoSensorMongo(self, datos):
        """
        Inserta datos en MongoDB y actualiza los archivos JSON
        """
        coleccion = self.conexion_Mongo("DatosMonitores")
        coleccion.insert_one(datos)
        self.guardatosultimos10RegistrosJson()
        self.obtenerultimodato_Monitor()

if __name__ == "__main__":
    monitor = Monitor()
    monitor.observar_cambios()