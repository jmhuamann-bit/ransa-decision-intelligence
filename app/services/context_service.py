"""
Servicio de contexto de la Torre de Control.

Devuelve "fichas contextuales" uniformes para el cross-filtering del mapa: cuando el
usuario hace clic en la red completa, un corredor, un nodo (ciudad/puerto/aeropuerto) o un
vehículo, toda la Torre se recalcula para ESE ámbito. Reutiliza los servicios existentes
(dashboard, predictive, decision_assistant, geo_data) — no duplica lógica de negocio.

Forma uniforme de la ficha (la consume torre.js):
{
  "tipo": "red|corredor|nodo|vehiculo",
  "titulo": str, "subtitulo": str,
  "kpis":   [ {icon, bg, label, value, unit} ],   # unit ∈ int|num|pct|pen|ton|dias|h
  "detalle":[ {label, value} ],
  "flujo":  { "estado", "prediccion": {texto, prob_pct, impacto}, "plan", "resultado" },
  "serie":  { "labels": [], "leadtime": [], "otif": [] } | None,
}
"""
from sqlalchemy import case, func

from app.extensions import db
from app.models.shipment import Shipment
from app.services import dashboard_service, predictive_service
from app.services.decision_assistant import RULES
from app.services.geo_data import get_coords

CO2_KG_POR_GALON = dashboard_service.CO2_KG_POR_GALON_DIESEL


def _kpi(icon, bg, label, value, unit="num"):
    return {"icon": icon, "bg": bg, "label": label, "value": value, "unit": unit}


def _impacto_from_prob(prob):
    return "Muy Alto" if prob >= 85 else "Alto" if prob >= 60 else "Medio" if prob >= 35 else "Bajo"


def _flujo(estado, prob, categoria, scope_txt):
    """Arma el mini-flujo de decisión: Estado → Predicción → Plan → Resultado."""
    meta = predictive_service.CATEGORIAS.get(categoria, {"label": "riesgo operativo"})
    plan = RULES.get(categoria, {}).get("recomendacion", "Monitorear el ámbito y preparar plan de contingencia.")
    reduccion = round(min(60, prob * 0.5), 0)
    return {
        "estado": estado,
        "prediccion": {
            "texto": f"Mayor riesgo latente: {meta['label']} en {scope_txt}.",
            "prob_pct": round(prob, 1),
            "impacto": _impacto_from_prob(prob),
        },
        "plan": plan,
        "resultado": f"Ejecutar el plan podría reducir hasta ~{reduccion:.0f}% la exposición estimada.",
    }


# ---------------------------------------------------------------- RED
def get_red() -> dict:
    k = dashboard_service.get_kpis()
    tendencia = dashboard_service.get_tendencia_mensual()
    red_scores = predictive_service.get_category_network_scores()

    top_cat, top_prob = "infraestructura", 0.0
    for cat, data in red_scores.items():
        if data["probabilidad_24h_top"] > top_prob:
            top_cat, top_prob = cat, data["probabilidad_24h_top"]

    serie = None
    if tendencia:
        serie = {
            "labels": [f"{t['mes'][:3]} {t['anio']}" for t in tendencia],
            "leadtime": [t["lead_time_promedio"] for t in tendencia],
            "otif": [t["otif_pct"] for t in tendencia],
        }

    return {
        "tipo": "red",
        "titulo": "Toda la red logística",
        "subtitulo": "Operación nacional RANSA Perú — datos simulados",
        "kpis": [
            _kpi("fa-truck-fast", "gd-bg-blue", "Embarques", k["total_embarques"], "int"),
            _kpi("fa-bullseye", "gd-bg-success", "OTIF", k["otif_pct"], "pct"),
            _kpi("fa-clock", "gd-bg-accent", "Lead Time", k["lead_time_promedio_dias"], "dias"),
            _kpi("fa-sack-dollar", "gd-bg-warning", "Costo total", k["costo_total_pen"], "pen"),
            _kpi("fa-leaf", "gd-bg-success", "CO₂ estimado", k["co2_toneladas"], "ton"),
            _kpi("fa-gauge-high", "gd-bg-blue", "Nivel de servicio", k["nivel_servicio_pct"], "pct"),
            _kpi("fa-triangle-exclamation", "gd-bg-danger", "Contingencias activas", k["contingencias_activas"], "int"),
            _kpi("fa-shield-halved", "gd-bg-danger", "Riesgo alto/crítico", k["distribucion_riesgo"]["alto_critico"], "int"),
        ],
        "detalle": [
            {"label": "Fill rate", "value": f"{k['fill_rate_pct']}%"},
            {"label": "Incidentes registrados", "value": f"{k['incidentes_totales']:,}"},
        ],
        "flujo": _flujo(
            f"Red nacional operando con {k['total_embarques']:,} embarques y OTIF {k['otif_pct']}%.",
            top_prob, top_cat, "la red",
        ),
        "serie": serie,
    }


# ---------------------------------------------------------------- CORREDOR
def _dominant_category(row) -> str:
    signals = {
        "geologico": (row.derrumbes or 0) + (row.deslizamientos or 0),
        "hidrologico": (row.inundaciones or 0),
        "social": (row.protestas or 0),
        "infraestructura": (row.deterioro or 0) + (row.bloqueos or 0),
        "seguridad": 100 - (row.seguridad or 100),
        "accidentalidad": (row.tasa_accidentes or 0),
    }
    return max(signals, key=signals.get)


def get_corredor(nombre: str) -> dict | None:
    row = (
        Shipment.query.with_entities(
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("prob_riesgo"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.sum(Shipment.consumo_combustible_galones).label("combustible"),
            func.avg(Shipment.distancia_km).label("distancia"),
            func.avg(Shipment.indice_derrumbes).label("derrumbes"),
            func.avg(Shipment.indice_deslizamientos).label("deslizamientos"),
            func.avg(Shipment.indice_inundaciones).label("inundaciones"),
            func.avg(Shipment.indice_protestas).label("protestas"),
            func.avg(Shipment.indice_deterioro_vial).label("deterioro"),
            func.avg(Shipment.indice_bloqueos).label("bloqueos"),
            func.avg(Shipment.indice_seguridad).label("seguridad"),
            (func.sum(case((Shipment.numero_accidentes > 0, 1), else_=0)) * 100.0 / func.count(Shipment.id)).label("tasa_accidentes"),
            func.sum(case((Shipment.prioridad_cliente == "Crítica / Estratégico", 1), else_=0)).label("criticos"),
        )
        .filter(Shipment.corredor_logistico == nombre)
        .first()
    )
    if not row or not row.total:
        return None

    otif_pct = round((row.otif or 0) * 100, 1)
    co2_ton = round((row.combustible or 0) * CO2_KG_POR_GALON / 1000, 1)
    cat = _dominant_category(row)
    prob = round(row.prob_riesgo or 0, 1)

    serie = _serie_mensual_corredor(nombre)

    return {
        "tipo": "corredor",
        "titulo": nombre,
        "subtitulo": f"Corredor logístico · {row.total:,} embarques históricos",
        "kpis": [
            _kpi("fa-truck-fast", "gd-bg-blue", "Embarques", row.total, "int"),
            _kpi("fa-bullseye", "gd-bg-success", "OTIF", otif_pct, "pct"),
            _kpi("fa-clock", "gd-bg-accent", "Lead Time", round(row.leadtime or 0, 2), "dias"),
            _kpi("fa-gauge-high", "gd-bg-danger", "Riesgo promedio", prob, "pct"),
            _kpi("fa-sack-dollar", "gd-bg-warning", "Costo promedio", round(row.costo or 0), "pen"),
            _kpi("fa-leaf", "gd-bg-success", "CO₂ estimado", co2_ton, "ton"),
        ],
        "detalle": [
            {"label": "Distancia promedio", "value": f"{round(row.distancia or 0)} km"},
            {"label": "Clientes críticos", "value": str(row.criticos or 0)},
        ],
        "flujo": _flujo(
            f"Corredor con OTIF {otif_pct}% y riesgo promedio {prob}% sobre {row.total:,} viajes.",
            prob, cat, "este corredor",
        ),
        "serie": serie,
    }


def _serie_mensual_corredor(nombre: str) -> dict | None:
    rows = (
        Shipment.query.with_entities(
            Shipment.ano, Shipment.mes,
            func.avg(Shipment.leadtime_real_dias), func.avg(Shipment.otif) * 100, func.count(Shipment.id),
        )
        .filter(Shipment.corredor_logistico == nombre)
        .group_by(Shipment.ano, Shipment.mes)
        .all()
    )
    if not rows:
        return None
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    data = sorted(
        [{"anio": r[0], "mes": r[1], "lt": round(r[2] or 0, 2), "otif": round(r[3] or 0, 1)} for r in rows],
        key=lambda d: (d["anio"], meses.index(d["mes"]) if d["mes"] in meses else 0),
    )
    return {
        "labels": [f"{d['mes'][:3]} {d['anio']}" for d in data],
        "leadtime": [d["lt"] for d in data],
        "otif": [d["otif"] for d in data],
    }


# ---------------------------------------------------------------- NODO
def get_nodo(municipio: str) -> dict | None:
    coords = get_coords(municipio)
    if not coords:
        return None

    row = (
        Shipment.query.with_entities(
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("prob_riesgo"),
            func.avg(Shipment.tiempo_espera_horas).label("espera"),
            func.avg(Shipment.utilizacion_flota_pct).label("util_flota"),
            func.avg(Shipment.nivel_inventario_pct).label("inventario"),
            func.avg(Shipment.utilizacion_almacen_pct).label("util_almacen"),
        )
        .filter((Shipment.ciudad_origen == municipio) | (Shipment.ciudad_destino == municipio))
        .first()
    )
    if not row or not row.total:
        return None

    prob = round(row.prob_riesgo or 0, 1)
    vehiculos_ahora = _vehiculos_en_nodo(municipio)

    if coords["es_puerto"]:
        rol, icono = "Puerto marítimo", "fa-anchor"
        kpis = [
            _kpi("fa-ship", "gd-bg-blue", "Buques activos ahora", vehiculos_ahora.get("Marítimo", 0), "int"),
            _kpi("fa-boxes-stacked", "gd-bg-accent", "Embarques por el nodo", row.total, "int"),
            _kpi("fa-hourglass-half", "gd-bg-warning", "Espera promedio", round(row.espera or 0, 1), "h"),
            _kpi("fa-gauge-high", "gd-bg-danger", "Riesgo promedio", prob, "pct"),
        ]
        detalle = [{"label": "Congestión (espera)", "value": f"{round(row.espera or 0,1)} h promedio"},
                   {"label": "OTIF del nodo", "value": f"{round((row.otif or 0)*100,1)}%"}]
    elif coords["es_aeropuerto_principal"]:
        rol, icono = "Aeropuerto principal", "fa-plane"
        kpis = [
            _kpi("fa-plane", "gd-bg-blue", "Vuelos activos ahora", vehiculos_ahora.get("Aéreo", 0), "int"),
            _kpi("fa-boxes-stacked", "gd-bg-accent", "Embarques por el nodo", row.total, "int"),
            _kpi("fa-warehouse", "gd-bg-warning", "Ocupación flota", round(row.util_flota or 0, 1), "pct"),
            _kpi("fa-gauge-high", "gd-bg-danger", "Riesgo promedio", prob, "pct"),
        ]
        detalle = [{"label": "Espera promedio", "value": f"{round(row.espera or 0,1)} h"},
                   {"label": "OTIF del nodo", "value": f"{round((row.otif or 0)*100,1)}%"}]
    else:
        rol, icono = "Centro logístico", "fa-warehouse"
        kpis = [
            _kpi("fa-truck-fast", "gd-bg-blue", "Vehículos activos ahora", vehiculos_ahora.get("total", 0), "int"),
            _kpi("fa-boxes-stacked", "gd-bg-accent", "Embarques por el nodo", row.total, "int"),
            _kpi("fa-warehouse", "gd-bg-warning", "Utilización almacén", round(row.util_almacen or 0, 1), "pct"),
            _kpi("fa-layer-group", "gd-bg-success", "Nivel inventario", round(row.inventario or 0, 1), "pct"),
        ]
        detalle = [{"label": "Riesgo promedio", "value": f"{prob}%"},
                   {"label": "OTIF del nodo", "value": f"{round((row.otif or 0)*100,1)}%"}]

    return {
        "tipo": "nodo",
        "titulo": municipio,
        "subtitulo": f"{rol} · {row.total:,} embarques (origen + destino)",
        "icono": icono,
        "kpis": kpis,
        "detalle": detalle,
        "flujo": _flujo(
            f"{rol} con {row.total:,} embarques y riesgo promedio {prob}%.",
            prob, "infraestructura", f"el nodo {municipio}",
        ),
        "serie": None,
    }


def _vehiculos_en_nodo(municipio: str) -> dict:
    try:
        from app.services.live_engine import get_engine
        snap = get_engine().snapshot(0)
    except Exception:
        return {}
    conteo = {"total": 0}
    for v in snap["vehicles"]:
        if v["origen"]["nombre"] == municipio or v["destino"]["nombre"] == municipio:
            conteo["total"] += 1
            conteo[v["tipo_transporte"]] = conteo.get(v["tipo_transporte"], 0) + 1
    return conteo


# ---------------------------------------------------------------- VEHÍCULO
def get_vehiculo(id_viaje: str) -> dict | None:
    s = Shipment.query.filter_by(id_viaje=id_viaje).first()
    if not s:
        return None

    otif_txt = "Cumplió OTIF" if s.otif else "Incumplió OTIF"
    costo = (s.costo_transporte_pen or 0) + (s.costo_peajes_pen or 0)
    co2_ton = round((s.consumo_combustible_galones or 0) * CO2_KG_POR_GALON / 1000, 2)
    prob = round(s.prob_riesgo_incumplimiento or 0, 1)

    return {
        "tipo": "vehiculo",
        "titulo": f"{s.id_viaje}",
        "subtitulo": f"{s.ciudad_origen} → {s.ciudad_destino} · {s.tipo_transporte}",
        "kpis": [
            _kpi("fa-gauge-high", "gd-bg-danger", "Riesgo IA", prob, "pct"),
            _kpi("fa-clock", "gd-bg-accent", "Lead Time real", round(s.leadtime_real_dias or 0, 2), "dias"),
            _kpi("fa-sack-dollar", "gd-bg-warning", "Costo", round(costo), "pen"),
            _kpi("fa-leaf", "gd-bg-success", "CO₂ estimado", co2_ton, "ton"),
        ],
        "detalle": [
            {"label": "Corredor", "value": s.corredor_logistico},
            {"label": "Tipo de carga", "value": s.tipo_carga or "—"},
            {"label": "Prioridad cliente", "value": s.prioridad_cliente or "—"},
            {"label": "Sector cliente", "value": s.sector_cliente or "—"},
            {"label": "OTIF histórico", "value": otif_txt},
        ],
        "flujo": _flujo(
            f"Embarque {s.id_viaje} con prioridad {s.prioridad_cliente} y riesgo IA {prob}%.",
            prob, "infraestructura", f"el corredor {s.corredor_logistico}",
        ),
        "serie": None,
    }
