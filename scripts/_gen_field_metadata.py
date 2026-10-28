"""
Generador: lee el diccionario de datos RANSA Perú (data/RANSA_Peru_Diccionario_Datos.csv) y emite
app/models/field_metadata.py (estático, versionado, legible). Solo las variables marcadas
En_Modelo = "Sí" se convierten en columnas de la base de datos; las complementarias
multimodales (vuelo, naviera, nivel del río...) quedan solo en el CSV.

Ejecutar cada vez que cambie el diccionario:  python scripts/_gen_field_metadata.py
"""
import csv
import os
import re
import unicodedata

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_PATH = os.path.join(BASE_DIR, "data", "RANSA_Peru_Diccionario_Datos.csv")
OUT_PATH = os.path.join(BASE_DIR, "app", "models", "field_metadata.py")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def to_column_name(variable: str) -> str:
    ascii_name = strip_accents(variable)
    ascii_name = re.sub(r"[^0-9a-zA-Z_]", "_", ascii_name)
    ascii_name = re.sub(r"_+", "_", ascii_name).strip("_")
    return ascii_name.lower()


def infer_sql_type(tipo_dato: str) -> str:
    tipo = strip_accents(tipo_dato).lower()
    if "identificador" in tipo:
        return "String"
    if "fecha" in tipo:
        return "Date"
    if "binaria" in tipo or "discreta" in tipo or "discreto" in tipo:
        return "Integer"
    if "continua" in tipo:
        return "Float"
    return "String"


GROUPS = [
    ("identificacion_temporal", ("id_viaje", "fecha", "dia_semana", "mes", "trimestre", "ano")),
    ("geografia", ("departamento", "ciudad", "corredor", "ruta", "altitud")),
    ("operacion_carga", ("tipo_transporte", "tipo_vehiculo", "tipo_carga", "sector_cliente", "peso", "volumen")),
    ("tiempos_transito", ("distancia", "tiempo_programado", "tiempo_entrega", "velocidad_promedio", "tiempo_espera", "consumo")),
    ("economico_financiero", ("costo", "precio", "ipc", "tipo_cambio", "inflacion", "prima", "deducible", "valor_")),
    ("flota", ("disponibilidad_flota", "utilizacion_flota")),
    ("infraestructura_vial", ("estado_via", "indice_deterioro", "numero_cierres", "numero_bloqueos", "indice_bloqueos",
                              "obras_viales", "restricciones")),
    ("seguridad", ("indice_seguridad", "riesgo_hurto", "numero_eventos_seguridad", "presencia_crimen", "indice_orden",
                   "riesgo_extorsion", "riesgo_vandalismo", "riesgo_saqueo")),
    ("orden_social", ("numero_paros", "indice_protestas", "manifestaciones", "huelgas", "bloqueos_sociales")),
    ("clima", ("temperatura", "precipitacion", "humedad", "velocidad_viento", "alerta_senamhi", "fenomeno")),
    ("riesgo_natural", ("numero_inundaciones", "indice_inundaciones", "numero_deslizamientos", "indice_deslizamientos",
                        "numero_derrumbes", "indice_derrumbes", "numero_incendios", "indice_incendios",
                        "riesgo_geologico", "riesgo_hidrologico")),
    ("incidentes", ("numero_accidentes", "intensidad_incidente", "duracion_incidente", "tiempo_cierre")),
    ("demanda_inventario", ("indice_abastecimiento", "nivel_inventario", "demanda")),
    ("servicio_cliente", ("prioridad_cliente", "otif", "fill_rate", "nivel_servicio")),
    ("almacenamiento", ("tiempo_almacenamiento", "cross_docking", "tipo_almacen", "capacidad_almacen", "utilizacion_almacen")),
    ("seguros", ("aseguradora", "tipo_cobertura", "siniestro", "estado_reclamacion")),
    ("objetivo", ("leadtime_real_dias",)),
]


def infer_group(column: str) -> str:
    for group, prefixes in GROUPS:
        if column.startswith(prefixes):
            return group
    return "otro"


rows = []
with open(DICT_PATH, newline="", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        variable = r["Variable"].strip()
        if not variable or r.get("En_Modelo", "Sí").strip() != "Sí":
            continue
        column = to_column_name(variable)
        rows.append({
            "variable": variable,
            "column": column,
            "tipo_dato": r["Tipo_de_Dato"].strip(),
            "sql_type": infer_sql_type(r["Tipo_de_Dato"]),
            "unidad": r["Unidad_de_Medida"].strip(),
            "fuente": r["Fuente_Publica_de_Referencia"].strip(),
            "descripcion": r["Descripcion"].strip(),
            "grupo": infer_group(column),
        })

lines = [
    '"""',
    "Metadatos del diccionario de datos RANSA Perú (generado automáticamente).",
    "Fuente: data/RANSA_Peru_Diccionario_Datos.csv",
    "NO editar a mano: regenerar con scripts/_gen_field_metadata.py",
    '"""',
    "",
    "FIELDS = [",
]
for r in rows:
    lines.append("    {")
    for key in ("variable", "column", "tipo_dato", "sql_type", "unidad", "fuente", "descripcion", "grupo"):
        val = r[key].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'        "{key}": "{val}",')
    lines.append("    },")
lines += [
    "]",
    "",
    "FIELDS_BY_COLUMN = {f['column']: f for f in FIELDS}",
    "FIELDS_BY_VARIABLE = {f['variable']: f for f in FIELDS}",
    "",
]

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"OK: {len(rows)} campos escritos en {OUT_PATH}")
