from flask import Blueprint, jsonify, request

from flask_login import login_required

from app.services import contingency_planner, decision_assistant

bp = Blueprint("strategic", __name__, url_prefix="/api/strategic")


@bp.get("/scenarios-48h")
@login_required
def scenarios_48h():
    return jsonify({"escenarios": decision_assistant.get_scenarios_48h()})


@bp.get("/plans")
@login_required
def plans():
    corredor = request.args.get("corredor", "")
    categoria = request.args.get("categoria", "")
    data = contingency_planner.generate_plans(corredor, categoria)
    if not data:
        return jsonify({"error": "No hay datos históricos suficientes para ese corredor"}), 404
    return jsonify(data)
