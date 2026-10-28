"""
Motor del Chat IA — Fase actual: intenciones basadas en reglas (patrones de palabras clave)
que consultan los servicios ya existentes (dashboard, monitoring, predictions, clients).

Preparado para conectar un LLM en una fase posterior: basta con reemplazar `answer()` por una
llamada a un proveedor (por ejemplo, usando estas mismas funciones de servicio como "tools" que
el modelo de lenguaje invoque), sin tocar la API ni el frontend.
"""
import re
import unicodedata

from sqlalchemy import case, func

from app.extensions import db
from app.models.alert import Alert
from app.models.shipment import Shipment
from app.services import client_service, dashboard_service
from app.services.geo_data import CITY_COORDS

ID_VIAJE_PATTERN = re.compile(r"RNS-\d{4}-\d{6}", re.IGNORECASE)


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _contains_any(text: str, *keywords) -> bool:
    return any(k in text for k in keywords)


def answer(message: str) -> dict:
    raw = message or ""
    text = _normalize(raw)

    id_match = ID_VIAJE_PATTERN.search(raw.upper())
    if id_match:
        return _answer_shipment_lookup(id_match.group(0))

    if _contains_any(text, "hola", "buenas", "buenos dias", "buenas tardes", "hey"):
        return _text("¡Hola! Soy el copiloto de RANSA. Puedo ayudarte con OTIF, Lead Time, "
                      "contingencias, la operación en vivo del gemelo digital, predicciones de riesgo, "
                      "clientes o el estado de un embarque (escribe su ID, ej. RNS-2025-000123). ¿Qué necesitas saber?")

    if _contains_any(text, "que puedes hacer", "ayuda", "opciones", "capacidades"):
        return _text(
            "Puedo responder sobre:\n"
            "• OTIF y Lead Time actuales\n"
            "• Contingencias y alertas críticas abiertas\n"
            "• Desempeño de los Modelos IA\n"
            "• Corredores logísticos con mayor riesgo\n"
            "• Segmentos de cliente (sector y prioridad)\n"
            "• Qué está pasando AHORA en el gemelo digital\n"
            "• Huaicos y lluvias, cadena de frío, Callao vs. Chancay\n"
            "• Estado de un embarque específico (dame su ID, ej. RNS-2025-000123)\n"
            "• La empresa: perfil público de RANSA, sus sedes y cada línea de negocio"
        )

    # --- Intents sobre la EMPRESA real (perfil público) y sus líneas de negocio ---
    linea = _find_linea(text)
    if linea:
        return _answer_linea(linea)

    if _contains_any(text, "linea de negocio", "lineas de negocio", "sedes", "colaboradores", "quien es ransa",
                     "que es ransa", "sobre ransa", "la empresa", "ceo", "accionista", "historia de ransa", "paises"):
        return _answer_empresa()

    # --- Intents de la operación EN VIVO (gemelo digital) ---
    if _contains_any(text, "ahora", "en vivo", "gemelo", "que esta pasando", "situacion actual", "en este momento"):
        return _answer_live()

    if _contains_any(text, "chancay") and not _contains_any(text, "cierro", "cerrar", "cierre"):
        return _answer_chancay()

    if _contains_any(text, "huaico", "lluvia", "senamhi", "derrumbe", "deslizamiento"):
        return _answer_categoria("geologico")

    if _contains_any(text, "cadena de frio", "reefer", "refrigerad", "agroexport", "arandano", "palta", "uva"):
        return _answer_cadena_frio()

    # --- Intents de DECISIÓN (Copilot) ---
    if _contains_any(text, "que pasa si", "que pasaria", "cerrar", "cierro", "cierre", "bloqueo de") and _find_city(raw):
        return _answer_cierre_nodo(_find_city(raw))

    if _contains_any(text, "monitorear", "vigilar", "atencion hoy", "prioridad hoy") and _contains_any(text, "corredor", "ruta", "hoy"):
        return _answer_corredor_monitorear()

    if _contains_any(text, "incumpl", "mayor probabilidad", "mas riesgo de incumplir", "embarques de riesgo", "embarques riesgosos"):
        return _answer_embarques_incumpliran()

    if _contains_any(text, "riesgo financiero", "mayor riesgo economico", "riesgo economico", "mas dinero", "mayor perdida"):
        return _answer_riesgo_financiero()

    if _contains_any(text, "emision", "co2", "huella de carbono", "reducir emisiones", "ambiental", "gnl", "gnv", "gas natural"):
        return _answer_emisiones()

    if _contains_any(text, "otif"):
        return _answer_otif()

    if _contains_any(text, "lead time", "tiempo de entrega", "tiempo promedio"):
        return _answer_leadtime()

    if _contains_any(text, "contingencia", "alerta critica", "alertas criticas", "riesgo alto"):
        return _answer_contingencias()

    if _contains_any(text, "prediccion", "modelo", "ia ", "inteligencia artificial", "auc", "precision"):
        return _answer_prediccion()

    if _contains_any(text, "corredor", "ruta mas riesgosa", "rutas riesgosas"):
        return _answer_corredores()

    if _contains_any(text, "cliente", "sector", "segmento"):
        return _answer_clientes()

    if _contains_any(text, "kpi", "indicador", "resumen", "dashboard"):
        return _answer_kpis()

    return _text(
        "No estoy seguro de haber entendido. Puedo ayudarte con OTIF, Lead Time, contingencias, "
        "predicciones de IA, corredores de riesgo, clientes, o el estado de un embarque "
        "(ej. RNS-2024-000123). ¿Puedes reformular tu pregunta?"
    )


LINEAS_CLAVE = {
    "Automotriz": ("automotriz", "ciguena", "vehiculos nuevos", "autos"),
    "Minería y Energía": ("mineria", "minero", "energia", "hidrocarburo", "liquidos", "concentrado"),
    "Comercio Exterior": ("comercio exterior", "aduana", "deposito temporal", "importacion", "exportacion"),
    "Logística de Frío": ("logistica de frio", "linea de frio"),
    "Distribución": ("distribucion", "consumo masivo", "retail"),
}


def _find_linea(text: str):
    for linea, claves in LINEAS_CLAVE.items():
        if _contains_any(text, *claves):
            return linea
    return None


def _answer_empresa():
    from app.services import ransa_profile as rp
    escala = " · ".join(f"{c['texto']} {c['etiqueta']}" for c in rp.CIFRAS[1:4])
    lider = rp.LIDERAZGO[0]
    fuente = rp.FUENTES[lider["fuente"]]
    return _text(
        f"**RANSA** (perfil público): {rp.PROPIEDAD}\n"
        f"• Escala del grupo: {escala}.\n"
        "• En el Perú: +3 M m² de almacenamiento, +98 mil posiciones y +20 mil posiciones de frío.\n"
        f"• Líneas de negocio: {', '.join(x['id'] for x in rp.LINEAS)}.\n"
        f"• Sedes marcadas en el gemelo: {', '.join(rp.SEDES)}.\n"
        f"• CEO del grupo: {lider['nombre']} (según {fuente['medio']}, {fuente['fecha']}).\n"
        "Fuentes y fechas en **Resumen RANSA**. La operación que ves en la plataforma es simulada."
    )


def _answer_linea(linea: str):
    from app.services import ransa_profile as rp
    datos = next((x for x in dashboard_service.get_lineas() if x["linea"] == linea), None)
    perfil = next((x for x in rp.LINEAS if x["id"] == linea), None)
    if not datos or not perfil:
        return _text(f"No encontré embarques de la línea {linea}.")
    return _text(
        f"**{linea}** — {perfil['resumen']}\n"
        f"• {datos['participacion_pct']:.1f} % de los embarques simulados ({_n(datos['embarques'])}), "
        f"OTIF {datos['otif_pct']:.1f} %, Lead Time {datos['lead_time_dias']:.2f} días.\n"
        f"• Riesgo IA promedio {datos['riesgo_promedio_pct']:.1f} % · {datos['co2_t']:,.0f} t de CO₂.\n"
        f"• Dato público: {perfil['dato']}\n"
        "Filtra esta línea en **Resumen RANSA** para ver su tendencia y corredores."
    )


def _n(x) -> str:
    """Entero con separador de miles (formato peruano: 30,000)."""
    return f"{round(x or 0):,}"


def _text(respuesta: str, tipo: str = "texto", datos=None) -> dict:
    return {"respuesta": respuesta, "tipo": tipo, "datos": datos}


def _answer_otif():
    k = dashboard_service.get_kpis()
    return _text(
        f"El OTIF actual es de **{k['otif_pct']}%** sobre {k['total_embarques']:,} embarques "
        f"(fill rate {k['fill_rate_pct']}%). Nivel de servicio compuesto: {k['nivel_servicio_pct']}%."
    )


def _answer_leadtime():
    k = dashboard_service.get_kpis()
    return _text(f"El Lead Time promedio actual es de **{k['lead_time_promedio_dias']} días**, sobre {k['total_embarques']:,} embarques.")


def _answer_contingencias():
    abiertas = Alert.query.filter_by(estado="Abierta").order_by(Alert.probabilidad_pct.desc()).limit(5).all()
    total = Alert.query.filter_by(estado="Abierta").count()
    if not total:
        return _text("No hay contingencias ni alertas críticas abiertas en este momento.")
    detalle = "\n".join(f"• {a.titulo} ({a.probabilidad_pct}%)" for a in abiertas)
    return _text(f"Hay **{total} alertas críticas abiertas**. Las de mayor probabilidad:\n{detalle}", tipo="lista")


def _answer_prediccion():
    from app.models.ml_model import MLModelRun
    run = MLModelRun.query.filter_by(activo=True).order_by(MLModelRun.creado_en.desc()).first()
    if not run:
        return _text("Aún no se ha entrenado ningún modelo de IA. Ve a Modelos IA para entrenarlo.")
    return _text(
        f"El modelo activo es **{run.algoritmo}** (versión {run.version}), entrenado con "
        f"{run.n_muestras_entrenamiento:,} embarques. Métricas sobre el conjunto de prueba: "
        f"AUC {run.auc}, Accuracy {run.accuracy}, Recall {run.recall}, Precision {run.precision_}, F1 {run.f1_score}."
    )


def _answer_corredores():
    corredores = dashboard_service.get_top_corredores_riesgo(limit=5)
    if not corredores:
        return _text("No hay suficientes datos para calcular corredores de riesgo.")
    detalle = "\n".join(f"• {c['corredor']}: riesgo {c['riesgo_promedio_pct']}%, OTIF {c['otif_pct']}%" for c in corredores)
    return _text(f"Los corredores con mayor riesgo actualmente son:\n{detalle}", tipo="lista")


def _answer_clientes():
    sectores = client_service.get_sector_summary()[:5]
    detalle = "\n".join(f"• {s['sector_cliente']}: {s['total_embarques']:,} embarques, OTIF {s['otif_pct']}%" for s in sectores)
    return _text(f"Resumen por sector de cliente:\n{detalle}", tipo="lista")


def _answer_kpis():
    k = dashboard_service.get_kpis()
    return _text(
        f"Resumen ejecutivo:\n"
        f"• Embarques: {k['total_embarques']:,}\n"
        f"• OTIF: {k['otif_pct']}%\n"
        f"• Lead Time: {k['lead_time_promedio_dias']} días\n"
        f"• Costo total: S/ {k['costo_total_pen']:,.0f}\n"
        f"• CO₂ estimado: {k['co2_toneladas']:,.1f} ton\n"
        f"• Contingencias activas: {k['contingencias_activas']:,}",
        tipo="lista",
    )


def _find_city(raw_text: str):
    t = _normalize(raw_text)
    for city in CITY_COORDS:
        if _normalize(city) in t:
            return city
    return None


def _answer_cierre_nodo(city: str):
    """What-if: impacto de cerrar/bloquear un nodo, sobre los datos históricos (simulados)."""
    row = (
        Shipment.query.with_entities(
            func.count(Shipment.id).label("total"),
            func.avg(Shipment.otif).label("otif"),
            func.sum(Shipment.costo_transporte_pen + Shipment.costo_peajes_pen).label("costo"),
            func.sum(case((Shipment.prioridad_cliente == "Crítica / Estratégico", 1), else_=0)).label("criticos"),
            func.count(func.distinct(Shipment.corredor_logistico)).label("corredores"),
        )
        .filter((Shipment.ciudad_origen == city) | (Shipment.ciudad_destino == city))
        .first()
    )
    if not row or not row.total:
        return _text(f"No tengo embarques históricos asociados a **{city}** para estimar el impacto.")
    costo_riesgo = round((row.costo or 0) * 0.02)
    return _text(
        f"**Escenario what-if: cerrar {city}.**\n"
        f"• Operaciones expuestas: {row.total:,} embarques históricos pasan por este nodo.\n"
        f"• Corredores afectados: {row.corredores}.\n"
        f"• Clientes críticos/estratégicos comprometidos: {row.criticos:,}.\n"
        f"• Costo en riesgo estimado (ventana): S/ {costo_riesgo:,.0f}.\n"
        f"• OTIF histórico del nodo: {round((row.otif or 0)*100,1)}%.\n"
        f"Recomendación: activar corredores alternos y priorizar la carga crítica antes del cierre. "
        f"Puedes modelarlo en detalle en el Simulador de escenarios.",
        tipo="lista",
    )


def _answer_corredor_monitorear():
    scores = None
    try:
        from app.services import predictive_service
        scores = predictive_service.get_category_network_scores()
    except Exception:
        scores = None
    if scores:
        top = max(scores.values(), key=lambda d: d["probabilidad_24h_top"])
        if top["top_corredores"]:
            c = top["top_corredores"][0]
            return _text(
                f"El corredor a monitorear hoy es **{c['corredor']}**: es el de mayor probabilidad "
                f"de {top['label'].lower()} en las próximas 24h ({c['probabilidad_pct']}%), con "
                f"{c['clientes_criticos']} clientes críticos expuestos. Revisa el detalle en Riesgo 24–48 h."
            )
    corredores = dashboard_service.get_top_corredores_riesgo(limit=1)
    if corredores:
        c = corredores[0]
        return _text(f"El corredor a vigilar es **{c['corredor']}** (riesgo {c['riesgo_promedio_pct']}%, OTIF {c['otif_pct']}%).")
    return _text("No hay datos suficientes para recomendar un corredor a monitorear.")


def _answer_embarques_incumpliran():
    rows = (
        Shipment.query
        .filter(Shipment.prob_riesgo_incumplimiento.isnot(None))
        .order_by(Shipment.prob_riesgo_incumplimiento.desc())
        .limit(5).all()
    )
    if not rows:
        return _text("Aún no hay predicciones de riesgo. Entrena el modelo en Modelos IA.")
    detalle = "\n".join(
        f"• {s.id_viaje} ({s.corredor_logistico}): {round(s.prob_riesgo_incumplimiento,1)}% de riesgo" for s in rows
    )
    return _text(f"Los embarques con mayor probabilidad de incumplir OTIF:\n{detalle}", tipo="lista")


def _answer_riesgo_financiero():
    row = (
        Shipment.query.with_entities(
            Shipment.corredor_logistico,
            func.sum((Shipment.costo_transporte_pen + Shipment.costo_peajes_pen) * Shipment.prob_riesgo_incumplimiento / 100).label("exposicion"),
            func.count(Shipment.id).label("total"),
        )
        .filter(Shipment.prob_riesgo_incumplimiento.isnot(None))
        .group_by(Shipment.corredor_logistico)
        .order_by(func.sum((Shipment.costo_transporte_pen + Shipment.costo_peajes_pen) * Shipment.prob_riesgo_incumplimiento / 100).desc())
        .first()
    )
    if not row:
        return _text("No hay datos suficientes para estimar el riesgo financiero.")
    return _text(
        f"El mayor riesgo financiero está en el corredor **{row.corredor_logistico}**: "
        f"exposición estimada de S/ {round(row.exposicion or 0):,.0f} "
        f"(costo × probabilidad de incumplimiento sobre {row.total:,} embarques)."
    )


def _answer_emisiones():
    k = dashboard_service.get_kpis()
    co2_txt = f"{k['co2_toneladas']:,.0f}"
    return _text(
        f"La huella estimada de la operación simulada es de **{co2_txt} t de CO₂** (consumo × factor de emisión de "
        f"cada combustible). Los {_n(k['viajes_gnl_gnv'])} viajes en unidades a GNL/GNV ya evitaron "
        f"**{k['co2_evitado_t']:,.0f} t** frente al diésel; RANSA renovó en el Perú 11 tractos y 27 camiones a GNL "
        f"(hasta −25 % de CO₂, ProActivo nov-2025) dentro de su plan de descarbonización 2030.\n"
        f"Para reducir más: consolidar carga (fill rate {k['fill_rate_pct']} %), usar cabotaje en corredores costeros "
        f"largos (Callao–Paita, Callao–Matarani) y optimizar las rutas de mayor pendiente. El Simulador estima cada medida."
    )


def _answer_shipment_lookup(id_viaje: str):
    s = Shipment.query.filter_by(id_viaje=id_viaje.upper()).first()
    if not s:
        return _text(f"No encontré ningún embarque con ID **{id_viaje.upper()}**.")
    otif_txt = "cumplió" if s.otif else "incumplió"
    riesgo_txt = f", riesgo estimado {s.prob_riesgo_incumplimiento}% ({s.nivel_riesgo})" if s.prob_riesgo_incumplimiento is not None else ""
    return _text(
        f"**{s.id_viaje}** — {s.ciudad_origen} → {s.ciudad_destino} ({s.corredor_logistico}), "
        f"transporte {s.tipo_transporte}, prioridad {s.prioridad_cliente}. "
        f"Lead Time real: {s.leadtime_real_dias} días, {otif_txt} OTIF{riesgo_txt}."
    )


def _answer_live():
    """Resumen de la operación en vivo del gemelo digital (motor en memoria)."""
    try:
        from app.services.live_engine import get_engine
        snap = get_engine().snapshot(10 ** 9)
    except Exception:
        return _text("El gemelo digital no está disponible en este momento.")
    k = snap["kpis"]
    eventos = snap["events"]
    lineas = [
        f"**Operación en vivo** (hora simulada {snap['sim_time'][11:16]}): {k['operaciones_activas']} unidades activas, "
        f"OTIF proyectado {k['otif_proyectado_pct']}%, {k['desvios_activos']} desvíos activos y "
        f"S/ {_n(k['carga_en_riesgo_pen'])} de carga con riesgo de llegar tarde.",
    ]
    if eventos:
        lineas.append("Eventos activos:")
        for e in eventos[:5]:
            rec = next((o for o in e["opciones"] if o["id"] == e["recomendada"]), None)
            estado = f"decisión aplicada: {e['decision']['nombre']}" if e["decision"] else (
                f"la IA recomienda «{rec['nombre']}»" if rec else "sin unidades afectadas")
            lineas.append(f"• {e['titulo']} en {e['lugar']} — {e['afectados']} unidades; {estado}.")
    else:
        lineas.append("No hay eventos activos en la red: la operación fluye con normalidad.")
    lineas.append("Abre la Torre de Control / Gemelo Digital para verlo en el mapa y aplicar decisiones.")
    return _text("\n".join(lineas), tipo="lista")


def _answer_chancay():
    def stats(nodo):
        return (
            Shipment.query.with_entities(
                func.count(Shipment.id), func.avg(Shipment.otif), func.avg(Shipment.leadtime_real_dias),
                func.avg(Shipment.tiempo_espera_horas),
            ).filter((Shipment.ciudad_origen == nodo) | (Shipment.ciudad_destino == nodo)).first()
        )
    ca, ch = stats("Callao"), stats("Chancay")
    if not ch or not ch[0]:
        return _text("Aún no hay embarques registrados por el Puerto de Chancay.")
    return _text(
        f"**Callao vs. Chancay** (desde el inicio de operaciones de Chancay, nov-2024):\n"
        f"• Callao: {_n(ca[0])} embarques, OTIF {round((ca[1] or 0) * 100, 1)}%, espera promedio {round(ca[3] or 0, 1)} h.\n"
        f"• Chancay: {_n(ch[0])} embarques, OTIF {round((ch[1] or 0) * 100, 1)}%, espera promedio {round(ch[3] or 0, 1)} h.\n"
        f"Chancay funciona como hub alterno ante oleajes o congestión del Callao: en el Simulador de red puedes "
        f"evaluar el escenario «Chancay como hub alterno del Callao».",
        tipo="lista",
    )


def _answer_categoria(categoria: str):
    from app.services import predictive_service
    scores = predictive_service.get_category_network_scores()
    data = scores.get(categoria)
    if not data or not data["top_corredores"]:
        return _text("No hay datos suficientes para estimar ese riesgo.")
    top = data["top_corredores"]
    detalle = "\n".join(f"• {c['corredor']}: {c['probabilidad_pct']}% a 24h" for c in top)
    return _text(
        f"Corredores más expuestos a **{data['label'].lower()}**:\n{detalle}\n"
        f"Probabilidad estimada a 48h en el corredor más expuesto: {data['probabilidad_48h_estimada']}%. "
        f"Recomendación: revisar avisos de SENAMHI y el estado de tránsito de Provías antes de despachar, y pre-asignar "
        f"la ruta alterna (p. ej. Cañete–Lunahuaná para la Carretera Central).",
        tipo="lista",
    )


def _answer_cadena_frio():
    frio = ["Alimentos refrigerados", "Agroexportación perecible (cadena de frío)", "Farmacéutica (cadena de frío)",
            "Pesca y congelados"]
    rows = (
        Shipment.query.with_entities(Shipment.tipo_carga, func.count(Shipment.id), func.avg(Shipment.otif),
                                     func.sum(Shipment.siniestro))
        .filter(Shipment.tipo_carga.in_(frio)).group_by(Shipment.tipo_carga).all()
    )
    if not rows:
        return _text("No hay embarques de cadena de frío registrados.")
    detalle = "\n".join(f"• {r[0]}: {_n(r[1])} embarques, OTIF {round((r[2] or 0) * 100, 1)}%, {int(r[3] or 0)} siniestros"
                        for r in rows)
    return _text(
        f"**Cadena de frío** (agroexportación, farma, refrigerados y congelados):\n{detalle}\n"
        f"En el gemelo digital, cada unidad refrigerada reporta su temperatura en tiempo real; si el equipo de frío "
        f"falla, la IA sugiere transbordo en el CD más cercano antes de superar los 8 °C.",
        tipo="lista",
    )
