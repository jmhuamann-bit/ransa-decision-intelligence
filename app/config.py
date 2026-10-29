"""
Configuracion centralizada de la aplicacion.

La capa de acceso a datos esta desacoplada del motor real: por defecto se usa
SQLite (data/ransa.db), pero SQLALCHEMY_DATABASE_URI acepta cualquier
URI soportada por SQLAlchemy (PostgreSQL, SQL Server via pyodbc, MySQL, etc.)
sin cambiar una sola linea de los modelos, servicios o API.
"""
import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raíz del proyecto
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")


def _build_default_sqlite_uri() -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, "ransa.db")
    return f"sqlite:///{db_path}"


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "ransa-dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _build_default_sqlite_uri())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    JSON_SORT_KEYS = False

    # Umbral de probabilidad (%) sobre el cual se dispara una Alerta Critica
    RISK_ALERT_THRESHOLD_PCT = float(os.environ.get("RISK_ALERT_THRESHOLD_PCT", 80))

    # Modo demostración: habilita el acceso de un clic por rol en el login (cuentas demo).
    # Desactivar en un despliegue real con DEMO_MODE=false.
    DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() in ("1", "true", "yes", "si", "sí")

    # Enlace público: quien llega sin sesión entra directo como "Visitante" (sin pantalla de login).
    # Para que nadie altere la demo de todos, se bloquean el perfil Administrador y las acciones que
    # cambian datos o modelos (reentrenar/activar, usuarios, escritura de embarques).
    PUBLIC_ACCESS = os.environ.get("PUBLIC_ACCESS", "true" if DEMO_MODE else "false").lower() in (
        "1", "true", "yes", "si", "sí")

    # Integraciones externas: se activan solo si existen credenciales (ver app/integrations)
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = os.environ.get("SMTP_PORT")
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

    WHATSAPP_BUSINESS_TOKEN = os.environ.get("WHATSAPP_BUSINESS_TOKEN")
    WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

    TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")

    OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
    MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN")


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


CONFIG_BY_NAME = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
