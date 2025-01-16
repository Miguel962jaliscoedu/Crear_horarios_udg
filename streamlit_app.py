# streamlit_app.py
import os
import pandas as pd
import streamlit as st
from Diseño.styles import apply_dataframe_styles, set_page_style, apply_dataframe_styles_with_cruces,get_reportlab_styles
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf
from Funciones.data_processing import fetch_table_data, process_data_from_web
from Funciones.utils import Clase, hay_cruce, detectar_cruces, crear_clases_desde_dataframe, generar_mensaje_cruces
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, show_abbreviations,FORM_URL, POST_URL

VERSION = os.environ.get("VERSION", "Version de desarrollo")
URL_PAGINA = os.environ.get("URL_PAGINA","Web de desarrollo")

# Configuración de la página y estilos generales
st.set_page_config(
    page_title="Generador de Horarios",
    page_icon="",
    layout="wide",
)
set_page_style()

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
            post_data = build_post_data(selected_options)
            table_data = fetch_table_data(POST_URL, post_data)

            if table_data is not None and not table_data.empty:
                st.session_state["query_state"]["done"] = True
                st.session_state["query_state"]["table_data"] = table_data
                st.session_state["query_state"]["selected_nrcs"] = []
                st.session_state.selected_options = selected_options
                st.rerun()
            else:
                st.warning("No se encontraron datos para las opciones seleccionadas.")
else:
    st.error("No se pudieron obtener las opciones del formulario")

if st.session_state["query_state"]["done"]:
    table_data = st.session_state["query_state"]["table_data"]
    if table_data is not None and not table_data.empty:
        if st.session_state.expanded_data.empty or not st.session_state.expanded_data.equals(table_data):
            st.session_state.expanded_data = process_data_from_web(table_data)

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

            if st.button("Generar horario", use_container_width=True):
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
                                    pdf_base64 = create_schedule_pdf(schedule, ciclo, as_base64=True)
                                    pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="800" type="application/pdf"></iframe>'
                                    st.markdown(pdf_display, unsafe_allow_html=True)

                                    styles_pdf = get_reportlab_styles()
                                    pdf_buffer = create_schedule_pdf(schedule, ciclo, URL_PAGINA)
                                    #st.download_button(
                                        #label="Descargar Horario (PDF)",
                                        #data=pdf_buffer,
                                        #file_name="horario.pdf",
                                        #mime="application/pdf",
                                    )
                                    #pdf_buffer.close()
                                #except #Exception as e:
                                    #st.error(f"Ocurrió un error al generar el PDF: {e}")
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

        else:
            st.warning("Selecciona al menos una materia, ya que no se encontraron las columnas 'Materia' o 'NRC' en los datos procesados.")
    else:
        st.warning("No se han obtenido datos de la consulta inicial. Realiza una consulta primero.")

if st.button("Nueva consulta", use_container_width=True):
    reset_query_state()
    st.rerun()

st.markdown(
    f"""
    <div class="footer">
        Desarrollado con la ayuda de IA (ChatGPT y Gemini) | Versión: {VERSION}
    </div>
    """,
    unsafe_allow_html=True,
)