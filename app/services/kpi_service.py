"""KPIs desagregados para el panel detallado (complementa dashboard_service, que trae los KPIs
ejecutivos consolidados)."""
from sqlalchemy import func

from app.models.shipment import Shipment


def _agg_by(column):
    return (
        Shipment.query.with_entities(
            column.label("grupo"),
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.avg(Shipment.distancia_km).label("distancia"),
            func.avg(Shipment.consumo_combustible_galones).label("combustible"),
        )
        .group_by(column)
        .order_by(func.count(Shipment.id).desc())
        .all()
    )


def _row_to_dict(r) -> dict:
    return {
        "grupo": r.grupo,
        "total_embarques": r.total,
        "otif_pct": round((r.otif or 0) * 100, 1),
        "leadtime_promedio_dias": round(r.leadtime or 0, 2),
        "costo_promedio_pen": round(r.costo or 0, 0),
        "riesgo_promedio_pct": round(r.riesgo or 0, 1),
        "distancia_promedio_km": round(r.distancia or 0, 1),
        "combustible_promedio_galones": round(r.combustible or 0, 1),
    }


def get_kpis_por_transporte() -> list:
    return [_row_to_dict(r) for r in _agg_by(Shipment.tipo_transporte)]


def get_kpis_por_prioridad() -> list:
    return [_row_to_dict(r) for r in _agg_by(Shipment.prioridad_cliente)]


def get_comparativo_trimestral() -> list:
    rows = (
        Shipment.query.with_entities(
            Shipment.ano, Shipment.trimestre,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
        )
        .group_by(Shipment.ano, Shipment.trimestre)
        .order_by(Shipment.ano, Shipment.trimestre)
        .all()
    )
    return [
        {
            "periodo": f"{r.ano}-T{r.trimestre}",
            "total_embarques": r.total,
            "otif_pct": round((r.otif or 0) * 100, 1),
            "leadtime_promedio_dias": round(r.leadtime or 0, 2),
            "costo_promedio_pen": round(r.costo or 0, 0),
        }
        for r in rows
    ]
