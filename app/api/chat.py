from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import chat_service

bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@bp.post("/message")
@login_required
def message():
    data = request.get_json(silent=True) or {}
    mensaje = (data.get("mensaje") or "").strip()
    if not mensaje:
        return jsonify({"error": "Escribe un mensaje"}), 400
    return jsonify(chat_service.answer(mensaje))
