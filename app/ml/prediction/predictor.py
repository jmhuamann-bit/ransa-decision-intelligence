"""Servir predicciones del modelo activo: ni entrena ni calcula metricas, solo carga el
artefacto guardado y predice. Lo usan el script de carga masiva, la API y el Simulador."""
import os

import joblib
import pandas as pd

from app.config import MODELS_DIR
from app.ml.data.dataset import ALL_FEATURES, ALL_FEATURES_FOR_COST
from app.models.ml_model import MLModelRun

_cache = {"run_id": None, "pipeline": None}
_regressor_cache: dict = {}


def get_active_model_run() -> MLModelRun | None:
    return MLModelRun.query.filter_by(activo=True).order_by(MLModelRun.creado_en.desc()).first()


def load_active_pipeline():
    run = get_active_model_run()
    if not run:
        return None, None
    if _cache["run_id"] != run.id:
        _cache["pipeline"] = joblib.load(resolve_artifact_path(run.ruta_artefacto))
        _cache["run_id"] = run.id
    return _cache["pipeline"], run


def resolve_artifact_path(path: str) -> str:
    """Los artefactos se guardan con ruta relativa a MODELS_DIR (portables entre máquinas);
    se aceptan también rutas absolutas antiguas si el archivo existe."""
    if path and os.path.isabs(path) and os.path.exists(path):
        return path
    return os.path.join(MODELS_DIR, os.path.basename(path.replace("\\", "/")))


def predict_proba_pct(X: pd.DataFrame) -> "pd.Series | None":
    """Devuelve la probabilidad de INCUMPLIMIENTO de OTIF (0-100) para cada fila de X."""
    pipeline, run = load_active_pipeline()
    if pipeline is None:
        return None
    proba = pipeline.predict_proba(X[ALL_FEATURES])[:, 1] * 100
    return pd.Series(proba, index=X.index).round(1)


def predict_single(input_dict: dict) -> float | None:
    """Predice la probabilidad de incumplimiento (0-100) para un unico escenario (usado por el Simulador)."""
    pipeline, run = load_active_pipeline()
    if pipeline is None:
        return None
    row = {f: input_dict.get(f) for f in ALL_FEATURES}
    df = pd.DataFrame([row])
    proba = pipeline.predict_proba(df[ALL_FEATURES])[:, 1][0] * 100
    return round(float(proba), 1)


def _load_regressor(target: str):
    path = os.path.join(MODELS_DIR, f"regressor_{target}.joblib")
    if not os.path.exists(path):
        return None
    if target not in _regressor_cache:
        _regressor_cache[target] = joblib.load(path)
    return _regressor_cache[target]


def predict_leadtime(input_dict: dict) -> float | None:
    pipeline = _load_regressor("leadtime_real_dias")
    if pipeline is None:
        return None
    row = {f: input_dict.get(f) for f in ALL_FEATURES}
    df = pd.DataFrame([row])
    value = float(pipeline.predict(df[ALL_FEATURES])[0])
    return round(max(value, 0.0), 2)


def predict_costo(input_dict: dict) -> float | None:
    pipeline = _load_regressor("costo_total_pen")
    if pipeline is None:
        return None
    row = {f: input_dict.get(f) for f in ALL_FEATURES_FOR_COST}
    df = pd.DataFrame([row])
    value = float(pipeline.predict(df[ALL_FEATURES_FOR_COST])[0])
    return round(max(value, 0.0), 0)


def bucket_risk(prob_pct: float) -> str:
    if prob_pct >= 75:
        return "Critico"
    if prob_pct >= 50:
        return "Alto"
    if prob_pct >= 25:
        return "Medio"
    return "Bajo"
