"""
Motor del Simulador de Escenarios.

Arma un escenario completo: toma las variables que el usuario controla en el formulario (corredor,
transporte, prioridad, clima, capacidad...), completa el resto de las ~72 variables del modelo con
valores tipicos (perfil historico del corredor elegido cuando existe, o la mediana/moda global) y
llama al motor de prediccion de IA (clasificador de riesgo OTIF + regresores de Lead Time y Costo).
"""
import pandas as pd

from app.extensions import db
from app.ml.data import dataset
from app.ml.prediction import predictor
from app.models.shipment import Shipment

_global_defaults_cache: dict | None = None

FORM_FIELDS = [
    "corredor_logistico", "tipo_transporte", "tipo_vehiculo", "tipo_carga", "prioridad_cliente",
    "peso_toneladas", "volumen_m3", "disponibilidad_flota_pct", "alerta_senamhi", "estado_via",
]


def invalidate_cache() -> None:
    global _global_defaults_cache
    _global_defaults_cache = None


def get_form_options() -> dict:
    def distinct(column):
        rows = db.session.query(column).distinct().order_by(column).all()
        return [r[0] for r in rows if r[0] not in (None, "")]

    return {
        "corredor_logistico": distinct(Shipment.corredor_logistico),
        "tipo_transporte": distinct(Shipment.tipo_transporte),
        "tipo_vehiculo": distinct(Shipment.tipo_vehiculo),
        "tipo_carga": distinct(Shipment.tipo_carga),
        "prioridad_cliente": distinct(Shipment.prioridad_cliente),
        "alerta_senamhi": distinct(Shipment.alerta_senamhi),
        "estado_via": distinct(Shipment.estado_via),
    }


def _compute_global_defaults() -> dict:
    columns = dataset.ALL_FEATURES
    rows = db.session.query(Shipment).with_entities(*[getattr(Shipment, c) for c in columns]).all()
    df = pd.DataFrame(rows, columns=columns)

    defaults = {}
    for c in dataset.NUMERIC_FEATURES:
        defaults[c] = float(df[c].median()) if df[c].notna().any() else 0.0
    for c in dataset.CATEGORICAL_FEATURES:
        mode = df[c].mode()
        defaults[c] = mode.iloc[0] if not mode.empty else None
    return defaults


def get_global_defaults() -> dict:
    global _global_defaults_cache
    if _global_defaults_cache is None:
        _global_defaults_cache = _compute_global_defaults()
    return _global_defaults_cache


def get_corredor_profile(corredor: str) -> dict | None:
    rows = Shipment.query.filter(Shipment.corredor_logistico == corredor).all()
    if not rows:
        return None

    df = pd.DataFrame([{
        "departamento_origen": r.departamento_origen,
        "departamento_destino": r.departamento_destino,
        "ruta_principal": r.ruta_principal,
        "distancia_km": r.distancia_km,
        "tiempo_programado_horas": r.tiempo_programado_horas,
        "leadtime_real_dias": r.leadtime_real_dias,
        "costo_total_pen": (r.costo_transporte_pen or 0) + (r.costo_peajes_pen or 0),
        "otif": r.otif,
    } for r in rows])

    def mode_of(col):
        m = df[col].mode()
        return m.iloc[0] if not m.empty else None

    return {
        "campos": {
            "departamento_origen": mode_of("departamento_origen"),
            "departamento_destino": mode_of("departamento_destino"),
            "ruta_principal": mode_of("ruta_principal"),
            "distancia_km": float(df["distancia_km"].median()),
            "tiempo_programado_horas": float(df["tiempo_programado_horas"].median()),
        },
        "baseline": {
            "leadtime_dias_historico": round(float(df["leadtime_real_dias"].median()), 2),
            "costo_pen_historico": round(float(df["costo_total_pen"].median()), 0),
            "otif_pct_historico": round(float(df["otif"].mean()) * 100, 1),
            "muestras": len(df),
        },
    }


def simulate(overrides: dict) -> dict:
    scenario = dict(get_global_defaults())

    baseline = None
    corredor = overrides.get("corredor_logistico")
    if corredor:
        profile = get_corredor_profile(corredor)
        if profile:
            scenario.update(profile["campos"])
            baseline = profile["baseline"]

    for field in FORM_FIELDS:
        value = overrides.get(field)
        if value not in (None, ""):
            scenario[field] = value

    prob = predictor.predict_single(scenario)
    if prob is None:
        raise RuntimeError("No hay un modelo de IA activo. Entrena el modelo en Modelos IA primero.")

    leadtime = predictor.predict_leadtime(scenario)
    costo = predictor.predict_costo(scenario)

    return {
        "prob_riesgo_incumplimiento": prob,
        "nivel_riesgo": predictor.bucket_risk(prob),
        "otif_esperado_pct": round(100 - prob, 1),
        "leadtime_dias": leadtime,
        "costo_pen": costo,
        "baseline": baseline,
        "escenario_usado": {k: scenario.get(k) for k in FORM_FIELDS},
    }
