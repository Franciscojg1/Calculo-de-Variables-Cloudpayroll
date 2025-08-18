import streamlit as st
import pandas as pd
import json
import os
import logging
from datetime import datetime
import tempfile
from excel_a_json import procesar_excel_a_json
from json_a_excel import procesar_archivo_json, guardar_resultados_csv
from PIL import Image
from typing import Dict, Any, List

# ----------------- CONFIGURACIÓN INICIAL -----------------
st.set_page_config(
    page_title="🔄 Calculadora de Variables de Liquidación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- CLASE HANDLER PARA LOGS -----------------
class StreamlitLogHandler(logging.Handler):
    def __init__(self, logs_list: List[str]):
        super().__init__()
        self.logs_list = logs_list

    def emit(self, record):
        msg = self.format(record)
        self.logs_list.append(msg)

# ----------------- FUNCIÓN PARA CONFIGURAR LOGGING -----------------
def setup_streamlit_logging(debug: bool):
    """Configuración robusta para evitar logs duplicados"""
    log_level = logging.DEBUG if debug else logging.INFO

    # Limpia todos los handlers existentes
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Configuración básica sin handler
    logging.basicConfig(level=log_level, handlers=[])

    # Crea UN handler compartido para Streamlit
    if 'logs' not in st.session_state:
        st.session_state.logs = []

    streamlit_handler = StreamlitLogHandler(st.session_state.logs)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    streamlit_handler.setFormatter(formatter)

    # Configuración específica para cada módulo
    modules = ['excel_a_json', 'json_a_excel', '__main__']
    for module in modules:
        logger_mod = logging.getLogger(module)
        logger_mod.setLevel(log_level)

        # Elimina handlers existentes en el logger del módulo
        for h in logger_mod.handlers[:]:
            logger_mod.removeHandler(h)

        # Añade el handler de Streamlit SOLO al logger del módulo
        logger_mod.addHandler(streamlit_handler)

        # IMPORTANTE: Desactiva la propagación al root logger
        logger_mod.propagate = False

    # Opcional: Si quieres que los logs de otros módulos también aparezcan
    root_logger.addHandler(streamlit_handler)
    root_logger.setLevel(log_level)

# ----------------- FUNCIÓN PARA MOSTRAR ESTADÍSTICAS -----------------
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

# ----------------- INTERFAZ PRINCIPAL -----------------
st.title("📊 Calculadora de Variables de Liquidación")
st.markdown("""
    **Automatiza el proceso de cálculo de variables de liquidación.**
    Subí el archivo Excel y descargá el resultado con todas las variables calculadas.
""")
st.markdown("---")

# ----------------- SIDEBAR CON CONFIGURACIÓN -----------------
with st.sidebar:
    try:
        logo = Image.open("logo.png")
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

# ----------------- CONFIGURACIÓN DE LOGGING -----------------
if 'logs' not in st.session_state:
    st.session_state.logs = []

setup_streamlit_logging(debug_mode)
logging.info("Aplicación iniciada. Logger de Streamlit configurado.")

if debug_mode:
    logging.debug("Modo de depuración activado.")
    logging.debug("Mensaje DEBUG de prueba - app.py")
    logging.getLogger('excel_a_json').debug("Mensaje DEBUG de prueba - excel_a_json")
    logging.getLogger('json_a_excel').debug("Mensaje DEBUG de prueba - json_a_excel")

# ----------------- UPLOADER DE ARCHIVOS -----------------
uploaded_file = st.file_uploader(
    "**Subí el archivo Excel** (formato .xlsx)",
    type=["xlsx"],
    help="El archivo debe contener las columnas requeridas: Legajo, Horario completo, Categoría, Sede etc."
)

# ----------------- PROCESAMIENTO DEL ARCHIVO -----------------
if uploaded_file:
    initial_log_count = len(st.session_state.logs)

    process_start_time = datetime.now()
    stats: Dict[str, Any] = {}

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("Analizando archivo...")
        df_preview = pd.read_excel(uploaded_file)
        logging.info(f"Archivo subido: {uploaded_file.name}. Total de registros: {len(df_preview)}")
        progress_bar.progress(25)

        status_text.text("Paso 1: Procesando Excel a JSON...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp_json:
            json_path = tmp_json.name

        df = pd.read_excel(uploaded_file)
        procesar_excel_a_json(df, output_json_path=json_path)
        logging.info("Archivo Excel procesado a JSON exitosamente.")
        progress_bar.progress(50)

        status_text.text("Paso 2: Calculando variables de liquidación...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_excel:
            excel_path = tmp_excel.name

        # >>>> IMPORTANTE: ahora la función devuelve 3 valores (Alternativa A)
        resultados, stats, resumen_horarios = procesar_archivo_json(json_path)
        logging.debug(f"type(resultados)={type(resultados)} | type(resumen_horarios)={type(resumen_horarios)}")
        logging.info("Cálculo de variables completado.")
        progress_bar.progress(75)

        status_text.text("Paso 3: Generando archivo de salida...")
        guardar_resultados_csv(resultados, excel_path)
        logging.info("Archivo de salida generado.")
        progress_bar.progress(100)

        with st.expander("📊 Resultados del Procesamiento", expanded=True):
            st.success("✅ Procesamiento completado satisfactoriamente")
            display_stats(stats)

            process_time = datetime.now() - process_start_time
            st.caption(f"⏱️ Tiempo total: {process_time.total_seconds():.2f} segundos")

            with open(excel_path, "rb") as f:
                st.download_button(
                    label="⬇️ Descargar Resultados",
                    data=f,
                    file_name=f"variables_calculadas_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    except Exception as e:
        status_text.error("Ocurrió un error durante el procesamiento")
        logging.error(f"Error crítico: {str(e)}", exc_info=True)
        st.error(f"Error: {str(e)}")

    finally:
        progress_bar.empty()
        status_text.empty()
        try:
            if 'json_path' in locals() and os.path.exists(json_path):
                os.unlink(json_path)
            if 'excel_path' in locals() and os.path.exists(excel_path):
                os.unlink(excel_path)
            logging.debug("Limpieza de archivos temporales completada.")
        except Exception as cleanup_error:
            logging.error(f"Error al limpiar archivos temporales: {cleanup_error}")

        if debug_mode:
            with st.expander("🔍 Detalles Técnicos (Modo Depuración)", expanded=False):
                st.markdown("#### Logs del Procesamiento")
                if len(st.session_state.logs) > initial_log_count:
                    new_logs = st.session_state.logs[initial_log_count:]
                    st.code("\n".join(new_logs), language="log")
                else:
                    st.warning("No se generaron nuevos logs durante el procesamiento")

                st.markdown("#### Información del Logger")
                root_logger = logging.getLogger()
                st.write(f"Handlers activos: {[h.__class__.__name__ for h in root_logger.handlers]}")
                st.write(f"Nivel del logger: {logging.getLevelName(root_logger.level)}")
                st.write(f"Total de logs registrados: {len(st.session_state.logs)}")

        # --- NUEVO EXPANDER PARA RESUMEN DE HORARIOS (SOLO DEBUG) ---
        with st.expander("🕗 Resumen de Horarios (Debug)", expanded=False):
            try:
                st.markdown("#### Resumen por Legajo")
                if 'resumen_horarios' in locals() and resumen_horarios:
                    legajo_seleccionado = st.selectbox(
                        "Selecciona un legajo:",
                        options=sorted(
                            resumen_horarios.keys(),
                            key=lambda x: int(x) if str(x).isdigit() else str(x)
                        ),
                        key="debug_legajo_selector"
                    )
                    if legajo_seleccionado is not None:
                        st.json(resumen_horarios[legajo_seleccionado])

                    st.download_button(
                        label="⬇️ Descargar Resúmenes Completos",
                        data=json.dumps(resumen_horarios, indent=2, ensure_ascii=False),
                        file_name=f"resumen_horarios_debug_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                        key="debug_download_button"
                    )
                else:
                    st.warning("No hay resúmenes disponibles (el JSON no trae 'horario.resumen').")
            except Exception as e:
                logging.getLogger('__main__').error(f"Error al mostrar resumen: {str(e)}", exc_info=True)
                st.error("Error al cargar resúmenes. Ver logs para detalles.")
                if debug_mode:
                    st.exception(e)

year = datetime.now().year  # <- año dinámico

# ----------------- FOOTER -----------------

st.markdown(f"""
    <style>
    .footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: black;
        color: white;
        text-align: center;
        padding: 10px;
        font-size: 0.8em;
        z-index: 9999;
    }}
    </style>
    <div class="footer">
        Variables de liquidación © {year}
    </div>
""", unsafe_allow_html=True)
