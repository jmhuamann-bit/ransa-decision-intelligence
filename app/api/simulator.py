from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import network_simulator, simulator_service

bp = Blueprint("simulator", __name__, url_prefix="/api/simulator")


@bp.get("/options")
@login_required
def options():
    return jsonify(simulator_service.get_form_options())


@bp.post("/predict")
@login_required
def predict():
    data = request.get_json(silent=True) or {}
    try:
        result = simulator_service.simulate(data)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result)


@bp.get("/network-options")
@login_required
def network_options():
    return jsonify(network_simulator.get_options())


@bp.post("/network")
@login_required
def network():
    data = request.get_json(silent=True) or {}
    result = network_simulator.simulate(data.get("escenario"), data.get("objetivo"))
    if not result:
        return jsonify({"error": "Escenario inválido o falta seleccionar el objetivo"}), 400
    return jsonify(result)
