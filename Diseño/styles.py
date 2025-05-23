import pandas as pd
import numpy as np
import datetime
import pytz # Asegúrate de que pytz esté importado si lo usas en otras funciones de styles.py
import streamlit as st

# --- Funciones de utilidad para el estilo (Mantenemos _to_minutes para robustez) ---
def _to_minutes(time_str):
    """Convierte una cadena de hora HH:MM a minutos desde la medianoche."""
    try:
        # Asegurarse de que la hora sea HH:MM
        if 'AM' in time_str or 'PM' in time_str:
            dt_obj = datetime.datetime.strptime(time_str.strip(), "%I:%M %p")
        else:
            dt_obj = datetime.datetime.strptime(time_str.strip(), "%H:%M")
        
        return dt_obj.hour * 60 + dt_obj.minute
    except ValueError:
        # Esto capturaría errores de formato si todavía llega algo inesperado.
        # Es lo que probablemente está causando el problema que aún persista en la tabla de vista previa
        # cuando hay un cruce. Lo estamos manejando con un valor alto para que no cause conflicto.
        return -1 # Retorna un valor que indique error o que no es un tiempo válido.


def _check_time_overlap(range1_str, range2_str):
    """
    Verifica si dos rangos de tiempo (ej. '08:00-09:00') se superponen.
    Ambos rangos deben estar en formato HH:MM-HH:MM.
    """
    try:
        start1_str, end1_str = range1_str.split('-')
        start2_str, end2_str = range2_str.split('-')

        start1_min = _to_minutes(start1_str)
        end1_min = _to_minutes(end1_str)
        start2_min = _to_minutes(start2_str)
        end2_min = _to_minutes(end2_str)

        # Si alguna conversión falló, no consideramos un cruce real
        if start1_min == -1 or end1_min == -1 or start2_min == -1 or end2_min == -1:
            return False

        # Verifica si hay solapamiento (incluyendo bordes)
        # La condición (A.start < B.end) AND (B.start < A.end)
        return start1_min < end2_min and start2_min < end1_min
    except Exception:
        # Cualquier error en el split o conversión significa que no hay un formato válido para cruce
        return False

# --- Estilos base para el DataFrame de la tabla principal (mantén el que ya tienes) ---
def apply_dataframe_styles(df, cruces_detectados=None, clases_seleccionadas=None):
    """
    Aplica estilos CSS al DataFrame principal, resaltando las filas de clases
    que tienen cruces de horario.
    
    df: El DataFrame de materias (horario_preliminar).
    cruces_detectados: Diccionario de cruces (ej. {'Lunes': [(clase1, clase2), ...]}).
    clases_seleccionadas: Lista de objetos Clase seleccionados.
    """
    if cruces_detectados is None:
        cruces_detectados = {}
    if clases_seleccionadas is None:
        clases_seleccionadas = []

    # Crear un set de NRCs de clases en conflicto para búsqueda rápida
    nrcs_en_conflicto = set()
    for dia, conflictos in cruces_detectados.items():
        for clase1, clase2 in conflictos:
            nrcs_en_conflicto.add(clase1.nrc)
            nrcs_en_conflicto.add(clase2.nrc)

    # Función para aplicar estilo a las filas
    def highlight_conflict_rows(row):
        # Asumiendo que tu DataFrame 'df' tiene una columna 'NRC'
        # o que puedes identificar la clase de alguna otra manera en la fila
        if 'NRC' in row.index and row['NRC'] in nrcs_en_conflicto:
            return ['background-color: #4a1a1a; border: 2px solid #FF5252; color: #FFC0CB; font-weight: bold;'] * len(row)
        return [''] * len(row) # Sin estilo si no hay conflicto


    # Estilo para el encabezado (índice)
    header_styles = [
        {'selector': 'th', 'props': [
            ('background-color', '#0e1117'), # Color de fondo oscuro (como el sidebar)
            ('color', 'white'), 
            ('font-size', '1rem'), 
            ('text-align', 'center'),
            ('padding', '10px'),
            ('border-bottom', '2px solid #333')
        ]},
        # Estilo para las celdas del DataFrame
        {'selector': 'td', 'props': [
            ('text-align', 'left'),
            ('padding', '8px'),
            ('font-size', '0.9rem'),
            ('border-bottom', '1px solid #333'), # Bordes sutiles entre filas
            ('white-space', 'pre-wrap') # Permite que el texto se ajuste
        ]},
        # Estilo para el índice del DataFrame (columnas de la izquierda si las hubiera)
        {'selector': 'th.row_heading', 'props': [
            ('background-color', '#1e2025'), # Un poco más claro que el encabezado
            ('color', 'white'), 
            ('font-size', '0.95rem'), 
            ('font-weight', 'bold')
        ]},
        # Estilo para el índice de columnas (encabezado del dataframe)
        {'selector': 'th.col_heading', 'props': [
            ('background-color', '#0e1117'),
            ('color', 'white'),
            ('font-size', '1rem')
        ]},
        # Estilo para el hover sobre las filas
        {'selector': 'tr:hover', 'props': [
            ('background-color', '#2a2e34') # Un ligero cambio al pasar el ratón
        ]}
    ]
    
    # Aplica estilos generales y luego los estilos de conflicto
    styled_df = df.style.set_table_styles(header_styles).map( # Cambiado de applymap a map
        lambda x: 'background-color: #21252b;' if pd.notna(x) and x != '' else 'background-color: #1a1d21;',
        subset=pd.IndexSlice[:, :]
    ).apply(highlight_conflict_rows, axis=1) # Aplica el estilo de conflicto fila por fila

    return styled_df

# --- Nuevo/Actualizado Estilo para la Tabla de Horario (Calendario) ---
def apply_dataframe_styles_with_cruces(df_calendario, cruces_detectados, clases_seleccionadas):
    """
    Aplica estilos al DataFrame del calendario, resaltando las celdas llenas
    y marcando los cruces de horario de forma sutil.

    df_calendario: El DataFrame del calendario (índice de horas, columnas de días).
    cruces_detectados: Diccionario de cruces (ej. {'Lunes': [(clase1, clase2), ...]}).
    clases_seleccionadas: Lista de objetos Clase seleccionados.
    """
    # Función de estilo para las celdas
    def _style_cell(val, dia_col, hora_idx):
        styles = []
        
        # Estilo base para celdas llenas (gris claro)
        if pd.notna(val) and val != '':
            styles.append('background-color: #2a2e34;') # Gris más claro para celdas con contenido
            styles.append('color: white;')
            styles.append('font-size: 0.85rem;')
            styles.append('vertical-align: top;') # Alinear texto arriba
            styles.append('padding: 5px;')
            styles.append('border: 1px solid #444;') # Borde sutil
        else:
            # Estilo para celdas vacías (gris oscuro)
            styles.append('background-color: #1a1d21;')
            styles.append('color: #555;') # Color de texto muy tenue para celdas vacías
            styles.append('border: 1px solid #222;')

        # Marcar cruces (solo si la celda no está vacía)
        if pd.notna(val) and val != '' and dia_col in cruces_detectados:
            for clase1_obj, clase2_obj in cruces_detectados[dia_col]:
                # Crear rangos de tiempo para la comparación de la celda del calendario
                # y las clases en conflicto.
                # Asegúrate de que hora_idx (ej. "07:00 - 08:00") sea compatible con _check_time_overlap
                # y que las horas de los objetos Clase también lo sean (HH:MM)
                
                # Para la celda del calendario, hora_idx es el rango de la celda (ej. "07:00-08:00")
                # Las horas de los objetos Clase ya deberían estar en HH:MM
                clase1_range = f"{clase1_obj.hora_inicio}-{clase1_obj.hora_fin}"
                clase2_range = f"{clase2_obj.hora_inicio}-{clase2_obj.hora_fin}"
                
                # Comprobar si la celda actual (hora_idx) se superpone con cualquiera de las clases en conflicto
                # Y que el día sea el mismo (ya filtrado por dia_col)
                if _check_time_overlap(hora_idx, clase1_range) or \
                   _check_time_overlap(hora_idx, clase2_range):
                    # Aplicar un estilo de "cruce" más sutil: borde rojo y sombra
                    styles.append('border: 2px solid #FF6347;') # Tomate/Rojo claro
                    styles.append('box-shadow: 0 0 5px rgba(255, 99, 71, 0.5);') # Sombra sutil
                    styles.append('font-weight: bold;') # Texto en negrita para cruces
                    styles.append('color: #FFC0CB;') # Color de texto rosado para hacer contraste con el rojo

        return "; ".join(styles)

    # Aplica la función de estilo a cada celda
    styled_df = df_calendario.style.apply(
        lambda s: [
            _style_cell(val, s.name, s.index[i]) # s.name es el día (columna), s.index[i] es la hora (fila)
            for i, val in enumerate(s)
        ],
        axis=0 # Aplicar columna por columna
    )
    
    # Estilos generales para el encabezado y el índice del calendario
    styled_df.set_table_styles([
        {'selector': 'th', 'props': [ # Encabezados de columnas (Lunes, Martes, etc.)
            ('background-color', '#0e1117'),
            ('color', 'white'),
            ('font-size', '1rem'),
            ('text-align', 'center'),
            ('padding', '10px'),
            ('border-bottom', '2px solid #333')
        ]},
        {'selector': 'th.row_heading', 'props': [ # Encabezados de filas (Horas)
            ('background-color', '#1e2025'),
            ('color', 'white'),
            ('font-size', '0.95rem'),
            ('font-weight', 'bold'),
            ('text-align', 'center'),
            ('padding', '10px')
        ]},
        # Estilo para el hover sobre las filas
        {'selector': 'tr:hover', 'props': [
            ('background-color', '#2a2e34') # Un ligero cambio al pasar el ratón
        ]}
    ])
    
    return styled_df

# --- Otras funciones de styles.py (mantén las que ya tienes) ---
def set_page_style():
    """Configura el estilo CSS general de la página de Streamlit."""
    st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117; /* Fondo oscuro principal */
            color: white; /* Color de texto predeterminado */
        }
        .stMarkdown, .stText, .stException {
            color: white; /* Asegura que el texto sea visible */
        }
        /* Color de los expanders */
        .streamlit-expanderHeader {
            background-color: #212529; /* Un tono más claro que el fondo principal */
            color: white;
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .streamlit-expanderContent {
            background-color: #1a1d21; /* Contenido del expander un poco más oscuro */
            border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-top: none; /* Eliminar el borde superior duplicado */
            padding: 1rem;
        }
        /* Estilo para los multiselect */
        .stMultiSelect div[data-baseweb="select"] > div {
            background-color: #212529;
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 0.25rem;
        }
        .stMultiSelect div[data-baseweb="select"] > div:hover {
            border-color: #6a6a6a;
        }
        .stMultiSelect div[data-baseweb="select"] div[data-baseweb="tag"] {
            background-color: #31353a; /* Tags de elementos seleccionados */
            color: white;
        }
        /* Estilo para los selectbox */
        .stSelectbox div[data-baseweb="select"] > div {
            background-color: #212529;
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 0.25rem;
        }
        .stSelectbox div[data-baseweb="select"] > div:hover {
            border-color: #6a6a6a;
        }
        /* Estilo de los botones */
        .stButton>button {
            background-color: #4CAF50; /* Un verde vibrante */
            color: white;
            border-radius: 0.5rem;
            border: none;
            padding: 10px 20px;
            font-size: 1rem;
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #45a049; /* Verde un poco más oscuro al pasar el ratón */
        }
        /* Estilos para los mensajes de Streamlit (info, success, warning, error) */
        .stAlert {
            border-radius: 0.5rem;
            padding: 1rem;
            font-size: 1rem;
        }
        .stAlert.info {
            background-color: #172a3a;
            color: #87CEEB; /* Azul claro */
            border: 1px solid #1f3b4d;
        }
        .stAlert.success {
            background-color: #1a361e;
            color: #8BC34A; /* Verde claro */
            border: 1px solid #28542b;
        }
        .stAlert.warning {
            background-color: #3a2a1a;
            color: #FFC107; /* Amarillo/naranja */
            border: 1px solid #543b28;
        }
        .stAlert.error {
            background-color: #4a1a1a;
            color: #FF5252; /* Rojo */
            border: 1px solid #6e2a2a;
        }
        /* Estilo para el input de texto (útil si hay un filtro de texto, etc.) */
        .stTextInput>div>div>input {
            background-color: #212529;
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 0.25rem;
        }
        .stTextInput>div>div>input:focus {
            border-color: #6a6a6a;
            outline: none;
        }
        /* Estilo para las pestañas */
        .stTabs [data-baseweb="tab-list"] button {
            background-color: #1a1d21; /* Fondo de pestaña inactiva */
            color: white;
            border-bottom: 2px solid transparent;
            padding: 10px 20px;
            font-weight: bold;
        }
        .stTabs [data-baseweb="tab-list"] button:hover {
            background-color: #2a2e34; /* Fondo de pestaña al pasar el ratón */
            color: white;
        }
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
            background-color: #0e1117; /* Fondo de pestaña activa (igual que el fondo principal) */
            border-bottom: 2px solid #4CAF50; /* Línea verde debajo de la pestaña activa */
            color: #4CAF50;
        }
        .stTabs [data-baseweb="tab-panel"] {
            background-color: #0e1117; /* Contenido de la pestaña */
            padding: 20px;
            border-top: none;
        }
        </style>
        """, unsafe_allow_html=True)


def get_reportlab_styles():
    """Define y/o modifica estilos básicos para ReportLab."""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.colors import black, red, green # Importar colores si los vas a usar directamente
    from reportlab.lib import colors

    styles = getSampleStyleSheet()

    # Modificar estilos existentes o crear nuevos con nombres únicos
    # Si 'Title' ya existe, lo modificamos directamente.
    # Si quieres uno nuevo, usa un nombre como 'MyTitleStyle'
    if 'Title' in styles:
        styles['Title'].fontSize = 24
        styles['Title'].spaceAfter = 12
        styles['Title'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Title',
                                  parent=styles['h1'], # Puedes basarlo en h1 si quieres
                                  fontSize=24,
                                  spaceAfter=12,
                                  alignment=TA_CENTER))

    if 'Subtitle' in styles:
        styles['Subtitle'].fontSize = 14
        styles['Subtitle'].spaceAfter = 8
        styles['Subtitle'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Subtitle',
                                  parent=styles['h2'], # Puedes basarlo en h2
                                  fontSize=14,
                                  spaceAfter=8,
                                  alignment=TA_CENTER))

    # Estilo para encabezados de tabla (aseguramos que sea un nuevo estilo o lo modificamos)
    # Es mejor crear uno si no lo tienen y basarlo en 'Normal'
    styles.add(ParagraphStyle(name='TableHeader',
                              parent=styles['Normal'],
                              fontSize=9,
                              fontName='Helvetica-Bold',
                              alignment=TA_CENTER,
                              spaceAfter=3,
                              spaceBefore=3))

    # Estilo para celdas de tabla
    styles.add(ParagraphStyle(name='TableCell',
                              parent=styles['Normal'],
                              fontSize=8,
                              fontName='Helvetica',
                              alignment=TA_LEFT,
                              spaceAfter=2,
                              spaceBefore=2))

    # Estilo para los mensajes de cruces
    styles.add(ParagraphStyle(name='ConflictMessage',
                              parent=styles['Normal'],
                              fontSize=9,
                              textColor=red, # Usar la importación de ReportLab colors.red
                              fontName='Helvetica-Bold',
                              spaceAfter=6,
                              alignment=TA_LEFT))
    
    # Asegúrate de que 'Hora', 'Materia', 'Aula', 'Profesor', 'Footer', 'FooterLink' también estén definidos
    # Si no están en getSampleStyleSheet(), se añadirán. Si ya existen, se modificarán.

    # Ejemplo: Estilo para las horas en la tabla del PDF
    if 'Hora' in styles:
        styles['Hora'].fontSize = 8
        styles['Hora'].fontName = 'Helvetica'
        styles['Hora'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Hora',
                                  parent=styles['Normal'],
                                  fontSize=8,
                                  fontName='Helvetica',
                                  alignment=TA_CENTER))

    # Estilo para Materia en la tabla del PDF
    if 'Materia' in styles:
        styles['Materia'].fontSize = 8
        styles['Materia'].fontName = 'Helvetica-Bold'
        styles['Materia'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Materia',
                                  parent=styles['Normal'],
                                  fontSize=8,
                                  fontName='Helvetica-Bold',
                                  alignment=TA_CENTER))
    
    # Estilo para Aula en la tabla del PDF
    if 'Aula' in styles:
        styles['Aula'].fontSize = 7
        styles['Aula'].fontName = 'Helvetica'
        styles['Aula'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Aula',
                                  parent=styles['Normal'],
                                  fontSize=7,
                                  fontName='Helvetica',
                                  alignment=TA_CENTER))

    # Estilo para Profesor en la tabla del PDF
    if 'Profesor' in styles:
        styles['Profesor'].fontSize = 7
        styles['Profesor'].fontName = 'Helvetica-Oblique'
        styles['Profesor'].alignment = TA_CENTER
    else:
        styles.add(ParagraphStyle(name='Profesor',
                                  parent=styles['Normal'],
                                  fontSize=7,
                                  fontName='Helvetica-Oblique',
                                  alignment=TA_CENTER))
    
    # Estilo para Footer
    if 'Footer' in styles:
        styles['Footer'].fontSize = 7
        styles['Footer'].textColor = black
        styles['Footer'].alignment = TA_RIGHT
    else:
        styles.add(ParagraphStyle(name='Footer',
                                  parent=styles['Normal'],
                                  fontSize=7,
                                  textColor=black,
                                  alignment=TA_RIGHT))

    # Estilo para FooterLink
    if 'FooterLink' in styles:
        styles['FooterLink'].fontSize = 7
        styles['FooterLink'].textColor = colors.blue # O el color que desees para un enlace
        styles['FooterLink'].alignment = TA_RIGHT
    else:
        styles.add(ParagraphStyle(name='FooterLink',
                                  parent=styles['Normal'],
                                  fontSize=7,
                                  textColor=colors.blue,
                                  alignment=TA_RIGHT))


    return styles