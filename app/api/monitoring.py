import csv
import io

from flask import Blueprint, Response, jsonify, request
from flask_login import login_required

from app.services import monitoring_service

bp = Blueprint("monitoring", __name__, url_prefix="/api/monitoring")


@bp.get("/shipments")
@login_required
def list_shipments():
    filtros = {k: request.args.get(k) for k in monitoring_service.FILTERABLE_FIELDS.keys()}
    filtros["busqueda"] = request.args.get("busqueda")
    filtros["fecha_desde"] = request.args.get("fecha_desde")
    filtros["fecha_hasta"] = request.args.get("fecha_hasta")

    page = request.args.get("page", default=1, type=int)
    page_size = request.args.get("page_size", default=25, type=int)
    sort_by = request.args.get("sort_by", default="fecha")
    sort_dir = request.args.get("sort_dir", default="desc")

    result = monitoring_service.search_shipments(filtros, page, page_size, sort_by, sort_dir)
    return jsonify(result)


@bp.get("/filters")
@login_required
def filters():
    return jsonify(monitoring_service.get_filter_options())


@bp.get("/shipments.csv")
@login_required
def export_csv():
    filtros = {k: request.args.get(k) for k in monitoring_service.FILTERABLE_FIELDS.keys()}
    filtros["busqueda"] = request.args.get("busqueda")
    filtros["fecha_desde"] = request.args.get("fecha_desde")
    filtros["fecha_hasta"] = request.args.get("fecha_hasta")

    result = monitoring_service.search_shipments(filtros, page=1, page_size=5000)
    output = io.StringIO()
    if result["items"]:
        writer = csv.DictWriter(output, fieldnames=list(result["items"][0].keys()))
        writer.writeheader()
        writer.writerows(result["items"])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ransa_monitoreo.csv"},
    )


@bp.get("/shipments/<id_viaje>")
@login_required
def shipment_detail(id_viaje):
    s = monitoring_service.get_shipment_detail(id_viaje)
    if not s:
        return jsonify({"error": "Embarque no encontrado"}), 404
    return jsonify(s.to_dict())
