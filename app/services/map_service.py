"""Agrega los embarques por nodo (ciudad) y por corredor logistico, con sus coordenadas,
para alimentar el Mapa Inteligente."""
from sqlalchemy import func

from app.extensions import db
from app.models.alert import Alert
from app.models.shipment import Shipment
from app.services.geo_data import CITY_COORDS, get_coords

SEMAFORO_MAP = {"Bajo": "verde", "Medio": "amarillo", "Alto": "rojo", "Critico": "rojo"}


def _base_query(tipo_transporte: str = None):
    q = Shipment.query
    if tipo_transporte:
        q = q.filter(Shipment.tipo_transporte == tipo_transporte)
    return q


def get_nodes(tipo_transporte: str = None) -> list:
    q = _base_query(tipo_transporte)

    origenes = (
        q.with_entities(
            Shipment.ciudad_origen.label("municipio"),
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.avg(Shipment.otif).label("otif"),
        ).group_by(Shipment.ciudad_origen).all()
    )
    destinos = (
        q.with_entities(
            Shipment.ciudad_destino.label("municipio"),
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.avg(Shipment.otif).label("otif"),
        ).group_by(Shipment.ciudad_destino).all()
    )

    agg = {}
    for row in list(origenes) + list(destinos):
        if not row.municipio:
            continue
        entry = agg.setdefault(row.municipio, {"total": 0, "riesgo_sum": 0.0, "otif_sum": 0.0, "n": 0})
        entry["total"] += row.total
        entry["riesgo_sum"] += (row.riesgo or 0) * row.total
        entry["otif_sum"] += (row.otif or 0) * row.total
        entry["n"] += row.total

    nodes = []
    for municipio, stats in agg.items():
        coords = get_coords(municipio)
        if not coords:
            continue
        riesgo = stats["riesgo_sum"] / stats["n"] if stats["n"] else 0
        otif = (stats["otif_sum"] / stats["n"]) * 100 if stats["n"] else 0
        nivel = "Alto" if riesgo >= 50 else "Medio" if riesgo >= 25 else "Bajo"
        nodes.append({
            "municipio": municipio,
            "lat": coords["lat"], "lon": coords["lon"],
            "es_puerto": coords["es_puerto"], "es_aeropuerto_principal": coords["es_aeropuerto_principal"],
            "total_embarques": stats["total"],
            "riesgo_promedio_pct": round(riesgo, 1),
            "otif_pct": round(otif, 1),
            "nivel_riesgo": nivel,
            "semaforo": SEMAFORO_MAP.get(nivel, "verde"),
        })
    return nodes


def get_routes(tipo_transporte: str = None, min_embarques: int = 3) -> list:
    q = _base_query(tipo_transporte)
    rows = (
        q.with_entities(
            Shipment.corredor_logistico,
            Shipment.ciudad_origen,
            Shipment.ciudad_destino,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
        )
        .group_by(Shipment.corredor_logistico, Shipment.ciudad_origen, Shipment.ciudad_destino)
        .having(func.count(Shipment.id) >= min_embarques)
        .all()
    )

    routes = []
    for r in rows:
        origen = get_coords(r.ciudad_origen)
        destino = get_coords(r.ciudad_destino)
        if not origen or not destino:
            continue
        riesgo = round(r.riesgo or 0, 1)
        nivel = "Alto" if riesgo >= 50 else "Medio" if riesgo >= 25 else "Bajo"
        routes.append({
            "corredor": r.corredor_logistico,
            "origen": {"municipio": r.ciudad_origen, "lat": origen["lat"], "lon": origen["lon"]},
            "destino": {"municipio": r.ciudad_destino, "lat": destino["lat"], "lon": destino["lon"]},
            "total_embarques": r.total,
            "riesgo_promedio_pct": riesgo,
            "otif_pct": round((r.otif or 0) * 100, 1),
            "leadtime_promedio_dias": round(r.leadtime or 0, 2),
            "nivel_riesgo": nivel,
            "semaforo": SEMAFORO_MAP.get(nivel, "verde"),
        })
    return routes


def get_alert_markers(limit: int = 200) -> list:
    rows = (
        db.session.query(Alert, Shipment)
        .join(Shipment, Alert.shipment_id == Shipment.id)
        .filter(Alert.estado == "Abierta")
        .order_by(Alert.probabilidad_pct.desc())
        .limit(limit)
        .all()
    )
    markers = []
    for alert, shipment in rows:
        coords = get_coords(shipment.ciudad_origen)
        if not coords:
            continue
        markers.append({
            "id_viaje": shipment.id_viaje,
            "lat": coords["lat"], "lon": coords["lon"],
            "ciudad_origen": shipment.ciudad_origen,
            "ciudad_destino": shipment.ciudad_destino,
            "corredor": shipment.corredor_logistico,
            "probabilidad_pct": alert.probabilidad_pct,
            "titulo": alert.titulo,
        })
    return markers


def get_known_cities() -> list:
    return [{"municipio": name, **coords} for name, coords in CITY_COORDS.items()]
