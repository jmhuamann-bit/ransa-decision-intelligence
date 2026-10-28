"""Calculo de KPIs ejecutivos a partir de la tabla shipments. Sin SQL crudo: usa el ORM (SQLAlchemy)."""
from sqlalchemy import func

from app.extensions import db
from app.models.alert import Alert
from app.models.shipment import Shipment

# Factor de emision referencial diesel (kg CO2 por galon) - EPA/UPME, usado solo como estimador
CO2_KG_POR_GALON_DIESEL = 10.21


def _base_query(filtros: dict = None):
    q = Shipment.query
    filtros = filtros or {}
    if filtros.get("anio"):
        q = q.filter(Shipment.ano == filtros["anio"])
    if filtros.get("departamento_origen"):
        q = q.filter(Shipment.departamento_origen == filtros["departamento_origen"])
    if filtros.get("tipo_transporte"):
        q = q.filter(Shipment.tipo_transporte == filtros["tipo_transporte"])
    return q


def get_kpis(filtros: dict = None) -> dict:
    q = _base_query(filtros)

    total = q.count()
    if total == 0:
        return _empty_kpis()

    agg = q.with_entities(
        func.avg(Shipment.leadtime_real_dias),
        func.avg(Shipment.otif) * 100,
        func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen),
        func.sum(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen),
        func.avg(Shipment.consumo_combustible_galones),
        func.sum(Shipment.consumo_combustible_galones),
        func.avg(Shipment.nivel_servicio_pct),
        func.avg(Shipment.fill_rate_pct),
    ).first()

    (avg_leadtime, otif_pct, avg_costo, costo_total, avg_combustible,
     combustible_total, nivel_servicio, fill_rate) = agg

    co2_ton = ((combustible_total or 0) * CO2_KG_POR_GALON_DIESEL) / 1000

    contingencias_activas = Alert.query.filter(Alert.estado == "Abierta").count()
    incidentes = q.with_entities(func.sum(Shipment.numero_accidentes)).scalar() or 0

    riesgo_alto = q.filter(Shipment.nivel_riesgo.in_(["Alto", "Critico"])).count()
    riesgo_medio = q.filter(Shipment.nivel_riesgo == "Medio").count()
    riesgo_bajo = q.filter(Shipment.nivel_riesgo == "Bajo").count()

    return {
        "total_embarques": total,
        "lead_time_promedio_dias": round(avg_leadtime or 0, 2),
        "otif_pct": round(otif_pct or 0, 1),
        "costo_promedio_pen": round(avg_costo or 0, 0),
        "costo_total_pen": round(costo_total or 0, 0),
        "co2_toneladas": round(co2_ton, 2),
        "nivel_servicio_pct": round(nivel_servicio or 0, 1),
        "fill_rate_pct": round(fill_rate or 0, 1),
        "contingencias_activas": contingencias_activas,
        "incidentes_totales": int(incidentes),
        "distribucion_riesgo": {
            "bajo": riesgo_bajo,
            "medio": riesgo_medio,
            "alto_critico": riesgo_alto,
        },
    }


def _empty_kpis() -> dict:
    return {
        "total_embarques": 0, "lead_time_promedio_dias": 0, "otif_pct": 0,
        "costo_promedio_pen": 0, "costo_total_pen": 0, "co2_toneladas": 0,
        "nivel_servicio_pct": 0, "fill_rate_pct": 0, "contingencias_activas": 0,
        "incidentes_totales": 0,
        "distribucion_riesgo": {"bajo": 0, "medio": 0, "alto_critico": 0},
    }


def get_tendencia_mensual(filtros: dict = None) -> list:
    q = _base_query(filtros)
    rows = (
        q.with_entities(
            Shipment.ano,
            Shipment.mes,
            func.avg(Shipment.leadtime_real_dias),
            func.avg(Shipment.otif) * 100,
            func.count(Shipment.id),
        )
        .group_by(Shipment.ano, Shipment.mes)
        .all()
    )
    meses_orden = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                   "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    data = [
        {
            "anio": r[0], "mes": r[1],
            "lead_time_promedio": round(r[2] or 0, 2),
            "otif_pct": round(r[3] or 0, 1),
            "total": r[4],
            "_orden": (r[0], meses_orden.index(r[1]) if r[1] in meses_orden else 0),
        }
        for r in rows
    ]
    data.sort(key=lambda x: x["_orden"])
    for d in data:
        d.pop("_orden")
    return data


def get_top_corredores_riesgo(limit: int = 8) -> list:
    rows = (
        Shipment.query.with_entities(
            Shipment.corredor_logistico,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif_avg"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo_avg"),
        )
        .group_by(Shipment.corredor_logistico)
        .having(func.count(Shipment.id) >= 5)
        .order_by(func.avg(Shipment.prob_riesgo_incumplimiento).desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        {
            "corredor": r[0],
            "total_embarques": r[1],
            "otif_pct": round((r[2] or 0) * 100, 1),
            "riesgo_promedio_pct": round(r[3] or 0, 1),
        }
        for r in rows
    ]


def get_actividad_reciente(limit: int = 12) -> list:
    from app.models.alert import Alert as AlertModel
    alerts = AlertModel.query.order_by(AlertModel.creado_en.desc()).limit(limit).all()
    return [a.to_dict() for a in alerts]
