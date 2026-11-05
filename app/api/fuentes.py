"""¿De dónde se extrae la data? — señales simuladas de redes, noticieros, policía e institutos por evento."""
from flask import Blueprint, jsonify
from flask_login import login_required

from app.services import fuentes_service

bp = Blueprint("fuentes", __name__, url_prefix="/api/fuentes")


@bp.get("/senales")
@login_required
def senales():
    return jsonify(fuentes_service.get_senales())
