# RANSA Decision Intelligence · Perú

Plataforma de *Decision Intelligence* con **gemelo digital** de la operación logística multimodal en el Perú:
anticipar, predecir y responder a contingencias (huaicos, bloqueos, oleajes anómalos, vaciantes, robos,
nevadas) en menos de 72 horas, sobre una red trazada en las **vías reales** del país.

> **Prototipo independiente de demostración con fines académicos.** Toda la información operativa es
> **100 % simulada**; no es un sistema oficial ni representa datos reales de RANSA.

**🔗 Demo en vivo:** https://ransa-decision-intelligence.onrender.com — entra con un perfil de demostración
(un clic). En el plan gratuito de Render el servicio se duerme sin visitas: la primera carga tarda ~50 s.

**Stack:** Python 3.11 · Flask · SQLAlchemy · scikit-learn (Gradient Boosting + Regresión Logística) ·
Leaflet · Chart.js · Bootstrap 5 · SQLite (PostgreSQL en producción opcional) · Render.

---

## Lo más destacado

| Módulo | Qué hace |
|---|---|
| **Gemelo Digital · Torre de Control** | 60 unidades (camiones, buques de cabotaje, convoyes fluviales, vuelos) recorren las rutas reales de OpenStreetMap. La velocidad de cada camión sale del perfil SRTM: pendiente + pérdida de potencia sobre 3.500 m (Ticlio, 4.818 m). Telemetría por unidad: altitud, combustible, motor, cadena de frío, horas de conducción (SUTRAN) y **perfil de altitud** de la ruta. |
| **Eventos geolocalizados** | Huaico, derrumbe, bloqueo, inundación, nevada, neblina, incendio, accidente, oleaje con cierre de puerto, vaciante del río… Un evento afecta a **todas** las rutas que pasan por el punto (un huaico en Chosica corta Lima–Huancayo, Cerro de Pasco, Huánuco y Pucallpa). Inyección con un clic en el mapa. |
| **Decision Intelligence en vivo** | Para cada evento la IA compara esperar, **desviar por la ruta alterna real** (Cañete–Lunahuaná PE-24, Canta–Huayllay PE-20A, con retorno al punto de desvío si hace falta), **puerto alterno** (Callao ⇄ Chancay), **transbordo a cabotaje** o congelar despachos; puntúa OTIF 40 %, costo 20 %, tiempo 20 %, CO₂ 10 % y riesgo 10 %, recomienda y ejecuta (o lo hace sola en modo **IA autónoma**). |
| **Escenarios Perú** | Huaico en Chosica, nevada en Ticlio, bloqueo del Corredor Minero Sur, oleaje en el Callao, paro de transportistas en Lima, Niño Costero en Piura, vaciante amazónica, neblina en Pasamayo, crisis social del sur. |
| **Modo presentación** | Recorrido guiado de 7 pasos para jurados y directivos. |
| **Predicciones IA** | Gradient Boosting (AUC 0.79 en prueba) vs. Regresión Logística (0.72); se activa el mejor. Importancia por permutación. |
| **Riesgo 24h / Anticipación 48h** | Proyección por corredor y categoría con **estacionalidad peruana** (lluvias dic–mar, heladas jun–ago, vaciante ago–oct). |
| **Simulador what-if** | Por embarque (regresores Gradient Boosting: Lead Time R² 0.97, costo R² 0.98) y de red (crisis social sur, Niño Costero, vaciante, *Chancay como hub alterno del Callao*…). |
| **Modelo Lead Time (ACP)** | ACP + regresión múltiple con factores nombrados automáticamente por sus cargas. |
| **Copiloto IA** | Responde qué pasa ahora en el gemelo, huaicos y lluvias, cadena de frío, Callao vs. Chancay, what-if de cierres… |
| **Contingencias** | Sala de crisis tipo WhatsApp (huaico en Matucana, Carretera Central) y flujo de aprobación directiva. |

## Datos simulados

* `data/peru_network.json` — red real: 33 nodos, **68 rutas** (48 carreteras sobre OSRM/OpenStreetMap con perfil
  SRTM, 8 de cabotaje, 2 fluviales amazónicas, 10 aéreas) y 25 puntos críticos. Se regenera con
  `python scripts/build_peru_network.py` (requiere internet).
* `data/RANSA_Peru_Dataset_Simulado.csv` — **30.000 embarques × 122 variables** (ene-2023 → set-2026) en soles,
  generados con `python scripts/generate_peru_dataset.py`. Incluye episodios con fechas reales: crisis social del
  sur (ene–mar 2023), Ciclón Yaku / Niño Costero (mar–abr 2023), El Niño costero (alerta ENFEN), estiaje amazónico
  (2023 y 2024), incendios forestales (2024), paros de transportistas por extorsión (2024–2025), inicio del Puerto
  de Chancay (14-nov-2024) y transición a la nueva terminal del Jorge Chávez (jun-2025).
* `data/RANSA_Peru_Diccionario_Datos.csv` — fuente pública de referencia de cada variable (SENAMHI, INDECI,
  INGEMMET, PNP, Defensoría del Pueblo, MTC/Provías, SUTRAN, APN, DHN, OSINERGMIN, INEI, BCRP…).

## Ejecutar en local

```bash
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
python run.py                    # http://localhost:5000
```

La base `data/ransa.db` y los modelos de `data/models/` ya vienen generados. Para reconstruir todo desde cero:

```bash
python scripts/generate_peru_dataset.py   # dataset + diccionario
python scripts/_gen_field_metadata.py     # metadatos de columnas
python scripts/_gen_shipment_model.py     # modelo SQLAlchemy
python scripts/import_data.py             # ETL a SQLite
python scripts/seed_users.py              # cuentas demo
python scripts/train_model.py             # Gradient Boosting + Regresión Logística + regresores
python scripts/fit_leadtime_pca.py        # ACP + regresión de Lead Time
```

**Acceso:** en el login, botones de *acceso de demostración* por rol (Administrador, Supervisor, Operaciones,
Cliente, Analista). Las cuentas demo y su contraseña están en `scripts/seed_users.py`. En un despliegue real,
desactivar el acceso demo con `DEMO_MODE=false`.

## Desplegar en Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jmhuamann-bit/ransa-decision-intelligence)

1. Pulsa el botón (o en Render: **New → Blueprint** y elige este repositorio): `render.yaml` crea el servicio
   `ransa-decision-intelligence` (Gunicorn con **1 worker y 8 hilos**: el gemelo vive en memoria y todos los
   usuarios deben ver la misma operación).
2. Abre la URL que entrega Render. En el plan gratuito el servicio se duerme tras ~15 min sin visitas; la
   primera carga tarda 30–60 s.
3. El plan gratuito tiene CPU limitada: **reentrenar** los modelos desde la web puede superar el tiempo máximo
   de respuesta. Los modelos ya vienen entrenados; para reentrenar, hazlo en local (`python scripts/train_model.py`)
   y sube los archivos de `data/`.

## Arquitectura

```
app/
  api/            Endpoints REST (/api/live/* = gemelo digital, /api/predictions, /api/strategic, ...)
  services/       live_engine (gemelo), geo_data (red real), predictive, decision_assistant,
                  network_simulator, contingency_planner, chat, reportes...
  ml/             data (variables pre-despacho, sin fuga) · training · prediction · evaluation
  etl/            lectura, validación, heurística de riesgo, carga
  models/         Shipment (98 columnas), User, Alert, MLModelRun, AuditLog
scripts/          construcción de red, generador del dataset, entrenamiento, ACP
static/ templates/  interfaz (Leaflet + Chart.js + Bootstrap)
data/             red, dataset, diccionario, BD SQLite y modelos entrenados
```

Mapas: © OpenStreetMap contributors · OpenTopoMap · Esri. Altitud: SRTM (NASA) vía OpenTopoData. Rutas: OSRM.
