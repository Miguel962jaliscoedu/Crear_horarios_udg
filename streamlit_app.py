import streamlit as st
import pandas as pd
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, FORM_URL, POST_URL
from Funciones.data_processing import fetch_table_data, process_data_from_web
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf

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

        carrera_input = st.text_input("Ingresa la abrebiatura de la carrera:")
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

    if "Materia" in expanded_data.columns and "NRC" in expanded_data.columns:
        # 1. Filtrar por Materia (ahora multiselect)
        st.write("### Selecciona las Materias que deseas incluir en tu horario:")
        unique_subjects = expanded_data["Materia"].unique().tolist()
        selected_subjects = st.multiselect("Seleccionar Materias", options=unique_subjects)

        filtered_by_subject = expanded_data.copy()

        if selected_subjects:
            filtered_by_subject = expanded_data[expanded_data["Materia"].isin(selected_subjects)]

            # 2. Mostrar la tabla de Materias (con toda la información de expanded_data)
            st.write("### Información de las Materias Seleccionadas:")
            st.dataframe(filtered_by_subject.reset_index(drop=True))

            # 3. Filtrar por NRC (después del filtro por materia)
            st.write("### Selecciona las clases que deseas incluir en tu horario:")
            unique_nrcs = filtered_by_subject["NRC"].unique().tolist()
            selected_nrcs = st.multiselect(
                "Selecciona los NRC:",
                options=unique_nrcs,
                default=st.session_state["query_state"]["selected_nrcs"],
                key="nrc_multiselect"
            )

            #Mostrar materias filtradas por NRC
            if selected_nrcs:
                filtered_by_nrc = filtered_by_subject[filtered_by_subject["NRC"].isin(selected_nrcs)]

                st.write("### Clases seleccionadas:")
                columns_to_show = [col for col in filtered_by_nrc.columns if col != "Sesión"]
                if not filtered_by_nrc.empty:
                    st.dataframe(filtered_by_nrc[columns_to_show].reset_index(drop=True))
                else:
                    st.write("No se encontraron materias con los NRC seleccionados.")
            else:
                st.write("Selecciona al menos un NRC para ver las materias correspondientes.")

        else:
            st.write("Selecciona al menos una materia para ver la información y los NRC correspondientes.") #Mensaje mejorado y mas completo

    else:
        st.warning("No se encontraron las columnas 'Materia' o 'NRC' en los datos.")

    if st.button("Generar horario"):
        if selected_nrcs:
            filtered_data = expanded_data[expanded_data["NRC"].isin(selected_nrcs)]
            if not filtered_data.empty:
                schedule = create_schedule_sheet(filtered_data)
                st.write("Horario generado:")
                st.dataframe(schedule)
                if schedule is not None and not schedule.empty: #Manejo de dataframe vacio o nulo
                    pdf_buffer = create_schedule_pdf(schedule)
                    st.download_button(
                        label="Descargar Horario (PDF)",
                        data=pdf_buffer,
                        file_name="horario.pdf",
                        mime="application/pdf",
                    )
                else:
                    st.warning("Por favor, genera un horario primero.")
        else:
            st.warning("Selecciona al menos un NRC.")

    if st.button("Nueva consulta"):
        reset_query_state()
        st.rerun()