import secrets
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

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


VISITANTE_EMAIL = "visitante@ransa.demo"


def get_visitante() -> User:
    """Cuenta del enlace público (se crea sola). Su clave es aleatoria: solo se entra por el enlace."""
    user = User.query.filter_by(email=VISITANTE_EMAIL).first()
    if user:
        return user
    user = User(nombre_completo="Visitante", email=VISITANTE_EMAIL, rol="Supervisor",
                cargo="Acceso público de demostración")
    user.set_password(secrets.token_urlsafe(32))
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:  # otra petición la creó al mismo tiempo
        db.session.rollback()
        user = User.query.filter_by(email=VISITANTE_EMAIL).first()
    return user
