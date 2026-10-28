from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import context_service

bp = Blueprint("context", __name__, url_prefix="/api/context")


@bp.get("/red")
@login_required
def red():
    return jsonify(context_service.get_red())


@bp.get("/corredor")
@login_required
def corredor():
    nombre = request.args.get("nombre", "")
    data = context_service.get_corredor(nombre)
    if not data:
        return jsonify({"error": "Corredor no encontrado"}), 404
    return jsonify(data)


@bp.get("/nodo")
@login_required
def nodo():
    municipio = request.args.get("municipio", "")
    data = context_service.get_nodo(municipio)
    if not data:
        return jsonify({"error": "Nodo no encontrado"}), 404
    return jsonify(data)


@bp.get("/vehiculo/<id_viaje>")
@login_required
def vehiculo(id_viaje):
    data = context_service.get_vehiculo(id_viaje)
    if not data:
        return jsonify({"error": "Embarque no encontrado"}), 404
    return jsonify(data)
