from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import dashboard_service

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _filtros_from_request() -> dict:
    return {
        "anio": request.args.get("anio", type=int),
        "departamento_origen": request.args.get("departamento_origen"),
        "tipo_transporte": request.args.get("tipo_transporte"),
    }


@bp.get("/kpis")
@login_required
def kpis():
    return jsonify(dashboard_service.get_kpis(_filtros_from_request()))


@bp.get("/tendencia")
@login_required
def tendencia():
    return jsonify({"tendencia": dashboard_service.get_tendencia_mensual(_filtros_from_request())})


@bp.get("/corredores-riesgo")
@login_required
def corredores_riesgo():
    return jsonify({"corredores": dashboard_service.get_top_corredores_riesgo()})


@bp.get("/actividad-reciente")
@login_required
def actividad_reciente():
    return jsonify({"actividad": dashboard_service.get_actividad_reciente()})
