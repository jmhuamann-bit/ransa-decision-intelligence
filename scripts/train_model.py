"""
Entrena los modelos de Predicciones IA sobre los embarques, deja activo el de mayor AUC, aplica
sus probabilidades a cada embarque y regenera las Alertas Críticas automáticas.

Uso:
    python scripts/train_model.py            # entrena todos los algoritmos y activa el mejor
    python scripts/train_model.py gradient_boosting   # solo uno
"""
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.ml.training.trainer import (
    ALGORITHM_LABELS, REGRESSION_TARGETS, train_all_and_activate_best, train_and_evaluate, train_regression,
)
from app.services.alert_service import regenerate_ai_alerts
from app.services.prediction_service import apply_predictions_to_all_shipments


def main():
    algorithm = sys.argv[1] if len(sys.argv) > 1 else None

    app = create_app(start_live_engine=False)
    with app.app_context():
        db.create_all()
        t0 = time.time()
        if algorithm:
            print(f"Entrenando modelo: {ALGORITHM_LABELS.get(algorithm, algorithm)} ...")
            run = train_and_evaluate(algorithm)
            runs = [run]
        else:
            print("Entrenando todos los algoritmos y activando el de mayor AUC ...")
            run, runs = train_all_and_activate_best()
        for r in runs:
            print(f"  {ALGORITHM_LABELS.get(r.algoritmo, r.algoritmo):<28} AUC={r.auc}  Accuracy={r.accuracy}  "
                  f"Recall={r.recall}  Precision={r.precision_}  F1={r.f1_score}")
        print(f"  ➜ Activo: {ALGORITHM_LABELS.get(run.algoritmo, run.algoritmo)} (versión {run.version}) · {time.time() - t0:.1f}s")

        print("Aplicando predicciones a todos los embarques...")
        t1 = time.time()
        n = apply_predictions_to_all_shipments()
        print(f"  {n} embarques actualizados en {time.time() - t1:.1f}s")

        print("Regenerando Alertas Críticas...")
        n_alerts = regenerate_ai_alerts()
        print(f"  {n_alerts} alertas críticas generadas (probabilidad >= {app.config['RISK_ALERT_THRESHOLD_PCT']}%)")

        print("Entrenando regresores auxiliares del Simulador (Lead Time y Costo)...")
        for target in REGRESSION_TARGETS:
            t2 = time.time()
            result = train_regression(target)
            print(f"  {result['label']}: MAE={result['mae']}  R2={result['r2']}  ({time.time() - t2:.1f}s)")

        print(f"Listo. Tiempo total: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
