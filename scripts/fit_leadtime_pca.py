"""
Modelo estadístico de Lead Time: ACP (PCA) + Regresión Lineal Múltiple — RANSA Perú.

Metodología (la misma del prototipo anterior de la plataforma, aplicada al dataset peruano):
  1. Se toman todas las variables numéricas del dataset (excepto el ID y la variable objetivo) y se
     descartan las que tienen más de 60 % de faltantes (variables exclusivas de un modo, como las
     de vuelos o buques); el resto se imputa por mediana y se estandariza.
  2. Se diagnostica la multicolinealidad (VIF) — justifica reducir dimensiones con ACP.
  3. ACP con 5 componentes; cada factor se NOMBRA AUTOMÁTICAMENTE según el tema que domina sus
     cargas factoriales (operación y costos, clima y riesgo natural, conflictividad y seguridad,
     macroeconomía, demanda y servicio...). El signo de cada componente se orienta para que su
     variable dominante cargue en positivo.
  4. Regresión lineal múltiple del Lead Time sobre los 5 factores + validación holdout 80/20
     (R², RMSE, MAE, MAPE) y VIF de los factores (≈ 1, por ortogonalidad).

Ejecutar:  python scripts/fit_leadtime_pca.py
Genera:    data/models/leadtime_pca_results.json  (lo consume el módulo "Modelo Lead Time")
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, "data", "RANSA_Peru_Dataset_Simulado.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "models", "leadtime_pca_results.json")

DEPENDIENTE = "LeadTime_Real_Dias"
# Variables que son el mismo resultado expresado de otra forma (incluirlas sería circular)
EXCLUIR = ("ID_Viaje", DEPENDIENTE, "Tiempo_Entrega_Real_Horas")
N_COMPONENTES = 5
MAX_FALTANTES = 0.60
# Se evaluó modelar log(1 + días) por la asimetría del Lead Time peruano (horas en distribución
# urbana, días en cabotaje y fluvial), pero al volver a días el ajuste empeora: se modela en días.
TRANSFORMACION = None

TEMAS = [
    ("Geografía andina: altitud, temperatura y jornada de conducción", "Factor_Geografia_Altitud",
     ("Altitud", "Horas_Conducción", "Temperatura")),
    ("Magnitud y costo de la operación", "Factor_Operacion_Costos",
     ("Peso", "Volumen", "Distancia", "Tiempo_Programado", "Costo", "Consumo", "Valor_Asegurado", "Prima", "Deducible",
      "Velocidad_Promedio", "Altitud", "Peajes", "Tiempo_Espera", "Valor_Siniestro")),
    ("Clima y riesgo natural (lluvias, huaicos, inundaciones)", "Factor_Clima_Riesgo_Natural",
     ("Precipitación", "Inundaciones", "Deslizamientos", "Derrumbes", "Humedad", "Viento", "Incendios",
      "Cierres", "Deterioro")),
    ("Conflictividad social, bloqueos y seguridad", "Factor_Conflictividad_Seguridad",
     ("Paros", "Protestas", "Manifestaciones", "Huelgas", "Bloqueos", "Seguridad", "Orden_Público", "Crimen",
      "Eventos_Seguridad", "Tiempo_Cierre", "Duración_Incidente")),
    ("Entorno macroeconómico (IPC, inflación, combustibles, tipo de cambio)", "Factor_Macroeconomico",
     ("IPC", "Inflación", "Precio_Diésel", "Precio_Gasolina", "Tipo_Cambio", "Año", "Precio_Peajes")),
    ("Demanda, capacidad y nivel de servicio", "Factor_Demanda_Servicio",
     ("Demanda", "Inventario", "Abastecimiento", "Utilización", "Disponibilidad", "Fill_Rate", "Nivel_Servicio",
      "OTIF", "Almacén", "Almacenamiento", "Cross_Docking", "Obras", "Restricciones")),
]


def vif(matriz: np.ndarray) -> list:
    """Factor de inflación de la varianza de cada columna: 1/(1-R²) al regresarla contra el resto."""
    valores = []
    for i in range(matriz.shape[1]):
        otras = np.delete(matriz, i, axis=1)
        r2 = LinearRegression().fit(otras, matriz[:, i]).score(otras, matriz[:, i])
        valores.append(float("inf") if r2 >= 1 else 1 / (1 - r2))
    return valores


def tema_de(variable: str) -> int | None:
    for i, (_, _, claves) in enumerate(TEMAS):
        if any(k.lower() in variable.lower() for k in claves):
            return i
    return None


def nombrar_componentes(cargas_por_comp: list) -> list:
    """Asigna a cada componente el tema con mayor suma de |carga| entre sus 12 variables dominantes,
    sin repetir nombre (si dos componentes comparten tema, el segundo recibe su 2.º tema)."""
    usados, nombres = set(), []
    for cargas in cargas_por_comp:
        puntajes = {}
        for var, c in sorted(cargas, key=lambda t: -abs(t[1]))[:12]:
            t = tema_de(var)
            if t is not None:
                puntajes[t] = puntajes.get(t, 0) + abs(c)
        orden = sorted(puntajes, key=lambda t: -puntajes[t]) or [0]
        elegido = next((t for t in orden if t not in usados), orden[0])
        usados.add(elegido)
        nombres.append(elegido)
    return nombres


def main() -> None:
    if not os.path.exists(CSV_PATH):
        sys.exit(f"No se encontró el dataset: {CSV_PATH}")

    print(f"Leyendo {os.path.basename(CSV_PATH)}...")
    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"  {df.shape[0]:,} observaciones × {df.shape[1]} variables")

    numericas = df.select_dtypes(include=[np.number]).columns.tolist()
    candidatas = [c for c in numericas if c not in EXCLUIR]
    excluidas = [c for c in candidatas if df[c].isna().mean() > MAX_FALTANTES]
    variables_acp = [c for c in candidatas if c not in excluidas]
    print(f"  {len(numericas)} numéricas → {len(variables_acp)} entran al ACP ({len(excluidas)} excluidas por faltantes)")

    X = df[variables_acp]
    faltantes = X.isna().sum()
    faltantes = faltantes[faltantes > 0]
    imputadas = [{"variable": v, "faltantes": int(n), "pct": round(n / len(X) * 100, 2)} for v, n in faltantes.items()]
    X = X.fillna(X.median(numeric_only=True))
    y_dias = df[DEPENDIENTE].values
    y = np.log1p(y_dias) if TRANSFORMACION == "log1p" else y_dias

    Z = StandardScaler().fit_transform(X)

    print(f"Calculando VIF de las {len(variables_acp)} variables originales (justifica el ACP)...")
    vif_orig = vif(Z)
    top_vif = sorted(zip(variables_acp, vif_orig), key=lambda t: -t[1])[:10]

    pca_full = PCA().fit(Z)
    kaiser_real = int((pca_full.explained_variance_ >= 1).sum())

    pca = PCA(n_components=N_COMPONENTES).fit(Z)
    scores = pca.transform(Z)

    cargas_por_comp, signos = [], []
    for i in range(N_COMPONENTES):
        cargas = pca.components_[i] * np.sqrt(pca.explained_variance_[i])
        dom = int(np.argmax(np.abs(cargas)))
        s = -1.0 if cargas[dom] < 0 else 1.0
        signos.append(s)
        cargas_por_comp.append(list(zip(variables_acp, cargas * s)))
    scores = scores * np.array(signos)
    temas = nombrar_componentes(cargas_por_comp)
    nombres = [TEMAS[t][1] for t in temas]
    etiquetas = [TEMAS[t][0] for t in temas]
    # nombres únicos aunque dos componentes compartan tema
    vistos = {}
    for i, n in enumerate(nombres):
        vistos[n] = vistos.get(n, 0) + 1
        if vistos[n] > 1:
            nombres[i] = f"{n}_{vistos[n]}"

    componentes_info = []
    for i in range(N_COMPONENTES):
        dominantes = sorted(cargas_por_comp[i], key=lambda t: -abs(t[1]))[:10]
        componentes_info.append({
            "n": i + 1,
            "nombre_publicado": nombres[i],
            "etiqueta_real": etiquetas[i],
            "autovalor": round(float(pca.explained_variance_[i]), 6),
            "pct_varianza": round(float(pca.explained_variance_ratio_[i] * 100), 6),
            "variables_dominantes": [{"variable": v, "carga": round(float(c), 4)} for v, c in dominantes],
        })
    varianza_acumulada = round(float(pca.explained_variance_ratio_.sum() * 100), 4)
    vif_factores = [round(v, 4) for v in vif(scores)]

    modelo_full = LinearRegression().fit(scores, y)
    r2_full = float(modelo_full.score(scores, y))
    n, k = len(y), N_COMPONENTES
    r2_ajustado = 1 - (1 - r2_full) * (n - 1) / (n - k - 1)
    residuos = y - modelo_full.predict(scores)
    rse = float(np.sqrt((residuos ** 2).sum() / (n - k - 1)))

    s_tr, s_te, y_tr, y_te = train_test_split(scores, y, test_size=0.2, random_state=42)
    modelo_cv = LinearRegression().fit(s_tr, y_tr)
    pred_log = modelo_cv.predict(s_te)
    # métricas de error en DÍAS (escala original), tras invertir la transformación
    if TRANSFORMACION == "log1p":
        y_te_d, pred = np.expm1(y_te), np.clip(np.expm1(pred_log), 0, None)
    else:
        y_te_d, pred = y_te, pred_log
    rmse = float(np.sqrt(mean_squared_error(y_te_d, pred)))
    mae = float(mean_absolute_error(y_te_d, pred))
    mask = np.abs(y_te_d) > 0.05
    mape = float(np.mean(np.abs((y_te_d[mask] - pred[mask]) / y_te_d[mask])) * 100)
    r2_test_dias = float(1 - ((y_te_d - pred) ** 2).sum() / ((y_te_d - y_te_d.mean()) ** 2).sum())

    resultados = {
        "dataset": {
            "archivo": os.path.basename(CSV_PATH),
            "observaciones": int(df.shape[0]),
            "variables_totales": int(df.shape[1]),
            "variables_numericas": len(numericas),
            "variables_acp": len(variables_acp),
            "excluidas_por_faltantes": excluidas,
            "imputadas_por_mediana": imputadas,
        },
        "multicolinealidad": {
            "vif_originales_sobre_10": int(sum(1 for v in vif_orig if v > 10)),
            "vif_originales_sobre_5": int(sum(1 for v in vif_orig if v > 5)),
            "total_variables": len(variables_acp),
            "top_vif_originales": [{"variable": v, "vif": round(x, 1) if np.isfinite(x) else 9999.0} for v, x in top_vif],
            "vif_factores": vif_factores,
        },
        "acp": {
            "n_componentes": N_COMPONENTES,
            "varianza_acumulada_pct": varianza_acumulada,
            "kaiser_real": kaiser_real,
            "componentes": componentes_info,
        },
        "regresion": {
            "intercepto": round(float(modelo_full.intercept_), 8),
            "coeficientes": [
                {"factor": nombres[i], "etiqueta_real": etiquetas[i], "coef": round(float(modelo_full.coef_[i]), 8)}
                for i in range(N_COMPONENTES)
            ],
            "r2": round(r2_full, 4),
            "r2_ajustado": round(float(r2_ajustado), 4),
            "error_estandar_residual": round(rse, 4),
        },
        "validacion": {
            "metodo": "Holdout 80/20 (random_state=42)",
            "r2_test": round(float(modelo_cv.score(s_te, y_te)), 4),
            "r2_test_dias": round(r2_test_dias, 4),
            "rmse_dias": round(rmse, 4),
            "mae_dias": round(mae, 4),
            "mape_pct": round(mape, 2),
            "n_test": int(len(y_te)),
            "n_mape": int(mask.sum()),
        },
        "objetivo": {
            "variable": DEPENDIENTE,
            "transformacion": TRANSFORMACION,
            "media": round(float(y_dias.mean()), 4),
            "media_log": round(float(y.mean()), 4),
            "min": round(float(y_dias.min()), 4),
            "max": round(float(y_dias.max()), 4),
        },
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)

    print()
    for c in componentes_info:
        print(f"  CP{c['n']} {c['nombre_publicado']:<36} {c['pct_varianza']:.2f}% var · "
              + ", ".join(v["variable"] for v in c["variables_dominantes"][:4]))
    print(f"  R² = {r2_full:.4f} · R² test = {resultados['validacion']['r2_test']} · R² test (días) = {r2_test_dias:.4f}")
    print(f"  RMSE = {rmse:.4f} d · MAE = {mae:.4f} d · MAPE = {mape:.2f}%")
    print(f"  VIF originales > 10: {resultados['multicolinealidad']['vif_originales_sobre_10']}/{len(variables_acp)} → VIF factores: {vif_factores}")
    print(f"\nResultados escritos en {OUT_PATH}")


if __name__ == "__main__":
    main()
