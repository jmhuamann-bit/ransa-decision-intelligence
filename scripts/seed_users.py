"""
Crea los usuarios demo iniciales (uno por rol) para poder iniciar sesión.
Ejecutar: python scripts/seed_users.py

IMPORTANTE: son credenciales de DEMOSTRACIÓN (dominio ficticio ransa.demo). Cambiarlas, o
desactivar el acceso demo con DEMO_MODE=false, antes de cualquier uso real.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User

DEMO_USERS = [
    {"nombre_completo": "Administrador RANSA", "email": "admin@ransa.demo", "rol": "Administrador",
     "cargo": "Administrador de Plataforma"},
    {"nombre_completo": "Lucía Quispe", "email": "supervisor@ransa.demo", "rol": "Supervisor",
     "cargo": "Gerente de Torre de Control"},
    {"nombre_completo": "Carlos Huamán", "email": "operaciones@ransa.demo", "rol": "Operaciones",
     "cargo": "Coordinador de Operaciones Multimodales"},
    {"nombre_completo": "Cliente Demo S.A.C.", "email": "cliente@ransa.demo", "rol": "Cliente",
     "cargo": "Jefe de Logística (cliente)"},
    {"nombre_completo": "Andrea Salazar", "email": "analista@ransa.demo", "rol": "Analista",
     "cargo": "Analista de Datos e IA"},
]
DEMO_PASSWORD = "Ransa2026!"


def seed() -> int:
    creados = 0
    for u in DEMO_USERS:
        if User.query.filter_by(email=u["email"]).first():
            continue
        user = User(nombre_completo=u["nombre_completo"], email=u["email"], rol=u["rol"], cargo=u["cargo"])
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        creados += 1
    db.session.commit()
    return creados


if __name__ == "__main__":
    app = create_app(start_live_engine=False)
    with app.app_context():
        db.create_all()
        n = seed()
        print(f"OK: {n} usuarios demo creados (o ya existían). Contraseña común definida en DEMO_PASSWORD.")
