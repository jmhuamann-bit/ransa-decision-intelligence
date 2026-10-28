"""
Generador de planes de contingencia alternativos (Plan A / B / C / D) — Centro de
Contingencias Inteligente.

Para un corredor y una categoría de riesgo, arma 4 planes de acción COMPARABLES lado a
lado, cada uno con su costo, tiempo, CO₂, OTIF esperado, nivel de riesgo, ventajas y
desventajas, más la recomendación de la IA (el plan con mejor puntaje compuesto).

Metodología (transparente):
  * La LÍNEA BASE sale de los datos históricos del corredor (costo, lead time, OTIF y consumo
    de combustible promedio de sus embarques históricos).
  * El escenario "SIN ACCIÓN" degrada esa línea base en función del riesgo real del
    corredor (`prob_riesgo_incumplimiento`, calculado por el modelo de IA).
  * Cada plan aplica factores de ajuste propios de su naturaleza logística (desviar cuesta
    más pero baja el riesgo; reprogramar casi no cuesta pero sacrifica OTIF, etc.).
    Esos factores son heurísticos y están declarados aquí de forma explícita: son
    supuestos de negocio auditables, NO salidas de un modelo entrenado.
  * El OTIF de cada plan se modela como RECUPERACIÓN de una fracción del OTIF que el
    evento hizo perder (la brecha entre "sin acción" y la línea base del corredor). Ningún
    plan supera el desempeño histórico del corredor: un plan de contingencia mitiga el
    daño, no mejora la operación normal.
"""
from sqlalchemy import func

from app.models.shipment import Shipment
from app.services import dashboard_service, predictive_service

CO2_KG_POR_GALON = dashboard_service.CO2_KG_POR_GALON_DIESEL

# Pesos del puntaje compuesto que define la recomendación de la IA.
PESOS = {"otif": 0.40, "costo": 0.20, "tiempo": 0.20, "co2": 0.10, "riesgo": 0.10}

PLANES = [
    {
        "id": "A", "nombre": "Desviar operaciones", "icon": "fa-diamond-turn-right",
        "descripcion": "Redirigir la carga por un corredor alterno que evita el punto de riesgo.",
        "d_costo": 0.18, "d_tiempo": 0.10, "d_co2": 0.16, "r_otif": 0.75, "d_riesgo": -0.50,
        "ventajas": ["Mantiene el flujo sin detener la operación.", "Reduce fuertemente la exposición al evento."],
        "desventajas": ["Mayor costo de flete y peajes.", "Requiere que exista ruta alterna disponible."],
    },
    {
        "id": "B", "nombre": "Cambiar modalidad", "icon": "fa-ship",
        "descripcion": "Migrar la carga a otro modo (cabotaje Callao–Paita/Matarani, aéreo o fluvial) para sortear el corredor afectado.",
        "d_costo": 0.35, "d_tiempo": -0.15, "d_co2": -0.22, "r_otif": 0.65, "d_riesgo": -0.40,
        "ventajas": ["Evita por completo la vía afectada.", "Menor huella de CO₂ en tramos largos."],
        "desventajas": ["Costo significativamente mayor.", "Depende del cupo y la frecuencia del modo alterno."],
    },
    {
        "id": "C", "nombre": "Redistribuir inventario", "icon": "fa-warehouse",
        "descripcion": "Abastecer al cliente desde otro centro de distribución o almacén más cercano al destino.",
        "d_costo": 0.08, "d_tiempo": -0.25, "d_co2": -0.30, "r_otif": 0.45, "d_riesgo": -0.30,
        "ventajas": ["Costo incremental bajo.", "Acorta el tiempo de entrega al cliente."],
        "desventajas": ["Requiere inventario disponible en el nodo alterno.", "No aplica a carga dedicada o de proyecto."],
    },
    {
        "id": "D", "nombre": "Reprogramar entregas", "icon": "fa-calendar-check",
        "descripcion": "Posponer los despachos no críticos hasta que el corredor se normalice.",
        "d_costo": -0.05, "d_tiempo": 0.40, "d_co2": -0.05, "r_otif": 0.20, "d_riesgo": -0.55,
        "ventajas": ["Costo mínimo, casi nulo.", "Elimina la exposición al riesgo."],
        "desventajas": ["Incumple la ventana de entrega comprometida.", "Impacta el OTIF y la satisfacción del cliente."],
    },
]


def _baseline(corredor: str) -> dict | None:
    row = (
        Shipment.query.with_entities(
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.avg(Shipment.leadtime_real_dias).label("leadtime"),
            func.avg(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.avg(Shipment.consumo_combustible_galones).label("combustible"),
            func.avg(Shipment.prob_riesgo_incumplimiento).label("prob_riesgo"),
        )
        .filter(Shipment.corredor_logistico == corredor)
        .first()
    )
    if not row or not row.total:
        return None
    return {
        "muestras": row.total,
        "otif_pct": round((row.otif or 0) * 100, 1),
        "leadtime_dias": round(row.leadtime or 0, 2),
        "costo_pen": round(row.costo or 0),
        "co2_ton": round((row.combustible or 0) * CO2_KG_POR_GALON / 1000, 3),
        "prob_riesgo_pct": round(row.prob_riesgo or 0, 1),
    }


def _nivel_riesgo(pct: float) -> str:
    return "Crítico" if pct >= 80 else "Alto" if pct >= 60 else "Medio" if pct >= 35 else "Bajo"


def _minmax(values):
    lo, hi = min(values), max(values)
    span = hi - lo
    return [(0.5 if span == 0 else (v - lo) / span) for v in values]


def generate_plans(corredor: str, categoria: str) -> dict | None:
    base = _baseline(corredor)
    if not base:
        return None

    prob = base["prob_riesgo_pct"]
    meta = predictive_service.CATEGORIAS.get(categoria, {"label": "Riesgo operativo", "icon": "fa-triangle-exclamation", "color": "#64748b"})

    # Escenario "no hacer nada" mientras ocurre el evento: la línea base se degrada.
    sin_accion = {
        "nombre": "Sin acción",
        "costo_pen": round(base["costo_pen"] * 1.22),
        "leadtime_dias": round(base["leadtime_dias"] * 1.35, 2),
        "co2_ton": round(base["co2_ton"] * 1.18, 3),
        "otif_pct": round(max(5.0, base["otif_pct"] - prob * 0.45), 1),
        "riesgo_pct": round(min(99.0, prob * 1.15), 1),
    }
    sin_accion["nivel_riesgo"] = _nivel_riesgo(sin_accion["riesgo_pct"])

    planes = []
    for p in PLANES:
        costo = round(base["costo_pen"] * (1 + p["d_costo"]))
        tiempo = round(base["leadtime_dias"] * (1 + p["d_tiempo"]), 2)
        co2 = round(base["co2_ton"] * (1 + p["d_co2"]), 3)
        # El plan recupera una fracción del OTIF perdido por el evento (nunca supera el histórico).
        brecha = max(0.0, base["otif_pct"] - sin_accion["otif_pct"])
        otif = round(min(99.0, sin_accion["otif_pct"] + brecha * p["r_otif"]), 1)
        riesgo = round(max(3.0, sin_accion["riesgo_pct"] * (1 + p["d_riesgo"])), 1)
        planes.append({
            "id": p["id"], "nombre": p["nombre"], "icon": p["icon"], "descripcion": p["descripcion"],
            "costo_pen": costo, "leadtime_dias": tiempo, "co2_ton": co2,
            "otif_pct": otif, "riesgo_pct": riesgo, "nivel_riesgo": _nivel_riesgo(riesgo),
            "ventajas": p["ventajas"], "desventajas": p["desventajas"],
            "delta_costo_pct": round(p["d_costo"] * 100),
            "delta_otif_pts": round(otif - sin_accion["otif_pct"], 1),
        })

    # Puntaje compuesto (normalizado entre los 4 planes): OTIF alto es bueno; costo,
    # tiempo, CO₂ y riesgo bajos son buenos.
    n_otif = _minmax([p["otif_pct"] for p in planes])
    n_costo = _minmax([p["costo_pen"] for p in planes])
    n_tiempo = _minmax([p["leadtime_dias"] for p in planes])
    n_co2 = _minmax([p["co2_ton"] for p in planes])
    n_riesgo = _minmax([p["riesgo_pct"] for p in planes])
    for i, p in enumerate(planes):
        p["score"] = round(100 * (
            PESOS["otif"] * n_otif[i]
            + PESOS["costo"] * (1 - n_costo[i])
            + PESOS["tiempo"] * (1 - n_tiempo[i])
            + PESOS["co2"] * (1 - n_co2[i])
            + PESOS["riesgo"] * (1 - n_riesgo[i])
        ), 1)

    recomendado = max(planes, key=lambda p: p["score"])
    for p in planes:
        p["recomendado"] = p["id"] == recomendado["id"]

    return {
        "corredor": corredor,
        "categoria": categoria,
        "titulo_riesgo": meta["label"],
        "icon": meta["icon"],
        "color": meta["color"],
        "baseline": base,
        "sin_accion": sin_accion,
        "planes": planes,
        "recomendado": recomendado["id"],
        "justificacion_recomendacion": (
            f"El Plan {recomendado['id']} ({recomendado['nombre']}) obtiene el mejor puntaje compuesto "
            f"({recomendado['score']}/100) ponderando OTIF esperado ({int(PESOS['otif']*100)}%), costo "
            f"({int(PESOS['costo']*100)}%), tiempo ({int(PESOS['tiempo']*100)}%), CO₂ ({int(PESOS['co2']*100)}%) "
            f"y riesgo residual ({int(PESOS['riesgo']*100)}%), sobre la línea base histórica de "
            f"{base['muestras']:,} embarques del corredor."
        ),
    }
