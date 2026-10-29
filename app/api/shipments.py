from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import monitoring_service, shipment_service
from app.services.auth_service import register_audit
from app.utils.decorators import disabled_in_public_demo, roles_required

bp = Blueprint("shipments", __name__, url_prefix="/api/shipments")

WRITE_ROLES = ("Operaciones", "Supervisor")


@bp.get("")
@login_required
def list_shipments():
    filtros = {k: request.args.get(k) for k in monitoring_service.FILTERABLE_FIELDS.keys()}
    filtros["busqueda"] = request.args.get("busqueda")
    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=20, type=int)
    result = monitoring_service.search_shipments(filtros, page, page_size, sort_by="fecha", sort_dir="desc")
    return jsonify(result)


@bp.get("/<int:shipment_id>")
@login_required
def get_shipment(shipment_id):
    from app.models.shipment import Shipment
    s = Shipment.query.get(shipment_id)
    if not s:
        return jsonify({"error": "Embarque no encontrado"}), 404
    return jsonify(s.to_dict())


@bp.post("")
@login_required
@roles_required(*WRITE_ROLES)
@disabled_in_public_demo
def create_shipment():
    data = request.get_json(silent=True) or {}
    errors = shipment_service.validate(data)
    if errors:
        return jsonify({"error": "Datos inválidos", "detalles": errors}), 400

    shipment = shipment_service.create_shipment(data)
    register_audit(current_user, "crear_embarque", entidad="Shipment", entidad_id=shipment.id_viaje,
                    detalle=f"Embarque creado: {shipment.corredor_logistico}")
    return jsonify(shipment.to_dict()), 201


@bp.put("/<int:shipment_id>")
@login_required
@roles_required(*WRITE_ROLES)
@disabled_in_public_demo
def update_shipment(shipment_id):
    data = request.get_json(silent=True) or {}
    errors = shipment_service.validate(data)
    if errors:
        return jsonify({"error": "Datos inválidos", "detalles": errors}), 400

    shipment = shipment_service.update_shipment(shipment_id, data)
    if not shipment:
        return jsonify({"error": "Embarque no encontrado"}), 404
    register_audit(current_user, "editar_embarque", entidad="Shipment", entidad_id=shipment.id_viaje)
    return jsonify(shipment.to_dict())


@bp.delete("/<int:shipment_id>")
@login_required
@roles_required(*WRITE_ROLES)
@disabled_in_public_demo
def delete_shipment(shipment_id):
    from app.models.shipment import Shipment
    s = Shipment.query.get(shipment_id)
    id_viaje = s.id_viaje if s else None
    ok = shipment_service.delete_shipment(shipment_id)
    if not ok:
        return jsonify({"error": "Embarque no encontrado"}), 404
    register_audit(current_user, "eliminar_embarque", entidad="Shipment", entidad_id=id_viaje)
    return jsonify({"ok": True})
