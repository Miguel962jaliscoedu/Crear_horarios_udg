# Funciones/utils.py
import datetime
import pytz

def clean_days(value):
    days_mapping = {
        "L": "Lunes", "M": "Martes", "I": "Miércoles", "J": "Jueves", "V": "Viernes", "S": "Sábado"
    }
    if isinstance(value, str):
        possible_days = list(value.strip())
        cleaned_days = [days_mapping.get(day, f"Desconocido({day})") for day in possible_days]
        return [day for day in cleaned_days if day and "Desconocido" not in day]
    return []

class Clase:
    def __init__(self, nrc, materia, dia, hora_inicio, hora_fin):
        self.nrc = nrc
        self.materia = materia
        self.dia = dia
        self.hora_inicio = hora_inicio
        self.hora_fin = hora_fin

def hay_cruce(clase1, clase2):
    if clase1.dia != clase2.dia:
        return False

    inicio1 = int(clase1.hora_inicio.replace(":", ""))
    fin1 = int(clase1.hora_fin.replace(":", ""))
    inicio2 = int(clase2.hora_inicio.replace(":", ""))
    fin2 = int(clase2.hora_fin.replace(":", ""))

    if inicio1 < fin2 and inicio2 < fin1:
        return True
    return False

def detectar_cruces(clases):
    cruces = {}
    for i in range(len(clases)):
        for j in range(i + 1, len(clases)):
            if hay_cruce(clases[i], clases[j]):
                dia = clases[i].dia
                cruces.setdefault(dia, []).append((clases[i], clases[j]))
    return cruces

def generar_mensaje_cruces(cruces):
    mensajes = []
    for dia, conflictos in cruces.items(): # Iterar sobre los items (clave-valor)
        for clase1, clase2 in conflictos:
            mensajes.append(f"- **{clase1.materia}** (NRC: {clase1.nrc}) se cruza con **{clase2.materia}** (NRC: {clase2.nrc}) el día {clase1.dia} de {clase1.hora_inicio} a {clase1.hora_fin}.")
    return mensajes

def formatear_hora(hora_str):
    """Convierte una cadena de hora a un formato consistente HH:MM."""
    try:
        hora_inicio_str, hora_fin_str = hora_str.split(" - ")
        hora_inicio = datetime.datetime.strptime(hora_inicio_str, "%I:%M %p").strftime("%H:%M")
        hora_fin = datetime.datetime.strptime(hora_fin_str, "%I:%M %p").strftime("%H:%M")
        return f"{hora_inicio} - {hora_fin}"
    except (ValueError, AttributeError):
        return None  # Manejar errores de formato

def crear_clases_desde_dataframe(df):
    clases_seleccionadas = []
    for _, row in df.iterrows():
        try:
            hora_formateada = formatear_hora(row["Hora"])
            if hora_formateada is None:
                raise ValueError(f"Formato de hora inválido: {row['Hora']}")

            hora_inicio, hora_fin = hora_formateada.split(" - ")
            clases_seleccionadas.append(Clase(row["NRC"], row["Materia"], row["Días"], hora_inicio, hora_fin))
        except (ValueError, KeyError, Exception) as e:
            raise  # Re-lanza la excepción para que se maneje en streamlit_app.py
    return clases_seleccionadas

def obtener_fecha_guadalajara():
    """Obtiene la fecha y hora actual en Guadalajara (GMT-6)."""
    guadalajara_tz = pytz.timezone("America/Mexico_City")
    fecha_actual = datetime.datetime.now()  # Obtener la fecha y hora "naive" (sin zona horaria)
    fecha_guadalajara = guadalajara_tz.localize(fecha_actual) # Localizar la fecha a Guadalajara
    return fecha_guadalajara.strftime("%d/%m/%Y %H:%M:%S")