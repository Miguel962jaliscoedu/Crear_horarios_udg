# main.py

import streamlit as st
import pandas as pd
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data
from Funciones.data_processing import fetch_table_data, process_data_from_web
from Funciones.schedule import create_schedule_sheet, create_schedule_image
from Funciones.utils import clean_days

# Función principal
def main():
    st.title("Generador de Horarios")

    form_options = fetch_form_options_with_descriptions(FORM_URL)
    if form_options:
        selected_options = {}
        for field, options in form_options.items():
            descriptions = [opt['description'] for opt in options]
            values = [opt['value'] for opt in options]
            selected_description = st.selectbox(f"Selecciona una opción para {field}:", descriptions)
            if selected_description:
                index = descriptions.index(selected_description)
                selected_value = values[index]
                selected_options[field] = {"value": selected_value}

        carrera_input = st.text_input("Ingresa el valor de la carrera (majrp):")
        if carrera_input:
            selected_options["majrp"] = {"value": carrera_input}

        st.write("Opciones seleccionadas:")
        st.json({key: value["value"] for key, value in selected_options.items()})

        if st.button("Consultar y generar horario"):
            if "ciclop" not in selected_options or not selected_options["ciclop"]["value"]:
                st.error("Debes seleccionar un ciclo antes de continuar.")
            else:
                post_data = build_post_data(selected_options)
                table_data = fetch_table_data(POST_URL, post_data)

                if table_data is not None and not table_data.empty:
                    st.write("Datos obtenidos de la página:")
                    st.dataframe(table_data)

                    expanded_data = process_data_from_web(table_data)

                    if "selected_nrcs" not in st.session_state:
                        st.session_state["selected_nrcs"] = []

                    selected_nrcs = st.multiselect(
                        "Selecciona los NRC de las materias que deseas incluir:",
                        options=expanded_data["NRC"].unique().tolist(),
                        default=st.session_state["selected_nrcs"],
                    )

                    if selected_nrcs != st.session_state["selected_nrcs"]:
                        st.session_state["selected_nrcs"] = selected_nrcs

                    filtered_data = expanded_data[expanded_data["NRC"].isin(st.session_state["selected_nrcs"])]
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

if __name__ == "__main__":
    main()