#streamlit_app.py

import streamlit as st
import pandas as pd
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, show_abbreviations,FORM_URL, POST_URL
from Funciones.data_processing import fetch_table_data, process_data_from_web
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf

# Configuración de la página
st.set_page_config(
    page_title="Generador de Horarios",
    page_icon="📅",  # Icono de calendario
    layout="wide",  # Diseño ancho para aprovechar el espacio
)

# Título principal con mejor formato
st.title("Generador de Horarios ")
st.markdown("---") # Separador visual

# Inicialización del estado en la sesión (sin cambios)
if "query_state" not in st.session_state:
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}
if "expanded_data" not in st.session_state:
    st.session_state.expanded_data = pd.DataFrame()

def reset_query_state():
    """Restablece el estado para una nueva consulta."""
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}
    st.session_state.expanded_data = pd.DataFrame()

# Consulta inicial
if not st.session_state["query_state"]["done"]:
    st.subheader("Selecciona los parámetros de la consulta:") # Subtítulo

    form_options = fetch_form_options_with_descriptions(FORM_URL)

    if form_options:
        selected_options = {}

        for field, options in form_options.items():
            options_dict = {option["description"]: option["value"] for option in options}
            selected_description = st.selectbox(f"Selecciona una opción para {field}:", options_dict.keys())
            selected_value = options_dict[selected_description]
            selected_options[field] = {"value": selected_value, "description": selected_description}

        if "cup" in selected_options:
            carreras_dict = show_abbreviations(selected_options["cup"]["value"])
            if carreras_dict:
                selected_carrera_description = st.selectbox("Selecciona la carrera:", list(carreras_dict.values()))
                st.warning("Asegúrate de seleccionar la opción CORRECTA para la carrera, ya que algunos centros universitarios tienen claves de carrera DUPLICADAS.")
                selected_carrera_abreviatura = list(carreras_dict.keys())[list(carreras_dict.values()).index(selected_carrera_description)]
                selected_options["majrp"] = {"value": selected_carrera_abreviatura, "description": selected_carrera_description}
            else:
                st.warning("No se pudieron obtener las carreras.")

        if st.button("Consultar", use_container_width=True): # Botón a ancho completo
            if "ciclop" not in selected_options or not selected_options["ciclop"]["value"]:
                st.error("Debes seleccionar un ciclo antes de continuar.")
            else:
                post_data = build_post_data(selected_options)
                table_data = fetch_table_data(POST_URL, post_data)

                if table_data is not None and not table_data.empty:
                    st.session_state["query_state"]["done"] = True
                    st.session_state["query_state"]["table_data"] = table_data
                    st.session_state["query_state"]["selected_nrcs"] = []
                    st.rerun()
                else:
                    st.warning("No se encontraron datos para las opciones seleccionadas.")
    else:
        st.error("No se pudieron obtener las opciones del formulario. Verifica la URL.")
else:
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

            st.subheader("Información de las Materias Seleccionadas:")
            st.dataframe(filtered_by_subject.reset_index(drop=True)) # Tabla con estilo

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
                st.subheader("Clases seleccionadas:")
                columns_to_show = [col for col in filtered_by_nrc.columns if col != "Sesión"]
                if not filtered_by_nrc.empty:
                    st.dataframe(filtered_by_nrc[columns_to_show].reset_index(drop=True)) # Tabla con estilo
                else:
                    st.warning("No se encontraron materias con los NRC seleccionados.")
            else:
                st.write("Selecciona al menos un NRC para ver las materias correspondientes.")

            if st.button("Generar horario", use_container_width=True): # Botón a ancho completo
                if selected_nrcs:
                    filtered_data = expanded_data[expanded_data["NRC"].isin(selected_nrcs)]
                    if not filtered_data.empty:
                        schedule = create_schedule_sheet(filtered_data)
                        st.write("Horario generado:")
                        if schedule is not None and not schedule.empty:
                            st.dataframe(schedule)
                            try: #Manejo de errores al generar el pdf
                                pdf_buffer = create_schedule_pdf(schedule)
                                st.download_button(
                                    label="Descargar Horario (PDF)",
                                    data=pdf_buffer.getvalue(),
                                    file_name="horario.pdf",
                                    mime="application/pdf",
                                )
                                pdf_buffer.close()
                            except Exception as e:
                                st.error(f"Ocurrió un error al generar el PDF: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            st.warning("No se pudo generar el horario. Verifica los datos.")
                    else:
                        st.warning("No hay datos para generar el horario con los NRCs seleccionados.")
                else:
                    st.warning("Selecciona al menos un NRC.")
        else:
            st.warning("Selecciona al menos una materia, ya que no se encontraron las columnas 'Materia' o 'NRC' en los datos procesados.")
    else:
        st.warning("No se han obtenido datos de la consulta inicial. Realiza una consulta primero.")

    if st.button("Nueva consulta", use_container_width=True): # Botón a ancho completo
        reset_query_state()
        st.rerun()