"""
¿De dónde se extrae la data? — escucha SIMULADA de fuentes abiertas que alimenta la probabilidad de contingencia.

La plataforma parte de la probabilidad base de cada evento (modelo histórico de Riesgo 24 h y escenarios de
48 h) y la actualiza con las señales que "extrae" de TikTok, Facebook, Instagram, noticieros, reportes
policiales e institutos (SENAMHI, INDECI/COEN, Provías, DHN). Todo es SIMULADO: cuentas enmascaradas, medios
genéricos y avisos de ejemplo; ninguna publicación es real.

Matemática (transparente y auditable):

    m_s = Σ_i e^(−Δt_i / τ) · (1 + ln r_i)      menciones de la fuente s ponderadas por recencia (τ = 6 h) y por
                                                cuántas veces se repite la misma noticia (r_i, tras deduplicar)
    logit(p) = logit(p₀) + β · Σ_s c_s · w_s · ln(1 + m_s)
        p₀   probabilidad base del modelo histórico (24 h o 48 h)
        w_s  credibilidad de la fuente (oficial 1.0 · policía 0.9 · noticieros 0.7 · Facebook 0.45 ·
             Instagram 0.4 · TikTok 0.35)
        c_s  0.6 para redes sociales cuando ninguna fuente oficial ni policial confirma (rumor); 1.0 si no
        β    0.22 — y la probabilidad final se limita a 97 %

Las publicaciones se generan por hora con una semilla fija (evento + hora): el pasado no cambia entre consultas
y, a medida que avanza el reloj, "llegan" publicaciones nuevas, como en una escucha real.
"""
import hashlib
import math
import random
import time
from datetime import datetime, timedelta, timezone

from app.services import geo_data

PERU_TZ = timezone(timedelta(hours=-5))
BETA = 0.22
TAU_H = 6.0
VENTANA_H = 12
P_MAX = 0.97
PENALIDAD_RUMOR = 0.6
CACHE_BASE_S = 300

# En orden de credibilidad: el aporte de cada fuente se mide sobre lo que ya explicaron las anteriores.
FUENTES = [
    {"id": "oficial", "nombre": "Institutos y meteorología", "detalle": "SENAMHI · INDECI/COEN · Provías · DHN",
     "icon": "fa-solid fa-cloud-sun-rain", "color": "#3d63ff", "peso": 1.00, "ritmo_min": 0.5, "red": False},
    {"id": "policia", "nombre": "Reportes policiales", "detalle": "PNP · Policía de Carreteras · SUTRAN",
     "icon": "fa-solid fa-shield-halved", "color": "#0d9488", "peso": 0.90, "ritmo_min": 1.1, "red": False},
    {"id": "medios", "nombre": "Noticieros", "detalle": "TV, radio y diarios regionales",
     "icon": "fa-solid fa-tv", "color": "#f97316", "peso": 0.70, "ritmo_min": 6.0, "red": False},
    {"id": "facebook", "nombre": "Facebook", "detalle": "Grupos de transportistas y de vecinos",
     "icon": "fa-brands fa-facebook", "color": "#1877f2", "peso": 0.45, "ritmo_min": 140.0, "red": True},
    {"id": "instagram", "nombre": "Instagram", "detalle": "Páginas de noticias locales, reels e historias",
     "icon": "fa-brands fa-instagram", "color": "#c13584", "peso": 0.40, "ritmo_min": 95.0, "red": True},
    {"id": "tiktok", "nombre": "TikTok", "detalle": "Videos de conductores y vecinos",
     "icon": "fa-brands fa-tiktok", "color": "#fe2c55", "peso": 0.35, "ritmo_min": 210.0, "red": True},
]
FUENTE = {f["id"]: f for f in FUENTES}

# Publicaciones relevantes esperadas en 12 h cuando la señal es máxima, según el tipo de evento.
PERFIL = {
    "geologico": {"oficial": 3, "policia": 2, "medios": 4, "facebook": 8, "instagram": 6, "tiktok": 12},
    "hidrologico": {"oficial": 3, "policia": 1, "medios": 4, "facebook": 7, "instagram": 6, "tiktok": 10},
    "social": {"oficial": 1, "policia": 3, "medios": 5, "facebook": 13, "instagram": 5, "tiktok": 14},
    "seguridad": {"oficial": 0.4, "policia": 4, "medios": 3, "facebook": 11, "instagram": 3, "tiktok": 7},
    "infraestructura": {"oficial": 2, "policia": 1, "medios": 2, "facebook": 5, "instagram": 3, "tiktok": 5},
    "accidentalidad": {"oficial": 1, "policia": 3, "medios": 3, "facebook": 6, "instagram": 4, "tiktok": 8},
}
CLAVES_LUGAR = {
    "geologico": ("huaico", "derrumbe", "deslizamiento", "caída de rocas"),
    "hidrologico": ("desborde", "inundaci", "vaciante", "estiaje"),
    "social": ("paro", "bloqueo"),
    "seguridad": ("extorsión", "robo"),
    "infraestructura": ("derrumbe", "congestión", "restricciones"),
    "accidentalidad": ("neblina", "accidentalidad", "heladas", "nevadas"),
}
RIOS = [("Huancayo", "Rímac"), ("Cerro de Pasco", "Rímac"), ("Huánuco", "Huallaga"), ("Pucallpa", "Aguaytía"),
        ("Yurimaguas", "Huallaga"), ("Tarapoto", "Mayo"), ("Paita", "Chira"), ("Piura", "Piura"), ("Tumbes", "Tumbes"),
        ("Chiclayo", "La Leche"), ("Trujillo", "Moche"), ("Chimbote", "Santa"), ("Huaraz", "Santa"), ("Cajamarca", "Jequetepeque"),
        ("Ica", "Ica"), ("Pisco", "Pisco"), ("Matarani", "Tambo"), ("Arequipa", "Chili"), ("Cusco", "Vilcanota"),
        ("Puerto Maldonado", "Inambari"), ("Iquitos", "Marañón"), ("Juliaca", "Coata"), ("Puno", "Ilave"), ("Ayacucho", "Pampas"),
        ("Tacna", "Caplina"), ("Moquegua", "Moquegua"), ("Lima", "Rímac")]

# ------------------------------------------------------------------ plantillas (todo simulado)
TEXTOS = {
    "geologico": {
        "tiktok": ["Así baja la quebrada en {corto} 😨 la pista ya está tapada de lodo #huaico #{tag}",
                   "Atentos choferes 🚛 no pasen por {corto}, el cerro se está viniendo abajo #{tag} #lluvias",
                   "Otra vez huaico en {corto}, carros varados desde la madrugada 😓 #{tag}"],
        "facebook": ["Compañeros, en {corto} la policía no deja pasar, dicen que cayó huaico. ¿Alguien que esté por la zona?",
                     "URGENTE: material en la vía a la altura de {corto}. Eviten salir de noche por {ruta}."],
        "instagram": ["🔴 Reportan huaico en {corto}: tránsito interrumpido en {ruta}. Más información en nuestras historias.",
                      "Lluvias intensas activan quebradas en {dep}. Vecinos de {corto} piden maquinaria."],
        "medios": ["Huaico interrumpe el tránsito en {ruta} a la altura de {corto}",
                   "Lluvias en {dep}: quebradas activadas ponen en riesgo el tránsito por {ruta}"],
        "policia": ["Parte: tránsito restringido en {ruta} km {km} por caída de huaico. Personal en la zona.",
                    "Se dispone desvío y control de paso en {corto} por material de deslizamiento en la vía."],
        "oficial": [("SENAMHI", "Aviso meteorológico N.° {n}: precipitaciones de moderada a fuerte intensidad en la sierra de {dep} · nivel {nivel}."),
                    ("INDECI · COEN", "Reporte de emergencia: activación de quebradas en {corto}; vías afectadas en {dep}."),
                    ("Provías Nacional", "Estado de vías: tránsito restringido en {ruta} km {km} por huaico; maquinaria en camino.")],
    },
    "hidrologico": {
        "tiktok": ["El río {rio} ya está llegando a la carretera en {corto} 🌊 #{tag} #lluvias",
                   "Miren cómo está el río {rio} hoy 😳 los camiones no pasan #{tag}"],
        "facebook": ["Vecinos de {corto}: el río {rio} sigue creciendo, la vía está con agua. Choferes tomen precauciones.",
                     "¿Alguien sabe si está pasando la carga por {corto}? Dicen que el río {rio} se desbordó."],
        "instagram": ["🌊 Crecida del río {rio} pone en alerta a {corto}. Tránsito restringido en {ruta}.",
                      "Así luce {ruta} a la altura de {corto} tras la crecida del río {rio}."],
        "medios": ["Crecida del río {rio} afecta el tránsito por {ruta} en {dep}",
                   "Desborde en {corto}: autoridades evalúan cerrar el paso de vehículos pesados"],
        "policia": ["Parte: vía inundada en {ruta} km {km}; se restringe el paso de vehículos pesados.",
                    "Se reporta agua sobre la calzada en {corto}; tránsito a una vía con apoyo policial."],
        "oficial": [("SENAMHI · Hidrología", "Aviso hidrológico: incremento del caudal del río {rio} · umbral {nivel}."),
                    ("INDECI · COEN", "Reporte: desborde en {corto}; vías y viviendas afectadas en {dep}."),
                    ("Provías Nacional", "Tránsito restringido por inundación en {ruta} km {km}.")],
    },
    "social": {
        "tiktok": ["Mañana paro en {corto} ✊ ya están juntando piedras en la vía #paro #{tag}",
                   "Así está {corto} ahorita, bloqueado de lado a lado 😤 #{tag} #paro"],
        "facebook": ["COMUNICADO: los gremios de {dep} acatarán paro indefinido desde mañana. Habrá bloqueo en {corto}.",
                     "Choferes, eviten {ruta}: anuncian bloqueo en {corto} desde las 5 a. m."],
        "instagram": ["📢 Anuncian paro regional en {dep}: puntos de bloqueo en {corto} y alrededores.",
                      "Comerciantes de {corto} se suman al paro. Transporte de carga, a la expectativa."],
        "medios": ["Gremios anuncian paro en {dep}: se prevén bloqueos en {ruta}",
                   "Bloqueo en {corto} deja varados a decenas de camiones de carga"],
        "policia": ["Parte: concentración de manifestantes en {corto}; se evalúa el restablecimiento del tránsito.",
                    "Se reporta piedras y llantas en la vía en {ruta} km {km}; tránsito interrumpido."],
        "oficial": [("Defensoría del Pueblo", "Reporte de conflictos sociales: anuncio de paro en {dep} con posibles bloqueos de vías."),
                    ("Provías Nacional", "Tránsito interrumpido por manifestantes en {ruta} km {km}.")],
    },
    "seguridad": {
        "tiktok": ["Ojo transportistas ⚠️ asaltos en {corto} de madrugada, ya van tres esta semana #{tag}",
                   "Nos cerraron el paso en {corto} y nos pidieron 'cupo' 😡 #extorsión #{tag}"],
        "facebook": ["Alerta en el grupo: otro robo de carga en {corto}, se llevaron la mercadería de un furgón. Viajen en convoy.",
                     "Compañeros, reportan extorsión a camioneros en {corto}. No se detengan en la zona."],
        "instagram": ["🚨 Denuncian nueva modalidad de robo a camiones de carga en {corto}.",
                      "Transportistas de {dep} exigen más resguardo policial en {ruta}."],
        "medios": ["Transportistas denuncian extorsiones en {corto}",
                   "Robo de carga en {ruta}: delincuentes interceptan camión en {corto}"],
        "policia": ["Denuncia registrada: robo de carga en {ruta} km {km}. Se activa plan de patrullaje.",
                    "Parte: intervención en {corto} tras reporte de extorsión a transportistas."],
        "oficial": [("Ministerio del Interior", "Se refuerza el patrullaje en accesos de {dep} por extorsión al transporte.")],
    },
    "infraestructura": {
        "tiktok": ["El puente en {corto} está rajado, solo pasa un carril 😬 #{tag}",
                   "Hueco gigante en {ruta} a la altura de {corto} 😱 #{tag}"],
        "facebook": ["Atención: trabajos en {corto}, pasan por turnos. La cola ya pasa el kilómetro.",
                     "La vía en {corto} está en pésimo estado, dos camiones se quedaron atascados."],
        "instagram": ["🚧 Trabajos de emergencia en {corto}: tránsito por un solo carril en {ruta}.",
                      "Así está {ruta} a la altura de {corto}. Vecinos piden mantenimiento."],
        "medios": ["Daños en {ruta} obligan a pasar por un solo carril en {corto}",
                   "Provías inicia trabajos de emergencia en {corto}"],
        "policia": ["Parte: tránsito regulado en {ruta} km {km} por trabajos en la vía.",
                    "Se controla el paso por turnos en {corto}; esperas de hasta dos horas."],
        "oficial": [("Provías Nacional", "Tránsito restringido por trabajos de emergencia en {ruta} km {km}."),
                    ("SUTRAN", "Restricción de carga pesada en {corto} por estado de la vía.")],
    },
    "accidentalidad": {
        "tiktok": ["Neblina total en {corto}, cero visibilidad 🌫️ vayan despacio #{tag}",
                   "Accidente en {corto}, un tráiler volcado bloquea la vía 😓 #{tag}"],
        "facebook": ["Choferes: neblina muy densa en {corto}, ya hubo un choque. Prendan las luces.",
                     "Accidente en {ruta} km {km}, hay cola de varios kilómetros."],
        "instagram": ["⚠️ Accidente en {corto}: tránsito restringido en {ruta}.",
                      "Neblina en {corto}: conductores reportan baja visibilidad esta noche."],
        "medios": ["Choque múltiple en {corto} complica el tránsito en {ruta}",
                   "Neblina y pista mojada: alerta en {corto} por accidentes"],
        "policia": ["Parte: accidente de tránsito en {ruta} km {km}; un carril habilitado.",
                    "Se reporta despiste de vehículo de carga en {corto}; personal en la zona."],
        "oficial": [("SENAMHI", "Pronóstico: neblina densa y baja visibilidad en {dep} durante la madrugada."),
                    ("SUTRAN", "Recomendación: reducir la velocidad en {corto} por alta accidentalidad.")],
    },
}
CORTO = {"marcapata": "Marcapata", "corredor_minero": "Espinar", "morrope": "Mórrope", "amazonas_vaciante": "Parinari",
         "ucayali_vaciante": "Orellana", "lima_norte": "Puente Piedra", "callao_gambetta": "la Av. Néstor Gambetta",
         "puerto_callao": "el Callao", "puerto_chancay": "Chancay", "puerto_paita": "Paita", "puerto_matarani": "Matarani"}
# Departamento, vía y río de cada punto crítico (para que los textos simulados hablen del lugar correcto)
PUNTO = {
    "chosica": ("Lima", "Carretera Central", "Rímac"), "matucana": ("Lima", "Carretera Central", "Rímac"),
    "ticlio": ("Lima", "Carretera Central", "Rímac"), "pasamayo": ("Lima", "Panamericana Norte", "Chancay"),
    "lima_norte": ("Lima", "Panamericana Norte", "Chillón"), "callao_gambetta": ("Callao", "Av. Néstor Gambetta", "Rímac"),
    "ica_pan_sur": ("Ica", "Panamericana Sur", "Ica"), "chala_atico": ("Arequipa", "Panamericana Sur", "Ocoña"),
    "corredor_minero": ("Cusco", "Corredor Minero Sur", "Apurímac"), "juliaca": ("Puno", "vía Juliaca–Cusco", "Coata"),
    "crucero_alto": ("Puno", "vía Arequipa–Juliaca (PE-34A)", "Coata"), "la_raya": ("Cusco", "vía Cusco–Puno (PE-3S)", "Vilcanota"),
    "marcapata": ("Cusco", "Interoceánica Sur", "Marcapata"), "piura_rio": ("Piura", "Panamericana Norte", "Piura"),
    "morrope": ("Lambayeque", "Panamericana Norte antigua", "La Leche"), "olmos": ("Lambayeque", "IIRSA Norte", "Olmos"),
    "carpish": ("Huánuco", "Carretera Central (PE-18A)", "Huallaga"), "conococha": ("Áncash", "vía Pativilca–Huaraz (PE-16)", "Santa"),
    "trujillo": ("La Libertad", "Panamericana Norte", "Moche"),
}
MEDIOS = ["Radio local · {dep}", "Noticiero regional de TV · {dep}", "Diario regional · {dep}", "Portal de noticias nacional",
          "Noticiero nacional de TV"]
PREFIJOS = ["chofer", "camionero", "ruta", "vecino", "carga", "transporte", "viajero", "pista", "andino", "noticias"]
NIVELES = ["amarillo", "naranja", "naranja", "rojo"]


def _sin_tildes(texto: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _cuenta(rng: random.Random, dep: str, prefijos=PREFIJOS) -> str:
    """Cuenta enmascarada (como en una herramienta de escucha que protege datos personales)."""
    p = rng.choice(prefijos)
    region = _sin_tildes(dep.split()[0]).lower()
    return f"@{p[:2]}{'*' * max(3, len(p) - 4)}{p[-2:]}_{region}"


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    limite, k, prod = math.exp(-lam), 0, rng.random()
    while prod > limite:
        k += 1
        prod *= rng.random()
    return k


def _seed(*partes) -> int:
    return int(hashlib.md5("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:12], 16)


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


# ------------------------------------------------------------------ eventos base (modelo histórico)
_cache = {"t": 0.0, "eventos": None}


def _distancia_km(lat1, lon1, lat2, lon2) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    return 6371 * math.hypot(dlat, dlon)


def _lugar(corredor: str, modo: str, categoria: str, origen: str, destino: str, rng: random.Random,
           hotspots: list, usados: set) -> dict:
    """Ubica el evento en un punto crítico real cercano a la ruta y aún no usado (o en un kilómetro de la vía)."""
    ruta = geo_data.get_route(corredor, modo) or geo_data.get_route(corredor, "Carretero")
    cerca = []
    if ruta:
        pts = ruta["geometry"][::max(1, len(ruta["geometry"]) // 60)]
        for h in hotspots:
            if h["id"] in usados:
                continue
            d = min(_distancia_km(h["lat"], h["lon"], p[0], p[1]) for p in pts)
            if d < 35:
                cerca.append((d, h))
    claves = CLAVES_LUGAR.get(categoria, ())
    ordenados = [h for _, h in sorted(cerca, key=lambda t: t[0])]
    afines = [h for h in ordenados if any(k in (h.get("descripcion") or "").lower() for k in claves)]
    en_via = [h for h in ordenados if modo != "Carretero" or not h["id"].startswith("puerto_")]
    elegido = afines[0] if afines else (en_via[0] if en_via else None)
    ruta_txt = (ruta or {}).get("ruta_principal") or "vía nacional"
    km = int(rng.uniform(0.15, 0.85) * ((ruta or {}).get("km") or 300))
    if elegido:
        usados.add(elegido["id"])
        nombre = elegido["nombre"]
        corto = CORTO.get(elegido.get("id"), nombre.split(" (")[0].split(" – ")[0].strip())
    else:
        corto = destino if rng.random() < 0.5 else origen
        nombre = f"{ruta_txt.split(' (')[0]} km {km} · cerca de {corto}"
    coords = geo_data.get_coords(corto) or geo_data.get_coords(destino) or geo_data.get_coords(origen) or {}
    dep, ruta_corta = coords.get("departamento", "Lima"), ruta_txt.split(" (")[0].split(" / ")[0]
    rio = next((r for clave, r in RIOS if clave in corredor), "Rímac")
    if elegido and elegido["id"] in PUNTO:
        dep, ruta_corta, rio = PUNTO[elegido["id"]]
    return {"nombre": nombre, "corto": corto, "ruta": ruta_corta, "dep": dep, "rio": rio, "km": km,
            "punto_critico": bool(elegido)}


def _eventos_base() -> list:
    if _cache["eventos"] is not None and time.time() - _cache["t"] < CACHE_BASE_S:
        return _cache["eventos"]
    from app.services.decision_assistant import get_scenarios_48h
    from app.services.predictive_service import get_forecast_24h

    pronostico = get_forecast_24h()
    p24_corredor = {(e["corredor"], e["categoria"]): e["probabilidad_pct"] / 100 for e in pronostico}
    eventos, por_categoria, usados = [], {}, set()
    for e in sorted(pronostico, key=lambda x: -x["probabilidad_pct"]):
        # variedad: máximo 2 eventos por tipo y un corredor por evento
        if por_categoria.get(e["categoria"], 0) >= 2 or e["corredor"] in usados or len(eventos) >= 8:
            continue
        por_categoria[e["categoria"]] = por_categoria.get(e["categoria"], 0) + 1
        usados.add(e["corredor"])
        eventos.append({"horizonte": "24 h", "titulo": e["titulo"], "categoria": e["categoria"], "icon": e["icon"],
                        "color": e["color"], "corredor": e["corredor"], "modo": e.get("tipo_transporte", "Carretero"),
                        "origen": e["origen"]["nombre"], "destino": e["destino"]["nombre"],
                        "p0": e["probabilidad_pct"] / 100, "clientes": e.get("clientes_criticos_expuestos", 0),
                        "costo_pen": e.get("costo_en_riesgo_pen", 0)})
    hotspots = geo_data.get_network()["hotspots"]
    puntos_usados = set()
    for ev in eventos:
        ev["key"] = f"{ev['horizonte']}|{ev['corredor']}|{ev['categoria']}"
        ev["lugar"] = _lugar(ev["corredor"], ev["modo"], ev["categoria"], ev["origen"], ev["destino"],
                             random.Random(_seed(ev["key"])), hotspots, puntos_usados)
    # 48 h: escenario de red; se ubica en el primer corredor probable con un punto crítico libre
    for s in get_scenarios_48h()[:5]:
        candidatos = [c for c in [s.get("corredor_principal")] + list(s.get("corredores_probables") or []) if c] or ["Lima - Huancayo"]
        elegido = None
        for corredor in dict.fromkeys(candidatos):
            partes = corredor.split(" - ")
            key = f"48 h|{corredor}|{s['categoria']}"
            lugar = _lugar(corredor, "Carretero", s["categoria"], partes[0], partes[-1], random.Random(_seed(key)),
                           hotspots, puntos_usados)
            if lugar["punto_critico"] or elegido is None:
                elegido = (corredor, partes, key, lugar)
            if lugar["punto_critico"]:
                break
        corredor, partes, key, lugar = elegido
        # base del corredor ampliada a 48 h (dos días con dependencia): p48 = 1 − (1 − p24)^1.5. El 99 % del
        # escenario es para toda la red; aquí el evento está ubicado en un corredor concreto.
        p24 = p24_corredor.get((corredor, s["categoria"]))
        p0 = 1 - (1 - p24) ** 1.5 if p24 is not None else min(0.95, s["probabilidad_48h_pct"] / 100 * 0.85)
        eventos.append({"horizonte": "48 h", "titulo": s["titulo"], "categoria": s["categoria"], "icon": s["icon"],
                        "color": s["color"], "corredor": corredor, "modo": "Carretero", "key": key, "lugar": lugar,
                        "origen": partes[0], "destino": partes[-1], "p0": p0,
                        "clientes": s.get("clientes_criticos_expuestos", 0), "costo_pen": s.get("impacto_economico_estimado_pen", 0)})
    _cache.update(t=time.time(), eventos=eventos)
    return eventos


# ------------------------------------------------------------------ señales simuladas
def _metricas(fuente: str, rng: random.Random) -> tuple:
    """(repeticiones de la misma noticia tras deduplicar, texto de alcance)."""
    if fuente == "tiktok":
        rep = 1 + int(rng.lognormvariate(1.6, 0.9))
        vistas = int(rng.lognormvariate(9.0, 1.1))
        return rep, f"{_miles(vistas)} vistas · {_miles(int(vistas * rng.uniform(.03, .1)))} me gusta"
    if fuente == "facebook":
        rep = 1 + int(rng.lognormvariate(1.1, 0.8))
        reac = int(rng.lognormvariate(4.4, 1.0))
        return rep, f"{_miles(reac)} reacciones · {_miles(int(reac * rng.uniform(.2, .9)))} compartidos"
    if fuente == "instagram":
        rep = 1 + int(rng.lognormvariate(0.9, 0.8))
        return rep, f"{_miles(int(rng.lognormvariate(8.2, 1.0)))} reproducciones"
    if fuente == "medios":
        return 1 + int(rng.random() * 3), "nota publicada"
    if fuente == "policia":
        return 1, f"parte N.° {rng.randint(120, 980)}-{datetime.now(PERU_TZ).year}"
    return 1, "comunicado oficial"


def _miles(n: int) -> str:
    return f"{n / 1000:.1f} mil".replace(".0 mil", " mil") if n >= 1000 else str(n)


def _publicaciones(ev: dict, ahora: datetime) -> list:
    """Publicaciones relevantes de las últimas VENTANA_H horas para un evento (semilla fija por hora)."""
    perfil = PERFIL.get(ev["categoria"], PERFIL["infraestructura"])
    rng_dia = random.Random(_seed(ev["key"], ahora.date()))
    fuerza = (0.25 + ev["p0"]) ** 1.3 * rng_dia.uniform(0.7, 1.3)
    tendencia = rng_dia.choices(["sube", "estable", "baja"], weights=[0.25 + ev["p0"], 0.4, 0.35])[0]
    hora_actual = ahora.replace(minute=0, second=0, microsecond=0)
    lugar = ev["lugar"]
    tag = "".join(w.capitalize() for w in _sin_tildes(lugar["corto"]).replace(".", "").split() if w.lower() not in ("el", "la", "de"))
    datos = {"corto": lugar["corto"], "ruta": lugar["ruta"], "dep": lugar["dep"], "rio": lugar["rio"], "km": lugar["km"], "tag": tag}
    textos = TEXTOS.get(ev["categoria"], TEXTOS["infraestructura"])
    pubs = []
    for h in range(VENTANA_H + 1):
        inicio = hora_actual - timedelta(hours=h)
        edad = h / VENTANA_H
        mult = {"sube": 0.4 + 1.2 * (1 - edad), "baja": 0.4 + 1.2 * edad, "estable": 1.0}[tendencia]
        for f in FUENTES:
            rng = random.Random(_seed(ev["key"], f["id"], inicio.isoformat()))
            for i in range(_poisson(rng, perfil.get(f["id"], 0) / VENTANA_H * fuerza * mult)):
                ts = inicio + timedelta(minutes=rng.uniform(0, 59.9))
                if ts > ahora or ts < ahora - timedelta(hours=VENTANA_H):
                    continue
                rep, alcance = _metricas(f["id"], rng)
                if f["id"] == "oficial":
                    autor, plantilla = rng.choice(textos["oficial"])
                    texto = plantilla.format(n=rng.randint(180, 420), nivel=rng.choice(NIVELES), **datos)
                elif f["id"] == "medios":
                    autor, texto = rng.choice(MEDIOS).format(**datos), rng.choice(textos["medios"]).format(**datos)
                elif f["id"] == "policia":
                    autor, texto = f"PNP · Policía de Carreteras ({lugar['dep']})", rng.choice(textos["policia"]).format(**datos)
                elif f["id"] == "facebook":
                    grupo = rng.choice([f"Transportistas {ev['corredor']}", f"Choferes de carga pesada · {lugar['dep']}",
                                        f"Vecinos de {lugar['corto']}"])
                    autor, texto = f"{grupo} (grupo)", rng.choice(textos["facebook"]).format(**datos)
                elif f["id"] == "instagram":
                    autor, texto = _cuenta(rng, lugar["dep"], ["noticias", "info", "reporte", "prensa"]), rng.choice(textos["instagram"]).format(**datos)
                else:
                    autor, texto = _cuenta(rng, lugar["dep"]), rng.choice(textos["tiktok"]).format(**datos)
                pubs.append({"fuente": f["id"], "autor": autor, "texto": texto, "ts": ts, "repeticiones": rep, "alcance": alcance})
    # deduplicación: la misma noticia publicada varias veces se agrupa y suma sus repeticiones
    noticias = {}
    for p in sorted(pubs, key=lambda x: x["ts"]):
        k = (p["fuente"], p["texto"])
        if k not in noticias:
            noticias[k] = dict(p, id=f"{_seed(ev['key'], *k):x}", primera=p["ts"])
        else:
            n = noticias[k]
            n.update(ts=p["ts"], autor=p["autor"], alcance=p["alcance"], repeticiones=n["repeticiones"] + p["repeticiones"])
    return list(noticias.values())


def _actualizar(p0: float, pubs: list, ahora: datetime) -> dict:
    m = {f["id"]: 0.0 for f in FUENTES}
    for p in pubs:
        dt_h = (ahora - p["ts"]).total_seconds() / 3600
        m[p["fuente"]] += math.exp(-dt_h / TAU_H) * (1 + math.log(p["repeticiones"]))
    confirmado = m["oficial"] > 0 or m["policia"] > 0
    techo = max(P_MAX, p0)  # las señales solo suman: nunca bajan la probabilidad base
    x, p_prev, aportes = _logit(p0), p0, []
    for f in FUENTES:
        c = 1.0 if (confirmado or not f["red"]) else PENALIDAD_RUMOR
        x += BETA * c * f["peso"] * math.log1p(m[f["id"]])
        p = max(p_prev, min(techo, _sigmoid(x)))
        aportes.append({"fuente": f["id"], "pp": round((p - p_prev) * 100, 1), "m": round(m[f["id"]], 2)})
        p_prev = p
    return {"p": p_prev, "aportes": aportes, "confirmado": confirmado}


def _hace(ts: datetime, ahora: datetime) -> str:
    minutos = int((ahora - ts).total_seconds() // 60)
    if minutos < 1:
        return "ahora"
    if minutos < 60:
        return f"hace {minutos} min"
    return f"hace {minutos // 60} h {minutos % 60:02d} min"


def _publicacion_dict(p: dict, ahora: datetime) -> dict:
    f = FUENTE[p["fuente"]]
    dt_h = (ahora - p["ts"]).total_seconds() / 3600
    return {"id": p["id"], "fuente": p["fuente"], "fuente_nombre": f["nombre"], "icon": f["icon"], "color": f["color"],
            "autor": p["autor"], "texto": p["texto"], "hace": _hace(p["ts"], ahora), "ts": p["ts"].isoformat(),
            "desde": _hace(p["primera"], ahora), "repeticiones": p["repeticiones"], "alcance": p["alcance"],
            "relevancia": round(f["peso"] * math.exp(-dt_h / TAU_H) * (1 + math.log(p["repeticiones"])), 3)}


def get_senales() -> dict:
    ahora = datetime.now(PERU_TZ)
    eventos, flujo = [], []
    relevantes = {f["id"]: 0 for f in FUENTES}
    for ev in _eventos_base():
        pubs = _publicaciones(ev, ahora)
        res = _actualizar(ev["p0"], pubs, ahora)
        antes = ahora - timedelta(hours=3)
        res_antes = _actualizar(ev["p0"], _publicaciones(ev, antes), antes)
        por_fuente = {f["id"]: 0 for f in FUENTES}
        for p in pubs:
            por_fuente[p["fuente"]] += 1
            relevantes[p["fuente"]] += p["repeticiones"]
        evidencias = sorted((_publicacion_dict(p, ahora) for p in pubs), key=lambda d: -d["relevancia"])
        confirmadores = sorted({p["autor"].split(" · ")[0] for p in pubs if p["fuente"] == "oficial"})
        eventos.append({
            "id": f"{_seed(ev['key']):x}", "horizonte": ev["horizonte"], "titulo": ev["titulo"], "categoria": ev["categoria"],
            "icon": ev["icon"], "color": ev["color"], "corredor": ev["corredor"], "lugar": ev["lugar"]["nombre"],
            "departamento": ev["lugar"]["dep"], "prob_base": round(ev["p0"] * 100, 1), "prob_final": round(res["p"] * 100, 1),
            "delta_pp": round((res["p"] - ev["p0"]) * 100, 1), "cambio_3h_pp": round((res["p"] - res_antes["p"]) * 100, 1),
            "confirmado": res["confirmado"], "confirmado_por": confirmadores or (["PNP"] if por_fuente["policia"] else []),
            "aportes": res["aportes"], "menciones": por_fuente, "menciones_total": len(pubs),
            "publicaciones_total": sum(p["repeticiones"] for p in pubs),
            "repeticiones_max": max((p["repeticiones"] for p in pubs), default=0),
            "clientes": ev["clientes"], "costo_pen": ev["costo_pen"], "evidencias": evidencias[:10],
        })
        for d in evidencias:
            flujo.append(dict(d, evento=ev["titulo"], lugar=ev["lugar"]["corto"], horizonte=ev["horizonte"]))
    eventos.sort(key=lambda e: (e["horizonte"] != "24 h", -e["prob_final"]))
    flujo.sort(key=lambda d: d["ts"], reverse=True)
    medianoche = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    minutos_hoy = (ahora - medianoche).total_seconds() / 60
    fuentes = [{
        "id": f["id"], "nombre": f["nombre"], "detalle": f["detalle"], "icon": f["icon"], "color": f["color"],
        "peso": f["peso"], "ritmo_min": f["ritmo_min"], "analizadas_hoy": int(minutos_hoy * f["ritmo_min"]),
        "relevantes_12h": relevantes[f["id"]],
    } for f in FUENTES]
    return {
        "ahora": ahora.isoformat(), "fuentes": fuentes, "eventos": eventos, "flujo": flujo[:40],
        "metodo": {"beta": BETA, "tau_h": TAU_H, "ventana_h": VENTANA_H, "penalidad_rumor": PENALIDAD_RUMOR,
                   "p_max": P_MAX, "pesos": {f["id"]: f["peso"] for f in FUENTES}},
        "nota": "Escucha SIMULADA con fines académicos: cuentas enmascaradas, medios genéricos y avisos de ejemplo.",
    }
