import os
import json
import base64
import logging
import requests
import pandas as pd
import streamlit as st
from io import BytesIO
import streamlit.components.v1 as components
# from streamlit_pdf_viewer import pdf_viewer
from Diseño.styles import apply_dataframe_styles, set_page_style, apply_dataframe_styles_with_cruces, get_reportlab_styles
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf
from Funciones.data_processing import fetch_table_data, process_data_from_web, cargar_datos_desde_json, guardar_datos_local
from Funciones.utils import detectar_cruces, crear_clases_desde_dataframe, generar_mensaje_cruces
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, show_abbreviations, FORM_URL, POST_URL

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------
# INICIALIZACIÓN DEL ESTADO
# --------------------------------------------------
def initialize_session_state():
    """Inicializa el estado de la sesión con verificaciones"""
    required_keys = {
        'query_state': {
            'done': False,
            'table_data': None,
            'selected_nrcs': [],
            'selected_subjects': []
        },
        'expanded_data': pd.DataFrame(columns=[
            'Materia', 'NRC', 'Profesor', 'Días', 'Hora', 'Edificio', 'Aula'
        ]),
        'selected_options': {},
        'clases_seleccionadas': [],    # <-- Añadido para persistencia
        'cruces_detectados': {}        # <-- Cambiado a diccionario para persistencia
    }
    
    for key, default_value in required_keys.items():
        if key not in st.session_state:
            st.session_state[key] = default_value.copy() if hasattr(default_value, 'copy') else default_value
        elif key == 'expanded_data' and not isinstance(st.session_state[key], pd.DataFrame):
            st.session_state[key] = pd.DataFrame(columns=default_value.columns)
        elif key == 'clases_seleccionadas' and not isinstance(st.session_state[key], list): # Asegurar que sea una lista
            st.session_state[key] = []
        elif key == 'cruces_detectados' and not isinstance(st.session_state[key], dict): # Asegurar que sea un diccionario
            st.session_state[key] = {}


initialize_session_state()

# --------------------------------------------------
# Configuración de la aplicación
# --------------------------------------------------
VERSION = os.environ.get("VERSION", "version de desarrollo")
URL_PAGINA = os.environ.get("URL_PAGINA", "web de desarrollo")
form_url = "https://docs.google.com/forms/d/e/1FAIpQLScc5fCcNo9ZocfuqDhJD5QOdbdTNP_RnUhTYAzkEIEFHIB2rA/viewform?embedded=true"

st.set_page_config(
    page_title="Generador de Horarios UDG",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)
set_page_style()

# --------------------------------------------------
# Funciones principales con cache y manejo de errores
# --------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_form_options_cached(form_url):
    """Versión cacheada de fetch_form_options_with_descriptions"""
    try:
        return fetch_form_options_with_descriptions(form_url)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error de conexión al obtener opciones: {str(e)}")
        st.error("Error de conexión al obtener las opciones. Intenta nuevamente más tarde.")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al obtener opciones: {str(e)}")
        st.error("Ocurrió un error inesperado al cargar las opciones.")
        return None

def reset_query_state():
    """Reinicia completamente el estado de la aplicación de manera segura"""
    # Guardar solo lo esencial
    essential_keys = ['selected_options']  # Mantener configuraciones básicas
    
    # Crear nuevo estado
    new_state = {
        'query_state': {
            'done': False,
            'table_data': None,
            'selected_nrcs': [],
            'selected_subjects': []
        },
        'expanded_data': pd.DataFrame(columns=[
            'Materia', 'NRC', 'Profesor', 'Días', 'Hora', 'Edificio', 'Aula'
        ]),
        'selected_options': st.session_state.get('selected_options', {}),
        'clases_seleccionadas': [], # Restablecer
        'cruces_detectados': {}     # Restablecer
    }
    
    # Limpiar y reconstruir el estado
    st.session_state.clear()
    st.session_state.update(new_state)
    
    # Limpiar archivos temporales de manera segura
    try:
        if os.path.exists('datos.json'):
            os.remove('datos.json')
    except Exception as e:
        logger.error(f"Error al eliminar archivo temporal: {str(e)}")
        # No es crítico, podemos continuar

def guardar_datos_local(data):
    """Guarda los datos en un archivo JSON"""
    try:
        with open('datos.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error al guardar datos: {str(e)}")
        st.error(f"Error al guardar datos: {str(e)}")
        st.error("No se pudo guardar la selección actual. Intenta nuevamente.")

def validate_data(df):
    """Valida que el DataFrame tenga la estructura esperada"""
    required_columns = ['Materia', 'NRC', 'Profesor', 'Días', 'Hora', 'Edificio', 'Aula']
    if not all(col in df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        raise ValueError(f"Faltan columnas requeridas: {missing}")
    if df.empty:
        raise ValueError("El DataFrame está vacío")

def mostrar_opciones_pdf(schedule_df):
    """Muestra opciones para ver y descargar el horario en formato PDF."""
    try:
        pdf_buffer = create_schedule_pdf(
            schedule_df,
            st.session_state.selected_options["ciclop"]["description"]
        )
        pdf_buffer.seek(0) # Asegúrate de que el buffer esté al inicio para su lectura

        # Opcion 1: Botón para descargar el PDF
        st.download_button(
            label="📄 Descargar PDF",
            data=pdf_buffer.getvalue(), # Usar .getvalue() para obtener los bytes
            file_name="mi_horario.pdf",
            mime="application/pdf",
            key="download_pdf_main_tab" # Añade un key único para este botón
        )

        st.markdown("---")
        st.subheader("👀 Vista Previa del Horario")
        
        # Opcion 2: Vista previa del PDF usando streamlit-pdf-viewer
        # Ajustar width al 100% y una altura fija (ej. 800px o más, según tu preferencia)
        # pdf_viewer(input=pdf_buffer.getvalue(), width="100%", height=650) 
        # NOTA: No puedes poner height="100%" directamente porque no funciona así en Streamlit/componentes HTML en este contexto.
        # Una altura fija generosa (como 800px o 1000px) es lo más común para que sea visible.

        pdf_buffer.seek(0) # Restablecer la posición del buffer si se va a usar de nuevo

        return pdf_buffer
    except Exception as e:
        logger.error(f"Error al generar PDF para previsualización: {str(e)}")
        st.error(f"Error al generar el horario PDF para previsualización: {str(e)}")
        return None

# --------------------------------------------------
# Interfaz de usuario
# --------------------------------------------------
with st.sidebar:
    st.title("⚙️ Opciones")
    st.markdown("---")
    if st.button("🔄 Nueva Consulta", use_container_width=True):
        reset_query_state()
        st.rerun()
    
    if st.session_state.selected_options.get("ciclop"):
        st.markdown(f"**Ciclo Actual:** {st.session_state.selected_options['ciclop']['description']}")
    
    st.markdown("---")
    st.markdown(f"**Versión:** {VERSION}")
    st.markdown(f"[Sitio Web]({URL_PAGINA})")

# Pestañas principales
tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ Consulta Inicial", 
    "2️⃣ Selección de Materias", 
    "3️⃣ Generar Horario",
    "📢 Feedback"
])

# --------------------------------------------------
# Contenido de las pestañas principales
# --------------------------------------------------
with tab1:
    st.markdown("## 📋 Consulta la Oferta Académica")
    
    form_options = fetch_form_options_cached(FORM_URL)
    if not form_options:
        st.stop()
    
    selected_options = {}
    for field, options in form_options.items():
        display_options = [f"{opt['value']} - {opt['description']}" for opt in options]
        selected = st.selectbox(f"Selecciona {field.replace('p', '')}:", display_options)
        value, desc = selected.split(" - ", 1)
        selected_options[field] = {"value": value, "description": desc}

    if "cup" in selected_options:
        try:
            carreras = show_abbreviations(selected_options["cup"]["value"])
            if carreras:
                selected_carrera = st.selectbox("Selecciona tu carrera:", 
                                                 [f"{k} - {v}" for k, v in carreras.items()])
                abrev, desc = selected_carrera.split(" - ", 1)
                selected_options["majrp"] = {"value": abrev, "description": desc}
                st.info("Asegurate de seleccionar el codigo de carrera correccto, ya que en algunos casos pueden existir mas de una clave para una misma carrera")
        except Exception as e:
            logger.error(f"Error al cargar carreras: {str(e)}")
            st.error("Error al cargar las carreras disponibles")

    if st.button("🔍 Consultar Oferta", type="primary"):
        if not selected_options.get("ciclop"):
            st.error("Debes seleccionar un ciclo")
        else:
            with st.status("Consultando datos...", expanded=True) as status:
                try:
                    post_data = build_post_data(selected_options)
                    table_data = fetch_table_data(POST_URL, post_data)
                    
                    if table_data is not None:
                        st.session_state.query_state.update({
                            "done": True,
                            "table_data": table_data
                        })
                        st.session_state.selected_options = selected_options
                        
                        # Procesar y validar datos
                        processed_data = process_data_from_web(table_data)
                        validate_data(processed_data)
                        
                        st.session_state.expanded_data = processed_data
                        
                        guardar_datos_local({
                            "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                            "ciclo": selected_options["ciclop"]["description"]
                        })
                        status.update(label="Consulta completada!", state="complete")
                        
                        st.success("""
                        ✅ Consulta exitosa!  
                        **Haz click en la pestaña '2️⃣ Selección de Materias'** para continuar.
                        """)
                except ValueError as e:
                    logger.error(f"Error de validación de datos: {str(e)}")
                    st.error(f"Error en los datos recibidos: {str(e)}")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error de conexión al consultar: {str(e)}")
                    st.error("Error de conexión al consultar los datos. Intenta nuevamente.")
                except Exception as e:
                    logger.error(f"Error inesperado al consultar: {str(e)}")
                    st.error(f"Error al consultar: {str(e)}")

with tab2:
    if not st.session_state.query_state.get('done'):
        st.warning("Primero realiza una consulta en la pestaña 'Consulta Inicial'")
    else:
        st.markdown("## 📚 Selección de Materias")
        
        if os.path.exists('datos.json'):
            try:
                datos = cargar_datos_desde_json()
                st.session_state.expanded_data = pd.DataFrame(datos.get("oferta_academica", []))
                st.session_state.query_state["selected_subjects"] = datos.get("materias_seleccionadas", [])
                st.session_state.query_state["selected_nrcs"] = datos.get("nrcs_seleccionados", [])
            except Exception as e:
                logger.error(f"Error al cargar datos: {str(e)}")
                st.error(f"Error al cargar datos guardados: {str(e)}")

        # Validar datos antes de continuar
        try:
            validate_data(st.session_state.expanded_data)
        except ValueError as e:
            st.error(f"Error en los datos: {str(e)}")
            st.error("Por favor, realiza una nueva consulta.")
            st.stop()

        materias = st.session_state.expanded_data["Materia"].unique()
        selected_subjects = st.multiselect(
            "Materias disponibles:",
            materias,
            default=st.session_state.query_state.get("selected_subjects", [])
        )

        if selected_subjects:
            st.session_state.query_state["selected_subjects"] = selected_subjects
            df_filtrado = st.session_state.expanded_data[
                st.session_state.expanded_data["Materia"].isin(selected_subjects)
            ].copy()
            
            # Optimizar operaciones con el DataFrame
            df_filtrado['Edificio_simple'] = df_filtrado['Edificio'].str[-1].fillna('')
            
            st.markdown("### 🔍 Grupos Disponibles")

            all_nrcs = []
            for materia in selected_subjects:
                with st.expander(f"📖 {materia}"):
                    grupos = df_filtrado[df_filtrado["Materia"] == materia]
                    
                    # Agrupar por NRC para mostrar todos los horarios
                    grupos_agrupados = grupos.groupby('NRC').agg({
                        'Profesor': 'first',
                        'Días': lambda x: ', '.join(x.astype(str)),
                        'Hora': lambda x: ', '.join(x.astype(str)),
                        'Edificio_simple': lambda x: ', '.join(x.astype(str)),
                        'Aula': lambda x: ', '.join(x.astype(str))
                    }).reset_index()
                    
                    # Crear descripción completa para cada NRC
                    descripciones_nrc = []
                    for _, row in grupos_agrupados.iterrows():
                        nrc_info = f"{row['NRC']} | {row['Profesor']} | "
                        
                        # Separar los diferentes horarios
                        dias = row['Días'].split(', ')
                        horas = row['Hora'].split(', ')
                        edificios = row['Edificio_simple'].split(', ')
                        aulas = row['Aula'].split(', ')
                        
                        horarios = []
                        for dia, hora, edificio, aula in zip(dias, horas, edificios, aulas):
                            horarios.append(f"{dia} {hora} ({edificio}-{aula})")
                        
                        nrc_info += " | ".join(horarios)
                        descripciones_nrc.append(nrc_info)
                    
                    # Mostrar multiselect con descripciones completas
                    seleccionados = st.multiselect(
                        f"Selecciona grupos para {materia}",
                        grupos_agrupados["NRC"].unique(),
                        format_func=lambda x: next((n for n in descripciones_nrc if str(x) in n.split(' | ')[0]), str(x)),
                        key=f"nrcs_{materia}",
                        default=[n for n in grupos_agrupados["NRC"] if n in st.session_state.query_state.get("selected_nrcs", [])]
                    )
                    all_nrcs.extend(seleccionados)
            
            # Solo si hay NRCs seleccionados, procedemos a guardar, generar vista previa y detectar cruces
            if all_nrcs:
                st.session_state.query_state['selected_nrcs'] = all_nrcs
                try:
                    guardar_datos_local({
                        "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                        "materias_seleccionadas": selected_subjects,
                        "nrcs_seleccionados": all_nrcs,
                        "ciclo": st.session_state.selected_options["ciclop"]["description"]
                    })
                    
                    # --------------------------------------------------
                    # CALCULAR Y ALMACENAR CLASES SELECCIONADAS Y CRUCES EN SESSION_STATE
                    # Esto DEBE hacerse antes de la Detección de Cruces y el Calendario
                    # --------------------------------------------------
                    st.session_state.clases_seleccionadas = crear_clases_desde_dataframe(
                        st.session_state.expanded_data[
                            st.session_state.expanded_data["NRC"].isin(all_nrcs)
                        ]
                    )
                    # Asumiendo que detectar_cruces devuelve un diccionario de {dia: [(Clase, Clase), ...]}
                    st.session_state.cruces_detectados = detectar_cruces(st.session_state.clases_seleccionadas)

                    # ---
                    ### **Detección de Cruces de Horario (Sección de Mensajes)**
                    # ---
                    st.markdown("---")
                    st.markdown("## 🔍 Detección de Cruces de Horario")
                    
                    if st.session_state.cruces_detectados:
                        st.error("🚨 Se detectaron los siguientes conflictos de horario:")
                        
                        # --- INICIO DEL CAMBIO CLAVE ---
                        # Usamos la función `generar_mensaje_cruces` de `Funciones/utils.py`
                        # para obtener los mensajes ya formateados.
                        mensajes_cruce = generar_mensaje_cruces(st.session_state.cruces_detectados)
                        for mensaje in mensajes_cruce:
                            st.markdown(mensaje) # Cada mensaje es una cadena de texto lista para mostrar.
                        # --- FIN DEL CAMBIO CLAVE ---
                        
                        st.warning("Por favor ajusta tus selecciones para resolver los conflictos")
                    else:
                        st.success("""
                        ✅ No se detectaron conflictos de horario!  
                        **Revisa la 'Vista Previa del Horario'** y luego haz click en la pestaña '3️⃣ Generar Horario'.
                        """)

                    # --------------------------------------------------
                    # Vista Previa y Visualización de Calendario Combinadas
                    # --------------------------------------------------
                    st.markdown("---")
                    st.markdown("## 📅 Vista Previa de tu Horario")
                    
                    # Crear DataFrame resumen
                    horario_preliminar = st.session_state.expanded_data[
                        st.session_state.expanded_data["NRC"].isin(all_nrcs)
                    ][['Materia', 'NRC', 'Días', 'Hora', 'Profesor', 'Edificio', 'Aula']]
                    
                    # Ordenar por días y hora para mejor visualización
                    dias_orden = {'Lunes': 0, 'Martes': 1, 'Miércoles': 2, 
                                  'Jueves': 3, 'Viernes': 4, 'Sábado': 5}
                    horario_preliminar['Dia_Orden'] = horario_preliminar['Días'].map(dias_orden)
                    horario_preliminar = horario_preliminar.sort_values(['Dia_Orden', 'Hora'])
                    
                    # Mostrar tabla con estilo
                    st.dataframe(
                    apply_dataframe_styles(
                        horario_preliminar,
                        st.session_state.cruces_detectados, # Pasar los cruces
                        st.session_state.clases_seleccionadas # Pasar las clases seleccionadas
                    ),
                    height=500,
                    use_container_width=True
                )
                    
                    # Integración de la Visualización de Calendario
                    st.markdown("---")
                    st.markdown("## 🗓️ Vista Previa del Horario")
                    try:
                        # Definir la lista de horas fijas exactamente como en schedule.py
                        hours_list_calendar = [
                            "07:00 AM - 07:59 AM", "08:00 AM - 08:59 AM", "09:00 AM - 09:59 AM", "10:00 AM - 10:59 AM",
                            "11:00 AM - 11:59 AM", "12:00 PM - 12:59 PM", "01:00 PM - 01:59 PM", "02:00 PM - 02:59 PM",
                            "03:00 PM - 03:59 PM", "04:00 PM - 04:59 PM", "05:00 PM - 05:59 PM", "06:00 PM - 06:59 PM",
                            "07:00 PM - 07:59 PM", "08:00 PM - 08:59 PM"
                        ]
                        days = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

                        # Crear el DataFrame del calendario con horas y días fijos
                        calendario = pd.DataFrame(index=hours_list_calendar, columns=days).fillna('')

                        # Rellenar el calendario con las clases seleccionadas
                        for clase_obj in st.session_state.clases_seleccionadas:
                            # --- INICIO DE LA CORRECCIÓN DE DÍAS ---
                            # Normalizar los días de la clase. Asumimos que clase_obj.dia es una cadena.
                            # Si es un solo día (ej. "Lunes"), lo ponemos en una lista.
                            # Si son varios días (ej. "Lunes, Miércoles"), los separamos y los ponemos en una lista.
                            clase_dias_raw = clase_obj.dia # Obtener el atributo 'dia'
                            
                            # Si es una cadena, intentar dividirla por comas o slash para obtener una lista de días
                            if isinstance(clase_dias_raw, str):
                                if ',' in clase_dias_raw:
                                    dias_de_esta_clase = [d.strip() for d in clase_dias_raw.split(',')]
                                elif '/' in clase_dias_raw:
                                    dias_de_esta_clase = [d.strip() for d in clase_dias_raw.split('/')]
                                else:
                                    dias_de_esta_clase = [clase_dias_raw.strip()]
                            elif isinstance(clase_dias_raw, list): # Si ya es una lista, usarla directamente
                                dias_de_esta_clase = [d.strip() for d in clase_dias_raw]
                            else:
                                # Manejar otros tipos de datos si es necesario (ej. si es None)
                                dias_de_esta_clase = []
                                st.warning(f"Formato de día inválido para la clase {clase_obj.materia}: {clase_dias_raw}")

                            # --- FIN DE LA CORRECCIÓN DE DÍAS ---

                            # Convertir las horas de la clase a formato de fecha y hora para comparación
                            try:
                                # Asumiendo que clase_obj.hora_inicio y hora_fin están en formato HH:MM (24h)
                                # y que los rangos de hours_list_calendar están en HH:MM AM/PM
                                class_start_dt = pd.to_datetime(clase_obj.hora_inicio, format="%H:%M")
                                class_end_dt = pd.to_datetime(clase_obj.hora_fin, format="%H:%M")
                            except ValueError:
                                st.warning(f"Formato de hora inválido para la clase {clase_obj.materia}: {clase_obj.hora_inicio}-{clase_obj.hora_fin}. No se mostrará correctamente en el calendario.")
                                continue # Saltar esta clase si las horas no son válidas

                            # Iterar por cada día que realmente tiene la clase (ahora ya es una lista)
                            for dia_clase in dias_de_esta_clase:
                                if dia_clase in days: # Asegurarse de que el día esté en las columnas del calendario
                                    # Iterar sobre cada intervalo de hora en el calendario
                                    for hour_range_str in hours_list_calendar:
                                        try:
                                            # Convertir el rango de horas del calendario a formato de fecha y hora
                                            interval_start_str, interval_end_str = hour_range_str.split(' - ')
                                            interval_start_dt = pd.to_datetime(interval_start_str, format="%I:%M %p")
                                            interval_end_dt = pd.to_datetime(interval_end_str, format="%I:%M %p")

                                            # Lógica de superposición de tiempo:
                                            # La clase se superpone con el intervalo si:
                                            # (inicio_clase < fin_intervalo) AND (fin_clase > inicio_intervalo)
                                            if class_start_dt < interval_end_dt and class_end_dt > interval_start_dt:
                                                # Contenido a añadir a la celda
                                                new_content = (
                                                    f"{clase_obj.materia}\n"
                                                    f"(NRC: {clase_obj.nrc})\n"
                                                    f"({clase_obj.edificio}-{clase_obj.aula})"
                                                )
                                                
                                                current_cell_content = calendario.loc[hour_range_str, dia_clase]
                                                if pd.isna(current_cell_content) or current_cell_content == '':
                                                    calendario.loc[hour_range_str, dia_clase] = new_content
                                                else:
                                                    # Si ya hay contenido, añadir un separador y el nuevo contenido
                                                    calendario.loc[hour_range_str, dia_clase] += f"\n---\n{new_content}"
                                        except ValueError:
                                            # Esto puede ocurrir si un rango de hour_list_calendar no se parsea bien
                                            st.warning(f"Error interno al parsear el intervalo de hora del calendario: {hour_range_str}")
                                            continue

                        # Mostrar el DataFrame con los estilos
                        st.dataframe(
                            apply_dataframe_styles_with_cruces(
                                calendario.fillna(''), 
                                st.session_state.cruces_detectados,
                                st.session_state.clases_seleccionadas
                            ), 
                            height=min(600, 50 + 45 * len(hours_list_calendar)), # Altura dinámica
                            use_container_width=True
                        )
                    except Exception as e:
                        st.warning(f"No se pudo generar el calendario visual. Error: {str(e)}")
                        st.exception(e) # Mostrar la excepción completa para depuración
                    
                except Exception as e:
                    logger.error(f"Error al guardar selección o generar vistas: {str(e)}")
                    st.error(f"No se pudo guardar tu selección o generar vistas. Intenta nuevamente: {str(e)}")
            else:
                st.info("Selecciona al menos un grupo para ver la vista previa del horario y detectar cruces.")

with tab3:
    if not st.session_state.query_state.get('done'):
        st.warning("Por favor completa primero la consulta en la pestaña '1️⃣ Consulta Inicial'")
    elif not st.session_state.query_state.get('selected_nrcs'):
        st.info("Selecciona materias y grupos en la pestaña '2️⃣ Selección de Materias'")
    else:
        st.markdown("## 🗓️ Vista Previa del Horario")
        
        try:
            # Validar datos antes de generar el horario
            validate_data(st.session_state.expanded_data)
            
            schedule_df = create_schedule_sheet(
                st.session_state.expanded_data[
                    st.session_state.expanded_data["NRC"].isin(st.session_state.query_state['selected_nrcs'])
                ]
            )
            
            pdf_buffer = mostrar_opciones_pdf(schedule_df)
            
            st.markdown("---")
            st.markdown("### 💾 Descargar Horario")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if pdf_buffer:
                    st.download_button(
                        label="📄 Descargar PDF",
                        data=pdf_buffer,
                        file_name="mi_horario.pdf",
                        mime="application/pdf",
                        key="download_pdf"
                    )
            
            with col2:
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    schedule_df.to_excel(writer, sheet_name='Horario', index=False)
                excel_buffer.seek(0)
                st.download_button(
                    label="📊 Descargar Excel",
                    data=excel_buffer,
                    file_name="mi_horario.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_excel"
                )
            
            with col3:
                json_data = {
                    "horario": schedule_df.to_dict(orient='records'),
                    "materias": st.session_state.query_state.get("selected_subjects", []),
                    "nrcs": st.session_state.query_state.get("selected_nrcs", []),
                    "ciclo": st.session_state.selected_options["ciclop"]["description"]
                }
                json_buffer = BytesIO()
                json_buffer.write(json.dumps(json_data, indent=2).encode('utf-8'))
                json_buffer.seek(0)
                st.download_button(
                    label="📝 Descargar JSON",
                    data=json_buffer,
                    file_name="mi_horario.json",
                    mime="application/json",
                    key="download_json"
                )
            
            try:
                guardar_datos_local({
                    "oferta_academica": st.session_state.expanded_data.to_dict(orient='records'),
                    "materias_seleccionadas": st.session_state.query_state.get("selected_subjects", []),
                    "nrcs_seleccionados": st.session_state.query_state.get("selected_nrcs", []),
                    "horario_generado": schedule_df.to_dict(orient='records'),
                    "ciclo": st.session_state.selected_options["ciclop"]["description"]
                })
            except Exception as e:
                logger.error(f"Error al guardar horario: {str(e)}")
                st.error("No se pudo guardar el horario generado")
            
        except ValueError as e:
            st.error(f"Error en los datos: {str(e)}")
            st.error("No se pudo generar el horario debido a problemas en los datos.")
        except Exception as e:
            logger.error(f"Error al generar el horario: {str(e)}")
            st.error(f"Error al generar el horario: {str(e)}")

# --------------------------------------------------
# Pestaña de Feedback
# --------------------------------------------------
with tab4:
    st.markdown("## 📢 Feedback y Sugerencias")
    components.iframe(form_url, height=800, scrolling=True)

# --------------------------------------------------
# Footer de la aplicación
# --------------------------------------------------
st.markdown(
    f"""
    <div style="text-align: center; margin-top: 50px; padding: 20px; color: #666; font-size: 0.8rem;">
        <p>Generador de Horarios UDG | Versión {VERSION}</p>
        <p>Desarrollado con Python 🐍 y Streamlit ❤️</p>
        <p><a href="{URL_PAGINA}" target="_blank">Visita nuestro sitio web</a></p>
    </div>
    """,
    unsafe_allow_html=True
)