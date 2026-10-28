"""
Catálogo geográfico de la red logística RANSA Perú.

Fuente única: data/peru_network.json, generado por scripts/build_peru_network.py con los nodos
reales de la red (centros de distribución, puertos marítimos y fluviales, aeropuertos), las rutas
trazadas sobre la red vial de OpenStreetMap (Panamericana, Carretera Central, IIRSA Norte,
Interoceánica, Corredor Minero Sur...) y su perfil de altitud SRTM. Este módulo lo carga una sola
vez y expone consultas para el Mapa, la Torre de Control / Gemelo Digital y el motor en vivo.
"""
import bisect
import json
import math
import os
from functools import lru_cache

NETWORK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "data", "peru_network.json")

PERU_CENTER = {"lat": -9.6, "lon": -75.3}
MODE_PREFIX = {"Carretero": "TER", "Marítimo": "MAR", "Fluvial": "FLU", "Aéreo": "AER"}


@lru_cache(maxsize=1)
def get_network() -> dict:
    with open(NETWORK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_city_coords() -> dict:
    coords = {}
    for n in get_network()["nodes"]:
        coords[n["nombre"]] = {
            "lat": n["lat"], "lon": n["lon"], "departamento": n["departamento"],
            "altitud_msnm": n["altitud_msnm"], "es_puerto": n["es_puerto"], "es_fluvial": n["es_fluvial"],
            "es_aeropuerto_principal": n["es_aeropuerto_principal"], "iata": n.get("iata"),
        }
    return coords


CITY_COORDS = _build_city_coords()


def get_coords(ciudad: str) -> dict | None:
    return CITY_COORDS.get(ciudad)


@lru_cache(maxsize=1)
def _routes_by_id() -> dict:
    return {r["id"]: r for r in get_network()["routes"]}


def get_route(corredor: str, modo: str, alterna: bool = False) -> dict | None:
    prefix = MODE_PREFIX.get(modo, "TER")
    return _routes_by_id().get(f"{prefix}:{corredor}" + ("|ALT" if alterna else ""))


def get_route_by_id(route_id: str) -> dict | None:
    return _routes_by_id().get(route_id)


def all_routes() -> list:
    return get_network()["routes"]


def get_hotspots() -> list:
    return get_network()["hotspots"]


# ------------------------------------------------------------------ geometría sobre rutas
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(min(1.0, h)))


def point_at_km(route: dict, km: float) -> tuple[float, float, float]:
    """(lat, lon, rumbo°) sobre la polilínea de la ruta a `km` del origen."""
    cum, geom = route["cum_km"], route["geometry"]
    km = max(0.0, min(km, cum[-1]))
    i = max(1, bisect.bisect_left(cum, km))
    i = min(i, len(cum) - 1)
    seg = (cum[i] - cum[i - 1]) or 1e-9
    f = (km - cum[i - 1]) / seg
    (la1, lo1), (la2, lo2) = geom[i - 1], geom[i]
    lat, lon = la1 + (la2 - la1) * f, lo1 + (lo2 - lo1) * f
    heading = math.degrees(math.atan2((lo2 - lo1) * math.cos(math.radians(lat)), la2 - la1))
    return lat, lon, heading


def profile_at_km(route: dict, km: float) -> tuple[float, float]:
    """(altitud m, velocidad de referencia km/h) interpolados del perfil SRTM/OSRM."""
    prof = route["profile"]
    kms = prof["km"]
    if not kms:
        return 0.0, 0.0
    km = max(kms[0], min(km, kms[-1]))
    i = max(1, min(bisect.bisect_left(kms, km), len(kms) - 1))
    seg = (kms[i] - kms[i - 1]) or 1e-9
    f = (km - kms[i - 1]) / seg
    alt = prof["alt"][i - 1] + (prof["alt"][i] - prof["alt"][i - 1]) * f
    v = prof["v"][i] if prof["v"] else 0.0
    return alt, v


def slope_at_km(route: dict, km: float) -> float:
    """Pendiente aproximada (m de desnivel por km) en el tramo que contiene `km`."""
    prof = route["profile"]
    kms = prof["km"]
    if len(kms) < 2:
        return 0.0
    i = max(1, min(bisect.bisect_left(kms, km), len(kms) - 1))
    dk = (kms[i] - kms[i - 1]) or 1e-9
    return (prof["alt"][i] - prof["alt"][i - 1]) / dk


def nearest_km_on_route(route: dict, lat: float, lon: float, max_km: float = 2.5) -> float | None:
    """Km de la ruta más cercano a (lat, lon) si la ruta pasa a menos de `max_km`; si no, None."""
    best_d, best_km = None, None
    cum, geom = route["cum_km"], route["geometry"]
    for i, (la, lo) in enumerate(geom):
        d = haversine_km(lat, lon, la, lo)
        if best_d is None or d < best_d:
            best_d, best_km = d, cum[i]
    if best_d is not None and best_d <= max_km:
        return best_km
    return None


def divergence_km(main: dict, alt: dict, tol_km: float = 1.5) -> float:
    """Km de la ruta principal donde la alterna se separa de ella (punto de desvío)."""
    for i, (la, lo) in enumerate(main["geometry"]):
        if nearest_km_on_route(alt, la, lo, max_km=tol_km) is None:
            return main["cum_km"][max(0, i - 1)]
    return main["cum_km"][-1]
