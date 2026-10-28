"""
El dataset RANSA Perú no incluye identidad de cliente (razón social/RUC), solo Sector_Cliente y
Prioridad_Cliente. Mientras se integra un maestro de clientes real, este servicio usa el cruce
Sector x Prioridad como "segmento de cliente" — el nivel de granularidad mas fino disponible en
los datos — para dar visibilidad de servicio por tipo de cliente.
"""
from sqlalchemy import func

from app.models.shipment import Shipment

SLA_OBJETIVO_OTIF_PCT = 90.0


def get_client_segments() -> list:
    rows = (
        Shipment.query.with_entities(
            Shipment.sector_cliente,
            Shipment.prioridad_cliente,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.avg(Shipment.fill_rate_pct).label("fill_rate"),
            func.avg(Shipment.nivel_servicio_pct).label("nivel_servicio"),
        )
        .group_by(Shipment.sector_cliente, Shipment.prioridad_cliente)
        .order_by(Shipment.sector_cliente)
        .all()
    )

    segments = []
    for r in rows:
        otif_pct = round((r.otif or 0) * 100, 1)
        segments.append({
            "sector_cliente": r.sector_cliente,
            "prioridad_cliente": r.prioridad_cliente,
            "total_embarques": r.total,
            "otif_pct": otif_pct,
            "cumple_sla": otif_pct >= SLA_OBJETIVO_OTIF_PCT,
            "leadtime_promedio_dias": round(r.leadtime or 0, 2),
            "costo_promedio_pen": round(r.costo or 0, 0),
            "riesgo_promedio_pct": round(r.riesgo or 0, 1),
            "fill_rate_pct": round(r.fill_rate or 0, 1),
            "nivel_servicio_pct": round(r.nivel_servicio or 0, 1),
        })
    return segments


def get_sector_summary() -> list:
    rows = (
        Shipment.query.with_entities(
            Shipment.sector_cliente,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
        )
        .group_by(Shipment.sector_cliente)
        .order_by(func.count(Shipment.id).desc())
        .all()
    )
    return [
        {
            "sector_cliente": r.sector_cliente,
            "total_embarques": r.total,
            "otif_pct": round((r.otif or 0) * 100, 1),
            "riesgo_promedio_pct": round(r.riesgo or 0, 1),
        }
        for r in rows
    ]
