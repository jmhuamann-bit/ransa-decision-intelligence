from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.ml_model import MLModelRun
from app.models.user import ROLES, User
from app.services.auth_service import create_user, register_audit
from app.utils.decorators import disabled_in_public_demo, roles_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/users")
@login_required
@roles_required()
def list_users():
    users = User.query.order_by(User.creado_en.desc()).all()
    return jsonify({"users": [u.to_dict() for u in users], "roles": list(ROLES)})


@bp.post("/users")
@login_required
@roles_required()
@disabled_in_public_demo
def create_user_endpoint():
    data = request.get_json(silent=True) or {}
    for field in ("nombre_completo", "email", "password", "rol"):
        if not data.get(field):
            return jsonify({"error": f"El campo '{field}' es obligatorio"}), 400
    if data["rol"] not in ROLES:
        return jsonify({"error": "Rol inválido"}), 400
    if User.query.filter_by(email=data["email"].strip().lower()).first():
        return jsonify({"error": "Ya existe un usuario con ese email"}), 400

    user = create_user(data["nombre_completo"], data["email"], data["password"], data["rol"],
                        telefono=data.get("telefono"), cargo=data.get("cargo"))
    register_audit(current_user, "crear_usuario", entidad="User", entidad_id=user.id, detalle=user.email)
    return jsonify(user.to_dict()), 201


@bp.put("/users/<int:user_id>")
@login_required
@roles_required()
@disabled_in_public_demo
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    data = request.get_json(silent=True) or {}
    if "rol" in data:
        if data["rol"] not in ROLES:
            return jsonify({"error": "Rol inválido"}), 400
        user.rol = data["rol"]
    if "activo" in data:
        if user.id == current_user.id and not data["activo"]:
            return jsonify({"error": "No puedes desactivar tu propia cuenta"}), 400
        user.activo = bool(data["activo"])
    if "cargo" in data:
        user.cargo = data["cargo"]
    if "telefono" in data:
        user.telefono = data["telefono"]
    db.session.commit()
    register_audit(current_user, "editar_usuario", entidad="User", entidad_id=user.id, detalle=user.email)
    return jsonify(user.to_dict())


@bp.get("/ai-settings")
@login_required
def ai_settings():
    run = MLModelRun.query.filter_by(activo=True).order_by(MLModelRun.creado_en.desc()).first()
    return jsonify({
        "umbral_alerta_critica_pct": current_app.config["RISK_ALERT_THRESHOLD_PCT"],
        "modelo_activo": run.to_dict() if run else None,
    })


@bp.get("/integrations")
@login_required
def integrations():
    cfg = current_app.config
    def status(*keys):
        return "Configurado" if all(cfg.get(k) for k in keys) else "No configurado"

    return jsonify({"integrations": [
        {"nombre": "Correo (SMTP / Microsoft 365)", "icono": "fa-envelope",
         "estado": status("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"),
         "descripcion": "Envío de alertas críticas por correo electrónico."},
        {"nombre": "WhatsApp Business API", "icono": "fa-brands fa-whatsapp",
         "estado": status("WHATSAPP_BUSINESS_TOKEN", "WHATSAPP_PHONE_ID"),
         "descripcion": "API oficial de Meta para notificaciones de alto riesgo."},
        {"nombre": "Microsoft Teams", "icono": "fa-brands fa-microsoft",
         "estado": status("TEAMS_WEBHOOK_URL"),
         "descripcion": "Webhook de canal para contingencias críticas."},
        {"nombre": "Slack", "icono": "fa-brands fa-slack",
         "estado": status("SLACK_WEBHOOK_URL"),
         "descripcion": "Webhook de canal para contingencias críticas."},
        {"nombre": "OpenWeather", "icono": "fa-cloud-sun",
         "estado": status("OPENWEATHER_API_KEY"),
         "descripcion": "Clima en tiempo real para el Mapa Inteligente."},
        {"nombre": "Mapbox", "icono": "fa-map",
         "estado": status("MAPBOX_TOKEN"),
         "descripcion": "Capas de mapa alternativas de alta resolución."},
    ]})


@bp.get("/audit-logs")
@login_required
@roles_required("Supervisor")
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.creado_en.desc()).limit(100).all()
    return jsonify({"logs": [l.to_dict() for l in logs]})
