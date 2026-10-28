"""Carga masiva de un DataFrame validado hacia la tabla shipments."""
import math

import pandas as pd

from app.extensions import db
from app.models.shipment import Shipment


def _clean_record(record: dict) -> dict:
    clean = {}
    for k, v in record.items():
        if v is None:
            clean[k] = None
        elif isinstance(v, float) and math.isnan(v):
            clean[k] = None
        elif hasattr(v, "item"):  # numpy/pandas scalar (Int64, etc.)
            try:
                clean[k] = v.item()
            except (ValueError, AttributeError):
                clean[k] = None if pd.isna(v) else v
        else:
            clean[k] = v
    return clean


def bulk_load(df: pd.DataFrame, batch_size: int = 1000) -> int:
    columns = [c for c in Shipment.COLUMNS if c in df.columns] + \
              ["prob_riesgo_incumplimiento", "nivel_riesgo", "alerta_critica"]
    records = df[columns].to_dict(orient="records")

    total = 0
    for i in range(0, len(records), batch_size):
        batch = [_clean_record(r) for r in records[i:i + batch_size]]
        db.session.bulk_insert_mappings(Shipment, batch)
        db.session.commit()
        total += len(batch)
    return total


def clear_shipments() -> None:
    db.session.query(Shipment).delete()
    db.session.commit()
