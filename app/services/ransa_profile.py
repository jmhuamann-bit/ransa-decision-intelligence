"""
Perfil PÚBLICO de RANSA que ancla la plataforma a la empresa real.

Todo lo de este módulo proviene de prensa y comunicados públicos (cada dato lleva su fuente y fecha).
La operación que muestra la plataforma —embarques, flota en vivo, eventos y decisiones— sigue siendo
SIMULADA: estos datos solo dan escala, geografía y mezcla de negocio realistas. Los cargos directivos
son los publicados en la fecha indicada y pueden haber cambiado.
"""

FUENTES = {
    "gestion_2026": {
        "medio": "Gestión", "fecha": "30-jun-2026",
        "titulo": "Ransa mueve el tablero en Perú: invierte US$ 12 millones y analiza salto al sector salud",
        "url": "https://gestion.pe/economia/empresas/ransa-mueve-el-tablero-en-peru-invierte-us-12-millones-y-analiza-salto-al-sector-salud-noticia/",
    },
    "gestion_2023": {
        "medio": "Gestión", "fecha": "03-abr-2023",
        "titulo": "Ransa contempla ir al cabotaje y sumar oferta logística en puerto de Chancay",
        "url": "https://gestion.pe/economia/empresas/ransa-contempla-ir-al-cabotaje-y-sumar-oferta-logistica-en-puerto-de-chancay-almacenes-logistica-operadores-bodegas-noticia/",
    },
    "forbes_2023": {
        "medio": "Forbes Perú", "fecha": "13-jul-2023",
        "titulo": "CEO de Ransa: TCF pasará a formar parte del portafolio de negocios del grupo",
        "url": "https://forbes.pe/negocios/2023-07-13/ceo-de-ransa-tcf-pasara-a-formar-parte-del-portafolio-de-negocios-del-grupo/",
    },
    "proactivo_2025": {
        "medio": "ProActivo", "fecha": "13-nov-2025",
        "titulo": "Ransa avanza hacia la descarbonización regional con la medición de su huella de carbono en 10 países",
        "url": "https://proactivo.com.pe/ransa-avanza-hacia-la-descarbonizacion-regional-con-la-medicion-de-su-huella-de-carbono-en-10-paises/",
    },
    "proactivo_2021": {
        "medio": "ProActivo", "fecha": "08-ene-2021",
        "titulo": "Ransa invierte en flota eficiente y ecoamigable para la logística de CBC Perú",
        "url": "https://proactivo.com.pe/ransa-invierte-23-millones-en-flota-de-ultima-gama-eficiente-y-ecoamigable-para-la-logistica-de-cbc-peru/",
    },
    "agraria_2025": {
        "medio": "Agraria.pe", "fecha": "02-oct-2025",
        "titulo": "Gestión logística eficiente impulsa la internacionalización",
        "url": "https://agraria.pe/noticias/gestion-logistica-eficiente-impulsa-la-internacionalizacion--40895",
    },
    "hig_2021": {
        "medio": "H.I.G. Capital", "fecha": "29-oct-2021",
        "titulo": "H.I.G. Capital Completes Strategic Investment in Grupo Ransa",
        "url": "https://hig.com/news/h-i-g-capital-completes-strategic-investment-in-grupo-ransa/",
    },
    "peruretail_frio": {
        "medio": "Peru Retail", "fecha": "abr-2022",
        "titulo": "Ransa proyecta crecer a doble dígito en su servicio de Logística de Frío",
        "url": "https://www.peru-retail.com/ransa-proyecta-crecer-a-doble-digito-en-su-servicio-de-logistica-de-frio/",
    },
    "peruretail_chiclayo": {
        "medio": "Peru Retail", "fecha": "s. f.",
        "titulo": "Ransa: centro de distribución en Chiclayo",
        "url": "https://www.peru-retail.com/ransa-centro-distribucion-chiclayo/",
    },
    "peruretail_callao": {
        "medio": "Peru Retail", "fecha": "2023",
        "titulo": "Ransa inaugura dos nuevos almacenes industriales en el Callao",
        "url": "https://www.peru-retail.com/ransa-inaugura-dos-nuevos-almacenes-industriales-en-el-callao-con-inversion-millonaria/",
    },
    "agraria_torreblanca": {
        "medio": "Agraria.pe", "fecha": "06-sep-2018",
        "titulo": "Torre Blanca inicia operaciones en su línea de empaque (planta de Chancay, Huaral)",
        "url": "https://agraria.pe/noticias/torre-blanca-inicia-operaciones-en-su-linea-de-empaque-para--17391",
    },
}

# Cifras de escala (públicas). "alcance" distingue el grupo regional de la operación en el Perú.
CIFRAS = [
    {"valor": 80, "texto": "+80 años", "etiqueta": "de trayectoria logística", "alcance": "Grupo", "fuente": "hig_2021"},
    {"valor": 12, "texto": "12", "etiqueta": "países, de México a Chile", "alcance": "Grupo", "fuente": "gestion_2026"},
    {"valor": 9000, "texto": "+9,000", "etiqueta": "colaboradores", "alcance": "Grupo", "fuente": "gestion_2026"},
    {"valor": 13, "texto": "13", "etiqueta": "ciudades con operación en el Perú", "alcance": "Perú", "fuente": "gestion_2026"},
    {"valor": 3, "texto": "+3 M m²", "etiqueta": "de áreas de almacenamiento", "alcance": "Perú", "fuente": "gestion_2023"},
    {"valor": 98000, "texto": "+98 mil", "etiqueta": "posiciones de almacén", "alcance": "Perú", "fuente": "gestion_2023"},
    {"valor": 20000, "texto": "+20 mil", "etiqueta": "posiciones de frío", "alcance": "Perú", "fuente": "peruretail_frio"},
]

PROPIEDAD = ("Operador logístico de origen peruano. Desde 2021 su accionista mayoritario es el fondo H.I.G. Capital; "
             "el Grupo Romero se mantiene como socio minoritario. En 2023 se fusionó con TCF (Centroamérica) y en "
             "2024 adquirió Loginsa (Chile).")

# Equipo directivo citado en prensa (cargo a la fecha de la fuente).
LIDERAZGO = [
    {"nombre": "Paolo Sacchi", "cargo": "CEO del Grupo Ransa", "fuente": "gestion_2026"},
    {"nombre": "Roberto Figari", "cargo": "Vicepresidente de Ransa Perú", "fuente": "gestion_2023"},
    {"nombre": "Sofía Torreli", "cargo": "Gerente de Negocios de Comercio Exterior", "fuente": "agraria_2025"},
    {"nombre": "Alexander Pamplona", "cargo": "Gerente corporativo de HSE y Sostenibilidad", "fuente": "proactivo_2025"},
]

# Líneas de negocio: la columna Línea_Negocio del dataset usa exactamente estos nombres.
LINEAS = [
    {"id": "Distribución", "icon": "fa-boxes-stacked", "color": "#ff7a1a",
     "resumen": "Consumo masivo y retail moderno en Lima, Callao y provincias.",
     "dato": "Flota Euro V dedicada a la distribución de CBC Perú en Lima y Callao (50 camiones, −22 % CO₂).",
     "fuente": "proactivo_2021"},
    {"id": "Comercio Exterior", "icon": "fa-ship", "color": "#3d63ff",
     "resumen": "Agenciamiento de aduanas, depósito temporal y transporte de contenedores (Callao, Chancay, Paita).",
     "dato": "Depósitos temporales con tomas para reefers y transporte con generadores para el agro.",
     "fuente": "agraria_2025"},
    {"id": "Logística de Frío", "icon": "fa-snowflake", "color": "#0ea5e9",
     "resumen": "Red de frío integrada en Lima, Callao, Chiclayo, Trujillo, Arequipa, Piura, Huancayo y Cusco.",
     "dato": "Consumo masivo aporta ~50 % y agroexportación ~20 % de la facturación de frío.",
     "fuente": "peruretail_frio"},
    {"id": "Minería y Energía", "icon": "fa-helmet-safety", "color": "#a16207",
     "resumen": "Segmento extractivo: concentrado, insumos MATPEL, repuestos y distribución de líquidos.",
     "dato": "11 tractos y 27 camiones a GNL en el Perú (hasta −25 % CO₂); +US$ 60 M en contratos regionales de energía y minería en 2025.",
     "fuente": "proactivo_2025"},
    {"id": "Automotriz", "icon": "fa-car-side", "color": "#8b5cf6",
     "resumen": "SLA: importación y alistamiento de vehículos; cigüeñas desde el puerto de Chancay hacia Lima.",
     "dato": "La inversión 2026 en el Perú incluye cigüeñas para el puerto de Chancay.",
     "fuente": "gestion_2026"},
]

# Sedes y activos públicos de RANSA asociados a los nodos de la red del gemelo digital.
SEDES = {
    "Callao": {"titulo": "Callao · operaciones industriales y comercio exterior",
               "detalle": "Nave nueva de 30 mil posiciones (más de US$ 11 M, 2023), depósito temporal de contenedores y red de frío.",
               "fuente": "gestion_2023"},
    "Lima": {"titulo": "Lima · distribución y frío",
             "detalle": "Distribución de consumo masivo con flota Euro V (CBC Perú) y cámaras de frío.",
             "fuente": "proactivo_2021"},
    "Chancay": {"titulo": "Chancay · Torre Blanca y automotriz",
                "detalle": "Planta de fruta Torre Blanca (Huaral; nuevo túnel de frío en 2026) y cigüeñas del puerto de Chancay a Lima.",
                "fuente": "gestion_2026"},
    "Chiclayo": {"titulo": "Chiclayo · centro de distribución",
                 "detalle": "S/ 14 M de inversión: 3,476 posiciones secas y 560 de frío.",
                 "fuente": "peruretail_chiclayo"},
    "Trujillo": {"titulo": "Trujillo · red de frío", "detalle": "Cámaras de frío y contenedores refrigerados.",
                 "fuente": "peruretail_frio"},
    "Piura": {"titulo": "Piura · red de frío", "detalle": "Cámaras de frío para agroexportación del norte.",
              "fuente": "peruretail_frio"},
    "Arequipa": {"titulo": "Arequipa · red de frío y sur", "detalle": "Cámaras de frío; base del corredor sur.",
                 "fuente": "peruretail_frio"},
    "Huancayo": {"titulo": "Huancayo · red de frío", "detalle": "Cámaras de frío en la sierra central.",
                 "fuente": "peruretail_frio"},
    "Cusco": {"titulo": "Cusco · red de frío", "detalle": "Cámaras de frío en el sur andino.",
              "fuente": "peruretail_frio"},
}

AGENDA_2026 = [
    {"texto": "Crecimiento en el Perú por encima de 10 % en 2026 (más de 12 % en el primer semestre).", "fuente": "gestion_2026"},
    {"texto": "Inversión cercana a US$ 12 M: camiones de distribución y comercio exterior, túnel de frío en Torre Blanca y cigüeñas en Chancay.", "fuente": "gestion_2026"},
    {"texto": "Nuevos centros de distribución en el Callao y el norte: +10 a 20 mil m² con modelo asset light.", "fuente": "gestion_2026"},
    {"texto": "Evalúa llevar al Perú su logística farmacéutica (hoy en Chile y Ecuador) entre fines de 2026 e inicios de 2027.", "fuente": "gestion_2026"},
    {"texto": "Cabotaje como plan B cuando los desastres naturales cortan las carreteras; carga aérea solo para contingencias.", "fuente": "gestion_2023"},
    {"texto": "Plan de descarbonización 2030: huella de carbono medida en 10 países (GHG Protocol, con IFC) y paneles solares en 5 centros del Perú en 2026.", "fuente": "proactivo_2025"},
]


def _con_fuente(item: dict) -> dict:
    out = dict(item)
    out["fuente"] = FUENTES[item["fuente"]] | {"id": item["fuente"]}
    return out


def get_profile() -> dict:
    return {
        "nombre": "RANSA",
        "propiedad": PROPIEDAD,
        "cifras": [_con_fuente(c) for c in CIFRAS],
        "liderazgo": [_con_fuente(p) for p in LIDERAZGO],
        "lineas": [_con_fuente(linea) for linea in LINEAS],
        "sedes": [{"nodo": k} | _con_fuente(v) for k, v in SEDES.items()],
        "agenda": [_con_fuente(a) for a in AGENDA_2026],
        "fuentes": [{"id": k} | v for k, v in FUENTES.items()],
        "nota": "Datos públicos de prensa con su fecha. La operación de la plataforma es simulada.",
    }


def sede_de(nodo: str):
    """Sede pública de RANSA asociada a un nodo de la red (o None)."""
    s = SEDES.get(nodo)
    return _con_fuente(s) if s else None


def color_linea(linea: str) -> str:
    return next((x["color"] for x in LINEAS if x["id"] == linea), "#64748b")
