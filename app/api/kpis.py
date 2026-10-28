from flask import Blueprint, jsonify
from flask_login import login_required

from app.services import kpi_service

bp = Blueprint("kpis", __name__, url_prefix="/api/kpis")


@bp.get("/por-transporte")
@login_required
def por_transporte():
    return jsonify({"items": kpi_service.get_kpis_por_transporte()})


@bp.get("/por-prioridad")
@login_required
def por_prioridad():
    return jsonify({"items": kpi_service.get_kpis_por_prioridad()})


@bp.get("/comparativo-trimestral")
@login_required
def comparativo_trimestral():
    return jsonify({"items": kpi_service.get_comparativo_trimestral()})
