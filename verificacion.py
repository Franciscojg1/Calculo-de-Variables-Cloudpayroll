# ==============================================================================
# SCRIPT DE VERIFICACIÓN (VERSIÓN FINAL CON REGEX CORREGIDO)
# ==============================================================================
import re
import logging
import json

# --- Configuración para ver los logs en la terminal ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- Diccionarios (versión final y completa) ---
DAY_MAP = {"lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6, "feriado": 7}
EQUIVALENCIAS = {
    "lunes a viernes": "lunes-viernes", "l a v": "lunes-viernes", "lunes, martes y miercoles": "lunes y martes y miércoles",
    "sábado por medio": "sábado por medio", "sxm": "sábado por medio", "1 sábado al mes": "sábados 1",
    "2 sábados al mes": "sábados 2", "3 sábados al mes": "sábados 3", "1 sabado al mes": "sabados 1",
    "2 sabados al mes": "sabados 2", "3 sabados al mes": "sabados 3", "1 sab al mes": "sabados 1",
    "2 sab al mes": "sabados 2", "3 sab al mes": "sabados 3", "1 s al mes": "sabados 1",
    "2 s al mes": "sabados 2", "3 s al mes": "sabados 3",
}
EQUIVALENCIAS = dict(sorted(EQUIVALENCIAS.items(), key=lambda item: len(item[0]), reverse=True))

# --- Funciones simuladas ---
def clean_and_standardize(s): return s.lower().replace('hs', '').replace(',', '')
def apply_equivalences(s, eq):
    for k, v in eq.items(): s = s.replace(k, v)
    return s
def format_time_to_hhmm(s): return f"{s.split(':')[0].zfill(2)}:{s.split(':')[1] if ':' in s else '00'}"
def generate_block_id(*args): return "test_id"

# --- Funciones de parseo (versiones finales y corregidas) ---
def get_day_indices(day_words):
    day_indices, proportional_data = set(), {}
    i = 0
    while i < len(day_words):
        word = day_words[i]
        if word in ["sábado", "sabado", "sábados"] and i + 1 < len(day_words) and day_words[i+1].isdigit():
            num = int(day_words[i+1])
            if 1 <= num <= 4:
                proportional_data[5], day_indices = num, day_indices.union({5})
                i += 2
                continue
        elif '-' in word:
            parts = word.split('-')
            if len(parts) == 2 and (start_idx := DAY_MAP.get(parts[0])) is not None and (end_idx := DAY_MAP.get(parts[1])) is not None:
                day_indices.update(range(min(start_idx, end_idx), max(start_idx, end_idx) + 1))
        elif (idx := DAY_MAP.get(word)) is not None:
            day_indices.add(idx)
        i += 1
    return sorted(list(day_indices)), proportional_data

def division_inteligente_bloques(texto, pattern):
    bloques = []
    partes = re.split(r'\s+y\s+', texto, flags=re.IGNORECASE)
    for parte in partes:
        if parte and (match := pattern.search(parte.strip())):
            bloques.append(match)
    return bloques

def parse_schedule_string(schedule_str):
    if not schedule_str: return []
    s_std = apply_equivalences(clean_and_standardize(schedule_str), EQUIVALENCIAS)
    logger.info(f"String con equivalencias: '{s_std}'")
    
    # --- CORRECCIÓN DEFINITIVA: Se añade '\d' para que el grupo de días acepte números ---
    pattern = re.compile(r"((?:[a-záéíóúñ\d\-]+(?:\s+y\s+|\s+)?)+?)(?:\s+de)?\s+(\d{1,2}(?:[:.]?\d{2})?)\s*(?:a|-)\s*(\d{1,2}(?:[:.]?\d{2})?)", re.IGNORECASE)
    
    matches = list(pattern.finditer(s_std))
    
    if " y " in s_std:
         logger.info("Se detectó 'y', aplicando división inteligente de bloques...")
         matches = division_inteligente_bloques(s_std, pattern)

    if not matches: return []
        
    normalized_blocks = []
    for match in matches:
        try:
            day_phrase = match.group(1).strip()
            tokens = re.findall(r'[a-záéíóúñ]+-[a-záéíóúñ]+|[a-záéíóúñ]+|\d+', day_phrase)
            day_words = [word for word in tokens if word not in ['y', 'de']]
            
            current_dias, proportional_data = get_day_indices(day_words)
            if not current_dias: continue

            if proportional_data:
                factor = proportional_data[5] / 4.0
            elif any(w in day_words for w in ["por", "medio"]):
                factor = 0.5
            else:
                factor = 1.0
            
            start_dt = int(match.group(2).split(':')[0])
            end_dt = int(match.group(3).split(':')[0])
            horas_dia = abs(end_dt - start_dt)

            normalized_blocks.append({"dias_semana": current_dias, "factor": factor, "horas_dia": horas_dia})
        except Exception as e:
            logger.error(f"Error procesando bloque: {match.group(0)} -> {e}")
    return normalized_blocks

# --- Script de prueba ---
if __name__ == "__main__":
    horario = "Lunes a viernes de 12 a 20hs y 1 Sábado al mes de 7 a 19hs"
    print(f"Probando horario: '{horario}'")
    
    bloques = parse_schedule_string(horario)
    
    total_horas = 0
    if bloques:
        for bloque in bloques:
            horas_bloque = bloque['horas_dia'] * len(bloque['dias_semana']) * bloque['factor']
            total_horas += horas_bloque
            print(f"-> Bloque procesado: días {bloque['dias_semana']}, {bloque['horas_dia']}hs/día, factor {bloque['factor']:.2f} => {horas_bloque:.2f}hs semanales")
    
    print(f"\nResultado final: {total_horas:.2f} horas semanales.")
    
    if total_horas == 43.0:
        print("✅ ¡Cálculo correcto!")
    else:
        print(f"❌ Cálculo incorrecto. Se esperaba 43.0 pero se obtuvo {total_horas:.2f}.")