# Funciones/schedule.py
import io
import os
import base64
import numpy as np
import pandas as pd
from Funciones.utils import obtener_fecha_guadalajara
from reportlab.lib import colors, units
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph
import traceback
from Diseño.styles import get_reportlab_styles

INSTITUTION_NAME = "UNIVERSIDAD DE GUADALAJARA"
URL_PAGINA = os.environ.get("URL_PAGINA")

def create_schedule_sheet(expanded_data):
    """Crea una hoja de horario en formato pandas DataFrame."""
    hours_list = [
        "07:00 AM - 07:59 AM", "08:00 AM - 08:59 AM", "09:00 AM - 09:59 AM", "10:00 AM - 10:59 AM",
        "11:00 AM - 11:59 AM", "12:00 PM - 12:59 PM", "01:00 PM - 01:59 PM", "02:00 PM - 02:59 PM",
        "03:00 PM - 03:59 PM", "04:00 PM - 04:59 PM", "05:00 PM - 05:59 PM", "06:00 PM - 06:59 PM",
        "07:00 PM - 07:59 PM", "08:00 PM - 08:59 PM"
    ]
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
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

def create_schedule_pdf(schedule, ciclo, as_base64=False):
    """Crea un archivo PDF con el horario."""
    try:
        buffer = io.BytesIO()
        styles = get_reportlab_styles()
        dias_semana = ["Hora", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]

        if "Sábado" in schedule.columns:
            sabado_data = schedule["Sábado"].iloc[1:].replace("", np.nan).replace(" ", np.nan)
            sabado_data = sabado_data.dropna()
            if not sabado_data.empty:
                dias_semana.append("Sábado")

        filas_no_vacias = []
        for index, row in schedule.iterrows():
            if not all(pd.isna(x) or str(x).strip() == "" for x in row[1:]):
                filas_no_vacias.append(index)

        schedule = schedule.loc[filas_no_vacias].reset_index(drop=True)

        data_for_table = []
        data_for_table.append(dias_semana)

        horas = schedule.index.to_list()

        for index, row in schedule.iterrows():
            hora = row["Hora"]
            try:
                hora_inicio, hora_fin = hora.split(" - ")
            except (ValueError, AttributeError):
                hora_inicio = hora
                hora_fin = ""
            p_hora_inicio = Paragraph(hora_inicio, styles['Hora'])
            p_hora_fin = Paragraph(hora_fin, styles['Hora'])
            hora_cell = [p_hora_inicio, p_hora_fin]

            data_row = [hora_cell]

            for dia in dias_semana[1:]:
                materia_data = row[dia]
                if pd.isna(materia_data):
                    data_row.append("")
                else:
                    parts = str(materia_data).split('\n')
                    materia = parts[0] if len(parts) >= 1 else ""
                    aula = parts[1] if len(parts) >= 2 else ""
                    profesor = parts[2] if len(parts) >= 3 else ""
                    data_row.append([
                        Paragraph(materia, styles['Materia']),
                        Paragraph(aula, styles['Aula']),
                        Paragraph(profesor, styles['Profesor'])
                    ])
            data_for_table.append(data_row)

        num_dias = len(dias_semana) - 1
        hora_width = 0.7 * units.inch
        left_margin = 0.5 * units.inch
        right_margin = 0.5 * units.inch

        available_width = landscape(letter)[0] - (left_margin + right_margin) - hora_width
        col_width = available_width / num_dias

        col_widths = [hora_width] + [col_width] * num_dias

        spans = []
        for j in range(1, len(dias_semana)):
            start_row = None
            for i in range(1, len(horas) + 1):
                if i < len(data_for_table) and j < len(data_for_table[0]):
                    current_cell = data_for_table[i][j]
                    prev_cell = data_for_table[i - 1][j] if i > 0 else None

                    if current_cell != " " and prev_cell is not None:
                        current_text = current_cell.getPlainText().strip() if isinstance(current_cell, Paragraph) else str(current_cell).strip()
                        prev_text = prev_cell.getPlainText().strip() if isinstance(prev_cell, Paragraph) else str(prev_cell).strip()

                        if current_text == prev_text:
                            if start_row is None:
                                start_row = i - 1
                            else:
                                if start_row is not None:
                                    spans.append(((j, start_row), (j, i - 1)))
                                    start_row = None
            if start_row is not None:
                spans.append(((j, start_row), (j, len(horas))))

        table = Table(data_for_table, colWidths=col_widths)
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('WORDWRAP', (1,1), (-1,-1), col_width)
        ])

        for start, end in spans:
            try:
                table_style.add('SPAN', start, end)
            except IndexError as e:
                print(f"Error al aplicar span: {start}, {end}. Dimensiones de la tabla: {table.getSize()}")
                traceback.print_exc()

        table.setStyle(table_style)

        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                                leftMargin=left_margin, rightMargin=right_margin,
                                topMargin=0.2 * units.inch, bottomMargin=1 * units.inch)

        elements = []
        elements.append(Paragraph(f"{INSTITUTION_NAME}", styles['Title']))
        elements.append(Paragraph(f"Horario de Clases - {ciclo}", styles['Subtitle']))
        elements.append(table)
        
        fecha_generacion = obtener_fecha_guadalajara()
        footer_text = f"Creado el: {fecha_generacion}"
        footer_link_text = f"Generado con ({URL_PAGINA})"

        elements.append(Paragraph(footer_text, styles['Footer']))
        elements.append(Paragraph(footer_link_text, styles['FooterLink']))

        doc.build(elements)

        if as_base64:
            buffer.seek(0)
            pdf_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return pdf_base64
        else:
            buffer.seek(0)
            return buffer

    except Exception as e:
        print(f"Error al construir el PDF: {e}")
        traceback.print_exc()
        return io.BytesIO()