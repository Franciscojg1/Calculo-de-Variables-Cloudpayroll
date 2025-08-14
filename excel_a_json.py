# =============== IMPORTS ===============
import pandas as pd
import json
import re
import logging
from datetime import datetime

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

def clean_and_standardize(text):
    text = text.lower().strip()
    text = re.sub(r'\s*(?:hs|hrs)\b', '', text)
    text = text.replace(',', ' y ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def apply_equivalences(text, equivalences):
    for old, new in equivalences.items():
        text = re.sub(r'\b' + re.escape(old) + r'\b', new, text)
    return text

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
    if pd.isna(legajo := row.get('Legajo')):
        errores.append("Legajo faltante")
    elif not isinstance(legajo, (int, float)) or legajo <= 0:
        errores.append("Legajo debe ser número positivo")
    if pd.isna(sector := row.get('Sector')) or str(sector).strip() == '':
        errores.append("Sector faltante o vacío")
    if pd.isna(categoria := row.get('Categoría')) or str(categoria).strip() == '':
        errores.append("Categoría faltante o vacía")
    else:
        cat_str_upper = re.sub(r'\s+', ' ', str(categoria).strip().upper())
        if not any(re.fullmatch(pattern, cat_str_upper) for pattern in CATEGORIA_MAP):
            errores.append(f"Categoría '{categoria}' no reconocida")
    if pd.isna(fecha_ingreso := row.get('Fecha ingreso')):
        errores.append("Fecha ingreso faltante")
    else:
        try:
            if isinstance(fecha_ingreso, (int, float)):
                pd.Timestamp('1899-12-30') + pd.Timedelta(days=fecha_ingreso)
            else:
                pd.to_datetime(fecha_ingreso, dayfirst=True)
        except:
            errores.append(f"Formato de fecha inválido: '{fecha_ingreso}'")
    if pd.isna(horario := row.get('Horario completo')) or str(horario).strip() == '':
        errores.append("Horario faltante o vacío")
    else:
        horario_str = str(horario).lower()
        if not any(dia in horario_str for dia in DAY_MAP):
            errores.append("Horario no especifica días válidos")
        if not re.search(r'\d{1,2}\s*[:.,]?\s*\d{0,2}\s*(?:a|-)\s*\d{1,2}\s*[:.,]?\s*\d{0,2}', horario_str):
            errores.append("Horario no contiene rango horario válido")
        if any(palabra in horario_str for palabra in ['variable', 'flexible', 'rotativo']):
            errores.append("Horario contiene términos ambiguos")
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

def parsear_fecha(date_value):
    if pd.isna(date_value) or date_value in [None, "", "nan", "NaT"]:
        return None
    if isinstance(date_value, (int, float)):
        try:
            dt = pd.to_datetime(date_value, unit='D', origin='1899-12-30')
            return dt.strftime('%d/%m/%Y')
        except Exception as e:
            return None
    fecha_str = str(date_value).strip()
    formatos = ['%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%Y%m%d']
    for fmt in formatos:
        try:
            fecha_dt = datetime.strptime(fecha_str, fmt)
            return fecha_dt.strftime('%d/%m/%Y')
        except ValueError:
            continue
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
    from datetime import datetime as dt
    total_horas = 0.0
    total_horas_nocturnas = 0.0
    dias_trabajo = set()
    tiene_nocturnidad = False
    bloques_por_dia = {i: [] for i in range(8)}
    detalle_nocturno = {'horario_nocturno': '22:00-06:00', 'total_horas': 0.0, 'por_dia': {}}
    for bloque in bloques:
        try:
            h_inicio = dt.strptime(bloque['hora_inicio'], '%H:%M').time()
            h_fin = dt.strptime(bloque['hora_fin'], '%H:%M').time()
            cruza_dia = bloque.get('cruza_dia', h_fin <= h_inicio)
            if cruza_dia:
                duracion_total = (24 - h_inicio.hour - h_inicio.minute/60) + (h_fin.hour + h_fin.minute/60)
                tiene_nocturnidad = True
            else:
                duracion_total = (h_fin.hour + h_fin.minute/60) - (h_inicio.hour + h_inicio.minute/60)
            horas_noct = 0.0  # Simplificado, podés expandir lógica de nocturnidad
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
    resultado = {
        'total_horas_semanales': round(total_horas, 2),
        'total_horas_nocturnas': round(total_horas_nocturnas, 2),
        'dias_trabajo': sorted(dias_trabajo),
        'tiene_nocturnidad': tiene_nocturnidad,
        'detalle_nocturnidad': {'total_horas': round(total_horas_nocturnas, 2)},
        'tiene_fin_semana': any(dia in {5, 6} for dia in dias_trabajo),
        'bloques_por_dia': {dia: bloques_por_dia[dia] for dia in sorted(dias_trabajo)}
    }
    if nombre_sede is not None:
        resultado['sede'] = nombre_sede.strip().upper()
    return resultado

# =============== FUNCIÓN PRINCIPAL ===============

def procesar_excel_a_json(df, output_json_path="horarios.json", logger_callback=None):
    """
    Procesa un DataFrame de pandas con datos de legajos y genera un archivo JSON normalizado.
    Versión mejorada con sistema de logging detallado.

    Args:
        df (pd.DataFrame): DataFrame con los datos de los legajos
        output_json_path (str): Ruta donde se guardará el JSON resultante
        logger_callback (function): Función para registrar mensajes (debe aceptar (message, level))

    Returns:
        str: Ruta del archivo JSON generado
    """
    def log(message, level="info"):
        """Función helper para logging consistente"""
        if logger_callback:
            logger_callback(message, level)

    try:
        # Inicialización de estadísticas
        stats = {
            'total_filas': len(df),
            'procesados_exitosamente': 0,
            'errores_parsing': 0,
            'filas_omitidas': 0,
            'total_errores_validacion': 0
        }
        
        all_normalized_data = []
        
        log(f"🚀 Iniciando procesamiento de {len(df)} filas", "info")
        log(f"Modo debug: {logger_callback is not None}", "debug")

        # Procesamiento de cada fila
        for index, row in df.iterrows():
            # Validación inicial
            log(f"Procesando fila {index + 1}/{len(df)} - Legajo: {row.get('Legajo', 'N/A')}", "debug")
            
            validacion = validar_fila_detallada(row)
            if not validacion['fila_valida']:
                stats['filas_omitidas'] += 1
                stats['total_errores_validacion'] += len(validacion['errores'])
                log(
                    f"Fila {index + 2} omitida (Legajo {row.get('Legajo', 'N/A')}): {validacion['errores']}", 
                    "warning"
                )
                continue

            legajo = row['Legajo']
            try:
                # Procesamiento del horario
                horario_original = str(row['Horario completo'])
                log(f"Interpretando horario para legajo {legajo}: {horario_original[:50]}...", "debug")
                
                normalized_schedule = parse_schedule_string(horario_original)
                
                if not normalized_schedule:
                    stats['errores_parsing'] += 1
                    log(
                        f"❌ Error de Parseo para legajo {legajo}. Horario no interpretable: {horario_original[:100]}", 
                        "error"
                    )
                    continue

                # Construcción del objeto normalizado
                empleado_mejorado = {
                    "id_legajo": int(legajo),
                    "datos_personales": {
                        "nombre": safe_str_get(row, 'Nombre completo'),
                        "sede": validacion['sede_normalizada']['nombre_normalizado'],
                        "sector": {
                            "principal": safe_str_get(row, 'Sector'),
                            "subsector": safe_str_get(row, 'Subsector')
                        },
                        "puesto": safe_str_get(row, 'Puesto')
                    },
                    "contratacion": {
                        "tipo": normalize_modalidad(row.get('Modalidad contratación')),
                        "categoria": normalize_categoria(row.get('Categoría')),
                        "fechas": {
                            "ingreso": parsear_fecha(row.get('Fecha ingreso')),
                            "fin": parsear_fecha(row.get('Fecha de fin'))
                        }
                    },
                    "horario": {
                        "bloques": [dict(bloque, legajo=legajo) for bloque in normalized_schedule],
                        "resumen": calcular_resumen_horario(normalized_schedule)
                    },
                    "remuneracion": {
                        "sueldo_base": clean_and_convert_to_float(row.get('Sueldo bruto pactado')),
                        "moneda": "ARS",
                        "adicionables": safe_str_get(row, 'Adicionales')
                    }
                }
                
                all_normalized_data.append(empleado_mejorado)
                stats['procesados_exitosamente'] += 1
                
                log(f"✓ Legajo {legajo} procesado correctamente. Bloques horarios: {len(normalized_schedule)}", "debug")

            except Exception as e:
                stats['filas_omitidas'] += 1
                log(
                    f"⚠ Error procesando legajo {legajo}: {str(e)}\nDatos fila: {dict(row.dropna())}", 
                    "error"
                )

        # Generación del JSON final
        output_mejorado = {
            "metadata": {
                "version_esquema": "1.2",
                "fecha_generacion": datetime.now().isoformat(),
                "estadisticas": {
                    **stats,
                    "total_registros_validos": len(all_normalized_data)
                },
                "sistema_origen": "horarios_parser_streamlit"
            },
            "legajos": all_normalized_data
        }

        # Guardado del archivo
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_mejorado, f, ensure_ascii=False, indent=2)

        log(
            f"""\n✅ Proceso completado:
            \n- Total filas procesadas: {stats['total_filas']}
            \n- Legajos válidos: {stats['procesados_exitosamente']}
            \n- Errores de validación: {stats['total_errores_validacion']}
            \n- Errores de parsing: {stats['errores_parsing']}
            \n- Filas omitidas: {stats['filas_omitidas']}""",
            "info"
        )

        log(f"Archivo JSON generado en: {output_json_path}", "debug")
        return output_json_path

    except Exception as e:
        error_msg = f"Error crítico en procesar_excel_a_json: {str(e)}"
        log(error_msg, "error")
        raise RuntimeError(error_msg)


def safe_str_get(row, field_name, default=None):
    """Obtiene valores de string de forma segura desde un DataFrame row."""
    value = row.get(field_name)
    return str(value).strip() if pd.notna(value) else default

# =============== USO RÁPIDO ===============
# df = pd.read_excel("Variables Julio 2025.xlsx")
# procesar_excel_a_json(df, output_json_path="horarios.json")