"""Capa de acceso a datos para el Centro de Monitoreo: filtros, paginacion y semaforo de riesgo."""
from app.extensions import db
from app.models.shipment import Shipment

FILTERABLE_FIELDS = {
    "sector_cliente": Shipment.sector_cliente,
    "departamento_origen": Shipment.departamento_origen,
    "ciudad_origen": Shipment.ciudad_origen,
    "departamento_destino": Shipment.departamento_destino,
    "ciudad_destino": Shipment.ciudad_destino,
    "corredor_logistico": Shipment.corredor_logistico,
    "tipo_transporte": Shipment.tipo_transporte,
    "tipo_vehiculo": Shipment.tipo_vehiculo,
    "prioridad_cliente": Shipment.prioridad_cliente,
    "nivel_riesgo": Shipment.nivel_riesgo,
    "otif": Shipment.otif,
    "ano": Shipment.ano,
}

SEMAFORO_MAP = {"Bajo": "verde", "Medio": "amarillo", "Alto": "rojo", "Critico": "rojo"}


def search_shipments(filtros: dict, page: int = 1, page_size: int = 25, sort_by: str = "fecha",
                      sort_dir: str = "desc") -> dict:
    q = Shipment.query

    for key, column in FILTERABLE_FIELDS.items():
        value = filtros.get(key)
        if value not in (None, "", "todos"):
            q = q.filter(column == value)

    if filtros.get("busqueda"):
        term = f"%{filtros['busqueda'].strip()}%"
        q = q.filter(Shipment.id_viaje.ilike(term))

    if filtros.get("fecha_desde"):
        q = q.filter(Shipment.fecha >= filtros["fecha_desde"])
    if filtros.get("fecha_hasta"):
        q = q.filter(Shipment.fecha <= filtros["fecha_hasta"])

    sort_column = getattr(Shipment, sort_by, Shipment.fecha)
    q = q.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())

    total = q.count()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for s in items:
        results.append({
            "id": s.id,
            "id_viaje": s.id_viaje,
            "fecha": s.fecha.isoformat() if s.fecha else None,
            "sector_cliente": s.sector_cliente,
            "departamento_origen": s.departamento_origen,
            "ciudad_origen": s.ciudad_origen,
            "departamento_destino": s.departamento_destino,
            "ciudad_destino": s.ciudad_destino,
            "corredor_logistico": s.corredor_logistico,
            "ruta_principal": s.ruta_principal,
            "tipo_transporte": s.tipo_transporte,
            "tipo_vehiculo": s.tipo_vehiculo,
            "prioridad_cliente": s.prioridad_cliente,
            "tiempo_programado_horas": s.tiempo_programado_horas,
            "tiempo_entrega_real_horas": s.tiempo_entrega_real_horas,
            "leadtime_real_dias": s.leadtime_real_dias,
            "otif": bool(s.otif),
            "costo_total_pen": (s.costo_transporte_pen or 0) + (s.costo_peajes_pen or 0),
            "prob_riesgo_incumplimiento": s.prob_riesgo_incumplimiento,
            "nivel_riesgo": s.nivel_riesgo,
            "semaforo": SEMAFORO_MAP.get(s.nivel_riesgo, "verde"),
            "alerta_critica": bool(s.alerta_critica),
        })

    return {
        "items": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_filter_options() -> dict:
    options = {}
    for key, column in FILTERABLE_FIELDS.items():
        if key in ("otif",):
            continue
        values = [row[0] for row in db.session.query(column).distinct().order_by(column).limit(300).all() if row[0] is not None]
        options[key] = values
    return options


def get_shipment_detail(id_viaje: str) -> Shipment | None:
    return Shipment.query.filter_by(id_viaje=id_viaje).first()
