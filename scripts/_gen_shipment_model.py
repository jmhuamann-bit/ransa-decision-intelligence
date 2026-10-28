"""
Generador: construye app/models/shipment.py a partir de field_metadata.FIELDS para que las
columnas del dataset RANSA Perú coincidan 1:1 con el esquema SQL, sin errores de transcripción.

Ejecutar cada vez que cambie field_metadata.py:  python scripts/_gen_shipment_model.py
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.models.field_metadata import FIELDS  # noqa: E402

OUT_PATH = os.path.join(BACKEND_DIR, "app", "models", "shipment.py")

TYPE_MAP = {
    "String": "db.String(255)",
    "Date": "db.Date",
    "Integer": "db.Integer",
    "Float": "db.Float",
}

lines = []
lines.append('"""')
lines.append("Modelo Embarque (Viaje/Shipment) - generado automaticamente desde field_metadata.FIELDS")
lines.append(f"para garantizar correspondencia exacta con las {len(FIELDS)} columnas del dataset RANSA Perú.")
lines.append("NO editar a mano: regenerar con scripts/_gen_shipment_model.py")
lines.append('"""')
lines.append("from app.extensions import db")
lines.append("")
lines.append("")
lines.append("class Shipment(db.Model):")
lines.append('    """Un registro = un viaje/embarque (ID_Viaje) del dataset RANSA Perú."""')
lines.append('    __tablename__ = "shipments"')
lines.append("")
lines.append("    id = db.Column(db.Integer, primary_key=True)")

for f in FIELDS:
    col = f["column"]
    if col == "id_viaje":
        lines.append(f'    {col} = db.Column(db.String(30), unique=True, nullable=False, index=True)')
        continue
    sql_type = TYPE_MAP[f["sql_type"]]
    index = ""
    if col in (
        "fecha", "departamento_origen", "ciudad_origen", "departamento_destino",
        "ciudad_destino", "tipo_transporte", "prioridad_cliente", "otif", "estado_via",
        "sector_cliente", "corredor_logistico",
    ):
        index = ", index=True"
    lines.append(f'    {col} = db.Column({sql_type}{index})')

lines.append("")
lines.append("    # --- Riesgo calculado por el modulo de Predicciones IA (ver app/ml) ---")
lines.append("    prob_riesgo_incumplimiento = db.Column(db.Float)  # 0-100, probabilidad de NO cumplir OTIF")
lines.append("    nivel_riesgo = db.Column(db.String(20), index=True)  # Bajo / Medio / Alto / Critico")
lines.append("    alerta_critica = db.Column(db.Boolean, default=False, index=True)")
lines.append("")
lines.append("    COLUMNS = [")
for f in FIELDS:
    lines.append(f'        "{f["column"]}",')
lines.append("    ]")
lines.append("")
lines.append("    def to_dict(self) -> dict:")
lines.append("        data = {c: getattr(self, c) for c in self.COLUMNS}")
lines.append('        data["id"] = self.id')
lines.append('        if data.get("fecha") is not None:')
lines.append('            data["fecha"] = data["fecha"].isoformat()')
lines.append('        data["prob_riesgo_incumplimiento"] = self.prob_riesgo_incumplimiento')
lines.append('        data["nivel_riesgo"] = self.nivel_riesgo')
lines.append('        data["alerta_critica"] = self.alerta_critica')
lines.append("        return data")
lines.append("")

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))

print(f"OK: modelo Shipment con {len(FIELDS)} columnas escrito en {OUT_PATH}")
