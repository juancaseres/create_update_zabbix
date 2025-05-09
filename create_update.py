import os
import requests
import json
import pandas as pd
import datetime
from zabbix_functions import login_zabbix, get_host_groups, obtener_ids, quitar_acentos, MAPA_LOCALIDADES, URL, USERNAME, PASSWORD

""" FUNCIONES PARA CREAR HOSTS EN ZABBIX """

# Función para crear conexión en Zabbix (Estructura JSON)
def create_host(url, auth_token, hostname, hostip, mac_add, groupids, contact, 
                address, lat, lon, notes, onu_sn, olt, slot, pon, city):
    data = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": hostname,
            "description": "NAP: " + notes,
            "visible": 1,
            "groups": [{"groupid": groupid} for groupid in groupids],
            "templates": [{"templateid": "10566"}],
            "interfaces": [
                {"type": 1, "main": 1, "useip": 1, "ip": hostip, "dns": "", "port": "10050"}
            ],
            "inventory_mode": 0,
            "inventory": {
                "macaddress_a": mac_add,
                "contact": contact,
                "location": address,
                "location_lat": lat,
                "location_lon": lon,
                "notes": "NAP: " + notes,
                "serialno_a": onu_sn, 
                "site_address_a": olt,
                "site_address_b": slot,
                "site_address_c": pon,
                "site_city": city,
            },
        },
        "auth": auth_token,
        "id": 2,
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()

    if "error" in response_json:
        raise Exception(f"Error al crear el host: {response_json['error']}")
    else:
        return f"Host creado exitosamente. Host ID: {response_json['result']['hostids'][0]}"
    
# Función principal que permite extraer una lista con los resultados de la creación de las conexiones clientes en Zabbix y sus posibles errores
def process_excel(file_path):


    columns = [
        "Nombre", "Customer", "Localidad", "OLT", "Feeder", "Slot", "PON",
        "NAP", "ONT/ONU", "Dirección IP", "MAC address", "Ubicación de la caja NAP (Coordenadas)", 
        "Dirección", "Numero de telefono"
    ]

    df = pd.read_excel(file_path, usecols=columns, dtype={'Slot': str,'PON': str})
    df = df.fillna("N/A").astype(str)

    df["Nombre"] = df["Nombre"].apply(quitar_acentos).str.strip()
    df["Customer"] = df["Customer"].str.strip()
    df["ONT/ONU"] = df["ONT/ONU"].str.strip()
    df["Localidad"] = df["Localidad"].str.strip()

    df["hostname"] = df.apply(
        lambda row: f"{row['Nombre']} {'PDFN' if row['ONT/ONU'] in ['', 'N/A'] else row['ONT/ONU']} ID{row['Customer']} {MAPA_LOCALIDADES.get(row['Localidad'], row['Localidad'])}",
        axis=1
    )

    df["OLT"] = df["OLT"].str.strip()
    df["Slot"] = df["Slot"].str.strip()
    df["PON"] = df["PON"].str.strip()

    client_data_dict = df.to_dict(orient="records")

    try:
        auth_token = login_zabbix(URL, USERNAME, PASSWORD)
    except Exception as e:
        return f"Error al iniciar sesión en Zabbix: {e}"
    
    host_groups = get_host_groups(URL, auth_token)
    zabbix_group_ids = {group['name'].strip(): group['groupid'].strip() for group in host_groups}

    resultados = []
    failures = []
    datos_con_hostid = []
    for row in client_data_dict:
        try:
            hostname = row["hostname"]
            groupids = obtener_ids(row["Localidad"], row["OLT"], row["Feeder"], zabbix_group_ids)
            
            coordenadas = row["Ubicación de la caja NAP (Coordenadas)"].strip()
            if coordenadas and "," in coordenadas:
                latitud, longitud = map(str.strip, coordenadas.split(","))
            else:
                latitud = ""
                longitud = ""

                """ if "," not in coordenadas:
                    raise ValueError("Formato de coordenadas inválido: no se encontró una coma.") """
            
            response = create_host(
                URL, auth_token, hostname, row["Dirección IP"].strip(), row["MAC address"], groupids, 
                row["Numero de telefono"], row["Dirección"].strip(), latitud, longitud, row["NAP"],
                row["ONT/ONU"], row["OLT"], row["Slot"], row["PON"], row["Localidad"]
            )
            host_id = response.split("Host ID: ")[-1]  # Extraer hostid
            row["hostid"] = host_id
            datos_con_hostid.append(row)
            resultados.append(f"{hostname} → {response}")
        except Exception as e:
            resultados.append(f"Error al crear host {row['hostname']}: {e}")

    print(resultados)

    if resultados:
        # Guardar Excel con hostids
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"created_hosts_{timestamp}.xlsx"
        file_path_result = os.path.join(RESULTS_FOLDER, filename)

        df_result = pd.DataFrame(datos_con_hostid)

        if not df_result.empty and 'hostid' in df_result.columns:
            cols = ['hostid'] + [c for c in df_result.columns if c != 'hostid']
            df_result = df_result[cols]

        df_result.to_excel(file_path_result, index=False)
        return resultados, filename
    else:
        return resultados, None


""" FUNCIONES PARA ACTUALIZAR HOSTS EN ZABBIX """


# Campos actualizables con sus etiquetas para el frontend
UPDATABLE_FIELDS = {
    "name": "Hostname",
    "description": "NAP",
    "inventory": {
        "alias": "hostid",
        "serialno_a": "ONT/ONU",
        "macaddress_a": "MAC address",
        "contact": "Numero de telefono",
        "location": "Direccion",
        "location_lat": "Latitud",
        "location_lon": "Longitud",
        "notes": "NAP", 
        "site_address_a": "OLT",
        "site_address_b": "Slot",
        "site_address_c": "PON",
        "site_city": "Localidad"
    }
}

RESULTS_FOLDER = "results"

def get_friendly_to_technical():
    friendly_to_technical = {}
    # Agregar campo especial 'description'
    if "description" in UPDATABLE_FIELDS:
        friendly_to_technical[UPDATABLE_FIELDS["description"]] = "description"
    # Agregar campos de inventario
    for tech, friendly in UPDATABLE_FIELDS["inventory"].items():
        friendly_to_technical[friendly] = tech
    return friendly_to_technical

def update_host(url, auth_token, hostid, selected_fields, row_data, group_ids_dict):
    params = {
        "hostid": hostid,
        "inventory_mode": 0,
    }

    friendly_to_tech = get_friendly_to_technical()

    nap_value = row_data.get("NAP", "")
    if "description" in selected_fields:
        params["description"] = f"NAP: {nap_value}"

    if "Hostname" in selected_fields:
        nombre = quitar_acentos(str(row_data.get("Nombre", "")).strip())
        customer = str(row_data.get("Customer", "")).strip()
        ont = str(row_data.get("ONT/ONU", "")).strip()
        localidad = str(row_data.get("Localidad", "")).strip()
        localidad_abrev = MAPA_LOCALIDADES.get(localidad, localidad)
        hostname = f"{nombre} {ont} ID{customer} {localidad_abrev}"
        params["host"] = hostname
        params["name"] = hostname

    if "modify_groups" in selected_fields:
        try:
            localidad = row_data.get("Localidad", "").strip()
            olt = row_data.get("OLT", "").strip()
            feeder = row_data.get("Feeder", "N/A").strip()
            nuevos_group_ids = obtener_ids(localidad, olt, feeder, group_ids_dict)
            params["groups"] = [{"groupid": gid} for gid in nuevos_group_ids]
        except Exception as e:
            return {
                "status": "error",
                "hostid": hostid,
                "message": f"Error en grupos: {str(e)}"
            }

    inventory_fields = {}

    for friendly_field in selected_fields:
        tech_field = friendly_to_tech.get(friendly_field)
        if not tech_field:
            continue

        if tech_field == "notes":
            inventory_fields[tech_field] = f"NAP: {nap_value}"
        elif friendly_field == "Latitud" or friendly_field == "Longitud":
            coordenadas = row_data.get("Ubicación de la caja NAP (Coordenadas)", "").strip()
            if coordenadas and "," in coordenadas:
                latitud, longitud = map(str.strip, coordenadas.split(",", 1))
                if friendly_field == "Latitud" and latitud:
                    inventory_fields["location_lat"] = latitud
                elif friendly_field == "Longitud" and longitud:
                    inventory_fields["location_lon"] = longitud
        elif friendly_field in row_data and pd.notna(row_data[friendly_field]):
            inventory_fields[tech_field] = row_data[friendly_field]

    if inventory_fields:
        params["inventory"] = inventory_fields

    data = {
        "jsonrpc": "2.0",
        "method": "host.update",
        "params": params,
        "auth": auth_token,
        "id": 2,
    }

    print("JSON que se enviará a Zabbix:", json.dumps(data, indent=2))

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    response_json = response.json()

    if "error" in response_json:
        raise Exception(f"Error al actualizar el host: {response_json['error']}")
    else:
        return {
            "status": "success",
            "hostid": hostid,
            "message": "Host actualizado exitosamente"
        }

def process_update_zabbix(file_path, selected_fields):
    try:
        auth_token = login_zabbix(URL, USERNAME, PASSWORD)
    except Exception as e:
        return {"error": f"Error al iniciar sesión en Zabbix: {e}"}

    df_update = pd.read_excel(file_path, dtype={'hostid': str, 'Slot': str,'PON': str})

    required_for_hostname = ["Nombre", "Customer", "ONT/ONU", "Localidad"]
    if "Hostname" in selected_fields:
        df_columns = df_update.columns.tolist()
        missing_cols = [col for col in required_for_hostname if col not in df_columns]
        if missing_cols:
            return {"error": f"Faltan las siguientes columnas requeridas para construir el hostname: {', '.join(missing_cols)}"}

    resultados = []
    report_data = []
    
    group_list = get_host_groups(URL, auth_token)
    group_ids_dict = {g["name"]: g["groupid"] for g in group_list}


    for index, row in df_update.iterrows():
        if pd.notna(row['hostid']):
            row_data = row.to_dict()
            try:
                result = update_host(URL, auth_token, row['hostid'], selected_fields, row_data, group_ids_dict)
                resultados.append(f"Host {row['hostid']} actualizado correctamente")
                report_data.append({
                    "hostid": row['hostid'],
                    "status": "success",
                    "message": "Actualización exitosa",
                    "updated_fields": ", ".join(selected_fields)
                })

            except Exception as e:
                resultados.append(f"Error al actualizar host {row['hostid']}: {str(e)}")
                report_data.append({
                    "hostid": row['hostid'],
                    "status": "error",
                    "message": str(e),
                    "updated_fields": ""
                })

        else:
            msg = f"Host ID no encontrado para fila {index+1}"
            resultados.append(msg)
            report_data.append({
                "hostid": None,
                "status": "error",
                "message": "Falta hostid en la fila",
                "updated_fields": ""
            })

    # Generar reporte Excel
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    report_filename = f"zabbix_update_report_{timestamp}.xlsx"
    report_path = os.path.join(RESULTS_FOLDER, report_filename)

    pd.DataFrame(report_data).to_excel(report_path, index=False)
    
    return {
        "resultados": resultados,
        "report_path": report_path,
        "report_filename": report_filename
    }

