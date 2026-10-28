from flask import Blueprint, jsonify
from flask_login import login_required

from app.services import predictive_service

bp = Blueprint("predictive", __name__, url_prefix="/api/predictive")


@bp.get("/forecast-24h")
@login_required
def forecast_24h():
    return jsonify({"eventos": predictive_service.get_forecast_24h(), "umbral_pct": predictive_service.PROB_THRESHOLD})


@bp.get("/heatmap")
@login_required
def heatmap():
    return jsonify({"puntos": predictive_service.get_heatmap_points()})
