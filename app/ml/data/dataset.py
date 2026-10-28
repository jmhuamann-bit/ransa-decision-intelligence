"""
Capa de datos del motor de Predicciones IA.

Define que variables del dataset se usan para predecir el INCUMPLIMIENTO de OTIF y arma el
DataFrame de entrenamiento a partir de la base de datos (dataset RANSA Perú).

Regla de diseno (evitar fuga de datos / data leakage): solo se incluyen variables conocibles
ANTES o AL MOMENTO DEL DESPACHO del viaje (condiciones de via, clima, seguridad, orden social,
economia, caracteristicas de la carga y del cliente). Se excluyen explicitamente variables que
solo se conocen DESPUES de completado el viaje -tiempo real de entrega, velocidad real, tiempo de
espera real, incidentes ocurridos en ESE viaje, fill rate, nivel de servicio, siniestros- porque
son resultado del viaje, no informacion disponible para anticiparlo. LeadTime_Real_Dias y OTIF
son, por definicion, el resultado que se quiere predecir.
"""
import pandas as pd

from app.extensions import db
from app.models.shipment import Shipment

TARGET_COLUMN = "otif"

NUMERIC_FEATURES = [
    "ano", "peso_toneladas", "volumen_m3", "distancia_km", "altitud_max_ruta_msnm", "tiempo_programado_horas",
    "costo_transporte_pen", "costo_peajes_pen", "disponibilidad_flota_pct", "utilizacion_flota_pct",
    "indice_deterioro_vial", "numero_cierres_viales", "numero_bloqueos_carretera", "indice_bloqueos",
    "obras_viales_activas", "restricciones_peso", "restricciones_horarias",
    "indice_seguridad", "numero_eventos_seguridad", "presencia_crimen_organizado", "indice_orden_publico",
    "numero_paros", "indice_protestas", "manifestaciones", "huelgas", "bloqueos_sociales",
    "temperatura_c", "precipitacion_mm", "humedad_pct", "velocidad_viento_kmh",
    "numero_inundaciones", "indice_inundaciones", "numero_deslizamientos", "indice_deslizamientos",
    "numero_derrumbes", "indice_derrumbes", "numero_incendios_forestales", "indice_incendios",
    "precio_diesel_pen_gal", "precio_gasolina_pen_gal", "ipc", "tipo_cambio_pen_usd", "inflacion_pct",
    "precio_peajes_promedio_pen", "indice_abastecimiento", "nivel_inventario_pct",
    "demanda_unidades", "demanda_pronosticada_unidades", "tiempo_almacenamiento_horas",
    "cross_docking", "capacidad_almacen_m3", "utilizacion_almacen_pct",
    "valor_asegurado_pen", "prima_seguro_pen", "deducible_pen",
]

CATEGORICAL_FEATURES = [
    "dia_semana", "mes", "departamento_origen", "departamento_destino", "corredor_logistico",
    "ruta_principal", "tipo_transporte", "tipo_vehiculo", "tipo_carga", "sector_cliente",
    "estado_via", "alerta_senamhi", "fenomeno_climatico", "riesgo_hurto_carga", "riesgo_extorsion",
    "riesgo_vandalismo", "riesgo_saqueo", "riesgo_geologico", "riesgo_hidrologico",
    "prioridad_cliente", "tipo_almacen", "aseguradora", "tipo_cobertura_seguro",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# El costo (flete + peajes) es una de las variables de entrada del clasificador de OTIF (se conoce
# al reservar el viaje), pero cuando el OBJETIVO a predecir es el costo mismo no puede figurar
# tambien como variable de entrada (seria circular). Este set reducido se usa solo para esa regresion.
COST_TARGET_COLUMNS = ("costo_transporte_pen", "costo_peajes_pen")
NUMERIC_FEATURES_FOR_COST = [f for f in NUMERIC_FEATURES if f not in COST_TARGET_COLUMNS]
ALL_FEATURES_FOR_COST = NUMERIC_FEATURES_FOR_COST + CATEGORICAL_FEATURES

# Variables descartadas deliberadamente por ser resultado del viaje (fuga de datos):
EXCLUDED_LEAKAGE_COLUMNS = [
    "tiempo_entrega_real_horas", "velocidad_promedio_kmh", "tiempo_espera_horas",
    "consumo_combustible_galones", "numero_accidentes", "intensidad_incidente",
    "duracion_incidente_horas", "tiempo_cierre_via_horas", "fill_rate_pct", "nivel_servicio_pct",
    "siniestro", "valor_siniestro_pen", "estado_reclamacion", "leadtime_real_dias", "otif",
]


def load_training_dataframe() -> pd.DataFrame:
    """Trae todos los embarques de la base de datos como DataFrame, con las columnas necesarias
    para entrenar el clasificador de OTIF y los regresores de Lead Time / Costo del Simulador."""
    columns = ALL_FEATURES + [TARGET_COLUMN, "leadtime_real_dias", "id", "id_viaje"]
    rows = db.session.query(Shipment).with_entities(
        *[getattr(Shipment, c) for c in columns]
    ).all()
    df = pd.DataFrame(rows, columns=columns)
    df["costo_total_pen"] = df["costo_transporte_pen"].fillna(0) + df["costo_peajes_pen"].fillna(0)
    return df


def split_features_target(df: pd.DataFrame):
    """Devuelve (X, y) donde y=1 significa INCUMPLIMIENTO de OTIF (la clase de riesgo a predecir)."""
    X = df[ALL_FEATURES].copy()
    y = (df[TARGET_COLUMN] == 0).astype(int)
    return X, y


def split_regression_target(df: pd.DataFrame, target: str):
    """target: 'leadtime_real_dias' o 'costo_total_pen'."""
    if target == "costo_total_pen":
        X = df[ALL_FEATURES_FOR_COST].copy()
    else:
        X = df[ALL_FEATURES].copy()
    y = df[target].copy()
    return X, y
