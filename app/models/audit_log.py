from datetime import datetime, timezone

from app.extensions import db


class AuditLog(db.Model):
    """Bitacora de acciones sensibles (login, cambios de configuracion, CRUD de embarques, ETL)."""
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    usuario_email = db.Column(db.String(150))
    accion = db.Column(db.String(100), nullable=False, index=True)
    entidad = db.Column(db.String(100))
    entidad_id = db.Column(db.String(50))
    detalle = db.Column(db.Text)
    ip = db.Column(db.String(60))
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario_email": self.usuario_email,
            "accion": self.accion,
            "entidad": self.entidad,
            "entidad_id": self.entidad_id,
            "detalle": self.detalle,
            "ip": self.ip,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
        }
