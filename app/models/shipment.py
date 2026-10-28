"""
Modelo Embarque (Viaje/Shipment) - generado automaticamente desde field_metadata.FIELDS
para garantizar correspondencia exacta con las 98 columnas del dataset RANSA Perú.
NO editar a mano: regenerar con scripts/_gen_shipment_model.py
"""
from app.extensions import db


class Shipment(db.Model):
    """Un registro = un viaje/embarque (ID_Viaje) del dataset RANSA Perú."""
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)
    id_viaje = db.Column(db.String(30), unique=True, nullable=False, index=True)
    fecha = db.Column(db.Date, index=True)
    dia_semana = db.Column(db.String(255))
    mes = db.Column(db.String(255))
    trimestre = db.Column(db.String(255))
    ano = db.Column(db.Integer)
    departamento_origen = db.Column(db.String(255), index=True)
    ciudad_origen = db.Column(db.String(255), index=True)
    departamento_destino = db.Column(db.String(255), index=True)
    ciudad_destino = db.Column(db.String(255), index=True)
    corredor_logistico = db.Column(db.String(255), index=True)
    ruta_principal = db.Column(db.String(255))
    tipo_transporte = db.Column(db.String(255), index=True)
    tipo_vehiculo = db.Column(db.String(255))
    tipo_carga = db.Column(db.String(255))
    sector_cliente = db.Column(db.String(255), index=True)
    peso_toneladas = db.Column(db.Float)
    volumen_m3 = db.Column(db.Float)
    distancia_km = db.Column(db.Float)
    altitud_max_ruta_msnm = db.Column(db.Float)
    tiempo_programado_horas = db.Column(db.Float)
    tiempo_entrega_real_horas = db.Column(db.Float)
    velocidad_promedio_kmh = db.Column(db.Float)
    tiempo_espera_horas = db.Column(db.Float)
    consumo_combustible_galones = db.Column(db.Float)
    costo_transporte_pen = db.Column(db.Float)
    costo_peajes_pen = db.Column(db.Float)
    disponibilidad_flota_pct = db.Column(db.Float)
    utilizacion_flota_pct = db.Column(db.Float)
    estado_via = db.Column(db.String(255), index=True)
    indice_deterioro_vial = db.Column(db.Float)
    numero_cierres_viales = db.Column(db.Integer)
    numero_bloqueos_carretera = db.Column(db.Integer)
    indice_bloqueos = db.Column(db.Float)
    obras_viales_activas = db.Column(db.Integer)
    restricciones_peso = db.Column(db.Integer)
    restricciones_horarias = db.Column(db.Integer)
    indice_seguridad = db.Column(db.Float)
    riesgo_hurto_carga = db.Column(db.String(255))
    numero_eventos_seguridad = db.Column(db.Integer)
    presencia_crimen_organizado = db.Column(db.Integer)
    indice_orden_publico = db.Column(db.Float)
    riesgo_extorsion = db.Column(db.String(255))
    riesgo_vandalismo = db.Column(db.String(255))
    riesgo_saqueo = db.Column(db.String(255))
    numero_paros = db.Column(db.Integer)
    indice_protestas = db.Column(db.Float)
    manifestaciones = db.Column(db.Integer)
    huelgas = db.Column(db.Integer)
    bloqueos_sociales = db.Column(db.Integer)
    temperatura_c = db.Column(db.Float)
    precipitacion_mm = db.Column(db.Float)
    humedad_pct = db.Column(db.Float)
    velocidad_viento_kmh = db.Column(db.Float)
    alerta_senamhi = db.Column(db.String(255))
    fenomeno_climatico = db.Column(db.String(255))
    numero_inundaciones = db.Column(db.Integer)
    indice_inundaciones = db.Column(db.Float)
    numero_deslizamientos = db.Column(db.Integer)
    indice_deslizamientos = db.Column(db.Float)
    numero_derrumbes = db.Column(db.Integer)
    indice_derrumbes = db.Column(db.Float)
    numero_incendios_forestales = db.Column(db.Integer)
    indice_incendios = db.Column(db.Float)
    riesgo_geologico = db.Column(db.String(255))
    riesgo_hidrologico = db.Column(db.String(255))
    numero_accidentes = db.Column(db.Integer)
    intensidad_incidente = db.Column(db.String(255))
    duracion_incidente_horas = db.Column(db.Float)
    tiempo_cierre_via_horas = db.Column(db.Float)
    precio_diesel_pen_gal = db.Column(db.Float)
    precio_gasolina_pen_gal = db.Column(db.Float)
    ipc = db.Column(db.Float)
    tipo_cambio_pen_usd = db.Column(db.Float)
    inflacion_pct = db.Column(db.Float)
    precio_peajes_promedio_pen = db.Column(db.Float)
    indice_abastecimiento = db.Column(db.Float)
    nivel_inventario_pct = db.Column(db.Float)
    demanda_unidades = db.Column(db.Float)
    demanda_pronosticada_unidades = db.Column(db.Float)
    prioridad_cliente = db.Column(db.String(255), index=True)
    otif = db.Column(db.Integer, index=True)
    fill_rate_pct = db.Column(db.Float)
    nivel_servicio_pct = db.Column(db.Float)
    tiempo_almacenamiento_horas = db.Column(db.Float)
    cross_docking = db.Column(db.Integer)
    tipo_almacen = db.Column(db.String(255))
    capacidad_almacen_m3 = db.Column(db.Float)
    utilizacion_almacen_pct = db.Column(db.Float)
    aseguradora = db.Column(db.String(255))
    tipo_cobertura_seguro = db.Column(db.String(255))
    valor_asegurado_pen = db.Column(db.Float)
    prima_seguro_pen = db.Column(db.Float)
    deducible_pen = db.Column(db.Float)
    siniestro = db.Column(db.Integer)
    valor_siniestro_pen = db.Column(db.Float)
    estado_reclamacion = db.Column(db.String(255))
    leadtime_real_dias = db.Column(db.Float)

    # --- Riesgo calculado por el modulo de Predicciones IA (ver app/ml) ---
    prob_riesgo_incumplimiento = db.Column(db.Float)  # 0-100, probabilidad de NO cumplir OTIF
    nivel_riesgo = db.Column(db.String(20), index=True)  # Bajo / Medio / Alto / Critico
    alerta_critica = db.Column(db.Boolean, default=False, index=True)

    COLUMNS = [
        "id_viaje",
        "fecha",
        "dia_semana",
        "mes",
        "trimestre",
        "ano",
        "departamento_origen",
        "ciudad_origen",
        "departamento_destino",
        "ciudad_destino",
        "corredor_logistico",
        "ruta_principal",
        "tipo_transporte",
        "tipo_vehiculo",
        "tipo_carga",
        "sector_cliente",
        "peso_toneladas",
        "volumen_m3",
        "distancia_km",
        "altitud_max_ruta_msnm",
        "tiempo_programado_horas",
        "tiempo_entrega_real_horas",
        "velocidad_promedio_kmh",
        "tiempo_espera_horas",
        "consumo_combustible_galones",
        "costo_transporte_pen",
        "costo_peajes_pen",
        "disponibilidad_flota_pct",
        "utilizacion_flota_pct",
        "estado_via",
        "indice_deterioro_vial",
        "numero_cierres_viales",
        "numero_bloqueos_carretera",
        "indice_bloqueos",
        "obras_viales_activas",
        "restricciones_peso",
        "restricciones_horarias",
        "indice_seguridad",
        "riesgo_hurto_carga",
        "numero_eventos_seguridad",
        "presencia_crimen_organizado",
        "indice_orden_publico",
        "riesgo_extorsion",
        "riesgo_vandalismo",
        "riesgo_saqueo",
        "numero_paros",
        "indice_protestas",
        "manifestaciones",
        "huelgas",
        "bloqueos_sociales",
        "temperatura_c",
        "precipitacion_mm",
        "humedad_pct",
        "velocidad_viento_kmh",
        "alerta_senamhi",
        "fenomeno_climatico",
        "numero_inundaciones",
        "indice_inundaciones",
        "numero_deslizamientos",
        "indice_deslizamientos",
        "numero_derrumbes",
        "indice_derrumbes",
        "numero_incendios_forestales",
        "indice_incendios",
        "riesgo_geologico",
        "riesgo_hidrologico",
        "numero_accidentes",
        "intensidad_incidente",
        "duracion_incidente_horas",
        "tiempo_cierre_via_horas",
        "precio_diesel_pen_gal",
        "precio_gasolina_pen_gal",
        "ipc",
        "tipo_cambio_pen_usd",
        "inflacion_pct",
        "precio_peajes_promedio_pen",
        "indice_abastecimiento",
        "nivel_inventario_pct",
        "demanda_unidades",
        "demanda_pronosticada_unidades",
        "prioridad_cliente",
        "otif",
        "fill_rate_pct",
        "nivel_servicio_pct",
        "tiempo_almacenamiento_horas",
        "cross_docking",
        "tipo_almacen",
        "capacidad_almacen_m3",
        "utilizacion_almacen_pct",
        "aseguradora",
        "tipo_cobertura_seguro",
        "valor_asegurado_pen",
        "prima_seguro_pen",
        "deducible_pen",
        "siniestro",
        "valor_siniestro_pen",
        "estado_reclamacion",
        "leadtime_real_dias",
    ]

    def to_dict(self) -> dict:
        data = {c: getattr(self, c) for c in self.COLUMNS}
        data["id"] = self.id
        if data.get("fecha") is not None:
            data["fecha"] = data["fecha"].isoformat()
        data["prob_riesgo_incumplimiento"] = self.prob_riesgo_incumplimiento
        data["nivel_riesgo"] = self.nivel_riesgo
        data["alerta_critica"] = self.alerta_critica
        return data
