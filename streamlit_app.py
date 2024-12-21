import streamlit as st
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from datetime import timedelta
import os

# Función para transformar el archivo Excel subido
def transform_excel(input_df):
    columns_mapping = {
        "Unnamed: 1": "NRC",
        "Unnamed: 2": "Clave",
        "Unnamed: 3": "Materia",
        "Unnamed: 4": "Sec",
        "Unnamed: 5": "CR",
        "Unnamed: 6": "CUP",
        "Unnamed: 7": "DIS",
        "Unnamed: 8": "Ses",
        "Unnamed: 9": "Hora",
        "Unnamed: 10": "Días",
        "Unnamed: 11": "Edif",
        "Unnamed: 12": "Aula",
        "Unnamed: 15": "Profesor"
    }
    input_df = input_df.rename(columns=columns_mapping)
    output_columns = [
        "NRC", "Clave", "Materia", "Sec", "CR", "CUP", "DIS",
        "Ses", "Hora", "Días", "Edif", "Aula", "Profesor"
    ]
    output_df = input_df[output_columns]
    output_df = output_df.dropna(how='all').reset_index(drop=True)
    return output_df

# Modificar días a nombres válidos
days_mapping = {
    "L": "Lunes", "M": "Martes", "I": "Miércoles", "J": "Jueves", "V": "Viernes",
    "lunes": "Lunes", "martes": "Martes", "miércoles": "Miércoles", "jueves": "Jueves", "viernes": "Viernes",
    "LUNES": "Lunes", "MARTES": "Martes", "MIÉRCOLES": "Miércoles", "JUEVES": "Jueves", "VIERNES": "Viernes",
}

# Nueva función para limpiar los días
def clean_days(value):
    if isinstance(value, str):
        possible_days = value.strip().split()
        cleaned_days = [days_mapping.get(day, None) for day in possible_days]
        return [day for day in cleaned_days if day is not None]
    return []

# Función para procesar y transformar los datos
def process_data(first_sheet):
    first_sheet = first_sheet.iloc[1:]
    columns_to_extract = ["NRC", "Materia", "Sec", "Ses", "Hora", "Días", "Edif", "Aula", "Profesor"]
    first_sheet = first_sheet[columns_to_extract]
    first_sheet.columns = ["NRC", "Materia", "Sección", "Sesión", "Hora", "Días", "Edificio", "Aula", "Profesor"]
    first_sheet.loc[:, "Materia"] = first_sheet["Materia"].ffill().infer_objects()
    first_sheet.loc[:, "NRC"] = first_sheet["NRC"].ffill().infer_objects()
    first_sheet.loc[:, "Sección"] = first_sheet["Sección"].ffill().infer_objects()
    first_sheet.loc[:, "Profesor"] = first_sheet["Profesor"].ffill().infer_objects()
    first_sheet = first_sheet.dropna(subset=["Sesión", "Hora", "Días"])

    first_sheet["Días"] = first_sheet["Días"].apply(clean_days)

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

    first_sheet["Hora"] = first_sheet["Hora"].apply(parse_time_range)
    expanded_data = first_sheet.explode("Días").reset_index(drop=True)
    return expanded_data

# Función para filtrar los datos según el NRC
def filter_by_nrc(data):
    unique_nrcs = data[["NRC", "Materia", "Profesor"]].drop_duplicates()

    selected_nrcs = st.multiselect("Selecciona los NRC de las materias que deseas incluir:", options=unique_nrcs["NRC"].astype(str).tolist())

    data["NRC"] = data["NRC"].astype(str)
    filtered_data = data[data["NRC"].isin(selected_nrcs)]

    if not filtered_data.empty:
        st.success(f"Se encontraron {len(filtered_data)} registros para los NRC seleccionados.")
        st.write("Registros encontrados para los NRC seleccionados:")
        st.dataframe(filtered_data)
    else:
        st.warning("No hay datos disponibles para los NRC seleccionados. Revisa los valores seleccionados.")

    return filtered_data

# Función para crear una hoja de horario
def create_schedule_sheet(expanded_data):
    hours_list = [
        "07:00 AM - 07:59 AM", "08:00 AM - 08:59 AM", "09:00 AM - 09:59 AM", "10:00 AM - 10:59 AM",
        "11:00 AM - 11:59 AM", "12:00 PM - 12:59 PM", "01:00 PM - 01:59 PM", "02:00 PM - 02:59 PM",
        "03:00 PM - 03:59 PM", "04:00 PM - 04:59 PM", "05:00 PM - 05:59 PM", "06:00 PM - 06:59 PM",
        "07:00 PM - 07:59 PM", "08:00 PM - 08:59 PM"
    ]
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    schedule = pd.DataFrame(columns=["Hora"] + days)
    schedule["Hora"] = hours_list

    for index, row in expanded_data.iterrows():
        for hour_range in hours_list:
            start_hour, end_hour = [pd.to_datetime(hr, format="%I:%M %p") for hr in hour_range.split(" - ")]
            class_start, class_end = [pd.to_datetime(hr, format="%I:%M %p") for hr in row["Hora"].split(" - ")]
            if start_hour < class_end and class_start < end_hour:
                day_col = row["Días"]
                edificio_letra = row["Edificio"][-1] if pd.notna(row["Edificio"]) else ""
                content = f"{row['Materia']}\n{edificio_letra} {row['Aula']}\n{row['Profesor']}"
                if pd.notna(schedule.loc[schedule["Hora"] == hour_range, day_col].values[0]):
                    schedule.loc[schedule["Hora"] == hour_range, day_col] += "\n" + content
                else:
                    schedule.loc[schedule["Hora"] == hour_range, day_col] = content

    # Ajustar estilo de tabla
    styled_schedule = schedule.style.set_properties(
        subset=["Hora"], 
        **{"width": "100px", "text-align": "center"}
    ).set_table_styles([
        {
            "selector": "th",
            "props": [
                ("background-color", "#f2f2f2"),
                ("color", "#333"),
                ("font-weight", "bold"),
                ("text-align", "center")
            ]
        },
        {
            "selector": "td",
            "props": [
                ("text-align", "center"),
                ("word-wrap", "break-word"),
                ("white-space", "pre-wrap")
            ]
        }
    ])

    return styled_schedule

# Función principal
def main():
    st.title("Generador de Horarios a partir de Excel")

    uploaded_file = st.file_uploader("Sube tu archivo Excel", type=["xlsx"])
    if uploaded_file is not None:
        input_df = pd.ExcelFile(uploaded_file).parse(0)
        st.write("Vista previa del archivo original:")
        st.dataframe(input_df.head())

        output_df = transform_excel(input_df)

        expanded_data = process_data(output_df)
        st.write("Datos procesados:")
        st.dataframe(expanded_data)

        filtered_data = filter_by_nrc(expanded_data)
        if not filtered_data.empty:
            # Generar el horario
            if st.button("Generar horario", key="generar_horario"):
                # Crear la hoja de horario (sin aplicar estilos por ahora)
                schedule = create_schedule_sheet(filtered_data)

                # Mostrar el horario generado
                st.write("Horario generado:")
                st.dataframe(schedule)

                # Obtener el DataFrame de datos (sin el Styler)
                schedule_data = schedule.data  # Esto es el DataFrame original sin el estilo

                # Definir la lista de horas
                hours_list = [
                    "07:00 AM - 07:59 AM", "08:00 AM - 08:59 AM", "09:00 AM - 09:59 AM", "10:00 AM - 10:59 AM",
                    "11:00 AM - 11:59 AM", "12:00 PM - 12:59 PM", "01:00 PM - 01:59 PM", "02:00 PM - 02:59 PM",
                    "03:00 PM - 03:59 PM", "04:00 PM - 04:59 PM", "05:00 PM - 05:59 PM", "06:00 PM - 06:59 PM",
                    "07:00 PM - 07:59 PM", "08:00 PM - 08:59 PM"
                ]

                # Crear un archivo Excel con el horario
                wb = Workbook()
                ws = wb.active
                ws.title = "Horario"

                # Agregar los encabezados al archivo Excel
                for c_idx, column_title in enumerate(schedule_data.columns, 1):
                    cell = ws.cell(row=1, column=c_idx, value=column_title)
                    # Aplicar estilos a los encabezados
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                    cell.fill = PatternFill(start_color="FFDDC1", end_color="FFDDC1", fill_type="solid")

                # Agregar los datos al archivo Excel (empezando en la fila 2)
                for r_idx, row in enumerate(schedule_data.values, 2):  # Comenzar en la fila 2
                    for c_idx, value in enumerate(row, 1):
                        cell = ws.cell(row=r_idx, column=c_idx, value=value)
                        # Estilos para las celdas de datos
                        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


                # Combinar celdas para clases que ocupan múltiples horas consecutivas
                for idx, row in schedule_data.iterrows():
                    # Parseamos el rango de horas para ver si abarcan más de una celda
                    start_hour, end_hour = [pd.to_datetime(hr, format="%I:%M %p") for hr in row["Hora"].split(" - ")]
    
                    # Convertimos las horas al formato adecuado para la comparación con hours_list
                    start_hour_str = start_hour.strftime("%I:%M %p").replace(" 0", " ")  # Quitar el cero inicial en formato de 12 horas
                    end_hour_str = end_hour.strftime("%I:%M %p").replace(" 0", " ")  # Quitar el cero inicial en formato de 12 horas

                    # Asegurarnos de que las horas en hours_list coincidan con el formato utilizado
                    start_idx = next((i for i, hour in enumerate(hours_list) if start_hour_str in hour), None)
                    end_idx = next((i for i, hour in enumerate(hours_list) if end_hour_str in hour), None)

                    # Si las horas no se encuentran en la lista hours_list, mostramos un mensaje de error
                    if start_idx is None or end_idx is None:
                        raise ValueError(f"Las horas {start_hour_str} y/o {end_hour_str} no se encuentran en la lista de horas disponibles.")

                    # Si la clase abarca varias horas, combinamos las celdas
                    if end_idx > start_idx:
                        day_col = row["Días"]
                        col_idx = schedule_data.columns.get_loc(day_col) + 1  # Obtener la columna correspondiente a los días
                        # Combinar las celdas correspondientes a las horas
                        ws.merge_cells(start_row=start_idx + 2, start_column=col_idx, end_row=end_idx + 2, end_column=col_idx)
                        merged_cell = ws.cell(row=start_idx + 2, column=col_idx)
                        merged_cell.value = f"{row['Materia']}\n{row['Edificio'][-1]} {row['Aula']}\n{row['Profesor']}"
                        merged_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

                # Ajustar el tamaño de las columnas
                for col in range(1, len(schedule_data.columns) + 1):
                    col_letter = get_column_letter(col)
                    max_length = 0
                    for row in schedule_data.iloc[:, col - 1]:
                        if isinstance(row, str):
                            max_length = max(max_length, len(row))
                    adjusted_width = min(max_length + 2, 40)  # Limitar el ancho máximo a 40
                    ws.column_dimensions[col_letter].width = adjusted_width


                # Guardar el archivo y permitir la descarga
                file_path = "horario_generado.xlsx"
                wb.save(file_path)

                # Descargar el archivo generado
                with open(file_path, "rb") as f:
                    st.download_button(
                        label="Descargar horario",
                        data=f,
                        file_name=file_path,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                # Eliminar el archivo temporal después de la descarga
                os.remove(file_path)


# Ejecutar la función principal
if __name__ == "__main__":
    main()


