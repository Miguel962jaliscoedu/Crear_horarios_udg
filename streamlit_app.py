import requests
from bs4 import BeautifulSoup
import pandas as pd
import streamlit as st
import io
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

# URLs
FORM_URL = "https://siiauescolar.siiau.udg.mx/wal/sspseca.forma_consulta"
POST_URL = "https://siiauescolar.siiau.udg.mx/wal/sspseca.consulta_oferta"

# Función para construir el cuerpo de la solicitud POST
def build_post_data(selected_options):
    return {
        "ciclop": selected_options.get("ciclop", {}).get("value", ""),
        "cup": selected_options.get("cup", {}).get("value", ""),
        "majrp": selected_options.get("majrp", {}).get("value", ""),
        "mostrarp": "",
        "crsep": "",
        "materiap": "",
        "horaip": "",
        "horafp": "",
        "edifp": "",
        "aulap": "",
        "ordenp": "0"
    }

# Función para extraer las opciones del formulario
def fetch_form_options_with_descriptions(url):
    try:
        response = requests.get(url, timeout=10)  # Se agrega un timeout
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            important_fields = ["ciclop", "cup"]  # Los campos que nos interesan
            options_data = {}

            for field_name in important_fields:
                select_tag = soup.find("select", {"name": field_name})
                if select_tag:
                    options = []
                    for option in select_tag.find_all("option"):
                        value = option.get("value", "").strip()
                        description = option.get_text(strip=True)  # Obtener solo el texto visible
                        if value and description:  # Solo incluir las opciones válidas
                            options.append({"value": value, "description": description})
                    options_data[field_name] = options

            return options_data
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener las opciones del formulario: {e}")
    return None

# Función para procesar subtablas
def process_subtable(subtable, row_data, column_name):
    rows = subtable.find_all("tr")
    sub_rows = []
    for row in rows:
        cols = [col.get_text(strip=True) for col in row.find_all("td")]
        if cols:  # Solo procesar filas no vacías
            new_row = row_data.copy()  # Copiamos la fila base
            new_row[column_name] = " | ".join(cols)  # Convertimos columnas en texto concatenado
            sub_rows.append(new_row)  # Agregar la nueva fila procesada
    return sub_rows

# Función para extraer sesiones y profesor
def extract_sessions_and_professor(cell):
    session_table = cell.find("table")
    session_rows = []
    professor_rows = []

    if session_table:
        # Procesar las filas de la tabla de sesiones
        session_rows = process_subtable(session_table, {}, "Ses/Hora/Días/Edif/Aula/Periodo")
        
        # Buscar la tabla interna de profesores
        professor_table = session_table.find_next("table")
        if professor_table:
            # Procesar las filas de la tabla de profesores
            professor_rows = process_subtable(professor_table, {}, "Ses/Profesor")

    # Convertir la información de profesores a una lista de diccionarios legible
    professor_info = [
        {"Ses/Profesor": row.get("Ses/Profesor", "")}
        for row in professor_rows
    ] if professor_rows else []

    return session_rows, professor_info

# Función para extraer datos de la tabla principal
def extract_table_data(soup):
    table = soup.find("table", {"border": "1"})
    rows = []

    for tr in table.find_all("tr")[2:]:  # Saltar los encabezados
        cells = tr.find_all("td")
        if len(cells) < 8:
            continue  # Ignorar filas incompletas

        # Datos base de la fila
        base_row = {
            "NRC": cells[0].get_text(strip=True),
            "Clave": cells[1].get_text(strip=True),
            "Materia": cells[2].get_text(strip=True),
            "Sec": cells[3].get_text(strip=True),
            "CR": cells[4].get_text(strip=True),
            "CUP": cells[5].get_text(strip=True),
            "DIS": cells[6].get_text(strip=True),
        }

        # Procesar subtablas
        session_cell = cells[7]
        session_rows, professor_info = extract_sessions_and_professor(session_cell)

        # Crear filas para cada sesión
        for session_row in session_rows:
            new_row = base_row.copy()

            # Dividir "Ses/Hora/Días/Edif/Aula/Periodo" en columnas
            session_parts = session_row.get("Ses/Hora/Días/Edif/Aula/Periodo", "").split(" | ")
            new_row["Sesión"] = session_parts[0] if len(session_parts) > 0 else ""
            new_row["Hora"] = session_parts[1] if len(session_parts) > 1 else ""
            new_row["Días"] = session_parts[2] if len(session_parts) > 2 else ""
            new_row["Edificio"] = session_parts[3] if len(session_parts) > 3 else ""
            new_row["Aula"] = session_parts[4] if len(session_parts) > 4 else ""
            new_row["Periodo"] = session_parts[5] if len(session_parts) > 5 else ""

            # Agregar "Profesor" como texto concatenado
            new_row["Profesor"] = ", ".join(
                prof.get("Ses/Profesor", "") for prof in professor_info
            ) if professor_info else ""

            rows.append(new_row)

    return rows

# Función para realizar la solicitud POST y extraer datos
def fetch_table_data(post_url, post_data):
    try:
        response = requests.post(post_url, data=post_data, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            rows = extract_table_data(soup)
            return pd.DataFrame(rows)
    except requests.exceptions.RequestException as e:
        st.error(f"Error al obtener los datos: {e}")
    return None


# Mapeo de días para conversión
days_mapping = {"L": "Lunes", "M": "Martes", "I": "Miércoles", "J": "Jueves", "V": "Viernes"}

def clean_days(value):
    """
    Convierte códigos de días a nombres completos (e.g., 'L' -> 'Lunes').
    """
    if isinstance(value, str):
        possible_days = value.strip().split()
        return [days_mapping.get(day, day) for day in possible_days]
    return []

def format_cell(row):
    """
    Formatea la información de cada materia, edificio y aula para mostrarse en el horario.
    """
    materia = row.get('Materia', "")
    edificio = row.get('Edificio', "")[-1] if isinstance(row.get('Edificio', ""), str) else ""
    aula = row.get('Aula', "")
    return f"{materia}\n{edificio} {aula}"


# Aplicación principal
st.title("Generador de Horarios")

# Obtener opciones del formulario
form_options = fetch_form_options_with_descriptions(FORM_URL)

if form_options:
    selected_options = {}

    for field, options in form_options.items():
        descriptions = [opt['description'] for opt in options]
        values = [opt['value'] for opt in options]

        # Mostrar un selectbox con las descripciones correspondientes
        print(f"Selecciona una opción para {field}:")
        for i, description in enumerate(descriptions):
            print(f"{i + 1}: {description}")
        
        selected_index = int(input("Selecciona el número de la opción: ")) - 1
        selected_value = values[selected_index]

        selected_options[field] = {"value": selected_value, "description": descriptions[selected_index]}

    print("Opciones seleccionadas:", selected_options)

    # Campo adicional para ingresar la carrera (majrp)
    carrera_input = st.text_input("Ingresa el valor de la carrera (majrp):")
    if carrera_input:
        selected_options["majrp"] = {"value": carrera_input}
    
    # Mostrar resultados seleccionados
    st.write("Opciones seleccionadas:")
    st.json({key: value["value"] for key, value in selected_options.items()})

    # Consultar y procesar datos
    if st.button("Consultar y generar horario"):
        if "ciclop" not in selected_options or not selected_options["ciclop"]["value"]:
            st.error("Debes seleccionar un ciclo antes de continuar.")
        else:
            post_data = build_post_data(selected_options)
            table_data = fetch_table_data(POST_URL, post_data)

            if table_data is not None and not table_data.empty:
                st.write("Datos obtenidos de la página:")
                st.dataframe(table_data)

                # Exportar a Excel
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    table_data.to_excel(writer, index=False, sheet_name="Horario")
                st.download_button(
                    label="Descargar horario en Excel",
                    data=buffer,
                    file_name="horario.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("No se pudo obtener información de la página.")
else:
    st.error("No se pudieron obtener las opciones del formulario.")

