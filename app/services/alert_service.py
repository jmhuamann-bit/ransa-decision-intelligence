"""Generacion de Alertas Criticas a partir de las predicciones del modelo de IA."""
from flask import current_app

from app.extensions import db
from app.models.alert import Alert
from app.models.shipment import Shipment


def regenerate_ai_alerts(threshold_pct: float = None) -> int:
    """Recalcula desde cero las alertas automaticas ('prediccion_ia') segun el riesgo vigente de
    cada embarque. Se ejecuta despues de cada entrenamiento/aplicacion de predicciones, por lo que
    las alertas de una corrida anterior se reemplazan por las actuales."""
    threshold_pct = threshold_pct if threshold_pct is not None else current_app.config["RISK_ALERT_THRESHOLD_PCT"]

    Alert.query.filter_by(tipo="prediccion_ia").delete()

    qualifying = (
        Shipment.query.filter(Shipment.prob_riesgo_incumplimiento >= threshold_pct)
        .order_by(Shipment.prob_riesgo_incumplimiento.desc())
        .all()
    )

    for s in qualifying:
        alert = Alert(
            shipment_id=s.id,
            id_viaje=s.id_viaje,
            tipo="prediccion_ia",
            severidad="Critica",
            titulo=f"Riesgo crítico de incumplimiento OTIF — {s.id_viaje}",
            descripcion=(
                f"El modelo de IA estima {s.prob_riesgo_incumplimiento}% de probabilidad de "
                f"incumplimiento OTIF para el corredor {s.corredor_logistico or 'N/D'} "
                f"({s.tipo_transporte or 'N/D'}, prioridad {s.prioridad_cliente or 'N/D'})."
            ),
            probabilidad_pct=s.prob_riesgo_incumplimiento,
            estado="Abierta",
        )
        db.session.add(alert)

    db.session.commit()
    return len(qualifying)
