from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import map_service
from app.services.geo_data import PERU_CENTER

bp = Blueprint("map", __name__, url_prefix="/api/map")


@bp.get("/nodes")
@login_required
def nodes():
    return jsonify({"nodes": map_service.get_nodes(request.args.get("tipo_transporte"))})


@bp.get("/routes")
@login_required
def routes():
    return jsonify({"routes": map_service.get_routes(request.args.get("tipo_transporte"))})


@bp.get("/alerts")
@login_required
def alerts():
    return jsonify({"alerts": map_service.get_alert_markers()})


@bp.get("/meta")
@login_required
def meta():
    return jsonify({"center": PERU_CENTER, "cities": map_service.get_known_cities()})
