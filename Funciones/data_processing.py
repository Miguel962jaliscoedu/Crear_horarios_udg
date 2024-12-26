# data_processing.py

from bs4 import BeautifulSoup
import pandas as pd
import requests
from Funciones.utils import clean_days

# Función para procesar subtablas
def process_subtable(subtable, row_data, column_name):
    rows = subtable.find_all("tr")
    sub_rows = []
    for row in rows:
        cols = [col.get_text(strip=True) for col in row.find_all("td")]
        if cols:
            new_row = row_data.copy()  
            new_row[column_name] = " | ".join(cols)  
            sub_rows.append(new_row)
    return sub_rows

# Función para extraer sesiones y profesor
def extract_sessions_and_professor(cell):
    session_table = cell.find("table")
    session_rows = []
    professor_rows = []

    if session_table:
        session_rows = process_subtable(session_table, {}, "Ses/Hora/Días/Edif/Aula/Periodo")
        professor_table = session_table.find_next("table")
        if professor_table:
            professor_rows = process_subtable(professor_table, {}, "Ses/Profesor")

    professor_info = [{"Ses/Profesor": row.get("Ses/Profesor", "")} for row in professor_rows] if professor_rows else []
    return session_rows, professor_info

# Función para extraer datos de la tabla principal
def extract_table_data(soup):
    table = soup.find("table", {"border": "1"})
    rows = []

    for tr in table.find_all("tr")[2:]:  
        try:
            cells = tr.find_all("td")
            if len(cells) < 8:
                continue  

            base_row = {
                "NRC": cells[0].get_text(strip=True),
                "Clave": cells[1].get_text(strip=True),
                "Materia": cells[2].get_text(strip=True),
                "Sec": cells[3].get_text(strip=True),
                "CR": cells[4].get_text(strip=True),
                "CUP": cells[5].get_text(strip=True),
                "DIS": cells[6].get_text(strip=True),
            }

            session_cell = cells[7]
            session_rows, professor_info = extract_sessions_and_professor(session_cell)

            for session_row in session_rows:
                new_row = base_row.copy()

                session_parts = session_row.get("Ses/Hora/Días/Edif/Aula/Periodo", "").split(" | ")
                new_row["Sesión"] = session_parts[0] if len(session_parts) > 0 else ""
                new_row["Hora"] = session_parts[1] if len(session_parts) > 1 else ""
                new_row["Días"] = session_parts[2] if len(session_parts) > 2 else ""
                new_row["Edificio"] = session_parts[3] if len(session_parts) > 3 else ""
                new_row["Aula"] = session_parts[4] if len(session_parts) > 4 else ""
                new_row["Periodo"] = session_parts[5] if len(session_parts) > 5 else ""

                new_row["Profesor"] = ", ".join(prof.get("Ses/Profesor", "") for prof in professor_info) if professor_info else ""

                rows.append(new_row)
        except Exception as e:
            raise Exception(f"Error procesando una fila de la tabla: {e}")

    return rows

def fetch_table_data(post_url, post_data):
    try:
        response = requests.post(post_url, data=post_data, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            rows = extract_table_data(soup)  # Asegúrate de que la función extract_table_data esté definida
            return pd.DataFrame(rows)
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener los datos: {e}")
    return None

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