import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime
import io
import logging
from typing import Dict, Any, Tuple
import tempfile
from excel_a_json import procesar_excel_a_json
from json_a_excel import procesar_archivo_json, guardar_resultados_csv
import PIL
from PIL import Image


# ----------------- Funciones de Ayuda y Configuración -----------------

# Configuración del logger para Streamlit
# Se usa st.session_state para almacenar logs entre reruns.
logger = logging.getLogger(__name__)

def setup_session_state():
    """Inicializa el estado de la sesión para logs si no existe."""
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {"message": "", "state": "running"}

def log_message(message: str, level: str = "info"):
    """
    Acumula logs en st.session_state y los envía al logger de Python.
    Esto desacopla la lógica de log de la UI de Streamlit.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{timestamp} - {level.upper()}: {message}"
    st.session_state.logs.append(formatted_message)
    
    # También se puede enviar al logger estándar para la consola
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(message)

def get_logs_from_session() -> str:
    """Obtiene todos los logs acumulados de la sesión como una sola cadena."""
    return "\n".join(st.session_state.logs)

def display_stats(stats: Dict[str, Any]):
    """Muestra estadísticas en un layout organizado usando st.columns."""
    if not stats:
        return
    
    cols = st.columns(4)
    with cols[0]:
        st.metric("Legajos Procesados", stats.get('legajos_procesados', 0))
    with cols[1]:
        st.metric("Variables Calculadas", stats.get('variables_calculadas', 0))
    with cols[2]:
        st.metric("Errores", stats.get('legajos_con_error', 0), delta_color="inverse")
    with cols[3]:
        total_legajos = stats.get('total_legajos', 1)
        success_rate = (stats.get('legajos_procesados', 0) / total_legajos) * 100 if total_legajos > 0 else 0
        st.metric("Tasa de Éxito", f"{success_rate:.1f}%")
        
# ----------------- Lógica de la Interfaz de Usuario (Streamlit) -----------------

st.set_page_config(
    page_title="🔄 Calculadora de Variables de Liquidación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Header
st.title("📊 Calculadora de Variables de Liquidación")
st.markdown("""
    **Automatiza el proceso de cálculo de variables de liquidación.**
    Subí el archivo Excel y descargá el resultado con todas las variables calculadas.
    """)
st.markdown("---")

# Sidebar
with st.sidebar:
    try:
        logo = Image.open("logo.png")  # Ruta relativa directa
        st.image(logo, width=150)
    except FileNotFoundError:
        st.error("""
        **Error**: Archivo 'logo.png' no encontrado.  
        Asegúrate de que:
        - El archivo existe en la misma carpeta que este script
        - El nombre coincide exactamente (incluyendo mayúsculas)
        """)
    st.markdown("---")
    st.markdown("### Configuración")
    debug_mode = st.checkbox("Modo depuración", True, help="Muestra logs detallados y archivos temporales.")
    st.markdown("---")
    st.markdown("**Instrucciones:**")
    st.markdown("1. Subí el archivo Excel con los datos de los legajos.")
    st.markdown("2. Esperá a que se complete el procesamiento.")
    st.markdown("3. Descargá el resultado.")
    st.markdown("---")
    st.markdown(f"*Versión 1.0 - {datetime.now().year}*")

# Área principal
uploaded_file = st.file_uploader(
    "**Subí el archivo Excel** (formato .xlsx)",
    type=["xlsx"],
    help="El archivo debe contener las columnas requeridas: Legajo, Horario completo, Categoría, Sede etc."
)

if uploaded_file:
    setup_session_state()  # Inicializa el estado de la sesión
    st.session_state.logs = [] # Limpia logs de la sesión anterior
    
    process_start_time = datetime.now()
    stats = {}
    
    # Procesamiento con spinner y barra de progreso
    progress_bar = st.progress(0)
    status_text = st.empty()  # Para actualizar mensajes de estado

    try:
        # 1. Vista previa del archivo
        status_text.text("Analizando archivo...")
        df_preview = pd.read_excel(uploaded_file)
        log_message(f"Archivo subido: {uploaded_file.name}. Total de registros: {len(df_preview)}")
        progress_bar.progress(25)

        # 2. Convertir Excel a JSON
        status_text.text("Paso 1: Procesando Excel a JSON...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_json:
            json_path = tmp_json.name
        
        df = pd.read_excel(uploaded_file)
        procesar_excel_a_json(df, output_json_path=json_path, logger_callback=log_message)
        log_message("Archivo Excel procesado a JSON exitosamente.")
        progress_bar.progress(50)

        # 3. Calcular variables
        status_text.text("Paso 2: Calculando variables de liquidación...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
            excel_path = tmp_excel.name

        resultados, stats = procesar_archivo_json(json_path, logger_callback=log_message)
        log_message("Cálculo de variables completado.")
        progress_bar.progress(75)

        # 4. Generar archivo de salida
        status_text.text("Paso 3: Generando archivo de salida...")
        guardar_resultados_csv(resultados, excel_path)
        log_message("Archivo de salida generado.")
        progress_bar.progress(100)

        # Resultados en expander abierto
        with st.expander("📊 Resultados del Procesamiento", expanded=True):
            st.success("✅ Procesamiento completado satisfactoriamente")
            display_stats(stats)
            
            process_time = datetime.now() - process_start_time
            st.caption(f"⏱️ Tiempo total: {process_time.total_seconds():.2f} segundos")
            
            # Botón de descarga
            with open(excel_path, "rb") as f:
                st.download_button(
                    label="⬇️ Descargar Resultados",
                    data=f,
                    file_name=f"variables_calculadas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        status_text.error("Ocurrió un error durante el procesamiento")
        log_message(f"Error crítico: {str(e)}", "error")
        st.error(f"Error: {str(e)}")
        
    finally:
        progress_bar.empty()  # Limpiar barra de progreso
        status_text.empty()   # Limpiar mensaje de estado
        # Limpieza de archivos temporales
        if 'json_path' in locals() and os.path.exists(json_path):
            os.unlink(json_path)
        if 'excel_path' in locals() and os.path.exists(excel_path):
            os.unlink(excel_path)
        log_message("Limpieza de archivos temporales completada.", "debug")

        # Modo depuración
        if debug_mode:
            with st.expander("🐞 Detalles Técnicos (Modo Depuración)", expanded=False):
                st.markdown("#### Logs Completos del Proceso")
                st.code(get_logs_from_session(), language="log")
                
# Footer (único al final de todo)
st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: black;
        color: white;
        text-align: center;
        padding: 10px;
        font-size: 0.8em;
    }
    </style>
    <div class="footer">
        Sistema de cálculo de variables laborales © {datetime.now().year}
    </div>
""", unsafe_allow_html=True)