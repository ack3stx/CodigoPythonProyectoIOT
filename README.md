# Sistema de Monitoreo con Sensores

Sistema para la captura, procesamiento y envío de datos de sensores ambientales. Permite operación sin conexión y sincronización posterior de datos.

## Características

- Lectura de datos de sensores a través de conexión serial
- Soporte para múltiples tipos de sensores (TEM, PIR, SON, GAS, LUZ)
- Operación offline con sincronización posterior
- Envío de datos a API REST
- Monitoreo de cambios en MongoDB

## Requisitos

- Python 3.6+
- PySerial
- Requests
- PyMongo

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/PythonIntegradora.git

# Instalar dependencias
pip install pyserial requests pymongo
```

## Uso

```bash
# Ejecutar el monitor para observar cambios en MongoDB
python Monitor.py

# Ejecutar la lectura de sensores
python Sensores.py
```

## Estructura

- `Padre.py`: Clase base con funciones comunes
- `Monitor.py`: Monitoreo de datos en MongoDB
- `Sensores.py`: Lectura, procesamiento y envío de datos de sensores