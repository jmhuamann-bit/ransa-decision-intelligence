"""Aplica las predicciones del modelo activo a los embarques guardados en la base de datos
(actualiza prob_riesgo_incumplimiento, nivel_riesgo y alerta_critica en cada fila de Shipment)."""
from flask import current_app

from app.extensions import db
from app.ml.data.dataset import load_training_dataframe
from app.ml.prediction.predictor import bucket_risk, predict_proba_pct
from app.models.shipment import Shipment


def apply_predictions_to_all_shipments(batch_size: int = 1000) -> int:
    df = load_training_dataframe()
    proba = predict_proba_pct(df)
    if proba is None:
        raise RuntimeError("No hay un modelo de IA activo. Entrena un modelo primero.")

    threshold = current_app.config["RISK_ALERT_THRESHOLD_PCT"]
    df = df.assign(prob=proba)

    updates = [
        {
            "id": int(row.id),
            "prob_riesgo_incumplimiento": float(row.prob),
            "nivel_riesgo": bucket_risk(row.prob),
            "alerta_critica": bool(row.prob >= threshold),
        }
        for row in df.itertuples()
    ]

    for i in range(0, len(updates), batch_size):
        db.session.bulk_update_mappings(Shipment, updates[i:i + batch_size])
        db.session.commit()

    return len(updates)
