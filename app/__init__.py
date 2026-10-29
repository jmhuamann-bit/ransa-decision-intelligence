import os

from flask import Flask, jsonify

from app.config import CONFIG_BY_NAME
from app.extensions import cors, db, login_manager, migrate


def create_app(config_name: str = None, start_live_engine: bool = True) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object(CONFIG_BY_NAME.get(config_name, CONFIG_BY_NAME["development"]))

    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, supports_credentials=True)

    login_manager.init_app(app)
    login_manager.login_view = "web.login_page"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        from flask import request, redirect, url_for
        if request.path.startswith("/api/"):
            return jsonify({"error": "No autenticado"}), 401
        return redirect(url_for("web.login_page"))

    @app.before_request
    def _acceso_publico():
        """Enlace público: quien llega sin sesión entra directo como Visitante. El login sigue
        disponible en /login para elegir otro perfil de demostración."""
        from flask import request
        from flask_login import current_user, login_user
        if not app.config.get("PUBLIC_ACCESS") or current_user.is_authenticated:
            return
        if request.endpoint in (None, "static", "web.login_page", "web.salud") or request.path.startswith("/api/auth/"):
            return
        from app.services.auth_service import get_visitante
        login_user(get_visitante(), remember=False)

    @app.context_processor
    def _plantillas():
        return {"public_access": app.config.get("PUBLIC_ACCESS", False)}

    register_blueprints(app)
    register_error_handlers(app)

    # run.py arranca con use_reloader=False y Gunicorn con un único worker (ver render.yaml), así
    # que hay un solo gemelo digital por servidor: todos los usuarios ven la MISMA operación.
    # El bucle del gemelo NO se lanza al importar: arranca con la primera petición del proceso que
    # realmente atiende (un hilo creado antes de un fork de Gunicorn no existiría en el worker) y un
    # vigía lo relanza si dejara de correr. Los scripts de carga/entrenamiento no lo arrancan.
    if start_live_engine:
        from app.services.live_engine import get_engine
        engine = get_engine()
        engine.attach(app)

        @app.before_request
        def _gemelo_vivo():
            engine.ensure_running()

    return app


def register_blueprints(app: Flask) -> None:
    from app.web import bp as web_bp
    from app.api.auth import bp as auth_bp
    from app.api.dashboard import bp as dashboard_bp
    from app.api.monitoring import bp as monitoring_bp
    from app.api.predictions import bp as predictions_bp
    from app.api.simulator import bp as simulator_bp
    from app.api.map import bp as map_bp
    from app.api.live import bp as live_bp
    from app.api.predictive import bp as predictive_bp
    from app.api.strategic import bp as strategic_bp
    from app.api.context import bp as context_bp
    from app.api.prioritization import bp as prioritization_bp
    from app.api.leadtime import bp as leadtime_bp
    from app.api.shipments import bp as shipments_bp
    from app.api.clients import bp as clients_bp
    from app.api.kpis import bp as kpis_bp
    from app.api.reports import bp as reports_bp
    from app.api.chat import bp as chat_bp
    from app.api.admin import bp as admin_bp
    from app.api.contingencies import bp as contingencies_bp
    from app.api.company import bp as company_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(predictions_bp)
    app.register_blueprint(simulator_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(predictive_bp)
    app.register_blueprint(strategic_bp)
    app.register_blueprint(context_bp)
    app.register_blueprint(prioritization_bp)
    app.register_blueprint(leadtime_bp)
    app.register_blueprint(shipments_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(kpis_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(contingencies_bp)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        from flask import request
        if request.path.startswith("/api/"):
            return jsonify({"error": "Recurso no encontrado"}), 404
        return e, 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request
        app.logger.exception("Error interno")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Error interno del servidor"}), 500
        return e, 500
