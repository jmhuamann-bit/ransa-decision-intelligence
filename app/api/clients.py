from flask import Blueprint, jsonify
from flask_login import login_required

from app.services import client_service

bp = Blueprint("clients", __name__, url_prefix="/api/clients")


@bp.get("/segments")
@login_required
def segments():
    return jsonify({"segments": client_service.get_client_segments(), "sla_objetivo_otif_pct": client_service.SLA_OBJETIVO_OTIF_PCT})


@bp.get("/sectors")
@login_required
def sectors():
    return jsonify({"sectors": client_service.get_sector_summary()})
