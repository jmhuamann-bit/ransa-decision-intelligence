from functools import wraps

from flask import jsonify
from flask_login import current_user


def roles_required(*roles):
    """Restringe un endpoint a uno o mas roles. Administrador siempre tiene acceso total."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({"error": "No autenticado"}), 401
            if current_user.rol != "Administrador" and current_user.rol not in roles:
                return jsonify({"error": "No autorizado para este recurso"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
