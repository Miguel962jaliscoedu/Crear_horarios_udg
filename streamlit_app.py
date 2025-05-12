import os
import json
import base64
from io import BytesIO
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests
import filelock
from Diseño.styles import apply_dataframe_styles, set_page_style, apply_dataframe_styles_with_cruces, get_reportlab_styles
from Funciones.schedule import create_schedule_sheet, create_schedule_pdf
from Funciones.data_processing import fetch_table_data, process_data_from_web, cargar_datos_desde_json, guardar_datos_local
from Funciones.utils import detectar_cruces, crear_clases_desde_dataframe, generar_mensaje_cruces
from Funciones.form_handler import fetch_form_options_with_descriptions, build_post_data, show_abbreviations, FORM_URL, POST_URL

# --------------------------------------------------
# INICIALIZACIÓN DEL ESTADO
# --------------------------------------------------
if 'query_state' not in st.session_state:
    st.session_state.query_state = {
        'done': False,
        'table_data': None,
        'selected_nrcs': [],
        'selected_subjects': []
    }

if 'expanded_data' not in st.session_state:
    st.session_state.expanded_data = pd.DataFrame(columns=[
        'Materia', 'NRC', 'Profesor', 'Días', 'Hora', 'Edificio', 'Aula'
    ])

if 'selected_options' not in st.session_state:
    st.session_state.selected_options = {}

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
# Funciones principales
# --------------------------------------------------
def reset_query_state():
    """Reinicia completamente el estado de la aplicación"""
    st.session_state.query_state = {
        'done': False,
        'table_data': None,
        'selected_nrcs': [],
        'selected_subjects': []
    }
    st.session_state.expanded_data = pd.DataFrame(columns=[
        'Materia', 'NRC', 'Profesor', 'Días', 'Hora', 'Edificio', 'Aula'
    ])
    st.session_state.selected_options = {}
    try:
        if os.path.exists('datos.json'):
            os.remove('datos.json')
    except Exception as e:
        st.error(f"Error al eliminar archivo: {str(e)}")

def guardar_datos_local(data):
    """Guarda los datos en un archivo JSON con bloqueo"""
    try:
        with filelock.FileLock('datos.json.lock'):
            with open('datos.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Error al guardar datos: {str(e)}")

def mostrar_vista_previa_pdf(schedule_df):
    """Muestra una vista previa del horario en formato PDF"""
    try:
        pdf_buffer = create_schedule_pdf(
            schedule_df,
            st.session_state.selected_options["ciclop"]["description"]
        )
        pdf_buffer.seek(0)
        
        base64_pdf = base64.b64encode(pdf_buffer.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        pdf_buffer.seek(0)
        return pdf_buffer
    except Exception as e:
        st.error(f"Error al generar vista previa del PDF: {str(e)}")
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

# Pestañas principales (ahora con 4 pestañas)
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
    
    try:
        form_options = fetch_form_options_with_descriptions(FORM_URL)
        if not form_options:
            st.error("No se pudieron cargar las opciones del formulario")
            st.stop()
    except Exception as e:
        st.error(f"Error al obtener opciones del formulario: {str(e)}")
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
        except Exception as e:
            st.error(f"Error al cargar carreras: {str(e)}")

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
                        st.session_state.expanded_data = process_data_from_web(table_data)
                        
                        guardar_datos_local({
                            "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                            "ciclo": selected_options["ciclop"]["description"]
                        })
                        status.update(label="Consulta completada!", state="complete")
                        
                        st.success("""
                        ✅ Consulta exitosa!  
                        **Haz click en la pestaña '2️⃣ Selección de Materias'** para continuar.
                        """)
                except Exception as e:
                    st.error(f"Error al consultar: {str(e)}")

with tab2:
    if not st.session_state.query_state.get('done'):
        st.warning("Primero realiza una consulta en la pestaña 'Consulta Inicial'")
    else:
        st.markdown("## 📚 Selección de Materias")
        
        if os.path.exists('datos.json'):
            try:
                with filelock.FileLock('datos.json.lock'):
                    datos = cargar_datos_desde_json()
                    st.session_state.expanded_data = pd.DataFrame(datos.get("oferta_academica", []))
                    st.session_state.query_state["selected_subjects"] = datos.get("materias_seleccionadas", [])
                    st.session_state.query_state["selected_nrcs"] = datos.get("nrcs_seleccionados", [])
            except Exception as e:
                st.error(f"Error al cargar datos: {str(e)}")

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
            
            # Convertir todas las columnas relevantes a string
            for col in ['Días', 'Hora', 'Edificio', 'Aula']:
                df_filtrado[col] = df_filtrado[col].astype(str)
            
            # Extraer solo la última letra del edificio
            df_filtrado['Edificio_simple'] = df_filtrado['Edificio'].str[-1]
            
            st.markdown("### 🔍 Grupos Disponibles")

            all_nrcs = []
            for materia in selected_subjects:
                with st.expander(f"📖 {materia}"):
                    grupos = df_filtrado[df_filtrado["Materia"] == materia]
                    
                    # Agrupar por NRC para mostrar todos los horarios
                    grupos_agrupados = grupos.groupby('NRC').agg({
                        'Profesor': 'first',
                        'Días': lambda x: ', '.join(x),
                        'Hora': lambda x: ', '.join(x),
                        'Edificio_simple': lambda x: ', '.join(x),
                        'Aula': lambda x: ', '.join(x)
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
            
            if all_nrcs:
                st.session_state.query_state['selected_nrcs'] = all_nrcs
                try:
                    guardar_datos_local({
                        "oferta_academica": st.session_state.expanded_data.to_dict(orient="records"),
                        "materias_seleccionadas": selected_subjects,
                        "nrcs_seleccionados": all_nrcs,
                        "ciclo": st.session_state.selected_options["ciclop"]["description"]
                    })
                except Exception as e:
                    st.error(f"Error al guardar selección: {str(e)}")
                
                try:
                    st.markdown("---")
                    st.markdown("## 🔍 Detección de Cruces de Horario")
                    
                    clases_seleccionadas = crear_clases_desde_dataframe(
                        st.session_state.expanded_data[
                            st.session_state.expanded_data["NRC"].isin(all_nrcs)
                        ]
                    )
                    cruces = detectar_cruces(clases_seleccionadas)
                    
                    if cruces:
                        st.error("🚨 Se detectaron los siguientes conflictos de horario:")
                        for conflicto in cruces:
                            st.markdown(f"• **{conflicto[0]}** cruza con **{conflicto[1]}**")
                        st.warning("Por favor ajusta tus selecciones para resolver los conflictos")
                    else:
                        st.success("""
                        ✅ No se detectaron conflictos de horario!  
                        **Haz click en la pestaña '3️⃣ Generar Horario'** para ver tu horario personalizado.
                        """)
                except Exception as e:
                    st.error(f"Error al verificar cruces: {str(e)}")

with tab3:
    if not st.session_state.query_state.get('done'):
        st.warning("Por favor completa primero la consulta en la pestaña '1️⃣ Consulta Inicial'")
    elif not st.session_state.query_state.get('selected_nrcs'):
        st.info("Selecciona materias y grupos en la pestaña '2️⃣ Selección de Materias'")
    else:
        st.markdown("## 🗓️ Vista Previa del Horario")
        
        try:
            schedule_df = create_schedule_sheet(
                st.session_state.expanded_data[
                    st.session_state.expanded_data["NRC"].isin(st.session_state.query_state['selected_nrcs'])
                ]
            )
            
            st.markdown("### 📄 Vista previa del horario (PDF)")
            pdf_buffer = mostrar_vista_previa_pdf(schedule_df)
            
            st.markdown("---")
            st.markdown("### 💾 Descargar Horario")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if pdf_buffer:
                    st.download_button(
                        label="📄 Descargar PDF",
                        data=pdf_buffer,
                        file_name="mi_horario.pdf",
                        mime="application/pdf"
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
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
                    mime="application/json"
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
                st.error(f"Error al guardar horario: {str(e)}")
            
        except Exception as e:
            st.error(f"Error al generar el horario: {str(e)}")

# --------------------------------------------------
# Pestaña de Feedback (ahora independiente)
# --------------------------------------------------
with tab4:
    st.markdown("## 📢 Feedback y Sugerencias")
    st.markdown("""
    <style>
        .feedback-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        .feedback-header {
            text-align: center;
            margin-bottom: 2rem;
        }
    </style>
    <div class="feedback-container">
        <div class="feedback-header">
            <h2>¡Tu opinión es importante!</h2>
            <p>Ayúdanos a mejorar esta herramienta compartiendo tus comentarios y sugerencias</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Formulario de feedback embebido
    components.iframe(
        form_url, 
        height=800, 
        scrolling=True
    )
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem;">
        <p>¿Tienes ideas para nuevas funcionalidades?</p>
        <p>¡Háznoslo saber!</p>
    </div>
    """, unsafe_allow_html=True)

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

# --------------------------------------------------
# Estilos CSS adicionales
# --------------------------------------------------
st.markdown("""
<style>
    /* Estilo para mensajes de guía */
    .stSuccess {
        border-left: 4px solid #4CAF50;
        background-color: #f8f9fa;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 4px;
    }
    
    /* Efecto hover en pestañas */
    .stTabs [aria-selected="false"] {
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="false"]:hover {
        color: #2196F3 !important;
    }
    
    /* Mejoras generales */
    .stAlert {
        border-radius: 8px;
    }
    .stButton>button {
        transition: transform 0.2s ease;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    
    /* Ajustes para la pestaña de feedback */
    .stTabs [aria-selected="true"][data-baseweb="tab"]:nth-child(4) {
        color: #FF6D00 !important;
        border-bottom: 2px solid #FF6D00;
    }
</style>
""", unsafe_allow_html=True)