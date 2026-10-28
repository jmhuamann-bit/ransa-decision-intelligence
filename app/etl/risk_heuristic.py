"""
Heuristica de riesgo pre-modelo, usada por el ETL para poblar prob_riesgo_incumplimiento/nivel_riesgo
en la carga inicial de datos historicos, ANTES de entrenar el modelo de Machine Learning real
(ver app/ml). Una vez entrenado el modelo de Predicciones IA, sus predicciones reemplazan estos
valores heuristicos (script scripts/train_model.py).

No usa variables posteriores al hecho (OTIF, Fill_Rate, Nivel_Servicio, Siniestro) para no filtrar
la variable objetivo: solo variables conocidas ANTES o DURANTE el viaje.
"""
import pandas as pd

ALERTA_SENAMHI_PUNTOS = {"Ninguna": 0, "Amarilla": 15, "Naranja": 30, "Roja": 50}


def calcular_riesgo_heuristico(df: pd.DataFrame) -> pd.DataFrame:
    componentes = pd.DataFrame(index=df.index)
    componentes["bloqueos"] = df["indice_bloqueos"].fillna(0)
    componentes["protestas"] = df["indice_protestas"].fillna(0)
    componentes["inundaciones"] = df["indice_inundaciones"].fillna(0)
    componentes["deslizamientos"] = df["indice_deslizamientos"].fillna(0)
    componentes["derrumbes"] = df["indice_derrumbes"].fillna(0)
    componentes["incendios"] = df["indice_incendios"].fillna(0)
    componentes["inseguridad"] = 100 - df["indice_seguridad"].fillna(100)
    componentes["desorden_publico"] = 100 - df["indice_orden_publico"].fillna(100)
    componentes["deterioro_vial"] = df["indice_deterioro_vial"].fillna(0)

    score = componentes.mean(axis=1)

    score += df["alerta_senamhi"].map(ALERTA_SENAMHI_PUNTOS).fillna(0)
    score += df["huelgas"].fillna(0) * 8
    score += df["presencia_crimen_organizado"].fillna(0) * 10
    score += (df["numero_paros"].fillna(0) > 0).astype(int) * 5

    score = score.clip(lower=0, upper=100)

    nivel = pd.cut(
        score,
        bins=[-1, 25, 50, 75, 101],
        labels=["Bajo", "Medio", "Alto", "Critico"],
    )

    return pd.DataFrame({
        "prob_riesgo_incumplimiento": score.round(1),
        "nivel_riesgo": nivel.astype(str),
        "alerta_critica": score >= 80,
    })
