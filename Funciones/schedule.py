# schedule.py

import pandas as pd
import matplotlib.pyplot as plt
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
def create_schedule_image(schedule):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    table = Table(ax, bbox=[0, 0, 1, 1])

    for i, col in enumerate(schedule.columns):
        table.add_cell(0, i, width=1.0 / len(schedule.columns), height=0.1, text=col, loc='center', facecolor='lightgrey')

    for i, row in enumerate(schedule.values):
        for j, val in enumerate(row):
            table.add_cell(i + 1, j, width=1.0 / len(schedule.columns), height=0.1, text=str(val), loc='center')

    ax.add_table(table)

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    
    return buf