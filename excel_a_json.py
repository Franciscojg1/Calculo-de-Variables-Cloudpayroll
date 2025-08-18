# =============== IMPORTS ===============
import pandas as pd
import json
import re
import math
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger('excel_a_json')


# =============== DICCIONARIOS GLOBALES ===============

DAY_MAP = {
    "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3,
    "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
    "lun": 0, "mar": 1, "mie": 2, "jue": 3, "vie": 4, "sab": 5, "dom": 6,
    "l": 0, "m": 1, "x": 2, "j": 3, "v": 4, "s": 5, "d": 6,
    "sábados": 5, "sabados": 5, "domingos": 6,
    "feriado": 7, "feriados": 7,
    "safe": "sábado y feriado", "dofe": "domingo y feriado", "sadofe": "sábado y domingo y feriado"
}

DAY_NAMES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo", 7: "feriado"
}

EQUIVALENCIAS = {
    "lunes a viernes": "lunes-viernes", "l a v": "lunes-viernes", "l-v": "lunes-viernes",
    "lunes a sabados": "lunes-sabado", "lunes a sabado": "lunes-sabado", "lunes a sábados": "lunes-sabado",
    "lunes a sab": "lunes-sabado",
    "lunes a domingos": "lunes-domingo", "lunes a domingo": "lunes-domingo",
    "lunes a jueves": "lunes-jueves", "lunes a miercoles": "lunes-miércoles", "lunes a martes": "lunes-martes",
    "martes a viernes": "martes-viernes",
    "lunes, martes y miercoles": "lunes y martes y miércoles", "lunes martes y miercoles": "lunes y martes y miércoles",
    "sábado domingo feriado": "sábado y domingo y feriado", "sábado feriado": "sábado y feriado", "domingo feriado": "domingo y feriado",
    "sxm": "sábado por medio", "dxm": "domingo por medio", "sadofe": "sábado y domingo y feriado", "safe": "sábado y feriado", "dofe": "domingo y feriado", "sado fe": "sábado y domingo y feriado",
    "sabados por medio": "sábado por medio", "sábado por medio": "sábado por medio", "domingo por medio": "domingo por medio",
    "feriados": "feriado",
}

EQUIVALENCIAS_EXTRA = {
    "lav": "lunes-viernes",      # LaV → lunes-viernes
    "la v": "lunes-viernes",     # La V → lunes-viernes
    "l a v": "lunes-viernes",    # L a V → lunes-viernes
    "l-v": "lunes-viernes",      # L-V → lunes-viernes
    "l/v": "lunes-viernes",      # L/V → lunes-viernes
    "l v": "lunes-viernes",      # L V → lunes-viernes
}

# después de definir EQUIVALENCIAS original:
EQUIVALENCIAS.update(EQUIVALENCIAS_EXTRA)
EQUIVALENCIAS = dict(sorted(EQUIVALENCIAS.items(), key=lambda item: len(item[0]), reverse=True))


MODALIDAD_MAP = {
    'EVENTUAL': 'eventual', 'PERÍODO DE PRUEBA': 'periodo_prueba', 'PERÍODO DE PRUEBA (JORNADA PARCIAL)': 'periodo_prueba_parcial',
    'TIEMPO COMPLETO INDETERMINADO': 'tiempo_completo_indefinido', 'TIEMPO COMPLETO PLAZO FIJO': 'tiempo_completo_plazo_fijo',
    'TIEMPO INDETERMINADO': 'tiempo_indefinido', 'TIEMPO PARCIAL INDETERMINADO': 'tiempo_parcial_indefinido',
    'TIEMPO PARCIAL PLAZO FIJO': 'tiempo_parcial_plazo_fijo', 'INDETERMINADO': 'tiempo_indefinido',
    'PLAZO FIJO': 'tiempo_completo_plazo_fijo', 'JORNADA PARCIAL': 'tiempo_parcial_indefinido'
}
CATEGORIA_MAP = {
    r'^1°\s*ADM\s*(?:\(DC\))?$': 'dc_1_adm', r'^1°\s*CATEGOR[ÍI]A\s*(?:\(DC\))?$': 'dc_1_categoria',
    r'^2°\s*CATEGOR[ÍI]A\s*(?:\(DC\))?$': 'dc_2_categoria', r'^3°\s*ADM\s*(?:\(DC\))?$': 'dc_3_adm',
    r'^3°\s*CATEGOR[ÍI]A\s*(?:\(DC\))?$': 'dc_3_categoria', r'^4°\s*CATEGOR[ÍI]A\s*(?:\(DC\))?$': 'dc_4_categoria',
    r'^5°\s*CATEGOR[ÍI]A\s*(?:\(DC\))?$': 'dc_5_categoria',
    r'^BQ\s*(?:\(DC\))?$': 'dc_bq', r'^PFC\s*(?:\(FC\))?$': 'fc_pfc',
}
TURNOS_NOCTURNOS_COMPLETOS = [('19:00', '07:00'), ('22:00', '06:00'), ('21:00', '07:00'), ('18:00', '07:00')]

SEDES_VALIDAS = {
    'PILAR': {'codigo': 'PL', 'nombre_normalizado': 'Pilar'},
    'SAN MIGUEL': {'codigo': 'SM', 'nombre_normalizado': 'San Miguel'},
    'SAN FERNANDO': {'codigo': 'SF', 'nombre_normalizado': 'San Fernando'},
    'BAZTERRICA': {'codigo': 'BZ', 'nombre_normalizado': 'Bazterrica'},
    'PATERNAL': {'codigo': 'PT', 'nombre_normalizado': 'Paternal'},
    'BELGRANO': {'codigo': 'BL', 'nombre_normalizado': 'Belgrano'},
    'PILAR II': {'codigo': 'P2', 'nombre_normalizado': 'Pilar II'},
    'CABILDO': {'codigo': 'CB', 'nombre_normalizado': 'Cabildo'},
    'SAN ISIDRO': {'codigo': 'SI', 'nombre_normalizado': 'San Isidro'},
    'MARTINEZ': {'codigo': 'MZ', 'nombre_normalizado': 'Martinez'},
    'VICENTE LOPEZ': {'codigo': 'VL', 'nombre_normalizado': 'Vicente Lopez'},
    'VILLA URQUIZA': {'codigo': 'VU', 'nombre_normalizado': 'Villa Urquiza'},
    'VICENTE LOPEZ II': {'codigo': 'V2', 'nombre_normalizado': 'Vicente Lopez II'},
    'SAN JUAN': {'codigo': 'SJ', 'nombre_normalizado': 'San Juan'},
    'RECOLETA': {'codigo': 'RC', 'nombre_normalizado': 'Recoleta'},
    'VICENTE LOPEZ 2': {'codigo': 'V2', 'nombre_normalizado': 'Vicente Lopez II'},
    'CABALLITO II': {'codigo': 'C2', 'nombre_normalizado': 'Caballito II'},
    'CLINICA SANTA ISABEL': {'codigo': 'CS', 'nombre_normalizado': 'Clínica Santa Isabel'},
    'SANTA ISABEL': {'codigo': 'CS', 'nombre_normalizado': 'Clínica Santa Isabel'},
    'NUÑEZ': {'codigo': 'NU', 'nombre_normalizado': 'Nuñez'},
    'PIVOT': {'codigo': 'PV', 'nombre_normalizado': 'Pivot'},
    'C DEL SOL': {'codigo': 'CD', 'nombre_normalizado': 'Clínica del Sol'},
    'RIO IV': {'codigo': 'R4', 'nombre_normalizado': 'Rio IV'},
    'PALERMO II': {'codigo': 'P2', 'nombre_normalizado': 'Palermo II'},
    'CONS. EXT. CL. BAZTERRICA': {'codigo': 'BZ', 'nombre_normalizado': 'Cons. Ext. Cl. Bazterrica'},
    'PARQUE PATRICIOS': {'codigo': 'PP', 'nombre_normalizado': 'Parque Patricios'},
    'DEVOTO': {'codigo': 'DV', 'nombre_normalizado': 'Devoto'},
    'CHACO': {'codigo': 'CH', 'nombre_normalizado': 'Chaco'},
    'FLORES': {'codigo': 'FL', 'nombre_normalizado': 'Flores'},
    'CLINICA BAZTERRICA': {'codigo': 'BZ', 'nombre_normalizado': 'Bazterrica'},
    'INTERIOR': {'codigo': 'IN', 'nombre_normalizado': 'Interior'},
    'CLINICA DEL SOL': {'codigo': 'CD', 'nombre_normalizado': 'Clínica del Sol'},
    'NUÑEZ II': {'codigo': 'N2', 'nombre_normalizado': 'Nuñez II'},
    'ALMAGRO': {'codigo': 'AL', 'nombre_normalizado': 'Almagro'},
    'PALERMO': {'codigo': 'PA', 'nombre_normalizado': 'Palermo'},
    'VICENTE LOPEZ2': {'codigo': 'V2', 'nombre_normalizado': 'Vicente Lopez II'},
    'VL': {'codigo': 'VL', 'nombre_normalizado': 'Vicente Lopez'},
    'VP': {'codigo': 'VL', 'nombre_normalizado': 'Vicente Lopez'},
}

# =============== HELPERS ===============

def clean_and_standardize(text: str) -> str:
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    text = text.lower().strip()
    text = re.sub(r'\s*(?:hs|hrs)\b', '', text)  # ej: "8hs", "8 hrs"
    text = text.replace(',', ' y ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def limpiar_prefijos_horas(text: str) -> str:
    # quita "45hs", "45 hs", "40h" al inicio
    return re.sub(r'^\s*\d+\s*h?s?\b\s*', '', text, flags=re.IGNORECASE)

def apply_equivalences(text: str, equivalences: dict) -> str:
    # variantes súper flexibles de LaV (L A V, L.A.V., L-V, etc.)
    text = re.sub(r'\b(?:l\s*[\.\-]?\s*a\s*[\.\-]?\s*v)\b',
                  'lunes-viernes', text, flags=re.IGNORECASE)

    # resto de equivalencias (palabra completa), priorizando claves largas
    for old, new in sorted(equivalences.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r'\b' + re.escape(old) + r'\b'
        text = re.sub(pattern, new, text, flags=re.IGNORECASE)
    return text

def normalizar_horario_input(s: str) -> str:
    s = clean_and_standardize(s)
    s = limpiar_prefijos_horas(s)
    s = apply_equivalences(s, EQUIVALENCIAS)
    return s

def format_time_to_hhmm(time_str):
    time_str = time_str.replace('.', ':')
    if ':' in time_str:
        parts = time_str.split(':')
        hours = parts[0].zfill(2)
        minutes = parts[1].ljust(2, '0')[:2]
    else:
        hours = time_str.zfill(2)
        minutes = '00'
    return f"{hours}:{minutes}"

def get_day_indices(day_words):
    day_indices = set()
    for word in day_words:
        if '-' in word:
            start_day_str, end_day_str = word.split('-')
            start_idx = DAY_MAP.get(start_day_str.strip())
            end_idx = DAY_MAP.get(end_day_str.strip())
            if start_idx is not None and end_idx is not None:
                for i in range(start_idx, end_idx + 1):
                    day_indices.add(i)
        else:
            idx = DAY_MAP.get(word)
            if isinstance(idx, int):
                day_indices.add(idx)
            elif isinstance(idx, str):
                expanded_words = idx.split()
                for exp_word in expanded_words:
                    exp_idx = DAY_MAP.get(exp_word)
                    if exp_idx is not None:
                        day_indices.add(exp_idx)
    return sorted(list(day_indices))

def generate_block_id(days, start_time, end_time, periodicity, counter):
    day_names = '_'.join([DAY_NAMES.get(d, str(d)) for d in days])
    time_part = f"{start_time.replace(':', '')}_{end_time.replace(':', '')}"
    period_part = periodicity.get('tipo', 'semanal')
    return f"{day_names}_{time_part}_{period_part}_{counter}"

def clean_and_convert_to_float(text_value):
    if pd.isna(text_value):
        return None
    text_value = str(text_value).strip()
    if not text_value:
        return None
    if re.search(r'[^\d.,$]', text_value):
        return None
    cleaned_value = text_value.replace('$', '').strip()
    if ',' in cleaned_value and '.' in cleaned_value:
        if cleaned_value.rfind(',') > cleaned_value.rfind('.'):
            cleaned_value = cleaned_value.replace('.', '')
            cleaned_value = cleaned_value.replace(',', '.')
        else:
            cleaned_value = cleaned_value.replace(',', '')
    elif ',' in cleaned_value:
        cleaned_value = cleaned_value.replace(',', '.')
    try:
        return float(cleaned_value)
    except ValueError:
        return None

def validar_fila_detallada(row):
    errores = []

    # Legajo
    if pd.isna(legajo := row.get('Legajo')):
        errores.append("Legajo faltante")
    elif not isinstance(legajo, (int, float)) or legajo <= 0:
        errores.append("Legajo debe ser número positivo")

    # Sector
    if pd.isna(sector := row.get('Sector')) or str(sector).strip() == '':
        errores.append("Sector faltante o vacío")

    # Categoría
    if pd.isna(categoria := row.get('Categoría')) or str(categoria).strip() == '':
        errores.append("Categoría faltante o vacía")
    else:
        cat_str_upper = re.sub(r'\s+', ' ', str(categoria).strip().upper())
        if not any(re.fullmatch(pattern, cat_str_upper) for pattern in CATEGORIA_MAP):
            errores.append(f"Categoría '{categoria}' no reconocida")

    # Fecha ingreso (obligatoria)
    if pd.isna(fecha_ingreso := row.get('Fecha ingreso')):
        errores.append("Fecha ingreso faltante")
    else:
        if parsear_fecha(fecha_ingreso) is None:
            errores.append(f"Formato de fecha inválido: '{fecha_ingreso}'")

    # Fecha fin (opcional, pero validar si viene)
    fecha_fin = row.get('Fecha de fin')
    if pd.notna(fecha_fin) and str(fecha_fin).strip() != '':
        if parsear_fecha(fecha_fin) is None:
            errores.append(f"Formato de fecha de fin inválido: '{fecha_fin}'")

    # Horario
    if pd.isna(horario := row.get('Horario completo')) or str(horario).strip() == '':
        errores.append("Horario faltante o vacío")
    else:
        horario_str = normalizar_horario_input(str(horario))

        # Chequeo de días con límites de palabra (evita falsos positivos)
        dia_ok = any(
            re.search(rf'\b{re.escape(k)}\b', horario_str)
            for k in DAY_MAP.keys() if isinstance(k, str)
        )
        if not dia_ok:
            errores.append("Horario no especifica días válidos")

        # Rango horario (8, 8-17, 08:00-17, 8:30 a 17, etc.)
        if not re.search(r'\d{1,2}\s*[:.,]?\s*\d{0,2}\s*(?:a|-)\s*\d{1,2}\s*[:.,]?\s*\d{0,2}', horario_str):
            errores.append("Horario no contiene rango horario válido")

        # Términos ambiguos
        ambiguos = ['variable', 'variables', 'flexible', 'flexibles', 'rotativo', 'rotativa', 'rotativos', 'rotativas']
        if any(pal in horario_str for pal in ambiguos):
            errores.append("Horario contiene términos ambiguos")

    # Sede
    if pd.isna(sede := row.get('Sede')) or str(sede).strip() == '':
        sede_norm = {'codigo': 'SD', 'nombre_normalizado': 'Campo Sede Vacío', 'tipo': 'no_definida'}
    else:
        sede_norm = normalizar_sede(str(sede).strip())

    return {
        'errores': errores,
        'fila_valida': len(errores) == 0,
        'sede_normalizada': sede_norm
    }

def normalize_modalidad(modalidad_str):
    if pd.isna(modalidad_str):
        return None
    clean_str = str(modalidad_str).strip().upper()
    clean_str = re.sub(r'\s+', ' ', clean_str)
    return MODALIDAD_MAP.get(clean_str, 'otro')

def normalize_categoria(cat_str):
    if pd.isna(cat_str):
        return None
    cat_str = str(cat_str).strip().upper()
    cat_str = re.sub(r'\s+', ' ', cat_str)
    for pattern, normalized in CATEGORIA_MAP.items():
        if re.fullmatch(pattern, cat_str, flags=re.IGNORECASE):
            return normalized
    if 'DC' in cat_str or 'DENTRO' in cat_str:
        base_cat = re.sub(r'\(.*?\)', '', cat_str).strip()
        return f'dc_{base_cat.lower()}'
    elif 'FC' in cat_str or 'FUERA' in cat_str:
        base_cat = re.sub(r'\(.*?\)', '', cat_str).strip()
        return f'fc_{base_cat.lower()}'
    return 'dc_otra'

def normalizar_sede(nombre_sede: str) -> dict:
    if not nombre_sede or str(nombre_sede).strip() == '':
        return {'codigo': 'SD', 'nombre_normalizado': 'Campo Sede Vacío', 'tipo': 'no_definida'}
    limpio = nombre_sede.strip().upper()
    limpio = limpio.replace('Á', 'A').replace('É', 'E').replace('Í', 'I')\
                  .replace('Ó', 'O').replace('Ú', 'U').replace('Ñ', 'N')
    limpio = limpio.replace('.', '').replace('°', '').replace('º', '')
    if limpio in SEDES_VALIDAS:
        resultado = SEDES_VALIDAS[limpio].copy()
        resultado['tipo'] = 'normal'
        return resultado
    return {'codigo': 'ND', 'nombre_normalizado': f'DESCONOCIDA ({nombre_sede.strip()})', 'tipo': 'desconocida'}

def parsear_fecha(valor: Any) -> Optional[str]:
    """
    Devuelve 'dd/mm/YYYY' o None.
    Soporta:
      - datetime / pandas.Timestamp
      - serial de Excel (número o string numérica)
      - strings con '/', '-', '.' y año de 2 o 4 dígitos (19/09/25 -> 19/09/2025)
    """
    # 1) nulos / vacíos
    if valor is None or (isinstance(valor, float) and (math.isnan(valor) or math.isinf(valor))):
        return None
    if isinstance(valor, str):
        s = valor.strip()
        if s == "" or s.lower() in {"nan", "none", "null"}:
            return None

    # 2) datetime-like directo
    try:
        if hasattr(valor, "to_pydatetime"):
            valor = valor.to_pydatetime()
        if isinstance(valor, datetime):
            return valor.strftime("%d/%m/%Y")
    except Exception:
        pass

    # 3) serial de Excel (número o string numérica)
    #    base 1899-12-30 evita el bug del 29/02/1900
    def es_numero(s):
        try:
            float(s)
            return True
        except:
            return False

    if isinstance(valor, (int, float)) or (isinstance(valor, str) and es_numero(valor)):
        try:
            dias = float(valor)
            base = datetime(1899, 12, 30)
            dt = base + timedelta(days=dias)
            return dt.strftime("%d/%m/%Y")
        except Exception:
            pass

    # 4) strings con formatos comunes y año de 2 dígitos
    try:
        s = str(valor).strip()

        # normalizar separadores a '/'
        s_norm = re.sub(r"[^0-9]", "/", s)
        s_norm = re.sub(r"/+", "/", s_norm).strip("/")

        candidatos = {s, s_norm, s_norm.replace("/", "-"), s_norm.replace("/", ".")}

        formatos = [
            "%d/%m/%Y", "%d/%m/%y",
            "%d-%m-%Y", "%d-%m-%y",
            "%Y/%m/%d", "%y/%m/%d",
            "%Y-%m-%d", "%y-%m-%d",
            "%d.%m.%Y", "%d.%m.%y",
        ]

        for cand in list(candidatos):
            for fmt in formatos:
                try:
                    # adaptar separador del candidato a cada fmt
                    if "." in fmt:
                        cand_fmt = cand.replace("/", ".").replace("-", ".")
                    elif "-" in fmt:
                        cand_fmt = cand.replace("/", "-").replace(".", "-")
                    else:
                        cand_fmt = cand.replace("-", "/").replace(".", "/")

                    dt = datetime.strptime(cand_fmt, fmt)
                    return dt.strftime("%d/%m/%Y")
                except ValueError:
                    continue
    except Exception:
        pass

    return None

def parse_schedule_string(schedule_str):
    if not schedule_str or not isinstance(schedule_str, str):
        return []
    s_cleaned = clean_and_standardize(schedule_str)
    s_std = apply_equivalences(s_cleaned, EQUIVALENCIAS)
    pattern = re.compile(
        r"((?:[a-záéíóúñ\-]+(?:\s+y\s+|\s+)?)+?)"
        r"(?:\s+de)?\s+"
        r"(\d{1,2}(?:[:.]?\d{2})?)"
        r"\s*(?:a|-)\s*"
        r"(\d{1,2}(?:[:.]?\d{2})?)"
        , re.IGNORECASE)
    matches = list(pattern.finditer(s_std))
    if not matches:
        return []
    normalized_blocks = []
    block_counter = 0
    for match in matches:
        block_counter += 1
        day_phrase = match.group(1).strip()
        time_start_str = match.group(2)
        time_end_str = match.group(3)
        original_segment = match.group(0).strip()
        day_words = re.split(r'\s+y\s+|\s+', day_phrase)
        day_words = [word for word in day_words if word]
        periodicity = {"tipo": "semanal", "frecuencia": 1}
        if "por" in day_words and "medio" in day_words:
            periodicity = {"tipo": "quincenal", "frecuencia": 2}
            day_words = [w for w in day_words if w not in ["por", "medio"]]
        current_dias = get_day_indices(day_words)
        start_time = format_time_to_hhmm(time_start_str)
        end_time = format_time_to_hhmm(time_end_str)
        if not current_dias:
            continue
        block_id = generate_block_id(current_dias, start_time, end_time, periodicity, block_counter)
        block_data = {
            "id": block_id,
            "dias_semana": current_dias,
            "hora_inicio": start_time,
            "hora_fin": end_time,
            "periodicidad": periodicity,
            "original_text_segment": original_segment,
        }
        if start_time > end_time:
            block_data["cruza_dia"] = True
        normalized_blocks.append(block_data)
    return normalized_blocks

def calcular_resumen_horario(bloques, nombre_sede=None):
    from datetime import datetime as dt, time as tm, timedelta
    
    total_horas = 0.0
    total_horas_nocturnas = 0.0
    dias_trabajo = set()
    tiene_nocturnidad = False
    bloques_por_dia = {i: [] for i in range(8)}
    detalle_nocturno = {'horario_nocturno': '22:00-06:00', 'total_horas': 0.0, 'por_dia': {}}
    
    HORA_INICIO_NOCTURNA = tm(22, 0)
    HORA_FIN_NOCTURNA = tm(6, 0)

    for bloque in bloques:
        try:
            h_inicio = dt.strptime(bloque['hora_inicio'], '%H:%M').time()
            h_fin = dt.strptime(bloque['hora_fin'], '%H:%M').time()
            cruza_dia = bloque.get('cruza_dia', h_fin <= h_inicio)

            # LÓGICA DE CALCULO DE DURACIÓN DEL BLOQUE
            if cruza_dia:
                duracion_total = (24 - h_inicio.hour - h_inicio.minute / 60) + (h_fin.hour + h_fin.minute / 60)
            else:
                duracion_total = (h_fin.hour + h_fin.minute / 60) - (h_inicio.hour + h_inicio.minute / 60)
            
            # --- LÓGICA DE CÁLCULO DE HORAS NOCTURNAS AGREGADA ---
            horas_noct = 0.0
            
            # Se crea una fecha base para poder manejar rangos de tiempo
            temp_dt_inicio = dt.combine(dt.today(), h_inicio)
            temp_dt_fin = dt.combine(dt.today(), h_fin)

            # Si el horario cruza la medianoche, se ajusta la fecha de fin
            if cruza_dia:
                temp_dt_fin += timedelta(days=1)
            
            temp_dt_nocturna_inicio = dt.combine(dt.today(), HORA_INICIO_NOCTURNA)
            temp_dt_nocturna_fin = dt.combine(dt.today() + timedelta(days=1), HORA_FIN_NOCTURNA)

            # Calcular la intersección entre el horario del bloque y el horario nocturno
            overlap_start = max(temp_dt_inicio, temp_dt_nocturna_inicio)
            overlap_end = min(temp_dt_fin, temp_dt_nocturna_fin)

            if overlap_start < overlap_end:
                overlap_duration = overlap_end - overlap_start
                horas_noct = overlap_duration.total_seconds() / 3600
                tiene_nocturnidad = True
            # --- FIN DE LÓGICA AGREGADA ---
            
            factor = 1.0 if bloque['periodicidad']['tipo'] == 'semanal' else 0.5
            dias = set(bloque['dias_semana'])
            cantidad_dias = len(dias)
            
            for dia in dias:
                dias_trabajo.add(dia)
                bloques_por_dia[dia].append({
                    'inicio': bloque['hora_inicio'],
                    'fin': bloque['hora_fin'],
                    'duracion_total': round(duracion_total, 2),
                    'horas_nocturnas': round(horas_noct, 2),
                    'periodicidad': bloque['periodicidad']['tipo'],
                    'horas_semanales': round(duracion_total * factor, 2),
                })
            
            total_horas += duracion_total * cantidad_dias * factor
            total_horas_nocturnas += horas_noct * cantidad_dias * factor
            
        except Exception as e:
            continue
            
    # ... (código final) ...
    
    resultado = {
        'total_horas_semanales': round(total_horas, 2),
        'total_horas_nocturnas': round(total_horas_nocturnas, 2),
        'dias_trabajo': sorted(dias_trabajo),
        'tiene_nocturnidad': tiene_nocturnidad,
        'detalle_nocturnidad': {
            'horario_nocturno': '22:00-06:00',
            'total_horas': round(total_horas_nocturnas, 2),
            'por_dia': {dia: sum(b['horas_nocturnas'] for b in bloques_por_dia[dia]) for dia in sorted(dias_trabajo)}
        },
        'tiene_fin_semana': any(dia in {5, 6} for dia in dias_trabajo),
        'bloques_por_dia': {dia: bloques_por_dia[dia] for dia in sorted(dias_trabajo)}
    }

    if nombre_sede is not None:
        resultado['sede'] = nombre_sede.strip().upper()

    return resultado

# =============== FUNCIÓN PRINCIPAL ===============

def procesar_excel_a_json(df, output_json_path="horarios.json"):
    """
    Procesa un DataFrame de pandas y genera un archivo JSON normalizado y enriquecido.
    - Incluye información del crudo (sector, subsector, puesto, sede, categoría, modalidad, fechas, sueldo, adicionales).
    - Conserva el texto original del horario en 'horario.texto_original'.
    - Usa el sistema de logging estándar.
    """
    try:
        logger = logging.getLogger('excel_a_json')

        # Inicialización de estadísticas
        stats = {
            'total_filas': len(df),
            'procesados_exitosamente': 0,
            'errores_parsing': 0,
            'filas_omitidas': 0,
            'total_errores_validacion': 0
        }

        all_normalized_data = []

        logger.info(f"🚀 Iniciando procesamiento de {len(df)} filas")

        # Procesamiento de cada fila
        for index, row in df.iterrows():
            legajo_str = f"Legajo: {row.get('Legajo', 'N/A')}"
            logger.debug(f"Procesando fila {index + 1}/{len(df)} - {legajo_str}")

            validacion = validar_fila_detallada(row)
            if not validacion['fila_valida']:
                stats['filas_omitidas'] += 1
                stats['total_errores_validacion'] += len(validacion['errores'])
                logger.warning(f"Fila {index + 2} omitida ({legajo_str}): {validacion['errores']}")
                continue

            legajo = row['Legajo']
            try:
                # Tomamos el horario original tal como viene en el Excel
                horario_original = str(row['Horario completo'])
                logger.debug(f"Interpretando horario para legajo {legajo}: {horario_original[:80]}...")

                # Parseo a bloques normalizados
                normalized_schedule = parse_schedule_string(horario_original)
                if not normalized_schedule:
                    stats['errores_parsing'] += 1
                    logger.error(f"❌ Error de Parseo para legajo {legajo}. Horario no interpretable: {horario_original[:120]}")
                    continue

                # Construcción de objeto enriquecido
                empleado_mejorado = {
                    "id_legajo": int(legajo),

                    # Datos personales / origen
                    "datos_personales": {
                        "nombre": safe_str_get(row, 'Nombre completo'),
                        "sede": validacion['sede_normalizada']['nombre_normalizado'],
                        "sector": {
                            "principal": safe_str_get(row, 'Sector'),
                            "subsector": safe_str_get(row, 'Subsector')
                        },
                        "puesto": safe_str_get(row, 'Puesto')
                    },

                    # Contratación
                    "contratacion": {
                        "tipo": normalize_modalidad(row.get('Modalidad contratación')),
                        "categoria": normalize_categoria(row.get('Categoría')),
                        "fechas": {
                            "ingreso": parsear_fecha(row.get('Fecha ingreso')),
                            "fin": parsear_fecha(row.get('Fecha de fin'))
                        }
                    },

                    # Horario (bloques, resumen estructurado y texto original)
                    "horario": {
                        "texto_original": horario_original,
                        "bloques": [dict(bloque, legajo=legajo) for bloque in normalized_schedule],
                        "resumen": calcular_resumen_horario(normalized_schedule)
                    },

                    # Remuneración y observaciones
                    "remuneracion": {
                        "sueldo_base": clean_and_convert_to_float(row.get('Sueldo bruto pactado')),
                        "moneda": "ARS",
                        "adicionables": safe_str_get(row, 'Adicionales')
                    },

                    # (Opcional) snapshot del crudo útil para auditoría
                    "crudo_min": {
                        "Legajo": row.get('Legajo'),
                        "Nombre completo": safe_str_get(row, 'Nombre completo'),
                        "Sector": safe_str_get(row, 'Sector'),
                        "Subsector": safe_str_get(row, 'Subsector'),
                        "Puesto": safe_str_get(row, 'Puesto'),
                        "Sede": safe_str_get(row, 'Sede'),
                        "Categoría": row.get('Categoría'),
                        "Modalidad contratación": row.get('Modalidad contratación'),
                        "Fecha ingreso": row.get('Fecha ingreso'),
                        "Fecha de fin": row.get('Fecha de fin'),
                        "Sueldo bruto pactado": row.get('Sueldo bruto pactado'),
                        "Adicionales": safe_str_get(row, 'Adicionales'),
                        "Horario completo": horario_original
                    }
                }

                all_normalized_data.append(empleado_mejorado)
                stats['procesados_exitosamente'] += 1
                logger.debug(f"✓ Legajo {legajo} procesado correctamente. Bloques horarios: {len(normalized_schedule)}")

            except Exception as e:
                stats['filas_omitidas'] += 1
                logger.error(
                    f"⚠ Error inesperado procesando legajo {legajo}: {str(e)}\n"
                    f"Datos fila: { {k: v for k, v in dict(row).items() if pd.notna(v)} }",
                    exc_info=True
                )

        # Salida final
        output_mejorado = {
            "metadata": {
                "version_esquema": "1.3",
                "fecha_generacion": datetime.now().isoformat(),
                "estadisticas": {**stats, "total_registros_validos": len(all_normalized_data)},
                "sistema_origen": "horarios_parser_streamlit"
            },
            "legajos": all_normalized_data
        }

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_mejorado, f, ensure_ascii=False, indent=2)

        resumen_msg = f"""
✅ Proceso completado:
- Total filas procesadas: {stats['total_filas']}
- Legajos válidos: {stats['procesados_exitosamente']}
- Errores de validación: {stats['total_errores_validacion']}
- Errores de parsing: {stats['errores_parsing']}
- Filas omitidas: {stats['filas_omitidas']}
"""
        logger.info(resumen_msg)
        logger.debug(f"Archivo JSON generado en: {output_json_path}")

        return output_json_path

    except Exception as e:
        error_msg = f"Error crítico en procesar_excel_a_json: {str(e)}"
        logging.getLogger('excel_a_json').critical(error_msg, exc_info=True)
        raise RuntimeError(error_msg)

def safe_str_get(row, field_name, default=None):
    """Obtiene valores de string de forma segura desde un DataFrame row."""
    value = row.get(field_name)
    return str(value).strip() if pd.notna(value) else default

# =============== BLOQUE DE EJECUCIÓN INDEPENDIENTE ===============
if __name__ == '__main__':
    # Esta sección SÓLO se ejecuta cuando corres este archivo directamente.
    # NO se ejecutará cuando Streamlit (app.py) lo importe.
    
    # 1. Configurar un logging básico para ver la salida en la consola.
    logging.basicConfig(
        level=logging.DEBUG,  # Muestra todos los mensajes, desde DEBUG hasta CRITICAL
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler() # Envía los logs a la consola
        ]
    )

    logger.info("--- Ejecutando script en modo de prueba independiente ---")
    
    # 2. Tu código de prueba (descomenta para usar)
    try:
        df_prueba = pd.read_excel("Variables Julio 2025.xlsx")
        procesar_excel_a_json(df_prueba, output_json_path="horarios_de_prueba.json")
        logger.info("--- Prueba finalizada exitosamente ---")
    except FileNotFoundError:
        logger.error("Error: El archivo 'Variables Julio 2025.xlsx' no fue encontrado. Asegúrate de que esté en la misma carpeta.")
    except Exception as e:
        logger.error(f"Ocurrió un error durante la prueba: {e}")
