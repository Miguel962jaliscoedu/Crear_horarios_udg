# main.py
import os
import json
import base64
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from Diseño.styles import apply_dataframe_styles, set_page_style, apply_dataframe_styles_with_cruces,get_reportlab_styles
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf
from Funciones.data_processing import fetch_table_data, process_data_from_web, cargar_datos_desde_json, guardar_datos_local
from Funciones.utils import detectar_cruces, crear_clases_desde_dataframe, generar_mensaje_cruces
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, show_abbreviations,FORM_URL, POST_URL
from Funciones.drive_utils import get_drive_service, guardar_en_drive

VERSION = os.environ.get("VERSION", "Version de desarrollo")
URL_PAGINA = os.environ.get("URL_PAGINA","Web de desarrollo")
form_url = "https://docs.google.com/forms/d/e/1FAIpQLScc5fCcNo9ZocfuqDhJD5QOdbdTNP_RnUhTYAzkEIEFHIB2rA/viewform?embedded=true"

# Configuración de la página y estilos generales
st.set_page_config(
    page_title="Generador de Horarios",
    page_icon="",
    layout="wide",
)
set_page_style()

@st.cache_data  # Caching para mejorar el rendimiento
def get_academic_offer(selected_options_json):
    selected_options = json.loads(selected_options_json)
    post_data = build_post_data(selected_options)
    table_data = fetch_table_data(POST_URL, post_data)
    if table_data is not None and not table_data.empty:
        expanded_data = process_data_from_web(table_data)
        return expanded_data.to_json(orient="records")  # Devuelve JSON
    return None

@st.cache_data
def generate_schedule(selected_nrcs_json, selected_options_json):
    selected_nrcs = json.loads(selected_nrcs_json)
    selected_options = json.loads(selected_options_json)
    ciclo = selected_options.get("ciclop", {}).get("description")
    expanded_data = pd.read_json(st.session_state.get("api_data")) #lee los datos del estado de la sesion
    if selected_nrcs:
        filtered_data = expanded_data[expanded_data["NRC"].isin(selected_nrcs)]
        if not filtered_data.empty:
            schedule = create_schedule_sheet(filtered_data)
            return schedule.to_json(orient="records") if schedule is not None and not schedule.empty else None
    return None

# Título principal
st.markdown("<h1 style='text-align: center;'>📅Crea tu horario de clases ‎ </h1>", unsafe_allow_html=True)
st.markdown("---")

# Inicialización del estado de la sesión
if "query_state" not in st.session_state:
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}
if "expanded_data" not in st.session_state:
    st.session_state.expanded_data = pd.DataFrame()
if "selected_options" not in st.session_state:
    st.session_state.selected_options = {}

def reset_query_state():
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}
    st.session_state.expanded_data = pd.DataFrame()
    if os.path.exists('datos.json'): #eliminar el archivo json para evitar errores con los datos
        os.remove('datos.json')


# Consulta inicial
st.subheader("Consulta la Oferta Academica:")

form_options = fetch_form_options_with_descriptions(FORM_URL)
selected_options = {}

if form_options:
    for field, options in form_options.items():
        display_options = [f"{option['value']} - {option['description']}" for option in options]
        selected_display_option = st.selectbox(f"Selecciona una opción para {field}:", display_options)
        selected_value = selected_display_option.split(" - ")[0]
        selected_description = selected_display_option.split(" - ")[1]
        selected_options[field] = {"value": selected_value, "description": selected_description}

    if "cup" in selected_options:
        carreras_dict = show_abbreviations(selected_options["cup"]["value"])
        if carreras_dict:
            display_carreras = [f"{abreviatura} - {descripcion}" for abreviatura, descripcion in carreras_dict.items()]
            selected_display_carrera = st.selectbox("Selecciona la carrera:", display_carreras)
            st.warning("Asegúrate de seleccionar la opción CORRECTA para la carrera, ya que algunos centros universitarios tienen claves de carrera DUPLICADAS.")
            selected_carrera_abreviatura = selected_display_carrera.split(" - ")[0]
            selected_carrera_descripcion = selected_display_carrera.split(" - ")[1]
            selected_options["majrp"] = {"value": selected_carrera_abreviatura, "description": selected_carrera_descripcion}
        else:
            st.warning("No se pudieron obtener las carreras.")

    if st.button("Consultar", use_container_width=True):
        if "ciclop" not in selected_options or not selected_options["ciclop"]["value"]:
            st.error("Debes seleccionar un ciclo antes de continuar.")
        else:
            with st.spinner("Consultando la información..."): #Indicador de carga
                post_data = build_post_data(selected_options)
                table_data = fetch_table_data(POST_URL, post_data)

                if table_data is not None and not table_data.empty:
                    st.session_state["query_state"]["done"] = True
                    st.session_state["query_state"]["table_data"] = table_data
                    st.session_state["query_state"]["selected_nrcs"] = []
                    st.session_state.selected_options = selected_options
                    st.session_state.expanded_data = process_data_from_web(table_data) #Procesar y guardar en json
                    data_to_save = {
                        "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                        "materias_seleccionadas": [],  # Inicializar listas vacías
                        "nrcs_seleccionados": [],
                        "horario_generado": None,
                        "ciclo": st.session_state.selected_options["ciclop"]["description"] if 'selected_options' in st.session_state and 'ciclop' in st.session_state.selected_options and 'description' in st.session_state.selected_options['ciclop'] else None
                    }
                    guardar_datos_local(data_to_save) #Guardar los datos localmente

                    st.rerun()
                else:
                    st.warning("No se encontraron datos para las opciones seleccionadas.")
else:
    st.error("No se pudieron obtener las opciones del formulario")

if st.session_state["query_state"]["done"]:  # Se ejecuta DESPUÉS de la consulta
    if os.path.exists('datos.json'):  # Verifica si existe el archivo JSON
        with open('datos.json', 'r', encoding='utf-8') as f:
            try:
                loaded_data = cargar_datos_desde_json() #Cargar los datos con la función modificada
                st.session_state.expanded_data = pd.DataFrame(loaded_data.get("oferta_academica",[])) #Extraer la oferta academica
                selected_subjects = loaded_data.get("materias_seleccionadas",[]) #Extraer las materias seleccionadas
                selected_nrcs = loaded_data.get("nrcs_seleccionados",[]) #Extraer los NRC seleccionados
                schedule = pd.DataFrame(loaded_data.get("horario_generado",[])) if loaded_data.get("horario_generado") else None #Extraer el horario generado
                st.session_state["query_state"]["done"] = True
                st.session_state["query_state"]["selected_nrcs"] = selected_nrcs
                if selected_subjects: #Para mostrar las materias seleccionadas al cargar
                    filtered_by_subject = st.session_state.expanded_data[st.session_state.expanded_data["Materia"].isin(selected_subjects)]
                    if not filtered_by_subject.empty:
                        st.subheader("Información de las Materias Seleccionadas:")
                        styled_subject_df = apply_dataframe_styles(filtered_by_subject.reset_index(drop=True))
                        st.dataframe(styled_subject_df)
                if selected_nrcs: #Para mostrar los NRC seleccionados al cargar
                    filtered_by_nrc = filtered_by_subject[filtered_by_subject["NRC"].isin(selected_nrcs)]
                    columns_to_show = [col for col in filtered_by_nrc.columns if col != "Sesión"]
                    if not filtered_by_nrc.empty:
                        try:
                            clases_seleccionadas = crear_clases_desde_dataframe(filtered_by_nrc)
                            cruces = detectar_cruces(clases_seleccionadas)
                            styled_nrc_df = apply_dataframe_styles_with_cruces(filtered_by_nrc[columns_to_show].reset_index(drop=True), cruces)
                            st.dataframe(styled_nrc_df, hide_index=True) # Oculta el índice directamente
                            if cruces:
                                st.warning("Se detectaron cruces de horario (resaltados en la tabla):")
                                mensajes_cruces = generar_mensaje_cruces(cruces) # Obtener los mensajes formateados
                                for mensaje in mensajes_cruces: # Mostrar los mensajes
                                    st.write(mensaje)
                            else:
                                st.success("No se detectaron cruces de horario.")
                        except (ValueError, KeyError, Exception) as e:
                            st.error(f"Error en la detección de cruces: {e}")
                            st.stop()
                    else:
                        st.warning("No se encontraron materias con los NRC seleccionados.")

            except json.JSONDecodeError as e:
                st.error(f"Error al decodificar el archivo JSON: {e}")
            except Exception as e:
                st.error(f"Error al cargar datos guardados: {e}")
    expanded_data = st.session_state.expanded_data

    if "Materia" in expanded_data.columns and "NRC" in expanded_data.columns:
        st.subheader("Selecciona las Materias que deseas incluir en tu horario:")
        unique_subjects = expanded_data["Materia"].unique().tolist()
        selected_subjects = st.multiselect("Seleccionar Materias", options=unique_subjects)

        filtered_by_subject = expanded_data.copy()
        if selected_subjects:
            filtered_by_subject = expanded_data[expanded_data["Materia"].isin(selected_subjects)]
        
        if not filtered_by_subject.empty:
            st.subheader("Información de las Materias Seleccionadas:")
            styled_subject_df = apply_dataframe_styles(filtered_by_subject.reset_index(drop=True))
            st.dataframe(styled_subject_df)

        st.subheader("Selecciona las clases que deseas incluir en tu horario:")
        unique_nrcs = filtered_by_subject["NRC"].unique().tolist()
        selected_nrcs = st.multiselect(
            "Selecciona los NRC:",
            options=unique_nrcs,
            default=st.session_state["query_state"]["selected_nrcs"],
            key="nrc_multiselect"
        )

        if selected_nrcs:
            filtered_by_nrc = filtered_by_subject[filtered_by_subject["NRC"].isin(selected_nrcs)]
            columns_to_show = [col for col in filtered_by_nrc.columns if col != "Sesión"]

            if not filtered_by_nrc.empty:
            # ... (mostrar tabla)
                try:
                    clases_seleccionadas = crear_clases_desde_dataframe(filtered_by_nrc)
                    cruces = detectar_cruces(clases_seleccionadas)

                    styled_nrc_df = apply_dataframe_styles_with_cruces(filtered_by_nrc[columns_to_show].reset_index(drop=True), cruces)
                    st.dataframe(styled_nrc_df, hide_index=True) # Oculta el índice directamente

                    if cruces:
                        st.warning("Se detectaron cruces de horario (resaltados en la tabla):")
                        mensajes_cruces = generar_mensaje_cruces(cruces) # Obtener los mensajes formateados
                        for mensaje in mensajes_cruces: # Mostrar los mensajes
                            st.write(mensaje)
                    else:
                        st.success("No se detectaron cruces de horario.")

                except (ValueError, KeyError, Exception) as e:
                    st.error(f"Error en la detección de cruces: {e}")
                    st.stop()
            else:
                st.warning("No se encontraron materias con los NRC seleccionados.")
        else:
            st.write("Selecciona al menos un NRC para ver las materias correspondientes.")

        if st.button("Generar horario", use_container_width=True): #Seccion para generar el horario (DESPUÉS DE LA SELECCIÓN DE NRCs)
            if 'selected_options' in st.session_state and 'ciclop' in st.session_state.selected_options and 'description' in st.session_state.selected_options['ciclop']:
                ciclo = st.session_state.selected_options["ciclop"]["description"]
                if selected_nrcs:
                    filtered_data = expanded_data[expanded_data["NRC"].isin(selected_nrcs)]
                    if not filtered_data.empty:
                        schedule = create_schedule_sheet(filtered_data)
                        st.write("Horario generado:")
                        if schedule is not None and not schedule.empty:
                            styled_schedule_df = apply_dataframe_styles(schedule)
                            st.dataframe(styled_schedule_df)
                            try:
                                styles_pdf = get_reportlab_styles()
                                pdf_buffer = create_schedule_pdf(schedule, ciclo)

                                pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')

                                st.markdown(f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="700" height="1000"></iframe>', unsafe_allow_html=True)

                                pdf_buffer.seek(0)
                                st.download_button(
                                    label="Descargar Horario",
                                    data=pdf_buffer,
                                    file_name="horario.pdf",
                                    mime="application/pdf"
                                )

                            except Exception as e:
                                st.error(f"Ocurrió un error: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            st.warning("No se pudo generar el horario. Verifica los datos.")
                    else:
                        st.warning("No hay datos para generar el horario con los NRCs seleccionados.")
                else:
                    st.warning("Selecciona al menos un NRC.")
            else:
                st.error("No se pudo obtener la información del ciclo. Por favor, realiza una nueva consulta.")
            data_to_save = {
                "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                "materias_seleccionadas": selected_subjects,
                "nrcs_seleccionados": selected_nrcs,
                "horario_generado": schedule.to_dict(orient="records") if schedule is not None and not schedule.empty else None,
                "ciclo": st.session_state.selected_options["ciclop"]["description"] if 'selected_options' in st.session_state and 'ciclop' in st.session_state.selected_options and 'description' in st.session_state.selected_options['ciclop'] else None
        }
            guardar_datos_local(data_to_save)

        #if st.checkbox("Guardar en Google Drive"):
            #service = get_drive_service()
            #if service:
                #nombre_archivo = f"horario_{data_to_save['ciclo']}.json" if data_to_save['ciclo'] else "horario.json"
                #id_archivo = guardar_en_drive(service, nombre_archivo, data_to_save)
                #if id_archivo:
                    #st.write(f"Puedes acceder a tu archivo en: https://drive.google.com/file/d/{id_archivo}/view?usp=sharing")
            #else:
                #st.error("No se pudo conectar con Google Drive. Revisa las credenciales.")

# Sección para el botón "Nueva consulta" (AL FINAL DEL ARCHIVO, ANTES DEL FOOTER)
if st.button("Nueva consulta", use_container_width=True):
    reset_query_state()
    st.rerun()

#Formulario Sugerencias
with st.expander("📝 Hacer una sugerencia o queja"):
    components.iframe(form_url, height=600, scrolling=True)

# --- Secciones de la API ---

# Ocultar la interfaz principal de Streamlit si se llama a un endpoint de la API
if st.query_params:
    if "endpoint" in st.query_params:
        endpoint = st.query_params["endpoint"][0]

        if endpoint == "get_academic_offer":
            selected_options_json = st.query_params.get("selected_options", [None])[0] #obtener los parametros
            if selected_options_json:
                academic_offer = get_academic_offer(selected_options_json)
                if academic_offer:
                    st.write(academic_offer) #devuelve la info
                else:
                    st.write(json.dumps({"error": "No se encontraron datos"}))
            else:
                st.write(json.dumps({"error": "Faltan parametros"}))

        elif endpoint == "generate_schedule":
            selected_nrcs_json = st.query_params.get("selected_nrcs", [None])[0]
            selected_options_json = st.query_params.get("selected_options", [None])[0]
            if selected_nrcs_json and selected_options_json:
                schedule_data = generate_schedule(selected_nrcs_json, selected_options_json)
                if schedule_data:
                    st.write(schedule_data)
                else:
                    st.write(json.dumps({"error": "No se pudo generar el horario"}))
            else:
                st.write(json.dumps({"error": "Faltan parametros"}))

        st.stop() # Detener la ejecución de Streamlit para que solo se muestre la respuesta de la API

#-----------------END-API-----------------

# Footer (AL FINAL DEL ARCHIVO)
st.markdown(
    f"""
    <div class="footer">
        Desarrollado con la ayuda de IA (ChatGPT y Gemini) | Versión: {VERSION} | <a href="{URL_PAGINA}" target="_blank">https://crear-horarios-udg.streamlit.app/</a>
    </div>
    """,
    unsafe_allow_html=True,
)
