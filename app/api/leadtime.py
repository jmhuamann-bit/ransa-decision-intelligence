from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.services import leadtime_pca_service

bp = Blueprint("leadtime", __name__, url_prefix="/api/leadtime")


@bp.get("/model")
@login_required
def model():
    data = leadtime_pca_service.get_model()
    if not data:
        return jsonify({"error": "El modelo aún no se ha ajustado. Ejecuta backend/scripts/fit_leadtime_pca.py"}), 404
    return jsonify(data)


@bp.post("/predict")
@login_required
def predict():
    data = request.get_json(silent=True) or {}
    result = leadtime_pca_service.predict(data.get("factores") or {})
    if not result:
        return jsonify({"error": "El modelo aún no se ha ajustado"}), 404
    return jsonify(result)
