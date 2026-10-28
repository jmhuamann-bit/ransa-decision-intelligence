"""CRUD de embarques individuales. Al crear/editar, aplica de inmediato el modelo de IA activo
(si existe) para que el nuevo embarque ya tenga probabilidad de riesgo, sin esperar al proximo
reentrenamiento masivo."""
from datetime import date, datetime

from app.extensions import db
from app.ml.prediction import predictor
from app.models.shipment import Shipment
from app.services import simulator_service

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

EDITABLE_FIELDS = [
    "fecha", "departamento_origen", "ciudad_origen", "departamento_destino", "ciudad_destino",
    "ruta_principal", "tipo_transporte", "tipo_vehiculo", "tipo_carga", "sector_cliente",
    "peso_toneladas", "volumen_m3", "distancia_km", "tiempo_programado_horas",
    "costo_transporte_pen", "costo_peajes_pen", "prioridad_cliente",
    "disponibilidad_flota_pct", "utilizacion_flota_pct",
]

REQUIRED_FIELDS = [
    "fecha", "departamento_origen", "ciudad_origen", "departamento_destino", "ciudad_destino",
    "tipo_transporte", "tipo_carga", "sector_cliente", "peso_toneladas", "volumen_m3",
    "distancia_km", "tiempo_programado_horas", "prioridad_cliente",
]


def _next_id_viaje() -> str:
    year = datetime.now().year
    prefix = f"RNS-{year}-"
    last = (
        Shipment.query.filter(Shipment.id_viaje.like(f"{prefix}%"))
        .order_by(Shipment.id_viaje.desc())
        .first()
    )
    next_n = 1
    if last:
        try:
            next_n = int(last.id_viaje.split("-")[-1]) + 1
        except (ValueError, IndexError):
            next_n = 1
    return f"{prefix}{next_n:06d}"


def validate(data: dict) -> list:
    errors = []
    for field in REQUIRED_FIELDS:
        if data.get(field) in (None, ""):
            errors.append(f"El campo '{field}' es obligatorio.")
    for field in ("peso_toneladas", "volumen_m3", "distancia_km", "tiempo_programado_horas"):
        value = data.get(field)
        if value not in (None, "") and float(value) < 0:
            errors.append(f"'{field}' no puede ser negativo.")
    return errors


def _apply_derived_fields(shipment: Shipment, data: dict) -> None:
    for field in EDITABLE_FIELDS:
        if field in data and data[field] not in (None, ""):
            value = data[field]
            if field == "fecha" and isinstance(value, str):
                value = date.fromisoformat(value)
            setattr(shipment, field, value)

    if shipment.fecha:
        shipment.dia_semana = DIAS_SEMANA[shipment.fecha.weekday()]
        shipment.mes = MESES[shipment.fecha.month - 1]
        shipment.trimestre = str((shipment.fecha.month - 1) // 3 + 1)
        shipment.ano = shipment.fecha.year

    if shipment.ciudad_origen and shipment.ciudad_destino:
        shipment.corredor_logistico = f"{shipment.ciudad_origen} - {shipment.ciudad_destino}"


def _apply_ai_scoring(shipment: Shipment) -> None:
    """Reutiliza el mismo mecanismo del Simulador: completa las variables no capturadas en el
    formulario con valores tipicos y consulta el modelo de IA activo, si existe."""
    scenario = dict(simulator_service.get_global_defaults())
    for field in EDITABLE_FIELDS:
        value = getattr(shipment, field, None)
        if value is not None:
            scenario[field] = value

    prob = predictor.predict_single(scenario)
    if prob is not None:
        shipment.prob_riesgo_incumplimiento = prob
        shipment.nivel_riesgo = predictor.bucket_risk(prob)
        from flask import current_app
        shipment.alerta_critica = prob >= current_app.config["RISK_ALERT_THRESHOLD_PCT"]


def create_shipment(data: dict) -> Shipment:
    shipment = Shipment(id_viaje=data.get("id_viaje") or _next_id_viaje())
    _apply_derived_fields(shipment, data)
    _apply_ai_scoring(shipment)
    db.session.add(shipment)
    db.session.commit()
    return shipment


def update_shipment(shipment_id: int, data: dict) -> Shipment | None:
    shipment = Shipment.query.get(shipment_id)
    if not shipment:
        return None
    _apply_derived_fields(shipment, data)
    _apply_ai_scoring(shipment)
    db.session.commit()
    return shipment


def delete_shipment(shipment_id: int) -> bool:
    shipment = Shipment.query.get(shipment_id)
    if not shipment:
        return False
    db.session.delete(shipment)
    db.session.commit()
    return True
