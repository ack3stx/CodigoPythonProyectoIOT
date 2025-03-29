import serial
import platform
from pymongo import MongoClient
import json
from bson import json_util
import socket


BAUDRATE = 9600


class Padre:

    def leerJson(self, archivo):
        try:
            with open(archivo) as file:
                data = json.load(file)
            return data
        except FileNotFoundError:
            return []

    def escribirJson(self, archivo, data):
        with open(archivo, 'w') as file:
            json.dump(data, file, indent=4, default=json_util.default)

    
    def conexion_Mongo(self, Coleccion):
        client = MongoClient('mongodb+srv://myAtlasDBUser:6FHvrSmI8v3kLsO0@myatlasclusteredu.c5nk4.mongodb.net/')
        db = client["iot"]
        coleccion = db[Coleccion]
        return coleccion
    
    def verificar_conexcion_internet(self):
        try:
            socket.create_connection(("www.google.com", 80))
            return True
        except OSError:
            pass
        return False
    

    