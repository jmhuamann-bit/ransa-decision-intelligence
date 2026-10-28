"""
Generador del DATASET SIMULADO de operación logística RANSA Perú (2023-01 → 2026-09).

Produce, con semilla fija (reproducible):
  * data/RANSA_Peru_Dataset_Simulado.csv   — 30.000 embarques × 123 variables
  * data/RANSA_Peru_Diccionario_Datos.csv  — diccionario de datos (fuente pública de referencia
                                             de cada variable en Perú)

Principios de diseño:
  1. Geografía REAL: distancias, altitudes y rutas salen de data/peru_network.json (red vial de
     OpenStreetMap + SRTM). Cada corredor se descompone automáticamente en tramos de costa
     norte/centro/sur, sierra central/sur, selva y corredor minero según su perfil de altitud.
  2. Estacionalidad y episodios PERUANOS con fechas reales: crisis social del sur
     (dic-2022/mar-2023), Ciclón Yaku y Niño Costero (mar-abr 2023), El Niño costero (alerta ENFEN
     2023-24), lluvias de sierra (dic-mar), heladas y nevadas (jun-ago), estiaje amazónico (2023
     y 2024), incendios forestales en selva (ago-oct 2024), paros de transportistas por extorsión
     (oct 2024 y oct 2025), inicio de operaciones del Puerto de Chancay (14-nov-2024) y
     transición a la nueva terminal del Aeropuerto Jorge Chávez (jun-2025).
  3. Causalidad explícita: el retraso REAL de cada viaje se materializa a partir de los índices
     de riesgo conocidos ANTES del despacho (bloqueos, huaicos, clima, seguridad, congestión
     portuaria, nivel del río...) más ruido. Por eso un modelo de IA puede anticiparlo, pero no
     con certeza absoluta — igual que en la realidad.
  4. Mezcla de negocio inspirada en el perfil PÚBLICO de RANSA (ver app/services/ransa_profile.py):
     líneas de Distribución, Comercio Exterior, Logística de Frío, Minería y Energía y Automotriz
     (cigüeñas Chancay → Lima); flota en transición a GNL en el segmento extractivo y de líquidos;
     salud/farma solo como piloto (RANSA evalúa entrar a ese negocio en el Perú hacia 2026-27).

Todo es SIMULADO con fines de demostración; los valores de referencia (precios de combustible,
inflación, tipo de cambio, peajes) son aproximaciones de orden de magnitud, no series oficiales.

Ejecutar:  python scripts/generate_peru_dataset.py
"""
import csv
import json
import math
import os
import sys
from datetime import date, timedelta

import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK_PATH = os.path.join(BASE_DIR, "data", "peru_network.json")
OUT_CSV = os.path.join(BASE_DIR, "data", "RANSA_Peru_Dataset_Simulado.csv")
OUT_DICT = os.path.join(BASE_DIR, "data", "RANSA_Peru_Diccionario_Datos.csv")

N_ROWS = 30000
START, END = date(2023, 1, 1), date(2026, 9, 30)
CHANCAY_START = date(2024, 11, 14)
SEED = 2026
rng = np.random.default_rng(SEED)

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
         "Octubre", "Noviembre", "Diciembre"]

# ---------------------------------------------------------------------------- corredores
# corredor, modo, peso relativo, mezcla de sectores
SECT = {
    "urbano": {"Consumo Masivo": .50, "Retail": .34, "Tecnología": .11, "Salud": .05},
    "callao": {"Consumo Masivo": .30, "Retail": .22, "Industrial": .17, "Tecnología": .09, "Automotriz": .10,
               "Pesca": .08, "Salud": .04},
    "chancay": {"Automotriz": .30, "Industrial": .28, "Tecnología": .14, "Retail": .14, "Consumo Masivo": .14},
    "nacional": {"Consumo Masivo": .48, "Retail": .24, "Industrial": .15, "Tecnología": .08, "Salud": .05},
    "agro": {"Agroexportación": .82, "Industrial": .08, "Pesca": .10},
    "minero": {"Minería": 1.0},
    "minero_mix": {"Minería": .55, "Consumo Masivo": .30, "Industrial": .15},
    "sur": {"Consumo Masivo": .38, "Retail": .22, "Industrial": .17, "Minería": .18, "Salud": .05},
    "selva": {"Consumo Masivo": .55, "Industrial": .22, "Retail": .18, "Salud": .05},
    "puerto_import": {"Industrial": .42, "Consumo Masivo": .25, "Tecnología": .13, "Retail": .12, "Automotriz": .08},
    "aereo": {"Tecnología": .30, "Agroexportación": .22, "Salud": .18, "Retail": .16, "Consumo Masivo": .14},
    "pesca": {"Pesca": .45, "Industrial": .30, "Consumo Masivo": .25},
}

CORRIDORS = [
    # ---- Carretero
    ("Callao - Lima", "Carretero", .075, "callao"), ("Lima - Lima", "Carretero", .062, "urbano"),
    ("Callao - Lurín", "Carretero", .040, "callao"), ("Chancay - Lima", "Carretero", .030, "chancay"),
    ("Chancay - Callao", "Carretero", .018, "chancay"), ("Lima - Trujillo", "Carretero", .034, "nacional"),
    ("Trujillo - Callao", "Carretero", .022, "agro"), ("Lima - Chimbote", "Carretero", .012, "pesca"),
    ("Lima - Chiclayo", "Carretero", .024, "nacional"), ("Lima - Piura", "Carretero", .024, "nacional"),
    ("Lima - Tumbes", "Carretero", .006, "nacional"), ("Lima - Huaraz", "Carretero", .010, "minero_mix"),
    ("Lima - Cajamarca", "Carretero", .012, "minero_mix"), ("Trujillo - Chiclayo", "Carretero", .010, "nacional"),
    ("Chiclayo - Piura", "Carretero", .010, "nacional"), ("Piura - Paita", "Carretero", .022, "agro"),
    ("Paita - Piura", "Carretero", .008, "puerto_import"), ("Piura - Tumbes", "Carretero", .005, "nacional"),
    ("Chiclayo - Tarapoto", "Carretero", .008, "selva"), ("Paita - Tarapoto", "Carretero", .006, "puerto_import"),
    ("Tarapoto - Yurimaguas", "Carretero", .008, "selva"), ("Lima - Huancayo", "Carretero", .035, "nacional"),
    ("Lima - Cerro de Pasco", "Carretero", .012, "minero_mix"), ("Lima - Huánuco", "Carretero", .010, "nacional"),
    ("Lima - Pucallpa", "Carretero", .012, "selva"), ("Lima - Ayacucho", "Carretero", .008, "nacional"),
    ("Lima - Ica", "Carretero", .024, "nacional"), ("Ica - Callao", "Carretero", .030, "agro"),
    ("Lima - Pisco", "Carretero", .006, "pesca"), ("Lima - Arequipa", "Carretero", .040, "sur"),
    ("Lima - Tacna", "Carretero", .010, "sur"), ("Lima - Cusco", "Carretero", .015, "nacional"),
    ("Arequipa - Juliaca", "Carretero", .015, "sur"), ("Arequipa - Puno", "Carretero", .006, "sur"),
    ("Arequipa - Cusco", "Carretero", .008, "sur"), ("Juliaca - Cusco", "Carretero", .004, "sur"),
    ("Matarani - Arequipa", "Carretero", .012, "puerto_import"), ("Arequipa - Matarani", "Carretero", .010, "minero_mix"),
    ("Challhuahuacho - Matarani", "Carretero", .025, "minero"), ("Cusco - Puerto Maldonado", "Carretero", .006, "selva"),
    ("Tacna - Arequipa", "Carretero", .006, "sur"), ("Ilo - Moquegua", "Carretero", .006, "minero_mix"),
    # ---- Marítimo (cabotaje)
    ("Callao - Paita", "Marítimo", .018, "nacional"), ("Paita - Callao", "Marítimo", .014, "agro"),
    ("Callao - Matarani", "Marítimo", .018, "sur"), ("Matarani - Callao", "Marítimo", .014, "minero_mix"),
    ("Callao - Ilo", "Marítimo", .008, "sur"), ("Callao - Salaverry", "Marítimo", .006, "nacional"),
    ("Chancay - Paita", "Marítimo", .006, "chancay"), ("Chancay - Matarani", "Marítimo", .006, "chancay"),
    # ---- Fluvial (Amazonía)
    ("Yurimaguas - Iquitos", "Fluvial", .018, "selva"), ("Pucallpa - Iquitos", "Fluvial", .012, "selva"),
    # ---- Aéreo
    ("Lima - Iquitos", "Aéreo", .025, "aereo"), ("Lima - Cusco", "Aéreo", .015, "aereo"),
    ("Lima - Arequipa", "Aéreo", .012, "aereo"), ("Lima - Piura", "Aéreo", .010, "aereo"),
    ("Lima - Tarapoto", "Aéreo", .010, "aereo"), ("Lima - Pucallpa", "Aéreo", .008, "aereo"),
    ("Lima - Juliaca", "Aéreo", .006, "aereo"), ("Lima - Tacna", "Aéreo", .005, "aereo"),
    ("Lima - Puerto Maldonado", "Aéreo", .005, "aereo"), ("Lima - Trujillo", "Aéreo", .004, "aereo"),
]

MODE_PREFIX = {"Carretero": "TER", "Marítimo": "MAR", "Fluvial": "FLU", "Aéreo": "AER"}

CARGA_POR_SECTOR = {
    "Consumo Masivo": [("Consumo masivo (seca)", .82), ("Alimentos refrigerados", .18)],
    "Retail": [("Retail y textil", 1.0)],
    "Agroexportación": [("Agroexportación perecible (cadena de frío)", 1.0)],
    "Minería": [("Concentrado de minerales", .64), ("Insumos mineros (MATPEL)", .16), ("Repuestos críticos", .10),
                ("Hidrocarburos y lubricantes (líquidos)", .10)],
    "Salud": [("Farmacéutica (cadena de frío)", .55), ("Dispositivos médicos", .45)],
    "Industrial": [("Industrial y maquinaria", .78), ("Repuestos críticos", .22)],
    "Pesca": [("Pesca y congelados", 1.0)],
    "Tecnología": [("Tecnología y electrónica", 1.0)],
    "Automotriz": [("Vehículos nuevos (cigüeña)", 1.0)],
}
VALOR_PEN_POR_T = {
    "Consumo masivo (seca)": 9000, "Alimentos refrigerados": 14000, "Retail y textil": 26000,
    "Agroexportación perecible (cadena de frío)": 13000, "Concentrado de minerales": 9500,
    "Insumos mineros (MATPEL)": 8000, "Repuestos críticos": 65000, "Farmacéutica (cadena de frío)": 90000,
    "Dispositivos médicos": 70000, "Industrial y maquinaria": 22000, "Pesca y congelados": 11000,
    "Tecnología y electrónica": 130000, "Hidrocarburos y lubricantes (líquidos)": 7000,
    "Vehículos nuevos (cigüeña)": 52000,
}
DENSIDAD_M3_POR_T = {
    "Consumo masivo (seca)": 3.0, "Alimentos refrigerados": 2.6, "Retail y textil": 4.6,
    "Agroexportación perecible (cadena de frío)": 2.4, "Concentrado de minerales": 0.45,
    "Insumos mineros (MATPEL)": 1.2, "Repuestos críticos": 2.2, "Farmacéutica (cadena de frío)": 5.0,
    "Dispositivos médicos": 5.5, "Industrial y maquinaria": 2.0, "Pesca y congelados": 2.1,
    "Tecnología y electrónica": 6.2, "Hidrocarburos y lubricantes (líquidos)": 1.25,
    "Vehículos nuevos (cigüeña)": 8.5,
}
# kg de CO₂ por galón consumido (GHG Protocol / factores de referencia). El GNL de la flota extractiva
# y de líquidos de RANSA reduce hasta 25 % las emisiones; el GNV urbano, ~18 %.
CO2_KG_POR_GALON = {
    "Diésel B5 · Euro V": 10.21, "Diésel B5 · Euro III/IV": 10.72, "GNL": 7.66, "GNV": 8.37,
    "Fuelóleo marino (VLSFO)": 11.30, "Diésel marino": 10.21, "Turbo A-1": 9.57,
}


def linea_negocio(sector: str, carga: str, modo: str, corredor: str, mix: str) -> str:
    """Línea de negocio RANSA que atiende el embarque (unidades públicas de la compañía)."""
    if sector == "Minería":
        return "Minería y Energía"
    if carga in FRIO:
        return "Logística de Frío"
    if sector == "Automotriz":
        return "Automotriz"
    if modo in ("Marítimo", "Aéreo") or mix == "puerto_import" or (
            ("Callao" in corredor or "Chancay" in corredor) and sector in ("Industrial", "Tecnología")):
        return "Comercio Exterior"
    return "Distribución"
FRIO = {"Alimentos refrigerados", "Agroexportación perecible (cadena de frío)", "Farmacéutica (cadena de frío)",
        "Pesca y congelados"}

ASEGURADORAS = [("Rímac Seguros", .26), ("Pacífico Seguros", .24), ("La Positiva Seguros", .16), ("Mapfre Perú", .14),
                ("Chubb Perú", .12), ("Avla Perú", .08)]
NAVIERAS = ["Maersk", "MSC", "Hapag-Lloyd", "CMA CGM", "COSCO Shipping", "ONE"]
NAVIERAS_FLUVIALES = ["Transportes Fluviales del Oriente", "Naviera Amazónica", "Fluvial Ucayali"]
AEROLINEAS = [("LATAM Cargo", "LA"), ("Sky Airline Cargo", "H2"), ("JetSMART Cargo", "JA"), ("Avianca Cargo", "AV")]
AEROPUERTOS = {
    "Lima": "LIM – Jorge Chávez", "Iquitos": "IQT – Francisco Secada", "Cusco": "CUZ – Velasco Astete",
    "Arequipa": "AQP – Rodríguez Ballón", "Piura": "PIU – Concha Iberico", "Tarapoto": "TPP – Guillermo del Castillo",
    "Pucallpa": "PCL – David Abensur", "Juliaca": "JUL – Inca Manco Cápac", "Tacna": "TCQ – Carlos Ciriani",
    "Puerto Maldonado": "PEM – Padre Aldamiz", "Trujillo": "TRU – Martínez de Pinillos",
}
ALT_AEROPUERTO = {"Lima": 34, "Iquitos": 93, "Cusco": 3310, "Arequipa": 2560, "Piura": 37, "Tarapoto": 270,
                  "Pucallpa": 148, "Juliaca": 3826, "Tacna": 469, "Puerto Maldonado": 200, "Trujillo": 30}
PUERTOS = {
    "Callao": ["Callao – Muelle Norte", "Callao – Muelle Sur"], "Chancay": ["Chancay – Terminal Multipropósito"],
    "Paita": ["Paita – Terminal Portuario"], "Matarani": ["Matarani – Terminal Sur"], "Ilo": ["Ilo – Terminal Portuario"],
    "Salaverry": ["Salaverry – Terminal Multipropósito"], "Yurimaguas": ["Yurimaguas – Nuevo Terminal Fluvial"],
    "Pucallpa": ["Pucallpa – Puerto Fluvial"], "Iquitos": ["Iquitos – Terminal Fluvial"],
}


# ---------------------------------------------------------------------------- helpers
def choice(options):
    labels, weights = zip(*options)
    w = np.array(weights, dtype=float)
    return labels[rng.choice(len(labels), p=w / w.sum())]


def wchoice(d):
    return choice(list(d.items()))


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def in_range(d, a, b):
    return a <= d <= b


def month_interp(d, table):
    """table: {(año, mes): valor} → interpolación diaria lineal entre meses."""
    keys = sorted(table)
    k = (d.year, d.month)
    if k <= keys[0]:
        return table[keys[0]]
    if k >= keys[-1]:
        return table[keys[-1]]
    i = keys.index(k)
    nxt = keys[i + 1]
    frac = (d.day - 1) / 30.0
    return table[k] + (table[nxt] - table[k]) * frac


def build_series():
    """Series mensuales de referencia (aproximadas) 2023-2026."""
    infl = {2023: [8.66, 8.65, 8.40, 7.97, 7.89, 6.46, 5.88, 5.58, 5.04, 4.34, 3.64, 3.24],
            2024: [3.02, 3.29, 3.05, 2.42, 2.00, 2.29, 2.13, 2.03, 1.78, 2.01, 2.27, 1.97],
            2025: [1.89, 1.48, 1.30, 1.65, 1.69, 1.69, 1.73, 1.11, 1.38, 1.35, 1.40, 1.52],
            2026: [1.70, 1.82, 1.95, 2.05, 2.10, 2.02, 1.96, 1.90, 1.88, 1.90, 1.90, 1.90]}
    diesel = {2023: [17.6, 17.4, 17.1, 16.9, 16.6, 16.3, 16.2, 16.5, 16.9, 16.8, 16.4, 16.1],
              2024: [16.0, 16.1, 16.3, 16.5, 16.4, 16.2, 16.1, 15.9, 15.7, 15.6, 15.8, 15.9],
              2025: [15.9, 15.8, 15.6, 15.4, 15.3, 15.4, 15.6, 15.7, 15.6, 15.5, 15.4, 15.4],
              2026: [15.3, 15.2, 15.3, 15.5, 15.6, 15.7, 15.6, 15.5, 15.4, 15.4, 15.4, 15.4]}
    gas = {y: [round(v * 0.985 + 0.35, 2) for v in vals] for y, vals in diesel.items()}
    tc = {2023: [3.85, 3.86, 3.79, 3.78, 3.69, 3.63, 3.60, 3.68, 3.78, 3.84, 3.76, 3.72],
          2024: [3.73, 3.80, 3.71, 3.77, 3.74, 3.79, 3.75, 3.74, 3.75, 3.77, 3.78, 3.75],
          2025: [3.74, 3.69, 3.66, 3.68, 3.62, 3.61, 3.57, 3.54, 3.48, 3.42, 3.39, 3.37],
          2026: [3.38, 3.40, 3.42, 3.41, 3.43, 3.44, 3.45, 3.44, 3.43, 3.43, 3.43, 3.43]}
    ipc = {}
    level = 108.46
    for y in (2023, 2024, 2025, 2026):
        for m in range(12):
            level *= (1 + infl[y][m] / 100) ** (1 / 12)
            ipc[(y, m + 1)] = round(level, 2)
    peaje = {}
    for y in (2023, 2024, 2025, 2026):
        for m in range(12):
            peaje[(y, m + 1)] = 7.6 + (y - 2023) * 0.27 + m * 0.02  # S/ por eje (referencial)
    def tab(series):
        return {(y, m + 1): series[y][m] for y in series for m in range(12)}
    return {"infl": tab(infl), "diesel": tab(diesel), "gas": tab(gas), "tc": tab(tc), "ipc": ipc, "peaje_eje": peaje}


SERIES = build_series()


# ---------------------------------------------------------------------------- regiones
def classify_point(lat, lon, alt):
    if alt >= 2300:
        return "sierra_central" if lat > -13.2 else "sierra_sur"
    if (lon > -76.9 and lat > -10.6 and alt < 1800) or (lon > -71.3 and lat > -13.9 and alt < 1500) \
            or (lon > -78.7 and lat > -6.8 and alt < 1800 and lon > -78.6):
        return "selva"
    if alt >= 1500:
        return "sierra_central" if lat > -13.2 else "sierra_sur"
    if lat > -9.0:
        return "costa_norte"
    if lat > -14.6:
        return "costa_centro"
    return "costa_sur"


def route_regions(route):
    prof = route["profile"]
    kms, alts = prof["km"], prof["alt"]
    geom, cum = route["geometry"], route["cum_km"]
    shares = {}
    j = 0
    for k, a in zip(kms, alts):
        while j < len(cum) - 2 and cum[j + 1] < k:
            j += 1
        lat, lon = geom[j]
        reg = classify_point(lat, lon, a)
        shares[reg] = shares.get(reg, 0) + 1
    total = sum(shares.values()) or 1
    out = {r: c / total for r, c in shares.items()}
    if route["corredor"].startswith("Challhuahuacho"):
        out = {"corredor_minero": 0.75, "sierra_sur": 0.1, "costa_sur": 0.15}
    return out


# Intensidad base mensual por región y amenaza (0-100). Meses 1..12
def season(month, peak_months, peak=1.0, base=0.15):
    return peak if month in peak_months else base


def hazard_profile(region, d):
    m = d.month
    rain_sierra = season(m, (12, 1, 2, 3), 1.0, 0.12)
    if m in (11, 4):
        rain_sierra = 0.45
    frost = season(m, (6, 7, 8), 1.0, 0.08)
    if m in (5, 9):
        frost = 0.4
    fog = season(m, (6, 7, 8, 9), 1.0, 0.2)
    rain_selva = season(m, (11, 12, 1, 2, 3, 4), 1.0, 0.35)
    fire = season(m, (8, 9, 10), 1.0, 0.05)
    rain_norte = season(m, (1, 2, 3, 4), 0.35, 0.03)
    h = {"lluvia": 0, "inundacion": 0, "huaico": 0, "derrumbe": 0, "helada": 0, "neblina": 0, "incendio": 0,
         "social": 0, "inseguridad": 0, "deterioro": 0, "congestion": 0}
    if region == "costa_centro":
        h.update(lluvia=4 + 6 * rain_norte, inundacion=3, huaico=6 + 10 * rain_sierra, derrumbe=5, neblina=10 + 32 * fog,
                 social=10, inseguridad=44, deterioro=24, congestion=38)
    elif region == "costa_norte":
        h.update(lluvia=6 + 45 * rain_norte, inundacion=6 + 40 * rain_norte, huaico=4 + 16 * rain_norte, derrumbe=4,
                 neblina=8 + 20 * fog, social=11, inseguridad=46, deterioro=26, congestion=20)
    elif region == "costa_sur":
        h.update(lluvia=3, inundacion=3, huaico=5 + 8 * rain_sierra, derrumbe=14, neblina=10 + 25 * fog, social=12,
                 inseguridad=26, deterioro=24, congestion=12)
    elif region == "sierra_central":
        h.update(lluvia=10 + 62 * rain_sierra, inundacion=4 + 10 * rain_sierra, huaico=8 + 55 * rain_sierra,
                 derrumbe=10 + 40 * rain_sierra, helada=8 + 58 * frost, neblina=8 + 18 * rain_sierra, social=14,
                 inseguridad=28, deterioro=42 + 12 * rain_sierra, congestion=14, incendio=4 + 18 * fire)
    elif region == "sierra_sur":
        h.update(lluvia=10 + 55 * rain_sierra, inundacion=4 + 12 * rain_sierra, huaico=6 + 40 * rain_sierra,
                 derrumbe=8 + 30 * rain_sierra, helada=10 + 64 * frost, neblina=6 + 14 * rain_sierra, social=22,
                 inseguridad=30, deterioro=40 + 12 * rain_sierra, congestion=10, incendio=4 + 16 * fire)
    elif region == "corredor_minero":
        h.update(lluvia=10 + 50 * rain_sierra, inundacion=4, huaico=6 + 30 * rain_sierra, derrumbe=10 + 26 * rain_sierra,
                 helada=10 + 50 * frost, neblina=6, social=42, inseguridad=36, deterioro=62 + 10 * rain_sierra,
                 congestion=8, incendio=3)
    elif region == "selva":
        h.update(lluvia=20 + 62 * rain_selva, inundacion=8 + 36 * rain_selva, huaico=8 + 44 * rain_selva,
                 derrumbe=8 + 36 * rain_selva, neblina=10 + 10 * rain_selva, social=13, inseguridad=34,
                 deterioro=48 + 14 * rain_selva, congestion=8, incendio=6 + 40 * fire, helada=3)
    return h


def episodes(d, regions, corredor, modo):
    """Multiplicadores por episodios históricos reales (y patrones recurrentes simulados)."""
    mult = {k: 1.0 for k in ("lluvia", "inundacion", "huaico", "derrumbe", "helada", "neblina", "incendio",
                             "social", "inseguridad", "congestion", "rio", "oleaje", "aereo")}
    labels = []
    sur = regions.get("sierra_sur", 0) + regions.get("corredor_minero", 0) + regions.get("costa_sur", 0) * 0.6
    norte = regions.get("costa_norte", 0)
    lima = "Lima" in corredor or "Callao" in corredor or "Chancay" in corredor or "Lurín" in corredor
    # 1) Crisis social del sur (dic-2022 → mar-2023): bloqueos masivos en Puno, Cusco, Apurímac, Arequipa, Ica
    if in_range(d, date(2023, 1, 1), date(2023, 3, 15)):
        f = 1 + 3.6 * min(1.0, sur * 1.4)
        if "Ica" in corredor or "Arequipa" in corredor or "Tacna" in corredor:
            f = max(f, 2.4)
        if in_range(d, date(2023, 1, 4), date(2023, 2, 10)):
            f *= 1.35
        mult["social"] *= f
        if f > 1.6:
            labels.append("crisis_social")
        if modo == "Aéreo" and any(c in corredor for c in ("Juliaca", "Cusco", "Arequipa")):
            mult["aereo"] *= 2.6
    # 2) Ciclón Yaku / Niño Costero (5-mar → 20-abr 2023)
    if in_range(d, date(2023, 3, 5), date(2023, 4, 20)):
        mult["inundacion"] *= 1 + 5.5 * norte
        mult["lluvia"] *= 1 + 4.0 * norte
        mult["huaico"] *= 1 + 2.5 * norte + 1.2 * regions.get("costa_centro", 0)
        if norte > 0.25:
            labels.append("yaku")
    # 3) El Niño costero (alerta ENFEN jun-2023 → abr-2024): lluvias sobre lo normal en el norte (verano 2024)
    if in_range(d, date(2024, 1, 10), date(2024, 3, 31)):
        mult["inundacion"] *= 1 + 1.3 * norte
        mult["lluvia"] *= 1 + 1.0 * norte
    # 4) Estiaje amazónico extremo
    if in_range(d, date(2023, 9, 1), date(2023, 11, 20)) or in_range(d, date(2024, 8, 10), date(2024, 11, 15)):
        mult["rio"] *= 2.6
    # 5) Incendios forestales en selva (ago-oct 2024)
    if in_range(d, date(2024, 8, 15), date(2024, 10, 20)):
        mult["incendio"] *= 1 + 3.2 * regions.get("selva", 0) + 1.2 * regions.get("sierra_central", 0)
    # 6) Paros de transportistas por extorsión (Lima / Trujillo)
    for a, b in ((date(2024, 10, 10), date(2024, 10, 12)), (date(2024, 10, 23), date(2024, 10, 25)),
                 (date(2025, 4, 10), date(2025, 4, 11)), (date(2025, 10, 6), date(2025, 10, 8))):
        if in_range(d, a, b) and (lima or "Trujillo" in corredor):
            mult["social"] *= 4.0
            mult["inseguridad"] *= 1.8
            labels.append("paro_transportistas")
    # Escalada de la extorsión al transporte (2024 → 2026) en Lima y la costa norte
    if d >= date(2024, 3, 1) and (lima or norte > 0.2):
        mult["inseguridad"] *= 1.18 if d < date(2025, 1, 1) else 1.28
    # 7) Nueva terminal del Aeropuerto Jorge Chávez (transición jun-jul 2025)
    if modo == "Aéreo" and in_range(d, date(2025, 6, 1), date(2025, 7, 20)):
        mult["aereo"] *= 1.7
        mult["congestion"] *= 1.5
        labels.append("nuevo_lim")
    # 8) Campaña de fin de año (Cyber Wow, Navidad) y Fiestas Patrias: congestión urbana y portuaria
    if d.month in (11, 12) or (d.month == 7 and d.day >= 15):
        mult["congestion"] *= 1.35
    # 9) Bloqueos recurrentes en el Corredor Minero Sur (episodios de 4-12 días, ~6 por año)
    if corredor.startswith("Challhuahuacho") or "Matarani" in corredor:
        if MINERO_EPISODES.get(d):
            mult["social"] *= 3.2
            labels.append("bloqueo_minero")
    # 10) Oleajes anómalos (avisos DHN): episodios de 1-3 días, más frecuentes en may-sep
    if modo == "Marítimo" and OLEAJE_DAYS.get(d):
        mult["oleaje"] *= 3.5
        labels.append("oleaje")
    return mult, labels


def _episode_calendar(per_year, dur, months_weight=None, seed=7):
    r = np.random.default_rng(seed)
    days = {}
    for y in range(2023, 2027):
        n = r.poisson(per_year)
        for _ in range(n):
            if months_weight:
                mw = np.array(months_weight, dtype=float)
                month = int(r.choice(12, p=mw / mw.sum())) + 1
            else:
                month = int(r.integers(1, 13))
            start = date(y, month, int(r.integers(1, 28)))
            length = int(r.integers(dur[0], dur[1] + 1))
            for k in range(length):
                days[start + timedelta(days=k)] = True
    return days


MINERO_EPISODES = _episode_calendar(6, (4, 12), seed=11)
OLEAJE_DAYS = _episode_calendar(14, (1, 3), months_weight=[.5, .5, .6, .9, 1.4, 1.6, 1.7, 1.6, 1.3, .9, .6, .5], seed=23)


# ---------------------------------------------------------------------------- red
def load_network():
    with open(NETWORK_PATH, encoding="utf-8") as f:
        net = json.load(f)
    nodes = {n["nombre"]: n for n in net["nodes"]}
    routes = {r["id"]: r for r in net["routes"]}
    return nodes, routes


def truck_hours(route):
    """Horas de conducción de un camión pesado a partir del perfil real: velocidad de referencia
    de OSRM corregida por pendiente (subidas de los Andes) y pérdida de potencia por altitud."""
    prof = route["profile"]
    kms, alts, vs = prof["km"], prof["alt"], prof["v"]
    hours = 0.0
    for i in range(1, len(kms)):
        dk = kms[i] - kms[i - 1]
        if dk <= 0:
            continue
        slope = (alts[i] - alts[i - 1]) / dk  # m por km
        v_car = vs[i] or 40
        v = min(v_car * 0.80, 72.0)
        if slope > 0:
            v *= max(0.40, 1 - slope / 115.0)
        elif slope < -25:
            v *= max(0.55, 1 + slope / 160.0)  # bajadas largas con freno motor
        if alts[i] > 3500:
            v *= 0.9
        hours += dk / max(v, 8.0)
    return hours


def n_peajes(route, regions):
    km = route["km"]
    if km < 30:
        return 0
    costa = sum(v for k, v in regions.items() if k.startswith("costa"))
    return int(round(km * costa / 105 + km * (1 - costa) / 175))


# ---------------------------------------------------------------------------- generación
def pick_date():
    total_days = (END - START).days + 1
    while True:
        d = START + timedelta(days=int(rng.integers(0, total_days)))
        f = [0.95, 0.92, 1.0, 0.98, 1.0, 0.98, 1.04, 1.0, 1.02, 1.05, 1.13, 1.16][d.month - 1]
        f *= 1 + 0.06 * (d.year - 2023)
        f *= 0.72 if d.weekday() == 6 else 1.0
        if rng.random() < f / 1.45:
            return d


def corridor_weight(c, d):
    corredor, modo, w, mix = c
    if "Chancay" in corredor:
        if d < CHANCAY_START:
            return 0.0
        ramp = min(1.0, 0.25 + (d - CHANCAY_START).days / 420)
        w *= ramp
    if mix == "agro":
        m = d.month
        if corredor == "Ica - Callao":
            w *= 1.9 if m in (12, 1, 2) else 1.4 if m in (4, 5, 6, 7) else 0.7
        elif corredor == "Trujillo - Callao":
            w *= 1.9 if m in (8, 9, 10, 11, 12) else 1.2 if m in (4, 5, 6) else 0.6
        elif corredor in ("Piura - Paita", "Paita - Callao"):
            w *= 2.0 if m in (11, 12, 1, 2) else 0.8
    if modo == "Marítimo" and corredor.startswith("Callao") and d >= CHANCAY_START:
        w *= 0.9  # parte de la carga migra a Chancay
    return w


def main():
    nodes, routes = load_network()
    corridor_info = {}
    for c in CORRIDORS:
        corredor, modo = c[0], c[1]
        rid = f"{MODE_PREFIX[modo]}:{corredor}"
        r = routes[rid]
        regions = route_regions(r) if modo == "Carretero" else (
            {"maritimo": 1.0} if modo == "Marítimo" else {"selva": 1.0} if modo == "Fluvial" else {"aereo": 1.0})
        info = {"route": r, "regions": regions}
        if modo == "Carretero":
            info["drive_h"] = truck_hours(r)
            info["peajes"] = n_peajes(r, regions)
        corridor_info[(corredor, modo)] = info
        if modo == "Carretero":
            print(f"  {corredor:<28} {r['km']:>7.1f} km  manejo {info['drive_h']:>5.1f} h  peajes {info['peajes']:>2}  "
                  + " ".join(f"{k}:{v:.2f}" for k, v in sorted(regions.items(), key=lambda kv: -kv[1])))

    rows = []
    for _ in range(N_ROWS):
        d = pick_date()
        weights = np.array([corridor_weight(c, d) for c in CORRIDORS])
        c = CORRIDORS[rng.choice(len(CORRIDORS), p=weights / weights.sum())]
        rows.append(make_row(d, c, corridor_info[(c[0], c[1])], nodes))

    rows.sort(key=lambda r: (r["Fecha"], r["_rand"]))
    seq = {}
    for r in rows:
        y = r["Año"]
        seq[y] = seq.get(y, 0) + 1
        r["ID_Viaje"] = f"RNS-{y}-{seq[y]:06d}"
        r.pop("_rand")

    header = [f["variable"] for f in DICTIONARY]
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})

    with open(OUT_DICT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Variable", "Tipo_de_Dato", "Unidad_de_Medida", "Fuente_Publica_de_Referencia", "Descripcion", "En_Modelo"])
        for fld in DICTIONARY:
            w.writerow([fld["variable"], fld["tipo"], fld["unidad"], fld["fuente"], fld["desc"], "Sí" if fld["modelo"] else "No"])

    otif = np.mean([r["OTIF"] for r in rows])
    print(f"\nOK: {len(rows):,} embarques × {len(header)} variables → {OUT_CSV}")
    print(f"    OTIF global {otif * 100:.1f}%  ·  diccionario → {OUT_DICT}")


def lvl3(v, a, b):
    return "Bajo" if v < a else "Medio" if v < b else "Alto"


def make_row(d, c, info, nodes):
    corredor, modo, _w, mix = c
    route, regions = info["route"], info["regions"]
    origen, destino = route["origen"], route["destino"]
    if modo == "Aéreo":
        origen = "Lima"
    sector = wchoice(SECT[mix])
    if corredor == "Challhuahuacho - Matarani":
        sector = "Minería"
    carga = choice(CARGA_POR_SECTOR[sector])
    if sector == "Minería" and "Matarani" not in corredor and "Ilo" not in corredor and carga == "Concentrado de minerales":
        carga = "Insumos mineros (MATPEL)" if rng.random() < .6 else "Repuestos críticos"
    prioridad = choice([("Estándar", .55), ("Alta", .30), ("Crítica / Estratégico", .15)])
    if sector in ("Salud", "Agroexportación") and rng.random() < .3:
        prioridad = "Crítica / Estratégico"

    # --------------------------------------------------- contexto de riesgo (pre-despacho)
    if modo == "Carretero":
        hz = {k: 0.0 for k in ("lluvia", "inundacion", "huaico", "derrumbe", "helada", "neblina", "incendio", "social",
                               "inseguridad", "deterioro", "congestion")}
        for reg, share in regions.items():
            hp = hazard_profile(reg, d)
            for k in hz:
                hz[k] += hp[k] * share
    else:
        base_reg = "costa_centro" if modo in ("Marítimo", "Aéreo") else "selva"
        hz = hazard_profile(base_reg, d)
        hz = {k: v * (0.35 if modo != "Fluvial" else 0.6) for k, v in hz.items()}
        if modo == "Fluvial":
            hz["lluvia"] = hazard_profile("selva", d)["lluvia"]
    mult, labels = episodes(d, regions, corredor, modo)
    for k in hz:
        hz[k] *= mult.get(k, 1.0)
    noise = lambda s=1.0: float(rng.normal(1.0, 0.18 * s))
    # condición del DÍA de despacho (conocible por boletines SENAMHI/INDECI, Defensoría, noticias):
    # factor log-normal que hace que un mismo corredor tenga días tranquilos y días críticos.
    dia = lambda sd: float(rng.lognormal(-sd * sd / 2, sd))
    clima_dia = dia(0.55)

    indice_inundaciones = clip(hz["inundacion"] * clima_dia * noise(0.6), 0, 100)
    indice_deslizamientos = clip(hz["huaico"] * clima_dia * noise(0.6), 0, 100)
    indice_derrumbes = clip(hz["derrumbe"] * clima_dia * noise(0.6) + 0.25 * indice_deslizamientos, 0, 100)
    indice_incendios = clip(hz["incendio"] * dia(0.6), 0, 100)
    indice_protestas = clip(hz["social"] * dia(0.7), 0, 100)
    indice_deterioro = clip(hz["deterioro"] * noise(0.6) + 0.15 * indice_deslizamientos, 3, 95)
    base_seg = {"Carretero": 100 - hz["inseguridad"], "Marítimo": 86, "Fluvial": 70, "Aéreo": 92}[modo]
    indice_seguridad = clip(base_seg * noise(0.35) if modo == "Carretero" else base_seg + rng.normal(0, 4), 12, 99)
    indice_orden_publico = clip(100 - 0.65 * indice_protestas - 0.25 * (100 - indice_seguridad) + rng.normal(8, 6), 15, 99)
    social_bloq = indice_protestas / 100
    indice_bloqueos = clip(0.62 * indice_protestas + 0.22 * indice_deslizamientos + 0.16 * indice_inundaciones
                           + rng.normal(0, 4), 0, 100) if modo == "Carretero" else clip(rng.normal(3, 2), 0, 15)
    numero_paros = int(rng.poisson(max(0.02, indice_protestas / 28)))
    manifestaciones = int(rng.poisson(max(0.02, indice_protestas / 40)))
    huelgas = int(rng.random() < clip(indice_protestas / 140, 0, .8))
    bloqueos_sociales = int(rng.poisson(max(0.01, (indice_protestas / 24) ** 1.3)))
    numero_bloqueos = int(rng.poisson(indice_bloqueos / 22)) if modo == "Carretero" else 0
    numero_cierres = int(rng.poisson((indice_deslizamientos + indice_inundaciones) / 70)) if modo == "Carretero" else 0
    numero_inund = int(rng.poisson(indice_inundaciones / 30))
    numero_desl = int(rng.poisson(indice_deslizamientos / 28))
    numero_derr = int(rng.poisson(indice_derrumbes / 30))
    numero_incend = int(rng.poisson(indice_incendios / 30))
    crimen = int(rng.random() < clip((100 - indice_seguridad - 22) / 70, 0.01, 0.85)) if modo != "Aéreo" else 0
    numero_eventos_seg = int(rng.poisson(max(0.03, (100 - indice_seguridad) / 32)))
    obras = int(rng.poisson(1.4 if ("Lima" in corredor or "Huancayo" in corredor) and modo == "Carretero" else 0.8))
    restr_peso = int(rng.random() < (0.22 if regions.get("sierra_central", 0) + regions.get("sierra_sur", 0) > .3 else 0.08))
    restr_hor = int(rng.random() < (0.72 if corredor in ("Callao - Lima", "Lima - Lima", "Callao - Lurín",
                                                         "Chancay - Lima", "Chancay - Callao") else 0.18))

    alt_max = route["alt_max"] if modo == "Carretero" else (
        max(ALT_AEROPUERTO.get(origen, 30), ALT_AEROPUERTO.get(destino, 30)) if modo == "Aéreo" else
        150 if modo == "Fluvial" else 0)
    prof = route["profile"]
    alt_mean = float(np.mean(prof["alt"])) if modo == "Carretero" else (130 if modo == "Fluvial" else 20)

    # clima
    m = d.month
    verano = m in (12, 1, 2, 3, 4)
    temp = 27 - 0.0058 * alt_mean + (3.5 if verano else -3.0) + rng.normal(0, 1.8)
    if modo == "Fluvial" or regions.get("selva", 0) > 0.5:
        temp = 28 + rng.normal(0, 1.5) - (5 if m in (6, 7, 8) and rng.random() < .35 else 0)
    precip = clip(0.9 * hz["lluvia"] * clima_dia * noise(0.8) + rng.gamma(1.2, 1.5), 0, 320)
    humedad = clip((82 if alt_mean < 800 else 58) + 0.12 * precip + rng.normal(0, 5), 18, 100)
    mar_dia = dia(0.5)
    oleaje_evento = modo == "Marítimo" and "oleaje" in labels
    viento = clip(rng.gamma(4, 3.0) * (mar_dia if modo == "Marítimo" else 1) + (8 if alt_mean > 3500 else 0)
                  + (6 if modo == "Marítimo" else 0) + (14 if oleaje_evento else 0), 0.5, 75)
    helada_dia = clip(hz["helada"] * clima_dia, 0, 100)
    neblina_dia = clip(hz["neblina"] * dia(0.45), 0, 100)
    peligro = max(indice_inundaciones, indice_deslizamientos, helada_dia, hz["lluvia"] * clima_dia * 0.8, neblina_dia * 0.7)
    alerta = "Ninguna" if peligro < 32 else "Amarilla" if peligro < 52 else "Naranja" if peligro < 70 else "Roja"
    if rng.random() < .08:
        alerta = ["Ninguna", "Amarilla"][int(rng.integers(0, 2))] if alerta == "Ninguna" else alerta

    sierra = regions.get("sierra_central", 0) + regions.get("sierra_sur", 0) + regions.get("corredor_minero", 0)
    if "yaku" in labels:
        fenomeno = "Ciclón Yaku / Niño Costero"
    elif in_range(d, date(2023, 6, 1), date(2024, 4, 15)):
        fenomeno = "El Niño Costero (alerta ENFEN)"
    elif modo == "Marítimo" and "oleaje" in labels:
        fenomeno = "Oleajes anómalos"
    elif sierra > 0.35 and m in (12, 1, 2, 3):
        fenomeno = "Lluvias intensas en sierra"
    elif sierra > 0.35 and m in (6, 7, 8):
        fenomeno = "Heladas y nevadas"
    elif (regions.get("selva", 0) > 0.4 or modo == "Fluvial") and m in (6, 7, 8):
        fenomeno = "Friaje amazónico"
    elif modo == "Fluvial" and m in (8, 9, 10):
        fenomeno = "Vaciante de ríos amazónicos"
    elif regions.get("selva", 0) > 0.3 and m in (8, 9, 10) and d.year == 2024:
        fenomeno = "Incendios forestales"
    elif m in (6, 7, 8, 9) and modo in ("Carretero", "Aéreo"):
        fenomeno = "Neblina / garúa costera"
    elif in_range(d, date(2024, 11, 1), date(2025, 3, 31)):
        fenomeno = "La Niña costera (débil)"
    else:
        fenomeno = "Condiciones normales (ENSO neutral)"

    estado_via_score = indice_deterioro + 0.35 * max(indice_deslizamientos, indice_inundaciones)
    estado_via = "Bueno" if estado_via_score < 32 else "Regular" if estado_via_score < 52 else "Malo" if estado_via_score < 72 else "Crítico"
    if modo != "Carretero":
        estado_via = "Bueno" if rng.random() < .7 else "Regular"

    # operación / flota
    util_alm_pre = clip(rng.normal(68, 11) + (10 if m in (10, 11, 12) else 0), 20, 99)
    disp_flota = clip(rng.normal(91, 4.2) - (5 if m in (11, 12) else 0) - 0.06 * indice_bloqueos, 62, 99.5)
    util_flota = clip(rng.normal(71, 9) + (9 if m in (11, 12) else 0) + (6 if sector == "Agroexportación" else 0), 30, 99)

    # --------------------------------------------------- vehículo, carga y distancia
    km = route["km"]
    if modo == "Carretero":
        urbano = km < 90
        if carga == "Concentrado de minerales":
            veh, cap = "Camión encapsulado (concentrado)", 34
        elif carga == "Insumos mineros (MATPEL)":
            veh, cap = "Cisterna / furgón MATPEL", 28
        elif carga == "Hidrocarburos y lubricantes (líquidos)":
            veh, cap = "Cisterna de líquidos", 30
        elif carga == "Vehículos nuevos (cigüeña)":
            veh, cap = "Cigüeña portavehículos (8 autos)", 12
        elif carga in FRIO:
            veh, cap = ("Furgón refrigerado urbano", 6) if urbano and rng.random() < .55 else ("Tractocamión refrigerado (reefer)", 26)
        elif carga == "Industrial y maquinaria" and rng.random() < .35:
            veh, cap = "Plataforma / cama baja", 30
        elif urbano:
            veh, cap = choice([(("Furgón urbano (N2)", 3.5), .45), (("Camión C2 (8 t)", 8), .35), (("Camión C3 (15 t)", 15), .20)])
        else:
            veh, cap = choice([(("Tractocamión T3S3 (30 t)", 30), .55), (("Camión C3 (15 t)", 15), .30), (("Camión C2 (8 t)", 8), .15)])
        dist = km * rng.uniform(0.985, 1.035) if corredor != "Lima - Lima" else rng.uniform(18, 95)
        peso = cap * clip(rng.beta(5, 2), 0.25, 1.0)
    elif modo == "Marítimo":
        veh = choice([("Buque portacontenedores", .55), ("Buque de cabotaje multipropósito", .30), ("Buque granelero", .15)])
        dist = km
        peso = float(clip(rng.lognormal(6.1, 0.65), 60, 4200)) if veh != "Buque granelero" else float(rng.uniform(800, 6500))
        if carga == "Concentrado de minerales":
            veh, peso = "Buque granelero", float(rng.uniform(1500, 9000))
        elif carga == "Vehículos nuevos (cigüeña)":
            veh, peso = "Buque ro-ro (vehículos)", float(rng.uniform(120, 1300))
        elif carga == "Hidrocarburos y lubricantes (líquidos)":
            veh, peso = "Buque tanque de cabotaje", float(rng.uniform(2000, 12000))
    elif modo == "Fluvial":
        veh = choice([("Empujador + chatas (convoy fluvial)", .6), ("Motonave fluvial", .4)])
        dist = km
        peso = float(clip(rng.lognormal(4.9, 0.6), 25, 900))
    else:
        veh = choice([("Avión carguero (B767-300F)", .42), ("Bodega de avión de pasajeros", .58)])
        dist = route["km"]
        peso = float(clip(rng.lognormal(0.3, 0.75), 0.08, 18 if "carguero" in veh else 4.5))
    volumen = peso * DENSIDAD_M3_POR_T[carga] * rng.uniform(0.85, 1.15)

    # --------------------------------------------------- tiempos esperados (programados)
    if modo == "Carretero":
        drive = info["drive_h"] * (dist / km if km else 1)
        if corredor == "Lima - Lima":
            drive = dist / rng.uniform(16, 24)
        rests = 0.5 * math.floor(drive / 4.5) + 5.0 * math.floor(drive / 13)
        handling = rng.uniform(1.0, 2.5) + (rng.uniform(1.5, 4.0) if "Callao" in corredor or "Chancay" in corredor else 0)
        esperado = drive + rests + handling
    elif modo == "Marítimo":
        sail = dist / rng.uniform(22, 27)
        esperado = sail + rng.uniform(18, 30) + rng.uniform(10, 20)
    elif modo == "Fluvial":
        esperado = dist / rng.uniform(10.5, 12.5) + rng.uniform(16, 26)
    else:
        esperado = dist / 640 + 0.6 + rng.uniform(5.0, 9.0)
    # El tiempo comprometido incorpora las esperas TÍPICAS del modo (andén, garita, fondeadero) y la
    # estacionalidad conocida (vaciante); los atrasos solo aparecen cuando la realidad supera lo típico.
    if modo == "Carretero":
        espera_tipica = 0.35 * (1.05 + 0.75 * util_flota / 100 + 0.9 * restr_hor
                                + (2.0 if "Callao" in corredor or "Chancay" in corredor else 0))
        holgura = 1.0 if km < 90 else 0.0
    elif modo == "Marítimo":
        espera_tipica, holgura = 0.15 * 5 + 0.8 * 9, 0.0
    elif modo == "Fluvial":
        espera_tipica, holgura = 0.15 * 5 + (esperado * 0.18 if m in (8, 9, 10) else 0), 0.0
    else:
        espera_tipica, holgura = 0.15 * 5 + 0.5, 0.0
    buffer = {"Estándar": 1.17, "Alta": 1.13, "Crítica / Estratégico": 1.10}[prioridad] + rng.normal(0, 0.012)
    t_prog = (esperado + espera_tipica) * buffer + holgura

    # --------------------------------------------------- materialización del viaje (post-despacho)
    delay = esperado * rng.normal(0.0, 0.025)
    espera = rng.gamma(2.0, 0.5) if modo == "Carretero" else rng.gamma(2, 2.5)
    accidentes = 0
    incidente_h = 0.0
    cierre_h = 0.0
    if modo == "Carretero":
        horas_riesgo = max(drive, 1.0)
        p_bloq = clip(1.25 * (indice_bloqueos / 100) ** 2.0 * (0.6 + horas_riesgo / 30), 0, 0.9)
        if rng.random() < p_bloq:
            cierre = rng.gamma(2.5, 1.2 + 9.0 * social_bloq)
            delay += cierre
            cierre_h += cierre
        p_huaico = clip(1.3 * ((indice_deslizamientos + indice_derrumbes) / 200) ** 2.0 * (0.5 + horas_riesgo / 26), 0, 0.85)
        if rng.random() < p_huaico:
            cierre = rng.gamma(2.5, 0.8 + 6.0 * (indice_deslizamientos + indice_derrumbes) / 200)
            delay += cierre
            cierre_h += cierre
        p_inund = clip(1.3 * (indice_inundaciones / 100) ** 2.0 * (0.6 + horas_riesgo / 24), 0, 0.85)
        if rng.random() < p_inund:
            cierre = rng.gamma(2.5, 0.8 + 7.0 * indice_inundaciones / 100)
            delay += cierre
            cierre_h += cierre
        delay += (helada_dia / 100) ** 1.5 * rng.uniform(0, 7) * (alt_max > 3800) + (neblina_dia / 100) ** 1.5 * rng.uniform(0, 3)
        lam_acc = 0.004 + km / 22000 * (1 + neblina_dia / 45 + helada_dia / 55) + (0.01 if alt_max > 4000 else 0)
        accidentes = int(rng.poisson(lam_acc))
        if accidentes:
            incidente_h = float(rng.gamma(2, 1.6)) * accidentes
            delay += incidente_h * rng.uniform(0.5, 1.0)
        espera += (util_flota / 100) ** 2 * rng.uniform(0, 2.2) + restr_hor * rng.uniform(0, 1.8)
        if "Callao" in corredor or "Chancay" in corredor:
            espera += rng.gamma(2.0, 0.9) * (1 + hz["congestion"] / 60) * (util_flota / 70) ** 2
        # falla mecánica: más probable con baja disponibilidad de flota y neumáticos gastados
        neum = choice([("Bueno", .45), ("Regular", .35), ("Desgaste", .20)])
        p_mec = 0.006 + (0.02 if neum == "Desgaste" else 0) + max(0.0, 94 - disp_flota) / 450 + (0.01 if alt_max > 4000 else 0)
        if rng.random() < p_mec:
            delay += rng.uniform(1.5, 9)
    else:
        neum = None
    # seguridad: robo / asalto
    p_robo = clip(((100 - indice_seguridad) / 100) ** 2.6 * (0.07 if modo == "Carretero" else 0.02) * (1 + crimen), 0, 0.3)
    robo = rng.random() < p_robo

    # modos no carreteros
    congestion_port = fondeo = gruas = None
    estado_mar = nivel_rio = None
    retraso_vuelo = cancel = congestion_aero = cap_bodega_aero = None
    if modo == "Marítimo":
        # la congestión del terminal se anticipa por la ocupación de almacenes/depósitos del puerto
        congestion_port = clip((0.75 * util_alm_pre + rng.normal(0, 8)) * mult["congestion"]
                               * (1.1 if "Callao" in corredor else 0.9), 5, 99)
        oleaje = oleaje_evento
        estado_mar = "Oleaje anómalo" if oleaje else ("Agitado" if viento > 26 else "Moderado" if viento > 17 else "Calmo")
        fondeo = clip(rng.gamma(2, 3) * (1 + congestion_port / 70) * (viento / 18) ** 1.5
                      + (rng.uniform(24, 60) if oleaje else 0), 0, 140)
        gruas = clip(rng.normal(80, 10) - (15 if oleaje else 0), 35, 100)
        delay += fondeo * 0.8 + (rng.uniform(6, 24) if estado_mar == "Agitado" and rng.random() < .3 else 0)
    elif modo == "Fluvial":
        if m in (8, 9, 10):
            nivel_rio = "Vaciante extrema" if mult["rio"] > 2 else "Vaciante"
        elif m in (2, 3, 4, 5):
            nivel_rio = "Creciente"
        else:
            nivel_rio = "Normal"
        rio_f = {"Normal": 0.0, "Creciente": 0.10, "Vaciante": 0.35, "Vaciante extrema": 0.95}[nivel_rio]
        delay += esperado * rio_f * rng.uniform(0.3, 1.0)
        estado_mar = None
    elif modo == "Aéreo":
        congestion_aero = clip(rng.normal(52, 18) * mult["congestion"], 5, 99)
        p_weather = 0.06 + (0.16 if ("Cusco" in corredor or "Juliaca" in corredor) and verano else 0) + \
            (0.10 if "Iquitos" in corredor and verano else 0) + min(0.35, precip / 140)
        retraso_vuelo = float(rng.gamma(1.4, 28) * (1 + precip / 60) * mult["aereo"]) if rng.random() < (0.22 + p_weather) else 0.0
        cancel = int(rng.random() < clip(0.012 + p_weather * 0.15 + (mult["aereo"] - 1) * 0.08, 0, 0.6))
        delay += retraso_vuelo / 60 + (rng.uniform(10, 26) if cancel else 0)
        cap_bodega_aero = clip(rng.normal(78, 12), 35, 100)

    t_real = max(esperado * 0.82, esperado + delay + espera * (0.35 if modo == "Carretero" else 0.15))
    leadtime = t_real / 24

    # completitud y servicio
    fill = clip(rng.normal(98.6, 1.4), 86, 100)
    inventario = clip(rng.normal(52, 15) - (8 if m in (11, 12) else 0), 3, 100)
    if inventario < 18:
        fill -= rng.uniform(2, 9)
    siniestro = 0
    valor_siniestro = 0.0
    valor_t = VALOR_PEN_POR_T[carga]
    valor_aseg = peso * valor_t * rng.uniform(0.85, 1.2)
    temp_reefer = None
    if carga in FRIO:
        temp_reefer = rng.normal(-18.5 if carga == "Pesca y congelados" else 4.2, 0.9)
        if delay > esperado * 0.4 and rng.random() < 0.35:
            temp_reefer += rng.uniform(3, 7)  # excursión térmica por demora
    if robo or (accidentes and rng.random() < .22) or (temp_reefer is not None and carga != "Pesca y congelados"
                                                         and temp_reefer > 8 and rng.random() < .6):
        siniestro = 1
        valor_siniestro = valor_aseg * rng.uniform(0.03, 0.45)
        fill -= rng.uniform(4, 30)
    fill = clip(fill, 40, 100)
    on_time = t_real <= t_prog
    otif = int(on_time and fill >= 95)
    on_time_score = clip(1 - max(0.0, t_real / t_prog - 1) * 1.6, 0, 1)
    nivel_servicio = clip(100 * (0.55 * on_time_score + 0.30 * fill / 100 + 0.15 * (1 - siniestro)) + rng.normal(0, 1.2), 15, 100)

    # --------------------------------------------------- costos (soles)
    peaje_eje = month_interp(d, SERIES["peaje_eje"])
    diesel = month_interp(d, SERIES["diesel"]) * (1 + 0.07 * sierra + (0.13 if "Iquitos" in corredor or "Pucallpa" in corredor else 0)) \
        * rng.uniform(0.98, 1.02)
    if modo == "Carretero":
        ejes = {"Furgón urbano (N2)": 2, "Camión C2 (8 t)": 2, "Camión C3 (15 t)": 3, "Furgón refrigerado urbano": 2}.get(veh, 6)
        precio_peaje = peaje_eje * ejes
        peajes = info["peajes"] * precio_peaje * (1 if corredor != "Lima - Lima" else 0)
        tarifa_km = {6: 5.3, 3: 3.7, 2: 2.6}[ejes]
        if "refriger" in veh:
            tarifa_km *= 1.32
        if "MATPEL" in veh:
            tarifa_km *= 1.25
        if "encapsulado" in veh:
            tarifa_km *= 1.12
        if "Cigüeña" in veh:
            tarifa_km *= 1.15
        if veh == "Cisterna de líquidos":
            tarifa_km *= 1.20
        tarifa_km *= 1 + 0.28 * sierra + 0.33 * regions.get("selva", 0)
        costo = max(380.0, dist * tarifa_km * (0.65 + 0.35 * peso / cap)) * (1 + (diesel - 16) / 40)
        if corredor in ("Lima - Lima", "Callao - Lima", "Callao - Lurín"):
            costo = rng.uniform(220, 420) + dist * tarifa_km * 0.9
        costo += max(0.0, t_real - t_prog) / 24 * rng.uniform(550, 900) * (t_real > t_prog * 1.15)  # sobreestadía
        # rendimiento de referencia en km por galón; los Andes castigan el consumo (subidas largas)
        rend = {6: 9.5, 3: 13.0, 2: 19.0}[ejes] * (1 - 0.30 * sierra) * (0.9 if "refriger" in veh else 1)
        galones = dist / max(rend, 3.0) * (0.75 + 0.25 * peso / cap)
    elif modo == "Marítimo":
        precio_peaje, peajes = 0.0, 0.0
        costo = peso * rng.uniform(95, 140) + rng.uniform(4500, 9000) + (fondeo or 0) * rng.uniform(40, 80)
        galones = (dist / 24) * 300 * clip(peso / 9000, 0.02, 0.6)
    elif modo == "Fluvial":
        precio_peaje, peajes = 0.0, 0.0
        costo = peso * rng.uniform(150, 230) * (1.25 if nivel_rio and "Vaciante" in nivel_rio else 1)
        galones = (dist / 11) * 32 * clip(peso / 600, 0.08, 1)
    else:
        precio_peaje, peajes = 0.0, 0.0
        tarifa_kg = {"Lima - Iquitos": 3.8, "Lima - Puerto Maldonado": 5.4, "Lima - Cusco": 4.4}.get(corredor, 4.1)
        costo = peso * 1000 * tarifa_kg * rng.uniform(0.9, 1.15)
        galones = (dist / 640) * 1100 * clip(peso / (50 if "carguero" in veh else 12), 0.01, 0.6)
    costo = float(costo)

    # combustible de la unidad: la flota RANSA migra a GNL en el segmento extractivo (tractos) y en la
    # distribución de líquidos; en Lima y Callao la distribución usa camiones Euro V y algo de GNV.
    if modo == "Carretero":
        urbano = km < 90
        if sector == "Minería" and veh in ("Camión encapsulado (concentrado)", "Tractocamión T3S3 (30 t)") and rng.random() < .30:
            combustible = "GNL"
        elif veh == "Cisterna de líquidos" and rng.random() < .55:
            combustible = "GNL"
        elif urbano and rng.random() < .12:
            combustible = "GNV"
        else:
            combustible = choice([("Diésel B5 · Euro V", .64 if urbano else .52),
                                  ("Diésel B5 · Euro III/IV", .36 if urbano else .48)])
    else:
        combustible = {"Marítimo": "Fuelóleo marino (VLSFO)", "Fluvial": "Diésel marino", "Aéreo": "Turbo A-1"}[modo]
    co2_kg = galones * CO2_KG_POR_GALON[combustible]
    linea = linea_negocio(sector, carga, modo, corredor, mix)

    # seguro
    cobertura = choice([("Todo Riesgo", .34), ("Básica (FPA)", .30), ("RC Transportista", .36)])
    tasa = {"Todo Riesgo": 0.0032, "Básica (FPA)": 0.0014, "RC Transportista": 0.0009}[cobertura] * (1 + (100 - indice_seguridad) / 120)
    prima = valor_aseg * tasa
    deducible = valor_aseg * {"Todo Riesgo": 0.05, "Básica (FPA)": 0.08, "RC Transportista": 0.10}[cobertura] * rng.uniform(0.6, 1.4)
    estado_recl = "No Aplica" if not siniestro else choice([("Pagada", .68), ("En Trámite", .20), ("Rechazada", .12)])

    # almacén
    if carga in FRIO:
        tipo_alm = "Congelado (-18 °C)" if carga == "Pesca y congelados" else "Refrigerado (0–8 °C)"
    elif "MATPEL" in carga or carga in ("Concentrado de minerales", "Hidrocarburos y lubricantes (líquidos)"):
        tipo_alm = "MATPEL / graneles minerales"
    elif carga == "Vehículos nuevos (cigüeña)":
        tipo_alm = "Patio de vehículos (alistamiento)"
    elif carga in ("Tecnología y electrónica", "Repuestos críticos", "Dispositivos médicos"):
        tipo_alm = "Alto valor / seguridad"
    elif modo in ("Marítimo",) and rng.random() < .5:
        tipo_alm = "Depósito temporal aduanero"
    else:
        tipo_alm = "Seco general"
    big = origen in ("Callao", "Lima", "Lurín", "Chancay")
    cap_alm = rng.uniform(35000, 120000) if big else rng.uniform(4000, 28000)
    util_alm = util_alm_pre
    t_alm = clip(rng.gamma(2.2, 10) * (1.6 if tipo_alm == "Depósito temporal aduanero" else 1), 0.5, 180)
    cross = int(rng.random() < (0.32 if sector in ("Retail", "Consumo Masivo") else 0.12))
    demanda = float(clip(rng.lognormal(5.2, 0.8) * (1.25 if m in (11, 12) else 1), 4, 9000))
    pron = float(clip(demanda * rng.normal(1, 0.12), 3, 9500))
    abast = clip(rng.normal(72, 9) - 0.12 * indice_bloqueos, 15, 100)

    # incidente reportado
    if accidentes == 0 and cierre_h == 0:
        intensidad = "Ninguno"
    else:
        sev = incidente_h + cierre_h
        intensidad = "Leve" if sev < 6 else "Moderado" if sev < 16 else "Grave"

    vel_prom = dist / max(t_real - espera * 0.35, 0.5) if modo != "Aéreo" else dist / max(t_real, 0.5)
    tipo_cont = None
    if modo == "Marítimo":
        tipo_cont = "40RF (reefer)" if carga in FRIO else ("Granel" if veh == "Buque granelero" else choice([("20GP", .45), ("40HC", .55)]))

    r = {
        "_rand": float(rng.random()), "ID_Viaje": "", "Fecha": d.isoformat(), "Día_Semana": DIAS[d.weekday()],
        "Mes": MESES[d.month - 1], "Trimestre": (d.month - 1) // 3 + 1, "Año": d.year,
        "Departamento_Origen": nodes[origen]["departamento"], "Ciudad_Origen": origen,
        "Departamento_Destino": nodes[destino]["departamento"], "Ciudad_Destino": destino,
        "Corredor_Logístico": corredor, "Ruta_Principal": route["ruta_principal"], "Tipo_Transporte": modo,
        "Tipo_Vehículo": veh, "Tipo_Carga": carga, "Sector_Cliente": sector, "Línea_Negocio": linea,
        "Peso_Toneladas": round(peso, 3), "Volumen_m3": round(volumen, 3), "Distancia_Km": round(dist, 1),
        "Altitud_Max_Ruta_msnm": int(alt_max),
        "Tiempo_Programado_Horas": round(t_prog, 2), "Tiempo_Entrega_Real_Horas": round(t_real, 2),
        "Velocidad_Promedio_Kmh": round(vel_prom, 1), "Tiempo_Espera_Horas": round(espera, 2),
        "Consumo_Combustible_Galones": round(galones, 2), "Combustible_Unidad": combustible,
        "Emisiones_CO2_kg": round(co2_kg, 1), "Costo_Transporte_PEN": round(costo, 2),
        "Costo_Peajes_PEN": round(peajes, 2), "Disponibilidad_Flota_Pct": round(disp_flota, 1),
        "Utilización_Flota_Pct": round(util_flota, 1), "Estado_Vía": estado_via,
        "Índice_Deterioro_Vial": round(indice_deterioro, 1), "Número_Cierres_Viales": numero_cierres,
        "Número_Bloqueos_Carretera": numero_bloqueos, "Índice_Bloqueos": round(indice_bloqueos, 1),
        "Obras_Viales_Activas": obras, "Restricciones_Peso": restr_peso, "Restricciones_Horarias": restr_hor,
        "Índice_Seguridad": round(indice_seguridad, 1), "Riesgo_Hurto_Carga": lvl3(100 - indice_seguridad, 38, 62),
        "Número_Eventos_Seguridad": numero_eventos_seg, "Presencia_Crimen_Organizado": crimen,
        "Índice_Orden_Público": round(indice_orden_publico, 1),
        "Riesgo_Extorsión": lvl3((100 - indice_seguridad) * (1.25 if crimen else 0.8), 34, 58),
        "Riesgo_Vandalismo": lvl3(indice_protestas * 0.7 + (100 - indice_seguridad) * 0.3, 25, 50),
        "Riesgo_Saqueo": lvl3(indice_protestas * 0.6 + indice_inundaciones * 0.4, 28, 55),
        "Número_Paros": numero_paros, "Índice_Protestas": round(indice_protestas, 1), "Manifestaciones": manifestaciones,
        "Huelgas": huelgas, "Bloqueos_Sociales": bloqueos_sociales, "Temperatura_C": round(temp, 1),
        "Precipitación_mm": round(precip, 1), "Humedad_Pct": round(humedad, 1), "Velocidad_Viento_Kmh": round(viento, 1),
        "Alerta_SENAMHI": alerta, "Fenómeno_Climático": fenomeno, "Número_Inundaciones": numero_inund,
        "Índice_Inundaciones": round(indice_inundaciones, 1), "Número_Deslizamientos": numero_desl,
        "Índice_Deslizamientos": round(indice_deslizamientos, 1), "Número_Derrumbes": numero_derr,
        "Índice_Derrumbes": round(indice_derrumbes, 1), "Número_Incendios_Forestales": numero_incend,
        "Índice_Incendios": round(indice_incendios, 1),
        "Riesgo_Geológico": lvl3((indice_deslizamientos + indice_derrumbes) / 2, 25, 50),
        "Riesgo_Hidrológico": lvl3(indice_inundaciones, 22, 45), "Número_Accidentes": accidentes,
        "Intensidad_Incidente": intensidad, "Duración_Incidente_Horas": round(incidente_h, 2),
        "Tiempo_Cierre_Vía_Horas": round(cierre_h, 2),
        "Precio_Diésel_PEN_Gal": round(diesel, 2), "Precio_Gasolina_PEN_Gal": round(month_interp(d, SERIES["gas"]), 2),
        "IPC": round(month_interp(d, SERIES["ipc"]), 2), "Tipo_Cambio_PEN_USD": round(month_interp(d, SERIES["tc"]) + rng.normal(0, 0.01), 3),
        "Inflación_Pct": round(month_interp(d, SERIES["infl"]), 2), "Precio_Peajes_Promedio_PEN": round(precio_peaje, 2),
        "Índice_Abastecimiento": round(abast, 1), "Nivel_Inventario_Pct": round(inventario, 1),
        "Demanda_Unidades": round(demanda), "Demanda_Pronosticada_Unidades": round(pron),
        "Prioridad_Cliente": prioridad, "OTIF": otif, "Fill_Rate_Pct": round(fill, 1),
        "Nivel_Servicio_Pct": round(nivel_servicio, 1), "Tiempo_Almacenamiento_Horas": round(t_alm, 2),
        "Cross_Docking": cross, "Tipo_Almacén": tipo_alm, "Capacidad_Almacén_m3": round(cap_alm),
        "Utilización_Almacén_Pct": round(util_alm, 1), "Aseguradora": choice(ASEGURADORAS),
        "Tipo_Cobertura_Seguro": cobertura, "Valor_Asegurado_PEN": round(valor_aseg, 2), "Prima_Seguro_PEN": round(prima, 2),
        "Deducible_PEN": round(deducible, 2), "Siniestro": siniestro, "Valor_Siniestro_PEN": round(valor_siniestro, 2),
        "Estado_Reclamación": estado_recl, "LeadTime_Real_Dias": round(leadtime, 3),
    }
    # ---- variables multimodales complementarias (no entran al modelo de BD)
    if modo == "Aéreo":
        aer, code = choice([(a, .40 if a[0] == "LATAM Cargo" else .2) for a in AEROLINEAS])
        r.update({"Aeropuerto_Origen": AEROPUERTOS["Lima"], "Aeropuerto_Destino": AEROPUERTOS.get(destino, ""),
                  "Aerolínea": aer, "Número_Vuelo": f"{code}{int(rng.integers(1000, 9999))}",
                  "Tipo_Aeronave": "B767-300F" if "carguero" in veh else choice([("A320neo", .5), ("A321", .3), ("B787-8", .2)]),
                  "Capacidad_Bodega_%": round(cap_bodega_aero, 1), "Retraso_Vuelo_min": round(retraso_vuelo),
                  "Cancelación_Vuelo": cancel, "Congestión_Aeroportuaria_%": round(congestion_aero, 1)})
    if modo in ("Marítimo", "Fluvial"):
        r.update({"Puerto_Origen": PUERTOS[origen][int(rng.integers(0, len(PUERTOS[origen])))],
                  "Puerto_Destino": PUERTOS[destino][int(rng.integers(0, len(PUERTOS[destino])))]})
    if modo == "Marítimo":
        r.update({"Naviera": NAVIERAS[int(rng.integers(0, len(NAVIERAS)))], "IMO_Buque": int(rng.integers(9100000, 9990000)),
                  "Tipo_Contenedor": tipo_cont, "Congestión_Portuaria_%": round(congestion_port, 1), "Estado_Mar": estado_mar,
                  "Tiempo_Fondeo_h": round(fondeo, 1), "Disponibilidad_Grúas_%": round(gruas, 1)})
    if modo == "Fluvial":
        r.update({"Naviera": NAVIERAS_FLUVIALES[int(rng.integers(0, len(NAVIERAS_FLUVIALES)))], "Nivel_Río": nivel_rio})
    if modo == "Carretero":
        r.update({"GPS_Activo": "Sí" if rng.random() < .97 else "No",
                  "Horas_Conducción": round(min(drive, 10) if drive else 1, 1),
                  "Nivel_Combustible_%": round(clip(rng.normal(72, 18), 15, 100)), "Estado_Neumáticos": neum})
    if temp_reefer is not None:
        r["Temperatura_Reefer_C"] = round(temp_reefer, 1)
    return r


# ---------------------------------------------------------------------------- diccionario
def F(variable, tipo, unidad, fuente, desc, modelo=True):
    return {"variable": variable, "tipo": tipo, "unidad": unidad, "fuente": fuente, "desc": desc, "modelo": modelo}


INT = "Interno RANSA (simulado)"
DICTIONARY = [
    F("ID_Viaje", "Identificador", "Texto (código)", INT, "Identificador único del viaje/envío, formato RNS-AAAA-NNNNNN."),
    F("Fecha", "Numérica (fecha)", "AAAA-MM-DD", INT, "Fecha de despacho del viaje."),
    F("Día_Semana", "Categórica", "Texto", INT, "Día de la semana del despacho."),
    F("Mes", "Categórica", "Texto", INT, "Mes calendario del viaje."),
    F("Trimestre", "Ordinal", "Entero (1-4)", INT, "Trimestre del año calendario."),
    F("Año", "Numérica (discreta)", "Año (AAAA)", INT, "Año calendario del viaje (2023-2026)."),
    F("Departamento_Origen", "Categórica", "Texto", "INEI (división político-administrativa)", "Departamento/región del Perú donde se origina el viaje."),
    F("Ciudad_Origen", "Categórica", "Texto", "INEI (centros poblados)", "Ciudad, puerto o centro logístico de origen."),
    F("Departamento_Destino", "Categórica", "Texto", "INEI (división político-administrativa)", "Departamento/región de destino."),
    F("Ciudad_Destino", "Categórica", "Texto", "INEI (centros poblados)", "Ciudad, puerto o centro logístico de destino."),
    F("Corredor_Logístico", "Categórica", "Texto", "MTC – Plan de Desarrollo de Servicios Logísticos de Transporte", "Par origen-destino de la red logística."),
    F("Ruta_Principal", "Categórica", "Texto", "MTC / Provías Nacional (Red Vial Nacional, SINAC)", "Vía nacional o ruta principal recorrida (PE-1N, PE-22, IIRSA, cabotaje, fluvial...)."),
    F("Tipo_Transporte", "Categórica", "Texto", "MTC / APN / DICAPI / CORPAC", "Modo: Carretero, Marítimo (cabotaje), Fluvial o Aéreo."),
    F("Tipo_Vehículo", "Categórica", "Texto", "MTC – Reglamento Nacional de Vehículos / SUTRAN", "Configuración vehicular, buque, convoy fluvial o aeronave."),
    F("Tipo_Carga", "Categórica", "Texto", INT, "Naturaleza de la carga (seca, cadena de frío, concentrado, MATPEL, etc.)."),
    F("Sector_Cliente", "Categórica", "Texto", INT, "Sector económico del cliente."),
    F("Línea_Negocio", "Categórica", "Texto", "RANSA – líneas de negocio públicas (prensa 2023-2026)",
      "Línea de negocio RANSA que atiende el embarque: Distribución, Comercio Exterior, Logística de Frío, Minería y Energía o Automotriz."),
    F("Peso_Toneladas", "Numérica continua", "Toneladas", "MTC – pesos y medidas vehiculares", "Peso bruto de la carga transportada."),
    F("Volumen_m3", "Numérica continua", "m³", INT, "Volumen de la carga."),
    F("Distancia_Km", "Numérica continua", "Kilómetros", "OpenStreetMap / Provías Nacional", "Distancia recorrida por la ruta real."),
    F("Altitud_Max_Ruta_msnm", "Numérica continua", "m s. n. m.", "SRTM 90 m (NASA) / IGN", "Altitud máxima de la ruta (pasos andinos como Ticlio 4.818 m) o del aeropuerto más alto."),
    F("Tiempo_Programado_Horas", "Numérica continua", "Horas", "RANSA (tiempos de tránsito comprometidos)", "Tiempo de tránsito comprometido con el cliente."),
    F("Tiempo_Entrega_Real_Horas", "Numérica continua", "Horas", "Interno RANSA (simulado, TMS/GPS)", "Tiempo real de entrega puerta a puerta."),
    F("Velocidad_Promedio_Kmh", "Numérica continua", "km/h", "SUTRAN / GPS (simulado)", "Velocidad comercial promedio del viaje."),
    F("Tiempo_Espera_Horas", "Numérica continua", "Horas", "Interno RANSA (simulado, TMS/GPS)", "Tiempo en colas de muelle, garita o andén."),
    F("Consumo_Combustible_Galones", "Numérica continua", "Galones", "MINEM / OSINERGMIN (rendimientos de referencia)", "Combustible atribuible al envío."),
    F("Combustible_Unidad", "Categórica", "Texto", "RANSA – renovación de flota a GNL (ProActivo, nov-2025) / MTC",
      "Tecnología de la unidad: Diésel B5 Euro V o III/IV, GNL, GNV, fuelóleo marino, diésel marino o Turbo A-1."),
    F("Emisiones_CO2_kg", "Numérica continua", "kg CO₂", "MINAM – Huella de Carbono Perú / GHG Protocol (factores de emisión)",
      "Emisiones de CO₂ del viaje (consumo × factor de emisión del combustible)."),
    F("Costo_Transporte_PEN", "Numérica continua", "Soles (S/)", "Interno RANSA (simulado, tarifas por modo/vehículo/región)", "Costo de flete del envío."),
    F("Costo_Peajes_PEN", "Numérica continua", "Soles (S/)", "MTC / Provías Nacional y concesionarias viales", "Costo total de peajes del recorrido."),
    F("Disponibilidad_Flota_Pct", "Numérica continua", "%", "Interno RANSA (simulado, KPI de flota)", "Disponibilidad de la flota al despacho."),
    F("Utilización_Flota_Pct", "Numérica continua", "%", "Interno RANSA (simulado, KPI de flota)", "Utilización de la flota."),
    F("Estado_Vía", "Ordinal", "Texto", "Provías Nacional (estado de la Red Vial Nacional)", "Estado de la vía (Bueno, Regular, Malo, Crítico)."),
    F("Índice_Deterioro_Vial", "Numérica continua", "Índice 0-100", "Provías Nacional / MTC", "Deterioro de la vía (100 = peor)."),
    F("Número_Cierres_Viales", "Numérica discreta (conteo)", "Conteo", "SUTRAN / Provías (estado de tránsito en vías nacionales)", "Cierres viales reportados en el corredor."),
    F("Número_Bloqueos_Carretera", "Numérica discreta (conteo)", "Conteo", "PNP / SUTRAN", "Bloqueos de carretera reportados."),
    F("Índice_Bloqueos", "Numérica continua", "Índice 0-100", "PNP / Defensoría del Pueblo (conflictos sociales)", "Exposición a bloqueos en el corredor."),
    F("Obras_Viales_Activas", "Numérica discreta (conteo)", "Conteo", "Provías Nacional / MML", "Obras viales activas en el recorrido."),
    F("Restricciones_Peso", "Binaria", "0/1", "MTC – pesos y medidas", "Restricción de peso por puentes o tramos."),
    F("Restricciones_Horarias", "Binaria", "0/1", "MML / ATU (horarios de carga pesada en Lima)", "Restricción horaria para carga pesada."),
    F("Índice_Seguridad", "Numérica continua", "Índice 0-100", "PNP / INEI (victimización)", "Seguridad del corredor (100 = más seguro)."),
    F("Riesgo_Hurto_Carga", "Ordinal", "Texto", "PNP (denuncias por robo de carga)", "Riesgo de robo/hurto de carga."),
    F("Número_Eventos_Seguridad", "Numérica discreta (conteo)", "Conteo", "PNP", "Eventos de seguridad reportados en el corredor."),
    F("Presencia_Crimen_Organizado", "Binaria", "0/1", "PNP / Ministerio del Interior (extorsión al transporte)", "Extorsión o crimen organizado activo en la zona."),
    F("Índice_Orden_Público", "Numérica continua", "Índice 0-100", "Ministerio del Interior / PNP", "Orden público (100 = normalidad)."),
    F("Riesgo_Extorsión", "Ordinal", "Texto", "PNP / Ministerio del Interior", "Riesgo de extorsión a transportistas."),
    F("Riesgo_Vandalismo", "Ordinal", "Texto", "PNP", "Riesgo de vandalismo contra la unidad o la carga."),
    F("Riesgo_Saqueo", "Ordinal", "Texto", "PNP / INDECI", "Riesgo de saqueo (protestas o desastres)."),
    F("Número_Paros", "Numérica discreta (conteo)", "Conteo", "Defensoría del Pueblo (reporte de conflictos sociales)", "Paros regionales o gremiales activos."),
    F("Índice_Protestas", "Numérica continua", "Índice 0-100", "Defensoría del Pueblo", "Intensidad de la conflictividad social."),
    F("Manifestaciones", "Numérica discreta (conteo)", "Conteo", "PNP", "Manifestaciones públicas en el corredor."),
    F("Huelgas", "Binaria", "0/1", "MTPE / Defensoría del Pueblo", "Huelga activa que afecta la operación."),
    F("Bloqueos_Sociales", "Numérica discreta (conteo)", "Conteo", "Defensoría del Pueblo / PNP", "Bloqueos por conflictos sociales (comunidades, gremios)."),
    F("Temperatura_C", "Numérica continua", "°C", "SENAMHI", "Temperatura ambiente promedio del recorrido."),
    F("Precipitación_mm", "Numérica continua", "mm", "SENAMHI", "Precipitación acumulada esperada."),
    F("Humedad_Pct", "Numérica continua", "%", "SENAMHI", "Humedad relativa."),
    F("Velocidad_Viento_Kmh", "Numérica continua", "km/h", "SENAMHI", "Velocidad del viento."),
    F("Alerta_SENAMHI", "Ordinal", "Texto", "SENAMHI (avisos meteorológicos)", "Nivel de aviso: Ninguna, Amarilla, Naranja, Roja."),
    F("Fenómeno_Climático", "Categórica", "Texto", "ENFEN / SENAMHI", "Fenómeno climático dominante (Niño Costero, lluvias de sierra, heladas, friaje, oleajes...)."),
    F("Número_Inundaciones", "Numérica discreta (conteo)", "Conteo", "INDECI (SINPAD)", "Inundaciones reportadas."),
    F("Índice_Inundaciones", "Numérica continua", "Índice 0-100", "INDECI / CENEPRED", "Exposición a inundaciones."),
    F("Número_Deslizamientos", "Numérica discreta (conteo)", "Conteo", "INDECI (SINPAD)", "Huaicos y deslizamientos reportados."),
    F("Índice_Deslizamientos", "Numérica continua", "Índice 0-100", "INGEMMET / CENEPRED", "Exposición a huaicos y deslizamientos."),
    F("Número_Derrumbes", "Numérica discreta (conteo)", "Conteo", "Provías Nacional / INDECI", "Derrumbes en la vía."),
    F("Índice_Derrumbes", "Numérica continua", "Índice 0-100", "INGEMMET / Provías Nacional", "Exposición a derrumbes."),
    F("Número_Incendios_Forestales", "Numérica discreta (conteo)", "Conteo", "SERFOR / INDECI", "Incendios forestales cercanos a la ruta."),
    F("Índice_Incendios", "Numérica continua", "Índice 0-100", "SERFOR / SENAMHI", "Exposición a incendios forestales."),
    F("Riesgo_Geológico", "Ordinal", "Texto", "INGEMMET", "Riesgo geológico del corredor."),
    F("Riesgo_Hidrológico", "Ordinal", "Texto", "ANA / SENAMHI", "Riesgo hidrológico del corredor."),
    F("Número_Accidentes", "Numérica discreta (conteo)", "Conteo", "SUTRAN / PNP", "Accidentes de tránsito durante el viaje."),
    F("Intensidad_Incidente", "Ordinal", "Texto", "SUTRAN / PNP", "Gravedad del incidente."),
    F("Duración_Incidente_Horas", "Numérica continua", "Horas", "SUTRAN / PNP", "Duración del incidente."),
    F("Tiempo_Cierre_Vía_Horas", "Numérica continua", "Horas", "SUTRAN / Provías Nacional", "Horas de vía cerrada sufridas por el viaje."),
    F("Precio_Diésel_PEN_Gal", "Numérica continua", "S/ por galón", "OSINERGMIN (Facilito) – referencial", "Precio del diésel B5 en la región."),
    F("Precio_Gasolina_PEN_Gal", "Numérica continua", "S/ por galón", "OSINERGMIN (Facilito) – referencial", "Precio del gasohol 90."),
    F("IPC", "Numérica continua", "Índice (dic-2021 = 100)", "INEI – referencial", "Índice de precios al consumidor (Lima Metropolitana)."),
    F("Tipo_Cambio_PEN_USD", "Numérica continua", "S/ por US$", "BCRP – referencial", "Tipo de cambio."),
    F("Inflación_Pct", "Numérica continua", "% anual", "INEI / BCRP – referencial", "Inflación interanual."),
    F("Precio_Peajes_Promedio_PEN", "Numérica continua", "Soles (S/)", "MTC / Provías Nacional y concesiones", "Tarifa promedio por peaje para la categoría del vehículo."),
    F("Índice_Abastecimiento", "Numérica continua", "Índice 0-100", "MIDAGRI / Interno RANSA (simulado)", "Nivel de abastecimiento del canal."),
    F("Nivel_Inventario_Pct", "Numérica continua", "%", INT, "Nivel de inventario del cliente al despacho."),
    F("Demanda_Unidades", "Numérica continua", "Unidades", INT, "Demanda real del periodo."),
    F("Demanda_Pronosticada_Unidades", "Numérica continua", "Unidades", INT, "Demanda pronosticada."),
    F("Prioridad_Cliente", "Ordinal", "Texto", "Interno RANSA (segmentación comercial)", "Prioridad comercial del cliente."),
    F("OTIF", "Binaria", "0/1", "Interno RANSA (KPI On Time In Full)", "1 = llegó a tiempo y completo."),
    F("Fill_Rate_Pct", "Numérica continua", "%", "Interno RANSA (KPI de completitud)", "Porcentaje del pedido efectivamente entregado."),
    F("Nivel_Servicio_Pct", "Numérica continua", "%", "Interno RANSA (KPI compuesto)", "Nivel de servicio compuesto."),
    F("Tiempo_Almacenamiento_Horas", "Numérica continua", "Horas", "Interno RANSA (almacenes, simulado)", "Tiempo de permanencia en almacén."),
    F("Cross_Docking", "Binaria", "0/1", "Interno RANSA", "Operación con cross-docking."),
    F("Tipo_Almacén", "Categórica", "Texto", "Interno RANSA (almacenes, simulado)", "Tipo de almacén (seco, refrigerado, congelado, MATPEL, aduanero...)."),
    F("Capacidad_Almacén_m3", "Numérica continua", "m³", "Interno RANSA (simulado)", "Capacidad del almacén asociado."),
    F("Utilización_Almacén_Pct", "Numérica continua", "%", "Interno RANSA (KPI de almacén)", "Ocupación del almacén."),
    F("Aseguradora", "Categórica", "Texto", "Mercado asegurador peruano (supuesto de mercado; no es fuente oficial)", "Compañía de seguros de la carga."),
    F("Tipo_Cobertura_Seguro", "Ordinal", "Texto", "Supuesto de mercado (SBS – pólizas de transporte)", "Tipo de cobertura."),
    F("Valor_Asegurado_PEN", "Numérica continua", "Soles (S/)", "Supuesto de mercado, derivado de peso y tipo de carga", "Valor asegurado de la carga."),
    F("Prima_Seguro_PEN", "Numérica continua", "Soles (S/)", "Supuesto de mercado", "Prima del seguro del envío."),
    F("Deducible_PEN", "Numérica continua", "Soles (S/)", "Supuesto de mercado", "Deducible aplicable."),
    F("Siniestro", "Binaria", "0/1", "Supuesto de mercado, ligado a seguridad, accidentes y cadena de frío", "1 = hubo siniestro."),
    F("Valor_Siniestro_PEN", "Numérica continua", "Soles (S/)", "Supuesto de mercado", "Monto del siniestro."),
    F("Estado_Reclamación", "Categórica", "Texto", "Supuesto de mercado", "Estado del reclamo al seguro."),
    F("LeadTime_Real_Dias", "Numérica continua (variable objetivo)", "Días", "Interno RANSA (KPI Lead Time)", "Lead time real del envío en días."),
    # ---- complementarias multimodales (CSV), no se cargan como columnas de la BD
    F("Aeropuerto_Origen", "Categórica", "Texto", "CORPAC / MTC", "Aeropuerto de origen (solo aéreo).", False),
    F("Aeropuerto_Destino", "Categórica", "Texto", "CORPAC / MTC", "Aeropuerto de destino (solo aéreo).", False),
    F("Aerolínea", "Categórica", "Texto", "MTC – DGAC", "Aerolínea o operador de carga.", False),
    F("Número_Vuelo", "Identificador", "Texto", INT, "Código de vuelo (simulado).", False),
    F("Tipo_Aeronave", "Categórica", "Texto", "MTC – DGAC", "Tipo de aeronave.", False),
    F("Capacidad_Bodega_%", "Numérica continua", "%", INT, "Ocupación de la bodega del avión.", False),
    F("Retraso_Vuelo_min", "Numérica continua", "Minutos", "CORPAC (simulado)", "Retraso del vuelo.", False),
    F("Cancelación_Vuelo", "Binaria", "0/1", "CORPAC (simulado)", "Vuelo cancelado.", False),
    F("Congestión_Aeroportuaria_%", "Numérica continua", "%", "LAP / CORPAC (simulado)", "Congestión del terminal de carga.", False),
    F("Puerto_Origen", "Categórica", "Texto", "APN (Autoridad Portuaria Nacional)", "Terminal portuario/fluvial de origen.", False),
    F("Puerto_Destino", "Categórica", "Texto", "APN", "Terminal portuario/fluvial de destino.", False),
    F("Naviera", "Categórica", "Texto", "APN / DICAPI", "Naviera o empresa fluvial.", False),
    F("IMO_Buque", "Identificador", "Número IMO", "OMI (simulado)", "Número IMO del buque.", False),
    F("Tipo_Contenedor", "Categórica", "Texto", "APN", "Tipo de contenedor o granel.", False),
    F("Congestión_Portuaria_%", "Numérica continua", "%", "APN (simulado)", "Congestión del terminal portuario.", False),
    F("Estado_Mar", "Categórica", "Texto", "DHN – Marina de Guerra del Perú (avisos de oleaje)", "Estado del mar / oleaje anómalo.", False),
    F("Tiempo_Fondeo_h", "Numérica continua", "Horas", "APN (simulado)", "Tiempo de espera en fondeadero.", False),
    F("Disponibilidad_Grúas_%", "Numérica continua", "%", "APN (simulado)", "Disponibilidad de grúas de muelle.", False),
    F("Nivel_Río", "Categórica", "Texto", "SENAMHI – Hidrología / DHN", "Nivel del río (Normal, Creciente, Vaciante, Vaciante extrema).", False),
    F("GPS_Activo", "Categórica", "Sí/No", "SUTRAN (GPS obligatorio)", "Unidad con GPS reportando.", False),
    F("Horas_Conducción", "Numérica continua", "Horas", "SUTRAN (jornada de conducción)", "Horas continuas de conducción.", False),
    F("Nivel_Combustible_%", "Numérica continua", "%", "Telemetría (simulado)", "Nivel de combustible al despacho.", False),
    F("Estado_Neumáticos", "Categórica", "Texto", "Inspección pre-viaje (simulado)", "Estado de neumáticos.", False),
    F("Temperatura_Reefer_C", "Numérica continua", "°C", "Telemetría de cadena de frío (simulado)", "Temperatura de la unidad refrigerada.", False),
]


if __name__ == "__main__":
    main()
