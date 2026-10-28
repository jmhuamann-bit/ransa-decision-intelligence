"""
Simulador de escenarios de RED (what-if ejecutivo).

A diferencia del simulador de un solo embarque (`simulator_service.py`, que llama al
modelo de IA para un viaje concreto), este módulo responde: "¿qué le pasa a TODA la
operación si ocurre X?" — cerrar un puerto, un paro nacional, temporada de lluvias,
+20% en combustible, etc.

Metodología (transparente):
  * La LÍNEA BASE se calcula con los 30.000 embarques del dataset RANSA Perú.
  * Cada escenario define (a) qué subconjunto de embarques afecta (un nodo, un corredor,
    un modo de transporte, o toda la red) y (b) unos factores de impacto sobre OTIF,
    lead time, costo, CO₂ y riesgo de ese subconjunto.
  * Los KPIs de red se recalculan mezclando el subconjunto afectado (con factores) y el
    no afectado (intacto).

Los factores de impacto son supuestos de negocio HEURÍSTICOS declarados explícitamente
aquí — son auditables y ajustables, y NO salidas de un modelo entrenado.
"""
from sqlalchemy import case, func

from app.models.shipment import Shipment
from app.services import dashboard_service
from app.services.geo_data import CITY_COORDS

CO2_KG_POR_GALON = dashboard_service.CO2_KG_POR_GALON_DIESEL

SUR_ANDINO = ["Cusco", "Juliaca", "Puno", "Arequipa", "Challhuahuacho", "Matarani", "Puerto Maldonado", "Tacna",
              "Moquegua", "Ilo", "Ica"]
NORTE_COSTERO = ["Piura", "Paita", "Tumbes", "Chiclayo", "Trujillo", "Salaverry", "Chimbote"]
SIERRA_SELVA = ["Huancayo", "Cerro de Pasco", "Huánuco", "Pucallpa", "Huaraz", "Cajamarca", "Cusco", "Juliaca", "Puno",
                "Ayacucho", "Tarapoto", "Yurimaguas", "Puerto Maldonado", "Challhuahuacho"]

ESCENARIOS = {
    "cerrar_puerto": {
        "nombre": "Cierre de puerto (oleaje anómalo)", "icon": "fa-anchor", "scope": "nodo", "requiere_objetivo": True,
        "descripcion": "La DHN cierra el puerto seleccionado por oleaje anómalo: buques en fondeadero y carga represada.",
        "otif_retention": 0.15, "lt_mult": 1.85, "costo_mult": 1.42, "co2_mult": 1.25, "riesgo_mult": 1.90,
        "recomendacion": "Activar el puerto alterno (Chancay o Callao, Salaverry/Paita en el norte, Ilo/Matarani en el sur), priorizar la carga crítica y renegociar ventanas de atraque.",
    },
    "cerrar_corredor": {
        "nombre": "Cierre de corredor (huaico / derrumbe)", "icon": "fa-hill-rockslide", "scope": "corredor", "requiere_objetivo": True,
        "descripcion": "El corredor seleccionado queda intransitable por un huaico o derrumbe de gran magnitud.",
        "otif_retention": 0.20, "lt_mult": 1.70, "costo_mult": 1.35, "co2_mult": 1.22, "riesgo_mult": 1.80,
        "recomendacion": "Desviar por las rutas alternas reales (Cañete–Lunahuaná PE-24 o Canta–Huayllay PE-20A para la Carretera Central) y evaluar cabotaje para la carga de mayor valor.",
    },
    "falla_centro_logistico": {
        "nombre": "Falla en centro de distribución", "icon": "fa-warehouse", "scope": "nodo", "requiere_objetivo": True,
        "descripcion": "El nodo seleccionado pierde capacidad de recepción, despacho y almacenamiento.",
        "otif_retention": 0.35, "lt_mult": 1.45, "costo_mult": 1.18, "co2_mult": 1.05, "riesgo_mult": 1.50,
        "recomendacion": "Redistribuir inventario desde almacenes cercanos (Lurín y Callao, Arequipa y Matarani) y activar cross-docking temporal.",
    },
    "accidente_multiple": {
        "nombre": "Accidente múltiple", "icon": "fa-car-burst", "scope": "corredor", "requiere_objetivo": True,
        "descripcion": "Siniestro vial con cierre temporal del corredor seleccionado.",
        "otif_retention": 0.45, "lt_mult": 1.35, "costo_mult": 1.12, "co2_mult": 1.08, "riesgo_mult": 1.60,
        "recomendacion": "Detener despachos hacia el tramo, reencaminar a los vehículos en tránsito y notificar a los clientes con entregas del día.",
    },
    "mantenimiento_corredor": {
        "nombre": "Obras / cierre programado (Provías)", "icon": "fa-person-digging", "scope": "corredor", "requiere_objetivo": True,
        "descripcion": "Obras programadas con cierres por horario reducen la capacidad del corredor seleccionado.",
        "otif_retention": 0.70, "lt_mult": 1.18, "costo_mult": 1.06, "co2_mult": 1.04, "riesgo_mult": 1.25,
        "recomendacion": "Reprogramar despachos fuera de la ventana de obra y ajustar los tiempos comprometidos con el cliente.",
    },
    "paro_transportistas": {
        "nombre": "Paro nacional de transportistas", "icon": "fa-road-barrier", "scope": "modo", "modo": "Carretero",
        "descripcion": "Paro de transportistas (p. ej. contra la extorsión) paraliza la operación carretera del país.",
        "otif_retention": 0.25, "lt_mult": 1.75, "costo_mult": 1.30, "co2_mult": 1.10, "riesgo_mult": 2.10,
        "recomendacion": "Adelantar despachos antes del paro, migrar la carga crítica a cabotaje/aéreo y activar el comité de crisis.",
    },
    "crisis_social_sur": {
        "nombre": "Crisis social en el sur andino", "icon": "fa-people-group", "scope": "ciudades", "ciudades": SUR_ANDINO,
        "descripcion": "Bloqueos simultáneos en Puno, Cusco, Apurímac, Arequipa e Ica (como en enero de 2023).",
        "otif_retention": 0.30, "lt_mult": 1.80, "costo_mult": 1.32, "co2_mult": 1.12, "riesgo_mult": 2.00,
        "recomendacion": "Consolidar carga en el Callao y moverla por cabotaje a Matarani/Ilo, reprogramar el Corredor Minero Sur y proteger la carga de salud y alimentos.",
    },
    "nino_costero": {
        "nombre": "Fenómeno El Niño Costero", "icon": "fa-cloud-showers-water", "scope": "ciudades", "ciudades": NORTE_COSTERO,
        "descripcion": "Lluvias extremas en la costa norte: desbordes del río Piura e inundación de la Panamericana Norte.",
        "otif_retention": 0.40, "lt_mult": 1.55, "costo_mult": 1.25, "co2_mult": 1.15, "riesgo_mult": 1.75,
        "recomendacion": "Seguir los comunicados del ENFEN, pre-posicionar inventario en Trujillo y Chiclayo y reservar cabotaje Callao–Paita.",
    },
    "temporada_lluvias": {
        "nombre": "Temporada de lluvias (sierra y selva)", "icon": "fa-cloud-showers-heavy", "scope": "ciudades", "ciudades": SIERRA_SELVA,
        "descripcion": "Lluvias intensas de diciembre a marzo: huaicos, derrumbes y cierres en los Andes y la ceja de selva.",
        "otif_retention": 0.60, "lt_mult": 1.28, "costo_mult": 1.12, "co2_mult": 1.10, "riesgo_mult": 1.55,
        "recomendacion": "Monitorear avisos de SENAMHI e INDECI, reforzar el mantenimiento preventivo de la flota y ampliar los tiempos comprometidos.",
    },
    "vaciante_amazonia": {
        "nombre": "Vaciante de ríos amazónicos", "icon": "fa-arrow-down-wide-short", "scope": "modo", "modo": "Fluvial",
        "descripcion": "El estiaje del Marañón, Ucayali y Amazonas restringe el calado de los convoyes hacia Iquitos.",
        "otif_retention": 0.45, "lt_mult": 1.60, "costo_mult": 1.30, "co2_mult": 1.10, "riesgo_mult": 1.70,
        "recomendacion": "Aligerar carga a chatas de menor calado, adelantar el abastecimiento de Iquitos y mover la carga crítica por aire.",
    },
    "congestion_portuaria": {
        "nombre": "Congestión portuaria en el Callao", "icon": "fa-ship", "scope": "modo", "modo": "Marítimo",
        "descripcion": "Saturación de muelles y demoras en inspecciones (SUNAT, SENASA, DIGESA) en los terminales.",
        "otif_retention": 0.40, "lt_mult": 1.60, "costo_mult": 1.20, "co2_mult": 1.05, "riesgo_mult": 1.70,
        "recomendacion": "Anticipar la documentación aduanera, reservar citas de atraque con antelación y derivar contenedores a Chancay.",
    },
    "saturacion_aeroportuaria": {
        "nombre": "Saturación del Aeropuerto Jorge Chávez", "icon": "fa-plane-circle-exclamation", "scope": "modo", "modo": "Aéreo",
        "descripcion": "Saturación del terminal de carga (como en la transición a la nueva terminal): cancelaciones y retrasos.",
        "otif_retention": 0.45, "lt_mult": 1.50, "costo_mult": 1.25, "co2_mult": 1.02, "riesgo_mult": 1.65,
        "recomendacion": "Reasignar a vuelos de otras franjas, negociar cupo en bodega de pasajeros y avisar a los clientes de carga urgente.",
    },
    "pico_agroexportacion": {
        "nombre": "Pico de agroexportación", "icon": "fa-seedling", "scope": "sector", "sector": "Agroexportación",
        "descripcion": "Campaña alta de arándano, uva y palta: saturación de cámaras de frío, reefers y cupos navieros.",
        "otif_retention": 0.65, "lt_mult": 1.30, "costo_mult": 1.28, "co2_mult": 1.12, "riesgo_mult": 1.40,
        "recomendacion": "Asegurar contenedores reefer y cupo naviero con anticipación, ampliar turnos en cámaras de frío y priorizar clientes estratégicos.",
    },
    "temporada_alta": {
        "nombre": "Campaña de fin de año (Cyber Wow / Navidad)", "icon": "fa-gifts", "scope": "red",
        "descripcion": "Pico estacional de demanda en toda la red.",
        "otif_retention": 0.70, "lt_mult": 1.22, "costo_mult": 1.18, "co2_mult": 1.15, "riesgo_mult": 1.35,
        "recomendacion": "Ampliar la flota temporal, reforzar turnos en almacenes y priorizar por criticidad de cliente.",
    },
    "combustible_20": {
        "nombre": "Diésel +20%", "icon": "fa-gas-pump", "scope": "red",
        "descripcion": "Alza del 20% en el precio del diésel: impacto puramente económico.",
        "otif_retention": 1.00, "lt_mult": 1.00, "costo_mult": 1.09, "co2_mult": 1.00, "riesgo_mult": 1.00,
        "recomendacion": "Renegociar tarifas de flete, optimizar rutas largas y consolidar carga para diluir el sobrecosto.",
    },
    "chancay_hub": {
        "nombre": "Chancay como hub alterno del Callao", "icon": "fa-circle-nodes", "scope": "nodo_fijo", "nodo": "Callao",
        "descripcion": "Escenario de MEJORA: derivar parte de la carga contenedorizada del Callao al megapuerto de Chancay.",
        "otif_retention": 1.00, "otif_recovery": 0.25, "lt_mult": 0.93, "costo_mult": 0.97, "co2_mult": 0.95, "riesgo_mult": 0.85,
        "recomendacion": "Derivar a Chancay la carga con destino Asia y los picos del Callao: descongestiona la Av. Néstor Gambetta y recupera OTIF.",
    },
}


def get_options() -> dict:
    escenarios = []
    for key, e in ESCENARIOS.items():
        escenarios.append({
            "id": key, "nombre": e["nombre"], "icon": e["icon"], "descripcion": e["descripcion"],
            "scope": e["scope"], "requiere_objetivo": e.get("requiere_objetivo", False),
        })
    puertos = sorted([c for c, v in CITY_COORDS.items() if v["es_puerto"] or v["es_fluvial"]])
    nodos = sorted(CITY_COORDS.keys())
    corredores = [
        r[0] for r in Shipment.query.with_entities(Shipment.corredor_logistico)
        .group_by(Shipment.corredor_logistico)
        .having(func.count(Shipment.id) >= 20)
        .order_by(func.count(Shipment.id).desc()).limit(80).all()
    ]
    return {"escenarios": escenarios, "puertos": puertos, "nodos": nodos, "corredores": corredores}


def _aggregates(query):
    return query.with_entities(
        func.count(Shipment.id).label("n"),
        func.sum(Shipment.otif).label("otif_ok"),
        func.sum(Shipment.leadtime_real_dias).label("lt_sum"),
        func.sum(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo_sum"),
        func.sum(Shipment.consumo_combustible_galones).label("comb_sum"),
        func.sum(Shipment.prob_riesgo_incumplimiento).label("riesgo_sum"),
    ).first()


def _filtro_afectados(escenario: dict, objetivo: str | None):
    q = Shipment.query
    scope = escenario["scope"]
    if scope == "nodo":
        return q.filter((Shipment.ciudad_origen == objetivo) | (Shipment.ciudad_destino == objetivo))
    if scope == "corredor":
        return q.filter(Shipment.corredor_logistico == objetivo)
    if scope == "modo":
        return q.filter(Shipment.tipo_transporte == escenario["modo"])
    if scope == "ciudades":
        ciudades = escenario["ciudades"]
        return q.filter(Shipment.ciudad_origen.in_(ciudades) | Shipment.ciudad_destino.in_(ciudades))
    if scope == "sector":
        return q.filter(Shipment.sector_cliente == escenario["sector"])
    if scope == "nodo_fijo":
        nodo = escenario["nodo"]
        return q.filter((Shipment.ciudad_origen == nodo) | (Shipment.ciudad_destino == nodo))
    return q  # red completa


def simulate(escenario_id: str, objetivo: str | None = None) -> dict | None:
    escenario = ESCENARIOS.get(escenario_id)
    if not escenario:
        return None
    if escenario.get("requiere_objetivo") and not objetivo:
        return None

    total = _aggregates(Shipment.query)
    if not total or not total.n:
        return None
    afect_q = _filtro_afectados(escenario, objetivo)
    af = _aggregates(afect_q)
    if not af or not af.n:
        return None

    n = total.n
    # Línea base (red completa, datos históricos)
    base = {
        "otif_pct": round((total.otif_ok or 0) / n * 100, 1),
        "leadtime_dias": round((total.lt_sum or 0) / n, 2),
        "costo_total_pen": round(total.costo_sum or 0),
        "co2_ton": round((total.comb_sum or 0) * CO2_KG_POR_GALON / 1000, 1),
        "riesgo_pct": round((total.riesgo_sum or 0) / n, 1),
    }

    # Recalcular la red mezclando el subconjunto afectado (con factores) y el intacto.
    otif_sim_ok = (total.otif_ok - af.otif_ok) + af.otif_ok * escenario["otif_retention"]
    if escenario.get("otif_recovery"):  # escenario de mejora: recupera parte de los incumplimientos
        otif_sim_ok += (af.n - af.otif_ok) * escenario["otif_recovery"]
    lt_sim_sum = (total.lt_sum - af.lt_sum) + af.lt_sum * escenario["lt_mult"]
    costo_sim_sum = (total.costo_sum - af.costo_sum) + af.costo_sum * escenario["costo_mult"]
    comb_sim_sum = (total.comb_sum - af.comb_sum) + af.comb_sum * escenario["co2_mult"]
    riesgo_sim_sum = (total.riesgo_sum - af.riesgo_sum) + min(
        af.n * 100, af.riesgo_sum * escenario["riesgo_mult"]
    )

    sim = {
        "otif_pct": round(otif_sim_ok / n * 100, 1),
        "leadtime_dias": round(lt_sim_sum / n, 2),
        "costo_total_pen": round(costo_sim_sum),
        "co2_ton": round(comb_sim_sum * CO2_KG_POR_GALON / 1000, 1),
        "riesgo_pct": round(riesgo_sim_sum / n, 1),
    }

    deltas = {
        "otif_pts": round(sim["otif_pct"] - base["otif_pct"], 1),
        "leadtime_pct": round((sim["leadtime_dias"] / base["leadtime_dias"] - 1) * 100, 1) if base["leadtime_dias"] else 0,
        "costo_pct": round((sim["costo_total_pen"] / base["costo_total_pen"] - 1) * 100, 1) if base["costo_total_pen"] else 0,
        "co2_pct": round((sim["co2_ton"] / base["co2_ton"] - 1) * 100, 1) if base["co2_ton"] else 0,
        "riesgo_pts": round(sim["riesgo_pct"] - base["riesgo_pct"], 1),
        "sobrecosto_pen": round(sim["costo_total_pen"] - base["costo_total_pen"]),
    }

    extra = (
        afect_q.with_entities(
            func.count(func.distinct(Shipment.corredor_logistico)).label("corredores"),
            func.sum(case((Shipment.prioridad_cliente == "Crítica / Estratégico", 1), else_=0)).label("criticos"),
        ).first()
    )

    return {
        "escenario": {
            "id": escenario_id, "nombre": escenario["nombre"], "icon": escenario["icon"],
            "descripcion": escenario["descripcion"], "scope": escenario["scope"],
        },
        "objetivo": objetivo,
        "afectados": {
            "embarques": af.n,
            "pct_red": round(af.n / n * 100, 1),
            "corredores": extra.corredores or 0,
            "clientes_criticos": extra.criticos or 0,
        },
        "baseline": base,
        "simulado": sim,
        "deltas": deltas,
        "recomendacion": escenario["recomendacion"],
    }
