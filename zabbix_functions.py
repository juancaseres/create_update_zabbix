import requests
import json
import unicodedata

MAPA_LOCALIDADES = {
    "Los teques": "LTQ OSS",
    "Maracay": "MCY OSS",
    "Valencia": "VAL OSS",
    "Barquisimeto": "BTO OSS",
    "Caracas (Red propia)": "CCS OSS",
    "Caracas (Red alquilada)": "CCS OSS",
    "Barcelona": "BCN OSS"
}

# Zabbix API URL y credenciales
URL = "http://10.177.255.28/zabbix/api_jsonrpc.php"
USERNAME = "Monitoreo"
PASSWORD = "MonitoreS1mpl3##"

# Función para iniciar sesión en Zabbix
def login_zabbix(url, username, password):
    data = {
        "jsonrpc": "2.0",
        "method": "user.login",
        "params": {"username": username, "password": password},
        "id": 1,
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()

    if "result" in response_json and "error" not in response_json:
        return response_json["result"]
    else:
        raise Exception(f"Error al iniciar sesión: {response_json}")

# Función para extraer todos los hosts registrados en Zabbix con sus hostids
def get_hosts(url, token):
    """
    Obtiene una lista de todos los hosts y sus IDs, nombres y direcciones IP.
    """
    data = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "name"],  # Obtener hostid y name
        },
        "auth": token,
        "id": 2
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()
    if "result" in response_json:
        return response_json["result"]
    else:
        raise Exception(f"Error al obtener los hosts: {response_json}")

# Función para extraer los grupos de hosts creados en Zabbix con sus respectivos IDs 
def get_host_groups(url, token):
    """
    Obtiene una lista de todos los grupos de hosts y sus IDs.
    """
    data = {
        "jsonrpc": "2.0",
        "method": "hostgroup.get",
        "params": {},
        "auth": token,
        "id": 2
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()
    if "result" in response_json:
        return response_json["result"]
    else:
        raise Exception(f"Error al obtener los grupos de hosts: {response_json}")
    
# Función para mapear los grupos de la conexión cliente con los IDs registrados en Zabbix
def obtener_ids(localidad, olt, feeder, group_ids_dict):
    
    group_loc = {
        "Los teques": "Clientes FTTH POC (Los Teques)",
        "Maracay": "Clientes FTTH POC (Maracay)",
        "Valencia": "Clientes FTTH POC (Valencia)",
        "Barquisimeto": "Clientes FTTH POC (Barquisimeto)",
        "Caracas (Red propia)": "Clientes FTTH POC (Caracas) - Red propia",
        "Caracas (Red alquilada)": "Clientes FTTH POC (Caracas) - Red alquilada",
        "Barcelona": "Clientes FTTH POC (Barcelona)"
    }

    if localidad == "Caracas (Red propia)":
        ids = ["35"]
    else:
        ids = ["35","34"]

    if group_loc.get(localidad) in group_ids_dict:
        ids.append(str(group_ids_dict[group_loc.get(localidad)]))
    else:
        raise ValueError(f"Localidad: '{group_loc.get(localidad)}' no definido en Zabbix")

    if olt not in ["No aplica","N/A",""]:
        if olt in group_ids_dict:
            ids.append(str(group_ids_dict[olt]))
        else:
            raise ValueError(f"OLT: '{olt}' no definida en Zabbix")
        

    if feeder not in ["No aplica","N/A",""]:
        if feeder in group_ids_dict:
            ids.append(str(group_ids_dict[feeder]))
        else:
            raise ValueError(f"Feeder '{feeder}' no encontrado en group_ids_dict")

    ids.append("90")
    return ids

# Función para eliminar acentos y caracteres no reconocidos por Zabbix
def quitar_acentos(cadena):
    if not isinstance(cadena, str):
        return cadena
    cadena = unicodedata.normalize("NFKD", cadena)
    return "".join(c for c in cadena if not unicodedata.combining(c)).replace("ñ", "n").replace("Ñ", "N")