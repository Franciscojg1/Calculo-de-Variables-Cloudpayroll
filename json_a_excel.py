#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SCRIPT DE CÁLCULO DE VARIABLES DE LIQUIDACIÓN - VERSIÓN MEJORADA 2.0

Características principales:
- Implementa todas las reglas del documento REGLAS.docx
- Sistema de logging detallado para debugging
- Validaciones exhaustivas de datos de entrada
- Generación de reportes de procesamiento
- Manejo robusto de errores
- Documentación clara de cada función
"""

import json
import unicodedata
import math
import logging
import os
import re
from datetime import datetime
import traceback
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from typing import Any, Dict, List, Optional, Set, Tuple
from typing import Callable, Any, Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger('json_a_excel')

def json_a_excel_streamlit(ruta_json: str, nombre_excel: str = "variables_calculadas.xlsx", logger_callback=None) -> Optional[str]:
    """
    Procesa un archivo JSON normalizado (legajos) y genera un Excel con variables calculadas.
    Retorna el path del Excel generado, o None si hubo error crítico.
    """
    try:
        # 2. Leer el archivo JSON
        if not os.path.exists(ruta_json):
            logger.error(f"No se encontró el archivo: {ruta_json}")
            if logger_callback: logger_callback(f"No se encontró el archivo: {ruta_json}")
            return None

        with open(ruta_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "legajos" not in data:
            logger.error("El JSON no contiene la clave 'legajos'")
            if logger_callback: logger_callback("El JSON no contiene la clave 'legajos'")
            return None
    except Exception as e:
            logger.error(f"Ocurrió un error crítico procesando el JSON: {e}", exc_info=True)
    if logger_callback:
        logger_callback(f"Ocurrió un error crítico procesando el JSON: {e}")
    return None

# --- Códigos de Color ANSI para Terminal ---
COLOR_RESET = "\033[0m"
COLOR_BLACK = "\033[30m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_WHITE = "\033[97m"
COLOR_BOLD = "\033[1m"
COLOR_UNDERLINE = "\033[4m"


def normalizar_texto(texto: Any) -> str:
    """
    Normaliza un texto para comparaciones robustas.
    """
    if texto is None:
        return ""

    if not isinstance(texto, str):
        texto = str(texto) if texto else ""

    try:
        texto_procesado = texto.lower()

        reemplazos_directos = {
            'ñ': 'n',
            'ç': 'c',
        }
        for char, reemplazo in reemplazos_directos.items():
            texto_procesado = texto_procesado.replace(char, reemplazo)

        texto_normalizado_unicode = unicodedata.normalize('NFKD', texto_procesado)

        texto_sin_diacriticos = ''.join(
            c for c in texto_normalizado_unicode
            if not unicodedata.combining(c)
        )

        texto_filtrado = re.sub(r'[^a-z0-9\s]', ' ', texto_sin_diacriticos)

        texto_limpio = re.sub(r'\s+', ' ', texto_filtrado).strip()

        return texto_limpio

    except Exception as e:
        # Puedes decidir si quieres mantener solo un logger.error aquí para casos de falla
        logger.error(f"Error crítico al normalizar texto: '{texto}'. Error: {str(e)}", exc_info=True)
        return str(texto).lower().strip()

def print_header():
    """Imprime el encabezado del programa"""
    header = """
    ============================================================
    SCRIPT DE CÁLCULO DE VARIABLES DE LIQUIDACIÓN - VERSIÓN 2.0
    Sistema automatizado para cálculo preciso de variables según:
    - Documento REGLAS.docx (Única fuente de verdad)
    - Estructura JSON normalizada
    ============================================================
    """
    print(header)
    logger.info("Inicializando sistema de cálculo de variables")

# ---
# ======================
# CONSTANTES NORMALIZADAS
# ======================

# Puestos especiales con nombres normalizados
PUESTOS_ESPECIALES: Dict[str, str] = {
    'TELEFONISTA': normalizar_texto('TELEFONISTA'),
    'RECEP_LAB': normalizar_texto('RECEPCIONISTA DE LABORATORIO'),
    'TEC_CARDIO': normalizar_texto('TECNICO EN PRACTICAS CARDIOLOGICAS'),
    'OP_LOGISTICA': normalizar_texto('OPERARIO DE LOGISTICA'),
    'MEDICO': normalizar_texto('MEDICO'),
    'MEDICA': normalizar_texto('MEDICA'),
    'MEDICO/A': normalizar_texto('MEDICO/A'),
    'ODONTOLOGO': normalizar_texto('ODONTOLOGO/A'),
    'ODONTOLOGO/A FELLOW': normalizar_texto('ODONTOLOGO/A FELLOW')
}

valores_profesionales_para_comparacion = (
            normalizar_texto('MEDICO'),
            normalizar_texto('MEDICA'),
            normalizar_texto('MEDICO/A'), # Normalizado al vuelo
            normalizar_texto('ODONTOLOGO/A'), # Normalizado al vuelo
            normalizar_texto('ODONTOLOGO/A FELLOW') # Normalizado al vuelo
        )

# Constantes de PISOS HORARIOS (claves en minúsculas)
PISOS_HORARIOS: Dict[str, float] = {
    normalizar_texto('GENERAL'): 36.0,
    normalizar_texto('LABORATORIO'): 27.0,
    normalizar_texto('IMAGENES'): 18.0
}

# Sector de Laboratorio excluido (en minúsculas)
SECTOR_EXCLUIDO_LABORATORIO = normalizar_texto("Laboratorio")

# Conjuntos de sectores imágenes (valores en minúsculas)
SECTORES_IMAGENES: Set[str] = {
    normalizar_texto("MAMOGRAFIA"),
    normalizar_texto("IMAGENES DMF"),
    normalizar_texto("TOMOGRAFIA COMPUTADA"),
    normalizar_texto("DENSITOMETRIA"),
    normalizar_texto("MEDICINA NUCLEAR"),
    normalizar_texto("PET/CT"),
    normalizar_texto("RADIOLOGIA"),
    normalizar_texto("RESONANCIA MAGNETICA"),
    normalizar_texto("IMAGENES") # Aseguramos que 'IMAGENES' esté si se usa como clave general
}

# Sectores con reglas especiales (valores en minúsculas)
SECTORES_ESPECIALES: Dict[str, List[str]] = {
    'HORAS_200': [normalizar_texto("CUAT")],
    'HORAS_156': [
        normalizar_texto("LABORATORIO"),
        normalizar_texto("MAMOGRAFIA"),
        normalizar_texto("IMAGENES DMF"),
        normalizar_texto("TOMOGRAFIA COMPUTADA"),
        normalizar_texto("DENSITOMETRIA"),
        normalizar_texto("MEDICINA NUCLEAR"),
        normalizar_texto("PET/CT"),
        normalizar_texto("RADIOLOGIA"),
        normalizar_texto("RESONANCIA MAGNETICA")
    ],
    'MEDICOS': [
        normalizar_texto("ECOGRAFIA"),
        normalizar_texto("MAMOGRAFIA")
    ]
}

# Términos especiales en horarios (valores en minúsculas)
TERMINOS_ESPECIALES: Set[str] = {
    normalizar_texto("SADOFE"),
    normalizar_texto("DOFE"),
    normalizar_texto("SADO"),
    normalizar_texto("SAFE")
}

# Sedes que no liquidan plus guardia (valores en minúsculas)
SEDES_NO_LIQUIDA_PLUS: Set[str] = {
    normalizar_texto("CLINICA BAZTERRICA"),
    normalizar_texto("CLINICA DEL SOL"),
    normalizar_texto("CONSULTORIOS BAZTERRICA"),
    normalizar_texto("PATERNAL"),
    normalizar_texto("C DEL SOL"),
    normalizar_texto("CDS"),
    normalizar_texto("C. DEL SOL")
}
# Sedes que están permitidas para considerar a alguien full guardia (valores en minúsculas)
sedes_permitidas = {
    normalizar_texto('clínica del sol'),
    normalizar_texto('c. del sol'),
    normalizar_texto('cds'),
    normalizar_texto('san miguel'),
    normalizar_texto('sm'),
    normalizar_texto('bazterrica'),
    normalizar_texto('cons. ext. cl. bazterrica'),
    normalizar_texto('clinica bazterrica'),
    normalizar_texto('Cons. Ext. Cl. Bazterrica'),
    normalizar_texto('Santa Isabel'),
    normalizar_texto('Clinica Santa Isabel')
}
# Constantes específicas para es_medico_productividad (valores en minúsculas)
SECTORES_MEDICOS: Set[str] = {
    normalizar_texto("ECOGRAFIA"),
    normalizar_texto("MAMOGRAFIA")
}

DIAS_ESPECIALES = {0, 1, 2}  # Lunes, Martes, Miércoles

# ======================
# REGLAS ESPECIALES - CLASES DE CONFIGURACIÓN
# ======================

class ConfigArt19:
    """Configuraciones para cálculo de Artículo 19"""
    PUESTOS_VALIDOS: Set[str] = {
        normalizar_texto("TECNICO DE LABORATORIO"),
        normalizar_texto("EXTRACCIONISTA"),
        normalizar_texto("BIOQUIMICO"),
        normalizar_texto("AUXILIAR TÉCNICO")
    }
    SECTOR_VALIDO: str = normalizar_texto("LABORATORIO")
    CATEGORIA_PREFIX: str = 'dc_' # Esta se compara con .lower(), así que el prefijo es lowercase
    HORAS_MIN: float = 36.0
    HORAS_MAX: float = 48.0
    PORCENTAJE_MAX: float = 33 # Variable antes CONSTANTES['PORCENTAJE_MAX_ART19']

class ConfigExtensionHoraria:
    """Configuraciones para extensión horaria (Variable 992)"""
    PUESTOS_VALIDOS: Set[str] = {
        normalizar_texto("TECNICO"),
        normalizar_texto("TECNICO PIVOT")
    }
    ID_LEGAJO_MAX: int = 3999
    HORAS_MINIMAS: float = 24.0

class ConfigBioimagenes:
    """Configuraciones para adicional de bioimágenes (Variable 10000)"""
    PUESTOS_VALIDOS: Set[str] = {
        normalizar_texto("TECNICO"),
        normalizar_texto("TECNICO DE REPROCESO"),
        normalizar_texto("TECNICO PIVOT")
    }
    TERMINOS_ADICIONALES: Set[str] = {
        normalizar_texto("LIC. EN BIOIMAGENES"),
        normalizar_texto("BIOIMAGENES"),
        normalizar_texto("LICENCIADO EN BIOIMAGENES"),
        normalizar_texto("PRESENTÓ TÍTULO"),
        normalizar_texto("TÍTULO")
    }

# Variables utilizadas en calcular_porcentaje_art19
CATEGORIA_ART19_PREFIX: str = ConfigArt19.CATEGORIA_PREFIX
PUESTOS_ART19: Set[str] = ConfigArt19.PUESTOS_VALIDOS
SECTOR_ART19: str = ConfigArt19.SECTOR_VALIDO
HORAS_MIN_ART19: float = ConfigArt19.HORAS_MIN
HORAS_MAX_ART19: float = ConfigArt19.HORAS_MAX
CONSTANTES: Dict[str, float] = {'PORCENTAJE_MAX_ART19': ConfigArt19.PORCENTAJE_MAX}
HORAS_BASE_CALCULO_ART19: float = 48.0 # Asumiendo 48 horas como base para el cálculo proporcional

TERMINOS_CESION_RAW = [
    "Cesión",
    "CECION" 
]

# Y luego normalizar la lista para crear el set final
# Esto se hace una sola vez cuando el script se carga
TERMINOS_CESION = {normalizar_texto(term) for term in TERMINOS_CESION_RAW}

# ==============================
# FUNCIONES PRINCIPALES
# ==============================

def procesar_archivo_json(
    ruta_archivo: str,
    modo_resumen: str = "mixto",  # "mixto" | "normalizado" | "crudo"
) -> Tuple[Optional[List[Tuple[int, int, Any]]], Dict[str, Any], Dict[Any, Any]]:
    """
    Procesa el archivo JSON y genera:
      - resultados: Lista de tuplas (id_legajo, codigo_variable, valor) o None
      - stats: métricas del procesamiento
      - resumen_horarios: dict {id_legajo: info_enriquecida}

    modo_resumen:
      - "mixto": prioriza campos normalizados y hace fallback al crudo si faltan (recomendado)
      - "normalizado": siempre usa los campos normalizados
      - "crudo": siempre usa los campos crudos (horario_resumen se desactiva)
    """
    logger = logging.getLogger('json_a_excel')

    # Helpers internos para selección de valores
    def _is_missing(v):
        if v is None:
            return True
        if isinstance(v, str) and v.strip() == "":
            return True
        if isinstance(v, (list, dict)) and len(v) == 0:
            return True
        return False

    def pick(norm, raw):
        if modo_resumen == "normalizado":
            return norm
        if modo_resumen == "crudo":
            return raw
        # mixto (default)
        return raw if _is_missing(norm) else norm

    # Inicialización de estadísticas
    stats: Dict[str, Any] = {
        'total_legajos': 0,
        'legajos_procesados': 0,
        'legajos_con_error': 0,
        'variables_calculadas': 0,
        'errores_por_tipo': defaultdict(int),
    }

    resumen_horarios: Dict[Any, Any] = {}

    try:
        logger.info(f"📂 Cargando archivo JSON: {ruta_archivo}")
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'legajos' not in data:
            error_msg = "El archivo JSON no contiene la clave 'legajos'"
            logger.error(error_msg)
            return None, stats, resumen_horarios

        stats['total_legajos'] = len(data['legajos'])
        resultados: List[Tuple[int, int, Any]] = []
        logger.info(f"🔍 Iniciando procesamiento de {stats['total_legajos']} legajos")

        for i, legajo in enumerate(data['legajos'], 1):
            # ----------- Armado del resumen enriquecido -----------
            crudo = legajo.get('crudo_min', {}) or {}
            dp = legajo.get('datos_personales', {}) or {}
            contr = legajo.get('contratacion', {}) or {}
            fechas = contr.get('fechas', {}) or {}
            remu = legajo.get('remuneracion', {}) or {}
            hor = legajo.get('horario', {}) or {}

            legajo_id = (
                legajo.get('id_legajo')
                or crudo.get('Legajo')
                or legajo.get('legajo')
                or legajo.get('id')
                or 'DESCONOCIDO'
            )

            # sector puede venir como dict en datos_personales
            sector_dict = dp.get('sector') if isinstance(dp.get('sector'), dict) else {}
            sector_principal_norm = sector_dict.get('principal') if sector_dict else None
            sector_sub_norm = sector_dict.get('subsector') if sector_dict else None

            resumen_horarios[legajo_id] = {
                'nombre_completo': pick(dp.get('nombre'), crudo.get('Nombre completo')),
                'sector': pick(sector_principal_norm, crudo.get('Sector')),
                'subsector': pick(sector_sub_norm, crudo.get('Subsector')),
                'puesto': pick(dp.get('puesto'), crudo.get('Puesto')),
                'sede': pick(dp.get('sede'), crudo.get('Sede')),
                'categoria': pick(contr.get('categoria'), crudo.get('Categoría')),
                'modalidad': pick(contr.get('tipo'), crudo.get('Modalidad contratación')),
                'fecha_ingreso': pick(fechas.get('ingreso'), crudo.get('Fecha ingreso')),
                'fecha_fin': pick(fechas.get('fin'), crudo.get('Fecha de fin')),
                'sueldo_bruto_pactado': pick(remu.get('sueldo_base'), crudo.get('Sueldo bruto pactado')),
                'adicionales': pick(remu.get('adicionables'), crudo.get('Adicionales')),
                # Horario: texto crudo (o texto_original si está disponible), y resumen solo si no es modo "crudo"
                'horario_texto': (
                    crudo.get('Horario completo') if modo_resumen == "crudo"
                    else (hor.get('texto_original') or crudo.get('Horario completo'))
                ),
                'horario_resumen': None if modo_resumen == "crudo" else hor.get('resumen'),
            }
            # ----------- Fin resumen enriquecido -----------

            try:
                logger.debug(f"Procesando legajo {i}/{stats['total_legajos']} (ID: {legajo_id})")

                if not validar_estructura_legajo(legajo):
                    stats['legajos_con_error'] += 1
                    stats['errores_por_tipo']['estructura_invalida'] += 1
                    logger.warning(f"Estructura inválida en legajo {legajo_id}")
                    continue

                variables_legajo = calcular_variables(legajo)
                if not variables_legajo:
                    logger.debug(f"Legajo {legajo_id} no generó variables calculadas")
                    continue

                for var_codigo, var_valor in variables_legajo:
                    resultados.append((legajo_id, var_codigo, var_valor))

                stats['legajos_procesados'] += 1
                stats['variables_calculadas'] += len(variables_legajo)

                if i % 10 == 0:
                    logger.info(
                        f"📊 Progreso: {i}/{stats['total_legajos']} | "
                        f"Éxitos: {stats['legajos_procesados']} | Errores: {stats['legajos_con_error']}"
                    )

            except Exception as e:
                stats['legajos_con_error'] += 1
                stats['errores_por_tipo'][type(e).__name__] += 1
                logger.error(f"⚠ Error procesando legajo {legajo_id}: {str(e)}")
                try:
                    logger.debug(f"Datos legajo problemático: {json.dumps(legajo, ensure_ascii=False)[:500]}...")
                except Exception:
                    pass  # por si el legajo no es serializable

        # Resultados finales
        if resultados:
            # legajo_id puede ser str/int: normalizamos el sort por str para evitar TypeError
            resultados_ordenados = sorted(resultados, key=lambda x: (str(x[0]), x[1]))
            logger.info(
                f"✅ Proceso completado:\n"
                f"- Legajos procesados: {stats['legajos_procesados']}/{stats['total_legajos']}\n"
                f"- Variables calculadas: {stats['variables_calculadas']}\n"
                f"- Errores: {stats['legajos_con_error']}\n"
                f"- Tipos de errores: {dict(stats['errores_por_tipo'])}"
            )
            return resultados_ordenados, stats, resumen_horarios
        else:
            logger.warning("❌ No se generaron resultados válidos")
            return None, stats, resumen_horarios

    except json.JSONDecodeError as je:
        logger.error(f"El archivo no es un JSON válido: {str(je)}")
        return None, stats, resumen_horarios
    except FileNotFoundError:
        logger.error(f"Archivo no encontrado: {ruta_archivo}")
        return None, stats, resumen_horarios
    except Exception as e:
        logger.critical(f"Error inesperado: {str(e)}\n{traceback.format_exc()}")
        return None, stats, resumen_horarios
    
def guardar_resultados_csv(resultados: List[Tuple[int, int, Any]], nombre_archivo: str = 'variables_calculadas.xlsx') -> None:
    try:
        # Crear libro y hoja
        wb = Workbook()
        ws = wb.active
        ws.title = "Variables Calculadas"

        # Estilo encabezado
        encabezados = ['LEGAJO', 'CODIGO VARIABLE', 'VALOR']
        header_font = Font(bold=True, color="000000")
        header_fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")

        for col_num, encabezado in enumerate(encabezados, 1):
            celda = ws.cell(row=1, column=col_num, value=encabezado)
            celda.font = header_font
            celda.fill = header_fill
            celda.alignment = Alignment(horizontal='center')

        # Cuerpo del Excel
        fila_excel = 2
        for fila in resultados:
            if isinstance(fila, tuple) and len(fila) == 3:
                id_legajo, codigo_variable, valor = fila

                if isinstance(valor, (float, int)):
                    valor_str = f"{valor:.5f}".rstrip('0').rstrip('.').replace('.', ',')
                else:
                    valor_str = str(valor)

                ws.cell(row=fila_excel, column=1, value=id_legajo)
                ws.cell(row=fila_excel, column=2, value=codigo_variable)
                ws.cell(row=fila_excel, column=3, value=valor_str)
                fila_excel += 1
            else:
                logger.warning(f"Se encontró un resultado mal formado y fue omitido: {fila}")

        # Ajuste automático de ancho
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2

        # Guardar archivo
        nombre_archivo = os.path.join(os.getcwd(), nombre_archivo)
        wb.save(nombre_archivo)
        logger.info(f"✅ Archivo Excel guardado con formato visual en: {nombre_archivo}")

    except Exception as e:
        logger.error(f"❌ Error al guardar archivo Excel: {e}", exc_info=True)

def calcular_variables(legajo: Dict[str, Any]) -> List[Tuple[int, Any]]:
    """
    Calcula todas las variables para un legajo según las reglas establecidas.
    """
    variables = []
    id_legajo = legajo.get('id_legajo', 'ID_DESCONOCIDO_EN_CALCULO')
    try:
        logger.debug(f"\nIniciando cálculo para legajo ID: {id_legajo}")

        # 1. Validación inicial (Variable 9000)
        if not validar_horario(legajo):
            logger.warning(f"Legajo {id_legajo}: Horario ambiguo/inválido. Generando 9000")
            variables.append((9000, "No se pudo interpretar correctamente el horario"))
            return variables

        # 2. Variables base (fundacionales)
        v239 = obtener_horas_semanales(legajo)
        variables.append((239, round(v239, 2)))
        logger.debug(f"Legajo {id_legajo}, Variable 239 calculada: {v239}")

        v1242 = calcular_dias_mensuales(legajo)
        variables.append((1242, v1242))
        logger.debug(f"Legajo {id_legajo}, Variable 1242 calculada: {v1242}")
        
        es_guardia_actual = es_guardia(legajo) 
        logger.debug(f"Legajo {id_legajo}, es_guardia_actual: {es_guardia_actual}")

        # Variable 1 - Sueldo básico
        if cumple_condicion_sueldo_basico(legajo):
            sueldo = round(float(legajo['remuneracion']['sueldo_base']), 2) if 'remuneracion' in legajo and 'sueldo_base' in legajo['remuneracion'] else 0.0
            variables.append((1, sueldo))
            logger.debug(f"Legajo {id_legajo}, Variable 1 calculada: {sueldo}")

        # Variable 2000 - Personal de Guardia
        if es_guardia_actual:
            variables.append((2000, 1))
            logger.debug(f"Legajo {id_legajo}, Variable 2000 aplicada (Personal de Guardia)")
        
        # 3. Variables derivadas directamente de 239 y 1242
        v4 = calcular_horas_mensuales(legajo, v239)
        variables.append((4, round(v4, 2)))
        logger.debug(f"Legajo {id_legajo}, Variable 4 calculada: {v4}")

        v1157 = obtener_horas_nocturnas(legajo, es_guardia_actual)
        
        if v239 == v1157 and v239 > 0:
            logger.debug(f"Legajo {id_legajo}: No se calcula V1157, las horas semanales son totalmente nocturnas ({v239}h).")
            if aplicar_adicional_nocturno(legajo, v1157, es_guardia_actual):
                variables.append((1498, 1))
                logger.debug(f"Legajo {id_legajo}, Variable 1498 aplicada (Adicional nocturno)")
        elif v1157 is not None and v1157 > 0:
            variables.append((1157, round(v1157, 2)))
            logger.debug(f"Legajo {id_legajo}, Variable 1157 calculada: {v1157}")
            if aplicar_adicional_nocturno(legajo, v1157, es_guardia_actual):
                variables.append((1498, 1))
                logger.debug(f"Legajo {id_legajo}, Variable 1498 aplicada (Adicional nocturno)")

        v992 = calcular_extension_horaria(legajo, v239)
        if v992 is not None:
            variables.append((992, round(v992, 2)))
            logger.debug(f"Legajo {id_legajo}, Variable 992 calculada: {v992}")

        v1131 = calcular_dias_especiales(legajo, v1242)
        if v1131 is not None:
            variables.append((1131, v1131))
            logger.debug(f"Legajo {id_legajo}, Variable 1131 calculada: {v1131}")

        if aplicar_lavado_uniforme(legajo):
            variables.append((1137, 1))
            logger.debug(f"Legajo {id_legajo}, Variable 1137 aplicada (Lavado de uniforme)")

        # 4. Variables proporcionales/condicionales complejas
        v1167 = calcular_jornada_reducida(legajo, es_guardia_actual)
        if v1167 is not None:
            variables.append((1167, v1167))
            logger.debug(f"Legajo {id_legajo}, Variable 1167 calculada: {v1167}")

        v1416 = calcular_jornada_art19(legajo, v239)
        if v1416 is not None:
            variables.append((1416, v1416))
            logger.debug(f"Legajo {id_legajo}, Variable 1416 aplicada (Jornada art. 19)")

        v1599 = calcular_porcentaje_art19(legajo, v239)
        if v1599 is not None:
            variables.append((1599, round(v1599, 4)))
            logger.debug(f"Legajo {id_legajo}, Variable 1599 calculada: {v1599}")

        if aplicar_proporcion_lavado(legajo):
            variables.append((1673, 1))
            logger.debug(f"Legajo {id_legajo}, Variable 1673 aplicada (Proporción lavado)")

        # 5. Variables administrativas
        fecha_fin = obtener_fecha_fin_contrato(legajo)
        if fecha_fin:
            variables.append((2006, fecha_fin))
            logger.debug(f"Legajo {id_legajo}, Variable 2006 calculada: {fecha_fin}")

        if aplicar_no_liquida_plus(legajo, es_guardia_actual):
            variables.append((2281, 1))
            logger.debug(f"Legajo {id_legajo}, Variable 2281 aplicada (No liquida plus)")

        if es_cajero(legajo):
            variables.append((426, 1))
            logger.debug(f"Legajo {id_legajo}, Variable 426 aplicada (Caja/Seguro)")

        # Variables informativas, médicas, etc.
        procesar_variables_informativas(legajo, variables)
        if es_medico_productividad(legajo):
            variables.extend([(1740, 1), (1251, 1), (1252, 1)])
            logger.debug(f"Legajo {id_legajo}, Variables médicas aplicadas (1740, 1251, 1252)")

        logger.info(f"Legajo {id_legajo}: {len(variables)} variables calculadas correctamente")
        
        logger.debug(f"--- Variables finales para Legajo {id_legajo}: {variables} ---")
        return variables

    except Exception as e:
        logger.error(f"Error calculando variables para legajo {id_legajo}: {str(e)}", exc_info=True)
        logger.debug(f"--- DEBUG: ERROR! Lista de variables hasta el momento para Legajo {id_legajo}: {variables} ---")
        return []
    
# FUNCIONES DE VALIDACIÓN
# ==============================

def validar_estructura_legajo(legajo: Dict[str, Any]) -> bool:
    """Valida que el legajo tenga la estructura mínima requerida"""
    campos_requeridos = ['id_legajo', 'datos_personales', 'contratacion', 'horario', 'remuneracion']

    if not all(k in legajo for k in campos_requeridos):
        logger.warning(f"Legajo {legajo.get('id_legajo', 'DESCONOCIDO')} tiene estructura incompleta")
        return False

    subcampos_requeridos = [
        ('datos_personales', ['nombre', 'sector', 'puesto', 'sede']), 
        ('contratacion', ['tipo', 'categoria', 'fechas']),
        ('horario', ['bloques', 'resumen']),
        ('remuneracion', ['sueldo_base', 'moneda'])
    ]

    for campo, subcampos in subcampos_requeridos:
        if not all(k in legajo.get(campo, {}) for k in subcampos):
            logger.warning(f"Legajo {legajo['id_legajo']} no tiene todos los subcampos requeridos en {campo}")
            return False

    return True

def validar_horario(legajo: Dict[str, Any]) -> bool:
    """
    Valida si el horario es interpretable

    Args:
        legajo: Diccionario con datos del legajo

    Returns:
        True si el horario es válido, False si es ambiguo/inválido
    """
    if not legajo['horario']['bloques']:
        logger.warning(f"Legajo {legajo['id_legajo']}: Horario vacío")
        return False

    # Validación adicional de estructura de bloques horarios
    for bloque in legajo['horario']['bloques']:
        if not all(k in bloque for k in ['dias_semana', 'hora_inicio', 'hora_fin']):
            logger.warning(f"Legajo {legajo['id_legajo']}: Bloque horario incompleto")
            return False

    return True

def contiene_full_guardia(texto: str) -> bool:
    """
    Detecta 'full guardia' en cualquier formato con tolerancia a:
    - Mayúsculas/minúsculas
    - Espacios extras: 'full  guardia'
    - Guiones: 'full-guardia'
    - Typos menores: 'ful guardia', 'fullgardia'
    """
    if not texto or not isinstance(texto, str):
        return False
    
    texto_limpio = re.sub(r'[^\w\s-]', ' ', texto.lower())  # Elimina puntuación excepto guiones
    texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()  # Normaliza espacios
    
    patron = re.compile(
        r'(?:full\s*[-]?\s*gu?a?rdia|gu?a?rdia\s*[-]?\s*full)',  # Admite orden invertido
        re.IGNORECASE
    )
    return bool(patron.search(texto_limpio))

def es_guardia(legajo: Dict[str, Any]) -> bool:
    """
    Determina si un legajo es GUARDIA según 3 condiciones acumulativas:
    1) Sede válida (según lista normalizada)
    2) Contiene 'full guardia' en adicionables
    3) Trabaja como máximo 3 días por semana
    """
    try:
        id_legajo = legajo.get('id_legajo', 'N/A')
        sede_raw = legajo.get('datos_personales', {}).get('sede', '')
        sede_normalizada = normalizar_texto(sede_raw)

        sede_valida = sede_normalizada in sedes_permitidas
        logger.debug(f"[es_guardia] Legajo {id_legajo}: Sede normalizada = '{sede_normalizada}', válida = {sede_valida}")
        if not sede_valida:
            logger.debug(f"[es_guardia] Legajo {id_legajo}: Sede '{sede_raw}' NO válida.")
            return False

        # --- 2. Validación de Adicionables ---
        adicionables = str(legajo.get('remuneracion', {}).get('adicionables') or '')
        adicionables_normalizados = normalizar_texto(adicionables)

        if 'full guardia' not in adicionables_normalizados:
            logger.debug(f"[es_guardia] Legajo {id_legajo}: Adicionables NO contienen 'full guardia'.")
            return False

        # --- 3. Validación de Días Trabajados ---
        bloques = legajo.get('horario', {}).get('bloques', [])
        dias_trabajados = set()

        for bloque in bloques:
            dias = bloque.get('dias_semana', [])
            if isinstance(dias, list):
                dias_trabajados.update(dias)

        if len(dias_trabajados) > 3:
            logger.debug(f"[es_guardia] Legajo {id_legajo}: Trabaja {len(dias_trabajados)} días (>3).")
            return False

        # --- Pasa TODAS las condiciones ---
        logger.info(f"[es_guardia] Legajo {id_legajo}: ✅ Validado como GUARDIA (sede='{sede_raw}', días={len(dias_trabajados)})")
        return True

    except Exception as e:
        logger.error(f"[es_guardia] Legajo {legajo.get('id_legajo', 'N/A')}: ❌ Error inesperado - {str(e)}")
        logger.error(traceback.format_exc())
        return False

    # 1. Helper function adaptada para el formato de tus constantes
def es_puesto_especial(puesto_normalizado: str) -> bool:
    """Versión mejorada para evitar falsos positivos"""
    # Limpieza adicional
    puesto_limpio = re.sub(r'\s+\bde\b\s+', ' ', puesto_normalizado).strip().lower()
    puesto_limpio = re.sub(r'[^a-z0-9 ]', '', puesto_limpio)  # Elimina caracteres especiales
    
    # Comparación más estricta
    for puesto_especial in PUESTOS_ESPECIALES.values():
        especial_limpio = re.sub(r'\s+\bde\b\s+', ' ', puesto_especial).strip().lower()
        especial_limpio = re.sub(r'[^a-z0-9 ]', '', especial_limpio)
        
        # Coincidencia exacta o comienzo del string
        if (puesto_limpio == especial_limpio or 
            puesto_limpio.startswith(especial_limpio + " ") or 
            especial_limpio.startswith(puesto_limpio + " ")):
            return True
            
    return False

def _parse_fecha_flexible(valor: Any) -> Optional[datetime]:
    """
    Intenta parsear una fecha en múltiples formatos comunes.
    Soporta:
      - Separadores: '/', '-', '.'
      - Años de 2 o 4 dígitos (25 -> 2025 por %y)
      - Ordenes habituales: dd/mm/aa(aa), dd-mm-aa(aa), aa(aa)-mm-dd, aa(aa)/mm/dd, dd.mm.aa(aa)
    Retorna un datetime o None si no pudo parsear.
    """
    logger = logging.getLogger(__name__)

    if valor is None:
        return None

    # Normalizar a str y limpiar espacios
    s = str(valor).strip()
    if not s:
        return None

    # Normalizamos unicode (por si viene con caracteres raros)
    s = unicodedata.normalize("NFKC", s)

    # Cambiamos cualquier separador no numérico por '/'
    s_norm = re.sub(r"[^0-9]", "/", s)
    s_norm = re.sub(r"/+", "/", s_norm).strip("/")

    # Lista de formatos a probar (dos y cuatro dígitos de año)
    formatos = [
        "%d/%m/%Y", "%d/%m/%y",
        "%d-%m-%Y", "%d-%m-%y",  # por si el usuario no normalizó separadores
        "%Y/%m/%d", "%y/%m/%d",
        "%Y-%m-%d", "%y-%m-%d",
        "%d.%m.%Y", "%d.%m.%y",
    ]

    # Primero probamos con la cadena original y sus variantes normalizadas
    candidatos = {s, s_norm, s_norm.replace("/", "-"), s_norm.replace("/", ".")}

    for cand in list(candidatos):
        for fmt in formatos:
            try:
                # Si el formato usa '-' o '.' lo probamos también
                cand_fmt = cand
                if "." in fmt:
                    cand_fmt = cand.replace("/", ".")
                elif "-" in fmt:
                    cand_fmt = cand.replace("/", "-")
                else:
                    cand_fmt = cand.replace("-", "/").replace(".", "/")

                dt = datetime.strptime(cand_fmt, fmt)
                # %y mapea 00-68 a 2000-2068 -> "25" => 2025 (justo lo que queremos)
                return dt
            except ValueError:
                continue

    # Heurística extra: si tenemos exactamente 3 grupos numéricos, intentamos reordenar
    partes = re.split(r"[^\d]", s)
    partes = [p for p in partes if p.isdigit()]
    if len(partes) == 3:
        d, m, a = partes[0], partes[1], partes[2]
        # Intento dd/mm/aa(aa)
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(f"{d}/{m}/{a}", fmt)
            except ValueError:
                pass
        # Intento aa(aa)/mm/dd
        for fmt in ("%Y/%m/%d", "%y/%m/%d"):
            try:
                return datetime.strptime(f"{a}/{m}/{d}", fmt)
            except ValueError:
                pass

    logger.debug(f"_parse_fecha_flexible: no se pudo interpretar la fecha '{valor}'")
    return None

# ==============================
# FUNCIONES DE CÁLCULO
# ==============================

def obtener_horas_semanales(legajo: Dict[str, Any]) -> float:
    try:
        # Uso robusto de .get()
        horas_raw = legajo.get('horario', {}).get('resumen', {}).get('total_horas_semanales')

        if horas_raw is None:
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: 'total_horas_semanales' es None. Devolviendo 0.0.")
            return 0.0

        horas = float(horas_raw)
        if horas < 0 or horas > 168:
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: Horas semanales fuera de rango ({horas})")
            return 0.0
        return horas
    except (TypeError, ValueError) as e: # KeyError ya no es probable con .get()
        logger.error(f"Legajo {legajo.get('id_legajo', 'N/A')}: Error al convertir horas semanales a float - {str(e)}")
        return 0.0
    except Exception as e: # Para cualquier otro error inesperado
        logger.error(f"Legajo {legajo.get('id_legajo', 'N/A')}: Error inesperado al obtener horas semanales - {str(e)}")
        logger.error(traceback.format_exc())
        return 0.0

def calcular_dias_mensuales(legajo: Dict[str, Any]) -> int:
    """
    Calcula días mensuales ajustando correctamente días con periodicidad quincenal o parcial.
    Versión corregida: procesa correctamente todos los bloques por día.
    """
    id_legajo = legajo.get("id_legajo", "DESCONOCIDO")

    try:
        bloques_por_dia = legajo.get("horario", {}).get("resumen", {}).get("bloques_por_dia", {})

        if not isinstance(bloques_por_dia, dict) or not bloques_por_dia:
            logger.warning(f"Legajo {id_legajo}: 'bloques_por_dia' ausente o vacío.")
            return 0

        dias_semanales = 0.0

        for dia_str, bloques in bloques_por_dia.items():
            if not isinstance(bloques, list) or not bloques:
                continue

            dia_procesado = False

            for bloque in bloques:
                if not isinstance(bloque, dict):
                    continue
                    
                periodicidad = str(bloque.get("periodicidad", "")).lower()
                
                if periodicidad == "semanal" and not dia_procesado:
                    dias_semanales += 1.0
                    dia_procesado = True
                    logger.debug(f"Legajo {id_legajo}: Día {dia_str} → semanal (1.0)")
                    
                elif periodicidad == "quincenal" and not dia_procesado:
                    dias_semanales += 0.5
                    dia_procesado = True
                    logger.debug(f"Legajo {id_legajo}: Día {dia_str} → quincenal (0.5)")
                    
                elif periodicidad == "proporcional" and not dia_procesado:
                    # CALCULAR FACTOR PROPORCIONAL
                    horas_semanales = bloque.get("horas_semanales", 0)
                    duracion_total = bloque.get("duracion_total", 1)
                    
                    if duracion_total > 0 and horas_semanales > 0:
                        factor = horas_semanales / duracion_total
                    else:
                        factor = 0.75  # Default
                    
                    dias_semanales += factor
                    dia_procesado = True
                    logger.debug(f"Legajo {id_legajo}: Día {dia_str} → proporcional (factor {factor})")

            # Si no se procesó el día (sin periodicidad reconocida), contar como semanal
            if not dia_procesado:
                dias_semanales += 1.0
                logger.debug(f"Legajo {id_legajo}: Día {dia_str} → sin periodicidad (1.0)")

        dias_mensuales = dias_semanales * 4.33
        parte_entera = int(dias_mensuales)
        parte_decimal = dias_mensuales - parte_entera
        dias_mensuales_redondeados = parte_entera + 1 if parte_decimal >= 0.5 else parte_entera

        logger.info(
            f"Legajo {id_legajo}: Días semanales efectivos = {dias_semanales:.2f}, "
            f"mensuales estimados = {dias_mensuales:.2f}, redondeado = {dias_mensuales_redondeados}"
        )

        return dias_mensuales_redondeados

    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error al calcular días mensuales. Detalle: {str(e)}")
        logger.error(traceback.format_exc())
        return 0
    
def cumple_condicion_sueldo_basico(legajo: Dict[str, Any]) -> bool:
    """
    Determina si aplica el sueldo básico (Variable 1) de forma robusta.
    """
    try:
        # 1. Se comprueban las condiciones de negocio primero para una salida rápida.
        if legajo['contratacion']['categoria'] != 'fc_pfc':
            return False

        sueldo = legajo['remuneracion']['sueldo_base']
        if sueldo is None:
            return False

        # 2. La validación numérica clave: intentar convertir el valor a float.
        #    Esta es la forma canónica en Python de verificar si algo es numérico.
        float(sueldo)

        return True

    except (KeyError, ValueError, TypeError):
        # Capturamos errores específicos de forma segura:
        # - KeyError: Si falta una clave como 'categoria' o 'sueldo_base'.
        # - ValueError / TypeError: Si el valor de 'sueldo' no puede convertirse a número (ej: "texto").
        return False

def obtener_horas_nocturnas(legajo: Dict[str, Any], es_guardia: bool) -> float:
    """
    Calcula horas nocturnas válidas para un legajo, considerando:
    - Guardias: siempre retorna 0.0
    - No guardias: horas del resumen horario (validando estructura)
    
    Args:
        legajo: Diccionario con datos del legajo
        es_guardia: Resultado de la función es_guardia()
        
    Returns:
        float: Horas nocturnas entre 0-168 (0 si hay errores)
    """
    # 1. Guardias no acumulan horas nocturnas
    if es_guardia:
        logger.debug(f"Legajo {legajo.get('id_legajo', 'N/A')}: Es guardia - horas nocturnas=0")
        return 0.0
    
    try:
        # 2. Obtener y validar horas de forma robusta
        horas_raw = legajo.get('horario', {}).get('resumen', {}).get('total_horas_nocturnas', 0)
        
        # Log de depuración para verificar el valor extraído
        logger.debug(f"Legajo {legajo.get('id_legajo', 'N/A')}: Horas nocturnas 'raw' extraídas: {horas_raw}")
        
        horas = float(horas_raw)
        
        # 3. Aplicar límites razonables (0 <= horas <= 168)
        horas_validas = max(0.0, min(horas, 168.0))
        
        if abs(horas_validas - horas) > 0.01:  # Tolerancia para floats
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: Ajustadas horas nocturnas {horas} → {horas_validas}")
        
        logger.debug(f"Legajo {legajo.get('id_legajo', 'N/A')}: Horas nocturnas válidas = {horas_validas}")
        return horas_validas
        
    except (TypeError, ValueError) as e:
        logger.error(f"Legajo {legajo.get('id_legajo', 'N/A')}: Valor inválido en horas nocturnas - {str(e)}")
        return 0.0
    except Exception as e:
        logger.error(f"Legajo {legajo.get('id_legajo', 'N/A')}: Error crítico - {str(e)}")
        logger.error(traceback.format_exc())
        return 0.0
    
def aplicar_lavado_uniforme(legajo: Dict[str, Any]) -> bool:
    """Determina si aplica lavado de uniforme (Variable 1137) de forma SUPER ROBUSTA."""
    try:
        # Acceder a 'datos_personales' de forma segura
        datos_personales = legajo.get('datos_personales')
        if not isinstance(datos_personales, dict):
            logger.warning(f"Legajo {legajo.get('id_legajo', 'UNKNOWN')}: 'datos_personales' es None o no es un diccionario válido.")
            return False

        # Normalizar el campo 'puesto' usando tu función
        puesto_raw = datos_personales.get('puesto')
        puesto_normalizado = normalizar_texto(puesto_raw) # <--- ¡Aquí está la corrección!

        # Acceder a 'sector' dentro de 'datos_personales' de forma segura
        sector_data = datos_personales.get('sector')
        if not isinstance(sector_data, dict):
            logger.warning(f"Legajo {legajo.get('id_legajo', 'UNKNOWN')}: El campo 'sector' es None o no es un diccionario válido para validación de lavado de uniforme.")
            return False

        # Normalizar el campo 'subsector' usando tu función
        subsector_raw = sector_data.get('subsector')
        subsector_normalizado = normalizar_texto(subsector_raw) # <--- ¡Aquí está la corrección!

        # La lógica de negocio utiliza los valores normalizados para la comparación
        # Asegúrate de que los strings de comparación también estén normalizados
        return (puesto_normalizado == normalizar_texto("OPERARIO DE LOGISTICA") and
                subsector_normalizado == normalizar_texto("INTERIOR"))

    except KeyError as ke:
        logger.error(f"Legajo {legajo.get('id_legajo', 'UNKNOWN')}: Falta clave esencial para validar lavado de uniforme - {str(ke)}")
        return False
    except Exception as e:
        logger.error(f"Legajo {legajo.get('id_legajo', 'UNKNOWN')}: Error general validando lavado de uniforme - {str(e)}")
        logger.error(traceback.format_exc())
        return False

def aplicar_adicional_nocturno(legajo: Dict[str, Any], horas_nocturnas: float, es_guardia: bool) -> bool:
    """
    Determina si aplica adicional nocturno según:
    1) NO sea guardia
    2) Tenga horas nocturnas > 0
    3) Pertenezca a categoría DC (Dentro de Convenio)
    Args:
        legajo: Diccionario con datos del legajo
        horas_nocturnas: Horas calculadas por obtener_horas_nocturnas()
        es_guardia: Resultado de es_guardia()
    Returns:
        bool: True si cumple TODAS las condiciones
    """
    id_legajo = legajo.get('id_legajo', 'N/A')
    
    # --- LOGS DE DEPURACIÓN AGREGADOS ---
    logger.debug(f"Legajo {id_legajo}: Evaluando adicional nocturno. es_guardia={es_guardia}, horas_nocturnas={horas_nocturnas}")

    # 1. Excepciones rápidas (guardias o sin horas nocturnas)
    if es_guardia:
        logger.debug(f"Legajo {id_legajo}: Excluido (es guardia) → Falso")
        return False
    if horas_nocturnas <= 0:
        logger.debug(f"Legajo {id_legajo}: Excluido (0 horas nocturnas) → Falso")
        return False

    try:
        # 2. Validar categoría
        categoria = legajo.get('contratacion', {}).get('categoria', '')
        
        # --- LOG DE DEPURACIÓN PARA LA CATEGORÍA ---
        logger.debug(f"Legajo {id_legajo}: Categoría a evaluar: '{categoria}'")
        
        if not categoria:
            logger.warning(f"Legajo {id_legajo}: Categoría vacía → Falso")
            return False
            
        # 3. Verificar convenio (DC = Dentro de Convenio)
        es_dc = str(categoria).lower().startswith('dc_')
        
        logger.info(
            f"Legajo {id_legajo}: "
            f"Adicional nocturno {'APLICA' if es_dc else 'NO aplica'} "
            f"(Categoría: {categoria}, Horas: {horas_nocturnas})"
        )
        return es_dc
        
    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error crítico - {str(e)}")
        logger.error(traceback.format_exc())
        return False

def obtener_fecha_fin_contrato(legajo: Dict[str, Any]) -> Optional[str]:
    """
    Lee 'contratacion.fechas.fin' y 'contratacion.tipo'.
    Si el tipo indica plazo fijo/determinado y la fecha es parseable,
    devuelve la fecha en formato dd/mm/YYYY; en caso contrario, None.
    Acepta años de 2 dígitos (25 -> 2025).
    """
    logger = logging.getLogger(__name__)
    try:
        contratacion = legajo.get("contratacion", {}) or {}
        tipo_contrato = str(contratacion.get("tipo", "") or "").lower()
        fechas = contratacion.get("fechas", {}) or {}
        fecha_fin_raw = fechas.get("fin")

        # Solo aplica si el tipo sugiere contrato a plazo/determinado
        # (soporta 'plazo_fijo', 'tiempo_completo_plazo_fijo', 'determinado', etc.)
        if not any(t in tipo_contrato for t in ("plazo_fijo", "determinado")):
            return None

        fecha_obj = _parse_fecha_flexible(fecha_fin_raw)
        if not fecha_obj:
            logger.warning(
                f"Legajo {legajo.get('id_legajo', 'N/A')}: "
                f"No se pudo interpretar fecha de fin '{fecha_fin_raw}'"
            )
            return None

        return fecha_obj.strftime("%d/%m/%Y")

    except Exception as e:
        logger.error(
            f"Legajo {legajo.get('id_legajo', 'N/A')}: "
            f"Error obteniendo fecha fin contrato - {e}",
            exc_info=True
        )
        return None

def aplicar_no_liquida_plus(legajo: Dict[str, Any], es_guardia: bool) -> bool:
    """
    Determina si un legajo no debe liquidar plus, considerando:
    - No es guardia O
    - Legajo <= 15000 O
    - Pertenece a sedes excluidas (C. DEL SOL, BAZTERRICA, etc.)
    
    Args:
        legajo: Diccionario con datos del legajo
        es_guardia: Booleano que indica si es guardia
        
    Returns:
        bool: True si NO debe liquidar plus, False si sí debe
    """
    # 1. Excepciones básicas
    if not es_guardia or legajo.get('id_legajo', 0) <= 15000:
        return False
    
    # 2. Obtención robusta de la sede
    try:
        sede_actual = legajo.get('datos_personales', {}).get('sede')
        if not sede_actual:  # None o cadena vacía
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: Sede no definida")
            return False
        
        # 3. Lista de sedes excluidas (usar nombres normalizados)
        SEDES_NO_LIQUIDA_PLUS = {
            'Clínica del Sol',  # Asegurar que coincida con tu normalización
            'Bazterrica',
            'CLINICA DEL SOL',  # Versión alternativa por si acaso
            'BAZTERRICA'
        }
        
        # 4. Comparación case-insensitive
        return sede_actual.upper() in {s.upper() for s in SEDES_NO_LIQUIDA_PLUS}
        
    except Exception as e:
        logger.error(f"Error en legajo {legajo.get('id_legajo', 'N/A')}: {str(e)}")
        logger.error(traceback.format_exc())
        return False  # Por defecto, no aplicar restricción si hay error

def es_cajero(legajo: Dict[str, Any]) -> bool:
    try:
        puesto_raw = legajo.get('datos_personales', {}).get('puesto') # Agregué {} a .get('datos_personales')
        puesto = normalizar_texto(puesto_raw) # <--- ¡CORRECCIÓN CLAVE! Usa normalizar_texto
        if not puesto: # Si es None o vacío después de normalizar
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: Puesto es vacío/None para validación de cajero.")
            return False

        categoria_raw = legajo.get('contratacion', {}).get('categoria') # Agregué {} a .get('contratacion')
        categoria = normalizar_texto(categoria_raw) # <--- ¡CORRECCIÓN CLAVE! Usa normalizar_texto
        if not categoria: # Si es None o vacío después de normalizar
            logger.warning(f"Legajo {legajo.get('id_legajo', 'N/A')}: Categoría es vacío/None para validación de cajero.")
            return False

        # Asegúrate de que las cadenas de comparación también estén normalizadas
        return (("CAJERO" in puesto.upper() or "CAJERO/A" in puesto.upper()) and
                any(adm in categoria for adm in ['adm', 'administrativo']))
    except KeyError as ke:
        logger.error(f"Legajo {legajo.get('id_legajo', 'DESCONOCIDO')}: Falta clave en datos para validar cajero - {str(ke)}")
        return False
    except Exception as e:
        logger.error(f"Legajo {legajo.get('id_legajo', 'DESCONOCIDO')}: Error validando cajero - {str(e)}")
        logger.error(traceback.format_exc())
        return False

def procesar_variables_informativas(legajo: Dict[str, Any], variables: List[Tuple[int, Any]]) -> None:
    id_legajo = legajo.get('id_legajo', 'N/A')
    try:
        # Obtener el valor de 'adicionables' de forma robusta.
        adicionables_raw = legajo.get('remuneracion', {}).get('adicionables', '')
        adicionables_normalizado = normalizar_texto(adicionables_raw) if adicionables_raw else ""
        
        # Aplicar reemplazos específicos para 'intangibilidad' ANTES de la verificación
        adicionables_para_intang = (adicionables_normalizado
                                    .replace("intang", "intangibilidad")
                                    .replace("intang.", "intangibilidad")
                                    .replace("intan", "intangibilidad")
                                    .replace("intangib", "intangibilidad"))

        # Obtener el valor de sueldo_base
        sueldo_base = legajo.get('remuneracion', {}).get('sueldo_base')  # Puede ser None si no existe o es null

        # --- Variables 7000 (Cesión) y 8000 (Intangibilidad) ---
        if any(term in adicionables_normalizado for term in TERMINOS_CESION):
            variables.append((7000, "Es cesión, revisar."))
            logger.debug(f"Legajo {id_legajo}: Variable 7000 aplicada (Cesión)")

        if "intangibilidad" in adicionables_para_intang:
            variables.append((8000, "Revisar Importe o % para Intangibilidad Salarial"))
            logger.debug(f"Legajo {id_legajo}: Variable 8000 aplicada (Intangibilidad)")

        # --- Nueva Variable 9000 (Adicional Voluntario) ---
        terminos_adic_voluntario = ["adic voluntario", "adicional voluntario", "voluntario empresa"]
        if any(term in adicionables_normalizado for term in terminos_adic_voluntario):
            variables.append((9000, "Revisar Adic Voluntario Empresa"))
            logger.debug(f"Legajo {id_legajo}: Variable 9000 aplicada (Adic Voluntario)")

        # --- Nueva Variable 11000 (PPR) ---
        ppr_en_adicionables = "ppr" in adicionables_normalizado
        sueldo_base_tiene_valor = sueldo_base is not None
        logger.debug(
            f"Legajo {id_legajo}: Evaluación V11000 -> ¿'PPR' en adicionables? {ppr_en_adicionables}. "
            f"¿Sueldo base tiene valor? {sueldo_base_tiene_valor} (valor: {sueldo_base})"
        )
        if ppr_en_adicionables and sueldo_base_tiene_valor:
            variables.append((11000, "Tiene PPR. Revisar archivo"))
            logger.debug(f"Legajo {id_legajo}: Variable 11000 aplicada (PPR)")

        # --- Variable 10000 (Licenciado Bioimágenes) ---
        if es_licenciado_bioimagenes(legajo):
            variables.append((10000, "Cargar Título en CP, es Licenciado"))
            logger.debug(f"Legajo {id_legajo}: Variable 10000 aplicada (Licenciado Bioimágenes)")

        # --- Variable 12000 (Falta sueldo bruto pactado para PFC) ---
        # Dispara si:
        #  - categoría == fc_pfc
        #  - falta sueldo_base (ausente, None o "")
        #  - NO dice "full guardia" en adicionables
        categoria = (legajo.get('contratacion', {}).get('categoria') or '').strip().lower()
        remuneracion = legajo.get('remuneracion', {})

        if categoria == "fc_pfc":
            sueldo_base_falta = (not isinstance(remuneracion, dict) or
                                 ('sueldo_base' not in remuneracion) or
                                 remuneracion.get('sueldo_base') in (None, ""))
            tiene_full_guardia = "full guardia" in adicionables_normalizado  # ya normalizado arriba

            logger.debug(
                f"Legajo {id_legajo}: Evaluación V12000 -> "
                f"categoria={categoria}, sueldo_base_falta={sueldo_base_falta}, "
                f"tiene_full_guardia={tiene_full_guardia}"
            )

            if sueldo_base_falta and not tiene_full_guardia:
                variables.append((12000, "Falta sueldo bruto pactado. Revisar Var 1"))
                logger.debug(f"Legajo {id_legajo}: Variable 12000 aplicada (Falta sueldo bruto pactado)")

    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error procesando variables informativas - {str(e)}", exc_info=True)

def es_medico_productividad(legajo: Dict[str, Any]) -> bool:
    """Determina si es médico de productividad (Variables 1740, 1251, 1252)"""
    try:
        puesto = legajo.get('datos_personales', {}).get('puesto')
        sector = legajo.get('datos_personales', {}).get('sector', {}).get('principal')

        if puesto is None or sector is None:
            logger.warning(f"Legajo {legajo.get('id_legajo', 'DESCONOCIDO')}: Puesto o sector principal es None para médico de productividad.")
            return False

        puesto_normalizado = normalizar_texto(puesto)
        sector_normalizado = normalizar_texto(sector)

        return (puesto_normalizado == PUESTOS_ESPECIALES['MEDICO'] and
                sector_normalizado in SECTORES_MEDICOS)
    except Exception as e:
        logger.error(f"Legajo {legajo.get('id_legajo', 'DESCONOCIDO')}: Error validando médico productividad - {str(e)}")
        return False

def es_licenciado_bioimagenes(legajo: Dict[str, Any]) -> bool:
    """
    Determina si aplica la variable 10000 (Licenciado en Bioimágenes) para un legajo,
    con normalización de inputs y búsqueda flexible en 'adicionables'.

    Args:
        legajo: Diccionario con los datos completos del legajo.

    Returns:
        bool: True si el legajo cumple con las condiciones para la variable 10000, False en caso contrario.
    """
    id_legajo = legajo.get('id_legajo', 'DESCONOCIDO')
    logger.debug(f"Evaluando 'es_licenciado_bioimagenes' para legajo ID: {id_legajo}")

    try:
        # 1. Obtener y normalizar el PUESTO
        puesto_raw = legajo.get('datos_personales', {}).get('puesto')
        if puesto_raw is None:
            logger.debug(f"Legajo {id_legajo}: Puesto es None. No aplica variable 10000.")
            return False
        puesto_normalizado = normalizar_texto(puesto_raw)

        # 2. Obtener y normalizar el SECTOR PRINCIPAL
        sector_data = legajo.get('datos_personales', {}).get('sector')
        if sector_data is None or not isinstance(sector_data, dict):
            logger.debug(f"Legajo {id_legajo}: Datos de sector inválidos o None. No aplica variable 10000.")
            return False
        sector_principal_raw = sector_data.get('principal')
        if sector_principal_raw is None:
            logger.debug(f"Legajo {id_legajo}: Sector principal es None. No aplica variable 10000.")
            return False
        sector_principal_normalizado = normalizar_texto(sector_principal_raw)

        # 3. Obtener y normalizar el campo 'ADICIONABLES'
        adicionables_raw = legajo.get('remuneracion', {}).get('adicionables')
        # Si 'adicionables' es None, se normalizará a una cadena vacía, lo cual es correcto para la búsqueda.
        adicionables_normalizado = normalizar_texto(adicionables_raw)

        # --- EVALUACIÓN DE CONDICIONES ---

         # Condición A: Puesto en la lista de puestos válidos (usando la clase de configuración)
        puesto_cumple = puesto_normalizado in ConfigBioimagenes.PUESTOS_VALIDOS
        if not puesto_cumple:
            logger.debug(
                f"Legajo {id_legajo}: Puesto '{puesto_normalizado}' no es uno de los válidos definidos en ConfigBioimagenes. "
                "No aplica variable 10000."
            )
            return False

        # Condición B: Sector en la lista de sectores válidos para 156 horas
        sector_cumple = sector_principal_normalizado in SECTORES_ESPECIALES.get('HORAS_156', [])
        if not sector_cumple:
            logger.debug(f"Legajo {id_legajo}: Sector '{sector_principal_normalizado}' no es uno de los válidos para 156 hs. No aplica variable 10000.")
            return False

        # Condición C: Alguno de los términos de 'adicionales' está presente
        termino_adicional_cumple = any(
             termino in adicionables_normalizado for termino in ConfigBioimagenes.TERMINOS_ADICIONALES
        )
        if not termino_adicional_cumple:
            logger.debug(f"Legajo {id_legajo}: No se encontró ningún término de bioimágenes/título en 'adicionables': '{adicionables_normalizado}'. No aplica variable 10000.")
            return False

        # Si todas las condiciones se cumplen
        logger.info(f"Legajo {id_legajo}: Se cumple la condición para la variable 10000 (Licenciado en Bioimágenes).")
        return True

    except KeyError as ke:
        logger.error(f"Legajo {id_legajo}: Error de clave (KeyError) al procesar datos para variable 10000. Detalles: {str(ke)}")
        logger.error(traceback.format_exc())
        return False
    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error inesperado al validar Licenciado en Bioimágenes. Detalles: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def calcular_horas_mensuales(legajo: Dict[str, Any], v239: float) -> float:
    """
    Calcula la variable 4 - Horas mensuales según reglas específicas.
    Aplica lógica robusta con normalización y control de errores.
    """
    id_legajo = legajo.get('id_legajo', 'N/A')
    try:
        # 1. Acceso seguro y normalización
        datos = legajo.get("datos_personales", {})
        puesto = normalizar_texto(datos.get("puesto")) # <--- Aquí se normaliza el 'puesto' del legajo
        sector = normalizar_texto(datos.get("sector", {}).get("principal"))

        logger.debug(f"DEBUG INICIO FUNCION: Legajo {id_legajo}, Puesto RAW='{datos.get('puesto')}', Puesto NORMALIZADO='{puesto}', Sector='{sector}', v239={v239}")

        # 2. Casos especiales de 200 hs
        if (
            (sector == "cuat" and puesto == PUESTOS_ESPECIALES['TELEFONISTA'] and v239 == 35) or
            (puesto == PUESTOS_ESPECIALES['RECEP_LAB'] and v239 == 35) or
            (puesto == PUESTOS_ESPECIALES['TEC_CARDIO'] and v239 >= 35) or
            (puesto == PUESTOS_ESPECIALES['OP_LOGISTICA'] and v239 >= 35) or
            (sector == "atencion al cliente laboratorio" and puesto == "recepcionista" and v239 >= 35)
        ):
            logger.info(f"Legajo {id_legajo}: Caso especial → 200 horas (Puesto + condición)")
            return 200.00
        else:
            logger.debug(f"DEBUG: Legajo {id_legajo}: No cumple caso 200hs. Condición evaluada: {(sector == 'cuat' and puesto == PUESTOS_ESPECIALES['TELEFONISTA'] and v239 == 35)} || {(puesto == PUESTOS_ESPECIALES['RECEP_LAB'] and v239 == 35)} || {(puesto == PUESTOS_ESPECIALES['TEC_CARDIO'] and v239 >= 35)} || {(puesto == PUESTOS_ESPECIALES['OP_LOGISTICA'] and v239 >= 35)}")

        # 3. Casos de puestos con piso 27 horas (bioquímicos, técnicos, etc.)
        puestos_piso_27 = [normalizar_texto(p) for p in [
            "AUXILIAR TECNICO", "TECNICO DE LABORATORIO",
            "TECNICO EXTRACCIONISTA", "BIOQUIMICO"
        ]]

        if puesto in puestos_piso_27:
            if 27 <= v239 <= 36:  # ✅ Rango exacto 27-36 → 156 horas
                logger.info(f"Legajo {id_legajo}: Puesto con piso 27 reconocido, v239={v239} entre 27-36 → 156 horas")
                return 156.00
            elif v239 < 27:  # ✅ Menos de 27 → proporcional 27 × 4.33
                horas_proporcionales = round(27 * 4.33, 2)
                logger.info(f"Legajo {id_legajo}: Puesto con piso 27, v239={v239} < 27 → proporcional {horas_proporcionales}")
                return horas_proporcionales
            else:  # ✅ Más de 36 → continúa al siguiente caso
                logger.debug(f"DEBUG: Legajo {id_legajo}: Puesto con piso 27, pero v239={v239} > 36, continúa evaluación")
        else:
            logger.debug(f"DEBUG: Legajo {id_legajo}: No es puesto con piso 27. Puesto '{puesto}' en {puestos_piso_27}: {puesto in puestos_piso_27}")

        # 4. Casos de puestos técnicos con piso 18 horas
        if (
            puesto in [normalizar_texto("TECNICO"), normalizar_texto("TECNICO PIVOT")]
            and sector != SECTOR_EXCLUIDO_LABORATORIO
            and 18 <= v239 <= 36
        ):
            logger.info(f"Legajo {id_legajo}: Puesto técnico 156 válido, v239={v239}")
            return 156.00
        else:
            logger.debug(f"DEBUG: Legajo {id_legajo}: No cumple caso técnicos 156hs. Puesto '{puesto}' en tecnicos: {puesto in [normalizar_texto('TECNICO'), normalizar_texto('TECNICO PIVOT')]}. Sector '{sector}' != '{SECTOR_EXCLUIDO_LABORATORIO}': {sector != SECTOR_EXCLUIDO_LABORATORIO}. v239={v239}, en rango 18-36: {18 <= v239 <= 36}")

        # 5. Caso médicos (pago proporcional directo)
        logger.debug(f"DEBUG: Legajo {id_legajo}: Evaluando Sección 5. Puesto='{puesto}'. Valores de comparación (re-normalizados al vuelo): {valores_profesionales_para_comparacion}. ¿Puesto está en valores?: {puesto in valores_profesionales_para_comparacion}")
        if puesto in valores_profesionales_para_comparacion:
            logger.info(f"Legajo {id_legajo}: Profesional de la salud, pago proporcional")
            return round(v239 * 4.33, 2)
        else:
            logger.debug(f"DEBUG: Legajo {id_legajo}: NO cumple condición de profesional de la salud en Sección 5.")

        # 6. Caso general con pisos (nuevo criterio) - CORREGIDO
        piso = PISOS_HORARIOS.get(normalizar_texto("GENERAL"), 36.0)
        sector_normalizado = normalizar_texto(sector)
        puesto_normalizado = normalizar_texto(puesto)

        # Definir sectores y puestos de laboratorio
        puestos_lab_piso_27 = [normalizar_texto(p) for p in [
            "AUXILIAR TECNICO", "TECNICO DE LABORATORIO", 
            "TECNICO EXTRACCIONISTA", "BIOQUIMICO"
        ]]

        sectores_laboratorio = [
            normalizar_texto('LABORATORIO'),
            normalizar_texto('ATENCION AL CLIENTE LABORATORIO'),
            normalizar_texto('LABORATORIO CLINICO'),
            normalizar_texto('ANALISIS CLINICOS')
        ]

        # 6.1 Sector LABORATORIO con puesto específico → piso 27
        if any(sector_normalizado == s for s in sectores_laboratorio) and puesto_normalizado in puestos_lab_piso_27:
            piso = 27.0
            logger.debug(f"DEBUG: Legajo {id_legajo}: Sector laboratorio con puesto específico → piso 27h")

        # 6.2 Sector IMÁGENES con puesto válido
        elif (
            sector_normalizado in SECTORES_IMAGENES
            and puesto_normalizado in ConfigBioimagenes.PUESTOS_VALIDOS
        ):
            piso = PISOS_HORARIOS.get(normalizar_texto("IMAGENES"), 18.0)
            logger.debug(f"DEBUG: Legajo {id_legajo}: Sector imágenes → piso {piso}h")

        logger.debug(f"DEBUG: Legajo {id_legajo}: Piso final determinado: {piso}")

        # 7. Si está por debajo del piso → proporcional
        if v239 < piso:
            logger.debug(f"Legajo {id_legajo}: Horas semanales {v239} debajo del piso {piso}, se liquida proporcional.")
            return round(piso * 4.33, 2)
        else:
            logger.debug(f"DEBUG: Legajo {id_legajo}: Horas semanales {v239} NO debajo del piso {piso}. Pasa al caso general.")

        # 8. Caso general por defecto
        logger.info(f"Legajo {id_legajo}: Sin coincidencias especiales → se asignan 200 hs mensuales.")
        return 200.00

    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error calculando horas mensuales - {str(e)}")
        return 200.00

def calcular_jornada_reducida(legajo: Dict[str, Any], es_guardia: bool) -> Optional[float]:
    """
    Calcula la variable 1167 (% de jornada reducida) con detección robusta de puestos especiales.
    Versión mejorada con manejo más robusto de categorías FC/PFC.
    """
    try:
        # --- Extracción de datos ---
        id_legajo = legajo.get('id_legajo', 'N/A')
        datos_personales = legajo.get('datos_personales', {})
        puesto = normalizar_texto(datos_personales.get('puesto', ''))
        sector = normalizar_texto(datos_personales.get('sector', {}).get('principal', ''))
        total_horas = legajo.get('horario', {}).get('resumen', {}).get('total_horas_semanales', 0.0)
        categoria = legajo.get('contratacion', {}).get('categoria', '')

        logger.debug(f"[1167] Legajo {id_legajo}: Categoría raw: '{categoria}'")

        # --- Validación mejorada de categorías FC/PFC ---
        if isinstance(categoria, str) and categoria.lower().replace(' ', '_') in {'pfc', 'fc_pfc'}:
            logger.debug(f"[1167] Legajo {id_legajo}: Excluido por categoría FC/PFC: '{categoria}'")
            return None

        # --- Validación de condiciones de exclusión ---
        if es_guardia:
            logger.debug(f"[1167] Legajo {id_legajo}: Excluido (es guardia)")
            return None
        if not puesto:
            logger.warning(f"[1167] Legajo {id_legajo}: Puesto no definido")
            return None
        if not sector:
            logger.warning(f"[1167] Legajo {id_legajo}: Sector no definido")
            return None

        # --- Detección robusta de puestos especiales ---
        if es_puesto_especial(puesto) and total_horas == 35.0:
            logger.debug(f"[1167] Legajo {id_legajo}: Excluido (puesto especial '{puesto}' con 35h)")
            return None

        # --- Determinar piso horario ---
        dias_trabajo = set(legajo.get('horario', {}).get('resumen', {}).get('dias_trabajo', []))
        
        # Lógica para la regla especial de 18 horas
        if total_horas == 18.0 and dias_trabajo.issuperset(DIAS_ESPECIALES):
            piso = 45.0
            resultado = round((total_horas / piso) * 100, 4)
            logger.info(f"[1167] Legajo {id_legajo}: APLICA (regla especial 18h en L/M/V → {resultado}%)")
            return resultado
        
        # --- Asignación de piso horario según sector y puesto (CORREGIDO) ---
        puestos_lab_piso_27 = [normalizar_texto(p) for p in [
            "AUXILIAR TECNICO", "TECNICO DE LABORATORIO", 
            "TECNICO EXTRACCIONISTA", "BIOQUIMICO"
        ]]
        
        # SECTORES RELACIONADOS CON LABORATORIO
        sectores_laboratorio = [
            normalizar_texto('LABORATORIO'),
            normalizar_texto('ATENCION AL CLIENTE LABORATORIO'),
            normalizar_texto('LABORATORIO CLINICO'),
            normalizar_texto('ANALISIS CLINICOS')
        ]
        
        logger.debug(f"[1167] Legajo {id_legajo}: DEBUG - Sector normalizado: '{sector}'")
        logger.debug(f"[1167] Legajo {id_legajo}: DEBUG - Puesto normalizado: '{puesto}'")
        logger.debug(f"[1167] Legajo {id_legajo}: DEBUG - Sectores laboratorio: {sectores_laboratorio}")
        logger.debug(f"[1167] Legajo {id_legajo}: DEBUG - ¿Sector relacionado con laboratorio? {any(sector == s for s in sectores_laboratorio)}")
        logger.debug(f"[1167] Legajo {id_legajo}: DEBUG - ¿Puesto en lista? {puesto in puestos_lab_piso_27}")

        # Si es sector RELACIONADO CON LABORATORIO y puesto específico → piso 27
        if any(sector == s for s in sectores_laboratorio) and puesto in puestos_lab_piso_27:
            piso = 27.0
            logger.debug(f"[1167] Legajo {id_legajo}: Sector relacionado con laboratorio '{sector}' con puesto '{puesto}' → piso 27h")
        elif sector in SECTORES_IMAGENES:
            piso = PISOS_HORARIOS.get(normalizar_texto('IMAGENES'), 36.0)
            logger.debug(f"[1167] Legajo {id_legajo}: Sector IMÁGENES → piso {piso}h")
        elif any(sector == s for s in sectores_laboratorio):
            piso = PISOS_HORARIOS.get(normalizar_texto('LABORATORIO'), 27.0)  # Default 27 para lab
            logger.debug(f"[1167] Legajo {id_legajo}: Sector laboratorio general → piso {piso}h")
        else:
            piso = PISOS_HORARIOS.get(normalizar_texto('GENERAL'), 36.0)
            logger.debug(f"[1167] Legajo {id_legajo}: Sector GENERAL → piso {piso}h")

        logger.debug(f"[1167] Legajo {id_legajo}: Piso determinado: {piso}h")

        # --- Cálculo final del porcentaje ---
        if total_horas < piso:
            resultado = round((total_horas / piso) * 100, 4)
            logger.info(f"[1167] Legajo {id_legajo}: APLICA ({total_horas}h < {piso}h → {resultado}%)")
            return resultado
            
        logger.debug(f"[1167] Legajo {id_legajo}: No aplica ({total_horas}h >= {piso}h)")
        return None

    except Exception as e:
        logger.error(f"[1167] Legajo {legajo.get('id_legajo', 'N/A')}: Error - {str(e)}")
        logger.error(traceback.format_exc())
        return None
    
def calcular_jornada_art19(legajo: Dict[str, Any], horas_semanales: float) -> Optional[int]:
    """
    Determina si aplica la variable 1416 (Jornada Art. 19) según las reglas:
    - Categoría debe contener el prefijo definido en ConfigArt19
    - Puesto debe estar en ConfigArt19.PUESTOS_VALIDOS
    - Sector debe coincidir con ConfigArt19.SECTOR_VALIDO (si está definido)
    - Horas semanales deben ser > ConfigArt19.HORAS_MIN

    Args:
        legajo: Diccionario con datos del legajo
        horas_semanales: Valor de la variable 239 (horas semanales)

    Returns:
        int: 1 si cumple condiciones, None si no aplica
    """
    try:
        if not legajo or not isinstance(horas_semanales, (int, float)):
            return None

        # 1. Validar categoría
        categoria_raw = legajo.get('contratacion', {}).get('categoria', '')
        categoria = normalizar_texto(categoria_raw)
        if normalizar_texto(ConfigArt19.CATEGORIA_PREFIX) not in categoria:
            return None

        # 2. Validar puesto
        puesto_raw = legajo.get('datos_personales', {}).get('puesto', '')
        puesto = normalizar_texto(puesto_raw)
        if puesto not in ConfigArt19.PUESTOS_VALIDOS:
            return None

        # 3. Validar sector (si está definido en la configuración)
        if hasattr(ConfigArt19, 'SECTOR_VALIDO'):
            sector_raw = legajo.get('datos_personales', {}).get('sector', {}).get('principal', '')
            sector = normalizar_texto(sector_raw)
            if sector != ConfigArt19.SECTOR_VALIDO:
                return None

        # 4. Validar horas semanales
        if horas_semanales <= ConfigArt19.HORAS_MIN:
            return None

        return 1

    except Exception as e:
        logger.error(f"Error calculando art.19 para legajo {legajo.get('id_legajo', 'DESCONOCIDO')}: {str(e)}")
        return None

def calcular_porcentaje_art19(legajo: Dict[str, Any], v239: float) -> Optional[float]:
    """
    Calcula la variable 1599 - % adicional por extensión horaria (Art. 19).

    Args:
        legajo: Diccionario con los datos completos del legajo.
        v239: Valor ya calculado de la variable 239 (horas semanales).

    Returns:
        float: El porcentaje calculado (hasta 4 decimales).
        None: Si no aplica la variable 1599.
    """
    id_legajo = legajo.get('id_legajo', 'DESCONOCIDO') # Obtener ID de forma segura

    logger.debug(f"Evaluando 1599 para legajo ID: {id_legajo}. Horas semanales (V239): {v239}")

    try:
        # Extraer y normalizar datos relevantes de forma segura
        puesto_raw = legajo['datos_personales'].get('puesto')
        if puesto_raw is None:
            logger.warning(f"Legajo {id_legajo}: Puesto es None, no se puede calcular 1599.")
            return None
        puesto = normalizar_texto(puesto_raw)

        categoria_raw = legajo['contratacion'].get('categoria')
        if categoria_raw is None:
            logger.warning(f"Legajo {id_legajo}: Categoría es None, no se puede calcular 1599.")
            return None
        categoria = categoria_raw.lower()

        sector_data = legajo['datos_personales'].get('sector')
        if sector_data is None or not isinstance(sector_data, dict):
            logger.warning(f"Legajo {id_legajo}: Datos de sector inválidos o None, no se puede calcular 1599.")
            return None

        sector_principal_raw = sector_data.get('principal')
        if sector_principal_raw is None:
            logger.warning(f"Legajo {id_legajo}: Sector principal es None, no se puede calcular 1599.")
            return None
        sector_principal = normalizar_texto(sector_principal_raw)

        # 1. Validar Categoría: Debe ser 'dentro de convenio'
        if CATEGORIA_ART19_PREFIX not in categoria:
            logger.debug(f"Legajo {id_legajo}: No aplica 1599. Categoría '{categoria}' no es '{CATEGORIA_ART19_PREFIX}'.")
            return None

        # 2. Validar Puesto
        if puesto not in PUESTOS_ART19:
            logger.debug(f"Legajo {id_legajo}: No aplica 1599. Puesto '{puesto_raw}' (normalizado: '{puesto}') no es uno de los puestos válidos: {PUESTOS_ART19}.")
            return None

        # 3. Validar Sector
        if sector_principal != SECTOR_ART19:
            logger.debug(f"Legajo {id_legajo}: No aplica 1599. Sector '{sector_principal_raw}' (normalizado: '{sector_principal}') no es '{SECTOR_ART19}'.")
            return None

        # 4. Validar Horas semanales (V239)
        # La regla dice "> 36 y <= 48", es decir, 36.01 a 48.00
        if not (HORAS_MIN_ART19 < v239 <= HORAS_MAX_ART19):
            logger.debug(f"Legajo {id_legajo}: No aplica 1599. Horas semanales ({v239}) no están en el rango ({HORAS_MIN_ART19},{HORAS_MAX_ART19}].")
            return None

        # 5. Realizar Cálculo Proporcional
        porcentaje = 0.0
        if v239 == HORAS_MAX_ART19: # Si es exactamente 48 horas
            porcentaje = CONSTANTES['PORCENTAJE_MAX_ART19']
            logger.debug(f"Legajo {id_legajo}: Calculado 1599 (48 hs exactas): {porcentaje:.4f}%")
        elif v239 > HORAS_MIN_ART19 and v239 < HORAS_MAX_ART19: # Entre 37 y 47.99 horas
            # Usamos HORAS_BASE_CALCULO_ART19 (48) para la proporción
            porcentaje = CONSTANTES['PORCENTAJE_MAX_ART19'] * (v239 / HORAS_BASE_CALCULO_ART19)
            logger.debug(f"Legajo {id_legajo}: Calculado 1599 (proporcional, {v239} hs): {porcentaje:.4f}%")

        # El caso else no debería ocurrir si las validaciones previas son correctas,
        # pero para mayor robustez se podría añadir un logger.error aquí si fuera crítico.

        # Redondear a 4 decimales según la regla
        return round(porcentaje, 4)

    except KeyError as ke:
        logger.error(f"Legajo {id_legajo}: Error - Falta un campo clave para calcular 1599. Detalles: {str(ke)}")
        logger.error(traceback.format_exc())
        return None
    except TypeError as te:
        logger.error(f"Legajo {id_legajo}: Error de tipo en los datos al calcular 1599. Detalles: {str(te)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error inesperado al calcular 1599. Detalles: {str(e)}")
        logger.error(traceback.format_exc())
        return None


def calcular_extension_horaria(legajo: Dict[str, Any], v239: float) -> Optional[float]:
    """
    Calcula la extensión horaria (Variable 992) según reglas actualizadas:
    - La variable 992 DEBE SER IGUAL A LA VARIABLE 239 (horas semanales)
    - Aplica exclusivamente a:
      * Puestos: 'TÉCNICO' o 'TÉCNICO PIVOT'
      * Sectores: Deben estar en 'SECTORES_IMAGENES' y NO ser 'LABORATORIO'
      * Legajos con ID <= 3999
      * Horas semanales > 24

    Args:
        legajo: Diccionario con los datos completos del legajo
        v239: Valor ya calculado de la variable 239 (horas semanales)

    Returns:
        float: El mismo valor que v239 si cumple todas las condiciones
        None: Si no aplica el adicional

    Ejemplo:
        >>> # Asumiendo un legajo_ejemplo con datos válidos y v239=32.5
        >>> # calcular_extension_horaria(legajo_ejemplo, 32.5)
        # 32.5  # Para un técnico en mamografía con 32.5 horas semanales
    """
    id_legajo = legajo.get('id_legajo', 'DESCONOCIDO')
    logger.debug(f"Evaluando extensión horaria (992) para legajo ID: {id_legajo}")

    try:
        # =============================================
        # 1. VALIDACIONES INICIALES (con logging detallado y acceso seguro a datos)
        # =============================================

        # Validar ID de legajo
        if id_legajo == 'DESCONOCIDO' or not isinstance(id_legajo, int) or id_legajo > 3999:
            logger.debug(f"Legajo {id_legajo} excluido (ID no válido o > 3999)")
            return None

        # Acceder y normalizar puesto de forma segura
        puesto_raw = legajo.get('datos_personales', {}).get('puesto')
        if puesto_raw is None:
            logger.debug(f"Legajo {id_legajo} excluido (puesto es None)")
            return None
        puesto_normalizado = normalizar_texto(puesto_raw)

        # Validar puesto (debe estar en los puestos válidos)
        if puesto_normalizado not in ConfigExtensionHoraria.PUESTOS_VALIDOS:
            logger.debug(f"Legajo {id_legajo} excluido (puesto '{puesto_normalizado}' no aplica para extensión horaria)")
            return None

        # Acceder y normalizar sector de forma segura
        sector_data = legajo.get('datos_personales', {}).get('sector', {})
        sector_principal_raw = sector_data.get('principal')
        if sector_principal_raw is None:
            logger.debug(f"Legajo {id_legajo} excluido (sector principal es None)")
            return None
        sector_normalizado = normalizar_texto(sector_principal_raw)

        # Validar sector: debe estar en SECTORES_IMAGENES y NO ser LABORATORIO
        if sector_normalizado not in SECTORES_IMAGENES:
            logger.debug(f"Legajo {id_legajo} excluido (sector '{sector_normalizado}' no está en SECTORES_IMAGENES)")
            return None

        if sector_normalizado == SECTOR_EXCLUIDO_LABORATORIO:
            logger.debug(f"Legajo {id_legajo} excluido (sector '{sector_normalizado}' es LABORATORIO)")
            return None

        # Validar horas mínimas
        if v239 <= 24:
            logger.debug(f"Legajo {id_legajo} excluido (horas semanales ({v239}) <= 24)")
            return None

        # =============================================
        # 2. APLICACIÓN DE REGLA PRINCIPAL
        # =============================================
        # REGLA CLAVE: 992 = 239 (mismo valor)
        valor_992 = round(float(v239), 2)

        logger.info(f"Legajo {id_legajo} CALCULA extensión horaria (992): {valor_992} (idéntico a 239 por regla)")

        return valor_992

    except KeyError as ke:
        logger.error(f"Legajo {id_legajo}: Falta campo obligatorio al calcular extensión horaria (992). Detalle: {str(ke)}")
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error inesperado al calcular extensión horaria (992). Detalle: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def calcular_dias_especiales(legajo: Dict[str, Any], v1242: int) -> Optional[int]:
    """
    Calcula la variable 1131 - Días mensuales especiales.
    Aplica validaciones específicas, incluyendo un caso especial para horarios
    de fin de semana/feriado ("sadofe").
    """
    id_legajo = legajo.get('id_legajo', 'N/A')

    try:
        # Acceso seguro y normalización
        datos = legajo.get("datos_personales", {})
        puesto = normalizar_texto(datos.get("puesto"))
        
        # --- ¡CORRECCIÓN AQUÍ! ---
        # Obtener los días de la semana desde el "resumen" del horario
        dias_semana_set = set(legajo.get("horario", {}).get("resumen", {}).get("dias_trabajo", []))

        # --- Logging para depuración ---
        logger.debug(f"DEBUG: Legajo {id_legajo}: Evaluando condiciones para V1131. Puesto normalizado='{puesto}'.")
        logger.debug(f"DEBUG: Legajo {id_legajo}: Días de la semana detectados: {dias_semana_set}") # Nuevo log para ver qué días detectó
        logger.debug(f"DEBUG: Legajo {id_legajo}: ¿Días semana son Sadofe ([5, 6, 7])? -> {dias_semana_set == {5, 6, 7}}")
        logger.debug(f"DEBUG: Legajo {id_legajo}: ¿V1242 < 22? ({v1242} < 22) -> {v1242 < 22}")
        logger.debug(f"DEBUG: Legajo {id_legajo}: ¿Puesto '{puesto}' en valores_profesionales_para_comparacion? -> {puesto in valores_profesionales_para_comparacion}")
        logger.debug(f"DEBUG: Legajo {id_legajo}: ¿El día '7' (feriado) está en dias_semana {dias_semana_set}? -> {7 in dias_semana_set}")


        # --- Nueva Condición Especial "Sadofe" ---
        # Si los días de la semana son exactamente Sábado (5), Domingo (6) y Feriado (7)
        if dias_semana_set == {5, 6, 7}:
            logger.info(f"Legajo {id_legajo}: V1131 APLICA por horario Sadofe ([5,6,7]). Retorna 10.")
            return 10 # Retorna 10 específicamente para este caso
            
        # --- Otras Condiciones (solo se evalúan si no se cumplió la Sadofe) ---
        if (
            v1242 < 22
            or puesto in valores_profesionales_para_comparacion
            or 7 in dias_semana_set # La condición de feriado general se mantiene aquí
        ):
            logger.info(f"Legajo {id_legajo}: V1131 APLICA por otras condiciones. Retorna v1242 ({v1242}).")
            return v1242

        logger.info(f"Legajo {id_legajo}: V1131 NO APLICA. Ninguna condición se cumplió.")
        return None
    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Error al calcular Variable 1131 - {str(e)}")
        logger.error(traceback.format_exc())
        return None

def aplicar_proporcion_lavado(legajo: Dict[str, Any]) -> bool:
    """
    Determina si aplica el adicional de lavado de uniforme (Variable 1137)
    basado en puesto, subsector y horas semanales.

    Condiciones (todas deben cumplirse):
    1. Puesto: "Operario de Logística"
    2. Subsector: "Interior" (debe existir y ser 'Interior' después de normalización)
    3. Total de Horas Semanales del legajo debe ser menor a 35.

    Args:
        legajo: El diccionario completo del registro del empleado.

    Returns:
        bool: True si el adicional aplica, False en caso contrario.
    """
    id_legajo = legajo.get('id_legajo', 'UNKNOWN')

    try:
        # -------------------------------------------------------------
        # 1. Validar y extraer datos personales (puesto y subsector)
        # -------------------------------------------------------------
        datos_personales = legajo.get('datos_personales')
        if not isinstance(datos_personales, dict):
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: 'datos_personales' no existe o no es un diccionario válido.")
            return False

        # Extraer y normalizar 'puesto'
        puesto_raw = datos_personales.get('puesto')
        puesto_normalizado = normalizar_texto(puesto_raw)
        if puesto_normalizado != normalizar_texto("OPERARIO DE LOGISTICA"):
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: Puesto '{puesto_normalizado}' no es 'Operario de Logística'.")
            return False

        # Extraer y normalizar 'subsector'
        sector_data = datos_personales.get('sector')
        if not isinstance(sector_data, dict):
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: 'sector' no existe o no es un diccionario válido.")
            return False

        subsector_raw = sector_data.get('subsector')
        subsector_normalizado = normalizar_texto(subsector_raw)
        # Condición estricta: debe ser "interior" Y no vacío/nulo después de normalización
        if subsector_normalizado != normalizar_texto("INTERIOR"):
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: Subsector '{subsector_normalizado}' no es 'Interior'.")
            return False

        # -------------------------------------------------------------
        # 2. Validar Total de Horas Semanales
        # -------------------------------------------------------------
        total_horas_semanales = None
        try:
            # Acceso seguro a los datos anidados con .get()
            horario_data = legajo.get('horario', {})
            resumen_data = horario_data.get('resumen', {})
            horas_raw = resumen_data.get('total_horas_semanales')

            if horas_raw is not None:
                total_horas_semanales = float(horas_raw)
            else:
                logger.debug(f"Legajo {id_legajo}: No aplica 1137: 'total_horas_semanales' es nulo o no existe.")
                return False # Si no existe, no cumple la condición

        except (ValueError, TypeError): # Captura si no se puede convertir a float
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: 'total_horas_semanales' no es un número válido: '{horas_raw}'.")
            return False

        # Una vez que tenemos total_horas_semanales como float (o None si hubo error)
        if total_horas_semanales is None or total_horas_semanales >= 35.0:
            logger.debug(f"Legajo {id_legajo}: No aplica 1137: Total horas semanales ({total_horas_semanales}) no es menor a 35.")
            return False

        # -------------------------------------------------------------
        # Si todas las condiciones se cumplen
        # -------------------------------------------------------------
        logger.info(f"Legajo {id_legajo}: El adicional de lavado de uniforme (1137) APLICA.")
        return True

    except Exception as e:
        logger.error(f"Legajo {id_legajo}: Ocurrió un error inesperado al validar el adicional de lavado de uniforme (1137) - {e}")
        logger.error(traceback.format_exc()) # Registra la traza completa del error para depuración
        return False

# ==============================
# FUNCIONES DE REPORTE Y SALIDA
# ==============================

def generar_reporte_parcial(
    estadisticas: Dict[str, Any],
    ruta_archivo_procesado: Optional[str] = None
) -> None:
    """
    Genera un reporte parcial de procesamiento ultra-perfeccionado
    con formato, color (para terminales compatibles) y detalles adicionales.

    Args:
        estadisticas: Diccionario con las métricas de procesamiento.
                      Se espera que contenga al menos:
                      'total_legajos', 'legajos_procesados',
                      'legajos_con_error', 'variables_calculadas'.
                      Los valores faltantes serán tratados como 0.
        ruta_archivo_procesado: Ruta opcional del archivo JSON/origen que fue procesado.
                                Si se proporciona, se incluirá en el reporte.
    """
    try:
        # Acceso robusto a las estadísticas usando .get() con valores por defecto.
        total_legajos = estadisticas.get('total_legajos', 0)
        legajos_procesados = estadisticas.get('legajos_procesados', 0)
        legajos_con_error = estadisticas.get('legajos_con_error', 0)
        variables_calculadas = estadisticas.get('variables_calculadas', 0)

        # --- Cálculo de la Tasa de Éxito ---
        tasa_exito_str = "0.00%"
        tasa_exito_color = COLOR_GREEN
        if total_legajos > 0:
            try:
                tasa_exito = (legajos_procesados / total_legajos) * 100
                tasa_exito_str = f"{tasa_exito:.2f}%"

                if tasa_exito == 100:
                    tasa_exito_color = COLOR_GREEN
                elif tasa_exito >= 80:
                    tasa_exito_color = COLOR_YELLOW
                else:
                    tasa_exito_color = COLOR_RED
            except Exception as e:
                logger.error(f"Error inesperado al calcular la tasa de éxito: {e}", exc_info=True)
                tasa_exito_str = "Error cálculo"
                tasa_exito_color = COLOR_RED
        else:
            tasa_exito_color = COLOR_YELLOW

        # --- Determinación del Estado General del Procesamiento ---
        estado_general_mensaje = ""
        estado_general_color = COLOR_RESET
        if total_legajos == 0:
            estado_general_mensaje = "NO SE ENCONTRARON DATOS PARA PROCESAR"
            estado_general_color = COLOR_YELLOW
        elif legajos_con_error > 0 and legajos_procesados == 0:
            estado_general_mensaje = "FALLO CRÍTICO: NINGÚN LEGAJO PROCESADO CORRECTAMENTE"
            estado_general_color = COLOR_RED
        elif legajos_con_error > 0:
            estado_general_mensaje = "PROCESAMIENTO COMPLETADO CON ERRORES DETECTADOS"
            estado_general_color = COLOR_YELLOW
        else:
            estado_general_mensaje = "PROCESAMIENTO COMPLETO Y EXITOSO"
            estado_general_color = COLOR_GREEN

        # --- Construcción del Reporte Final con Formato y Colores ---
        reporte = f"""
{COLOR_BOLD}{COLOR_CYAN}╔═══════════════════════════════════════════════════════════╗{COLOR_RESET}
{COLOR_BOLD}{COLOR_CYAN}║         INFORME PARCIAL DE PROCESAMIENTO DE LEGAJOS       ║{COLOR_RESET}
{COLOR_BOLD}{COLOR_CYAN}╚═══════════════════════════════════════════════════════════╝{COLOR_RESET}
{COLOR_BLUE}Fecha del Reporte:{COLOR_RESET} {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{COLOR_BLUE}Archivo Procesado:{COLOR_RESET} {ruta_archivo_procesado if ruta_archivo_procesado else 'N/A (No especificado)'}
{COLOR_BOLD}{COLOR_CYAN}─────────────────────────────────────────────────────────────{COLOR_RESET}

{COLOR_BOLD}≫ ESTADÍSTICAS CLAVE:{COLOR_RESET}
  • Total de legajos a procesar:   {total_legajos}
  • Legajos procesados exitosamente: {COLOR_GREEN}{legajos_procesados}{COLOR_RESET}
  • Legajos con errores detectados:  {COLOR_RED}{legajos_con_error}{COLOR_RESET}
  • Variables calculadas generadas:  {COLOR_BLUE}{variables_calculadas}{COLOR_RESET}

{COLOR_BOLD}≫ RENDIMIENTO GENERAL:{COLOR_RESET}
  • Tasa de éxito del procesamiento: {tasa_exito_color}{COLOR_BOLD}{tasa_exito_str}{COLOR_RESET}

{COLOR_BOLD}{COLOR_CYAN}─────────────────────────────────────────────────────────────{COLOR_RESET}
{COLOR_BOLD}≫ ESTADO DEL PROCESAMIENTO:{COLOR_RESET} {estado_general_color}{COLOR_BOLD}{estado_general_mensaje}{COLOR_RESET}
{COLOR_BOLD}{COLOR_CYAN}─────────────────────────────────────────────────────────────{COLOR_RESET}

{COLOR_BLUE}Notas:{COLOR_RESET}
  - Para detalles de errores, revise el archivo 'liquidacion_debug.log'.
  - Los archivos de resultados CSV contienen las variables generadas.
"""
        logger.info(reporte)
        print(reporte)

    except Exception as e:
        logger.error(f"Error CRÍTICO al generar el reporte parcial. Detalle: {e}", exc_info=True)

def generar_reporte_final(resultados: List[Tuple[int, int, Any]], ruta_archivo: str) -> None:
    """Genera un reporte final detallado"""
    try:
        # Estadísticas por variable
        variables_calculadas = len(resultados)
        variables_unicas = len({v[1] for v in resultados})

        # Conteo por tipo de variable
        conteo_variables = {}
        for _, codigo, _ in resultados:
            conteo_variables[codigo] = conteo_variables.get(codigo, 0) + 1

        # Top 5 variables más frecuentes
        top_variables = sorted(conteo_variables.items(), key=lambda x: x[1], reverse=True)[:5]

        reporte = f"""
        INFORME FINAL DE PROCESAMIENTO
        ==============================
        Archivo procesado: {ruta_archivo}
        Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

        ESTADÍSTICAS GENERALES
        ---------------------
        - Total variables calculadas: {variables_calculadas}
        - Variables únicas calculadas: {variables_unicas}

        VARIABLES MÁS FRECUENTES
        ------------------------
        {chr(10).join(f'- Variable {codigo}: {cantidad} veces' for codigo, cantidad in top_variables)}

        ARCHIVOS GENERADOS
        ------------------
        - variables_calculadas.csv: Contiene todas las variables calculadas
        - liquidacion_debug.log: Registro detallado del procesamiento

        REVISIONES RECOMENDADAS
        -----------------------
        1. Verificar legajos con errores en el log
        2. Validar variables con conteo inusual
        3. Revisar casos especiales (guardias, médicos, etc.)
        """
        logger.info(reporte)
        print(reporte)
        # Guardar reporte en archivo
        with open('reporte_final.txt', 'w', encoding='utf-8') as f:
            f.write(reporte)

    except Exception as e:
        logger.error(f"Error generando reporte final: {str(e)}")
        
# =============== BLOQUE DE EJECUCIÓN INDEPENDIENTE ===============
# =============== BLOQUE DE EJECUCIÓN INDEPENDIENTE ===============
if __name__ == '__main__':
    # Esta sección SÓLO se ejecuta cuando corres este archivo directamente.
    
    # 1. Se ha eliminado la configuración local de logging de aquí.
    #    Ahora, la configuración debe hacerse a nivel de la aplicación
    #    que use este script, como una app de Streamlit, para evitar
    #    conflictos y duplicación.
    #
    #    Ejemplo de configuración para una aplicación que importe este script:
    #    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    logger.info("--- Ejecutando json_a_excel.py en modo de prueba ---")
    
    # 2. Tu código de prueba
    try:
        # Crea un archivo JSON de prueba si no existe
        json_prueba = {
            "legajos": [
                {
                    "id_legajo": 101,
                    "remuneracion": {"sueldo_base": 1000},
                    "horario": {
                        "resumen": {"total_horas_semanales": 40, "total_horas_nocturnas": 0, "dias_trabajo": [0,1,2,3,4]},
                        "bloques": [{"dias_semana": [0,1,2,3,4], "hora_inicio": "09:00", "hora_fin": "17:00"}]
                    },
                    "contratacion": {"categoria": "dc_1_categoria"},
                    "datos_personales": {"sede": "Pilar", "sector": {"principal": "Administración"}}
                }
            ]
        }
        with open("horarios_prueba.json", "w") as f:
            json.dump(json_prueba, f)

        # Llama a tus funciones principales
        resultados, stats = procesar_archivo_json("horarios_prueba.json")
        if resultados:
            guardar_resultados_csv(resultados, "resultados_de_prueba.xlsx")
        
        generar_reporte_parcial(stats, "horarios_prueba.json")

    except Exception as e:
        logger.critical(f"Ocurrió un error catastrófico durante la prueba: {e}", exc_info=True)