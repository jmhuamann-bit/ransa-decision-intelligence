from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import prioritization_service

bp = Blueprint("prioritization", __name__, url_prefix="/api/prioritization")


@bp.get("/queue")
@login_required
def queue():
    limit = request.args.get("limit", default=20, type=int)
    return jsonify(prioritization_service.get_queue(limit=limit))
