/* Gemelo Digital · Torre de Control RANSA Perú.
   El servidor simula la operación (app/services/live_engine.py); aquí se dibuja sobre la red vial
   real y se anima cada unidad por estima (km + velocidad × tiempo simulado) entre consultas. */
(function () {
  const POLL_MS = 1500;
  const PERU_BOUNDS = [[-18.4, -81.4], [-0.1, -68.6]];
  const MODE_ICON = { "Carretero": "fa-truck", "Marítimo": "fa-ship", "Fluvial": "fa-ferry", "Aéreo": "fa-plane" };
  const MODE_COLOR = { "Carretero": "#3d63ff", "Marítimo": "#1d4ed8", "Fluvial": "#0891b2", "Aéreo": "#475569" };
  const SEV_COLOR = { Critica: "#e11d48", Alta: "#f97316", Media: "#eab308", Baja: "#94a3b8" };
  const STATE_COLOR = { en_ruta: "#3d63ff", lento: "#eab308", detenido: "#e11d48", desviado: "#8b5cf6", esperando: "#94a3b8", descanso: "#94a3b8", fondeado: "#0ea5e9" };
  const ESTADO_TXT = { en_ruta: "En ruta", lento: "Avance lento", detenido: "Detenido", desviado: "Ruta alterna", esperando: "En espera", descanso: "Pausa SUTRAN", fondeado: "En fondeadero" };
  const RISK_COLOR = { verde: "#16a34a", amarillo: "#eab308", rojo: "#e11d48" };
  const MOVING = new Set(["en_ruta", "lento", "desviado"]);

  let map, baseLayer, currentBase = "claro";
  const L_ = {};
  let net = null;
  const routesById = {};
  const routeLines = {};
  let routeRisk = {};
  let catalog = { escenarios: [], eventos: [] };
  let snap = null, snapAt = 0, sinceId = 0, feedCount = 0;
  const veh = {};
  const evMarkers = {};
  let selectedId = null, follow = false;
  let scope = { tipo: "red", ref: null };
  let injectTipo = null;
  let inspChart = null, profileChart = null, profileRouteId = null;
  let lastDecisionsHash = "", lastNodesHash = "";
  let tour = null;
  let modeFilter = "";
  const sedeByNode = {};
  const LINEA_ICON = { "Distribución": "fa-boxes-stacked", "Comercio Exterior": "fa-ship", "Logística de Frío": "fa-snowflake",
    "Minería y Energía": "fa-helmet-safety", "Automotriz": "fa-car-side" };

  const $ = (id) => document.getElementById(id);
  const esc = (t) => { const d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; };
  const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  // ======================================================== geometría
  function pointAt(geom, cum, km) {
    if (!geom || !geom.length) return null;
    const total = cum[cum.length - 1];
    km = Math.max(0, Math.min(km, total));
    let lo = 1, hi = cum.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid] < km) lo = mid + 1; else hi = mid; }
    const i = Math.max(1, lo);
    const seg = (cum[i] - cum[i - 1]) || 1e-9;
    const f = (km - cum[i - 1]) / seg;
    const a = geom[i - 1], b = geom[i];
    const lat = a[0] + (b[0] - a[0]) * f, lon = a[1] + (b[1] - a[1]) * f;
    const heading = Math.atan2((b[1] - a[1]) * Math.cos(lat * Math.PI / 180), b[0] - a[0]) * 180 / Math.PI;
    return { lat, lon, heading };
  }
  function sliceGeom(route, kmA, kmB) {
    const pts = [];
    const a = pointAt(route.geometry, route.cum_km, kmA), b = pointAt(route.geometry, route.cum_km, kmB);
    if (!a || !b) return pts;
    pts.push([a.lat, a.lon]);
    route.cum_km.forEach((c, i) => { if (c > kmA && c < kmB) pts.push(route.geometry[i]); });
    pts.push([b.lat, b.lon]);
    return pts;
  }

  // ======================================================== mapa
  const BASEMAPS = {
    claro: () => L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19, attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors" }),
    oscuro: () => L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 16, attribution: "Mapa base &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors" }),
    relieve: () => L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
      maxZoom: 17, attribution: "&copy; OpenStreetMap contributors, SRTM | &copy; OpenTopoMap (CC-BY-SA)" }),
    satelite: () => L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      maxZoom: 18, attribution: "Imágenes &copy; Esri, Maxar, Earthstar Geographics" }),
  };
  function setBase(name) {
    if (baseLayer) map.removeLayer(baseLayer);
    baseLayer = BASEMAPS[name]().addTo(map);
    baseLayer.bringToBack();
    currentBase = name;
    const shown = name === "oscuro" ? "claro" : name;
    document.querySelectorAll("#twBasemap button").forEach((b) => b.classList.toggle("active", b.dataset.base === shown));
  }
  const isDark = () => document.documentElement.getAttribute("data-theme") === "dark";

  function initMap() {
    map = L.map("torreMap", { zoomControl: true, preferCanvas: false, minZoom: 4, zoomSnap: 0.25, zoomDelta: 0.5, worldCopyJump: false });
    map.fitBounds(PERU_BOUNDS, { padding: [6, 6] });
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    setBase(dark ? "oscuro" : "claro");
    ["rutas", "alternas", "tramos", "eventos", "sedes", "nodos", "hotspots", "flota"].forEach((k) => { L_[k] = L.layerGroup().addTo(map); });
    map.removeLayer(L_.hotspots);
    map.on("click", onMapClick);
    map.on("dragstart", () => { follow = false; updateFollowBtn(); });
  }

  // ======================================================== red estática
  function drawNetwork() {
    L_.rutas.clearLayers();
    net.routes.forEach((r) => {
      routesById[r.id] = r;
      if (r.alterna_de) return;
      const risk = routeRisk[`${r.corredor}|${r.modo}`];
      let style;
      if (r.modo === "Carretero") style = { color: risk ? RISK_COLOR[risk.semaforo] : "#64748b", weight: 2.6, opacity: .55 };
      else if (r.modo === "Marítimo") style = { color: "#1d4ed8", weight: 2, opacity: .55, dashArray: "6 8" };
      else if (r.modo === "Fluvial") style = { color: "#0891b2", weight: 3.2, opacity: .7 };
      else style = { color: "#64748b", weight: 1.2, opacity: .35, dashArray: "2 7" };
      const line = L.polyline(r.geometry, style);
      line.bindTooltip(`<b>${esc(r.corredor)}</b> · ${esc(r.modo)}<br>${esc(r.ruta_principal)} · ${gdFormatNumber(r.km, 0)} km` +
        (r.alt_max > 1500 ? ` · máx ${gdFormatNumber(r.alt_max, 0)} m s. n. m.` : "") +
        (risk ? `<br>Riesgo histórico IA: ${gdFormatPct(risk.riesgo_promedio_pct)} · OTIF ${gdFormatPct(risk.otif_pct)}` : ""), { sticky: true });
      line.on("click", (e) => { L.DomEvent.stopPropagation(e); if (!injectTipo) selectCorredor(r.corredor); });
      line.addTo(L_.rutas);
      routeLines[r.id] = { line, style };
    });

    L_.nodos.clearLayers();
    L_.sedes.clearLayers();
    net.nodes.forEach((n) => {
      const cls = n.es_puerto ? "puerto" : n.es_fluvial ? "fluvial" : n.roles.includes("cd") ? "" : "aero";
      const icon = n.es_puerto ? "fa-anchor" : n.es_fluvial ? "fa-water" : n.roles.includes("cd") ? "fa-warehouse" : "fa-plane";
      const label = n.roles.includes("hub") || n.sede;
      if (n.sede) {
        sedeByNode[n.nombre] = n.sede;
        L.marker([n.lat, n.lon], { icon: L.divIcon({ className: "", html: '<div class="tw-sede-ring"></div>', iconSize: [44, 44], iconAnchor: [22, 22] }),
          interactive: false, zIndexOffset: 300 }).addTo(L_.sedes);
      }
      const m = L.marker([n.lat, n.lon], {
        icon: L.divIcon({ className: "", html: `<div class="tw-node ${cls}${n.sede ? " sede" : ""}" data-node="${esc(n.nombre)}"><i class="fa-solid ${icon}"></i></div>${label ? `<div class="tw-node-label">${esc(n.nombre)}</div>` : ""}`,
          iconSize: [24, 24], iconAnchor: [12, 12] }),
        zIndexOffset: 400,
      });
      m.bindTooltip(`<b>${esc(n.nombre)}</b> · ${esc(n.departamento)}<br>${gdFormatNumber(n.altitud_msnm, 0)} m s. n. m.${n.iata ? ` · Aeropuerto ${n.iata}` : ""}` +
        (n.sede ? `<div class="tw-tip-sede"><i class="fa-solid fa-building"></i> <b>Sede RANSA</b> · ${esc(n.sede.titulo)}<br>${esc(n.sede.detalle)}</div>` : ""),
        { direction: "top", offset: [0, -12] });
      m.on("click", (e) => { L.DomEvent.stopPropagation(e); if (!injectTipo) selectNodo(n.nombre); });
      m.addTo(L_.nodos);
    });

    L_.hotspots.clearLayers();
    net.hotspots.forEach((h) => {
      L.marker([h.lat, h.lon], { icon: L.divIcon({ className: "", html: `<div class="tw-hotspot"><i class="fa-solid fa-triangle-exclamation"></i></div>`, iconSize: [16, 16], iconAnchor: [8, 8] }) })
        .bindTooltip(`<b>${esc(h.nombre)}</b><br>${esc(h.descripcion)}`, { direction: "top" })
        .addTo(L_.hotspots);
    });
  }

  async function loadHeat() {
    try {
      const { puntos } = await RansaAPI.get("/api/predictive/heatmap");
      if (window.L && L.heatLayer) {
        L_.calor = L.heatLayer(puntos.map((p) => [p[0], p[1], Math.max(0.2, p[2])]), { radius: 38, blur: 30, maxZoom: 8,
          gradient: { 0.2: "#22c55e", 0.45: "#eab308", 0.7: "#f97316", 0.9: "#e11d48" } });
      }
    } catch (e) { /* capa opcional */ }
  }

  // ======================================================== KPIs
  function renderOpsKpis(k) {
    const otifCls = k.otif_proyectado_pct >= 85 ? "success" : k.otif_proyectado_pct >= 70 ? "warning" : "danger";
    const items = [
      { id: "mov", icon: "fa-route", label: "En movimiento", value: `${gdFormatNumber(k.vehiculos_en_operacion, 0)}<small>/${gdFormatNumber(k.operaciones_activas, 0)}</small>` },
      { id: "otif", icon: "fa-bullseye", label: "OTIF proyectado", value: gdFormatPct(k.otif_proyectado_pct), cls: otifCls },
      { id: "inc", icon: "fa-triangle-exclamation", label: "Eventos activos", value: gdFormatNumber(k.incidentes_actuales, 0), cls: k.incidentes_actuales ? "danger" : "" },
      { id: "ia", icon: "fa-brain", label: "Decisiones pendientes", value: gdFormatNumber(k.alertas_ia, 0), cls: k.alertas_ia ? "danger" : "success" },
      { id: "carga", icon: "fa-sack-dollar", label: "Carga en riesgo", value: gdFormatPENShort(k.carga_en_riesgo_pen), cls: k.carga_en_riesgo_pen > 0 ? "warning" : "" },
      { id: "co2", icon: "fa-leaf", label: "CO₂ viajes en curso", value: `${gdFormatNumber(k.co2_en_curso_t, 1)} t` },
    ];
    const box = $("torreOpsKpis");
    if (!box.children.length) {
      box.innerHTML = items.map((i) => `<div class="torre-ops-item" data-k="${i.id}"><i class="fa-solid ${i.icon}"></i><span class="torre-ops-val"></span><span class="torre-ops-lbl">${i.label}</span></div>`).join("");
    }
    items.forEach((i) => {
      const el = box.querySelector(`[data-k="${i.id}"]`);
      const val = el.querySelector(".torre-ops-val");
      el.className = `torre-ops-item ${i.cls || ""}`;
      if (val.innerHTML !== i.value) {
        const first = !val.innerHTML;
        val.innerHTML = i.value;
        if (!first) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
      }
    });
  }

  // ======================================================== flota
  function vehRoute(v) { return v.custom_route ? v.custom_route : routesById[v.route_id]; }

  function vehHtml(v) {
    const sel = v.id === selectedId ? " sel" : "";
    const big = v.tipo_transporte !== "Carretero" ? " big" : "";
    return `<div class="tw-veh estado-${v.estado}${sel}${big}"><i class="fa-solid ${MODE_ICON[v.tipo_transporte] || "fa-truck"} rot"></i></div>`;
  }

  function upsertVehicles(list) {
    const ids = new Set();
    list.forEach((v) => {
      ids.add(v.id);
      let e = veh[v.id];
      const route = vehRoute(v);
      if (!route) return;
      if (!e) {
        const p = pointAt(route.geometry, route.cum_km, v.km) || { lat: v.lat, lon: v.lon };
        const marker = L.marker([p.lat, p.lon], { icon: L.divIcon({ className: "", html: vehHtml(v), iconSize: [26, 26], iconAnchor: [13, 13] }), zIndexOffset: 800 });
        marker.on("click", (ev) => { L.DomEvent.stopPropagation(ev); if (!injectTipo) selectVehicle(v.id); });
        marker.bindTooltip("", { direction: "top", offset: [0, -14] });
        marker.addTo(L_.flota);
        e = veh[v.id] = { marker, kmShown: v.km, estado: null, sel: null };
      }
      e.data = v;
      e.route = route;
      e.kmBase = v.km;
      e.tBase = performance.now();
      e.kmh = MOVING.has(v.estado) ? v.v_kmh : 0;
      e.total = v.km_total;
      if (e.estado !== v.estado || e.sel !== (v.id === selectedId)) {
        e.marker.setIcon(L.divIcon({ className: "", html: vehHtml(v), iconSize: [26, 26], iconAnchor: [13, 13] }));
        e.estado = v.estado;
        e.sel = v.id === selectedId;
      }
      const evt = v.evento ? ` · <b style="color:${SEV_COLOR[v.evento.severidad] || "#94a3b8"}">${esc(v.evento.titulo)}</b>` : "";
      e.marker.setTooltipContent(`<b>${esc(v.id)}</b> ${esc(v.nombre)} · ${esc(v.corredor)}<br>${ESTADO_TXT[v.estado] || v.estado} · ${gdFormatNumber(v.v_kmh, 0)} km/h${evt}`);
    });
    Object.keys(veh).forEach((id) => {
      if (!ids.has(id)) { L_.flota.removeLayer(veh[id].marker); delete veh[id]; if (id === selectedId) clearUnit(); }
    });
  }

  function animate() {
    const now = performance.now();
    const simRate = snap && !snap.paused ? snap.speed : 0;
    Object.values(veh).forEach((e) => {
      if (!e.route) return;
      const dt = Math.min(3, (now - e.tBase) / 1000);
      const target = Math.min(e.total, e.kmBase + e.kmh * simRate * dt / 3600);
      e.kmShown = e.kmShown + (target - e.kmShown) * 0.25;
      if (Math.abs(target - e.kmShown) > 25) e.kmShown = target;
      const p = pointAt(e.route.geometry, e.route.cum_km, e.kmShown);
      if (!p) return;
      e.marker.setLatLng([p.lat, p.lon]);
      const el = e.marker.getElement();
      if (el) {
        const icon = el.querySelector(".rot");
        if (icon) {
          const modo = e.data.tipo_transporte;
          if (modo === "Aéreo") icon.style.transform = `rotate(${p.heading - 90}deg)`;
          else if (modo === "Carretero") icon.style.transform = p.heading < 0 ? "scaleX(-1)" : "";
        }
      }
      if (follow && e.data.id === selectedId) map.panTo([p.lat, p.lon], { animate: false });
    });
    updateClock(now);
    requestAnimationFrame(animate);
  }

  function updateClock(now) {
    if (!snap) return;
    const elapsed = snap.paused ? 0 : (now - snapAt) / 1000 * snap.speed;
    const t = new Date(new Date(snap.sim_time).getTime() + elapsed * 1000);
    // hora de Perú (UTC-5, sin horario de verano)
    const pe = new Date(t.getTime() + (t.getTimezoneOffset() - 300) * 60000);
    $("twClock").textContent = pe.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", hour12: false });
    $("twClockDate").textContent = pe.toLocaleDateString("es-PE", { weekday: "short", day: "2-digit", month: "short" }) + " · hora Perú (simulada)";
  }

  // ======================================================== eventos
  function eventIcon(e) {
    const color = SEV_COLOR[e.severidad] || "#94a3b8";
    return L.divIcon({ className: "", iconSize: [34, 34], iconAnchor: [17, 17],
      html: `<div class="tw-event"><div class="ring" style="background:${color}55"></div><div class="core" style="background:${color}"><i class="fa-solid ${e.icon}"></i></div></div>` });
  }
  function eventPopup(e) {
    const dec = e.decision ? `<div class="gd-popup-row" style="color:#15803d"><b>✔ ${esc(e.decision.nombre)}</b></div>` : "";
    return `<div class="gd-popup-title"><i class="fa-solid ${e.icon}"></i> ${esc(e.titulo)}</div>
      <div class="gd-popup-row">${esc(e.lugar)}</div>
      <div class="gd-popup-row">Severidad <b>${esc(e.severidad)}</b> · restan <b>${gdFormatNumber(e.restante_h, 1)} h</b></div>
      <div class="gd-popup-row">${e.afectados} unidades afectadas${e.rutas.length ? ` · ${e.rutas.length} corredores` : ""}</div>${dec}
      <div class="d-flex gap-1 mt-2"><button class="gd-btn gd-btn-accent gd-btn-sm" onclick="window.twGoDecision(${e.id})">Ver decisión IA</button>
      <button class="gd-btn gd-btn-outline gd-btn-sm" onclick="window.twResolve(${e.id})">Resolver ya</button></div>`;
  }
  function renderEvents(events) {
    const ids = new Set(events.map((e) => e.id));
    Object.keys(evMarkers).forEach((id) => {
      if (!ids.has(+id)) { evMarkers[id].layers.forEach((l) => l.remove()); delete evMarkers[id]; }
    });
    L_.tramos.clearLayers();
    L_.alternas.clearLayers();
    events.forEach((e) => {
      let em = evMarkers[e.id];
      if (!em) {
        const marker = L.marker([e.lat, e.lon], { icon: eventIcon(e), zIndexOffset: 1000 }).bindPopup(eventPopup(e), { maxWidth: 300 });
        const layers = [marker];
        if (!e.bloquea && e.alcance !== "via") {
          layers.push(L.circle([e.lat, e.lon], { radius: e.radio_km * 1000, color: SEV_COLOR[e.severidad], weight: 1, fillOpacity: .08 }));
        } else if (!e.bloquea) {
          layers.push(L.circle([e.lat, e.lon], { radius: e.radio_km * 1000, color: SEV_COLOR[e.severidad], weight: 1, dashArray: "4 6", fillOpacity: .06 }));
        }
        layers.forEach((l) => l.addTo(L_.eventos));
        em = evMarkers[e.id] = { marker, layers };
      } else {
        em.marker.setPopupContent(eventPopup(e));
      }
      // tramos cortados o con restricción sobre TODAS las rutas que pasan por el punto
      Object.entries(e.route_hits || {}).forEach(([rid, km]) => {
        const r = routesById[rid];
        if (!r || r.alterna_de) return;
        const half = Math.max(3, e.radio_km);
        const pts = sliceGeom(r, Math.max(0, km - half), Math.min(r.cum_km[r.cum_km.length - 1], km + half));
        if (pts.length > 1) {
          L.polyline(pts, { color: e.bloquea ? "#e11d48" : "#eab308", weight: e.bloquea ? 7 : 6, opacity: .85, dashArray: e.bloquea ? "1 9" : null, lineCap: "round" }).addTo(L_.tramos);
        }
      });
      // rutas alternas propuestas por la IA (o ya aplicadas)
      const opt = (e.opciones || []).find((o) => o.id === "desviar");
      if (opt) {
        new Set(Object.keys(e.route_hits || {}).map((rid) => routesById[rid]?.corredor)).forEach((corr) => {
          const alt = routesById[`TER:${corr}|ALT`];
          if (alt) L.polyline(alt.geometry, { color: "#8b5cf6", weight: 3.5, opacity: e.decision ? .9 : .55, dashArray: "8 7" })
            .bindTooltip(`Ruta alterna real: ${esc(alt.ruta_principal)} (${gdFormatNumber(alt.km, 0)} km)`, { sticky: true }).addTo(L_.alternas);
        });
      }
    });
    // rutas compuestas de unidades que ya se desviaron (retorno + alterna)
    Object.values(veh).forEach((e) => {
      if (e.data.custom_route) L.polyline(e.data.custom_route.geometry, { color: "#8b5cf6", weight: 3, opacity: .8, dashArray: "6 6" }).addTo(L_.alternas);
      else if (e.data.desvio && routesById[e.data.route_id]) {
        const r = routesById[e.data.route_id];
        if (r.alterna_de) L.polyline(r.geometry, { color: "#8b5cf6", weight: 3, opacity: .8, dashArray: "6 6" }).addTo(L_.alternas);
      }
    });
  }

  window.twResolve = async (id) => { try { await RansaAPI.post(`/api/live/events/${id}/resolve`); toast("Evento resuelto: la vía se restablece."); poll(); } catch (e) { toast(e.message); } };
  window.twGoDecision = (id) => { const el = document.querySelector(`.tw-ev[data-ev="${id}"]`); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.animate([{ boxShadow: "0 0 0 0 rgba(255,122,26,.7)" }, { boxShadow: "0 0 0 14px rgba(255,122,26,0)" }], { duration: 900 }); } };

  // ======================================================== decisiones
  function renderDecisions(events) {
    const list = events.filter((e) => e.alcance !== "unidad")
      .sort((a, b) => (a.decision ? 1 : 0) - (b.decision ? 1 : 0) || (b.afectados - a.afectados));
    $("twEventsCount").textContent = list.length;
    // solo se re-dibuja cuando cambia algo relevante para decidir (no por cada sol de standby)
    const hash = JSON.stringify(list.map((e) => [e.id, e.afectados, e.decision && e.decision.opcion, Math.ceil(e.restante_h / 2), e.recomendada,
      (e.opciones || []).map((o) => [o.id, o.unidades_tarde, o.unidades])]));
    if (hash === lastDecisionsHash) return;
    lastDecisionsHash = hash;
    if (!list.length) {
      $("twDecisions").innerHTML = `<div class="tw-empty"><i class="fa-solid fa-circle-check"></i><div><b>Red sin eventos activos.</b><br>Lanza un escenario peruano o inyecta un evento en el mapa para ver cómo responde la IA.</div></div>`;
      return;
    }
    const box = $("twDecisions"), keepScroll = box.scrollTop;
    box.innerHTML = list.map((e) => {
      const color = SEV_COLOR[e.severidad] || "#94a3b8";
      const rutas = e.rutas.slice(0, 4).map((r) => `<span class="tw-chip">${esc(r)}</span>`).join("") + (e.rutas.length > 4 ? `<span class="tw-chip">+${e.rutas.length - 4}</span>` : "");
      const opts = (e.opciones || []).map((o) => `
        <div class="tw-opt ${o.recomendada ? "rec" : ""}">
          <div class="tw-opt-name"><i class="fa-solid ${o.icon}"></i>${esc(o.nombre)}</div>
          ${o.recomendada ? `<span class="tw-chip orange" style="align-self:flex-start;"><i class="fa-solid fa-star"></i> IA recomienda</span>` : ""}
          <div class="tw-opt-desc">${esc(o.descripcion)}</div>
          <div class="tw-opt-kpis">
            <span>Tiempo <b>${o.delta_horas >= 0 ? "+" : ""}${gdFormatNumber(o.delta_horas, 1)} h</b></span>
            <span>Costo <b>${gdFormatPENShort(o.costo_pen)}</b></span>
            <span>Tarde <b>${o.unidades_tarde}/${o.unidades}</b></span>
            <span>CO₂ <b>${o.co2_kg >= 0 ? "+" : ""}${gdFormatNumber(o.co2_kg / 1000, 1)} t</b></span>
          </div>
          <div class="tw-score" title="Puntaje compuesto ${o.score}/100"><div style="width:${o.score}%"></div></div>
          ${e.decision ? "" : `<button class="gd-btn ${o.recomendada ? "gd-btn-accent" : "gd-btn-outline"} gd-btn-sm" data-apply="${e.id}" data-opt="${o.id}">Aplicar</button>`}
        </div>`).join("");
      return `<div class="tw-ev sev-${e.severidad}" data-ev="${e.id}">
        <div class="tw-ev-head">
          <div class="tw-ev-ico" style="background:${color}"><i class="fa-solid ${e.icon}"></i></div>
          <div style="flex:1;min-width:0;">
            <div class="tw-ev-title">${esc(e.titulo)}</div>
            <div class="tw-ev-sub">${esc(e.lugar)}</div>
            <div class="tw-ev-meta">
              <span class="tw-chip red"><i class="fa-solid fa-truck"></i> ${e.afectados} afectadas</span>
              <span class="tw-chip"><i class="fa-solid fa-hourglass-half"></i> ${gdFormatNumber(e.restante_h, 1)} h restantes</span>
              ${e.valor_carga_pen ? `<span class="tw-chip orange"><i class="fa-solid fa-sack-dollar"></i> ${gdFormatPENShort(e.valor_carga_pen)} en carga</span>` : ""}
              ${e.origen === "escenario" ? `<span class="tw-chip violet">Escenario</span>` : e.origen === "manual" ? `<span class="tw-chip violet">Inyectado</span>` : ""}
            </div>
            ${rutas ? `<div class="tw-ev-meta">${rutas}</div>` : ""}
          </div>
          <button class="gd-icon-btn" title="Ver en el mapa" data-fly="${e.id}"><i class="fa-solid fa-location-dot"></i></button>
        </div>
        ${e.decision ? `<div class="tw-applied"><i class="fa-solid fa-circle-check"></i><b>${e.decision.automatico ? "IA autónoma" : "Aplicada"}:</b> ${esc(e.decision.nombre)} — ${esc(e.decision.detalle)}</div>` : ""}
        ${opts ? `<div class="tw-opts">${opts}</div>` : (e.afectados ? "" : `<div class="tw-ev-sub mt-2">Sin unidades expuestas por ahora: la IA monitorea el tramo.</div>`)}
      </div>`;
    }).join("");
    box.scrollTop = keepScroll;
    $("twDecisions").querySelectorAll("[data-apply]").forEach((b) => b.addEventListener("click", () => applyDecision(+b.dataset.apply, b.dataset.opt, b)));
    $("twDecisions").querySelectorAll("[data-fly]").forEach((b) => b.addEventListener("click", () => {
      const e = (snap.events || []).find((x) => x.id === +b.dataset.fly);
      if (e) { map.flyTo([e.lat, e.lon], 9, { duration: 1.2 }); evMarkers[e.id]?.marker.openPopup(); }
    }));
  }

  async function applyDecision(eventId, optId, btn) {
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
    try {
      const r = await RansaAPI.post("/api/live/decision", { event_id: eventId, opcion: optId });
      toast(`✔ ${r.nombre}: ${r.detalle}`);
      lastDecisionsHash = "";
      await poll();
    } catch (e) { toast(e.message); if (btn) btn.disabled = false; }
  }

  // ======================================================== feed
  function feedItemHtml(f) {
    const color = f.categoria === "decision" ? "#ff7a1a" : (SEV_COLOR[f.severidad] || "#94a3b8");
    const click = f.vehicle_id || f.event_id ? " clickable" : "";
    return `<div class="gd-feed-item cat-${f.categoria}${click}" data-v="${f.vehicle_id || ""}" data-e="${f.event_id || ""}">
      <span class="gd-dot" style="background:${color};margin-top:6px;flex-shrink:0;width:8px;height:8px;border-radius:50%;"></span>
      <div class="flex-grow-1"><div class="gd-feed-text">${esc(f.texto)}</div><div class="gd-feed-ts">${esc(f.sim_ts)} · ${esc(f.ts)}</div></div></div>`;
  }
  function prependFeed(entries) {
    if (!entries.length) return;
    feedCount += entries.length;
    $("torreFeedCount").textContent = feedCount;
    const box = $("torreFeed");
    box.insertAdjacentHTML("afterbegin", entries.slice().reverse().map(feedItemHtml).join(""));
    while (box.children.length > 150) box.removeChild(box.lastElementChild);
  }

  // ======================================================== contexto (cross-filtering)
  const ICON_BY_TIPO_FICHA = { red: "fa-diagram-project", corredor: "fa-route", nodo: "fa-location-dot", vehiculo: "fa-truck-fast" };
  async function selectRed() {
    scope = { tipo: "red", ref: null };
    renderContext(await RansaAPI.get("/api/context/red"));
    $("torreReset").style.display = "none";
    highlightRoutes(null);
  }
  async function selectCorredor(nombre) {
    scope = { tipo: "corredor", ref: nombre };
    try { renderContext(await RansaAPI.get(`/api/context/corredor?nombre=${encodeURIComponent(nombre)}`)); } catch (e) { return; }
    $("torreReset").style.display = "inline-flex";
    highlightRoutes(nombre);
    showTab("contexto");
  }
  async function selectNodo(nombre) {
    scope = { tipo: "nodo", ref: nombre };
    try { renderContext(await RansaAPI.get(`/api/context/nodo?municipio=${encodeURIComponent(nombre)}`)); } catch (e) { return; }
    $("torreReset").style.display = "inline-flex";
    highlightRoutes(null);
    showTab("contexto");
  }
  function highlightRoutes(corredor) {
    Object.values(routeLines).forEach(({ line, style }) => line.setStyle(style));
    if (!corredor) return;
    Object.entries(routeLines).forEach(([rid, { line }]) => {
      if (routesById[rid].corredor === corredor) { line.setStyle({ color: "#ff7a1a", weight: 5, opacity: .95 }); line.bringToFront(); }
    });
  }
  function renderContext(ficha) {
    $("inspTitulo").textContent = ficha.titulo;
    $("inspSub").textContent = ficha.subtitulo;
    $("inspIcon").innerHTML = `<i class="fa-solid ${ficha.icono || ICON_BY_TIPO_FICHA[ficha.tipo] || "fa-diagram-project"}"></i>`;
    $("torreKpiRow").innerHTML = ficha.kpis.slice(0, 6).map((k) => `<div class="tw-kpi"><div class="l"><i class="fa-solid ${k.icon}"></i>${esc(k.label)}</div><div class="v">${gdFormatByUnit(k.value, k.unit)}</div></div>`).join("");
    const sede = scope.tipo === "nodo" ? sedeByNode[scope.ref] : null;
    $("inspSede").style.display = sede ? "block" : "none";
    if (sede) {
      $("inspSede").innerHTML = `<div class="t"><i class="fa-solid fa-building"></i> Sede RANSA · ${esc(sede.titulo)}</div><div>${esc(sede.detalle)}</div>
        <a href="${sede.fuente.url}" target="_blank" rel="noopener">${esc(sede.fuente.medio)}, ${esc(sede.fuente.fecha)}</a>`;
    }
    const f = ficha.flujo, pred = f.prediccion;
    const predColor = pred.prob_pct >= 60 ? "var(--gd-danger)" : pred.prob_pct >= 35 ? "#b8860b" : "var(--gd-success)";
    $("inspFlujo").innerHTML = `
      <div class="gd-flow-step"><span class="gd-flow-dot s1"></span><div class="k">Estado actual</div><div class="v">${esc(f.estado)}</div></div>
      <div class="gd-flow-step"><span class="gd-flow-dot s2"></span><div class="k">Predicción</div><div class="v">${esc(pred.texto)} <b style="color:${predColor}">(${gdFormatPct(pred.prob_pct, 0)} · impacto ${esc(pred.impacto)})</b></div></div>
      <div class="gd-flow-step"><span class="gd-flow-dot s3"></span><div class="k">Plan recomendado</div><div class="v"><b>${esc(f.plan)}</b></div></div>
      <div class="gd-flow-step"><span class="gd-flow-dot s4"></span><div class="k">Resultado esperado</div><div class="v">${esc(f.resultado)}</div></div>`;
    renderInspChart(ficha.serie);
  }
  function renderInspChart(serie) {
    const wrap = $("inspChartWrap");
    if (inspChart) { inspChart.destroy(); inspChart = null; }
    if (!serie || !serie.labels.length) { wrap.style.display = "none"; return; }
    wrap.style.display = "block";
    inspChart = new Chart($("inspChart"), {
      type: "line",
      data: { labels: serie.labels, datasets: [
        { label: "Lead Time (días)", data: serie.leadtime, borderColor: "#3d63ff", backgroundColor: "rgba(61,99,255,.08)", yAxisID: "y", tension: .35, fill: true, pointRadius: 0 },
        { label: "OTIF (%)", data: serie.otif, borderColor: "#ff7a1a", backgroundColor: "rgba(255,122,26,.08)", yAxisID: "y1", tension: .35, fill: true, pointRadius: 0 },
      ] },
      options: { maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 10 }, boxWidth: 10 } } },
        scales: { x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 9 }, maxTicksLimit: 6 } },
          y: { position: "left", grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 9 } } },
          y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 9 } }, min: 0, max: 100 } } },
    });
  }

  // ======================================================== unidad
  function selectVehicle(id) {
    selectedId = id;
    const e = veh[id];
    if (!e) return;
    Object.values(veh).forEach((x) => { x.sel = null; });
    upsertVehicles(snap.vehicles.filter(passFilter));
    showTab("unidad");
    renderUnit(true);
    selectCorredorSilently(e.data.corredor);
  }
  async function selectCorredorSilently(nombre) {
    scope = { tipo: "corredor", ref: nombre };
    try { renderContext(await RansaAPI.get(`/api/context/corredor?nombre=${encodeURIComponent(nombre)}`)); $("torreReset").style.display = "inline-flex"; } catch (e) {}
    highlightRoutes(nombre);
  }
  function clearUnit() {
    selectedId = null; follow = false;
    $("twUnit").style.display = "none"; $("twUnitEmpty").style.display = "flex";
    if (profileChart) { profileChart.destroy(); profileChart = null; profileRouteId = null; }
  }
  function tel(label, value, opts = {}) {
    const bar = opts.bar != null ? `<div class="bar"><div style="width:${Math.max(0, Math.min(100, opts.bar))}%;background:${opts.color || "#3d63ff"}"></div></div>` : "";
    return `<div class="tw-tel ${opts.alert ? "alert" : ""}"><div class="l">${label}</div><div class="v">${value}</div>${bar}</div>`;
  }
  function renderUnit(full) {
    const e = veh[selectedId];
    if (!e) { clearUnit(); return; }
    const v = e.data;
    $("twUnitEmpty").style.display = "none"; $("twUnit").style.display = "block";
    $("twUnitIcon").style.background = STATE_COLOR[v.estado] || "#3d63ff";
    $("twUnitIcon").innerHTML = `<i class="fa-solid ${MODE_ICON[v.tipo_transporte] || "fa-truck"}"></i>`;
    $("twUnitId").textContent = v.id;
    $("twUnitName").textContent = v.tipo_transporte === "Carretero" ? `Placa ${v.nombre}` : v.nombre;
    $("twUnitSub").innerHTML = `${esc(v.origen.nombre)} → ${esc(v.destino.nombre)} · ${esc(v.tipo_vehiculo)}
      <div class="tw-unit-tags"><span class="tw-chip"><i class="fa-solid ${LINEA_ICON[v.linea] || "fa-boxes-stacked"}"></i> ${esc(v.linea)}</span>
      <span class="tw-chip ${/GNL|GNV/.test(v.combustible_tipo) ? "green" : ""}"><i class="fa-solid fa-gas-pump"></i> ${esc(v.combustible_tipo)}</span></div>`;
    $("twUnitState").textContent = ESTADO_TXT[v.estado] || v.estado;
    $("twUnitState").className = `tw-chip ${v.estado === "detenido" ? "red" : v.estado === "desviado" ? "violet" : v.otif_proyectado ? "green" : "orange"}`;
    const pct = v.km_total ? (e.kmShown / v.km_total) * 100 : 0;
    $("twUnitBar").style.width = `${pct}%`;
    $("twUnitKm").textContent = `${gdFormatNumber(e.kmShown, 0)} / ${gdFormatNumber(v.km_total, 0)} km`;
    const eta = new Date(v.eta), prog = new Date(v.eta_prog);
    const fmt = (d) => d.toLocaleString("es-PE", { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "America/Lima" });
    $("twUnitEta").innerHTML = v.otif_proyectado
      ? `ETA ${fmt(eta)} · <b style="color:var(--gd-success)">a tiempo</b>`
      : `ETA ${fmt(eta)} · <b style="color:var(--gd-danger)">+${gdFormatNumber(v.retraso_h, 1)} h vs ${fmt(prog)}</b>`;
    const alertBox = $("twUnitAlert");
    if (v.evento) {
      alertBox.style.display = "block";
      alertBox.innerHTML = `<i class="fa-solid ${v.evento.icon}" style="color:${SEV_COLOR[v.evento.severidad]}"></i> <b>${esc(v.evento.titulo)}</b> · ${esc(v.evento.efecto)}` +
        (v.evento.event_id ? ` · <a href="#" onclick="window.twGoDecision(${v.evento.event_id});return false;">ver decisión IA</a>` : "");
    } else alertBox.style.display = "none";

    const t = v.telemetria;
    const parts = [
      tel("Velocidad", `${gdFormatNumber(MOVING.has(v.estado) ? v.v_kmh : 0, 0)} km/h`),
      tel(v.tipo_transporte === "Aéreo" ? "Altitud vuelo" : "Altitud", `${gdFormatNumber(v.alt, 0)} m`, { bar: v.alt / (v.tipo_transporte === "Aéreo" ? 110 : 50), color: "#8b5cf6" }),
      tel("Riesgo IA", gdFormatPct(v.prob_riesgo, 0), { bar: v.prob_riesgo, color: v.prob_riesgo >= 60 ? "#e11d48" : v.prob_riesgo >= 35 ? "#eab308" : "#16a34a" }),
    ];
    if (v.tipo_transporte === "Carretero") {
      parts.push(tel("Combustible", `${t.combustible_pct}%`, { bar: t.combustible_pct, color: t.combustible_pct < 25 ? "#e11d48" : "#16a34a", alert: t.combustible_pct < 20 }));
      parts.push(tel("Motor", `${gdFormatNumber(t.temp_motor_c, 0)} °C`, { bar: (t.temp_motor_c - 60) * 2, color: t.temp_motor_c > 100 ? "#e11d48" : "#f97316", alert: t.temp_motor_c > 102 }));
      parts.push(tel("Conducción", `${gdFormatNumber(t.horas_conduccion, 1)} / 5 h`, { bar: t.horas_conduccion / 5 * 100, color: t.horas_conduccion > 4.5 ? "#e11d48" : "#3d63ff" }));
      if (t.reefer_c != null) {
        const exc = Math.abs(t.reefer_c - t.reefer_set_c) > 3;
        parts.push(tel("Cadena de frío", `${gdFormatNumber(t.reefer_c, 1)} °C`, { bar: 100 - Math.min(100, Math.abs(t.reefer_c - t.reefer_set_c) * 18), color: exc ? "#e11d48" : "#0891b2", alert: exc }));
      }
    }
    parts.push(tel("Costo extra", gdFormatPENShort(v.costo_extra_pen)));
    parts.push(tel("CO₂", `${gdFormatNumber(v.co2_kg / 1000, 2)} t`));
    $("twUnitTelemetry").innerHTML = parts.join("");
    $("twUnitCargo").innerHTML = `
      <div>Carga<b>${esc(v.tipo_carga)}</b></div><div>Cliente (sector)<b>${esc(v.sector_cliente)}</b></div>
      <div>Prioridad<b>${esc(v.prioridad_cliente)}</b></div><div>Valor asegurado<b>${gdFormatPENShort(v.valor_carga_pen)}</b></div>
      <div>Corredor<b>${esc(v.corredor)}</b></div><div>Embarque histórico<b class="gd-mono">${esc(v.id_viaje || "—")}</b></div>`;
    renderProfile(v, e, full);
  }
  function renderProfile(v, e, full) {
    const route = e.route;
    const rid = v.custom_route ? `custom:${v.id}:${v.km_total}` : v.route_id;
    let prof = route.profile;
    if (v.tipo_transporte === "Aéreo") {
      const n = 40, km = route.cum_km[route.cum_km.length - 1];
      const xs = Array.from({ length: n + 1 }, (_, i) => km * i / n);
      prof = { km: xs, alt: xs.map((x) => Math.min(10500, Math.min(x, km - x) * 95)) };
    }
    if (!prof || !prof.km || prof.km.length < 2 || (v.tipo_transporte !== "Carretero" && v.tipo_transporte !== "Aéreo")) {
      $("twProfileMax").textContent = v.tipo_transporte === "Marítimo" ? "· navegación a nivel del mar" : v.tipo_transporte === "Fluvial" ? "· navegación fluvial (~110 m s. n. m.)" : "";
      if (profileChart) { profileChart.destroy(); profileChart = null; profileRouteId = null; }
      return;
    }
    const kmNow = e.kmShown * (prof.km[prof.km.length - 1] / (v.km_total || 1));
    const altNow = interp(prof.km, prof.alt, kmNow);
    if (profileChart && profileRouteId === rid && !full) {
      profileChart.data.datasets[1].data = [{ x: kmNow, y: altNow }];
      profileChart.update("none");
      return;
    }
    if (profileChart) profileChart.destroy();
    profileRouteId = rid;
    let iMax = 0;
    prof.alt.forEach((a, i) => { if (a > prof.alt[iMax]) iMax = i; });
    const peakName = peakLabel(route, prof.km[iMax]);
    $("twProfileMax").textContent = v.tipo_transporte === "Aéreo" ? "· crucero ~10.500 m" : `· máx ${gdFormatNumber(prof.alt[iMax], 0)} m${peakName ? ` (${peakName})` : ""}`;
    profileChart = new Chart($("twProfileChart"), {
      type: "line",
      data: { datasets: [
        { label: "Altitud", data: prof.km.map((k, i) => ({ x: k, y: prof.alt[i] })), borderColor: "#8b5cf6", backgroundColor: "rgba(139,92,246,.14)", fill: true, pointRadius: 0, tension: .25, borderWidth: 2 },
        { label: "Unidad", data: [{ x: kmNow, y: altNow }], type: "scatter", pointRadius: 7, pointBackgroundColor: "#ff7a1a", pointBorderColor: "#fff", pointBorderWidth: 2 },
        { label: "Punto más alto", data: [{ x: prof.km[iMax], y: prof.alt[iMax] }], type: "scatter", pointRadius: 4, pointStyle: "triangle", pointBackgroundColor: "#e11d48" },
      ] },
      options: { maintainAspectRatio: false, parsing: false, animation: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${gdFormatNumber(c.parsed.y, 0)} m · km ${gdFormatNumber(c.parsed.x, 0)}` } } },
        scales: { x: { type: "linear", min: 0, max: prof.km[prof.km.length - 1], title: { display: true, text: "km", font: { size: 10 } }, grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 9 }, maxTicksLimit: 7 } },
          y: { min: 0, title: { display: true, text: "m s. n. m.", font: { size: 10 } }, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 9 } } } } },
    });
  }
  function interp(xs, ys, x) {
    if (x <= xs[0]) return ys[0];
    for (let i = 1; i < xs.length; i++) if (xs[i] >= x) { const f = (x - xs[i - 1]) / ((xs[i] - xs[i - 1]) || 1); return ys[i - 1] + (ys[i] - ys[i - 1]) * f; }
    return ys[ys.length - 1];
  }
  function peakLabel(route, km) {
    const p = pointAt(route.geometry, route.cum_km, km);
    if (!p || !net) return "";
    let best = null, bd = 1e9;
    net.hotspots.forEach((h) => { const d = Math.hypot(h.lat - p.lat, (h.lon - p.lon) * Math.cos(p.lat * Math.PI / 180)) * 111; if (d < bd) { bd = d; best = h; } });
    return best && bd < 25 ? best.nombre.split(" (")[0] : "";
  }
  function updateFollowBtn() { $("twFollow").innerHTML = follow ? '<i class="fa-solid fa-crosshairs"></i> Siguiendo…' : '<i class="fa-solid fa-crosshairs"></i> Seguir unidad'; }

  // ======================================================== nodos
  function renderNodes(nodos) {
    const hash = JSON.stringify(nodos.map((n) => [n.nombre, n.estado, n.llegando, n.en_cola, n.ocupacion_pct]));
    if (hash === lastNodesHash) return;
    lastNodesHash = hash;
    $("twNodes").innerHTML = nodos.map((n) => {
      const chip = n.estado === "cerrado" ? "red" : n.estado === "congestionado" ? "orange" : "green";
      const icon = n.es_puerto ? "fa-anchor" : n.es_fluvial ? "fa-water" : "fa-warehouse";
      return `<div class="tw-node-row" data-node="${esc(n.nombre)}">
        <i class="fa-solid ${icon}" style="color:var(--gd-accent);width:18px;text-align:center;"></i>
        <div style="flex:1;min-width:0;"><div class="n">${esc(n.nombre)}${sedeByNode[n.nombre] ? ' <span class="tw-sede-badge">Sede RANSA</span>' : ""}</div><div class="s">${n.llegando} llegando · ${n.en_cola} en cola · ocupación ${n.ocupacion_pct}%</div></div>
        <div class="occ"><div style="width:${n.ocupacion_pct}%;background:${n.ocupacion_pct > 88 ? "#e11d48" : n.ocupacion_pct > 75 ? "#eab308" : "#3d63ff"}"></div></div>
        <span class="tw-chip ${chip}">${n.estado}</span></div>`;
    }).join("");
    $("twNodes").querySelectorAll(".tw-node-row").forEach((row) => row.addEventListener("click", () => {
      const n = nodos.find((x) => x.nombre === row.dataset.node);
      if (n) { map.flyTo([n.lat, n.lon], 9, { duration: 1 }); selectNodo(n.nombre); }
    }));
    // estado visual de los nodos en el mapa (puerto cerrado / congestionado)
    nodos.forEach((n) => {
      const el = document.querySelector(`.tw-node[data-node="${CSS.escape(n.nombre)}"]`);
      if (el) { el.classList.toggle("cerrado", n.estado === "cerrado"); el.classList.toggle("congestionado", n.estado === "congestionado"); }
    });
  }

  // ======================================================== polling
  function passFilter(v) { return !modeFilter || v.tipo_transporte === modeFilter; }

  async function poll() {
    if (document.hidden && snap) return;
    try {
      const data = await RansaAPI.get(`/api/live/poll?since_id=${sinceId}`);
      snap = data; snapAt = performance.now();
      sinceId = data.last_id || sinceId;
      renderOpsKpis(data.kpis);
      upsertVehicles(data.vehicles.filter(passFilter));
      renderEvents(data.events);
      renderDecisions(data.events);
      renderNodes(data.nodos);
      prependFeed(data.feed || []);
      syncControls(data);
      if (selectedId) renderUnit(false);
    } catch (e) { /* reintenta en la siguiente vuelta */ }
  }

  function syncControls(d) {
    $("twPlay").innerHTML = d.paused ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-pause"></i>';
    $("twLivePill").classList.toggle("paused", d.paused);
    $("twLivePill").innerHTML = `<span class="gd-live-dot"></span> ${d.paused ? "En pausa" : "En vivo"}`;
    document.querySelectorAll("#twSpeed button").forEach((b) => b.classList.toggle("active", +b.dataset.speed === d.speed));
    $("twAuto").checked = !!d.autonomo;
  }

  async function control(body) {
    try { const s = await RansaAPI.post("/api/live/control", body); if (snap) Object.assign(snap, s); syncControls(snap || s); poll(); } catch (e) { toast(e.message); }
  }

  // ======================================================== escenarios / inyección
  async function loadCatalog() {
    try { catalog = await RansaAPI.get("/api/live/catalog"); } catch (e) { return; }
    $("twScenarioMenu").innerHTML = catalog.escenarios.map((s) => `
      <div class="tw-scn" data-scn="${s.id}"><div class="ico"><i class="fa-solid ${s.icon}"></i></div><div><b>${esc(s.titulo)}</b><span>${esc(s.descripcion)}</span></div></div>`).join("");
    $("twScenarioMenu").querySelectorAll("[data-scn]").forEach((el) => el.addEventListener("click", () => runScenario(el.dataset.scn)));
    $("twInjectMenu").innerHTML = `<div class="tw-panel-title px-1"><i class="fa-solid fa-hand-pointer"></i> Elige el evento y haz clic en el mapa</div>
      <div class="tw-inject-grid">${catalog.eventos.map((ev) => `<button data-tipo="${ev.tipo}"><i class="fa-solid ${ev.icon}"></i>${esc(ev.titulo)}</button>`).join("")}</div>`;
    $("twInjectMenu").querySelectorAll("[data-tipo]").forEach((b) => b.addEventListener("click", () => startInject(b.dataset.tipo, b.textContent.trim())));
  }
  async function runScenario(id, { fly = true } = {}) {
    try {
      const r = await RansaAPI.post("/api/live/scenario", { id });
      toast(`⚡ Escenario activado: ${r.titulo}`);
      await poll();
      if (fly) {
        const evs = (snap.events || []).filter((e) => r.eventos.includes(e.id));
        if (evs.length === 1) map.flyTo([evs[0].lat, evs[0].lon], 9, { duration: 1.4 });
        else if (evs.length > 1) map.flyToBounds(L.latLngBounds(evs.map((e) => [e.lat, e.lon])).pad(0.6), { duration: 1.4 });
      }
      return r;
    } catch (e) { toast(e.message); return null; }
  }
  function startInject(tipo, titulo) {
    injectTipo = tipo;
    map.getContainer().classList.add("tw-injecting");
    showBanner(`<i class="fa-solid fa-location-crosshairs"></i> Haz clic sobre una vía del mapa para ubicar: <b>${esc(titulo)}</b>`, [{ label: "Cancelar", cls: "stop", fn: stopInject }]);
  }
  function stopInject() { injectTipo = null; map.getContainer().classList.remove("tw-injecting"); hideBanner(); }
  async function onMapClick(e) {
    if (!injectTipo) return;
    const tipo = injectTipo;
    stopInject();
    try {
      const r = await RansaAPI.post("/api/live/events", { tipo, lat: e.latlng.lat, lon: e.latlng.lng });
      toast(`📍 ${r.titulo} en ${r.lugar}`);
      await poll();
    } catch (err) { toast(err.message); }
  }

  // ======================================================== UI helpers
  function showTab(name) {
    document.querySelectorAll("#twTabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
    document.querySelectorAll(".tw-tab").forEach((p) => { p.style.display = p.dataset.pane === name ? "block" : "none"; });
  }
  let toastTimer = null;
  function toast(msg) {
    const t = $("twToast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("show"), 4200);
  }
  function showBanner(html, buttons = []) {
    const b = $("twBanner");
    b.innerHTML = `<div style="flex:1;">${html}</div>` + buttons.map((x, i) => `<button class="${x.cls}" data-bi="${i}">${x.label}</button>`).join("");
    b.style.display = "flex";
    b.querySelectorAll("[data-bi]").forEach((el) => el.addEventListener("click", () => buttons[+el.dataset.bi].fn()));
  }
  function hideBanner() { $("twBanner").style.display = "none"; }

  // ======================================================== modo presentación
  const TOUR = [
    { t: "La red RANSA en vivo: sus sedes públicas (Callao, Lima, Chancay, Chiclayo, Arequipa…) y 60 unidades —camiones, cabotaje, convoyes amazónicos y vuelos— sobre las vías reales del Perú.",
      run: async () => { map.flyToBounds(PERU_BOUNDS, { duration: 1.2 }); showTab("contexto"); selectRed(); } },
    { t: "Los Andes cambian todo: seguimos un camión por la Carretera Central y vemos su perfil de altitud rumbo a Ticlio (4,818 m).",
      run: async () => {
        const cands = Object.values(veh).filter((e) => e.data.tipo_transporte === "Carretero" && (routesById[e.data.route_id]?.alt_max || 0) > 4000);
        const pick = cands.find((e) => /Huancayo|Pasco|Huánuco|Pucallpa/.test(e.data.corredor)) || cands[0];
        if (pick) { selectVehicle(pick.data.id); follow = true; updateFollowBtn(); map.setZoom(8); }
      } },
    { t: "Temporada de lluvias: un huaico corta la Carretera Central en Chosica. Todas las rutas que pasan por ese punto quedan afectadas.",
      run: async () => { follow = false; await runScenario("huaico_carretera_central"); } },
    { t: "La IA compara esperar, desviar por la ruta alterna real (Cañete–Lunahuaná / Canta–Huayllay) o congelar despachos, y recomienda la mejor.",
      run: async () => {
        const e = (snap.events || []).find((x) => x.tipo === "huaico" && !x.decision);
        if (e) { window.twGoDecision(e.id); if (e.recomendada) await applyDecision(e.id, e.recomendada); }
      } },
    { t: "Ahora el mar: la DHN cierra el Callao por oleaje anómalo. Los buques fondean… o se desvían al megapuerto de Chancay.",
      run: async () => { await runScenario("oleaje_callao"); } },
    { t: "Decisión aplicada: buques a Chancay y última milla por la Panamericana Norte.",
      run: async () => {
        const e = (snap.events || []).find((x) => x.tipo === "oleaje" && !x.decision);
        if (e && e.recomendada) await applyDecision(e.id, e.recomendada);
      } },
    { t: "Resultado en tiempo real: OTIF proyectado, carga protegida, costo de contingencia y CO₂ — todo trazable en la bitácora.",
      run: async () => { map.flyToBounds(PERU_BOUNDS, { duration: 1.2 }); document.getElementById("torreOpsKpis").scrollIntoView({ behavior: "smooth", block: "center" });
        document.querySelectorAll(".torre-ops-item").forEach((el) => { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }); } },
  ];
  async function tourStep(i) {
    if (i >= TOUR.length) { tour = null; hideBanner(); toast("Fin de la presentación. ¡El gemelo sigue en vivo!"); return; }
    tour = i;
    showBanner(`<div class="step">Paso ${i + 1} de ${TOUR.length}</div>${esc(TOUR[i].t)}`,
      [{ label: i === TOUR.length - 1 ? "Terminar" : "Siguiente ›", cls: "next", fn: () => tourStep(i + 1) }, { label: "Salir", cls: "stop", fn: () => { tour = null; hideBanner(); } }]);
    try { await TOUR[i].run(); } catch (e) { /* el paso sigue aunque falle una acción */ }
  }

  function copilotPrompt() {
    if (selectedId && veh[selectedId]) { const v = veh[selectedId].data; return `Analiza el embarque ${v.id_viaje || v.id} del corredor ${v.corredor}.`; }
    if (scope.tipo === "corredor") return `Analiza el corredor ${scope.ref}: riesgos y qué debo hacer.`;
    if (scope.tipo === "nodo") return `¿Qué pasa si cierro ${scope.ref}?`;
    return "¿Qué está pasando ahora en el gemelo?";
  }

  // ======================================================== arranque
  document.addEventListener("DOMContentLoaded", async () => {
    initMap();
    wireControls();  // los controles responden desde el primer segundo, aunque la red siga cargando
    const [network, routesRisk] = await Promise.all([
      RansaAPI.get("/api/live/network"),
      RansaAPI.get("/api/map/routes").catch(() => ({ routes: [] })),
    ]);
    net = network;
    routesRisk.routes.forEach((r) => {
      // /api/map/routes no distingue modo: se asigna al carretero salvo rutas exclusivas de otro modo
      routeRisk[`${r.corredor}|Carretero`] = r; routeRisk[`${r.corredor}|Marítimo`] = r; routeRisk[`${r.corredor}|Fluvial`] = r;
    });
    drawNetwork();
    loadHeat();
    loadCatalog();
    await Promise.all([selectRed(), poll()]);
    requestAnimationFrame(animate);
    setInterval(poll, POLL_MS);
    setInterval(() => { if (scope.tipo === "red") selectRed(); }, 60000);
  });

  function wireControls() {
    $("torreReset").addEventListener("click", selectRed);
    document.querySelectorAll("#twModes button").forEach((b) => b.addEventListener("click", () => {
      modeFilter = b.dataset.modo;
      document.querySelectorAll("#twModes button").forEach((x) => x.classList.toggle("active", x === b));
      lastDecisionsHash = "";
      if (snap) upsertVehicles(snap.vehicles.filter(passFilter));
      poll();
    }));
    $("inspCopilot").addEventListener("click", () => window.gdOpenCopilot && window.gdOpenCopilot(copilotPrompt()));
    $("twUnitCopilot").addEventListener("click", () => window.gdOpenCopilot && window.gdOpenCopilot(copilotPrompt()));
    $("twFollow").addEventListener("click", () => { follow = !follow; updateFollowBtn(); if (follow) map.setZoom(Math.max(map.getZoom(), 8)); });
    document.querySelectorAll("#twTabs button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
    document.querySelectorAll("#twBasemap button").forEach((b) => b.addEventListener("click", () => setBase(b.dataset.base === "claro" && isDark() ? "oscuro" : b.dataset.base)));
    document.querySelectorAll("[data-layer]").forEach((cb) => cb.addEventListener("change", () => {
      const groups = { sedes: [L_.sedes], hotspots: [L_.hotspots], calor: [L_.calor] };
      (groups[cb.dataset.layer] || []).forEach((g) => { if (!g) return; if (cb.checked) g.addTo(map); else map.removeLayer(g); });
    }));
    $("twPlay").addEventListener("click", () => control({ paused: !(snap && snap.paused) }));
    document.querySelectorAll("#twSpeed button").forEach((b) => b.addEventListener("click", () => control({ speed: +b.dataset.speed })));
    $("twAuto").addEventListener("change", (e) => control({ autonomo: e.target.checked }));
    $("twReset").addEventListener("click", async () => {
      if (!confirm("¿Reiniciar el gemelo digital? Se borran eventos y decisiones de la sesión simulada.")) return;
      await RansaAPI.post("/api/live/reset"); lastDecisionsHash = ""; clearUnit(); toast("Gemelo digital reiniciado."); poll();
    });
    $("twTourBtn").addEventListener("click", () => tourStep(0));
    $("twLayersToggle").addEventListener("click", () => $("twLayersPanel").classList.toggle("collapsed"));
    $("torreFeed").addEventListener("click", (ev) => {
      const item = ev.target.closest(".gd-feed-item");
      if (!item) return;
      if (item.dataset.v && veh[item.dataset.v]) { selectVehicle(item.dataset.v); const p = veh[item.dataset.v].marker.getLatLng(); map.flyTo(p, 9, { duration: 1 }); }
      else if (item.dataset.e) { const e = (snap.events || []).find((x) => x.id === +item.dataset.e); if (e) map.flyTo([e.lat, e.lon], 9, { duration: 1 }); }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && injectTipo) stopInject(); });
    document.addEventListener("gd-theme-changed", (e) => {
      if (e.detail.theme === "dark" && currentBase === "claro") setBase("oscuro");
      if (e.detail.theme === "light" && currentBase === "oscuro") setBase("claro");
    });
  }
})();
