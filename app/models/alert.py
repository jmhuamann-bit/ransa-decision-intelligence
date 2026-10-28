from datetime import datetime, timezone

from app.extensions import db


class Alert(db.Model):
    """Alerta generada por el motor de Predicciones IA u operativamente (contingencia manual)."""
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    shipment_id = db.Column(db.Integer, db.ForeignKey("shipments.id"), index=True)
    id_viaje = db.Column(db.String(30), index=True)
    tipo = db.Column(db.String(40), nullable=False, default="prediccion_ia")  # prediccion_ia | contingencia_manual
    severidad = db.Column(db.String(20), nullable=False, default="Critica")  # Baja/Media/Alta/Critica
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    probabilidad_pct = db.Column(db.Float)
    estado = db.Column(db.String(20), nullable=False, default="Abierta")  # Abierta/En Gestion/Resuelta
    creado_en = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resuelto_en = db.Column(db.DateTime)
    canal_notificacion = db.Column(db.String(200))  # registro de a donde se hubiera enviado (email/whatsapp/teams/slack)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shipment_id": self.shipment_id,
            "id_viaje": self.id_viaje,
            "tipo": self.tipo,
            "severidad": self.severidad,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "probabilidad_pct": self.probabilidad_pct,
            "estado": self.estado,
            "canal_notificacion": self.canal_notificacion,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
            "resuelto_en": self.resuelto_en.isoformat() if self.resuelto_en else None,
        }
