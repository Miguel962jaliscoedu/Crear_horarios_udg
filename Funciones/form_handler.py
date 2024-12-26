# form_handler.py

import requests
from bs4 import BeautifulSoup

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
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            important_fields = ["ciclop", "cup"]  
            options_data = {}

            for field_name in important_fields:
                select_tag = soup.find("select", {"name": field_name})
                if select_tag:
                    options = []
                    for option in select_tag.find_all("option"):
                        value = option.get("value", "").strip()
                        description = option.get_text(strip=True)
                        if value and description:
                            options.append({"value": value, "description": description})
                    options_data[field_name] = options

            return options_data
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error al obtener las opciones del formulario: {e}")