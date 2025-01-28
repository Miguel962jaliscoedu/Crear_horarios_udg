# data_processing.py

from bs4 import BeautifulSoup
import pandas as pd
import requests
import json
import os
from Funciones.utils import clean_days

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

                profesores = [prof.get("Ses/Profesor", "") for prof in professor_info] if professor_info else []
                for profesor_completo in profesores:
                    ses_prof_parts = profesor_completo.split(" | ", 1)
                    ses = ses_prof_parts[0] if len(ses_prof_parts) > 0 else ""
                    profesor = ses_prof_parts[1] if len(ses_prof_parts) > 1 else ""

                    new_row["Ses"] = ses
                    new_row["Profesor"] = profesor
                    rows.append(new_row)

        except Exception as e:
            raise Exception(f"Error procesando una fila de la tabla: {e}")

    return rows

def fetch_table_data(post_url, post_data):
    try:
        response = requests.post(post_url, data=post_data, timeout=10)
        response.raise_for_status()  # Lanza una excepción para códigos de estado HTTP erróneos (4xx o 5xx)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = extract_table_data(soup)
        return pd.DataFrame(rows)
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener los datos: {e}")
        return None

def filter_relevant_columns(df):
    relevant_columns = ["NRC", "Materia", "Sec", "Sesión", "Hora", "Días", "Edificio", "Aula", "Profesor"]
    return df[relevant_columns]

def parse_time_range(time_string):
    try:
        start, end = time_string.split("-")
        start_dt = pd.to_datetime(start.strip(), format="%H%M")
        end_dt = pd.to_datetime(end.strip(), format="%H%M")
        start_12h = start_dt.strftime("%I:%M %p")
        end_12h = end_dt.strftime("%I:%M %p")
        return f"{start_12h} - {end_12h}"
    except (ValueError, AttributeError): #Capturar el error si time_string es None
        return time_string

def process_data_from_web(df, nombre_archivo="datos.json"):
    """
    Procesa los datos de la web, los guarda en un archivo JSON y devuelve un DataFrame.
    """
    try:
        df = filter_relevant_columns(df)
        df.columns = ["NRC", "Materia", "Sección", "Sesión", "Hora", "Días", "Edificio", "Aula", "Profesor"]
        df.loc[:, "Días"] = df["Días"].apply(clean_days)
        df.loc[:, "Hora"] = df["Hora"].apply(parse_time_range)
        expanded_data = df.explode("Días").reset_index(drop=True)

        processed_data = expanded_data.to_dict(orient='records')

        with open(nombre_archivo, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=4)

        df_from_json = pd.read_json(nombre_archivo, encoding='utf-8')
        return df_from_json

    except (KeyError, TypeError, AttributeError, ValueError) as e:
        print(f"Error al procesar los datos: {e}")
        return pd.DataFrame()
    except Exception as e:
      print(f"Un error inesperado a ocurrido: {e}")
      return pd.DataFrame()

def cargar_datos_desde_json(nombre_archivo="datos.json"):
    """
    Carga los datos desde un archivo JSON y devuelve un diccionario con toda la información.
    """
    try:
        if os.path.exists(nombre_archivo):
            with open(nombre_archivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data #Devuelve el diccionario completo

        else:
            print(f"Archivo {nombre_archivo} no encontrado. Se devolverá un diccionario vacío.")
            return {} #Devuelve un diccionario vacio
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON: {e}")
        return {}
    except FileNotFoundError:
        print(f"Archivo {nombre_archivo} no encontrado. Se devolverá un diccionario vacío.")
        return {}
    except Exception as e:
        print(f"Error al cargar datos desde JSON: {e}")
        return {}

def guardar_datos_local(data):
    try:
        with open('datos.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error al guardar datos localmente: {e}")