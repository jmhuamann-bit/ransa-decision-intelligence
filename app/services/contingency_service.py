"""Gestion del ciclo de vida de las Alertas/Contingencias: alertas automaticas generadas por el
modelo de IA (tipo='prediccion_ia'), contingencias creadas manualmente por un operador
(tipo='contingencia_manual'), y planes de contingencia propuestos por el AI Decision
Assistant (tipo='plan_contingencia_ia', ver app/services/decision_assistant.py).

Flujo normal:            Abierta -> En Gestion -> Resuelta.
Flujo de plan de IA:      Pendiente Aprobación Directiva -> (un directivo aprueba) -> Comunicada -> En Gestion -> Resuelta.

El flujo de plan de IA existe porque la comunicacion de un plan de contingencia (avisar
a las areas de RANSA, al conductor y negociar con el cliente) NUNCA debe salir
automaticamente: primero se avisa solo a los directivos (Administrador/Supervisor) y
unicamente cuando ellos aprueban se simula el despliegue del comunicado al resto de
audiencias -- ver aprobar_y_comunicar()."""
from datetime import datetime, timezone

from app.extensions import db
from app.models.alert import Alert
from app.models.shipment import Shipment

ESTADOS_VALIDOS = ("Abierta", "Pendiente Aprobación Directiva", "En Gestion", "Comunicada", "Resuelta")

# Canales de notificacion preparados (ver app/config.py) - se listan aqui para reflejar en el
# detalle de cada alerta a donde SE ENVIARIA la notificacion una vez se configuren credenciales.
CANALES_PREPARADOS = ("Email", "WhatsApp Business", "Microsoft Teams", "Slack")


def get_summary() -> dict:
    from sqlalchemy import func
    rows = Alert.query.with_entities(Alert.estado, func.count(Alert.id)).group_by(Alert.estado).all()
    counts = {estado: 0 for estado in ESTADOS_VALIDOS}
    for estado, total in rows:
        counts[estado] = total
    criticas_abiertas = Alert.query.filter_by(estado="Abierta", severidad="Critica").count()
    return {
        "abiertas": counts["Abierta"],
        "en_gestion": counts["En Gestion"],
        "resueltas": counts["Resuelta"],
        "criticas_abiertas": criticas_abiertas,
        "total": sum(counts.values()),
    }


def list_alerts(filtros: dict, page: int = 1, page_size: int = 20) -> dict:
    q = Alert.query
    if filtros.get("estado"):
        q = q.filter(Alert.estado == filtros["estado"])
    if filtros.get("severidad"):
        q = q.filter(Alert.severidad == filtros["severidad"])
    if filtros.get("tipo"):
        q = q.filter(Alert.tipo == filtros["tipo"])
    if filtros.get("busqueda"):
        q = q.filter(Alert.id_viaje.ilike(f"%{filtros['busqueda'].strip()}%"))

    q = q.order_by(Alert.creado_en.desc())
    total = q.count()
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [a.to_dict() for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def get_alert_detail(alert_id: int) -> dict | None:
    alert = Alert.query.get(alert_id)
    if not alert:
        return None
    data = alert.to_dict()
    if alert.shipment_id:
        shipment = Shipment.query.get(alert.shipment_id)
        if shipment:
            data["embarque"] = {
                "id_viaje": shipment.id_viaje,
                "ciudad_origen": shipment.ciudad_origen,
                "ciudad_destino": shipment.ciudad_destino,
                "tipo_transporte": shipment.tipo_transporte,
                "prioridad_cliente": shipment.prioridad_cliente,
                "tiempo_programado_horas": shipment.tiempo_programado_horas,
                "nivel_riesgo": shipment.nivel_riesgo,
            }
    data["canales_preparados"] = list(CANALES_PREPARADOS)
    return data


def update_estado(alert_id: int, nuevo_estado: str) -> Alert | None:
    if nuevo_estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado invalido: {nuevo_estado}")
    alert = Alert.query.get(alert_id)
    if not alert:
        return None
    alert.estado = nuevo_estado
    alert.resuelto_en = datetime.now(timezone.utc) if nuevo_estado == "Resuelta" else None
    db.session.commit()
    return alert


def create_manual_contingency(data: dict) -> Alert:
    alert = Alert(
        id_viaje=data.get("id_viaje") or None,
        tipo="contingencia_manual",
        severidad=data.get("severidad", "Media"),
        titulo=data["titulo"],
        descripcion=data.get("descripcion"),
        probabilidad_pct=None,
        estado="Abierta",
    )
    if data.get("id_viaje"):
        shipment = Shipment.query.filter_by(id_viaje=data["id_viaje"]).first()
        if shipment:
            alert.shipment_id = shipment.id
    db.session.add(alert)
    db.session.commit()
    return alert


def _ahora_txt() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%d/%m %H:%M")


def create_plan_contingencia(data: dict) -> Alert:
    """Primer paso del flujo de plan de contingencia: la IA (o un operador en su nombre)
    propone una accion, pero solo se notifica a los directivos -- nadie mas se entera
    todavia."""
    alert = Alert(
        id_viaje=data.get("id_viaje") or None,
        tipo="plan_contingencia_ia",
        severidad=data.get("severidad", "Alta"),
        titulo=data["titulo"],
        descripcion=data.get("descripcion"),
        probabilidad_pct=data.get("probabilidad_pct"),
        estado="Pendiente Aprobación Directiva",
        canal_notificacion=f"[{_ahora_txt()}] Directivos RANSA: notificados para aprobación del plan.",
    )
    if data.get("id_viaje"):
        shipment = Shipment.query.filter_by(id_viaje=data["id_viaje"]).first()
        if shipment:
            alert.shipment_id = shipment.id
    db.session.add(alert)
    db.session.commit()
    return alert


def aprobar_y_comunicar(alert_id: int) -> Alert | None:
    """Un directivo aprueba el plan. Solo a partir de aqui se simula el despliegue del
    comunicado al resto de audiencias (areas de RANSA, conductor, cliente). No se
    envian mensajes reales -- no hay credenciales SMTP/WhatsApp/Teams configuradas (ver
    app/config.py) -- se deja un registro de a quien y cuando se habria notificado."""
    alert = Alert.query.get(alert_id)
    if not alert or alert.estado != "Pendiente Aprobación Directiva":
        return None
    ts = _ahora_txt()
    lineas = [
        alert.canal_notificacion or "",
        f"[{ts}] Áreas RANSA (Torre de Control, Servicio al Cliente, Seguridad): notificadas con el plan de contingencia.",
        f"[{ts}] Conductor asignado: notificado con las instrucciones del plan.",
        f"[{ts}] Cliente afectado: negociación del plan de contingencia iniciada.",
    ]
    alert.canal_notificacion = "\n".join(l for l in lineas if l)
    alert.estado = "Comunicada"
    db.session.commit()
    return alert
