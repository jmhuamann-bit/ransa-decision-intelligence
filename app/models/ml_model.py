from datetime import datetime, timezone

from app.extensions import db


class MLModelRun(db.Model):
    """Metadatos de cada entrenamiento de modelo (permite comparar algoritmos y versiones)."""
    __tablename__ = "ml_model_runs"

    id = db.Column(db.Integer, primary_key=True)
    algoritmo = db.Column(db.String(60), nullable=False)  # logistic_regression | random_forest | xgboost | ...
    version = db.Column(db.String(30), nullable=False)
    objetivo = db.Column(db.String(60), nullable=False, default="incumplimiento_otif")
    activo = db.Column(db.Boolean, default=False, index=True)  # modelo actualmente en produccion

    accuracy = db.Column(db.Float)
    precision_ = db.Column("precision", db.Float)
    recall = db.Column(db.Float)
    f1_score = db.Column(db.Float)
    auc = db.Column(db.Float)

    n_muestras_entrenamiento = db.Column(db.Integer)
    n_muestras_prueba = db.Column(db.Integer)
    features_json = db.Column(db.Text)  # lista de variables usadas
    importancia_json = db.Column(db.Text)  # importancia de variables
    matriz_confusion_json = db.Column(db.Text)
    curva_roc_json = db.Column(db.Text)
    hiperparametros_json = db.Column(db.Text)
    ruta_artefacto = db.Column(db.String(300))  # .joblib

    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        import json

        return {
            "id": self.id,
            "algoritmo": self.algoritmo,
            "version": self.version,
            "objetivo": self.objetivo,
            "activo": self.activo,
            "metrics": {
                "accuracy": self.accuracy,
                "precision": self.precision_,
                "recall": self.recall,
                "f1_score": self.f1_score,
                "auc": self.auc,
            },
            "n_muestras_entrenamiento": self.n_muestras_entrenamiento,
            "n_muestras_prueba": self.n_muestras_prueba,
            "features": json.loads(self.features_json) if self.features_json else [],
            "importancia_variables": json.loads(self.importancia_json) if self.importancia_json else [],
            "matriz_confusion": json.loads(self.matriz_confusion_json) if self.matriz_confusion_json else None,
            "curva_roc": json.loads(self.curva_roc_json) if self.curva_roc_json else None,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
        }
