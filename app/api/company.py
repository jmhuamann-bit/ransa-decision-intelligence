"""Perfil público de RANSA (prensa y comunicados con fuente y fecha) que contextualiza la plataforma."""
from flask import Blueprint, jsonify
from flask_login import login_required

from app.services import ransa_profile

bp = Blueprint("company", __name__, url_prefix="/api/company")


@bp.get("/profile")
@login_required
def profile():
    return jsonify(ransa_profile.get_profile())
