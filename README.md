# 📚 Planeación de Horarios UDG

Esta aplicación web desarrollada con Streamlit te permite consultar la oferta académica de la Universidad de Guadalajara, seleccionar materias, detectar posibles cruces de horario y generar el posible horario para el proximo semestre en formatos PDF, Excel y JSON.

---

## 🧱 Estructura del Proyecto

```
📁 Proyecto/
│
├── Streamlit_app.py           # Archivo principal de la aplicación Streamlit
├── 📁 Diseño/                 # Estilos personalizados (CSS y funciones visuales)
│   └── styles.py
├── 📁 Funciones/              # Lógica de negocio y procesamiento de datos
│   ├── schedule.py           # Creación de horarios en PDF y Excel
│   ├── data_processing.py    # Procesamiento de la tabla web
│   ├── utils.py              # Funciones auxiliares (cruces, clases, etc.)
│   └── form_handler.py       # Manejo del formulario de Oferta academica.
├── datos.json                # Archivo local donde se guarda la selección del usuario
└── requirements.txt          # Dependencias del proyecto
```

---

## ⚙️ Requisitos del Sistema

- Python 3.8 o superior
- Paquetes principales:
  - `streamlit`
  - `pandas`
  - `requests`
  - `xlsxwriter`
  - `reportlab`
  - `filelock`

Instalación:
```bash
pip install -r requirements.txt
```

---

## 🧠 Funcionamiento General

### 1️⃣ Consulta Inicial
- El usuario selecciona opciones del formulario (Ciclo, CU, carrera, etc.).
- Se realiza una solicitud POST a la página oficial y se obtiene la tabla con la oferta académica.
- Los datos se procesan y guardan localmente en `datos.json`.

### 2️⃣ Selección de Materias
- Se listan todas las materias y grupos disponibles.
- El usuario selecciona materias y NRCs (grupos).
- Se detectan automáticamente conflictos de horario (cruces).

### 3️⃣ Generación de Horario
- Se genera un horario personalizado con los grupos seleccionados.
- El usuario puede descargar el horario en:
  - PDF (con vista previa embebida)
  - Excel
  - JSON

### 4️⃣ Feedback
- Se incluye un formulario de Google incrustado para recibir sugerencias de los usuarios.

---

## 🧩 Detalles Técnicos

- **Estado de sesión (`st.session_state`)** se utiliza para mantener persistencia entre pestañas.
- **Bloqueo de archivos** (`filelock`) garantiza que no haya corrupción del archivo `datos.json`.
- **PDF dinámico** con `reportlab` para diseño personalizado del horario.
- **Detección de cruces** a partir de intervalos horarios agrupados por NRC.
- **CSS personalizado** para mejorar estética (ver `set_page_style()` en `styles.py`).

---

## 🔒 Manejo de Errores

- Todos los bloques importantes están envueltos en `try/except`.
- En caso de error, se muestra un `st.error()` descriptivo.
- Archivos locales se manejan con seguridad de concurrencia.

---

## 🧪 Pruebas y Validaciones

- Validación automática de selección de ciclo.
- Revisión de conflictos de horario antes de permitir avanzar.
- Formato de datos consistente antes de exportar.

---

## 🚀 Despliegue

Se puede desplegar fácilmente en **Streamlit Cloud** u otro servidor compatible.

Ejemplo:
```bash
streamlit run app.py
```

---

## NOTA

- Desarrollado con Inteligencia artificial.
- Basado en datos públicos de la Universidad de Guadalajara.
