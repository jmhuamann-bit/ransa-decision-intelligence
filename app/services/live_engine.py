"""
Motor del GEMELO DIGITAL de la operación RANSA Perú (Torre de Control en vivo).

Qué simula:
  * Una flota multimodal (camiones, buques de cabotaje, convoyes fluviales y vuelos de carga) que
    recorre las RUTAS REALES de data/peru_network.json. La velocidad de cada camión sale del perfil
    real de la vía: velocidad de referencia OSRM corregida por pendiente (subidas andinas) y por
    pérdida de potencia sobre 3.500 m s. n. m.
  * Telemetría por unidad: altitud, velocidad, combustible, temperatura de motor, temperatura del
    equipo de frío (cadena de frío) y horas de conducción con pausas obligatorias (SUTRAN).
  * Eventos peruanos GEOLOCALIZADOS (huaicos, derrumbes, bloqueos, nevadas, neblina, inundaciones,
    oleajes anómalos con cierre de puerto, vaciante de ríos, robos, fallas...). Un evento afecta a
    TODAS las rutas que pasan por ese punto (p. ej. un huaico en Chosica detiene a la flota de
    Lima–Huancayo, Lima–Cerro de Pasco, Lima–Huánuco y Lima–Pucallpa).
  * Decision Intelligence: para cada evento la IA arma opciones comparables (esperar, desviar por
    la ruta alterna real, puerto alterno, transbordo a cabotaje, reprogramar despachos) con su
    impacto en tiempo, costo (S/), CO₂ y OTIF, recomienda una y la ejecuta si el usuario la aplica
    (o automáticamente en modo autónomo).

IMPORTANTE: este módulo NUNCA escribe en la base de datos. Todo su estado vive en memoria y se
pierde al reiniciar — es intencional, para no contaminar los datos históricos usados por el resto
de la plataforma. Solo LEE (un muestreo de embarques del dataset al arrancar, para poblar la flota con
atributos auténticos del dataset y su riesgo calculado por el modelo de IA).
"""
import bisect
import math
import os
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.services import geo_data

PERU_TZ = timezone(timedelta(hours=-5), "PET")
TICK_SECONDS = 1.0
DEFAULT_SPEED = 240          # 1 s real = 4 min simulados
ALLOWED_SPEEDS = (60, 240, 600, 1800)
FLEET_TARGET = {"Carretero": 44, "Marítimo": 6, "Fluvial": 4, "Aéreo": 6}
FEED_MAXLEN = 250
MAX_AUTO_LOCATION_EVENTS = 6
STOP_BEFORE_KM = 9.0          # distancia a la que la flota se detiene antes de una vía bloqueada
# probabilidad base por unidad y por tick (a velocidad x240); la frecuencia crece de forma sublineal
# con la velocidad para que la demo sea dinámica sin volverse caótica
BASE_EVENT_P_PER_TICK = 0.0008
RISK_MULT = {"Bajo": 0.45, "Medio": 1.0, "Alto": 1.9, "Critico": 3.0}
STANDBY_PEN_H = 78.0          # costo de unidad detenida (sobreestadía) por hora
TARIFA_DESVIO_PEN_KM = 6.4
CO2_KG_POR_KM_CAMION = 1.05
# GNL (tractos extractivos y cisternas de líquidos RANSA) emite hasta 25 % menos que el diésel
CO2_FACTOR_COMBUSTIBLE = {"GNL": 0.75, "GNV": 0.82, "Diésel B5 · Euro III/IV": 1.05}
URBAN = {"Callao - Lima", "Lima - Lima", "Callao - Lurín"}

ESTADO_TXT = {"detenido": "detenido", "lento": "avanza con restricción", "desviado": "en ruta alterna",
              "esperando": "en espera", "descanso": "en pausa de conducción", "fondeado": "en fondeadero"}

# ----------------------------------------------------------------------------- catálogo de eventos
# alcance: "via" (punto de la red, afecta a toda ruta que pase), "unidad" (solo esa unidad),
#          "puerto" (cierra un puerto), "modo" (tramo fluvial / aéreo)
EVENTS = {
    "huaico": {"titulo": "Huaico", "categoria": "geologico", "severidad": "Critica", "icon": "fa-hill-rockslide",
               "alcance": "via", "bloquea": True, "dur": (6, 28), "radio": 3, "modos": ("Carretero",)},
    "derrumbe": {"titulo": "Derrumbe en la vía", "categoria": "geologico", "severidad": "Alta", "icon": "fa-hill-avalanche",
                 "alcance": "via", "bloquea": True, "dur": (3, 12), "radio": 2, "modos": ("Carretero",)},
    "bloqueo_social": {"titulo": "Bloqueo / paro regional", "categoria": "social", "severidad": "Critica",
                       "icon": "fa-people-group", "alcance": "via", "bloquea": True, "dur": (8, 60), "radio": 3,
                       "modos": ("Carretero",)},
    "inundacion": {"titulo": "Inundación de la vía", "categoria": "hidrologico", "severidad": "Alta", "icon": "fa-house-flood-water",
                   "alcance": "via", "bloquea": True, "dur": (6, 40), "radio": 4, "modos": ("Carretero",)},
    "accidente": {"titulo": "Accidente de tránsito", "categoria": "accidentalidad", "severidad": "Alta", "icon": "fa-car-burst",
                  "alcance": "via", "bloquea": True, "dur": (1.5, 6), "radio": 1.5, "modos": ("Carretero",)},
    "nevada": {"titulo": "Nevada / granizada", "categoria": "climatico", "severidad": "Media", "icon": "fa-snowflake",
               "alcance": "via", "bloquea": False, "factor": 0.35, "dur": (3, 10), "radio": 18, "modos": ("Carretero",)},
    "neblina": {"titulo": "Neblina densa", "categoria": "climatico", "severidad": "Media", "icon": "fa-smog",
                "alcance": "via", "bloquea": False, "factor": 0.5, "dur": (2, 7), "radio": 15, "modos": ("Carretero",)},
    "incendio": {"titulo": "Incendio forestal cercano", "categoria": "climatico", "severidad": "Alta", "icon": "fa-fire",
                 "alcance": "via", "bloquea": False, "factor": 0.4, "dur": (4, 16), "radio": 10, "modos": ("Carretero",)},
    "obras": {"titulo": "Cierre parcial por obras", "categoria": "infraestructura", "severidad": "Baja", "icon": "fa-person-digging",
              "alcance": "via", "bloquea": False, "factor": 0.55, "dur": (2, 8), "radio": 3, "modos": ("Carretero",)},
    "congestion": {"titulo": "Congestión / restricción vehicular", "categoria": "infraestructura", "severidad": "Baja",
                   "icon": "fa-traffic-light", "alcance": "via", "bloquea": False, "factor": 0.4, "dur": (1, 5), "radio": 6,
                   "modos": ("Carretero",)},
    "falla_mecanica": {"titulo": "Falla mecánica", "categoria": "operacion", "severidad": "Alta", "icon": "fa-screwdriver-wrench",
                       "alcance": "unidad", "efecto": "detenido", "dur": (1.5, 7), "modos": ("Carretero", "Fluvial")},
    "robo": {"titulo": "Intento de robo de carga", "categoria": "seguridad", "severidad": "Critica", "icon": "fa-user-ninja",
             "alcance": "unidad", "efecto": "detenido", "dur": (2, 8), "modos": ("Carretero",)},
    "reefer": {"titulo": "Falla del equipo de frío", "categoria": "cadena_frio", "severidad": "Alta", "icon": "fa-temperature-arrow-up",
               "alcance": "unidad", "efecto": "lento", "dur": (2, 6), "modos": ("Carretero",)},
    "documentos": {"titulo": "Retraso documental (SUNAT)", "categoria": "operacion", "severidad": "Baja", "icon": "fa-file-circle-exclamation",
                   "alcance": "unidad", "efecto": "esperando", "dur": (1, 5), "modos": ("Marítimo", "Aéreo", "Fluvial")},
    "senasa": {"titulo": "Inspección SENASA", "categoria": "operacion", "severidad": "Media", "icon": "fa-magnifying-glass",
               "alcance": "unidad", "efecto": "esperando", "dur": (1, 4), "modos": ("Carretero", "Marítimo")},
    "cliente": {"titulo": "Cambio de cita del cliente", "categoria": "cliente", "severidad": "Baja", "icon": "fa-calendar-xmark",
                "alcance": "unidad", "efecto": "esperando", "dur": (1, 4), "modos": ("Carretero",)},
    "vuelo_demorado": {"titulo": "Vuelo demorado por clima", "categoria": "aeropuerto", "severidad": "Media", "icon": "fa-plane-circle-exclamation",
                       "alcance": "unidad", "efecto": "esperando", "dur": (1, 5), "modos": ("Aéreo",)},
    "oleaje": {"titulo": "Oleaje anómalo: puerto cerrado (DHN)", "categoria": "puerto", "severidad": "Critica", "icon": "fa-water",
               "alcance": "puerto", "dur": (12, 42), "radio": 90, "modos": ("Marítimo",)},
    "congestion_portuaria": {"titulo": "Congestión portuaria", "categoria": "puerto", "severidad": "Media", "icon": "fa-ship",
                             "alcance": "puerto", "dur": (4, 14), "radio": 60, "modos": ("Marítimo",), "factor": 0.0},
    "vaciante": {"titulo": "Vaciante del río: restricción de calado", "categoria": "hidrologico", "severidad": "Alta",
                 "icon": "fa-arrow-down-wide-short", "alcance": "modo", "bloquea": False, "factor": 0.45, "dur": (36, 140),
                 "radio": 260, "modos": ("Fluvial",)},
}

SCENARIOS = {
    "huaico_carretera_central": {
        "titulo": "Huaico en Chosica (Carretera Central)", "icon": "fa-hill-rockslide",
        "descripcion": "Temporada de lluvias: un huaico cierra la Carretera Central en el Km 34. Afecta a toda la flota hacia la sierra central y la selva.",
        "eventos": [("huaico", "chosica", 16)]},
    "nevada_ticlio": {
        "titulo": "Nevada en Ticlio (4.818 m)", "icon": "fa-snowflake",
        "descripcion": "Heladas de invierno: la nevada en el Abra Anticona obliga a circular con cadenas y a baja velocidad.",
        "eventos": [("nevada", "ticlio", 9)]},
    "bloqueo_corredor_minero": {
        "titulo": "Bloqueo en el Corredor Minero Sur", "icon": "fa-people-group",
        "descripcion": "Comunidades bloquean la vía en Espinar: los camiones encapsulados con concentrado quedan detenidos camino a Matarani.",
        "eventos": [("bloqueo_social", "corredor_minero", 54)]},
    "oleaje_callao": {
        "titulo": "Oleaje anómalo: cierre del Callao", "icon": "fa-water",
        "descripcion": "La DHN cierra el Terminal Portuario del Callao. Los buques quedan en fondeadero: ¿esperar o desviar a Chancay?",
        "eventos": [("oleaje", "puerto_callao", 30)]},
    "paro_transportistas": {
        "titulo": "Paro de transportistas en Lima", "icon": "fa-road-barrier",
        "descripcion": "Paro contra la extorsión: bloqueos en Lima Norte y la Panamericana Sur, congestión en el acceso al Callao.",
        "eventos": [("bloqueo_social", "lima_norte", 14), ("bloqueo_social", (-12.2550, -76.8950, "Panamericana Sur – Lurín"), 14),
                    ("congestion", "callao_gambetta", 14)]},
    "nino_costero": {
        "titulo": "Niño Costero: lluvias extremas en el norte", "icon": "fa-cloud-showers-water",
        "descripcion": "Lluvias torrenciales desbordan el río Piura e inundan la Panamericana Norte en Lambayeque.",
        "eventos": [("inundacion", "piura_rio", 40), ("inundacion", "morrope", 34), ("huaico", (-7.36, -79.47, "Pacasmayo – Quebrada"), 20)]},
    "vaciante_amazonia": {
        "titulo": "Vaciante histórica en la Amazonía", "icon": "fa-arrow-down-wide-short",
        "descripcion": "El estiaje del Marañón y el Ucayali restringe el calado: los convoyes fluviales a Iquitos navegan a media marcha.",
        "eventos": [("vaciante", "amazonas_vaciante", 120), ("vaciante", "ucayali_vaciante", 120)]},
    "neblina_pasamayo": {
        "titulo": "Neblina en Pasamayo", "icon": "fa-smog",
        "descripcion": "Neblina densa en el acceso norte de Lima: visibilidad mínima y tránsito restringido.",
        "eventos": [("neblina", "pasamayo", 6)]},
    "crisis_sur": {
        "titulo": "Crisis social en el sur", "icon": "fa-triangle-exclamation",
        "descripcion": "Paro regional simultáneo en Juliaca, la Panamericana Sur (Ica) y el Corredor Minero, como en enero de 2023.",
        "eventos": [("bloqueo_social", "juliaca", 48), ("bloqueo_social", "ica_pan_sur", 30), ("bloqueo_social", "corredor_minero", 48)]},
}

SHIP_NAMES = ["MN Andes Express", "MN Pacífico Sur", "MN Humboldt", "MN Paracas", "MN Nazca Trader", "MN Sechura",
              "MN Mollendo Star", "MN Chimú", "MN Callao Bay", "MN Lobos de Tierra", "MN Islay", "MN Atico"]
RIVER_NAMES = ["Convoy Amazonas I", "Empujador Ucayali", "Motonave Marañón", "Convoy Huallaga", "Motonave Nauta",
               "Convoy Requena", "Empujador Itaya"]
AIRLINES = ["LA", "H2", "JA", "AV"]
FRIO = {"Alimentos refrigerados", "Agroexportación perecible (cadena de frío)", "Farmacéutica (cadena de frío)",
        "Pesca y congelados"}

PORT_HOTSPOT = {"Callao": "puerto_callao", "Chancay": "puerto_chancay", "Paita": "puerto_paita", "Matarani": "puerto_matarani"}
ALT_PORT = {"Callao": "Chancay", "Chancay": "Callao", "Paita": "Salaverry", "Matarani": "Ilo", "Ilo": "Matarani"}
MODAL_SHIFT = {  # vía costera bloqueada → cabotaje
    "Lima - Arequipa": "Callao - Matarani", "Lima - Tacna": "Callao - Ilo", "Lima - Piura": "Callao - Paita",
    "Lima - Chiclayo": "Callao - Paita", "Lima - Trujillo": "Callao - Salaverry", "Lima - Tumbes": "Callao - Paita",
}


def _now() -> datetime:
    return datetime.now(PERU_TZ).replace(microsecond=0)


def _plate(rnd: random.Random) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return f"{rnd.choice(letters)}{rnd.randint(1, 9)}{rnd.choice(letters)}-{rnd.randint(100, 999)}"


# ----------------------------------------------------------------------------- tiempos nominales
_timing_cache: dict = {}


def _truck_speed(v_ref: float, slope: float, alt: float) -> float:
    v = min((v_ref or 40.0) * 0.80, 72.0)
    if slope > 0:
        v *= max(0.40, 1 - slope / 115.0)
    elif slope < -25:
        v *= max(0.55, 1 + slope / 160.0)
    if alt > 3500:
        v *= 0.9
    return max(v, 8.0)


def _mode_speed(modo: str, km: float, total: float) -> float:
    if modo == "Marítimo":
        return 10.0 if km < 12 or total - km < 12 else 24.0
    if modo == "Fluvial":
        return 11.5
    if modo == "Aéreo":
        edge = min(km, total - km)
        return 260.0 if edge < 25 else 420.0 if edge < 70 else 650.0
    return 40.0


def route_timing(route: dict) -> dict:
    """Horas nominales acumuladas a lo largo del perfil de la ruta (sin eventos)."""
    rid = route["id"]
    if rid.startswith("CUSTOM:"):
        if "_timing" not in route:
            route["_timing"] = _compute_timing(route)
        return route["_timing"]
    if rid in _timing_cache:
        return _timing_cache[rid]
    data = _compute_timing(route)
    _timing_cache[rid] = data
    return data


def _compute_timing(route: dict) -> dict:
    kms, alts, vs = route["profile"]["km"], route["profile"]["alt"], route["profile"]["v"]
    cum_h = [0.0]
    speeds = []
    for i in range(1, len(kms)):
        dk = kms[i] - kms[i - 1]
        if route["modo"] == "Carretero":
            v = _truck_speed(vs[i], (alts[i] - alts[i - 1]) / dk if dk > 0 else 0, alts[i])
        else:
            v = _mode_speed(route["modo"], kms[i], kms[-1])
        speeds.append(v)
        cum_h.append(cum_h[-1] + (dk / v if dk > 0 else 0))
    return {"kms": kms, "cum_h": cum_h, "speeds": speeds or [40.0], "total_h": cum_h[-1]}


def _hours_at(timing: dict, km: float) -> float:
    kms, cum_h = timing["kms"], timing["cum_h"]
    if km <= kms[0]:
        return 0.0
    if km >= kms[-1]:
        return cum_h[-1]
    i = bisect.bisect_left(kms, km)
    f = (km - kms[i - 1]) / ((kms[i] - kms[i - 1]) or 1e-9)
    return cum_h[i - 1] + (cum_h[i] - cum_h[i - 1]) * f


def _speed_at(timing: dict, km: float) -> float:
    i = max(0, min(bisect.bisect_left(timing["kms"], km) - 1, len(timing["speeds"]) - 1))
    return timing["speeds"][i]


# ----------------------------------------------------------------------------- estado
@dataclass
class LiveEvent:
    id: int
    tipo: str
    titulo: str
    categoria: str
    severidad: str
    icon: str
    alcance: str
    lat: float
    lon: float
    lugar: str
    inicio: datetime
    fin: datetime
    bloquea: bool = False
    factor: float = 1.0
    radio_km: float = 3.0
    origen: str = "auto"
    puerto: Optional[str] = None
    route_hits: dict = field(default_factory=dict)
    decision: Optional[dict] = None
    afectados_total: int = 0
    unidad: Optional[str] = None
    notificado: bool = False


@dataclass
class Vehicle:
    id: str
    nombre: str
    modo: str
    tipo_vehiculo: str
    tipo_carga: str
    sector: str
    prioridad: str
    nivel_riesgo: str
    prob_riesgo: float
    id_viaje: str
    corredor: str
    route_id: str
    base_route_id: str
    km: float
    km_total: float
    salida: datetime
    eta_prog: datetime
    valor_carga: float
    peso_t: float
    linea: str = "Distribución"
    combustible_tipo: str = "Diésel B5 · Euro V"
    estilo: float = 1.0
    v_kmh: float = 0.0
    estado: str = "en_ruta"
    evento_id: Optional[int] = None
    incidente: Optional[dict] = None
    combustible: float = 80.0
    temp_motor: float = 86.0
    reefer_set: Optional[float] = None
    reefer: Optional[float] = None
    horas_conduccion: float = 0.0
    descanso_hasta: Optional[datetime] = None
    desvio: bool = False
    destino_override: Optional[str] = None
    custom_route: Optional[dict] = None
    co2_kg: float = 0.0
    costo_extra: float = 0.0
    cola_evento: Optional[int] = None
    cola_km: Optional[float] = None
    hist: deque = field(default_factory=lambda: deque(maxlen=90))


@dataclass
class FeedEntry:
    id: int
    ts: str
    sim_ts: str
    categoria: str
    severidad: str
    texto: str
    vehicle_id: Optional[str]
    event_id: Optional[int] = None


class LiveOperationsEngine:
    def __init__(self):
        self._lock = threading.RLock()
        self._rnd = random.Random()
        self._thread: Optional[threading.Thread] = None
        self._start_lock = threading.Lock()
        self._app = None
        self._pid: Optional[int] = None
        self._gen = 0              # generación del bucle: un bucle reemplazado termina solo
        self._last_beat = 0.0      # latido (time.monotonic) del último ciclo
        self._pools: dict = {}
        self._corridor_weights: dict = {}
        self._reset_state()

    def _reset_state(self):
        self._vehicles: dict[str, Vehicle] = {}
        self._events: dict[int, LiveEvent] = {}
        self._feed: deque = deque(maxlen=FEED_MAXLEN)
        self._tick = 0
        self._next_feed_id = getattr(self, "_next_feed_id", 1)
        self._next_vehicle_seq = 1
        self._next_event_id = 1
        self._sim_time = _now()
        self._started_at = datetime.now()
        self.speed = DEFAULT_SPEED
        self.paused = False
        self.autonomo = False
        self._holds: dict[str, datetime] = {}
        self._port_closed: dict[str, int] = {}
        self._stats = {"entregas": 0, "entregas_a_tiempo": 0, "co2_kg": 0.0, "costo_contingencia": 0.0,
                       "decisiones": 0, "otif_salvados": 0}

    # ------------------------------------------------------------------ arranque
    def attach(self, app) -> None:
        """Asocia la app; el bucle arranca con la primera petición del proceso que la atiende."""
        self._app = app

    def _running_here(self) -> bool:
        """El bucle corre en ESTE proceso y late (un hilo vivo pero sin ciclos en 15 s está atascado)."""
        t = self._thread
        return (t is not None and t.is_alive() and self._pid == os.getpid()
                and time.monotonic() - self._last_beat < 15)

    def ensure_running(self) -> None:
        """Vigía barato (se llama en cada petición). Gunicorn puede crear el proceso que atiende con un
        fork, y los hilos NO sobreviven al fork: si el bucle no corre en ESTE proceso, se relanza sin
        perder la operación. Así las unidades siempre avanzan, en local y en Render."""
        if not self._running_here() and self._app is not None:
            self.start(self._app)

    def start(self, app) -> None:
        with self._start_lock:
            if self._running_here():
                return
            self._app = app
            if not self._vehicles:
                with self._lock:
                    if not self._vehicles:
                        self._load_pools(app)
                        self._spawn_initial_fleet()
                        self._push_feed("operacion", "Baja", "Gemelo digital iniciado: flota RANSA sincronizada con la red vial del Perú.", None)
            self._gen += 1
            self._pid = os.getpid()
            self._last_beat = time.monotonic()
            self._thread = threading.Thread(target=self._run, args=(app, self._gen), daemon=True,
                                            name=f"ransa-digital-twin-{self._gen}")
            self._thread.start()

    def _after_fork_in_child(self) -> None:
        # en el hijo no existe el hilo del padre y los candados pudieron quedar tomados: se reinician
        self._lock = threading.RLock()
        self._start_lock = threading.Lock()
        self._thread = None

    def _load_pools(self, app) -> None:
        from sqlalchemy import func
        from app.extensions import db
        from app.models.shipment import Shipment

        rows = []
        try:
            with app.app_context():
                rows = (
                    Shipment.query.with_entities(
                        Shipment.corredor_logistico, Shipment.tipo_transporte, Shipment.tipo_vehiculo,
                        Shipment.tipo_carga, Shipment.sector_cliente, Shipment.prioridad_cliente,
                        Shipment.nivel_riesgo, Shipment.prob_riesgo_incumplimiento, Shipment.id_viaje,
                        Shipment.valor_asegurado_pen, Shipment.peso_toneladas, Shipment.linea_negocio,
                        Shipment.combustible_unidad,
                    )
                    .order_by(func.random()).limit(6000).all()
                )
                db.session.remove()
        except Exception:  # BD vacía o sin migrar: la flota usa atributos genéricos
            rows = []

        pools = {m: [] for m in FLEET_TARGET}
        counts: dict = {}
        for r in rows:
            if r.tipo_transporte not in pools:
                continue
            if not geo_data.get_route(r.corredor_logistico, r.tipo_transporte):
                continue
            pools[r.tipo_transporte].append({
                "corredor": r.corredor_logistico, "tipo_vehiculo": r.tipo_vehiculo, "tipo_carga": r.tipo_carga,
                "sector": r.sector_cliente, "prioridad": r.prioridad_cliente, "nivel_riesgo": r.nivel_riesgo or "Medio",
                "prob_riesgo": r.prob_riesgo_incumplimiento if r.prob_riesgo_incumplimiento is not None else 25.0,
                "id_viaje": r.id_viaje, "valor": r.valor_asegurado_pen or 0.0, "peso": r.peso_toneladas or 0.0,
                "linea": r.linea_negocio or "Distribución", "combustible": r.combustible_unidad or "Diésel B5 · Euro V",
            })
            key = (r.tipo_transporte, r.corredor_logistico)
            counts[key] = counts.get(key, 0) + 1
        for modo in pools:
            if not pools[modo]:
                pools[modo] = self._synthetic_pool(modo)
        self._pools = pools

    def _synthetic_pool(self, modo: str) -> list:
        prefix = geo_data.MODE_PREFIX[modo] + ":"
        out = []
        for r in geo_data.all_routes():
            if r["id"].startswith(prefix) and not r["alterna_de"]:
                out.append({"corredor": r["corredor"], "tipo_vehiculo": "Unidad", "tipo_carga": "Consumo masivo (seca)",
                            "sector": "Consumo Masivo", "prioridad": "Estándar", "nivel_riesgo": "Medio", "prob_riesgo": 25.0,
                            "id_viaje": None, "valor": 250000.0, "peso": 20.0, "linea": "Distribución",
                            "combustible": "Diésel B5 · Euro V"})
        return out

    def _spawn_initial_fleet(self) -> None:
        for modo, n in FLEET_TARGET.items():
            for _ in range(n):
                self._spawn_vehicle(modo, mid_route=True)

    def _pick_row(self, modo: str, corredor: Optional[str] = None, mid_route: bool = False) -> Optional[dict]:
        pool = self._pools.get(modo) or []
        if corredor:
            cands = [p for p in pool if p["corredor"] == corredor]
            return self._rnd.choice(cands) if cands else None
        for _ in range(12):
            row = self._rnd.choice(pool) if pool else None
            if not row:
                return None
            hold = self._holds.get(row["corredor"])
            if hold and hold > self._sim_time:
                continue
            route = geo_data.get_route(row["corredor"], modo)
            # al iniciar, la flota visible en ruta es proporcional a la duración del viaje
            if mid_route and route and modo == "Carretero":
                dur = route_timing(route)["total_h"]
                if self._rnd.random() > min(1.0, 0.15 + dur / 14):
                    continue
            if row["corredor"] in URBAN and self._rnd.random() < 0.55:
                continue
            return row
        return self._rnd.choice(pool) if pool else None

    def _spawn_vehicle(self, modo: str, mid_route: bool = False, corredor: Optional[str] = None,
                       km_start: Optional[float] = None, route_id: Optional[str] = None) -> Optional[Vehicle]:
        row = self._pick_row(modo, corredor, mid_route)
        if not row:
            return None
        route = geo_data.get_route_by_id(route_id) if route_id else geo_data.get_route(row["corredor"], modo)
        if not route:
            return None
        timing = route_timing(route)
        total = route["cum_km"][-1]
        km = km_start if km_start is not None else (self._rnd.uniform(0.0, 0.85) * total if mid_route else 0.0)
        hecho_h = _hours_at(timing, km)
        handling = {"Carretero": self._rnd.uniform(1.0, 2.5), "Marítimo": 6.0, "Fluvial": 6.0, "Aéreo": 3.0}[modo]
        rests = 0.5 * math.floor(timing["total_h"] / 4.5) if modo == "Carretero" else 0.0
        plan_h = (timing["total_h"] + rests + handling) * self._rnd.uniform(1.09, 1.17)
        salida = self._sim_time - timedelta(hours=hecho_h * self._rnd.uniform(1.0, 1.12) + handling * 0.5)
        seq = self._next_vehicle_seq
        self._next_vehicle_seq += 1
        letra = {"Carretero": "T", "Marítimo": "M", "Fluvial": "F", "Aéreo": "A"}[modo]
        if modo == "Carretero":
            nombre = _plate(self._rnd)
        elif modo == "Marítimo":
            nombre = SHIP_NAMES[seq % len(SHIP_NAMES)]
        elif modo == "Fluvial":
            nombre = RIVER_NAMES[seq % len(RIVER_NAMES)]
        else:
            nombre = f"{self._rnd.choice(AIRLINES)}{self._rnd.randint(1100, 9899)}"
        carga = row["tipo_carga"] or "Consumo masivo (seca)"
        reefer_set = (-18.0 if carga == "Pesca y congelados" else 4.0) if carga in FRIO and modo == "Carretero" else None
        v = Vehicle(
            id=f"RNS-{letra}{seq:03d}", nombre=nombre, modo=modo, tipo_vehiculo=row["tipo_vehiculo"] or "Unidad",
            tipo_carga=carga, sector=row["sector"] or "—", prioridad=row["prioridad"] or "Estándar",
            nivel_riesgo=row["nivel_riesgo"], prob_riesgo=float(row["prob_riesgo"]), id_viaje=row["id_viaje"],
            corredor=row["corredor"], route_id=route["id"], base_route_id=route["id"], km=km, km_total=total,
            salida=salida, eta_prog=salida + timedelta(hours=plan_h), valor_carga=float(row["valor"] or 0),
            peso_t=float(row["peso"] or 0), linea=row.get("linea") or "Distribución",
            combustible_tipo=row.get("combustible") or "Diésel B5 · Euro V", estilo=self._rnd.uniform(0.93, 1.05),
            combustible=self._rnd.uniform(45, 95), temp_motor=self._rnd.uniform(84, 90),
            reefer_set=reefer_set, reefer=(reefer_set + self._rnd.uniform(-0.6, 0.6)) if reefer_set is not None else None,
            horas_conduccion=self._rnd.uniform(0, 3.5) if modo == "Carretero" else 0.0,
        )
        self._vehicles[v.id] = v
        return v

    # ------------------------------------------------------------------ bucle
    def _run(self, app, gen: int) -> None:
        while gen == self._gen:
            time.sleep(TICK_SECONDS)
            if gen != self._gen:  # el vigía lanzó un bucle nuevo: este termina
                return
            try:
                self._tick_once()
            except Exception:
                app.logger.exception("Error en tick del gemelo digital")

    def _tick_once(self) -> None:
        with self._lock:
            self._last_beat = time.monotonic()
            self._tick += 1
            if self.paused:
                return
            dt_h = self.speed * TICK_SECONDS / 3600.0
            self._sim_time += timedelta(seconds=self.speed * TICK_SECONDS)
            self._expire_events()
            for v in list(self._vehicles.values()):
                self._advance_vehicle(v, dt_h)
            self._maybe_auto_events(dt_h)
            if self.autonomo:
                for ev in list(self._events.values()):
                    if ev.decision is None and ev.alcance != "unidad":
                        opts = self._options(ev)
                        if opts["opciones"] and opts["afectados"] > 0:
                            self._apply_option(ev, opts["recomendada"], automatico=True)
            for modo, n in FLEET_TARGET.items():
                actual = sum(1 for v in self._vehicles.values() if v.modo == modo)
                if actual < n and self._rnd.random() < 0.5:
                    self._spawn_vehicle(modo)

    # ------------------------------------------------------------------ movimiento
    def _route_of(self, v: Vehicle) -> dict:
        return v.custom_route or geo_data.get_route_by_id(v.route_id)

    def _advance_vehicle(self, v: Vehicle, dt_h: float) -> None:
        route = self._route_of(v)
        timing = route_timing(route)
        now = self._sim_time
        lat, lon, _ = geo_data.point_at_km(route, v.km)

        # incidentes propios de la unidad
        if v.incidente:
            if now >= v.incidente["fin"]:
                self._push_feed(v.incidente["categoria"], "Baja", f"{v.id} ({v.nombre}) retoma la marcha tras: {v.incidente['titulo']}.", v.id)
                v.incidente = None
                v.estado = "desviado" if v.desvio else "en_ruta"
            elif v.incidente["efecto"] in ("detenido", "esperando"):
                v.estado = v.incidente["efecto"]
                v.v_kmh = 0.0
                self._standby(v, dt_h)
                self._telemetry(v, route, 0.0, dt_h)
                return

        # pausa obligatoria de conducción (SUTRAN: tras ~5 h continuas)
        if v.modo == "Carretero":
            if v.descanso_hasta:
                if now >= v.descanso_hasta:
                    v.descanso_hasta = None
                    v.horas_conduccion = 0.0
                    v.estado = "desviado" if v.desvio else "en_ruta"
                else:
                    v.estado = "descanso"
                    v.v_kmh = 0.0
                    self._telemetry(v, route, 0.0, dt_h)
                    return
            elif v.horas_conduccion >= 5.0 and v.corredor not in URBAN:
                v.descanso_hasta = now + timedelta(minutes=self._rnd.randint(30, 50))
                v.estado = "descanso"
                v.v_kmh = 0.0
                return

        # eventos de vía / puerto / río
        factor = 1.0
        blocked_by = None
        slowed_by = None
        for ev in self._events.values():
            if ev.alcance == "puerto":
                dest = v.destino_override or route["destino"]
                if v.modo == "Marítimo" and dest == ev.puerto and v.km_total - v.km <= ev.radio_km and ev.tipo == "oleaje":
                    blocked_by = ev
                elif v.modo == "Marítimo" and dest == ev.puerto and v.km_total - v.km <= ev.radio_km:
                    slowed_by, factor = ev, min(factor, 0.25)
                continue
            if ev.alcance == "modo":
                if v.modo == "Fluvial" and geo_data.haversine_km(lat, lon, ev.lat, ev.lon) <= ev.radio_km:
                    slowed_by, factor = ev, min(factor, ev.factor)
                continue
            if ev.alcance != "via" or v.modo != "Carretero":
                continue
            km_ev = ev.route_hits.get(v.route_id) if not v.custom_route else None
            if km_ev is None:
                continue
            if ev.bloquea:
                if v.km <= km_ev + 0.2 and km_ev - v.km <= STOP_BEFORE_KM:
                    blocked_by = ev
                    break
            elif abs(v.km - km_ev) <= ev.radio_km:
                slowed_by, factor = ev, min(factor, ev.factor)

        if blocked_by:
            if v.evento_id != blocked_by.id:
                blocked_by.afectados_total += 1
            v.evento_id = blocked_by.id
            km_ev = blocked_by.route_hits.get(v.route_id) if v.modo == "Carretero" else None
            if km_ev is not None:
                # la unidad avanza hasta el final de la cola del atasco y se forma en fila
                if v.cola_evento != blocked_by.id:
                    n = sum(1 for o in self._vehicles.values() if o.cola_evento == blocked_by.id)
                    v.cola_evento, v.cola_km = blocked_by.id, max(0.0, km_ev - 0.4 - 0.3 * n)
                if v.km < v.cola_km - 0.05:
                    speed = min(_speed_at(timing, v.km) * 0.6, 30.0)
                    v.km = min(v.cola_km, v.km + speed * dt_h)
                    v.v_kmh, v.estado = round(speed, 1), "lento"
                    self._telemetry(v, route, speed, dt_h)
                    return
            v.estado = "fondeado" if v.modo == "Marítimo" else "detenido"
            v.v_kmh = 0.0
            self._standby(v, dt_h)
            self._telemetry(v, route, 0.0, dt_h)
            return
        v.evento_id = slowed_by.id if slowed_by else None

        if v.incidente and v.incidente["efecto"] == "lento":
            factor = min(factor, 0.6)
        base_v = _speed_at(timing, v.km) if v.modo == "Carretero" else _mode_speed(v.modo, v.km, v.km_total)
        speed = base_v * v.estilo * factor
        v.v_kmh = round(speed, 1)
        v.estado = "lento" if factor < 0.95 else ("desviado" if v.desvio else "en_ruta")
        d_km = speed * dt_h
        v.km = min(v.km_total, v.km + d_km)
        if v.modo == "Carretero":
            v.horas_conduccion += dt_h
            v.co2_kg += d_km * CO2_KG_POR_KM_CAMION * CO2_FACTOR_COMBUSTIBLE.get(v.combustible_tipo, 1.0) * (
                1.25 if geo_data.slope_at_km(route, v.km) > 20 else 1.0)
        elif v.modo == "Marítimo":
            v.co2_kg += d_km * 18.0
        elif v.modo == "Fluvial":
            v.co2_kg += d_km * 6.0
        else:
            v.co2_kg += d_km * 9.5
        self._telemetry(v, route, speed, dt_h)
        if v.km >= v.km_total - 1e-6:
            self._complete_vehicle(v)

    def _standby(self, v: Vehicle, dt_h: float) -> None:
        if v.modo == "Carretero":
            cost = STANDBY_PEN_H * dt_h
        elif v.modo == "Marítimo":
            cost = 1250.0 * dt_h   # demora del buque (fracción atribuible)
        else:
            cost = 140.0 * dt_h
        v.costo_extra += cost
        self._stats["costo_contingencia"] += cost

    def _telemetry(self, v: Vehicle, route: dict, speed: float, dt_h: float) -> None:
        alt, _ = geo_data.profile_at_km(route, v.km) if v.modo == "Carretero" else (
            (0.0, 0.0) if v.modo == "Marítimo" else (110.0, 0.0) if v.modo == "Fluvial" else (0.0, 0.0))
        if v.modo == "Aéreo":
            edge = min(v.km, v.km_total - v.km)
            alt = min(10500.0, edge * 95.0)
        slope = geo_data.slope_at_km(route, v.km) if v.modo == "Carretero" else 0.0
        if v.modo == "Carretero":
            burn = speed * dt_h / max(8.5 * (1 - min(0.35, max(0.0, slope) / 90)), 3.5) / 3.2  # % del tanque
            v.combustible -= burn
            if v.combustible < 14:
                v.combustible = self._rnd.uniform(88, 97)
                self._push_feed("operacion", "Baja", f"{v.id} repostó en grifo de ruta ({v.corredor}).", v.id)
            target = 86 + max(0.0, slope) * 0.18 + (4 if alt > 4000 else 0)
            v.temp_motor += (target - v.temp_motor) * 0.25 + self._rnd.uniform(-0.4, 0.4)
        if v.reefer is not None:
            if v.incidente and v.incidente.get("tipo") == "reefer":
                v.reefer += 0.9 * dt_h * 4
            else:
                v.reefer += (v.reefer_set - v.reefer) * 0.2 + self._rnd.uniform(-0.15, 0.15)
        v.hist.append((round(v.km, 1), round(alt), round(speed, 1), round(v.reefer, 1) if v.reefer is not None else None))
        v._alt = alt  # type: ignore[attr-defined]

    def _complete_vehicle(self, v: Vehicle) -> None:
        a_tiempo = self._sim_time <= v.eta_prog
        self._stats["entregas"] += 1
        self._stats["entregas_a_tiempo"] += int(a_tiempo)
        self._stats["co2_kg"] += v.co2_kg
        dest = v.destino_override or self._route_of(v)["destino"]
        estado = "a tiempo ✓" if a_tiempo else f"con retraso de {self._fmt_h((self._sim_time - v.eta_prog).total_seconds() / 3600)}"
        self._push_feed("operacion", "Baja" if a_tiempo else "Media",
                        f"Entrega completada — {v.id} ({v.nombre}) llegó a {dest} {estado}.", v.id)
        del self._vehicles[v.id]
        if v.destino_override == "Chancay" and self._rnd.random() < 0.9:
            nv = self._spawn_vehicle("Carretero", corredor="Chancay - Callao")
            if nv:
                self._push_feed("operacion", "Baja", f"Última milla: {nv.id} lleva la carga desembarcada en Chancay al Callao.", nv.id)
        else:
            self._spawn_vehicle(v.modo)

    # ------------------------------------------------------------------ eventos
    def _expire_events(self) -> None:
        for ev in list(self._events.values()):
            if self._sim_time >= ev.fin:
                del self._events[ev.id]
                if ev.puerto:
                    self._port_closed.pop(ev.puerto, None)
                n = sum(1 for v in self._vehicles.values() if v.evento_id == ev.id)
                for v in self._vehicles.values():
                    if v.evento_id == ev.id:
                        v.evento_id = None
                    if v.cola_evento == ev.id:
                        v.cola_evento, v.cola_km = None, None
                txt = "Puerto reabierto" if ev.tipo == "oleaje" else "Vía restablecida" if ev.bloquea else "Condición normalizada"
                self._push_feed(ev.categoria, "Baja", f"{txt}: {ev.titulo.lower()} en {ev.lugar} finalizó"
                                + (f" ({n} unidades reanudan marcha)." if n else "."), None, ev.id)

    def _maybe_auto_events(self, dt_h: float) -> None:
        month = self._sim_time.month
        n_loc = sum(1 for e in self._events.values() if e.alcance == "via" and e.origen == "auto")
        for v in list(self._vehicles.values()):
            if v.incidente or v.evento_id:
                continue
            p = BASE_EVENT_P_PER_TICK * RISK_MULT.get(v.nivel_riesgo, 1.0) * (0.5 + (v.prob_riesgo or 0) / 100)
            if self._rnd.random() >= p * (self.speed / 240) ** 0.5:
                continue
            tipo = self._pick_event_type(v, month)
            if not tipo:
                continue
            cat = EVENTS[tipo]
            if cat["alcance"] == "via":
                if n_loc >= MAX_AUTO_LOCATION_EVENTS:
                    continue
                route = self._route_of(v)
                km_ev = min(v.km_total - 1, v.km + self._rnd.uniform(5, 30))
                if km_ev <= v.km + 2:
                    continue
                lat, lon, _ = geo_data.point_at_km(route, km_ev)
                self.create_event(tipo, lat, lon, lugar=self._place_name(lat, lon, v.corredor), origen="auto")
                n_loc += 1
            elif cat["alcance"] == "unidad":
                self._vehicle_incident(v, tipo)
            elif cat["alcance"] == "puerto" and v.modo == "Marítimo":
                dest = self._route_of(v)["destino"]
                if dest in PORT_HOTSPOT and not any(e.puerto == dest for e in self._events.values()):
                    hs = self._hotspot(PORT_HOTSPOT[dest])
                    self.create_event(tipo, hs["lat"], hs["lon"], lugar=hs["nombre"], origen="auto", puerto=dest)
            elif cat["alcance"] == "modo" and v.modo == "Fluvial" and month in (7, 8, 9, 10, 11):
                if not any(e.tipo == "vaciante" for e in self._events.values()):
                    hs = self._hotspot("amazonas_vaciante" if "Yurimaguas" in v.corredor else "ucayali_vaciante")
                    self.create_event("vaciante", hs["lat"], hs["lon"], lugar=hs["nombre"], origen="auto")

    def _pick_event_type(self, v: Vehicle, month: int) -> Optional[str]:
        route = self._route_of(v)
        if v.modo == "Carretero":
            alt, _ = geo_data.profile_at_km(route, v.km)
            lat, lon, _ = geo_data.point_at_km(route, v.km)
            lluvia = month in (12, 1, 2, 3)
            invierno = month in (6, 7, 8)
            sierra_selva = alt > 1800 or lon > -76.2
            w = {
                "huaico": (3.0 if lluvia else 0.4) * (1.6 if sierra_selva else 0.25),
                "derrumbe": 1.0 * (1.5 if sierra_selva else 0.4),
                "bloqueo_social": 1.6 if ("Matarani" in v.corredor or "Juliaca" in v.corredor or "Cusco" in v.corredor) else 0.55,
                "inundacion": (2.6 if lluvia and lat > -8.5 else 0.15),
                "nevada": (3.0 if invierno else 0.5) if alt > 3800 else 0.0,
                "neblina": (2.0 if invierno and alt < 500 else 0.4),
                "accidente": 1.2, "obras": 0.8, "congestion": 2.2 if v.corredor in URBAN else 0.3,
                "incendio": 1.2 if month in (8, 9, 10) and lon > -76.6 else 0.0,
                "falla_mecanica": 1.3, "robo": 1.4 if lat > -12.3 and alt < 600 else 0.3,
                "reefer": 1.2 if v.reefer is not None else 0.0, "cliente": 0.6,
                "senasa": 0.6 if "Agro" in (v.tipo_carga or "") else 0.0,
            }
        elif v.modo == "Marítimo":
            w = {"oleaje": 1.2 if month in (5, 6, 7, 8, 9) else 0.5, "congestion_portuaria": 1.0, "documentos": 0.8, "senasa": 0.3}
        elif v.modo == "Fluvial":
            w = {"vaciante": 2.5 if month in (8, 9, 10) else 0.2, "falla_mecanica": 0.8, "documentos": 0.5}
        else:
            w = {"vuelo_demorado": 1.5, "documentos": 0.7}
        items = [(k, x) for k, x in w.items() if x > 0]
        if not items:
            return None
        total = sum(x for _, x in items)
        r = self._rnd.uniform(0, total)
        for k, x in items:
            r -= x
            if r <= 0:
                return k
        return items[-1][0]

    def _vehicle_incident(self, v: Vehicle, tipo: str, horas: Optional[float] = None) -> None:
        cat = EVENTS[tipo]
        dur = horas or self._rnd.uniform(*cat["dur"])
        v.incidente = {"tipo": tipo, "titulo": cat["titulo"], "categoria": cat["categoria"], "severidad": cat["severidad"],
                       "icon": cat["icon"], "efecto": cat["efecto"], "fin": self._sim_time + timedelta(hours=dur)}
        lat, lon, _ = geo_data.point_at_km(self._route_of(v), v.km)
        lugar = self._place_name(lat, lon, v.corredor)
        extra = ""
        if tipo == "reefer":
            extra = f" Temperatura de la carga en alza ({v.reefer:.1f} °C, consigna {v.reefer_set:.0f} °C): la IA sugiere transbordo en el CD más cercano."
        elif tipo == "robo":
            extra = " Se activa protocolo de seguridad y aviso a la PNP; GPS y botón de pánico verificados."
        self._push_feed(cat["categoria"], cat["severidad"], f"{cat['titulo']} — {v.id} ({v.nombre}) en {lugar}.{extra}", v.id)

    def _hotspot(self, hid: str) -> dict:
        for h in geo_data.get_hotspots():
            if h["id"] == hid:
                return h
        raise KeyError(hid)

    def _place_name(self, lat: float, lon: float, corredor: str = "") -> str:
        best, best_d = None, 1e9
        for h in geo_data.get_hotspots():
            d = geo_data.haversine_km(lat, lon, h["lat"], h["lon"])
            if d < best_d:
                best, best_d = h, d
        if best and best_d < 12:
            return best["nombre"]
        city, cd = None, 1e9
        for name, c in geo_data.CITY_COORDS.items():
            d = geo_data.haversine_km(lat, lon, c["lat"], c["lon"])
            if d < cd:
                city, cd = name, d
        txt = f"a {cd:.0f} km de {city}" if cd >= 3 else city
        return f"{corredor} ({txt})" if corredor else txt

    def create_event(self, tipo: str, lat: float, lon: float, horas: Optional[float] = None, lugar: Optional[str] = None,
                     origen: str = "manual", puerto: Optional[str] = None) -> Optional[LiveEvent]:
        cat = EVENTS.get(tipo)
        if not cat:
            return None
        with self._lock:
            if cat["alcance"] == "unidad":
                return None
            if cat["alcance"] == "puerto" and not puerto:
                puerto = min(PORT_HOTSPOT, key=lambda p: geo_data.haversine_km(lat, lon, self._hotspot(PORT_HOTSPOT[p])["lat"],
                                                                               self._hotspot(PORT_HOTSPOT[p])["lon"]))
            for e in self._events.values():  # fusionar con un evento igual muy cercano
                if e.tipo == tipo and geo_data.haversine_km(lat, lon, e.lat, e.lon) < 6:
                    e.fin = max(e.fin, self._sim_time + timedelta(hours=horas or self._rnd.uniform(*cat["dur"])))
                    return e
            dur = horas or self._rnd.uniform(*cat["dur"])
            ev = LiveEvent(
                id=self._next_event_id, tipo=tipo, titulo=cat["titulo"], categoria=cat["categoria"], severidad=cat["severidad"],
                icon=cat["icon"], alcance=cat["alcance"], lat=lat, lon=lon,
                lugar=lugar or self._place_name(lat, lon), inicio=self._sim_time, fin=self._sim_time + timedelta(hours=dur),
                bloquea=cat.get("bloquea", False), factor=cat.get("factor", 1.0), radio_km=cat.get("radio", 3), origen=origen,
                puerto=puerto,
            )
            self._next_event_id += 1
            if ev.alcance == "via":
                for r in geo_data.all_routes():
                    if r["modo"] != "Carretero":
                        continue
                    km = geo_data.nearest_km_on_route(r, lat, lon, max_km=2.5)
                    if km is not None:
                        ev.route_hits[r["id"]] = km
            if puerto:
                self._port_closed[puerto] = ev.id
            self._events[ev.id] = ev
            rutas = sorted({geo_data.get_route_by_id(rid)["corredor"] for rid in ev.route_hits})
            alcance_txt = f" Afecta a {len(rutas)} corredores: {', '.join(rutas[:4])}{'…' if len(rutas) > 4 else ''}." if rutas else ""
            dur_txt = f" Duración estimada: {self._fmt_h(dur)}."
            self._push_feed(ev.categoria, ev.severidad, f"{ev.titulo} en {ev.lugar}.{alcance_txt}{dur_txt}", None, ev.id)
            return ev

    def resolve_event(self, event_id: int) -> bool:
        with self._lock:
            ev = self._events.get(event_id)
            if not ev:
                return False
            ev.fin = self._sim_time
            self._expire_events()
            return True

    # ------------------------------------------------------------------ decisiones IA
    def _affected(self, ev: LiveEvent) -> list:
        out = []
        for v in self._vehicles.values():
            if v.evento_id == ev.id:
                out.append(v)
                continue
            if ev.alcance == "via" and v.modo == "Carretero" and not v.custom_route:
                km_ev = ev.route_hits.get(v.route_id)
                if km_ev is not None and v.km < km_ev and (ev.bloquea or abs(v.km - km_ev) < 200):
                    out.append(v)
            elif ev.alcance == "puerto" and v.modo == "Marítimo" and (v.destino_override or self._route_of(v)["destino"]) == ev.puerto                     and v.km_total - v.km <= 450:  # buques que llegarían durante el cierre
                out.append(v)
            elif ev.alcance == "modo" and v.modo == "Fluvial":
                out.append(v)
        return out

    def _remaining_ev_h(self, ev: LiveEvent) -> float:
        return max(0.0, (ev.fin - self._sim_time).total_seconds() / 3600)

    def _options(self, ev: LiveEvent) -> dict:
        afect = self._affected(ev)
        n = len(afect)
        rem = self._remaining_ev_h(ev)
        opciones = []
        if n == 0:
            return {"afectados": 0, "opciones": [], "recomendada": None}

        def eta_sin_evento(v):
            """ETA de la unidad descontando la demora que ya le imputa ESTE evento (cada opción
            suma luego su propia demora: esperar, desviar, transbordar...)."""
            eta = self._eta(v)
            if v.evento_id == ev.id:
                if ev.bloquea or ev.alcance == "puerto":
                    eta -= timedelta(hours=rem)
                else:
                    eta -= timedelta(hours=rem * (1 - ev.factor) * 0.5)
            return eta

        def late_after(extra_h_by_vehicle):
            tarde = 0
            for v, extra in extra_h_by_vehicle:
                eta = eta_sin_evento(v) + timedelta(hours=extra)
                tarde += int(eta > v.eta_prog)
            return tarde

        valor = sum(v.valor_carga for v in afect)
        espera_evento = rem if (ev.bloquea or ev.alcance == "puerto") else rem * (1 - ev.factor) * 0.5
        base_tarde = sum(1 for v in afect if eta_sin_evento(v) + timedelta(hours=espera_evento) > v.eta_prog)

        if ev.alcance == "via":
            wait_extra = [(v, rem if ev.bloquea else rem * (1 - ev.factor) * 0.5) for v in afect]
            opciones.append(self._opt("esperar", "Esperar reapertura", "fa-hourglass-half",
                                      f"Las {n} unidades aguardan en zona segura hasta que se restablezca la vía (~{self._fmt_h(rem)}).",
                                      horas=rem if ev.bloquea else rem * 0.3, costo=STANDBY_PEN_H * rem * n,
                                      co2=n * rem * 2.2, tarde=late_after(wait_extra), n=n, riesgo=0.55))
            desvios = []
            for v in afect:
                alt = geo_data.get_route(v.corredor, "Carretero", alterna=True)
                main = geo_data.get_route_by_id(v.route_id)
                if not alt or v.desvio or not main or main.get("alterna_de"):
                    continue
                plan = self._detour_plan(v, main, alt)
                if not plan:
                    continue
                desvios.append((v, alt, plan, plan["delta_h"], plan["extra_km"]))
            if desvios:
                dh = sum(d[3] for d in desvios) / len(desvios)
                dkm = sum(d[4] for d in desvios) / len(desvios)
                extra = [(d[0], d[3]) for d in desvios] + [(v, rem) for v in afect if v not in [d[0] for d in desvios]]
                alternas = sorted({d[1]["ruta_principal"].replace("Alterna ", "") for d in desvios})
                ruta_alt = alternas[0] if len(alternas) == 1 else "rutas alternas (" + " y ".join(alternas) + ")"
                con_retorno = sum(1 for d in desvios if d[2]["tipo"] == "retorno")
                retorno_txt = f" ({con_retorno} deben retornar hasta el punto de desvío)" if con_retorno else ""
                opciones.append(self._opt("desviar", f"Desviar por {ruta_alt}", "fa-diamond-turn-right",
                                          f"{len(desvios)} de {n} unidades toman la ruta alterna real{retorno_txt}: +{dkm:.0f} km en promedio, sin esperar la reapertura.",
                                          horas=dh, costo=sum(max(0, d[4]) for d in desvios) * TARIFA_DESVIO_PEN_KM,
                                          co2=sum(max(0, d[4]) for d in desvios) * CO2_KG_POR_KM_CAMION, tarde=late_after(extra),
                                          n=len(desvios), riesgo=0.3, extra={"desvios": len(desvios)}))
            costeros = [v for v in afect if v.corredor in MODAL_SHIFT and v.estado in ("detenido", "lento", "en_ruta")]
            if costeros and rem > 14:
                ruta_mar = MODAL_SHIFT[costeros[0].corredor]
                mar = geo_data.get_route(ruta_mar, "Marítimo")
                h_mar = route_timing(mar)["total_h"] + 30 if mar else 60
                extra = [(v, h_mar - (route_timing(geo_data.get_route_by_id(v.route_id))["total_h"]
                                      - _hours_at(route_timing(geo_data.get_route_by_id(v.route_id)), v.km))) for v in costeros]
                opciones.append(self._opt("modal", f"Transbordo a cabotaje ({ruta_mar})", "fa-ship",
                                          f"Consolidar la carga de {len(costeros)} unidades en el Callao y enviarla por mar: evita la vía bloqueada y reduce CO₂.",
                                          horas=sum(e for _, e in extra) / len(extra), costo=2600.0 * len(costeros),
                                          co2=-0.45 * sum(v.km_total for v in costeros) * CO2_KG_POR_KM_CAMION,
                                          tarde=late_after(extra), n=len(costeros), riesgo=0.2))
            evitadas = max(1, round(len(ev.route_hits) * rem / 10))  # salidas que se evitaría enviar al bloqueo
            opciones.append(self._opt("reprogramar", "Esperar y congelar nuevos despachos", "fa-calendar-check",
                                      f"Las unidades en tránsito esperan y se congelan las salidas hacia el tramo hasta la reapertura (~{evitadas} despachos que no quedarán atrapados).",
                                      horas=rem if ev.bloquea else rem * 0.3,
                                      costo=max(0.0, STANDBY_PEN_H * rem * n - STANDBY_PEN_H * rem * 0.5 * evitadas * 0.3),
                                      co2=n * rem * 2.2, tarde=late_after(wait_extra), n=n, riesgo=0.4))
        elif ev.alcance == "puerto":
            alt_port = ALT_PORT.get(ev.puerto)
            opciones.append(self._opt("esperar", "Esperar en fondeadero", "fa-anchor",
                                      f"Los {n} buques fondean hasta la reapertura del puerto de {ev.puerto} (~{self._fmt_h(rem)}).",
                                      horas=rem, costo=1250.0 * rem * n, co2=n * rem * 40,
                                      tarde=late_after([(v, rem) for v in afect]), n=n, riesgo=0.45))
            if alt_port in ("Chancay", "Callao"):
                opciones.append(self._opt("puerto_alterno", f"Desviar a {alt_port}", "fa-route",
                                          f"Los buques atracan en {alt_port} y la carga sigue por carretera (Panamericana Norte) a sus almacenes.",
                                          horas=4.0, costo=3800.0 * n, co2=n * 260, tarde=late_after([(v, 4.0) for v in afect]),
                                          n=n, riesgo=0.2))
            opciones.append(self._opt("reprogramar", "Reprogramar zarpes", "fa-calendar-check",
                                      "Se reprograman las ventanas de atraque y se avisa a los clientes con carga crítica.",
                                      horas=rem * 0.8, costo=900.0 * n, co2=0, tarde=late_after([(v, rem * 0.8) for v in afect]),
                                      n=n, riesgo=0.35))
        elif ev.alcance == "modo":
            opciones.append(self._opt("continuar", "Navegar con restricción", "fa-water",
                                      "Los convoyes siguen a media marcha por el canal navegable, con sondaje permanente.",
                                      horas=rem * 0.4, costo=140 * rem * n, co2=0, tarde=late_after([(v, rem * 0.4) for v in afect]),
                                      n=n, riesgo=0.5))
            opciones.append(self._opt("aligerar", "Aligerar carga a chatas menores", "fa-boxes-stacked",
                                      "Transbordo parcial a chatas de menor calado: recupera velocidad a cambio de un sobrecosto.",
                                      horas=rem * 0.15 + 6, costo=4200.0 * n, co2=n * 90,
                                      tarde=late_after([(v, rem * 0.15 + 6) for v in afect]), n=n, riesgo=0.25))
        if not opciones:
            return {"afectados": n, "opciones": [], "recomendada": None}
        self._score(opciones)
        rec = max(opciones, key=lambda o: o["score"])
        for o in opciones:
            o["recomendada"] = o["id"] == rec["id"]
        return {"afectados": n, "valor_carga_pen": round(valor), "tarde_sin_accion": base_tarde,
                "opciones": opciones, "recomendada": rec["id"]}

    def _opt(self, oid, nombre, icon, descripcion, horas, costo, co2, tarde, n, riesgo, extra=None):
        return {"id": oid, "nombre": nombre, "icon": icon, "descripcion": descripcion,
                "delta_horas": round(horas, 1), "costo_pen": round(costo), "co2_kg": round(co2),
                "unidades_tarde": int(tarde), "unidades": int(n), "riesgo": riesgo, **(extra or {})}

    @staticmethod
    def _score(opciones: list) -> None:
        def mm(vals, invert=True):
            lo, hi = min(vals), max(vals)
            return [0.5 if hi == lo else ((hi - x) / (hi - lo) if invert else (x - lo) / (hi - lo)) for x in vals]
        n_otif = mm([o["unidades_tarde"] for o in opciones])
        n_cost = mm([o["costo_pen"] for o in opciones])
        n_time = mm([o["delta_horas"] for o in opciones])
        n_co2 = mm([o["co2_kg"] for o in opciones])
        n_risk = mm([o["riesgo"] for o in opciones])
        for i, o in enumerate(opciones):
            o["score"] = round(100 * (0.40 * n_otif[i] + 0.20 * n_cost[i] + 0.20 * n_time[i] + 0.10 * n_co2[i] + 0.10 * n_risk[i]), 1)

    _div_cache: dict = {}

    def _detour_plan(self, v: Vehicle, main: dict, alt: dict) -> Optional[dict]:
        """Plan de desvío para una unidad: si aún no pasa el punto de desvío entra directo a la
        alterna; si ya lo pasó, RETORNA por la vía principal hasta ese punto (como haría un camión
        detenido antes de un huaico en Chosica) y luego toma la alterna."""
        div = self._divergence(main, alt)
        if v.km <= div:
            lat, lon, _ = geo_data.point_at_km(main, v.km)
            km_alt = geo_data.nearest_km_on_route(alt, lat, lon, max_km=4.0)
            if km_alt is None:
                return None
            extra_km = (alt["cum_km"][-1] - km_alt) - (main["cum_km"][-1] - v.km)
            t_main, t_alt = route_timing(main), route_timing(alt)
            dh = (t_alt["total_h"] - _hours_at(t_alt, km_alt)) - (t_main["total_h"] - _hours_at(t_main, v.km))
            return {"tipo": "directo", "km_alt": km_alt, "extra_km": extra_km, "delta_h": dh, "retorno_km": 0.0}
        retorno = v.km - div
        if retorno > 140:  # demasiado lejos para volver: espera
            return None
        lat, lon, _ = geo_data.point_at_km(main, div)
        km_alt = geo_data.nearest_km_on_route(alt, lat, lon, max_km=4.0) or 0.0
        t_main, t_alt = route_timing(main), route_timing(alt)
        rem_alt_h = t_alt["total_h"] - _hours_at(t_alt, km_alt)
        rem_main_h = t_main["total_h"] - _hours_at(t_main, v.km)
        back_h = _hours_at(t_main, v.km) - _hours_at(t_main, div)
        extra_km = retorno + (alt["cum_km"][-1] - km_alt) - (main["cum_km"][-1] - v.km)
        return {"tipo": "retorno", "km_alt": km_alt, "div_km": div, "extra_km": extra_km,
                "delta_h": back_h + rem_alt_h - rem_main_h, "retorno_km": retorno}

    def _compose_detour(self, v: Vehicle, main: dict, alt: dict, plan: dict) -> dict:
        """Ruta compuesta: tramo de retorno (principal invertida) + alterna desde el punto de desvío."""
        def slice_geom(route, km_a, km_b):
            cum, geom = route["cum_km"], route["geometry"]
            lo, hi = min(km_a, km_b), max(km_a, km_b)
            pts = [list(geo_data.point_at_km(route, lo)[:2])]
            pts += [g for g, c in zip(geom, cum) if lo < c < hi]
            pts.append(list(geo_data.point_at_km(route, hi)[:2]))
            return pts if km_a <= km_b else list(reversed(pts))

        def slice_profile(route, km_a, km_b):
            prof = route["profile"]
            lo, hi = min(km_a, km_b), max(km_a, km_b)
            items = [(k, a, vv) for k, a, vv in zip(prof["km"], prof["alt"], prof["v"]) if lo <= k <= hi]
            if km_a > km_b:
                items = list(reversed(items))
            return items

        back_geom = slice_geom(main, v.km, plan["div_km"])
        alt_geom = slice_geom(alt, plan["km_alt"], alt["cum_km"][-1])
        geom = back_geom + alt_geom[1:]
        cum = [0.0]
        for i in range(1, len(geom)):
            cum.append(cum[-1] + geo_data.haversine_km(geom[i - 1][0], geom[i - 1][1], geom[i][0], geom[i][1]))
        # perfil compuesto re-indexado desde 0
        items = slice_profile(main, v.km, plan["div_km"])
        prof_km, prof_alt, prof_v = [], [], []
        base = 0.0
        prev_k = None
        for k, a, vv in items:
            base = base if prev_k is None else base + abs(k - prev_k)
            prev_k = k
            prof_km.append(round(base, 2)); prof_alt.append(a); prof_v.append(vv)
        offset = prof_km[-1] if prof_km else 0.0
        for k, a, vv in slice_profile(alt, plan["km_alt"], alt["cum_km"][-1]):
            kk = offset + (k - plan["km_alt"])
            if prof_km and kk <= prof_km[-1]:
                continue
            prof_km.append(round(kk, 2)); prof_alt.append(a); prof_v.append(vv)
        if len(prof_km) < 2:
            prof_km, prof_alt, prof_v = [0.0, cum[-1]], [0, 0], [40, 40]
        scale = cum[-1] / prof_km[-1] if prof_km[-1] else 1.0
        prof_km = [round(k * scale, 2) for k in prof_km]
        return {"id": f"CUSTOM:{v.id}", "corredor": main["corredor"], "origen": main["origen"], "destino": main["destino"],
                "modo": "Carretero", "ruta_principal": f"Retorno + {alt['ruta_principal']}", "alterna_de": main["corredor"],
                "geometry": [[round(p[0], 5), round(p[1], 5)] for p in geom], "cum_km": [round(c, 3) for c in cum],
                "km": cum[-1], "profile": {"km": prof_km, "alt": prof_alt, "v": prof_v},
                "alt_max": max(prof_alt), "alt_min": min(prof_alt), "ascenso_total_m": 0}

    def _divergence(self, main: dict, alt: dict) -> float:
        key = (main["id"], alt["id"])
        if key not in self._div_cache:
            self._div_cache[key] = geo_data.divergence_km(main, alt)
        return self._div_cache[key]

    def options_for(self, event_id: int) -> Optional[dict]:
        with self._lock:
            ev = self._events.get(event_id)
            return self._options(ev) if ev else None

    def apply_decision(self, event_id: int, option_id: str) -> Optional[dict]:
        with self._lock:
            ev = self._events.get(event_id)
            if not ev:
                return None
            return self._apply_option(ev, option_id)

    def _apply_option(self, ev: LiveEvent, option_id: str, automatico: bool = False) -> Optional[dict]:
        if ev.decision:  # una decisión por evento: evita aplicarla dos veces (doble clic, IA autónoma + usuario)
            return ev.decision
        opts = self._options(ev)
        opt = next((o for o in opts["opciones"] if o["id"] == option_id), None)
        if not opt:
            return None
        afect = self._affected(ev)
        detalle = ""
        if option_id == "desviar":
            n = n_ret = 0
            for v in afect:
                alt = geo_data.get_route(v.corredor, "Carretero", alterna=True)
                main = geo_data.get_route_by_id(v.route_id)
                if not alt or v.desvio or not main or main.get("alterna_de"):
                    continue
                plan = self._detour_plan(v, main, alt)
                if not plan:
                    continue
                if plan["tipo"] == "directo":
                    v.route_id, v.km, v.km_total = alt["id"], plan["km_alt"], alt["cum_km"][-1]
                else:
                    v.custom_route = self._compose_detour(v, main, alt, plan)
                    v.route_id, v.km, v.km_total = v.custom_route["id"], 0.0, v.custom_route["cum_km"][-1]
                    n_ret += 1
                v.desvio = True
                v.evento_id = None
                v.cola_evento, v.cola_km = None, None
                v.estado = "desviado"
                extra_km = max(0.0, plan["extra_km"])
                v.costo_extra += extra_km * TARIFA_DESVIO_PEN_KM
                self._stats["costo_contingencia"] += extra_km * TARIFA_DESVIO_PEN_KM
                n += 1
            ruta = opt["nombre"].replace("Desviar por ", "")
            detalle = f"{n} unidades desviadas por {ruta}" + (f" ({n_ret} retornan hasta el punto de desvío)." if n_ret else ".")
        elif option_id == "modal":
            costeros = [v for v in afect if v.corredor in MODAL_SHIFT]
            ruta_mar = MODAL_SHIFT[costeros[0].corredor] if costeros else None
            for v in costeros:
                del self._vehicles[v.id]
            if ruta_mar:
                buque = self._spawn_vehicle("Marítimo", corredor=ruta_mar) or self._spawn_vehicle("Marítimo")
                if buque:
                    buque.tipo_carga = f"Carga consolidada de {len(costeros)} unidades"
                    buque.prioridad = "Crítica / Estratégico"
                    detalle = f"Carga de {len(costeros)} camiones consolidada en el {buque.nombre} ({ruta_mar})."
            self._stats["costo_contingencia"] += opt["costo_pen"]
        elif option_id == "puerto_alterno":
            alt_port = ALT_PORT.get(ev.puerto)
            hs_alt = self._hotspot(PORT_HOTSPOT[alt_port])
            for v in afect:
                route = self._route_of(v)
                # sigue la ruta costera del cabotaje hasta la altura del puerto alterno y entra a él
                total = route["cum_km"][-1]
                k_cut = None
                best = 1e9
                for (la, lo), c in zip(route["geometry"], route["cum_km"]):
                    d = geo_data.haversine_km(la, lo, hs_alt["lat"], hs_alt["lon"])
                    if d < best:
                        best, k_cut = d, c
                if k_cut is None or k_cut <= v.km + 1 or best > 120:
                    k_cut = total
                pts = [list(geo_data.point_at_km(route, v.km)[:2])]
                pts += [g for g, c in zip(route["geometry"], route["cum_km"]) if v.km < c < k_cut]
                pts.append(list(geo_data.point_at_km(route, k_cut)[:2]))
                if k_cut >= total - 1 and best > 25:  # el puerto alterno queda más allá del destino original
                    pts.append([(pts[-1][0] + hs_alt["lat"]) / 2, min(pts[-1][1], hs_alt["lon"]) - 0.2])
                pts.append([hs_alt["lat"], hs_alt["lon"]])
                cum = [0.0]
                for i in range(1, len(pts)):
                    cum.append(cum[-1] + geo_data.haversine_km(*pts[i - 1], *pts[i]))
                v.custom_route = {"id": f"CUSTOM:{v.id}", "corredor": f"{route['origen']} - {alt_port}", "origen": route["origen"],
                                  "destino": alt_port, "modo": "Marítimo", "ruta_principal": f"Desvío a {alt_port}",
                                  "geometry": pts, "cum_km": cum, "km": cum[-1],
                                  "profile": {"km": [0, cum[-1]], "alt": [0, 0], "v": [0, 0]}}
                v.km, v.km_total, v.destino_override, v.desvio = 0.0, cum[-1], alt_port, True
                v.evento_id = None
            self._stats["costo_contingencia"] += opt["costo_pen"]
            detalle = f"{len(afect)} buques desviados a {alt_port}; la última milla sale por carretera."
        elif option_id == "reprogramar":
            for v in afect:
                self._holds[v.corredor] = ev.fin
            for rid in ev.route_hits:
                r = geo_data.get_route_by_id(rid)
                if r:
                    self._holds[r["corredor"]] = ev.fin
            detalle = f"Nuevos despachos congelados en {len(set(self._holds))} corredores hasta la reapertura."
        elif option_id == "aligerar":
            ev.factor = 0.8
            self._stats["costo_contingencia"] += opt["costo_pen"]
            detalle = "Transbordo a chatas menores: los convoyes recuperan velocidad (80%)."
        else:
            detalle = opt["descripcion"]
        salvados = max(0, opts["tarde_sin_accion"] - opt["unidades_tarde"])
        self._stats["decisiones"] += 1
        self._stats["otif_salvados"] += salvados
        ev.decision = {"opcion": option_id, "nombre": opt["nombre"], "automatico": automatico,
                       "aplicada_en": self._sim_time.isoformat(), "detalle": detalle}
        quien = "IA autónoma" if automatico else "Decisión aprobada"
        self._push_feed("decision", "Media", f"{quien}: {opt['nombre']} — {detalle}"
                        + (f" OTIF protegido en {salvados} entregas." if salvados else ""), None, ev.id)
        return ev.decision

    # ------------------------------------------------------------------ escenarios y control
    def run_scenario(self, scenario_id: str) -> Optional[dict]:
        sc = SCENARIOS.get(scenario_id)
        if not sc:
            return None
        with self._lock:
            creados = []
            for tipo, ref, horas in sc["eventos"]:
                if isinstance(ref, tuple):
                    lat, lon, lugar = ref
                    puerto = None
                else:
                    hs = self._hotspot(ref)
                    lat, lon, lugar = hs["lat"], hs["lon"], hs["nombre"]
                    puerto = next((p for p, h in PORT_HOTSPOT.items() if h == ref), None)
                ev = self.create_event(tipo, lat, lon, horas=horas, lugar=lugar, origen="escenario", puerto=puerto)
                if ev:
                    creados.append(ev)
                    self._seed_traffic(ev)
            self._push_feed("decision", "Alta", f"Escenario activado: {sc['titulo']}. La IA evalúa opciones de respuesta.", None)
            return {"escenario": scenario_id, "titulo": sc["titulo"], "eventos": [e.id for e in creados]}

    def _seed_traffic(self, ev: LiveEvent) -> None:
        """Asegura flota real aproximándose al evento para que su efecto se vea en el mapa."""
        if ev.alcance == "via":
            rids = [rid for rid in ev.route_hits if "|ALT" not in rid]
            self._rnd.shuffle(rids)
            for rid in rids[:3]:
                r = geo_data.get_route_by_id(rid)
                km_ev = ev.route_hits[rid]
                for _ in range(2):
                    km0 = max(0.0, km_ev - self._rnd.uniform(25, 90))
                    self._spawn_vehicle("Carretero", corredor=r["corredor"], km_start=km0, route_id=rid)
        elif ev.alcance == "puerto":
            for r in geo_data.all_routes():
                if r["modo"] == "Marítimo" and r["destino"] == ev.puerto:
                    self._spawn_vehicle("Marítimo", corredor=r["corredor"], km_start=max(0.0, r["cum_km"][-1] - self._rnd.uniform(60, 160)))
        elif ev.alcance == "modo":
            for r in geo_data.all_routes():
                if r["modo"] == "Fluvial":
                    self._spawn_vehicle("Fluvial", corredor=r["corredor"], km_start=self._rnd.uniform(40, 300))

    def control(self, speed=None, paused=None, autonomo=None) -> dict:
        with self._lock:
            if speed is not None and int(speed) in ALLOWED_SPEEDS:
                self.speed = int(speed)
            if paused is not None:
                self.paused = bool(paused)
            if autonomo is not None:
                self.autonomo = bool(autonomo)
                self._push_feed("decision", "Baja", "Modo IA autónoma " + ("ACTIVADO: la IA aplicará la mejor opción en cada evento."
                                                                         if self.autonomo else "desactivado: las decisiones requieren aprobación."), None)
            return {"speed": self.speed, "paused": self.paused, "autonomo": self.autonomo}

    def reset(self) -> None:
        with self._lock:
            self._reset_state()
            self._spawn_initial_fleet()
            self._push_feed("operacion", "Baja", "Gemelo digital reiniciado.", None)

    # ------------------------------------------------------------------ utilidades
    def _eta(self, v: Vehicle) -> datetime:
        route = self._route_of(v)
        if v.custom_route and v.modo != "Carretero":
            rem_h = (v.km_total - v.km) / 22.0
        else:
            t = route_timing(route)
            rem_h = max(0.0, t["total_h"] - _hours_at(t, v.km)) / max(v.estilo, 0.5)
        if v.modo == "Carretero":
            rem_h += 0.5 * math.floor((v.horas_conduccion + rem_h) / 5.0)
        if v.evento_id and v.evento_id in self._events:
            ev = self._events[v.evento_id]
            if ev.bloquea or ev.alcance == "puerto":
                rem_h += self._remaining_ev_h(ev)
            else:
                rem_h += self._remaining_ev_h(ev) * (1 - ev.factor) * 0.5
        if v.incidente:
            rem_h += max(0.0, (v.incidente["fin"] - self._sim_time).total_seconds() / 3600)
        if v.descanso_hasta:
            rem_h += max(0.0, (v.descanso_hasta - self._sim_time).total_seconds() / 3600)
        return self._sim_time + timedelta(hours=rem_h)

    @staticmethod
    def _fmt_h(h: float) -> str:
        if h < 1:
            return f"{h * 60:.0f} min"
        if h < 48:
            return f"{h:.1f} h"
        return f"{h / 24:.1f} días"

    def _push_feed(self, categoria, severidad, texto, vehicle_id, event_id=None) -> None:
        self._feed.append(FeedEntry(id=self._next_feed_id, ts=datetime.now().strftime("%H:%M:%S"),
                                    sim_ts=self._sim_time.strftime("%d/%m %H:%M"), categoria=categoria,
                                    severidad=severidad, texto=texto, vehicle_id=vehicle_id, event_id=event_id))
        self._next_feed_id += 1

    # ------------------------------------------------------------------ lectura
    def snapshot(self, since_id: int = 0) -> dict:
        with self._lock:
            vehicles = [self._vehicle_to_dict(v) for v in self._vehicles.values()]
            return {
                "server_time": datetime.now().isoformat(),
                "sim_time": self._sim_time.isoformat(),
                "speed": self.speed, "paused": self.paused, "autonomo": self.autonomo,
                "tick": self._tick,
                "started_at": self._started_at.isoformat(),
                "vehicles": vehicles,
                "events": [self._event_to_dict(e) for e in sorted(self._events.values(), key=lambda e: e.id)],
                "kpis": self._compute_kpis(vehicles),
                "nodos": self._nodes_state(),
                "feed": [self._feed_to_dict(f) for f in self._feed if f.id > since_id],
                "last_id": self._feed[-1].id if self._feed else since_id,
            }

    def summary(self) -> dict:
        """Versión liviana del estado (KPIs + eventos activos) para el pulso del Resumen RANSA."""
        orden = {"Critica": 0, "Alta": 1, "Media": 2, "Baja": 3}
        with self._lock:
            vehicles = [self._vehicle_to_dict(v) for v in self._vehicles.values()]
            eventos = sorted(self._events.values(), key=lambda e: (orden.get(e.severidad, 9), -e.id))
            return {
                "sim_time": self._sim_time.isoformat(),
                "kpis": self._compute_kpis(vehicles),
                "eventos": [{"id": e.id, "titulo": e.titulo, "lugar": e.lugar, "severidad": e.severidad, "icon": e.icon}
                            for e in eventos],
            }

    def _vehicle_to_dict(self, v: Vehicle) -> dict:
        route = self._route_of(v)
        lat, lon, heading = geo_data.point_at_km(route, v.km)
        origen = route["origen"] if route["modo"] != "Aéreo" else "Lima"
        destino = v.destino_override or route["destino"]
        oc, dc = geo_data.get_coords(origen) or {}, geo_data.get_coords(destino) or {}
        eta = self._eta(v)
        ev = self._events.get(v.evento_id) if v.evento_id else None
        evento = None
        if v.incidente:
            evento = {k: v.incidente[k] for k in ("tipo", "titulo", "categoria", "severidad", "icon", "efecto")}
        elif ev:
            evento = {"tipo": ev.tipo, "titulo": ev.titulo, "categoria": ev.categoria, "severidad": ev.severidad,
                      "icon": ev.icon, "efecto": "detenido" if ev.bloquea else "lento", "event_id": ev.id}
        return {
            "id": v.id, "nombre": v.nombre, "tipo_transporte": v.modo, "tipo_vehiculo": v.tipo_vehiculo,
            "tipo_carga": v.tipo_carga, "corredor": v.corredor, "id_viaje": v.id_viaje, "sector_cliente": v.sector,
            "linea": v.linea, "combustible_tipo": v.combustible_tipo,
            "prioridad_cliente": v.prioridad, "nivel_riesgo": v.nivel_riesgo, "prob_riesgo": round(v.prob_riesgo, 1),
            "estado": v.estado, "route_id": route["id"], "km": round(v.km, 2), "km_total": round(v.km_total, 1),
            "t": round(v.km / v.km_total, 4) if v.km_total else 0, "v_kmh": v.v_kmh,
            "lat": round(lat, 5), "lon": round(lon, 5), "heading": round(heading, 1),
            "alt": round(getattr(v, "_alt", 0.0)), "desvio": v.desvio,
            "custom_route": {"geometry": v.custom_route["geometry"], "cum_km": v.custom_route["cum_km"],
                             "profile": {k: v.custom_route["profile"][k] for k in ("km", "alt")}} if v.custom_route else None,
            "origen": {"nombre": origen, "lat": oc.get("lat"), "lon": oc.get("lon")},
            "destino": {"nombre": destino, "lat": dc.get("lat"), "lon": dc.get("lon")},
            "salida": v.salida.isoformat(), "eta": eta.isoformat(), "eta_prog": v.eta_prog.isoformat(),
            "retraso_h": round(max(0.0, (eta - v.eta_prog).total_seconds() / 3600), 2),
            "eta_horas": round(max(0.0, (eta - self._sim_time).total_seconds() / 3600), 1),
            "otif_proyectado": eta <= v.eta_prog,
            "telemetria": {"combustible_pct": round(v.combustible), "temp_motor_c": round(v.temp_motor, 1),
                           "reefer_c": round(v.reefer, 1) if v.reefer is not None else None,
                           "reefer_set_c": v.reefer_set, "horas_conduccion": round(v.horas_conduccion, 1)},
            "valor_carga_pen": round(v.valor_carga), "costo_extra_pen": round(v.costo_extra), "co2_kg": round(v.co2_kg),
            "evento": evento,
            "control_offset": 0,
        }

    def _event_to_dict(self, e: LiveEvent) -> dict:
        opts = self._options(e) if e.alcance != "unidad" else {"afectados": 0, "opciones": [], "recomendada": None}
        return {
            "id": e.id, "tipo": e.tipo, "titulo": e.titulo, "categoria": e.categoria, "severidad": e.severidad,
            "icon": e.icon, "alcance": e.alcance, "lat": e.lat, "lon": e.lon, "lugar": e.lugar, "radio_km": e.radio_km,
            "bloquea": e.bloquea, "factor": e.factor, "origen": e.origen, "puerto": e.puerto,
            "inicio": e.inicio.isoformat(), "fin": e.fin.isoformat(),
            "restante_h": round(self._remaining_ev_h(e), 1),
            "rutas": sorted({geo_data.get_route_by_id(r)["corredor"] for r in e.route_hits}),
            "route_hits": {rid: round(km, 1) for rid, km in e.route_hits.items()},
            "afectados": opts["afectados"], "opciones": opts["opciones"], "recomendada": opts["recomendada"],
            "tarde_sin_accion": opts.get("tarde_sin_accion", 0), "valor_carga_pen": opts.get("valor_carga_pen", 0),
            "decision": e.decision,
        }

    def _feed_to_dict(self, f: FeedEntry) -> dict:
        return {"id": f.id, "ts": f.ts, "sim_ts": f.sim_ts, "categoria": f.categoria, "severidad": f.severidad,
                "texto": f.texto, "vehicle_id": f.vehicle_id, "event_id": f.event_id}

    def _nodes_state(self) -> list:
        out = []
        for name in ("Callao", "Chancay", "Paita", "Matarani", "Ilo", "Salaverry", "Lurín", "Lima", "Arequipa", "Trujillo",
                     "Iquitos", "Yurimaguas", "Pucallpa", "Huancayo", "Cusco", "Piura"):
            c = geo_data.get_coords(name)
            if not c:
                continue
            llegando = sum(1 for v in self._vehicles.values()
                           if (v.destino_override or self._route_of(v)["destino"]) == name and v.km_total - v.km < 60)
            cola = sum(1 for v in self._vehicles.values()
                       if (v.destino_override or self._route_of(v)["destino"]) == name and v.estado in ("fondeado", "esperando"))
            cerrado = name in self._port_closed
            seed = (hash(name) % 17) + self._sim_time.hour
            ocupacion = 58 + (seed % 23) + min(12, llegando * 3)
            out.append({"nombre": name, "lat": c["lat"], "lon": c["lon"], "es_puerto": c["es_puerto"],
                        "es_fluvial": c["es_fluvial"], "estado": "cerrado" if cerrado else "congestionado" if cola >= 2 else "operativo",
                        "llegando": llegando, "en_cola": cola, "ocupacion_pct": min(99, ocupacion)})
        return out

    def _compute_kpis(self, vehicles: list) -> dict:
        total = len(vehicles)
        afectados = [v for v in vehicles if v["evento"]]
        en_mov = [v for v in vehicles if v["estado"] in ("en_ruta", "lento", "desviado")]
        desvios = [v for v in vehicles if v["desvio"]]
        a_tiempo = [v for v in vehicles if v["otif_proyectado"]]
        tarde = [v for v in vehicles if not v["otif_proyectado"]]
        etas = [v["eta_horas"] for v in vehicles]
        avg_prob = sum(v["prob_riesgo"] for v in vehicles) / total if total else 0
        incident_ratio = len(afectados) / total * 100 if total else 0
        criticos = [v for v in tarde if v["prioridad_cliente"] == "Crítica / Estratégico"]
        pend = [e for e in self._events.values() if e.decision is None and e.alcance != "unidad"
                and e.severidad in ("Alta", "Critica")]
        entregas = self._stats["entregas"]
        co2_t = (self._stats["co2_kg"] + sum(v["co2_kg"] for v in vehicles)) / 1000
        return {
            "operaciones_activas": total,
            "vehiculos_en_operacion": len(en_mov),
            "incidentes_actuales": len(self._events) + sum(1 for v in self._vehicles.values() if v.incidente),
            "vehiculos_afectados": len(afectados),
            "rutas_afectadas": len({v["corredor"] for v in afectados}),
            "clientes_impactados": len(criticos),
            "desvios_activos": len(desvios),
            "eta_promedio_h": round(sum(etas) / len(etas), 1) if etas else 0,
            "alertas_ia": len(pend),
            "riesgo_global_pct": min(100, round(0.7 * avg_prob + 0.3 * incident_ratio, 1)),
            "otif_proyectado_pct": round(len(a_tiempo) / total * 100, 1) if total else 0,
            "carga_en_riesgo_pen": round(sum(v["valor_carga_pen"] for v in tarde)),
            "entregas": entregas,
            "otif_real_pct": round(self._stats["entregas_a_tiempo"] / entregas * 100, 1) if entregas else None,
            "co2_t": round(co2_t, 1),
            "co2_en_curso_t": round(sum(v["co2_kg"] for v in vehicles) / 1000, 1),
            "costo_contingencia_pen": round(self._stats["costo_contingencia"]),
            "decisiones": self._stats["decisiones"],
            "otif_salvados": self._stats["otif_salvados"],
        }


_engine = LiveOperationsEngine()


def get_engine() -> LiveOperationsEngine:
    return _engine


if hasattr(os, "register_at_fork"):  # Unix (Render); en Windows no hay fork
    os.register_at_fork(after_in_child=_engine._after_fork_in_child)


def start_engine(app) -> None:
    _engine.start(app)


def list_scenarios() -> list:
    return [{"id": k, "titulo": s["titulo"], "icon": s["icon"], "descripcion": s["descripcion"]} for k, s in SCENARIOS.items()]


def list_event_types() -> list:
    return [{"tipo": k, "titulo": e["titulo"], "icon": e["icon"], "severidad": e["severidad"], "alcance": e["alcance"]}
            for k, e in EVENTS.items() if e["alcance"] != "unidad"]
