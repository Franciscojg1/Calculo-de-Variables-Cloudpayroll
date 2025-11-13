import streamlit as st
import pandas as pd
import json
import os
import logging
import math
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

# ----------------- FUNCIÓN PARA COLOREAR LOGS -----------------
def colorear_log(log_line: str) -> str:
    """
    Convierte una línea de log en HTML con colores según el nivel y contenido.
    
    Args:
        log_line: Línea de log en formato texto
        
    Returns:
        HTML string con colores aplicados
    """
    # Escapar HTML para evitar inyección
    import html
    line = html.escape(log_line)
    
    # Detectar nivel de log
    if " - ERROR - " in line or "ERROR CRÍTICO" in line:
        color = "#FF6B6B"  # Rojo
        weight = "bold"
    elif " - WARNING - " in line:
        color = "#FFA500"  # Naranja
        weight = "normal"
    elif " - INFO - " in line:
        # Detectar si es variable CALCULADA o NO CALCULADA
        if "✓ CALCULADA" in line:
            color = "#4CAF50"  # Verde
            weight = "bold"
        elif "✗ NO CALCULADA" in line:
            color = "#FF6B6B"  # Rojo
            weight = "bold"
        elif "INICIANDO CÁLCULO" in line or "RESUMEN" in line:
            color = "#00BCD4"  # Cyan
            weight = "bold"
        else:
            color = "#E0E0E0"  # Gris claro
            weight = "normal"
    elif " - DEBUG - " in line:
        # Logs de debug con prefijos [VXX]
        if "[V" in line and "✗" in line:
            color = "#FF9999"  # Rojo claro
            weight = "normal"
        else:
            color = "#90CAF9"  # Azul claro
            weight = "normal"
    else:
        color = "#CCCCCC"  # Gris por defecto
        weight = "normal"
    
    return f'<span style="color: {color}; font-weight: {weight}; font-family: monospace; font-size: 12px;">{line}</span>'

# ----------------- FUNCIÓN PARA MOSTRAR LOGS CON COLORES -----------------
def mostrar_logs_coloreados(logs: list, max_lines: int = None):
    """
    Muestra logs con colores usando st.markdown.
    
    Args:
        logs: Lista de líneas de log
        max_lines: Número máximo de líneas a mostrar (None = todas)
    """
    if not logs:
        st.warning("No hay logs para mostrar")
        return
    
    # Limitar número de líneas si es necesario
    logs_a_mostrar = logs[-max_lines:] if max_lines else logs
    
    # Convertir cada línea a HTML coloreado
    html_lines = [colorear_log(log) for log in logs_a_mostrar]
    
    # Unir y mostrar con markdown
    html_content = "<br>".join(html_lines)
    st.markdown(
        f'<div style="background-color: #1E1E1E; padding: 15px; border-radius: 5px; overflow-x: auto; max-height: 500px; overflow-y: auto;">{html_content}</div>',
        unsafe_allow_html=True
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

    # Opcional: Si querés que los logs de otros módulos también aparezcan
    root_logger.addHandler(streamlit_handler)
    root_logger.setLevel(log_level)

    # === Opción 1: Silenciar DEBUG/INFO de watchdog (hot-reload) ===
    for noisy in [
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.inotify_buffer',
    ]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

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

# ----------------- HELPERS DE RENDER ROBUSTO -----------------
def _sanitize_json_like(obj):
    """Convierte NaN/NaT a None y sanea estructuras para st.json."""
    if isinstance(obj, dict):
        return {k: _sanitize_json_like(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_like(v) for v in obj]
    # Detectar NaN/NaT
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return obj

def render_json_flexible(value, title=None):
    """Muestra dict/list como JSON; si viene string intenta json.loads; si no, muestra texto crudo."""
    if title:
        st.markdown(title)

    if value is None:
        st.info("Sin resumen disponible para este legajo.")
        return

    if isinstance(value, (dict, list)):
        st.json(_sanitize_json_like(value))
        return

    if isinstance(value, str):
        value_str = value.strip()
        try:
            parsed = json.loads(value_str)
            st.json(_sanitize_json_like(parsed))
        except Exception:
            st.warning("El resumen no viene en formato JSON válido. Muestro el contenido bruto:")
            st.code(value_str)
        return

    # Cualquier otro tipo
    try:
        st.json(value)
    except Exception:
        st.code(str(value))

# ----------------- HELPERS PARA UI (EVITAR 'nan'/'NaT') -----------------
def normalize_missing(v):
    """
    Devuelve None si v es 'vacío': None, NaN, NaT, '', 'nan', 'NaN', 'null', 'None'.
    """
    if v is None:
        return None
    # pandas: NaN/NaT
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    # strings "vacíos"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"", "nan", "nat", "null", "none"}:
            return None
    return v

def fmt_field(v, default="—"):
    v2 = normalize_missing(v)
    return default if v2 is None else v2

def fmt_date_field(v, default="—"):
    v2 = normalize_missing(v)
    if v2 is None:
        return default
    # Si ya es datetime/Timestamp -> formatear
    if isinstance(v2, (datetime, pd.Timestamp)):
        return v2.strftime("%d/%m/%Y")
    # Si es string, intento parsear
    if isinstance(v2, str):
        dt = pd.to_datetime(v2, errors="coerce", dayfirst=True)
        if not pd.isna(dt):
            return dt.strftime("%d/%m/%Y")
        return v2  # lo devuelvo crudo si no pudo parsear
    return str(v2)

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

    # === Nuevo: selector de modo de resumen ===
    st.markdown("### Modo resumen")
    modo_resumen = st.selectbox(
        "Utilizar sólo en caso de diferencias:",
        options=["Mixto", "Normalizado", "Crudo"],
        index=0,  # default = "Mixto"
        help=(
            "Mixto: usa valores normalizados y completa con crudo si faltan.\n"
            "Normalizado: sólo campos normalizados (puede dejar vacíos si faltan).\n"
            "Crudo: sólo desde el Excel original."
        ),
        key="modo_resumen_selector"
    )

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

# --- OPCIONAL: resetear logs si cambia el archivo subido ---
if uploaded_file:
    current_name = getattr(uploaded_file, "name", None)
    if st.session_state.get("last_uploaded_filename") != current_name:
        # Limpiar EN EL LUGAR para no romper la referencia del handler
        if 'logs' in st.session_state and isinstance(st.session_state.logs, list):
            st.session_state.logs.clear()
        else:
            st.session_state.logs = []
        st.session_state.last_uploaded_filename = current_name

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

        # Función admite modo_resumen desde el UI
        modo_resumen_param = (modo_resumen or "").strip().lower()
        resultados, stats, resumen_horarios = procesar_archivo_json(json_path, modo_resumen=modo_resumen_param)
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

# ================== BLOQUES DE DEBUG ==================
if uploaded_file and debug_mode:
    with st.expander("🔍 Detalles Técnicos (Modo Depuración)", expanded=False):
        # ---------- RESUMEN MENSAJES DE DEPURACIÓN ----------
        st.markdown("#### Resumen Mensajes de Depuración")

        # Solo los logs de esta corrida (desde initial_log_count)
        logs_todos = st.session_state.logs
        logs_nuevos = logs_todos[initial_log_count:] if len(logs_todos) > initial_log_count else logs_todos

        # Contadores por nivel
        niveles = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        warnings_list, errores_list = [], []

        for line in logs_nuevos:
            # Formato: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            try:
                level = line.split(" - ")[2].strip()
            except Exception:
                level = ""
            if level in niveles:
                niveles[level] += 1
            if level == "WARNING":
                warnings_list.append(line)
            if level in ("ERROR", "CRITICAL"):
                errores_list.append(line)

        c = st.columns(5)
        with c[0]:
            st.metric("Warnings", niveles["WARNING"], delta_color="inverse")
        with c[1]:
            st.metric("Errores", niveles["ERROR"], delta_color="inverse")
        with c[2]:
            st.metric("Críticos", niveles["CRITICAL"], delta_color="inverse")
        with c[3]:
            st.metric("Info", niveles["INFO"])
        with c[4]:
            st.metric("Debug", niveles["DEBUG"])

        # Si stats tiene errores por tipo, mostrar
        if isinstance(stats, dict) and stats.get("errores_por_tipo"):
            st.markdown("**Errores por tipo (stats):**")
            st.json({k: int(v) for k, v in stats["errores_por_tipo"].items()})

        # ---------- VISTAS/FILTROS ----------
        st.markdown("#### Logs del Procesamiento")

        with st.expander(f"🟨 Ver solo Warnings ({len(warnings_list)})", expanded=False):
            if warnings_list:
                mostrar_logs_coloreados(warnings_list)
            else:
                st.info("Sin warnings registrados en esta corrida.")

        with st.expander(f"🟥 Ver solo Errores/Críticos ({len(errores_list)})", expanded=False):
            if errores_list:
                mostrar_logs_coloreados(errores_list)
            else:
                st.info("Sin errores/críticos registrados en esta corrida.")

        with st.expander("📜 Ver todos los logs", expanded=False):
            if logs_nuevos:
                mostrar_logs_coloreados(logs_nuevos)
            else:
                st.warning("No se generaron nuevos logs durante el procesamiento")

        # ---------- INFORMACIÓN DEL LOGGER ----------
        st.markdown("#### Información del Logger")
        root_logger = logging.getLogger()
        st.write(f"Handlers activos (root): {[h.__class__.__name__ for h in root_logger.handlers]}")
        st.write(f"Nivel del logger (root): {logging.getLevelName(root_logger.level)}")
        st.write(f"Logs de esta corrida: {len(logs_nuevos)}")
        st.write(f"Logs acumulados (sesión): {len(st.session_state.logs)}")

        # Botón para limpiar logs de sesión
        if st.button("🧹 Limpiar logs de sesión", key="clear_logs"):
            st.session_state.logs.clear()
            try:
                st.rerun()
            except Exception:
                st.experimental_rerun()

    # --- EXPANDER: RESUMEN ENRIQUECIDO DE LEGAJOS (SOLO DEBUG) ---
    with st.expander("🗂️ Resumen de Legajos (Modo Depuración)", expanded=False):
        try:
            st.markdown("#### Resumen por Legajo")
            st.caption(f"Modo de resumen activo: **{modo_resumen}**")

            if 'resumen_horarios' in locals() and resumen_horarios:
                legajo_seleccionado = st.selectbox(
                    "Seleccioná un legajo:",
                    options=sorted(
                        resumen_horarios.keys(),
                        key=lambda x: int(x) if str(x).isdigit() else str(x)
                    ),
                    key="debug_legajo_selector"
                )

                if legajo_seleccionado is not None:
                    info = resumen_horarios.get(legajo_seleccionado, {}) or {}

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Nombre:** {fmt_field(info.get('nombre_completo'))}")
                        st.write(f"**Sector/Subsector:** {fmt_field(info.get('sector'))} / {fmt_field(info.get('subsector'))}")
                        st.write(f"**Puesto:** {fmt_field(info.get('puesto'))}")
                        st.write(f"**Sede:** {fmt_field(info.get('sede'))}")
                        st.write(f"**Categoría:** {fmt_field(info.get('categoria'))}")
                    with col2:
                        st.write(f"**Modalidad:** {fmt_field(info.get('modalidad'))}")
                        fi = fmt_date_field(info.get('fecha_ingreso'))
                        ff = fmt_date_field(info.get('fecha_fin'))
                        st.write(f"**Fecha ingreso / fin:** {fi} / {ff}")
                        st.write(f"**Sueldo bruto pactado:** {fmt_field(info.get('sueldo_bruto_pactado'))}")
                        st.write(f"**Adicionales:** {fmt_field(info.get('adicionales'))}")

                    st.markdown("**Horario (texto original):**")
                    st.code(fmt_field(info.get('horario_texto')))

                    # --- Resumen estructurado del horario (robusto) ---
                    render_json_flexible(info.get('horario_resumen'), "**Resumen estructurado del horario:**")

                    ver_json = st.checkbox("Ver JSON completo del legajo", value=False, key="ver_json_legajo")
                    if ver_json:
                        st.json(_sanitize_json_like(info))

                st.download_button(
                    label="⬇️ Descargar Resúmenes Completos",
                    data=json.dumps(_sanitize_json_like(resumen_horarios), indent=2, ensure_ascii=False),
                    file_name=f"resumen_legajos_debug_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json",
                    key="debug_download_resumenes"
                )
            else:
                st.warning("No hay resúmenes disponibles (el JSON no trae datos enriquecidos de legajos).")

        except Exception as e:
            logging.getLogger('__main__').error(f"Error al mostrar resumen: {str(e)}", exc_info=True)
            st.error("Error al cargar resúmenes. Ver logs para detalles.")
            st.exception(e)

# ----------------- FOOTER -----------------
year = datetime.now().year
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
