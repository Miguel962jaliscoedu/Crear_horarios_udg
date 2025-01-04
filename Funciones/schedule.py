# schedule.py

import pandas as pd
import matplotlib.pyplot as plt
import textwrap
from matplotlib.table import Table
from io import BytesIO

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
def wrap_text(text, width):
    """Envuelve el texto a un ancho dado."""
    return textwrap.fill(text, width)

def create_schedule_image(schedule):
    """
    Crea una imagen del horario.

    Args:
        schedule (pandas.DataFrame): Los datos del horario.

    Returns:
        BytesIO: Un flujo de bytes que contiene los datos de la imagen PNG.
    """

    num_rows = len(schedule)
    fig_height = max(6, min(20, num_rows * 0.7))  # Ajusta la altura de la figura para evitar que sea excesivamente alta
    # El valor 0.7 se usa para ajustar la altura de cada fila.

    fig, ax = plt.subplots(figsize=(10, fig_height))
    ax.axis('off')  # Desactiva los ejes

    table = Table(ax, bbox=[0, 0, 1, 1])  # Crea la tabla

    num_cols = len(schedule.columns)
    cell_width = 1.0 / num_cols  # Calcula el ancho de cada celda
    cell_height = 1.0 / (num_rows + 1)  # Calcula la altura de cada celda (+1 para los encabezados)

    font_size = int(fig_height * 72 / (num_rows + 3))  # Calcula el tamaño de la fuente dinámicamente

    # Añade las celdas de encabezado
    for i, col in enumerate(schedule.columns):
        table.add_cell(0, i, width=cell_width, height=cell_height, text=col,
                       loc='center', facecolor='lightgrey', edgecolor='black',
                       textprops={'ha': 'center', 'va': 'center'})  # Usa textprops para centrar el texto

    # Añade las celdas de datos (con ajuste de texto opcional)
    for i, row in enumerate(schedule.values):
        for j, val in enumerate(row):
            wrapped_text = wrap_text(str(val), 15)  # Envuelve el texto si es necesario (ajusta el ancho si es necesario)
            table.add_cell(i + 1, j, width=cell_width, height=cell_height, text=wrapped_text,
                           loc='center', edgecolor='black', cellColours=['white'],
                           textprops={'fontsize': font_size, 'ha': 'center', 'va': 'center'})  # Usa textprops para el tamaño de fuente y centrado

    ax.add_table(table)  # Añade la tabla al eje

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')  # Guarda la figura en un buffer de bytes
    buf.seek(0)  # Regresa al inicio del buffer
    return buf