"""Calculo de metricas, curva ROC, matriz de confusion e importancia de variables.
Separado del entrenamiento para poder reutilizarse con cualquier algoritmo (no solo Regresion Logistica)."""
import numpy as np
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score, roc_curve,
)


def compute_classification_metrics(y_true, y_pred, y_proba) -> dict:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1_score": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "auc": round(float(roc_auc_score(y_true, y_proba)), 4),
    }


def compute_confusion_matrix(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "verdaderos_negativos": int(tn), "falsos_positivos": int(fp),
        "falsos_negativos": int(fn), "verdaderos_positivos": int(tp),
        "etiquetas": {"0": "Cumple OTIF", "1": "Incumple OTIF"},
    }


def compute_roc_curve(y_true, y_proba, max_points: int = 60) -> dict:
    fpr, tpr, _ = roc_curve(y_true, y_proba)
    if len(fpr) > max_points:
        idx = np.linspace(0, len(fpr) - 1, max_points).astype(int)
        fpr, tpr = fpr[idx], tpr[idx]
    return {"fpr": [round(float(x), 4) for x in fpr], "tpr": [round(float(x), 4) for x in tpr]}


def compute_logreg_importance(pipeline, top_n: int = 15) -> list:
    """Importancia de variables para Regresion Logistica: valor absoluto del coeficiente estandarizado
    (las variables numericas ya estan escaladas y las categoricas son dummies 0/1, por lo que los
    coeficientes son comparables entre si)."""
    preprocessor = pipeline.named_steps["preprocessor"]
    classifier = pipeline.named_steps["classifier"]

    feature_names = preprocessor.get_feature_names_out()
    coefs = classifier.coef_[0]

    items = []
    for name, coef in zip(feature_names, coefs):
        clean_name = name.replace("num__", "").replace("cat__", "")
        items.append({
            "variable": clean_name,
            "coeficiente": round(float(coef), 4),
            "direccion": "aumenta_riesgo" if coef > 0 else "reduce_riesgo",
        })

    items.sort(key=lambda x: abs(x["coeficiente"]), reverse=True)
    return items[:top_n]
