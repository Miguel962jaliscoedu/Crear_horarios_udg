# schedule.py

import io
import pandas as pd
from reportlab.lib import colors, pagesizes, units
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph

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

                materia = row.get("Materia", "Información no disponible")
                edificio = row.get("Edificio", "")
                letra_edificio = edificio[-1] if edificio else ""
                aula = row.get("Aula", "Información no disponible")
                profesor = row.get("Profesor", "Información no disponible")

                content = f"{materia}\n{letra_edificio} - {aula}\n{profesor}"

                if pd.notna(schedule.loc[schedule["Hora"] == hour_range, day_col].values[0]):
                    schedule.loc[schedule["Hora"] == hour_range, day_col] += "\n" + content
                else:
                    schedule.loc[schedule["Hora"] == hour_range, day_col] = content
    return schedule

def create_schedule_pdf(schedule):
    buffer = io.BytesIO()
    stylesheet = getSampleStyleSheet()

    data_with_paragraphs = []
    for row in schedule.values.tolist():
        new_row = []
        for cell_content in row:
            if pd.isna(cell_content):
                new_row.append("")
            elif isinstance(cell_content, str):
                p_style = ParagraphStyle(name='Normal',
                                         fontName='Helvetica',
                                         fontSize=8,
                                         alignment=1,
                                         leading=10,
                                         wordWrap='CJK')
                p = Paragraph(cell_content, p_style)
                new_row.append(p)
            else:
                new_row.append(cell_content)
        data_with_paragraphs.append(new_row)

    data_with_paragraphs.insert(0, schedule.columns.tolist())

    # Márgenes reducidos (ajusta estos valores según necesites)
    margin_left = 0.2 * units.inch
    margin_right = 0.2 * units.inch
    margin_top = 0.2 * units.inch
    margin_bottom = 0.2 * units.inch

    available_width = landscape(letter)[0] - (margin_left + margin_right) #Ancho disponible considerando margenes
    available_height = landscape(letter)[1] - (margin_top + margin_bottom)

    # Ancho fijo para la columna "Hora"
    hora_col_width = 0.8 * units.inch #Ancho fijo para la columna de hora
    col_widths = [hora_col_width] #Inicializar col_widths con el ancho fijo de la columna de hora

    # Cálculo del ancho de las demás columnas basado en el contenido del párrafo
    for i, col in enumerate(schedule.columns[1:]): #Iterar desde la segunda columna en adelante
        max_width_col = 0
        for row in data_with_paragraphs[1:]:
            if isinstance(row[i + 1], Paragraph): #row[i+1] porque se empieza desde la segunda columna
                width, height = row[i + 1].wrapOn(None, (available_width - hora_col_width)/(len(schedule.columns)-1), available_height) #Ancho disponible menos el de la columna de hora y dividido entre el numero de columnas restantes
                max_width_col = max(max_width_col, width)
        col_widths.append(max_width_col)


    table = Table(data_with_paragraphs, colWidths=col_widths)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
    ]))

    # Detectar desbordamiento y ajustar el tamaño de fuente si es necesario
    w, h = table.wrapOn(None, available_width, available_height)
    while w > available_width:
        for row in data_with_paragraphs[1:]:
          for cell in row:
            if isinstance(cell, Paragraph):
              cell.style.fontSize -= 0.5
              cell.style.leading = cell.style.fontSize * 1.25
        table = Table(data_with_paragraphs, colWidths=col_widths)
        w, h = table.wrapOn(None, available_width, available_height)
        if cell.style.fontSize <= 4:
          print("No se pudo ajustar la tabla al ancho de la página.")
          break

    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=margin_left, rightMargin=margin_right, topMargin=margin_top, bottomMargin=margin_bottom) #Usar los margenes definidos
    elements = [table]

    try:
        doc.build(elements)
    except Exception as e:
        print(f"Error al construir el PDF: {e}")
        import traceback
        traceback.print_exc()
        return io.BytesIO()

    buffer.seek(0)
    return buffer