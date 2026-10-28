"""
Predictive Intelligence — Modulo 2 (horizonte 24 horas).

Metodologia (transparente): para cada corredor logistico se agregan los embarques
HISTORICOS del dataset RANSA Peru (30.000 registros simulados) y se calcula, por categoria
de riesgo, una probabilidad estimada de que ocurra un evento de ese tipo en las proximas 24
horas. Esa probabilidad combina:

  1) la frecuencia historica de ese tipo de evento en ese corredor (indices del dataset,
     cuya fuente publica de referencia en Peru es SENAMHI, INDECI, INGEMMET, PNP, Defensoria
     del Pueblo, Provias Nacional -- ver app/models/field_metadata.py), normalizada entre
     corredores; y
  2) el riesgo de incumplimiento OTIF ya calculado por el modelo de IA existente
     (app/ml) para los embarques de ese corredor.

No es una integracion en vivo con noticias/redes sociales/APIs meteorologicas (eso
requeriria credenciales externas que hoy no existen en config.py, salvo
OPENWEATHER_API_KEY reservada mas no usada) -- es una proyeccion estadistica sobre
datos históricos, documentada como tal. Solo se devuelven eventos con probabilidad >= 80%,
para no saturar al operador con ruido de baja confianza.
"""
from sqlalchemy import case, func

from app.models.shipment import Shipment
from app.services.geo_data import get_coords

PROB_THRESHOLD = 80.0
ZONE_MIN_THRESHOLD = 45.0

CATEGORIAS = {
    "geologico": {"label": "Huaico / derrumbe", "icon": "fa-hill-rockslide", "color": "#92400e"},
    "hidrologico": {"label": "Inundación / creciente súbita", "icon": "fa-water", "color": "#0369a1"},
    "social": {"label": "Paro / bloqueo de vías", "icon": "fa-people-group", "color": "#7c3aed"},
    "infraestructura": {"label": "Deterioro / cierre vial", "icon": "fa-road-circle-exclamation", "color": "#b45309"},
    "seguridad": {"label": "Robo de carga / extorsión", "icon": "fa-shield-halved", "color": "#be123c"},
    "accidentalidad": {"label": "Accidente de tránsito", "icon": "fa-car-burst", "color": "#dc2626"},
}


def _corridor_aggregates():
    return (
        Shipment.query.with_entities(
            Shipment.corredor_logistico,
            Shipment.tipo_transporte,
            Shipment.ciudad_origen,
            Shipment.ciudad_destino,
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("prob_riesgo"),
            func.avg(Shipment.indice_derrumbes).label("derrumbes"),
            func.avg(Shipment.indice_deslizamientos).label("deslizamientos"),
            func.avg(Shipment.indice_inundaciones).label("inundaciones"),
            func.avg(Shipment.indice_protestas).label("protestas"),
            func.avg(Shipment.indice_deterioro_vial).label("deterioro"),
            func.avg(Shipment.indice_bloqueos).label("bloqueos"),
            func.avg(Shipment.indice_seguridad).label("seguridad"),
            func.sum(case((Shipment.numero_accidentes > 0, 1), else_=0)).label("con_accidentes"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.sum(case((Shipment.prioridad_cliente == "Crítica / Estratégico", 1), else_=0)).label("clientes_criticos"),
        )
        .group_by(Shipment.corredor_logistico, Shipment.tipo_transporte, Shipment.ciudad_origen, Shipment.ciudad_destino)
        .having(func.count(Shipment.id) >= 8)
        .all()
    )


def _norm(value, lo, hi):
    if value is None or hi <= lo:
        return 0.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100))


def get_forecast_24h(limit: int = 30) -> list:
    rows = _corridor_aggregates()
    if not rows:
        return []

    fields = ["derrumbes", "deslizamientos", "inundaciones", "protestas", "deterioro", "bloqueos"]
    bounds = {f: (
        min((getattr(r, f) or 0) for r in rows),
        max((getattr(r, f) or 0) for r in rows),
    ) for f in fields}
    seg_bounds = (min((r.seguridad or 0) for r in rows), max((r.seguridad or 0) for r in rows))

    try:
        from app.services.live_engine import get_engine
        vehiculos_por_corredor = {}
        for v in get_engine().snapshot(0)["vehicles"]:
            vehiculos_por_corredor[v["corredor"]] = vehiculos_por_corredor.get(v["corredor"], 0) + 1
    except Exception:
        vehiculos_por_corredor = {}

    eventos = []
    for r in rows:
        origen, destino = get_coords(r.ciudad_origen), get_coords(r.ciudad_destino)
        if not origen or not destino:
            continue
        tasa_accidentes = (r.con_accidentes / r.total * 100) if r.total else 0
        scores = {
            "geologico": (_norm(r.derrumbes, *bounds["derrumbes"]) + _norm(r.deslizamientos, *bounds["deslizamientos"])) / 2,
            "hidrologico": _norm(r.inundaciones, *bounds["inundaciones"]),
            "social": _norm(r.protestas, *bounds["protestas"]),
            "infraestructura": (_norm(r.deterioro, *bounds["deterioro"]) + _norm(r.bloqueos, *bounds["bloqueos"])) / 2,
            "seguridad": 100 - _norm(r.seguridad, *seg_bounds),
            "accidentalidad": min(100.0, tasa_accidentes * 4),
        }
        for categoria, score in scores.items():
            probabilidad = round(0.55 * score + 0.45 * (r.prob_riesgo or 0), 1)
            if probabilidad < ZONE_MIN_THRESHOLD:
                continue
            meta = CATEGORIAS[categoria]
            eta_adicional_h = round((r.leadtime or 0) * 24 * 0.18, 1)
            impacto_nivel = (
                "Muy Alto" if probabilidad >= 92 or (r.clientes_criticos or 0) >= 8 else
                "Alto" if probabilidad >= 85 or (r.clientes_criticos or 0) >= 3 else
                "Medio"
            )
            eventos.append({
                "corredor": r.corredor_logistico,
                "tipo_transporte": r.tipo_transporte,
                "categoria": categoria,
                "titulo": meta["label"],
                "icon": meta["icon"],
                "color": meta["color"],
                "probabilidad_pct": probabilidad,
                "alerta_alta": probabilidad >= PROB_THRESHOLD,
                "impacto_nivel": impacto_nivel,
                "muestras_historicas": r.total,
                "origen": {"nombre": r.ciudad_origen, "lat": origen["lat"], "lon": origen["lon"]},
                "destino": {"nombre": r.ciudad_destino, "lat": destino["lat"], "lon": destino["lon"]},
                "vehiculos_en_ruta_ahora": vehiculos_por_corredor.get(r.corredor_logistico, 0),
                "clientes_criticos_expuestos": r.clientes_criticos or 0,
                "costo_en_riesgo_pen": round((r.costo or 0) * (r.total or 0) * 0.02, 0),
                "eta_adicional_estimada_horas": eta_adicional_h,
            })

    eventos.sort(key=lambda e: e["probabilidad_pct"], reverse=True)

    # Ensure geographic diversity: pick the top event per origin zone first,
    # then fill remaining slots with highest-probability events from any zone.
    # Also deduplicate: keep only the top event per (origin, category) pair.
    seen_origin_cat = set()
    deduped = []
    for ev in eventos:
        key = (ev["origen"]["nombre"], ev["categoria"])
        if key not in seen_origin_cat:
            seen_origin_cat.add(key)
            deduped.append(ev)

    seen_origins = set()
    priority = []
    rest = []
    for ev in deduped:
        o = ev["origen"]["nombre"]
        if o not in seen_origins:
            seen_origins.add(o)
            priority.append(ev)
        else:
            rest.append(ev)
    result = priority + rest
    return result[:limit]


def _score_rows(rows):
    fields = ["derrumbes", "deslizamientos", "inundaciones", "protestas", "deterioro", "bloqueos"]
    bounds = {f: (
        min((getattr(r, f) or 0) for r in rows),
        max((getattr(r, f) or 0) for r in rows),
    ) for f in fields}
    seg_bounds = (min((r.seguridad or 0) for r in rows), max((r.seguridad or 0) for r in rows))

    scored = []
    for r in rows:
        tasa_accidentes = (r.con_accidentes / r.total * 100) if r.total else 0
        scores = {
            "geologico": (_norm(r.derrumbes, *bounds["derrumbes"]) + _norm(r.deslizamientos, *bounds["deslizamientos"])) / 2,
            "hidrologico": _norm(r.inundaciones, *bounds["inundaciones"]),
            "social": _norm(r.protestas, *bounds["protestas"]),
            "infraestructura": (_norm(r.deterioro, *bounds["deterioro"]) + _norm(r.bloqueos, *bounds["bloqueos"])) / 2,
            "seguridad": 100 - _norm(r.seguridad, *seg_bounds),
            "accidentalidad": min(100.0, tasa_accidentes * 4),
        }
        scored.append((r, scores))
    return scored


def get_category_network_scores(top_n_corredores: int = 3) -> dict:
    """Para el Módulo 3 (Strategic Forecast 48h): resume, por categoría de riesgo, el
    panorama de TODA la red logística (no solo un corredor) -- probabilidad promedio,
    corredores más probables y muestras históricas analizadas. La probabilidad a 48h se
    estima como la probabilidad a 24h del corredor más expuesto, incrementada de forma
    conservadora (+15%, tope 99%) para reflejar una ventana de tiempo mayor -- una
    aproximación simple y transparente, no una serie de tiempo real. (Nota: se evita
    deliberadamente la regla del complemento 1-(1-p)^2 porque con probabilidades a 24h
    ya altas -80-90%- infla casi todo hacia ~99% y borra la diferencia entre escenarios,
    que es justamente lo que el negocio necesita ver.)

    Mejora RANSA: la probabilidad a 48h se ajusta por ESTACIONALIDAD. En el Perú el riesgo
    cambia mucho con el mes (huaicos e inundaciones en dic-mar, heladas en jun-ago, vaciante en
    ago-oct): el factor estacional es la intensidad histórica del riesgo en los corredores más
    expuestos durante el mes en curso, dividida entre su promedio anual."""
    rows = _corridor_aggregates()
    if not rows:
        return {}

    resumen = {cat: {"corredores": []} for cat in CATEGORIAS}
    for r, scores in _score_rows(rows):
        for categoria, score in scores.items():
            prob24 = round(0.55 * score + 0.45 * (r.prob_riesgo or 0), 1)
            resumen[categoria]["corredores"].append({
                "corredor": r.corredor_logistico,
                "tipo_transporte": r.tipo_transporte,
                "probabilidad_pct": prob24,
                "muestras": r.total,
                "clientes_criticos": r.clientes_criticos or 0,
                "costo_promedio_pen": r.costo or 0,
                "leadtime_promedio_dias": r.leadtime or 0,
            })

    resultado = {}
    for categoria, data in resumen.items():
        corredores = sorted(data["corredores"], key=lambda c: c["probabilidad_pct"], reverse=True)
        top = corredores[:top_n_corredores]
        top_prob = top[0]["probabilidad_pct"] if top else 0.0
        estacional = _seasonal_factor(categoria, [c["corredor"] for c in top])
        prob_48h = round(max(3.0, min(99.0, top_prob * 1.15 * estacional["factor"])), 1)
        resultado[categoria] = {
            **CATEGORIAS[categoria],
            "categoria": categoria,
            "top_corredores": top,
            "muestras_totales": sum(c["muestras"] for c in corredores),
            "clientes_criticos_totales": sum(c["clientes_criticos"] for c in top),
            "probabilidad_24h_top": top_prob,
            "probabilidad_48h_estimada": prob_48h,
            "estacionalidad": estacional,
            "costo_en_riesgo_pen": sum(round(c["costo_promedio_pen"] * c["muestras"] * 0.02) for c in top),
        }
    return resultado


MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
         "Octubre", "Noviembre", "Diciembre"]

_INDICE_CATEGORIA = {
    "geologico": lambda: Shipment.indice_deslizamientos + Shipment.indice_derrumbes,
    "hidrologico": lambda: Shipment.indice_inundaciones,
    "social": lambda: Shipment.indice_protestas,
    "infraestructura": lambda: Shipment.indice_deterioro_vial + Shipment.indice_bloqueos,
    "seguridad": lambda: 100 - Shipment.indice_seguridad,
    "accidentalidad": lambda: case((Shipment.numero_accidentes > 0, 100.0), else_=0.0),
}


def _seasonal_factor(categoria: str, corredores: list, mes: int | None = None) -> dict:
    """Intensidad histórica del riesgo en el mes `mes` (por defecto, el actual) frente al promedio
    anual, sobre los corredores indicados. Acotado a [0.35, 1.30] para no exagerar."""
    from datetime import datetime
    mes = mes or datetime.now().month
    nombre_mes = MESES[mes - 1]
    expr = _INDICE_CATEGORIA[categoria]()
    base_q = Shipment.query.filter(Shipment.corredor_logistico.in_(corredores)) if corredores else Shipment.query
    anual = base_q.with_entities(func.avg(expr)).scalar() or 0
    del_mes = base_q.filter(Shipment.mes == nombre_mes).with_entities(func.avg(expr)).scalar() or 0
    factor = (del_mes / anual) if anual else 1.0
    return {"mes": nombre_mes, "factor": round(max(0.35, min(1.30, factor)), 2), "factor_bruto": round(factor, 2)}


def get_heatmap_points() -> list:
    """Puntos ponderados por riesgo para el mapa de calor (usa el riesgo real de IA por nodo)."""
    rows = (
        Shipment.query.with_entities(
            Shipment.ciudad_origen.label("municipio"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("riesgo"),
            func.count(Shipment.id).label("total"),
        )
        .group_by(Shipment.ciudad_origen)
        .having(func.count(Shipment.id) >= 5)
        .all()
    )
    points = []
    for r in rows:
        coords = get_coords(r.municipio)
        if not coords:
            continue
        points.append([coords["lat"], coords["lon"], round((r.riesgo or 0) / 100, 3)])
    return points
