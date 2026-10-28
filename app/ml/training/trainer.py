"""
Entrenamiento de modelos de Predicciones IA.

Arquitectura desacoplada por diseño: este módulo NO sabe de dónde vienen los datos (eso es
app/ml/data), ni cómo se calculan las métricas (eso es app/ml/evaluation), ni cómo se sirven
las predicciones (eso es app/ml/prediction). Solo arma el pipeline de scikit-learn, lo entrena
y evalúa.

Algoritmos disponibles (todos incluidos en scikit-learn, sin dependencias adicionales):
  * logistic_regression — línea base interpretable (coeficientes estandarizados).
  * gradient_boosting   — HistGradientBoosting: capta efectos NO lineales e interacciones propias
    de la operación peruana (p. ej. el riesgo de huaico solo se dispara en temporada de lluvias y
    en tramos de sierra; la vaciante solo pesa en ago-oct). Su importancia de variables se mide por
    permutación (caída de AUC al desordenar cada variable).
Para agregar otro algoritmo basta con registrarlo en ALGORITHMS: imputación, codificación,
evaluación y persistencia se reutilizan sin cambios.
"""
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from app.config import MODELS_DIR
from app.extensions import db
from app.ml.data.dataset import (
    ALL_FEATURES, ALL_FEATURES_FOR_COST, CATEGORICAL_FEATURES, NUMERIC_FEATURES, NUMERIC_FEATURES_FOR_COST,
    load_training_dataframe, split_features_target, split_regression_target,
)
from app.ml.evaluation.metrics import (
    compute_classification_metrics, compute_confusion_matrix,
    compute_logreg_importance, compute_roc_curve,
)
from app.models.ml_model import MLModelRun

ALGORITHMS = {
    "logistic_regression": lambda: LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
    "gradient_boosting": lambda: HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31, l2_regularization=0.5,
        categorical_features=list(range(len(NUMERIC_FEATURES), len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES))),
        class_weight="balanced", random_state=42),
}

ALGORITHM_LABELS = {
    "logistic_regression": "Regresión Logística",
    "gradient_boosting": "Gradient Boosting (HistGB)",
}

# Config de los regresores auxiliares que alimentan al Simulador (no son el modelo de riesgo OTIF)
REGRESSION_TARGETS = {
    "leadtime_real_dias": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES, "label": "Lead Time (días)"},
    "costo_total_pen": {"numeric": NUMERIC_FEATURES_FOR_COST, "categorical": CATEGORICAL_FEATURES, "label": "Costo total (S/)"},
}


def _build_preprocessor(numeric_features, categorical_features) -> ColumnTransformer:
    numeric_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    return ColumnTransformer([
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ])


def _build_tree_preprocessor(numeric_features, categorical_features) -> ColumnTransformer:
    """Para árboles: numéricas tal cual (HistGB maneja NaN de forma nativa) y categóricas como
    códigos ordinales; las categorías desconocidas o faltantes quedan en -1 (= faltante)."""
    return ColumnTransformer([
        ("num", "passthrough", numeric_features),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1, encoded_missing_value=-1),
         categorical_features),
    ])


def build_pipeline(algorithm: str = "logistic_regression") -> Pipeline:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Algoritmo no soportado: {algorithm}. Disponibles: {list(ALGORITHMS)}")
    if algorithm == "gradient_boosting":
        preprocessor = _build_tree_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    else:
        preprocessor = _build_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", ALGORITHMS[algorithm]()),
    ])


def build_regression_pipeline(numeric_features, categorical_features) -> Pipeline:
    preprocessor = _build_tree_preprocessor(numeric_features, categorical_features)
    n_num, n_cat = len(numeric_features), len(categorical_features)
    return Pipeline([
        ("preprocessor", preprocessor),
        # HistGradientBoosting: captura la no linealidad de la red peruana (un mismo km en sierra
        # cuesta y demora mucho más que en costa) mejor que una regresión lineal.
        ("regressor", HistGradientBoostingRegressor(max_iter=300, learning_rate=0.07, max_leaf_nodes=31,
                                                    categorical_features=list(range(n_num, n_num + n_cat)),
                                                    random_state=42)),
    ])


def _permutation_importance(pipeline, X_test, y_test, top_n: int = 15) -> list:
    sample = X_test.sample(n=min(2500, len(X_test)), random_state=7)
    y_sample = y_test.loc[sample.index]
    result = permutation_importance(pipeline, sample, y_sample, scoring="roc_auc", n_repeats=3, random_state=7, n_jobs=1)
    items = [
        {"variable": name, "coeficiente": round(float(mean), 4), "direccion": "aumenta_riesgo"}
        for name, mean in zip(ALL_FEATURES, result.importances_mean)
    ]
    items.sort(key=lambda x: x["coeficiente"], reverse=True)
    return items[:top_n]


def train_and_evaluate(algorithm: str = "logistic_regression", test_size: float = 0.2,
                       random_state: int = 42, activate: bool = True) -> MLModelRun:
    df = load_training_dataframe()
    X, y = split_features_target(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # 1) Pipeline de evaluación: se entrena SOLO con el conjunto de entrenamiento para poder
    #    medir el desempeño real sobre datos que el modelo no vio (conjunto de prueba).
    eval_pipeline = build_pipeline(algorithm)
    eval_pipeline.fit(X_train, y_train)
    y_pred = eval_pipeline.predict(X_test)
    y_proba = eval_pipeline.predict_proba(X_test)[:, 1]

    metrics = compute_classification_metrics(y_test, y_pred, y_proba)
    confusion = compute_confusion_matrix(y_test, y_pred)
    roc = compute_roc_curve(y_test, y_proba)
    if algorithm == "logistic_regression":
        importance = compute_logreg_importance(eval_pipeline, top_n=15)
    else:
        importance = _permutation_importance(eval_pipeline, X_test, y_test, top_n=15)

    # 2) Pipeline de producción: se re-entrena con el 100% de los datos (más datos = mejor modelo
    #    final) para generar las predicciones que se guardan en cada embarque y para el simulador.
    #    Las métricas reportadas SIEMPRE provienen del paso 1 (conjunto de prueba), nunca de este.
    production_pipeline = build_pipeline(algorithm)
    production_pipeline.fit(X, y)

    os.makedirs(MODELS_DIR, exist_ok=True)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    artifact_path = os.path.join(MODELS_DIR, f"{algorithm}_{version}.joblib")
    joblib.dump(production_pipeline, artifact_path)

    if activate:
        db.session.query(MLModelRun).update({MLModelRun.activo: False})

    run = MLModelRun(
        algoritmo=algorithm,
        version=version,
        objetivo="incumplimiento_otif",
        activo=activate,
        accuracy=metrics["accuracy"],
        precision_=metrics["precision"],
        recall=metrics["recall"],
        f1_score=metrics["f1_score"],
        auc=metrics["auc"],
        n_muestras_entrenamiento=len(X_train),
        n_muestras_prueba=len(X_test),
        features_json=json.dumps(NUMERIC_FEATURES + CATEGORICAL_FEATURES),
        importancia_json=json.dumps(importance),
        matriz_confusion_json=json.dumps(confusion),
        curva_roc_json=json.dumps(roc),
        hiperparametros_json=json.dumps({"test_size": test_size, "random_state": random_state}),
        # ruta relativa al directorio de modelos: el artefacto sigue siendo válido si el proyecto
        # se mueve de carpeta o se despliega en otro servidor (Render, etc.)
        ruta_artefacto=os.path.basename(artifact_path),
    )
    db.session.add(run)
    db.session.commit()
    return run


def train_all_and_activate_best() -> tuple[MLModelRun, list]:
    """Entrena todos los algoritmos registrados y deja activo el de mayor AUC en prueba."""
    runs = [train_and_evaluate(alg, activate=False) for alg in ALGORITHMS]
    best = max(runs, key=lambda r: r.auc or 0)
    db.session.query(MLModelRun).update({MLModelRun.activo: False})
    best.activo = True
    db.session.commit()
    return best, runs


def train_regression(target: str, test_size: float = 0.2, random_state: int = 42) -> dict:
    """Entrena un regresor auxiliar (Lead Time o Costo) para el Simulador. No usa el modelo de
    riesgo OTIF ni comparte artefacto con él: se guarda por separado como regressor_<target>.joblib."""
    if target not in REGRESSION_TARGETS:
        raise ValueError(f"Objetivo de regresión no soportado: {target}")
    cfg = REGRESSION_TARGETS[target]

    df = load_training_dataframe()
    X, y = split_regression_target(df, target)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)

    eval_pipeline = build_regression_pipeline(cfg["numeric"], cfg["categorical"])
    eval_pipeline.fit(X_train, y_train)
    y_pred = np.clip(eval_pipeline.predict(X_test), 0, None)

    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))

    production_pipeline = build_regression_pipeline(cfg["numeric"], cfg["categorical"])
    production_pipeline.fit(X, y)

    os.makedirs(MODELS_DIR, exist_ok=True)
    artifact_path = os.path.join(MODELS_DIR, f"regressor_{target}.joblib")
    joblib.dump(production_pipeline, artifact_path)

    result = {"target": target, "label": cfg["label"], "mae": round(mae, 3), "r2": round(r2, 3),
              "n_train": len(X_train), "n_test": len(X_test), "path": artifact_path}
    _save_regressor_metrics(target, result)
    return result


def _save_regressor_metrics(target: str, result: dict) -> None:
    """Persiste las métricas de prueba de los regresores (las muestra el módulo Lead Time)."""
    path = os.path.join(MODELS_DIR, "regressors_metrics.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    data[target] = {k: result[k] for k in ("label", "mae", "r2", "n_train", "n_test")}
    data[target]["algoritmo"] = "HistGradientBoostingRegressor"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
