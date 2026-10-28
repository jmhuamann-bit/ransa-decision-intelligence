"""
Sirve los resultados del modelo estadístico de Lead Time (ACP + Regresión Múltiple).

El ajuste NO se hace en caliente: lo produce `backend/scripts/fit_leadtime_pca.py`, que
deja los resultados en `backend/data/models/leadtime_pca_results.json`. Este servicio solo
los lee y los cachea en memoria (el análisis tarda ~1 min por el cálculo de VIF sobre 76
variables, así que no tiene sentido rehacerlo por request).
"""
import json
import os

from flask import current_app

_cache: dict | None = None


def _results_path() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "data", "models", "leadtime_pca_results.json")


def get_model() -> dict | None:
    """Devuelve los resultados del modelo, o None si aún no se ha ejecutado el ajuste."""
    global _cache
    if _cache is not None:
        return _cache
    path = _results_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            _cache = json.load(f)
        ml_path = os.path.join(os.path.dirname(path), "regressors_metrics.json")
        if os.path.exists(ml_path):
            with open(ml_path, "r", encoding="utf-8") as f:
                _cache["ml_regresor"] = json.load(f)
        return _cache
    except (OSError, json.JSONDecodeError):
        current_app.logger.exception("No se pudo leer leadtime_pca_results.json")
        return None


def predict(factores: dict) -> dict | None:
    """Aplica la ecuación publicada a un vector de 5 factores dado por el usuario.

    Sirve para explorar la sensibilidad del Lead Time a cada factor: los factores son
    puntuaciones estandarizadas (media 0, desviación 1), así que un valor de +1 significa
    'una desviación estándar por encima de la operación promedio'.
    """
    model = get_model()
    if not model:
        return None
    reg = model["regresion"]
    total = reg["intercepto"]
    aportes = []
    for c in reg["coeficientes"]:
        valor = float(factores.get(c["factor"], 0) or 0)
        aporte = c["coef"] * valor
        total += aporte
        aportes.append({
            "factor": c["factor"],
            "etiqueta_real": c["etiqueta_real"],
            "valor": valor,
            "coef": c["coef"],
            "aporte_dias": round(aporte, 4),
        })
    return {
        "leadtime_estimado_dias": round(total, 3),
        "intercepto": reg["intercepto"],
        "aportes": aportes,
        "media_historica": model["objetivo"]["media"],
    }
