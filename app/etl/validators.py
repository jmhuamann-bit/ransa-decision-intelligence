"""Validacion, deduplicacion y deteccion de inconsistencias para la carga ETL."""
import pandas as pd


def validate_and_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report = {"filas_originales": len(df), "errores": []}

    antes = len(df)
    df = df.drop_duplicates(subset=["id_viaje"], keep="first")
    duplicados = antes - len(df)
    if duplicados:
        report["errores"].append(f"{duplicados} filas duplicadas por id_viaje eliminadas")

    antes = len(df)
    df = df.dropna(subset=["id_viaje", "fecha"])
    sin_clave = antes - len(df)
    if sin_clave:
        report["errores"].append(f"{sin_clave} filas sin id_viaje/fecha descartadas")

    inconsistentes = df["tiempo_entrega_real_horas"] < 0
    if inconsistentes.any():
        report["errores"].append(f"{int(inconsistentes.sum())} filas con tiempo de entrega negativo corregidas a 0")
        df.loc[inconsistentes, "tiempo_entrega_real_horas"] = 0

    for col in ("peso_toneladas", "volumen_m3", "distancia_km"):
        neg = df[col] < 0
        if neg.any():
            report["errores"].append(f"{int(neg.sum())} filas con {col} negativo corregidas a 0")
            df.loc[neg, col] = 0

    df["sector_cliente"] = df["sector_cliente"].astype(str).str.strip()
    df["departamento_origen"] = df["departamento_origen"].astype(str).str.strip()
    df["ciudad_origen"] = df["ciudad_origen"].astype(str).str.strip()

    report["filas_finales"] = len(df)
    return df, report
