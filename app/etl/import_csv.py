"""Lectura y tipado de archivos fuente (CSV/Excel) hacia un DataFrame normalizado con nombres de columna
internos (snake_case, sin tildes), listos para validar y cargar a la base de datos."""
import pandas as pd

from app.models.field_metadata import FIELDS

VARIABLE_TO_COLUMN = {f["variable"]: f["column"] for f in FIELDS}
COLUMN_TO_SQLTYPE = {f["column"]: f["sql_type"] for f in FIELDS}

BINARY_COLUMNS = [f["column"] for f in FIELDS if f["tipo_dato"] == "Binaria"]
FLOAT_COLUMNS = [f["column"] for f in FIELDS if f["sql_type"] == "Float"]
INT_COLUMNS = [f["column"] for f in FIELDS if f["sql_type"] == "Integer" and f["tipo_dato"] != "Binaria"]
STRING_COLUMNS = [f["column"] for f in FIELDS if f["sql_type"] == "String" and f["column"] != "id_viaje"]


def read_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df = df.rename(columns=VARIABLE_TO_COLUMN)
    return _cast_types(df)


def read_excel(path: str, sheet_name=0) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name)
    df = df.rename(columns=VARIABLE_TO_COLUMN)
    return _cast_types(df)


def _cast_types(df: pd.DataFrame) -> pd.DataFrame:
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce").dt.date

    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in INT_COLUMNS + BINARY_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in STRING_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace({"nan": None, "None": None})

    return df
