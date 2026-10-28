"""Instancias unicas de extensiones Flask, compartidas por toda la app (evita imports circulares)."""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_cors import CORS
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
cors = CORS()
migrate = Migrate()
