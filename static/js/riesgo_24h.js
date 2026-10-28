(function () {
  let map, heatLayer, nodesLayer, routesLayer;
  let allEventos = [];
  let filteredEventos = [];
  let activeFilter = null;
  let selectedIdx = -1;
  let autoInterval = null;
  let markerMap = {};
  let routeMap = {};
  let destMarkerMap = {};
  const PERU_BOUNDS = [[-18.4, -81.4], [-0.1, -68.6]];

  const CATS = {
    geologico:       { label: "Geológico",       icon: "fa-mountain",                color: "#92400e" },
    hidrologico:     { label: "Hidrológico",      icon: "fa-water",                   color: "#0369a1" },
    social:          { label: "Social",           icon: "fa-people-group",            color: "#7c3aed" },
    infraestructura: { label: "Infraestructura",  icon: "fa-road-circle-exclamation",  color: "#b45309" },
    seguridad:       { label: "Seguridad",        icon: "fa-shield-halved",           color: "#be123c" },
    accidentalidad:  { label: "Accidentalidad",   icon: "fa-car-burst",               color: "#dc2626" },
  };

  function initMap() {
    map = L.map("predMap", { scrollWheelZoom: true, minZoom: 4 }).fitBounds(PERU_BOUNDS);
    // si la página abrió en la pestaña 48 h, el mapa nació oculto: reencuadrar al mostrarlo
    window.addEventListener("gd:vista", (e) => {
      if (e.detail !== "24h") return;
      map.invalidateSize();
      if (selectedIdx < 0) map.fitBounds(PERU_BOUNDS);
      if (heatLayer && !map.hasLayer(heatLayer)) heatLayer.addTo(map);
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    nodesLayer = L.layerGroup().addTo(map);
    routesLayer = L.layerGroup().addTo(map);
  }

  function kpiTile({ icon, bg, label, value, sub }) {
    return `<div class="col-6 col-lg-3">
      <div class="gd-kpi">
        <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
        <div class="gd-kpi-label">${label}</div>
        <div class="gd-kpi-value">${value}</div>
        ${sub ? `<div class="gd-kpi-delta" style="color:var(--gd-text-muted);">${sub}</div>` : ""}
      </div>
    </div>`;
  }

  function renderKpis(eventos) {
    const corredores = new Set(eventos.map(e => e.corredor));
    const vehiculos = eventos.reduce((s, e) => s + (e.vehiculos_en_ruta_ahora || 0), 0);
    const clientes = eventos.reduce((s, e) => s + (e.clientes_criticos_expuestos || 0), 0);
    const costo = eventos.reduce((s, e) => s + (e.costo_en_riesgo_pen || 0), 0);
    document.getElementById("predKpiRow").innerHTML = [
      kpiTile({ icon: "fa-triangle-exclamation", bg: "gd-bg-danger", label: "Eventos detectados", value: gdFormatNumber(eventos.length, 0), sub: eventos.filter(e=>e.alerta_alta).length + " alertas altas" }),
      kpiTile({ icon: "fa-road", bg: "gd-bg-warning", label: "Corredores en observación", value: gdFormatNumber(corredores.size, 0) }),
      kpiTile({ icon: "fa-truck", bg: "gd-bg-info", label: "Vehículos en riesgo", value: gdFormatNumber(vehiculos, 0) }),
      kpiTile({ icon: "fa-sack-dollar", bg: "gd-bg-danger", label: "Costo en riesgo estimado", value: gdFormatPEN(costo) }),
    ].join("");
  }

  function renderFilters(eventos) {
    const counts = {};
    eventos.forEach(e => { counts[e.categoria] = (counts[e.categoria] || 0) + 1; });
    const box = document.getElementById("predFilters");
    let html = `<span class="pred-filter-chip active" data-cat="all"><i class="fa-solid fa-layer-group"></i> Todos <span class="chip-count">${eventos.length}</span></span>`;
    for (const [cat, meta] of Object.entries(CATS)) {
      if (!counts[cat]) continue;
      html += `<span class="pred-filter-chip" data-cat="${cat}"><i class="fa-solid ${meta.icon}"></i> ${meta.label} <span class="chip-count">${counts[cat]}</span></span>`;
    }
    box.innerHTML = html;
    box.querySelectorAll(".pred-filter-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const cat = chip.dataset.cat;
        activeFilter = cat === "all" ? null : cat;
        box.querySelectorAll(".pred-filter-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        applyFilter();
      });
    });
  }

  function renderLegend() {
    const box = document.getElementById("predLegend");
    box.innerHTML = Object.values(CATS).map(m =>
      `<span class="pred-legend-item"><span class="pred-legend-dot" style="background:${m.color}"></span>${m.label}</span>`
    ).join("");
  }

  function applyFilter() {
    filteredEventos = activeFilter ? allEventos.filter(e => e.categoria === activeFilter) : [...allEventos];
    renderEventos(filteredEventos);
    renderNodesAndRoutes(filteredEventos);
    document.getElementById("predEventCount").textContent = `${filteredEventos.length} evento${filteredEventos.length !== 1 ? "s" : ""}`;
    deselectAll();
    fitAllMarkers(filteredEventos);
  }

  function impactoBadge(nivel) {
    const cls = nivel === "Muy Alto" ? "rojo" : nivel === "Alto" ? "amarillo" : "gris";
    return `<span class="gd-badge ${cls}"><span class="gd-dot ${cls}"></span>${nivel}</span>`;
  }

  function alertaBadge(alta) {
    if (alta) return `<span class="gd-badge rojo" style="font-size:10px;"><i class="fa-solid fa-circle-exclamation me-1"></i>Alerta alta</span>`;
    return `<span class="gd-badge gris" style="font-size:10px;"><i class="fa-solid fa-eye me-1"></i>En observación</span>`;
  }

  function eventCardHtml(e, idx) {
    return `<div class="gd-event-card" data-idx="${idx}">
      <div class="gd-event-card-head">
        <div class="gd-event-card-icon" style="background:${e.color};"><i class="fa-solid ${e.icon}"></i></div>
        <div>
          <div class="gd-event-card-title">${e.titulo}</div>
          <div class="gd-event-card-sub">${e.corredor} · ${e.tipo_transporte}</div>
          <div class="mt-1">${impactoBadge(e.impacto_nivel)} ${alertaBadge(e.alerta_alta)}</div>
        </div>
        <div class="gd-event-card-prob">
          <div class="val" style="color:${e.color}">${gdFormatPct(e.probabilidad_pct, 0)}</div>
          <div class="lbl">Prob. 24h</div>
        </div>
      </div>
      <div class="gd-event-route">
        <i class="fa-solid fa-location-dot"></i> ${e.origen.nombre}
        <span class="gd-route-arrow">→</span>
        <i class="fa-solid fa-flag-checkered"></i> ${e.destino.nombre}
      </div>
      <div class="gd-event-metrics">
        <div class="gd-event-metric">Vehículos<b>${gdFormatNumber(e.vehiculos_en_ruta_ahora, 0)}</b></div>
        <div class="gd-event-metric">Clientes críticos<b>${gdFormatNumber(e.clientes_criticos_expuestos, 0)}</b></div>
        <div class="gd-event-metric">Costo en riesgo<b>${gdFormatPEN(e.costo_en_riesgo_pen)}</b></div>
        <div class="gd-event-metric">ETA adicional<b>+${gdFormatNumber(e.eta_adicional_estimada_horas)} h</b></div>
      </div>
    </div>`;
  }

  function renderEventos(eventos) {
    const box = document.getElementById("predEventos");
    if (!eventos.length) {
      box.innerHTML = `<div class="gd-empty-state"><i class="fa-regular fa-circle-check"></i><div>Sin eventos con probabilidad ≥ 80% — operación estable.</div></div>`;
      return;
    }
    box.innerHTML = eventos.map((e, i) => eventCardHtml(e, i)).join("");
    box.querySelectorAll(".gd-event-card").forEach(card => {
      card.addEventListener("click", () => selectEvent(parseInt(card.dataset.idx)));
    });
    gdInitTooltips(box);
  }

  // Offset overlapping markers so each one is visible
  function offsetCoord(lat, lon, idx, total) {
    if (total <= 1) return [lat, lon];
    const angle = (2 * Math.PI * idx) / total;
    const radius = 0.015 + (total > 4 ? 0.008 : 0);
    return [lat + radius * Math.cos(angle), lon + radius * Math.sin(angle)];
  }

  function renderNodesAndRoutes(eventos) {
    nodesLayer.clearLayers();
    routesLayer.clearLayers();
    markerMap = {};
    routeMap = {};
    destMarkerMap = {};

    // Group by origin to detect overlaps
    const originGroups = {};
    eventos.forEach((e, idx) => {
      const key = `${e.origen.lat.toFixed(3)},${e.origen.lon.toFixed(3)}`;
      if (!originGroups[key]) originGroups[key] = [];
      originGroups[key].push(idx);
    });

    eventos.forEach((e, idx) => {
      const oKey = `${e.origen.lat.toFixed(3)},${e.origen.lon.toFixed(3)}`;
      const group = originGroups[oKey];
      const posInGroup = group.indexOf(idx);
      const [oLat, oLon] = offsetCoord(e.origen.lat, e.origen.lon, posInGroup, group.length);

      // Curved route line (arc through midpoint)
      const midLat = (oLat + e.destino.lat) / 2;
      const midLon = (oLon + e.destino.lon) / 2;
      const dx = e.destino.lon - oLon;
      const dy = e.destino.lat - oLat;
      const arcOffset = 0.08 * (posInGroup - (group.length - 1) / 2);
      const arcLat = midLat + dx * arcOffset;
      const arcLon = midLon - dy * arcOffset;

      const routeLine = L.polyline(
        [[oLat, oLon], [arcLat, arcLon], [e.destino.lat, e.destino.lon]],
        { color: e.color, weight: 3, opacity: 0.55, dashArray: "8 5", smoothFactor: 2 }
      ).addTo(routesLayer);
      routeMap[idx] = routeLine;

      // Origin marker — numbered with event index
      const markerSize = 32;
      const mk = L.marker([oLat, oLon], {
        icon: L.divIcon({
          className: "pred-marker-wrap",
          html: `<div class="pred-marker" style="background:${e.color};" data-idx="${idx}">
                   <i class="fa-solid ${e.icon}"></i>
                   <span class="pred-marker-num">${idx + 1}</span>
                 </div>`,
          iconSize: [markerSize, markerSize], iconAnchor: [markerSize / 2, markerSize / 2],
        }),
        zIndexOffset: 1000 - idx,
      }).bindPopup(`
        <div class="gd-popup-title"><i class="fa-solid ${e.icon}" style="color:${e.color};margin-right:4px"></i>${e.titulo}</div>
        <div class="gd-popup-row"><b>${e.corredor}</b></div>
        <div class="gd-popup-row">${e.origen.nombre} → ${e.destino.nombre}</div>
        <div class="gd-popup-row">Probabilidad: <b style="color:${e.color}">${gdFormatPct(e.probabilidad_pct, 0)}</b> · Impacto: <b>${e.impacto_nivel}</b></div>
        <div class="gd-popup-row">Vehículos: <b>${e.vehiculos_en_ruta_ahora}</b> · Clientes: <b>${e.clientes_criticos_expuestos}</b></div>
        <div class="gd-popup-row">Costo en riesgo: <b>${gdFormatPEN(e.costo_en_riesgo_pen)}</b></div>
      `, { maxWidth: 280 }).addTo(nodesLayer);

      mk.on("click", () => selectEvent(idx));
      markerMap[idx] = mk;

      // Destination marker
      const destMk = L.marker([e.destino.lat, e.destino.lon], {
        icon: L.divIcon({
          className: "pred-dest-wrap",
          html: `<div class="pred-dest-marker" style="border-color:${e.color};"><i class="fa-solid fa-flag-checkered" style="color:${e.color};"></i></div>`,
          iconSize: [24, 24], iconAnchor: [12, 12],
        }),
      }).bindPopup(`<div class="gd-popup-title">${e.destino.nombre}</div><div class="gd-popup-row">Destino — ${e.corredor}</div>`).addTo(nodesLayer);
      destMarkerMap[idx] = destMk;
    });
  }

  function fitAllMarkers(eventos) {
    if (!eventos.length) return;
    const allPoints = [];
    eventos.forEach(e => {
      allPoints.push([e.origen.lat, e.origen.lon]);
      allPoints.push([e.destino.lat, e.destino.lon]);
    });
    const bounds = L.latLngBounds(allPoints);
    map.fitBounds(bounds.pad(0.15), { maxZoom: 10, duration: 0.5 });
  }

  function selectEvent(idx) {
    deselectAll();
    if (idx < 0 || idx >= filteredEventos.length) return;
    selectedIdx = idx;
    const e = filteredEventos[idx];

    // Highlight card
    const card = document.querySelector(`.gd-event-card[data-idx="${idx}"]`);
    if (card) {
      card.classList.add("selected", "pulse");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      setTimeout(() => card.classList.remove("pulse"), 600);
    }

    // Highlight route
    if (routeMap[idx]) {
      routeMap[idx].setStyle({ weight: 5, opacity: 1, dashArray: "10 6" });
      routeMap[idx].getElement()?.classList.add("route-active");
    }

    // Dim other routes
    Object.entries(routeMap).forEach(([k, r]) => {
      if (parseInt(k) !== idx) r.setStyle({ opacity: 0.15 });
    });

    // Highlight marker
    const mkEl = markerMap[idx]?.getElement()?.querySelector(".pred-marker");
    if (mkEl) mkEl.classList.add("pred-marker-active");

    // Zoom to the selected route
    const bounds = L.latLngBounds([
      [e.origen.lat, e.origen.lon],
      [e.destino.lat, e.destino.lon],
    ]);
    map.fitBounds(bounds.pad(0.5), { maxZoom: 10, duration: 0.5 });

    document.getElementById("predAutoStatus").textContent =
      `▸ ${idx + 1}/${filteredEventos.length} · ${e.titulo} — ${e.corredor} (${gdFormatPct(e.probabilidad_pct, 0)})`;
  }

  function deselectAll() {
    selectedIdx = -1;
    document.querySelectorAll(".gd-event-card.selected").forEach(c => c.classList.remove("selected"));
    Object.values(routeMap).forEach(r => {
      r.setStyle({ weight: 3, opacity: 0.55, dashArray: "8 5" });
      r.getElement()?.classList.remove("route-active");
    });
    document.querySelectorAll(".pred-marker-active").forEach(m => m.classList.remove("pred-marker-active"));
    document.getElementById("predAutoStatus").textContent = "";
  }

  function toggleAuto() {
    const btn = document.getElementById("predAutoBtn");
    const icon = document.getElementById("predAutoIcon");
    const label = document.getElementById("predAutoLabel");
    if (autoInterval) {
      clearInterval(autoInterval);
      autoInterval = null;
      btn.classList.remove("running");
      icon.className = "fa-solid fa-play";
      label.textContent = "Auto-simulación";
      deselectAll();
      fitAllMarkers(filteredEventos);
      return;
    }
    btn.classList.add("running");
    icon.className = "fa-solid fa-pause";
    label.textContent = "Detener";
    let cur = 0;
    selectEvent(cur);
    autoInterval = setInterval(() => {
      cur = (cur + 1) % filteredEventos.length;
      selectEvent(cur);
    }, 3500);
  }

  function renderDistribution(eventos) {
    const counts = {};
    const maxProb = {};
    eventos.forEach(e => {
      counts[e.categoria] = (counts[e.categoria] || 0) + 1;
      if (!maxProb[e.categoria] || e.probabilidad_pct > maxProb[e.categoria])
        maxProb[e.categoria] = e.probabilidad_pct;
    });
    const maxCount = Math.max(...Object.values(counts), 1);
    const box = document.getElementById("predDistRow");
    box.innerHTML = Object.entries(CATS).map(([cat, meta]) => {
      const c = counts[cat] || 0;
      const p = maxProb[cat] || 0;
      const pct = Math.round((c / maxCount) * 100);
      return `<div class="pred-dist-item" data-cat="${cat}">
        <div class="pred-dist-icon" style="background:${meta.color}"><i class="fa-solid ${meta.icon}"></i></div>
        <div class="pred-dist-label">${meta.label}</div>
        <div class="pred-dist-count">${c}</div>
        <div class="pred-dist-sub">${c ? `máx ${gdFormatPct(p, 0)}` : "sin alertas"}</div>
        <div class="pred-dist-bar"><div class="pred-dist-bar-fill" style="width:${pct}%;background:${meta.color}"></div></div>
      </div>`;
    }).join("");

    box.querySelectorAll(".pred-dist-item").forEach(item => {
      item.addEventListener("click", () => {
        const cat = item.dataset.cat;
        activeFilter = cat;
        document.querySelectorAll(".pred-filter-chip").forEach(c => {
          c.classList.toggle("active", c.dataset.cat === cat);
        });
        applyFilter();
      });
    });
  }

  function renderHeatmap(puntos) {
    if (heatLayer) map.removeLayer(heatLayer);
    heatLayer = L.heatLayer(puntos, { radius: 30, blur: 22, maxZoom: 9, max: 1.0,
      gradient: { 0.2: "#ff7a1a", 0.5: "#eab308", 0.8: "#ef4444", 1.0: "#7f1d1d" }
    });
    // con el mapa oculto (pestaña 48 h) el lienzo mide 0 px: la capa se agrega al mostrarse
    if (map.getSize().x > 0) heatLayer.addTo(map);
  }

  async function load() {
    const [{ eventos, umbral_pct }, { puntos }] = await Promise.all([
      RansaAPI.get("/api/predictive/forecast-24h"),
      RansaAPI.get("/api/predictive/heatmap"),
    ]);
    document.getElementById("gdUmbral").textContent = umbral_pct;
    document.getElementById("gdMetodoInfo").innerHTML = gdGlossaryIcon("Índice de riesgo");
    allEventos = eventos;
    filteredEventos = [...eventos];
    renderKpis(eventos);
    renderFilters(eventos);
    renderLegend();
    renderEventos(filteredEventos);
    renderHeatmap(puntos);
    renderNodesAndRoutes(filteredEventos);
    renderDistribution(eventos);
    document.getElementById("predEventCount").textContent = `${eventos.length} evento${eventos.length !== 1 ? "s" : ""}`;
    document.getElementById("predEventosSub").textContent = `Próximas 24h · ordenados por probabilidad`;
    fitAllMarkers(filteredEventos);
    gdInitTooltips(document);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initMap();
    await load();
    document.getElementById("predAutoBtn").addEventListener("click", toggleAuto);
    setInterval(load, 60000);
  });
})();
