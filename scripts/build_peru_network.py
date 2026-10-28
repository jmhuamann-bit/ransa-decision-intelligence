"""
Construye la RED LOGÍSTICA DE PERÚ que usan el Gemelo Digital, el motor de operación en
vivo y el generador del dataset simulado.

Qué hace:
  1. Define los nodos reales de la red (CDs, puertos, aeropuertos, puertos fluviales y
     puntos críticos) con coordenadas de dominio público.
  2. Traza cada corredor carretero sobre la RED VIAL REAL (OSRM / OpenStreetMap), forzando
     los puntos de paso que definen la vía nacional (Panamericana, Carretera Central,
     IIRSA Norte, Interoceánica Sur, Corredor Minero Sur...).
  3. Muestrea el PERFIL DE ALTITUD de cada ruta (SRTM 90 m vía OpenTopoData), clave en Perú:
     un mismo corredor puede pasar del nivel del mar a 4.818 m (Abra Anticona / Ticlio).
  4. Genera las rutas de cabotaje (offshore), fluviales (Huallaga–Marañón–Amazonas y
     Ucayali–Amazonas) y aéreas.

Salida: data/peru_network.json (versionado en el repo: la app NO necesita internet para
funcionar, salvo las teselas del mapa).

Ejecutar (requiere internet, ~3 min):  python scripts/build_peru_network.py
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(BASE_DIR, "data", "peru_network.json")
CACHE_DIR = os.path.join(BASE_DIR, "scripts", ".cache")

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
ELEV_URL = "https://api.opentopodata.org/v1/srtm90m?locations="
USER_AGENT = "ransa-decision-intelligence/1.0 (network builder)"

# --------------------------------------------------------------------------- NODOS
# roles: cd (centro de distribución / ciudad), puerto, aeropuerto, fluvial, hub
NODES = {
    "Lima": {"dep": "Lima", "lat": -12.0464, "lon": -77.0428, "roles": ["cd", "hub"], "iata": None},
    "Callao": {"dep": "Callao", "lat": -12.0500, "lon": -77.1300, "roles": ["cd", "puerto", "aeropuerto", "hub"], "iata": "LIM",
               "puerto": {"lat": -12.0480, "lon": -77.1520}, "aero": {"lat": -12.0219, "lon": -77.1143}},
    "Lurín": {"dep": "Lima", "lat": -12.2746, "lon": -76.8706, "roles": ["cd"]},
    "Chancay": {"dep": "Lima", "lat": -11.5800, "lon": -77.2650, "roles": ["puerto"], "puerto": {"lat": -11.5870, "lon": -77.2780}},
    "Trujillo": {"dep": "La Libertad", "lat": -8.1116, "lon": -79.0287, "roles": ["cd", "aeropuerto"], "iata": "TRU",
                 "aero": {"lat": -8.0814, "lon": -79.1088}},
    "Salaverry": {"dep": "La Libertad", "lat": -8.2236, "lon": -78.9776, "roles": ["puerto"], "puerto": {"lat": -8.2230, "lon": -78.9890}},
    "Chimbote": {"dep": "Áncash", "lat": -9.0745, "lon": -78.5936, "roles": ["cd"]},
    "Huaraz": {"dep": "Áncash", "lat": -9.5278, "lon": -77.5278, "roles": ["cd"]},
    "Chiclayo": {"dep": "Lambayeque", "lat": -6.7714, "lon": -79.8409, "roles": ["cd", "aeropuerto"], "iata": "CIX",
                 "aero": {"lat": -6.7875, "lon": -79.8281}},
    "Piura": {"dep": "Piura", "lat": -5.1945, "lon": -80.6328, "roles": ["cd", "aeropuerto"], "iata": "PIU",
              "aero": {"lat": -5.2058, "lon": -80.6164}},
    "Paita": {"dep": "Piura", "lat": -5.0892, "lon": -81.1144, "roles": ["puerto"], "puerto": {"lat": -5.0790, "lon": -81.1100}},
    "Tumbes": {"dep": "Tumbes", "lat": -3.5669, "lon": -80.4515, "roles": ["cd"]},
    "Cajamarca": {"dep": "Cajamarca", "lat": -7.1617, "lon": -78.5128, "roles": ["cd"]},
    "Tarapoto": {"dep": "San Martín", "lat": -6.4825, "lon": -76.3652, "roles": ["cd", "aeropuerto"], "iata": "TPP",
                 "aero": {"lat": -6.5086, "lon": -76.3732}},
    "Yurimaguas": {"dep": "Loreto", "lat": -5.8964, "lon": -76.1086, "roles": ["fluvial"], "puerto": {"lat": -5.9020, "lon": -76.0930}},
    "Iquitos": {"dep": "Loreto", "lat": -3.7437, "lon": -73.2516, "roles": ["cd", "fluvial", "aeropuerto"], "iata": "IQT",
                "aero": {"lat": -3.7847, "lon": -73.3088}, "puerto": {"lat": -3.7300, "lon": -73.2380}},
    "Pucallpa": {"dep": "Ucayali", "lat": -8.3791, "lon": -74.5539, "roles": ["cd", "fluvial", "aeropuerto"], "iata": "PCL",
                 "aero": {"lat": -8.3779, "lon": -74.5743}, "puerto": {"lat": -8.3790, "lon": -74.5330}},
    "Huancayo": {"dep": "Junín", "lat": -12.0651, "lon": -75.2049, "roles": ["cd"]},
    "Cerro de Pasco": {"dep": "Pasco", "lat": -10.6864, "lon": -76.2625, "roles": ["cd"]},
    "Huánuco": {"dep": "Huánuco", "lat": -9.9306, "lon": -76.2422, "roles": ["cd"]},
    "Ayacucho": {"dep": "Ayacucho", "lat": -13.1588, "lon": -74.2239, "roles": ["cd"]},
    "Ica": {"dep": "Ica", "lat": -14.0678, "lon": -75.7286, "roles": ["cd"]},
    "Pisco": {"dep": "Ica", "lat": -13.7103, "lon": -76.2054, "roles": ["cd"]},
    "Arequipa": {"dep": "Arequipa", "lat": -16.4090, "lon": -71.5375, "roles": ["cd", "aeropuerto", "hub"], "iata": "AQP",
                 "aero": {"lat": -16.3411, "lon": -71.5830}},
    "Matarani": {"dep": "Arequipa", "lat": -16.9970, "lon": -72.1060, "roles": ["puerto"], "puerto": {"lat": -17.0000, "lon": -72.1130}},
    "Moquegua": {"dep": "Moquegua", "lat": -17.1956, "lon": -70.9353, "roles": ["cd"]},
    "Ilo": {"dep": "Moquegua", "lat": -17.6394, "lon": -71.3375, "roles": ["puerto"], "puerto": {"lat": -17.6430, "lon": -71.3500}},
    "Tacna": {"dep": "Tacna", "lat": -18.0066, "lon": -70.2463, "roles": ["cd", "aeropuerto"], "iata": "TCQ",
              "aero": {"lat": -18.0533, "lon": -70.2758}},
    "Juliaca": {"dep": "Puno", "lat": -15.5000, "lon": -70.1333, "roles": ["cd", "aeropuerto"], "iata": "JUL",
                "aero": {"lat": -15.4671, "lon": -70.1582}},
    "Puno": {"dep": "Puno", "lat": -15.8402, "lon": -70.0219, "roles": ["cd"]},
    "Cusco": {"dep": "Cusco", "lat": -13.5319, "lon": -71.9675, "roles": ["cd", "aeropuerto"], "iata": "CUZ",
              "aero": {"lat": -13.5357, "lon": -71.9388}},
    "Challhuahuacho": {"dep": "Apurímac", "lat": -14.1186, "lon": -72.2489, "roles": ["cd"]},
    "Puerto Maldonado": {"dep": "Madre de Dios", "lat": -12.5933, "lon": -69.1891, "roles": ["cd", "aeropuerto"], "iata": "PEM",
                         "aero": {"lat": -12.6136, "lon": -69.2286}},
}

# Puntos de paso de las vías nacionales (para forzar el trazo real de cada corredor)
W = {
    "Ticlio": (-11.5953, -76.1956), "La Oroya": (-11.5186, -75.8997), "Pativilca": (-10.6966, -77.7811),
    "Conococha": (-10.1300, -77.2800), "Chilete": (-7.2220, -78.8400), "Nazca": (-14.8309, -74.9389),
    "Camaná": (-16.6243, -72.7110), "Puquio": (-14.6939, -74.1247), "Abancay": (-13.6339, -72.8814),
    "Sicuani": (-14.2694, -71.2261), "Espinar": (-14.7914, -71.4103), "Urcos": (-13.6889, -71.6253),
    "Quincemil": (-13.2333, -70.7500), "Olmos": (-5.9850, -79.7470), "Bagua Grande": (-5.7569, -78.4417),
    "Pedro Ruiz": (-5.9419, -77.9806), "Moyobamba": (-6.0346, -76.9717), "Sullana": (-4.9039, -80.6853),
    "Talara": (-4.5772, -81.2719), "Máncora": (-4.1069, -81.0475), "Tingo María": (-9.2950, -75.9970),
    "Huaytará": (-13.6039, -75.3533), "Cañete": (-13.0775, -76.3881), "Lunahuaná": (-12.9606, -76.1394),
    "Chupaca": (-12.0617, -75.2875), "Canta": (-11.4670, -76.6240), "Huayllay": (-11.0039, -76.3653),
    "Ate": (-12.0275, -76.9200), "Surco": (-12.1450, -76.9917), "Miraflores": (-12.1211, -77.0297),
    "San Isidro": (-12.0970, -77.0365), "Los Olivos": (-11.9919, -77.0700), "SJL": (-11.9780, -77.0010),
    "Moquegua": (-17.1956, -70.9353), "Juliaca": (-15.5000, -70.1333), "Arequipa": (-16.4090, -71.5375),
    "Cusco": (-13.5319, -71.9675), "Trujillo": (-8.1116, -79.0287), "Chiclayo": (-6.7714, -79.8409),
    "Piura": (-5.1945, -80.6328), "Cerro de Pasco": (-10.6864, -76.2625), "Huánuco": (-9.9306, -76.2422),
}

# --------------------------------------------------------------------------- CORREDORES
# (corredor, origen, destino, ruta_principal, puntos_de_paso, alterna_de)
ROAD = [
    ("Callao - Lima", "Callao", "Lima", "Av. Néstor Gambetta / Vía Expresa", [], None),
    ("Callao - Lurín", "Callao", "Lurín", "Vía de Evitamiento / Panamericana Sur", [], None),
    ("Lima - Lima", "Lima", "Lima", "Distribución urbana Lima Metropolitana",
     ["Ate", "SJL", "Los Olivos", "San Isidro", "Miraflores", "Surco"], None),
    ("Chancay - Lima", "Chancay", "Lima", "Panamericana Norte (PE-1N) / Variante de Pasamayo", [], None),
    ("Chancay - Callao", "Chancay", "Callao", "Panamericana Norte (PE-1N) / Av. Néstor Gambetta", [], None),
    ("Lima - Trujillo", "Lima", "Trujillo", "Panamericana Norte (PE-1N)", [], None),
    ("Lima - Chimbote", "Lima", "Chimbote", "Panamericana Norte (PE-1N)", [], None),
    ("Lima - Chiclayo", "Lima", "Chiclayo", "Panamericana Norte (PE-1N)", ["Trujillo"], None),
    ("Lima - Piura", "Lima", "Piura", "Panamericana Norte (PE-1N)", ["Trujillo", "Chiclayo"], None),
    ("Lima - Tumbes", "Lima", "Tumbes", "Panamericana Norte (PE-1N)", ["Trujillo", "Chiclayo", "Piura", "Sullana", "Talara", "Máncora"], None),
    ("Lima - Huaraz", "Lima", "Huaraz", "Panamericana Norte / Pativilca–Huaraz (PE-16)", ["Pativilca", "Conococha"], None),
    ("Lima - Cajamarca", "Lima", "Cajamarca", "Panamericana Norte / Ciudad de Dios–Cajamarca (PE-08)", ["Trujillo", "Chilete"], None),
    ("Trujillo - Callao", "Trujillo", "Callao", "Panamericana Norte (PE-1N)", [], None),
    ("Trujillo - Chiclayo", "Trujillo", "Chiclayo", "Panamericana Norte (PE-1N)", [], None),
    ("Chiclayo - Piura", "Chiclayo", "Piura", "Panamericana Norte (PE-1N)", [], None),
    ("Piura - Paita", "Piura", "Paita", "IIRSA Norte (PE-02)", [], None),
    ("Paita - Piura", "Paita", "Piura", "IIRSA Norte (PE-02)", [], None),
    ("Piura - Tumbes", "Piura", "Tumbes", "Panamericana Norte (PE-1N)", ["Sullana", "Talara", "Máncora"], None),
    ("Chiclayo - Tarapoto", "Chiclayo", "Tarapoto", "IIRSA Norte / Fernando Belaúnde (PE-5N)",
     ["Olmos", "Bagua Grande", "Pedro Ruiz", "Moyobamba"], None),
    ("Paita - Tarapoto", "Paita", "Tarapoto", "IIRSA Norte (PE-02 / PE-5N)",
     ["Piura", "Olmos", "Bagua Grande", "Pedro Ruiz", "Moyobamba"], None),
    ("Tarapoto - Yurimaguas", "Tarapoto", "Yurimaguas", "IIRSA Norte (PE-5N)", [], None),
    ("Lima - Huancayo", "Lima", "Huancayo", "Carretera Central (PE-22)", ["Ticlio", "La Oroya"], None),
    ("Lima - Cerro de Pasco", "Lima", "Cerro de Pasco", "Carretera Central (PE-22) / PE-3N", ["Ticlio", "La Oroya"], None),
    ("Lima - Huánuco", "Lima", "Huánuco", "Carretera Central (PE-22) / PE-3N", ["Ticlio", "La Oroya", "Cerro de Pasco"], None),
    ("Lima - Pucallpa", "Lima", "Pucallpa", "Carretera Central / Federico Basadre (PE-18C)",
     ["Ticlio", "La Oroya", "Cerro de Pasco", "Huánuco", "Tingo María"], None),
    ("Lima - Ayacucho", "Lima", "Ayacucho", "Vía Los Libertadores (PE-28A)", ["Huaytará"], None),
    ("Lima - Ica", "Lima", "Ica", "Panamericana Sur (PE-1S)", [], None),
    ("Ica - Callao", "Ica", "Callao", "Panamericana Sur (PE-1S)", [], None),
    ("Lima - Pisco", "Lima", "Pisco", "Panamericana Sur (PE-1S)", [], None),
    ("Lima - Arequipa", "Lima", "Arequipa", "Panamericana Sur (PE-1S)", ["Nazca", "Camaná"], None),
    ("Lima - Tacna", "Lima", "Tacna", "Panamericana Sur (PE-1S)", ["Nazca", "Camaná", "Moquegua"], None),
    ("Lima - Cusco", "Lima", "Cusco", "Panamericana Sur / Nazca–Abancay (PE-30A)", ["Nazca", "Puquio", "Abancay"], None),
    ("Arequipa - Juliaca", "Arequipa", "Juliaca", "Arequipa–Juliaca (PE-34A)", [], None),
    ("Arequipa - Puno", "Arequipa", "Puno", "Arequipa–Juliaca–Puno (PE-34A / PE-3S)", ["Juliaca"], None),
    ("Arequipa - Cusco", "Arequipa", "Cusco", "PE-34A / Longitudinal de la Sierra Sur (PE-3S)", ["Juliaca", "Sicuani"], None),
    ("Juliaca - Cusco", "Juliaca", "Cusco", "Longitudinal de la Sierra Sur (PE-3S)", ["Sicuani"], None),
    ("Matarani - Arequipa", "Matarani", "Arequipa", "Panamericana Sur / PE-34A", [], None),
    ("Arequipa - Matarani", "Arequipa", "Matarani", "Panamericana Sur / PE-34A", [], None),
    ("Challhuahuacho - Matarani", "Challhuahuacho", "Matarani", "Corredor Minero Sur (PE-3SG / PE-34A)", ["Espinar", "Arequipa"], None),
    ("Cusco - Puerto Maldonado", "Cusco", "Puerto Maldonado", "Interoceánica Sur (PE-30C)", ["Urcos", "Quincemil"], None),
    ("Tacna - Arequipa", "Tacna", "Arequipa", "Panamericana Sur (PE-1S)", ["Moquegua"], None),
    ("Ilo - Moquegua", "Ilo", "Moquegua", "Costanera / Ilo–Moquegua (PE-36)", [], None),
    # ---- rutas alternas (se usan cuando el gemelo digital desvía la flota) ----
    ("Lima - Huancayo", "Lima", "Huancayo", "Alterna Cañete–Lunahuaná–Yauyos (PE-24)", ["Cañete", "Lunahuaná", "Chupaca"], "Lima - Huancayo"),
    ("Lima - Cerro de Pasco", "Lima", "Cerro de Pasco", "Alterna Canta–Huayllay (PE-20A)", ["Canta", "Huayllay"], "Lima - Cerro de Pasco"),
    ("Lima - Huánuco", "Lima", "Huánuco", "Alterna Canta–Huayllay (PE-20A)", ["Canta", "Huayllay", "Cerro de Pasco"], "Lima - Huánuco"),
    ("Lima - Pucallpa", "Lima", "Pucallpa", "Alterna Canta–Huayllay (PE-20A)",
     ["Canta", "Huayllay", "Cerro de Pasco", "Huánuco", "Tingo María"], "Lima - Pucallpa"),
    ("Lima - Cusco", "Lima", "Cusco", "Alterna Arequipa–Juliaca–Sicuani", ["Nazca", "Camaná", "Arequipa", "Juliaca", "Sicuani"], "Lima - Cusco"),
    ("Challhuahuacho - Matarani", "Challhuahuacho", "Matarani", "Alterna vía Cusco–Juliaca", ["Cusco", "Sicuani", "Juliaca", "Arequipa"],
     "Challhuahuacho - Matarani"),
]

# Cabotaje: puntos offshore (lat, lon) que siguen la costa peruana mar adentro
SEA_NORTH = [(-12.00, -77.32), (-11.60, -77.48), (-11.10, -77.78), (-10.75, -77.98), (-10.10, -78.38), (-9.10, -78.80),
             (-8.25, -79.20), (-7.40, -79.78), (-6.80, -80.15), (-6.10, -80.95), (-5.40, -81.35), (-5.12, -81.24)]
SEA_SOUTH = [(-12.10, -77.30), (-12.50, -76.98), (-13.10, -76.58), (-13.85, -76.42), (-14.60, -76.05), (-15.35, -75.35),
             (-15.90, -74.45), (-16.35, -73.55), (-16.80, -72.85), (-17.10, -72.25)]
SEA_ILO = [(-17.25, -71.95), (-17.60, -71.48)]

SEA = [
    ("Callao - Paita", "Callao", "Paita", "Cabotaje Pacífico Norte", "N"),
    ("Paita - Callao", "Paita", "Callao", "Cabotaje Pacífico Norte", "N-"),
    ("Callao - Salaverry", "Callao", "Salaverry", "Cabotaje Pacífico Norte", "N:Salaverry"),
    ("Chancay - Paita", "Chancay", "Paita", "Cabotaje Pacífico Norte", "N"),
    ("Callao - Matarani", "Callao", "Matarani", "Cabotaje Pacífico Sur", "S"),
    ("Matarani - Callao", "Matarani", "Callao", "Cabotaje Pacífico Sur", "S-"),
    ("Callao - Ilo", "Callao", "Ilo", "Cabotaje Pacífico Sur", "S:Ilo"),
    ("Chancay - Matarani", "Chancay", "Matarani", "Cabotaje Pacífico Sur", "S"),
]

RIVER = [
    ("Yurimaguas - Iquitos", "Yurimaguas", "Iquitos", "Fluvial Huallaga–Marañón–Amazonas",
     [(-5.902, -76.093), (-5.62, -75.93), (-5.23, -75.68), (-5.07, -75.58), (-4.95, -75.22), (-4.78, -74.88), (-4.62, -74.45),
      (-4.55, -74.02), (-4.50, -73.60), (-4.25, -73.45), (-3.98, -73.36), (-3.73, -73.238)], 640),
    ("Pucallpa - Iquitos", "Pucallpa", "Iquitos", "Fluvial Ucayali–Amazonas",
     [(-8.379, -74.533), (-7.95, -74.85), (-7.33, -75.01), (-6.90, -75.15), (-6.45, -75.00), (-5.95, -74.70), (-5.50, -74.20),
      (-5.06, -73.85), (-4.90, -73.67), (-4.51, -73.58), (-4.10, -73.42), (-3.73, -73.238)], 1010),
]

AIR = [
    ("Lima - Iquitos", "Callao", "Iquitos"), ("Lima - Cusco", "Callao", "Cusco"), ("Lima - Arequipa", "Callao", "Arequipa"),
    ("Lima - Piura", "Callao", "Piura"), ("Lima - Tarapoto", "Callao", "Tarapoto"), ("Lima - Pucallpa", "Callao", "Pucallpa"),
    ("Lima - Juliaca", "Callao", "Juliaca"), ("Lima - Tacna", "Callao", "Tacna"), ("Lima - Puerto Maldonado", "Callao", "Puerto Maldonado"),
    ("Lima - Trujillo", "Callao", "Trujillo"),
]

# Puntos críticos reales de la red (para eventos del gemelo digital y capas de riesgo)
HOTSPOTS = [
    {"id": "chosica", "nombre": "Chosica (Carretera Central Km 34)", "lat": -11.9375, "lon": -76.6972, "riesgo": "geologico",
     "descripcion": "Quebradas activas: huaicos recurrentes en temporada de lluvias (dic–mar)."},
    {"id": "matucana", "nombre": "Matucana (Carretera Central Km 75)", "lat": -11.8436, "lon": -76.3850, "riesgo": "geologico",
     "descripcion": "Derrumbes y caída de rocas en la quebrada del Rímac."},
    {"id": "ticlio", "nombre": "Ticlio – Abra Anticona (4.818 m)", "lat": -11.5953, "lon": -76.1956, "riesgo": "climatico",
     "descripcion": "Paso de alta montaña: nevadas, granizo y heladas (jun–ago)."},
    {"id": "pasamayo", "nombre": "Serpentín de Pasamayo", "lat": -11.6990, "lon": -77.2120, "riesgo": "accidentalidad",
     "descripcion": "Neblina costera y alta accidentalidad en el acceso norte de Lima."},
    {"id": "lima_norte", "nombre": "Lima Norte – Puente Piedra", "lat": -11.8670, "lon": -77.0750, "riesgo": "seguridad",
     "descripcion": "Extorsión a transportistas y robo de carga en accesos a Lima."},
    {"id": "callao_gambetta", "nombre": "Callao – Av. Néstor Gambetta", "lat": -12.0150, "lon": -77.1200, "riesgo": "infraestructura",
     "descripcion": "Congestión de acceso al terminal portuario y restricciones horarias."},
    {"id": "ica_pan_sur", "nombre": "Ica – Panamericana Sur", "lat": -14.0678, "lon": -75.7286, "riesgo": "social",
     "descripcion": "Paros agrarios y bloqueos de la Panamericana Sur."},
    {"id": "chala_atico", "nombre": "Chala – Atico (PE-1S)", "lat": -16.2100, "lon": -73.6200, "riesgo": "geologico",
     "descripcion": "Derrumbes en acantilados costeros de la Panamericana Sur."},
    {"id": "corredor_minero", "nombre": "Corredor Minero Sur – Espinar", "lat": -14.7914, "lon": -71.4103, "riesgo": "social",
     "descripcion": "Bloqueos comunales recurrentes en el corredor de concentrados."},
    {"id": "juliaca", "nombre": "Juliaca – Altiplano", "lat": -15.5000, "lon": -70.1333, "riesgo": "social",
     "descripcion": "Paros regionales y bloqueos (crisis social dic 2022 – mar 2023)."},
    {"id": "crucero_alto", "nombre": "Crucero Alto (4.528 m, PE-34A)", "lat": -15.7700, "lon": -70.9200, "riesgo": "climatico",
     "descripcion": "Heladas y nevadas en el tramo Arequipa–Juliaca."},
    {"id": "la_raya", "nombre": "Abra La Raya (4.335 m)", "lat": -14.4833, "lon": -70.9833, "riesgo": "climatico",
     "descripcion": "Nevadas en el límite Cusco–Puno."},
    {"id": "marcapata", "nombre": "Interoceánica – Marcapata", "lat": -13.5000, "lon": -70.9700, "riesgo": "geologico",
     "descripcion": "Huaicos y deslizamientos en la ceja de selva."},
    {"id": "piura_rio", "nombre": "Piura – Río Piura", "lat": -5.1800, "lon": -80.6300, "riesgo": "hidrologico",
     "descripcion": "Desbordes del río Piura durante El Niño Costero (2017, 2023)."},
    {"id": "morrope", "nombre": "Lambayeque – Mórrope", "lat": -6.5400, "lon": -80.0100, "riesgo": "hidrologico",
     "descripcion": "Inundaciones de la Panamericana Norte antigua."},
    {"id": "olmos", "nombre": "Olmos – IIRSA Norte", "lat": -5.9850, "lon": -79.7470, "riesgo": "seguridad",
     "descripcion": "Robo de carga en tramos despoblados."},
    {"id": "carpish", "nombre": "Túnel de Carpish (Huánuco)", "lat": -9.6800, "lon": -76.0800, "riesgo": "geologico",
     "descripcion": "Derrumbes en la ceja de selva central."},
    {"id": "conococha", "nombre": "Conococha (4.100 m)", "lat": -10.1300, "lon": -77.2800, "riesgo": "climatico",
     "descripcion": "Heladas y granizo en el acceso a Huaraz."},
    {"id": "trujillo", "nombre": "Trujillo", "lat": -8.1116, "lon": -79.0287, "riesgo": "seguridad",
     "descripcion": "Extorsión al transporte de carga."},
    {"id": "amazonas_vaciante", "nombre": "Marañón – Parinari", "lat": -4.6200, "lon": -74.4500, "riesgo": "hidrologico",
     "descripcion": "Vaciante del río (ago–oct): restricciones de calado para chatas."},
    {"id": "ucayali_vaciante", "nombre": "Ucayali – Orellana", "lat": -6.9000, "lon": -75.1500, "riesgo": "hidrologico",
     "descripcion": "Estiaje del Ucayali: navegación restringida."},
    {"id": "puerto_callao", "nombre": "Terminal Portuario del Callao", "lat": -12.0480, "lon": -77.1520, "riesgo": "puerto",
     "descripcion": "Oleajes anómalos (avisos DHN) y congestión de muelles."},
    {"id": "puerto_chancay", "nombre": "Puerto de Chancay", "lat": -11.5870, "lon": -77.2780, "riesgo": "puerto",
     "descripcion": "Megapuerto multipropósito (inicio de operaciones: nov 2024)."},
    {"id": "puerto_paita", "nombre": "Puerto de Paita", "lat": -5.0790, "lon": -81.1100, "riesgo": "puerto",
     "descripcion": "Oleajes anómalos y picos de agroexportación."},
    {"id": "puerto_matarani", "nombre": "Puerto de Matarani", "lat": -17.0000, "lon": -72.1130, "riesgo": "puerto",
     "descripcion": "Concentrados mineros del sur; cierres por oleaje."},
]


# --------------------------------------------------------------------------- utilidades
def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def cumulative_km(points):
    out = [0.0]
    for i in range(1, len(points)):
        out.append(out[-1] + haversine_km(points[i - 1], points[i]))
    return out


def douglas_peucker(points, tol_deg):
    """Simplificación Douglas–Peucker (iterativa) sobre (lat, lon) con corrección por coseno."""
    if len(points) < 3:
        return points
    k = math.cos(math.radians(points[0][0]))
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        ax, ay = points[s][1] * k, points[s][0]
        bx, by = points[e][1] * k, points[e][0]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, idx = -1.0, None
        for i in range(s + 1, e):
            px, py = points[i][1] * k, points[i][0]
            if norm < 1e-9:  # tramo cerrado (ruta en bucle): distancia al punto inicial
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol_deg:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    return [p for p, k_ in zip(points, keep) if k_]


def http_json(url, cache_key=None, retries=4):
    if cache_key:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = os.path.join(CACHE_DIR, cache_key + ".json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            if cache_key:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            return data
        except Exception as e:  # red inestable / límite de tasa: reintentar con espera
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"Fallo al consultar {url[:120]}...: {last}")


def slug(text):
    import unicodedata
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return "".join(c if c.isalnum() else "_" for c in t).strip("_")


def node_point(name, kind=None):
    n = NODES[name]
    if kind and kind in n:
        return (n[kind]["lat"], n[kind]["lon"])
    return (n["lat"], n["lon"])


# --------------------------------------------------------------------------- rutas viales
def osrm_route(points, cache_key):
    coords = ";".join(f"{lon:.5f},{lat:.5f}" for lat, lon in points)
    url = OSRM_URL + coords + "?overview=full&geometries=geojson&annotations=distance,duration"
    data = http_json(url, cache_key)
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM sin ruta para {cache_key}: {data.get('code')}")
    route = data["routes"][0]
    geom = [(c[1], c[0]) for c in route["geometry"]["coordinates"]]
    dist, dur = [], []
    for leg in route["legs"]:
        ann = leg.get("annotation") or {}
        dist += ann.get("distance", [])
        dur += ann.get("duration", [])
    if len(dist) != len(geom) - 1:  # anotaciones inconsistentes: velocidad uniforme
        total_d, total_t = route["distance"], route["duration"]
        cum = cumulative_km(geom)
        dist = [(cum[i + 1] - cum[i]) * 1000 for i in range(len(geom) - 1)]
        dur = [d / (total_d / total_t) for d in dist]
    return geom, dist, dur, route["distance"] / 1000.0, route["duration"] / 3600.0


def sample_elevations(samples, cache_key):
    out = []
    for i in range(0, len(samples), 100):
        chunk = samples[i:i + 100]
        locs = "|".join(f"{lat:.5f},{lon:.5f}" for lat, lon in chunk)
        part_key = f"{cache_key}_elev_{i // 100}"
        cached = os.path.exists(os.path.join(CACHE_DIR, part_key + ".json"))
        data = http_json(ELEV_URL + urllib.parse.quote(locs, safe="|,.-"), part_key)
        if data.get("status") != "OK":
            raise RuntimeError(f"Elevación no disponible para {cache_key}")
        out += [max(0.0, r["elevation"] or 0.0) for r in data["results"]]
        if not cached:
            time.sleep(1.1)  # límite de OpenTopoData: 1 consulta/segundo
    return out


def build_road_route(corredor, origen, destino, ruta, vias, alterna_de):
    o_kind = "puerto" if origen in ("Chancay", "Paita", "Matarani", "Ilo") else None
    d_kind = "puerto" if destino in ("Chancay", "Paita", "Matarani", "Ilo", "Yurimaguas") else None
    pts = [node_point(origen, o_kind)] + [W[v] for v in vias] + [node_point(destino, d_kind)]
    import hashlib
    raw = corredor + ("|ALT|" + ruta if alterna_de else "")
    key = "osrm_" + slug(corredor)[:24] + "_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
    geom, dist_m, dur_s, total_km, total_h = osrm_route(pts, key)
    time.sleep(0.6)

    # perfil: muestreo cada ~4 km sobre la geometría completa (altitud + velocidad de referencia)
    cum = [0.0]
    for d in dist_m:
        cum.append(cum[-1] + d / 1000.0)
    step = 4.0 if total_km > 60 else 1.0
    targets = [min(total_km, i * step) for i in range(int(total_km // step) + 1)]
    if targets[-1] < total_km:
        targets.append(total_km)
    samples, sample_km, sample_speed = [], [], []
    j = 0
    for t in targets:
        while j < len(cum) - 2 and cum[j + 1] < t:
            j += 1
        seg = cum[j + 1] - cum[j] or 1e-9
        f = max(0.0, min(1.0, (t - cum[j]) / seg))
        lat = geom[j][0] + (geom[j + 1][0] - geom[j][0]) * f
        lon = geom[j][1] + (geom[j + 1][1] - geom[j][1]) * f
        samples.append((lat, lon))
        sample_km.append(t)
        # velocidad de referencia (auto) promedio en la ventana [t-step, t+step]
        lo, hi = t - step, t + step
        d_sum = t_sum = 0.0
        for k in range(len(dist_m)):
            if cum[k + 1] < lo:
                continue
            if cum[k] > hi:
                break
            d_sum += dist_m[k]
            t_sum += dur_s[k]
        sample_speed.append(round((d_sum / t_sum) * 3.6, 1) if t_sum > 0 else 40.0)
    elev = sample_elevations(samples, key)
    # picos imposibles del SRTM (muestras en laderas junto a la vía): si un punto exige una
    # pendiente > 12 % hacia AMBOS vecinos en sentidos opuestos, se reemplaza por su promedio.
    for i in range(1, len(elev) - 1):
        dk1 = (sample_km[i] - sample_km[i - 1]) * 1000 or 1
        dk2 = (sample_km[i + 1] - sample_km[i]) * 1000 or 1
        g1, g2 = (elev[i] - elev[i - 1]) / dk1, (elev[i] - elev[i + 1]) / dk2
        if (g1 > 0.12 and g2 > 0.12) or (g1 < -0.12 and g2 < -0.12):
            elev[i] = (elev[i - 1] + elev[i + 1]) / 2

    simple = douglas_peucker(geom, 0.0009 if total_km > 80 else 0.0002)
    simple_cum = cumulative_km(simple)
    scale = total_km / simple_cum[-1] if simple_cum[-1] else 1.0
    ascenso = sum(max(0.0, elev[i] - elev[i - 1]) for i in range(1, len(elev)))
    return {
        "corredor": corredor, "origen": origen, "destino": destino, "modo": "Carretero",
        "ruta_principal": ruta, "alterna_de": alterna_de,
        "km": round(total_km, 1), "horas_ref_auto": round(total_h, 2),
        "geometry": [[round(p[0], 5), round(p[1], 5)] for p in simple],
        "cum_km": [round(c * scale, 2) for c in simple_cum],
        "profile": {"km": [round(k, 1) for k in sample_km], "alt": [round(e) for e in elev], "v": sample_speed},
        "alt_max": round(max(elev)), "alt_min": round(min(elev)), "ascenso_total_m": round(ascenso),
    }


def build_polyline_route(corredor, origen, destino, ruta, modo, pts, km_override=None, alt=0):
    cum = cumulative_km(pts)
    total = km_override or cum[-1]
    scale = total / cum[-1]
    n = max(2, int(total // 20))
    return {
        "corredor": corredor, "origen": origen, "destino": destino, "modo": modo,
        "ruta_principal": ruta, "alterna_de": None, "km": round(total, 1),
        "geometry": [[round(p[0], 5), round(p[1], 5)] for p in pts],
        "cum_km": [round(c * scale, 2) for c in cum],
        "profile": {"km": [round(total * i / n, 1) for i in range(n + 1)], "alt": [alt] * (n + 1), "v": [0] * (n + 1)},
        "alt_max": alt, "alt_min": alt, "ascenso_total_m": 0,
    }


def sea_points(code, origen, destino):
    o = node_point(origen, "puerto")
    d = node_point(destino, "puerto")
    if code.startswith("N"):
        path = SEA_NORTH[:]
        if ":Salaverry" in code:
            path = [p for p in SEA_NORTH if p[0] <= -8.25]
        if origen == "Chancay":
            path = [p for p in path if p[0] >= -11.60]
    else:
        path = SEA_SOUTH[:]
        if ":Ilo" in code:
            path = SEA_SOUTH + SEA_ILO
        if origen == "Chancay":
            path = [(-11.65, -77.45), (-12.00, -77.38)] + path[1:]
    pts = [o] + path + [d]
    if code.endswith("-"):
        pts = [node_point(origen, "puerto")] + list(reversed(path)) + [node_point(destino, "puerto")]
    return pts


def air_arc(o, d, n=36, bend=0.12):
    mx, my = (o[1] + d[1]) / 2, (o[0] + d[0]) / 2
    dx, dy = d[1] - o[1], d[0] - o[0]
    cx, cy = mx - dy * bend, my + dx * bend
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * o[1] + 2 * (1 - t) * t * cx + t ** 2 * d[1]
        y = (1 - t) ** 2 * o[0] + 2 * (1 - t) * t * cy + t ** 2 * d[0]
        pts.append((y, x))
    return pts


def main():
    routes = []
    print(f"Trazando {len(ROAD)} rutas carreteras sobre OpenStreetMap (OSRM)...")
    for corredor, origen, destino, ruta, vias, alt in ROAD:
        r = build_road_route(corredor, origen, destino, ruta, vias, alt)
        r["id"] = "TER:" + corredor + ("|ALT" if alt else "")
        routes.append(r)
        print(f"  {r['id']:<42} {r['km']:>7.1f} km  alt máx {r['alt_max']:>5} m  ({len(r['geometry'])} vértices)")

    for corredor, origen, destino, ruta, code in SEA:
        r = build_polyline_route(corredor, origen, destino, ruta, "Marítimo", sea_points(code, origen, destino))
        r["id"] = "MAR:" + corredor
        routes.append(r)
    for corredor, origen, destino, ruta, pts, km in RIVER:
        r = build_polyline_route(corredor, origen, destino, ruta, "Fluvial", pts, km_override=km, alt=110)
        r["id"] = "FLU:" + corredor
        routes.append(r)
    for corredor, origen, destino in AIR:
        o, d = node_point(origen, "aero"), node_point(destino, "aero")
        r = build_polyline_route(corredor, origen, destino, "Vuelo doméstico de carga", "Aéreo", air_arc(o, d))
        r["id"] = "AER:" + corredor
        routes.append(r)

    # altitud de cada nodo (SRTM)
    names = list(NODES)
    elev = sample_elevations([node_point(n) for n in names], "nodes")
    nodes = []
    for name, alt in zip(names, elev):
        n = NODES[name]
        nodes.append({
            "nombre": name, "departamento": n["dep"], "lat": n["lat"], "lon": n["lon"],
            "altitud_msnm": round(alt), "roles": n["roles"],
            "es_puerto": "puerto" in n["roles"], "es_fluvial": "fluvial" in n["roles"],
            "es_aeropuerto_principal": "aeropuerto" in n["roles"], "iata": n.get("iata"),
            "puerto": n.get("puerto"), "aero": n.get("aero"),
        })

    out = {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "fuentes": {
            "vias": "© OpenStreetMap contributors · trazado con OSRM",
            "altitud": "SRTM 90 m (NASA) vía OpenTopoData",
            "nodos": "Coordenadas de dominio público (centroides urbanos, puertos y aeropuertos)",
        },
        "nodes": nodes,
        "routes": routes,
        "hotspots": HOTSPOTS,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"\nRed escrita en {OUT_PATH} ({size_kb:.0f} KB): {len(nodes)} nodos, {len(routes)} rutas, {len(HOTSPOTS)} puntos críticos")


if __name__ == "__main__":
    main()
