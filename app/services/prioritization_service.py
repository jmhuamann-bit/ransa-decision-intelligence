"""
Priorización de carga (heurística H2) — cola de triaje.

Responde la pregunta que un Director de Operaciones se hace en plena crisis:
**"si no puedo despachar todo, ¿qué carga sale primero?"**

Puntaje multicriterio ponderado sobre los embarques en riesgo, combinando:
  * criterio humanitario/esencial (sector del cliente: salud primero),
  * criticidad comercial (prioridad del cliente),
  * valor económico de la carga (valor asegurado),
  * penalización por costo de la operación,
  * riesgo de incumplimiento calculado por el modelo de IA.

Los pesos y los puntajes por sector son supuestos de negocio explícitos y auditables
(declarados abajo), no salidas de un modelo entrenado.
"""
from app.models.shipment import Shipment

PESOS = {"humanitario": 0.35, "criticidad": 0.25, "valor": 0.20, "penalizacion": 0.10, "riesgo": 0.10}

SECTOR_SCORES = {
    "Salud": 100,             # medicamentos y dispositivos médicos: criterio humanitario
    "Agroexportación": 85,    # perecible con ventana de embarque y cadena de frío
    "Consumo Masivo": 70,     # alimentos y abastecimiento básico de la población
    "Pesca": 65,              # congelados con cadena de frío
    "Minería": 55,            # alto valor, pero tolera reprogramación
    "Tecnología": 50,
    "Retail": 45,
    "Industrial": 40,
    "Automotriz": 35,         # vehículos nuevos: alto valor, tolera reprogramación
}
PRIORIDAD_SCORES = {"Crítica / Estratégico": 100, "Alta": 70, "Estándar": 40}

UMBRAL_RIESGO_PCT = 60.0
CANDIDATOS = 200


def _nivel(score: float) -> str:
    return "CRÍTICA" if score >= 70 else "ALTA" if score >= 55 else "MEDIA" if score >= 40 else "BAJA"


def _norm(value, lo, hi):
    if value is None or hi <= lo:
        return 50.0
    return max(0.0, min(100.0, (value - lo) / (hi - lo) * 100))


def get_queue(limit: int = 20) -> dict:
    rows = (
        Shipment.query
        .filter(Shipment.prob_riesgo_incumplimiento >= UMBRAL_RIESGO_PCT)
        .order_by(Shipment.prob_riesgo_incumplimiento.desc())
        .limit(CANDIDATOS)
        .all()
    )
    if not rows:
        return {"items": [], "pesos": _pesos_publicos(), "sector_scores": SECTOR_SCORES, "candidatos": 0}

    valores = [r.valor_asegurado_pen or 0 for r in rows]
    costos = [(r.costo_transporte_pen or 0) + (r.costo_peajes_pen or 0) for r in rows]
    v_lo, v_hi = min(valores), max(valores)
    c_lo, c_hi = min(costos), max(costos)

    items = []
    for r in rows:
        hum = SECTOR_SCORES.get(r.sector_cliente, 50)
        crit = PRIORIDAD_SCORES.get(r.prioridad_cliente, 40)
        costo = (r.costo_transporte_pen or 0) + (r.costo_peajes_pen or 0)
        valor = _norm(r.valor_asegurado_pen or 0, v_lo, v_hi)
        pen = _norm(costo, c_lo, c_hi)
        riesgo = r.prob_riesgo_incumplimiento or 0

        score = round(
            PESOS["humanitario"] * hum
            + PESOS["criticidad"] * crit
            + PESOS["valor"] * valor
            + PESOS["penalizacion"] * pen
            + PESOS["riesgo"] * riesgo,
            1,
        )
        items.append({
            "id_viaje": r.id_viaje,
            "corredor": r.corredor_logistico,
            "sector_cliente": r.sector_cliente,
            "prioridad_cliente": r.prioridad_cliente,
            "tipo_carga": r.tipo_carga,
            "tipo_transporte": r.tipo_transporte,
            "riesgo_pct": round(riesgo, 1),
            "valor_asegurado_pen": round(r.valor_asegurado_pen or 0),
            "costo_pen": round(costo),
            "score": score,
            "nivel": _nivel(score),
        })

    items.sort(key=lambda i: i["score"], reverse=True)
    for idx, item in enumerate(items, start=1):
        item["rank"] = idx

    return {
        "items": items[:limit],
        "pesos": _pesos_publicos(),
        "sector_scores": SECTOR_SCORES,
        "candidatos": len(items),
        "umbral_riesgo_pct": UMBRAL_RIESGO_PCT,
    }


def _pesos_publicos() -> list:
    etiquetas = {
        "humanitario": "Criterio humanitario (sector)",
        "criticidad": "Criticidad del cliente",
        "valor": "Valor de la carga",
        "penalizacion": "Costo de la operación",
        "riesgo": "Riesgo de incumplimiento (IA)",
    }
    return [{"criterio": etiquetas[k], "peso_pct": round(v * 100)} for k, v in PESOS.items()]
