from datetime import datetime, timezone

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.user import User


def authenticate(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email.strip().lower()).first()
    if not user or not user.activo or not user.check_password(password):
        return None
    user.ultimo_acceso = datetime.now(timezone.utc)
    db.session.commit()
    return user


def register_audit(user: User | None, accion: str, entidad: str = None, entidad_id: str = None,
                    detalle: str = None, ip: str = None) -> None:
    log = AuditLog(
        user_id=user.id if user else None,
        usuario_email=user.email if user else None,
        accion=accion,
        entidad=entidad,
        entidad_id=str(entidad_id) if entidad_id is not None else None,
        detalle=detalle,
        ip=ip,
    )
    db.session.add(log)
    db.session.commit()


def create_user(nombre_completo: str, email: str, password: str, rol: str, telefono: str = None,
                 cargo: str = None) -> User:
    user = User(
        nombre_completo=nombre_completo,
        email=email.strip().lower(),
        rol=rol,
        telefono=telefono,
        cargo=cargo,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user
