"""API del Gemelo Digital (operación en vivo): lectura del estado, control de la simulación,
inyección de eventos, escenarios y ejecución de decisiones de la IA."""
from flask import Blueprint, Response, jsonify, request
from flask_login import current_user, login_required

from app.services import geo_data, ransa_profile
from app.services.auth_service import register_audit
from app.services.live_engine import get_engine, list_event_types, list_scenarios

bp = Blueprint("live", __name__, url_prefix="/api/live")

_network_cache: dict = {}


@bp.get("/poll")
@login_required
def poll():
    since_id = request.args.get("since_id", default=0, type=int)
    return jsonify(get_engine().snapshot(since_id=since_id))


@bp.get("/kpis")
@login_required
def kpis():
    return jsonify(get_engine().summary())


@bp.get("/network")
@login_required
def network():
    """Red vial real (nodos, rutas con geometría y perfil de altitud, puntos críticos). Es estática:
    se sirve con caché de navegador para que el mapa cargue una sola vez ~600 KB."""
    if "body" not in _network_cache:
        import json
        net = geo_data.get_network()
        for n in net["nodes"]:  # sedes públicas de RANSA en los nodos de la red
            sede = ransa_profile.sede_de(n["nombre"])
            if sede:
                n["sede"] = sede
        _network_cache["body"] = json.dumps(net, ensure_ascii=False, separators=(",", ":"))
    resp = Response(_network_cache["body"], mimetype="application/json")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@bp.get("/catalog")
@login_required
def catalog():
    return jsonify({"escenarios": list_scenarios(), "eventos": list_event_types()})


@bp.post("/control")
@login_required
def control():
    data = request.get_json(silent=True) or {}
    state = get_engine().control(speed=data.get("speed"), paused=data.get("paused"), autonomo=data.get("autonomo"))
    return jsonify(state)


@bp.post("/events")
@login_required
def create_event():
    data = request.get_json(silent=True) or {}
    tipo = data.get("tipo")
    try:
        lat, lon = float(data.get("lat")), float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Faltan coordenadas del evento"}), 400
    horas = data.get("horas")
    ev = get_engine().create_event(tipo, lat, lon, horas=float(horas) if horas else None, origen="manual")
    if not ev:
        return jsonify({"error": "Tipo de evento no válido"}), 400
    register_audit(current_user, "gemelo_inyectar_evento", entidad="LiveEvent", entidad_id=ev.id,
                   detalle=f"{ev.titulo} en {ev.lugar}")
    return jsonify({"id": ev.id, "titulo": ev.titulo, "lugar": ev.lugar}), 201


@bp.post("/events/<int:event_id>/resolve")
@login_required
def resolve_event(event_id):
    if not get_engine().resolve_event(event_id):
        return jsonify({"error": "Evento no encontrado"}), 404
    return jsonify({"ok": True})


@bp.get("/events/<int:event_id>/options")
@login_required
def event_options(event_id):
    data = get_engine().options_for(event_id)
    if data is None:
        return jsonify({"error": "Evento no encontrado"}), 404
    return jsonify(data)


@bp.post("/decision")
@login_required
def decision():
    data = request.get_json(silent=True) or {}
    try:
        event_id = int(data.get("event_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Evento inválido"}), 400
    result = get_engine().apply_decision(event_id, data.get("opcion") or "")
    if not result:
        return jsonify({"error": "No se pudo aplicar la decisión (evento finalizado u opción no disponible)"}), 400
    register_audit(current_user, "gemelo_aplicar_decision", entidad="LiveEvent", entidad_id=event_id,
                   detalle=f"{result['nombre']} — {result['detalle']}")
    return jsonify(result)


@bp.post("/scenario")
@login_required
def scenario():
    data = request.get_json(silent=True) or {}
    result = get_engine().run_scenario(data.get("id") or "")
    if not result:
        return jsonify({"error": "Escenario no encontrado"}), 404
    register_audit(current_user, "gemelo_escenario", entidad="Scenario", entidad_id=result["escenario"], detalle=result["titulo"])
    return jsonify(result)


@bp.post("/reset")
@login_required
def reset():
    get_engine().reset()
    return jsonify({"ok": True})
