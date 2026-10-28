from flask import Blueprint, Response, request
from flask_login import login_required

from app.services import monitoring_service, report_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/ejecutivo.pdf")
@login_required
def ejecutivo_pdf():
    pdf_bytes = report_service.build_executive_pdf()
    return Response(
        pdf_bytes, mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=ransa_reporte_ejecutivo.pdf"},
    )


@bp.get("/monitoreo.xlsx")
@login_required
def monitoreo_excel():
    filtros = {k: request.args.get(k) for k in monitoring_service.FILTERABLE_FIELDS.keys()}
    filtros["busqueda"] = request.args.get("busqueda")
    excel_bytes = report_service.build_monitoring_excel(filtros)
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ransa_monitoreo.xlsx"},
    )
