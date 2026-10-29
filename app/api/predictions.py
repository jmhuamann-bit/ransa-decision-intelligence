from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.ml.training.trainer import ALGORITHM_LABELS, ALGORITHMS, train_all_and_activate_best, train_and_evaluate
from app.models.ml_model import MLModelRun
from app.models.shipment import Shipment
from app.services.alert_service import regenerate_ai_alerts
from app.services.auth_service import register_audit
from app.services.prediction_service import apply_predictions_to_all_shipments
from app.utils.decorators import disabled_in_public_demo, roles_required

bp = Blueprint("predictions", __name__, url_prefix="/api/predictions")


def _run_dict(run: MLModelRun) -> dict:
    data = run.to_dict()
    data["algoritmo_label"] = ALGORITHM_LABELS.get(run.algoritmo, run.algoritmo)
    return data


@bp.get("/model")
@login_required
def current_model():
    run = MLModelRun.query.filter_by(activo=True).order_by(MLModelRun.creado_en.desc()).first()
    if not run:
        return jsonify({"model": None, "message": "Aún no se ha entrenado ningún modelo."})
    return jsonify({"model": _run_dict(run)})


@bp.get("/algorithms")
@login_required
def algorithms():
    return jsonify({"algoritmos": [{"id": k, "label": v} for k, v in ALGORITHM_LABELS.items()]})


@bp.get("/runs")
@login_required
def runs():
    """Comparativo: el entrenamiento más reciente de cada algoritmo."""
    out = []
    for alg in ALGORITHMS:
        run = MLModelRun.query.filter_by(algoritmo=alg).order_by(MLModelRun.creado_en.desc()).first()
        if run:
            d = _run_dict(run)
            d.pop("curva_roc", None)
            d.pop("importancia_variables", None)
            d.pop("features", None)
            d["activo"] = bool(run.activo)
            out.append(d)
    return jsonify({"runs": out})


def _refresh_after_activation(run: MLModelRun) -> dict:
    n_shipments = apply_predictions_to_all_shipments()
    n_alerts = regenerate_ai_alerts()
    from app.services import simulator_service
    simulator_service.invalidate_cache()
    return {"model": _run_dict(run), "embarques_actualizados": n_shipments, "alertas_generadas": n_alerts}


@bp.post("/train")
@login_required
@roles_required("Analista")
@disabled_in_public_demo
def train():
    data = request.get_json(silent=True) or {}
    algoritmo = data.get("algoritmo") or "todos"
    if algoritmo == "todos":
        run, _ = train_all_and_activate_best()
    elif algoritmo in ALGORITHMS:
        run = train_and_evaluate(algoritmo)
    else:
        return jsonify({"error": f"Algoritmo no soportado: {algoritmo}"}), 400
    result = _refresh_after_activation(run)
    register_audit(
        current_user, "entrenamiento_modelo_ia", entidad="MLModelRun", entidad_id=run.id,
        detalle=f"{run.algoritmo} v{run.version} — AUC={run.auc} — {result['embarques_actualizados']} embarques "
                f"actualizados, {result['alertas_generadas']} alertas críticas generadas",
    )
    return jsonify(result)


@bp.post("/activate/<int:run_id>")
@login_required
@roles_required("Analista")
@disabled_in_public_demo
def activate(run_id):
    run = MLModelRun.query.get(run_id)
    if not run:
        return jsonify({"error": "Modelo no encontrado"}), 404
    db.session.query(MLModelRun).update({MLModelRun.activo: False})
    run.activo = True
    db.session.commit()
    result = _refresh_after_activation(run)
    register_audit(current_user, "activar_modelo_ia", entidad="MLModelRun", entidad_id=run.id,
                   detalle=f"{run.algoritmo} v{run.version} activado (AUC={run.auc})")
    return jsonify(result)


@bp.get("/top-riesgo")
@login_required
def top_riesgo():
    shipments = (
        Shipment.query.filter(Shipment.prob_riesgo_incumplimiento.isnot(None))
        .order_by(Shipment.prob_riesgo_incumplimiento.desc())
        .limit(20)
        .all()
    )
    return jsonify({
        "items": [
            {
                "id_viaje": s.id_viaje,
                "fecha": s.fecha.isoformat() if s.fecha else None,
                "corredor_logistico": s.corredor_logistico,
                "tipo_transporte": s.tipo_transporte,
                "prioridad_cliente": s.prioridad_cliente,
                "prob_riesgo_incumplimiento": s.prob_riesgo_incumplimiento,
                "nivel_riesgo": s.nivel_riesgo,
                "otif_real": bool(s.otif),
            }
            for s in shipments
        ]
    })
