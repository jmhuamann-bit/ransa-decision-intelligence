"""
AI Decision Assistant — Módulo 3 (Strategic Forecast, horizonte 48 horas).

Es un MOTOR EXPERTO BASADO EN REGLAS, no un LLM: determinístico, sin costo por uso,
sin API key ni dependencia de conectividad externa, y cada recomendación es trazable a
una plantilla explícita (fácil de auditar y explicar ante un directivo). Para cada
categoría de riesgo, combina el panorama de red calculado en predictive_service.py con
una plantilla de explicación/justificación/recomendación/acciones escrita por un
analista logístico, y devuelve un "escenario" completo: probabilidad, impacto,
explicación, justificación, recomendación, acciones propuestas, impacto económico y
prioridad -- exactamente el patrón Evento → Probabilidad → Impacto → Acción pedido por
negocio.
"""
from app.services import predictive_service

RULES = {
    "geologico": {
        "escenario": "Riesgo de huaico / derrumbe",
        "explicacion": "Los corredores que cruzan los Andes y la ceja de selva (Carretera Central, Interoceánica, IIRSA Norte) concentran huaicos y derrumbes, sobre todo entre diciembre y marzo.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos en los corredores más expuestos; el corredor {top_corredor} concentra la mayor frecuencia de huaicos y derrumbes, con una probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Preparar el desvío por la ruta alterna (p. ej. Cañete–Lunahuaná o Canta–Huayllay para la Carretera Central) y adelantar el despacho de la carga crítica antes de la ventana de lluvias.",
        "acciones": [
            "Revisar el estado de tránsito de Provías Nacional / SUTRAN y los avisos de SENAMHI antes de cada despacho.",
            "Pre-asignar la ruta alterna y avisar a los conductores en tránsito (GPS y radio).",
            "Priorizar la carga crítica (salud, cadena de frío) en la ventana de menor riesgo.",
            "Coordinar con el COE / INDECI regional los puntos de espera seguros ante un cierre.",
        ],
    },
    "hidrologico": {
        "escenario": "Riesgo de inundación / desborde",
        "explicacion": "En la costa norte (Piura, Lambayeque, Tumbes) las lluvias del verano y los eventos El Niño Costero desbordan ríos e inundan la Panamericana; en la Amazonía la vaciante restringe la navegación.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos; el corredor {top_corredor} presenta el mayor índice de inundaciones, con probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Monitorear los comunicados del ENFEN y los avisos de SENAMHI, y preparar el trasbordo a cabotaje (Callao–Paita) si la Panamericana Norte se corta.",
        "acciones": [
            "Consultar el aviso meteorológico vigente de SENAMHI y el comunicado ENFEN antes de despachar.",
            "Identificar almacenes de contingencia en Trujillo y Chiclayo para retener carga.",
            "Evaluar cupo de cabotaje Callao–Paita para la carga crítica del norte.",
            "Informar a los clientes de agroexportación sobre el riesgo para sus ventanas de embarque.",
        ],
    },
    "social": {
        "escenario": "Posible paro / bloqueo de vías",
        "explicacion": "La conflictividad social (paros regionales, bloqueos comunales en el Corredor Minero Sur, paros de transportistas por extorsión) es una de las principales causas de incumplimiento en el sur andino.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos; el corredor {top_corredor} concentra la mayor incidencia de bloqueos, con probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Anticipar los despachos programados, activar el comité de crisis y evaluar rutas o modos alternos (cabotaje Callao–Matarani) para los clientes con mayor exposición.",
        "acciones": [
            "Revisar el reporte de conflictos sociales de la Defensoría del Pueblo y las alertas de la PNP.",
            "Adelantar los despachos de los próximos 2 días en los corredores expuestos.",
            "Contactar proactivamente a los clientes críticos/estratégicos y acordar nuevas ventanas.",
            "Definir puntos de pernocte seguros y protocolo de comunicación con los conductores.",
        ],
    },
    "infraestructura": {
        "escenario": "Deterioro vial / cierre de infraestructura",
        "explicacion": "Los tramos de sierra y selva con mayor deterioro (y las obras activas en accesos a Lima) elevan la probabilidad de cierres parciales y averías.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos; el corredor {top_corredor} presenta el mayor índice de deterioro/bloqueos, con probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Reforzar el mantenimiento preventivo de la flota asignada (frenos, neumáticos) y ajustar los tiempos comprometidos en los tramos con obras.",
        "acciones": [
            "Programar revisión de frenos y neumáticos de las unidades que suben a la sierra.",
            "Consultar el plan de obras y los cierres programados de Provías Nacional / concesionarias.",
            "Ajustar el tiempo de tránsito comunicado al cliente en tramos con obras.",
            "Evitar las restricciones horarias de carga pesada en Lima (vías expresas y accesos al Callao).",
        ],
    },
    "seguridad": {
        "escenario": "Robo de carga / extorsión al transporte",
        "explicacion": "Los accesos a Lima y Callao y la costa norte (Trujillo, Chiclayo, Piura) registran los índices de seguridad más bajos de la red, con extorsión creciente al transporte desde 2024.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos; el corredor {top_corredor} presenta el menor índice de seguridad de la red, con probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Activar el protocolo de seguridad para la carga de mayor valor: custodia, convoyes, horarios diurnos y monitoreo GPS con botón de pánico.",
        "acciones": [
            "Asignar custodia o convoy a la carga de mayor valor asegurado.",
            "Restringir el tránsito nocturno y las paradas no autorizadas en tramos críticos.",
            "Coordinar con la PNP (División de Protección de Carreteras) el acompañamiento en zonas de riesgo.",
            "Verificar coberturas de la póliza de transporte para los envíos expuestos.",
        ],
    },
    "accidentalidad": {
        "escenario": "Accidentalidad vial elevada",
        "explicacion": "Las curvas y pendientes de los pasos andinos (Ticlio, Abra Anticona), la neblina costera (Pasamayo) y los tramos largos de la Panamericana Sur concentran la accidentalidad.",
        "justificacion_tpl": "Se analizaron {muestras:,} viajes históricos; el corredor {top_corredor} concentra la mayor tasa de accidentalidad, con probabilidad estimada a 24h de {prob24}%.",
        "recomendacion": "Reforzar las políticas de descanso (jornada de conducción SUTRAN) y de velocidad, con doble conductor en las rutas de más de 12 horas.",
        "acciones": [
            "Verificar el cumplimiento de las pausas de conducción y el registro de jornada.",
            "Asignar doble conductor en rutas largas (Lima–Cusco, Lima–Tacna, Lima–Pucallpa).",
            "Revisar frenos, luces y neumáticos antes de cruzar los pasos de alta montaña.",
            "Limitar la velocidad en tramos con neblina o curvas críticas mediante telemetría.",
        ],
    },
}


NIVELES = ["Bajo", "Medio", "Alto", "Muy Alto"]
UMBRAL_CLIENTES_CRITICOS = 200  # clientes críticos expuestos en los 3 corredores más afectados


def _prioridad(prob_48h: float, clientes_criticos: int) -> str:
    idx = 2 if prob_48h >= 85 else 1 if prob_48h >= 60 else 0
    if clientes_criticos >= UMBRAL_CLIENTES_CRITICOS:
        idx = min(2, idx + 1)
    return ["Baja", "Media", "Alta"][idx]


def _impacto_nivel(prob_48h: float, clientes_criticos: int) -> str:
    idx = 3 if prob_48h >= 90 else 2 if prob_48h >= 75 else 1 if prob_48h >= 55 else 0
    if clientes_criticos >= UMBRAL_CLIENTES_CRITICOS:
        idx = min(3, idx + 1)
    return NIVELES[idx]


def get_scenarios_48h() -> list:
    resumen = predictive_service.get_category_network_scores()
    escenarios = []
    letras = "ABCDEF"
    for i, (categoria, data) in enumerate(sorted(resumen.items(), key=lambda kv: kv[1]["probabilidad_48h_estimada"], reverse=True)):
        if not data["top_corredores"]:
            continue
        regla = RULES[categoria]
        top_corredor = data["top_corredores"][0]["corredor"]
        # Probabilidad, impacto y prioridad salen de los datos (no se fijan por ranking).
        prob48 = data["probabilidad_48h_estimada"]
        clientes_criticos = data["clientes_criticos_totales"]
        justificacion = regla["justificacion_tpl"].format(
            muestras=data["muestras_totales"], top_corredor=top_corredor, prob24=data["probabilidad_24h_top"],
        )
        est = data.get("estacionalidad")
        if est:
            nivel = ("muy por encima" if est["factor_bruto"] >= 1.15 else "por encima" if est["factor_bruto"] >= 1.03 else
                     "en línea con" if est["factor_bruto"] >= 0.92 else "por debajo de" if est["factor_bruto"] >= 0.7 else
                     "muy por debajo de")
            justificacion += (f" Estacionalidad: en {est['mes'].lower()} la intensidad histórica de este riesgo está {nivel} "
                              f"su promedio anual (factor {est['factor_bruto']}).")
        escenarios.append({
            "id": f"escenario_{categoria}",
            "letra": letras[i] if i < len(letras) else str(i + 1),
            "categoria": categoria,
            "titulo": regla["escenario"],
            "icon": data["icon"],
            "color": data["color"],
            "probabilidad_48h_pct": prob48,
            "impacto_nivel": _impacto_nivel(prob48, clientes_criticos),
            "prioridad": _prioridad(prob48, clientes_criticos),
            "explicacion": regla["explicacion"],
            "justificacion": justificacion,
            "recomendacion": regla["recomendacion"],
            "acciones_propuestas": regla["acciones"],
            "impacto_economico_estimado_pen": data["costo_en_riesgo_pen"],
            "clientes_criticos_expuestos": clientes_criticos,
            "corredores_probables": [c["corredor"] for c in data["top_corredores"]],
            "corredor_principal": top_corredor,
            "estacionalidad": est,
        })
    escenarios.sort(key=lambda e: e["probabilidad_48h_pct"], reverse=True)
    for i, e in enumerate(escenarios):
        e["letra"] = letras[i] if i < len(letras) else str(i + 1)
    return escenarios
