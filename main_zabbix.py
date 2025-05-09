import os
import re
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, flash
import pandas as pd
from zabbix_functions import login_zabbix, get_hosts, URL, USERNAME, PASSWORD
from create_update import process_excel, process_update_zabbix, UPDATABLE_FIELDS

# Configuración de Flask
app = Flask(__name__)
app.secret_key = "secret_key"
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["RESULTS_FOLDER"] = RESULTS_FOLDER


@app.route("/crear_hosts", methods=["GET", "POST"])
def upload_file_create():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No se seleccionó un archivo.")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("No se seleccionó un archivo.")
            return redirect(request.url)
        if file:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)
            resultados, report_filename = process_excel(file_path)
            success = [r for r in resultados if "Host creado exitosamente" in r]
            return render_template("resultados_create.html", resultados=resultados, success=success, report_filename=report_filename)

    return render_template("upload_create.html")

@app.route("/download-hosts")
def descargar_hosts():
    try:
        auth_token = login_zabbix(URL, USERNAME, PASSWORD)
        hosts = get_hosts(URL, auth_token)

        data = []
        for host in hosts:
            hostid = host["hostid"]
            name = host["name"]

            serial_onu_pattern = r"(TPLG\w{8}|FHTT\w{8}|ALCL\w{8})"
            customer_id_pattern = r"(ID\d{6,9})"

            serial_onu_match = re.search(serial_onu_pattern, name)
            customer_id_match = re.search(customer_id_pattern, name)

            serial_onu = serial_onu_match.group(0) if serial_onu_match else "N/A"
            customer_id_full = customer_id_match.group(0) if customer_id_match else "N/A"

            customer_id = customer_id_full[2:] if customer_id_full != "N/A" else "N/A"

            nombre = name.split(serial_onu)[0].strip() if serial_onu != "N/A" else name

            data.append([customer_id, hostid, nombre, serial_onu])

        df = pd.DataFrame(data, columns=["customer id", "hostid", "nombre", "serial onu"])

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hosts_zabbix_{timestamp}.xlsx"
        file_path = os.path.join(app.config["RESULTS_FOLDER"], filename)
        df.to_excel(file_path, index=False)

        return send_from_directory(directory=app.config["RESULTS_FOLDER"], path=filename, as_attachment=True)

    except Exception as e:
        return f"Error al generar el archivo: {str(e)}", 500

@app.route("/actualizar_hosts", methods=["GET", "POST"])
def upload_file_update():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No se seleccionó un archivo.")
            return redirect(request.url)
        
        file = request.files["file"]
        if file.filename == "":
            flash("No se seleccionó un archivo.")
            return redirect(request.url)
        
        if file:
            # Obtener campos seleccionados del formulario
            selected_fields = request.form.getlist('fields')
            if not selected_fields:
                flash("No se seleccionaron campos para actualizar.")
                return redirect(request.url)
            
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(file_path)
            
            try:
                process_result = process_update_zabbix(file_path, selected_fields)
                if "error" in process_result:
                    flash(process_result["error"])
                    return redirect(request.url)
                
                return render_template(
                    "resultados_update.html",
                    resultados=process_result["resultados"],
                    report_filename=process_result["report_filename"]
                )
            except Exception as e:
                flash(f"Error al procesar el archivo: {str(e)}")
                return redirect(request.url)
    
    return render_template("upload_update.html", fields=UPDATABLE_FIELDS)

@app.route("/descargar/<filename>")
def descargar_archivo(filename):
    
    return send_from_directory(
        directory=app.config["RESULTS_FOLDER"],
        path=filename,
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(debug=False)

