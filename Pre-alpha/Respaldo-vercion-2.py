import requests
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
import io
from bs4 import BeautifulSoup
from matplotlib.table import Table
from io import BytesIO

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

# Función para extraer opciones del formulario con descripciones
def fetch_form_options_with_descriptions(url):
    try:
        response = requests.get(url, timeout=10)  # Agregar timeout
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            important_fields = ["ciclop", "cup"]  # Solo los campos necesarios
            options_data = {}

            for field_name in important_fields:
                select_tag = soup.find("select", {"name": field_name})
                if select_tag:
                    options = []
                    for option in select_tag.find_all("option"):
                        value = option.get("value", "").strip()
                        description = option.get_text(strip=True)  # Extraer solo el texto visible de la opción
                        if value and description:  # Solo incluir valores y descripciones no vacíos
                            options.append({"value": value, "description": description})
                    options_data[field_name] = options

            return options_data
    except requests.exceptions.RequestException as e:
        st.error(f"Error al obtener las opciones del formulario: {e}")
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
        try:
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
        except Exception as e:
            st.error(f"Error procesando una fila de la tabla: {e}")

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

# Modificar días a nombres válidos
days_mapping = {
    "L": "Lunes", "M": "Martes", "I": "Miércoles", "J": "Jueves", "V": "Viernes", "S": "Sabado"
}

# Nueva función para limpiar los días
def clean_days(value):
    if isinstance(value, str):
        # Separar por espacios y mapear días válidos
        possible_days = list(value.strip())  # Convertir cada carácter a lista
        cleaned_days = [days_mapping.get(day, f"Desconocido({day})") for day in possible_days]
        return [day for day in cleaned_days if day and "Desconocido" not in day]
    return []

def filter_relevant_columns(df):
    # Lista de columnas que necesitamos
    relevant_columns = ["NRC", "Materia", "Sec", "Sesión", "Hora", "Días", "Edificio", "Aula", "Profesor"]
    return df[relevant_columns]

# Función para procesar los datos obtenidos de la web
def process_data_from_web(df):
    df = filter_relevant_columns(df)
    df.columns = ["NRC", "Materia", "Sección", "Sesión", "Hora", "Días", "Edificio", "Aula", "Profesor"]

    def parse_time_range(time_string):
        try:
            start, end = time_string.split("-")
            start_dt = pd.to_datetime(start.strip(), format="%H%M")
            end_dt = pd.to_datetime(end.strip(), format="%H%M")
            start_12h = start_dt.strftime("%I:%M %p")
            end_12h = end_dt.strftime("%I:%M %p")
            return f"{start_12h} - {end_12h}"
        except Exception:
            return time_string

    df["Días"] = df["Días"].apply(clean_days)
    df["Hora"] = df["Hora"].apply(parse_time_range)
    expanded_data = df.explode("Días").reset_index(drop=True)
    return expanded_data

# Función para crear la tabla del horario
def create_schedule_sheet(expanded_data):
    hours_list = [
        "07:00 AM - 07:59 AM", "08:00 AM - 08:59 AM", "09:00 AM - 09:59 AM", "10:00 AM - 10:59 AM",
        "11:00 AM - 11:59 AM", "12:00 PM - 12:59 PM", "01:00 PM - 01:59 PM", "02:00 PM - 02:59 PM",
        "03:00 PM - 03:59 PM", "04:00 PM - 04:59 PM", "05:00 PM - 05:59 PM", "06:00 PM - 06:59 PM",
        "07:00 PM - 07:59 PM", "08:00 PM - 08:59 PM"
    ]
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sabado"]
    schedule = pd.DataFrame(columns=["Hora"] + days)
    schedule["Hora"] = hours_list

    for index, row in expanded_data.iterrows():
        for hour_range in hours_list:
            start_hour, end_hour = [pd.to_datetime(hr, format="%I:%M %p") for hr in hour_range.split(" - ")]
            class_start, class_end = [pd.to_datetime(hr, format="%I:%M %p") for hr in row["Hora"].split(" - ")]
            if start_hour < class_end and class_start < end_hour:
                day_col = row["Días"]
                content = f"{row['Materia']} ({row['Aula']})\n{row['Profesor']}"
                if pd.notna(schedule.loc[schedule["Hora"] == hour_range, day_col].values[0]):
                    schedule.loc[schedule["Hora"] == hour_range, day_col] += "\n" + content
                else:
                    schedule.loc[schedule["Hora"] == hour_range, day_col] = content
    return schedule

# Función para convertir la tabla en imagen
def create_schedule_image(schedule):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    table = Table(ax, bbox=[0, 0, 1, 1])

    # Agregar las celdas de la tabla
    for i, col in enumerate(schedule.columns):
        table.add_cell(0, i, width=1.0 / len(schedule.columns), height=0.1, text=col, loc='center', facecolor='lightgrey')

    # Agregar filas
    for i, row in enumerate(schedule.values):
        for j, val in enumerate(row):
            table.add_cell(i + 1, j, width=1.0 / len(schedule.columns), height=0.1, text=str(val), loc='center')

    ax.add_table(table)

    # Guardar la imagen en un buffer
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    return buf

# Aplicación principal
st.title("Generador de Horarios")

# Obtener opciones del formulario
form_options = fetch_form_options_with_descriptions(FORM_URL)

if form_options:
    selected_options = {}

    # Iterar sobre los campos (como ciclop, cup, etc.)
    for field, options in form_options.items():
        # Extraemos solo las descripciones para mostrar
        descriptions = [opt['description'] for opt in options]
        values = [opt['value'] for opt in options]

        # Mostrar el selectbox con las descripciones correspondientes al campo
        selected_description = st.selectbox(f"Selecciona una opción para {field}:", descriptions)

        if selected_description:
            # Obtener el índice de la descripción seleccionada
            index = descriptions.index(selected_description)
            selected_value = values[index]  # Obtener el valor correspondiente

            # Guardar el valor seleccionado en el diccionario de opciones
            selected_options[field] = {"value": selected_value}

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

                # Procesar los datos de la web
                expanded_data = process_data_from_web(table_data)

                # Inicializar el estado de sesión para los NRC seleccionados
                if "selected_nrcs" not in st.session_state:
                    st.session_state["selected_nrcs"] = []

                # Mostrar la multiselección para los NRC
                selected_nrcs = st.multiselect(
                    "Selecciona los NRC de las materias que deseas incluir:",
                    options=expanded_data["NRC"].unique().tolist(),
                    default=st.session_state["selected_nrcs"],  # Usar los valores almacenados
                )

                # Actualizar el estado de sesión solo si hay cambios
                if selected_nrcs != st.session_state["selected_nrcs"]:
                    st.session_state["selected_nrcs"] = selected_nrcs

                # Filtrar los datos por los NRC seleccionados
                filtered_data = expanded_data[expanded_data["NRC"].isin(st.session_state["selected_nrcs"])]

                # Crear el horario si hay datos filtrados
                if not filtered_data.empty:
                    schedule = create_schedule_sheet(filtered_data)

                    # Mostrar la tabla del horario
                    st.write("Horario generado:")
                    st.dataframe(schedule)

                    # Crear la imagen del horario
                    schedule_image_buf = create_schedule_image(schedule)

                    # Mostrar la imagen
                    st.image(schedule_image_buf)

                    # Opción para descargar la imagen
                    st.download_button(
                        label="Descargar horario como imagen",
                        data=schedule_image_buf,
                        file_name="horario.png",
                        mime="image/png",
                    )
                else:
                    st.warning("No se pudo generar el horario con los NRC seleccionados.")