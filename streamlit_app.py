import streamlit as st
import pandas as pd
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, FORM_URL, POST_URL
from Funciones.data_processing import fetch_table_data, process_data_from_web
from Funciones.schedule import create_schedule_sheet, create_schedule_image

# Inicialización del estado en la sesión.
if "query_state" not in st.session_state:
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}

def reset_query_state():
    """Restablece el estado para una nueva consulta."""
    st.session_state["query_state"] = {"done": False, "table_data": None, "selected_nrcs": []}

# Consulta inicial.
if not st.session_state["query_state"]["done"]:
    st.title("Generador de Horarios")

    form_options = fetch_form_options_with_descriptions(FORM_URL)

    if form_options:
        selected_options = {}

        for field, options in form_options.items():
            values = [opt["value"] for opt in options]
            selected_value = st.selectbox(f"Selecciona una opción para {field}:", values)

            if selected_value:
                selected_options[field] = {"value": selected_value}

        carrera_input = st.text_input("Ingresa el valor de la carrera (majrp):")
        if carrera_input:
            selected_options["majrp"] = {"value": carrera_input}

        st.write("Opciones seleccionadas:")
        st.json({key: value["value"] for key, value in selected_options.items()})

        if st.button("Consultar"):
            if "ciclop" not in selected_options or not selected_options["ciclop"]["value"]:
                st.error("Debes seleccionar un ciclo antes de continuar.")
            else:
                post_data = build_post_data(selected_options)
                table_data = fetch_table_data(POST_URL, post_data)

                if table_data is not None and not table_data.empty:
                    st.session_state["query_state"]["done"] = True
                    st.session_state["query_state"]["table_data"] = table_data
                    st.session_state["query_state"]["selected_nrcs"] = [] #Reiniciamos la lista de NRCs
                    st.rerun() #Se mantiene el rerun para actualizar la interfaz a la siguiente parte
                else:
                    st.warning("No se encontraron datos para las opciones seleccionadas.")
else:
    table_data = st.session_state["query_state"]["table_data"]

    if "expanded_data" not in st.session_state or not st.session_state.expanded_data.equals(table_data):
        st.session_state.expanded_data = process_data_from_web(table_data)

    expanded_data = st.session_state.expanded_data

    # Manejo simplificado del multiselect usando la clave
    st.multiselect(
        "Selecciona los NRC:",
        options=expanded_data["NRC"].unique().tolist(),
        default=st.session_state["query_state"]["selected_nrcs"],
        key="nrc_multiselect"  # Clave esencial
    )

    # Acceso directo a los NRC seleccionados usando la clave
    selected_nrcs = st.session_state.nrc_multiselect

    if st.button("Generar horario"):
        if selected_nrcs:
            filtered_data = expanded_data[expanded_data["NRC"].isin(selected_nrcs)]
            if not filtered_data.empty:
                schedule = create_schedule_sheet(filtered_data)
                st.write("Horario generado:")
                st.dataframe(schedule)
                schedule_image_buf = create_schedule_image(schedule)
                st.image(schedule_image_buf)
                st.download_button(
                    label="Descargar horario como imagen",
                    data=schedule_image_buf,
                    file_name="horario.png",
                    mime="image/png",
                )
            else:
                st.warning("No se pudo generar el horario con los NRC seleccionados.")
        else:
            st.warning("Selecciona al menos un NRC.")

    if st.button("Nueva consulta"):
        reset_query_state()
        st.rerun() #Se mantiene el rerun para reiniciar la app