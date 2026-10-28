# RANSA Decision Intelligence · Perú

Plataforma de *Decision Intelligence* con **gemelo digital** de la operación logística multimodal de RANSA en el Perú:
ver la red en vivo, anticipar contingencias (huaicos, bloqueos, oleajes anómalos, vaciantes, robos, nevadas) y decidir
con IA en minutos, sobre una red trazada en las **vías reales** del país.

> **Prototipo académico independiente, sin vínculo con RANSA.** El perfil de la empresa (escala, sedes, líneas de
> negocio, flota a GNL, directivos) proviene de **prensa pública con fuente y fecha**. La operación —embarques, flota en
> vivo, eventos y decisiones— es **100 % simulada**.

**🔗 Demo en vivo:** https://ransa-decision-intelligence.onrender.com — entra con un perfil de demostración
(un clic). En el plan gratuito de Render el servicio se duerme sin visitas: la primera carga tarda ~50 s.

**Stack:** Python 3.11 · Flask · SQLAlchemy · scikit-learn (Gradient Boosting + Regresión Logística, ACP) ·
Leaflet · Chart.js · Bootstrap 5 · SQLite (PostgreSQL opcional) · Render.

---

## 6 módulos (pensados para presentar)

| Módulo | Qué hace |
|---|---|
| **Torre de Control** | Gemelo digital: 60 unidades (camiones, cabotaje, convoyes fluviales, vuelos) sobre las rutas reales de OpenStreetMap, con velocidad según pendiente y altitud SRTM (Ticlio, 4,818 m). Sedes públicas de RANSA marcadas en el mapa; cada unidad muestra su **línea de negocio** y su **combustible** (Diésel Euro V, GNL, GNV). Escenarios peruanos, inyección de eventos con un clic y **Decision Intelligence** que compara esperar, desviar por la ruta alterna real, puerto alterno (Callao ⇄ Chancay) o cabotaje (OTIF 40 % · costo 20 % · tiempo 20 % · CO₂ 10 % · riesgo 10 %). Presentación guiada de 7 pasos. |
| **Resumen RANSA** | Perfil público de la empresa con fuentes, pulso en vivo del gemelo y la operación 2023–2026 por **línea de negocio**, año y modo: OTIF, Lead Time, costo, CO₂ (y CO₂ evitado con GNL/GNV), corredores de mayor riesgo y agenda 2026 de la empresa. |
| **Riesgo 24–48 h** | Probabilidad por corredor de eventos geológicos, hidrológicos, sociales, de seguridad o accidentes en 24 h; escenarios de red a 48 h con **estacionalidad peruana** y planes A/B/C/D. |
| **Simulador what-if** | Un embarque (regresores Gradient Boosting: Lead Time R² 0.97, costo R² 0.96) o toda la red (crisis social del sur, Niño Costero, vaciante, Chancay como hub alterno…). |
| **Modelos IA** | Clasificación del OTIF: Gradient Boosting (AUC 0.796 en prueba) vs. Regresión Logística (0.732), curva ROC, matriz de confusión e importancia por permutación. Lead Time: ACP (70 variables → 5 factores nombrados por sus cargas, VIF) + regresión múltiple (R² prueba 0.44). |
| **Datos de embarques** | Los 30,000 embarques con filtros (línea, modo, riesgo, OTIF…) y exportación a CSV, Excel y reporte ejecutivo PDF. |

El **AI Copilot** (barra superior) responde en cualquier pantalla: qué pasa ahora en el gemelo, Callao vs. Chancay,
cadena de frío, CO₂ y GNL, el perfil de RANSA o cómo va cada línea de negocio.

## RANSA según fuentes públicas

* Operador logístico de origen peruano con más de 80 años; desde 2021 su accionista mayoritario es **H.I.G. Capital**
  y el Grupo Romero se mantiene como socio minoritario. Fusión con TCF (2023) y compra de Loginsa en Chile (2024).
* **12 países** de México a Chile, **+9,000 colaboradores** y **13 ciudades** con operación en el Perú (Gestión, jun-2026).
* En el Perú: **+3 M m²** de almacenamiento, **+98 mil posiciones** (Gestión, abr-2023) y **+20 mil posiciones de frío**
  en Lima, Callao, Chiclayo, Trujillo, Arequipa, Piura, Huancayo y Cusco (Peru Retail, 2022).
* Líneas que modela la plataforma: **Distribución**, **Comercio Exterior**, **Logística de Frío**, **Minería y Energía** y
  **Automotriz** (SLA; cigüeñas Chancay → Lima). Flota en transición a **GNL**: 11 tractos y 27 camiones (ProActivo, nov-2025).
* Las fuentes completas, con enlace y fecha, están en `app/services/ransa_profile.py` y en el módulo Resumen RANSA.

## Datos simulados

* `data/peru_network.json` — red real: 33 nodos, 68 rutas (48 carreteras sobre OSRM/OpenStreetMap con perfil SRTM,
  8 de cabotaje, 2 fluviales, 10 aéreas) y 25 puntos críticos. Se regenera con `python scripts/build_peru_network.py`.
* `data/RANSA_Peru_Dataset_Simulado.csv` — **30,000 embarques × 125 variables** (ene-2023 → set-2026) en soles, con
  **línea de negocio**, **combustible de la unidad** y **emisiones de CO₂** por viaje. Episodios con fechas reales: crisis
  social del sur (2023), Ciclón Yaku / Niño Costero (2023), estiaje amazónico (2023-24), incendios forestales (2024),
  paros de transportistas por extorsión (2024-25), inicio del Puerto de Chancay (14-nov-2024) y nueva terminal del
  Jorge Chávez (jun-2025).
* `data/RANSA_Peru_Diccionario_Datos.csv` — fuente pública de referencia de cada variable (SENAMHI, INDECI, INGEMMET,
  PNP, Defensoría del Pueblo, MTC/Provías, SUTRAN, APN, DHN, MINAM, OSINERGMIN, INEI, BCRP…).

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
  api/            Endpoints REST (/api/live/* = gemelo digital, /api/company = perfil RANSA, /api/dashboard, ...)
  services/       live_engine (gemelo), ransa_profile (perfil público), geo_data (red real), predictive,
                  decision_assistant, network_simulator, chat, reportes...
  ml/             data (variables pre-despacho, sin fuga) · training · prediction · evaluation
  etl/            lectura, validación, heurística de riesgo, carga
  models/         Shipment (101 columnas), User, Alert, MLModelRun, AuditLog
scripts/          construcción de red, generador del dataset, entrenamiento, ACP
static/ templates/  interfaz (Leaflet + Chart.js + Bootstrap)
data/             red, dataset, diccionario, BD SQLite y modelos entrenados
```

Mapas: © OpenStreetMap contributors · OpenTopoMap · Esri. Altitud: SRTM (NASA) vía OpenTopoData. Rutas: OSRM.
