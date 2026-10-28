/* Resumen RANSA: perfil público de la empresa + pulso en vivo del gemelo + operación histórica simulada. */
(function () {
  let chartTendencia;
  let perfil = null;
  const LINEA = {};
  const $ = (id) => document.getElementById(id);
  const cssVar = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = (t) => { const d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; };
  const src = (f) => `<a class="rs-src" href="${f.url}" target="_blank" rel="noopener">${esc(f.medio)} · ${esc(f.fecha)}</a>`;

  function filtros() {
    const qs = new URLSearchParams();
    if ($("fLinea").value) qs.set("linea", $("fLinea").value);
    if ($("fAnio").value) qs.set("anio", $("fAnio").value);
    if ($("fTransporte").value) qs.set("tipo_transporte", $("fTransporte").value);
    return qs.toString();
  }

  // ------------------------------------------------------------------ perfil público
  async function loadPerfil() {
    perfil = await RansaAPI.get("/api/company/profile");
    perfil.lineas.forEach((l) => { LINEA[l.id] = l; });
    $("rsPropiedad").textContent = perfil.propiedad;
    $("rsLineas").innerHTML = perfil.lineas.map((l) =>
      `<button class="rs-linea" data-linea="${esc(l.id)}" style="--c:${l.color}" title="${esc(l.resumen)}"><i class="fa-solid ${l.icon}"></i>${esc(l.id)}</button>`).join("");
    $("rsCifras").innerHTML = perfil.cifras.map((c, i) => `
      <div class="rs-cifra" style="animation-delay:${i * 70}ms">
        <div class="rs-cifra-v">${esc(c.texto)}</div>
        <div class="rs-cifra-l">${esc(c.etiqueta)}</div>
        <a class="rs-cifra-src" href="${c.fuente.url}" target="_blank" rel="noopener">${esc(c.alcance)} · ${esc(c.fuente.medio)}</a>
      </div>`).join("");
    $("fLinea").innerHTML = `<option value="">Todas las líneas</option>` +
      perfil.lineas.map((l) => `<option value="${esc(l.id)}">${esc(l.id)}</option>`).join("");
    $("rsAgenda").innerHTML = perfil.agenda.map((a) => `<li>${esc(a.texto)} ${src(a.fuente)}</li>`).join("");
    $("rsTeam").innerHTML = perfil.liderazgo.map((p) => `
      <a class="rs-person" href="${p.fuente.url}" target="_blank" rel="noopener" title="Cargo según ${esc(p.fuente.medio)}, ${esc(p.fuente.fecha)}">
        <span class="rs-person-av">${esc(gdInitials(p.nombre))}</span>
        <span><b>${esc(p.nombre)}</b><small>${esc(p.cargo)}</small></span>
      </a>`).join("");
    $("rsFuentes").innerHTML = perfil.fuentes.map((f) =>
      `<li><a href="${f.url}" target="_blank" rel="noopener">${esc(f.titulo)}</a> — ${esc(f.medio)}, ${esc(f.fecha)}</li>`).join("");
    document.querySelectorAll(".rs-linea").forEach((b) => b.addEventListener("click", () => setLinea(b.dataset.linea)));
  }

  function setLinea(linea) {
    $("fLinea").value = $("fLinea").value === linea ? "" : linea;
    reload();
  }

  function renderFiltroTxt(k) {
    const l = LINEA[$("fLinea").value];
    const partes = [l ? l.id : "Toda la operación", `${gdFormatNumber(k.total_embarques, 0)} embarques`];
    if ($("fAnio").value) partes.push($("fAnio").value);
    if ($("fTransporte").value) partes.push($("fTransporte").value);
    $("rsFiltroTxt").innerHTML = esc(partes.join(" · ")) + (l ? `<div class="rs-linea-dato" style="--c:${l.color}"><i class="fa-solid ${l.icon}"></i> ${esc(l.resumen)} <b>${esc(l.dato)}</b> ${src(l.fuente)}</div>` : "");
    document.querySelectorAll(".rs-linea").forEach((b) => b.classList.toggle("active", b.dataset.linea === $("fLinea").value));
  }

  // ------------------------------------------------------------------ KPIs (con contador animado)
  const KPIS = [
    { id: "kEmb", icon: "fa-truck-fast", bg: "gd-bg-blue", label: "Embarques", get: (k) => k.total_embarques,
      fmt: (v) => gdFormatNumber(v, 0), sub: (k) => `Fill rate ${gdFormatPct(k.fill_rate_pct)}` },
    { id: "kOtif", icon: "fa-bullseye", bg: "gd-bg-success", label: "OTIF", get: (k) => k.otif_pct,
      fmt: (v) => gdFormatPct(v), sub: (k) => `Nivel de servicio ${gdFormatPct(k.nivel_servicio_pct)}` },
    { id: "kLt", icon: "fa-clock", bg: "gd-bg-accent", label: "Lead Time", get: (k) => k.lead_time_promedio_dias,
      fmt: (v) => `${gdFormatNumber(v, 2)} d`, sub: () => "Promedio puerta a puerta" },
    { id: "kCosto", icon: "fa-sack-dollar", bg: "gd-bg-warning", label: "Costo logístico", get: (k) => k.costo_total_pen,
      fmt: (v) => gdFormatPENShort(v), sub: (k) => `${gdFormatPEN(k.costo_promedio_pen)} por embarque` },
    { id: "kCo2", icon: "fa-leaf", bg: "gd-bg-success", label: "CO₂ emitido", get: (k) => k.co2_toneladas,
      fmt: (v) => `${gdFormatNumber(v, 0)} t`, sub: (k) => `${gdFormatNumber(k.co2_evitado_t, 0)} t evitadas con GNL/GNV` },
    { id: "kRiesgo", icon: "fa-shield-halved", bg: "gd-bg-danger", label: "Riesgo alto o crítico", get: (k) => k.distribucion_riesgo.alto_critico,
      fmt: (v) => gdFormatNumber(v, 0), sub: (k) => `${gdFormatPct(k.distribucion_riesgo.alto_critico / Math.max(1, k.total_embarques) * 100)} de los embarques` },
  ];

  function buildKpis() {
    $("gdKpiRow").innerHTML = KPIS.map((c) => `
      <div class="col-6 col-md-4 col-xxl-2">
        <div class="gd-kpi">
          <div class="gd-kpi-icon ${c.bg}"><i class="fa-solid ${c.icon}"></i></div>
          <div class="gd-kpi-label">${c.label}</div>
          <div class="gd-kpi-value" id="${c.id}">—</div>
          <div class="gd-kpi-delta" style="color:var(--gd-text-muted);" id="${c.id}Sub">&nbsp;</div>
        </div>
      </div>`).join("");
  }

  async function loadKpis() {
    const k = await RansaAPI.get(`/api/dashboard/kpis?${filtros()}`);
    KPIS.forEach((c) => {
      gdCountUp($(c.id), c.get(k) || 0, c.fmt);
      $(c.id + "Sub").textContent = c.sub(k);
    });
    renderFiltroTxt(k);
  }

  // ------------------------------------------------------------------ tendencia
  async function loadTendencia() {
    const { tendencia } = await RansaAPI.get(`/api/dashboard/tendencia?${filtros()}`);
    const labels = tendencia.map((t) => `${t.mes.slice(0, 3)} ${String(t.anio).slice(2)}`);
    const lt = tendencia.map((t) => t.lead_time_promedio);
    const otif = tendencia.map((t) => t.otif_pct);
    if (chartTendencia) {
      chartTendencia.data.labels = labels;
      chartTendencia.data.datasets[0].data = otif;
      chartTendencia.data.datasets[1].data = lt;
      chartTendencia.update();
      return;
    }
    chartTendencia = new Chart($("chartTendencia"), {
      type: "line",
      data: {
        labels,
        datasets: [
          { label: "OTIF (%)", data: otif, borderColor: "#ff7a1a", backgroundColor: "rgba(255,122,26,.10)", yAxisID: "y1",
            tension: .35, fill: true, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 },
          { label: "Lead Time (días)", data: lt, borderColor: "#3d63ff", backgroundColor: "rgba(61,99,255,0)", yAxisID: "y",
            tension: .35, fill: false, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2 },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 }, boxWidth: 12 } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 10 }, maxRotation: 0, autoSkipPadding: 12 } },
          y: { position: "right", grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "días" } },
          y1: { position: "left", grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") }, suggestedMin: 60, max: 100, title: { display: true, text: "OTIF %" } },
        },
      },
    });
  }

  // ------------------------------------------------------------------ líneas de negocio
  async function loadLineas() {
    const { lineas } = await RansaAPI.get(`/api/dashboard/lineas?${filtros()}`);
    const sel = $("fLinea").value;
    const max = Math.max(1, ...lineas.map((l) => l.participacion_pct));
    $("rsLineasPerf").innerHTML = lineas.map((l) => {
      const c = (LINEA[l.linea] || {}).color || "#64748b";
      const cls = l.otif_pct >= 84 ? "ok" : l.otif_pct >= 79 ? "mid" : "bad";
      return `<button class="rs-lp ${sel === l.linea ? "active" : ""} ${sel && sel !== l.linea ? "dim" : ""}" data-linea="${esc(l.linea)}" style="--c:${c}">
        <span class="rs-lp-top"><span class="rs-lp-name"><span class="rs-lp-dot"></span>${esc(l.linea)}</span><span class="rs-lp-otif ${cls}">OTIF ${gdFormatPct(l.otif_pct)}</span></span>
        <span class="rs-lp-bar"><span style="width:${(l.participacion_pct / max * 100).toFixed(1)}%"></span></span>
        <span class="rs-lp-meta">${gdFormatPct(l.participacion_pct)} de los embarques · Lead Time ${gdFormatNumber(l.lead_time_dias, 2)} d · riesgo IA ${gdFormatPct(l.riesgo_promedio_pct, 0)} · ${gdFormatNumber(l.co2_t, 0)} t CO₂</span>
      </button>`;
    }).join("");
    document.querySelectorAll(".rs-lp").forEach((b) => b.addEventListener("click", () => setLinea(b.dataset.linea)));
  }

  // ------------------------------------------------------------------ corredores
  async function loadCorredores() {
    const { corredores } = await RansaAPI.get(`/api/dashboard/corredores-riesgo?${filtros()}`);
    const tbody = document.querySelector("#tblCorredores tbody");
    if (!corredores.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">Sin datos suficientes para este filtro</td></tr>`;
      return;
    }
    const max = Math.max(...corredores.map((c) => c.riesgo_promedio_pct), 1);
    tbody.innerHTML = corredores.map((c) => {
      const badge = c.riesgo_promedio_pct >= 45 ? "rojo" : c.riesgo_promedio_pct >= 25 ? "amarillo" : "verde";
      return `<tr>
        <td><strong>${esc(c.corredor)}</strong></td>
        <td class="text-end">${gdFormatNumber(c.total_embarques, 0)}</td>
        <td class="text-end">${gdFormatPct(c.otif_pct)}</td>
        <td><div class="rs-riskbar ${badge}"><span style="width:${(c.riesgo_promedio_pct / max * 100).toFixed(0)}%"></span><b>${gdFormatPct(c.riesgo_promedio_pct)}</b></div></td>
      </tr>`;
    }).join("");
  }

  // ------------------------------------------------------------------ pulso en vivo del gemelo
  async function pollLive() {
    try {
      const d = await RansaAPI.get("/api/live/kpis");
      const k = d.kpis;
      const ev = d.eventos[0];
      $("rsLiveItems").innerHTML = `
        <span><b id="lvMov">${k.vehiculos_en_operacion}</b> unidades en movimiento</span>
        <span><b>${d.eventos.length}</b> eventos activos</span>
        <span>OTIF proyectado <b>${gdFormatPct(k.otif_proyectado_pct)}</b></span>
        <span><b>${gdFormatPENShort(k.carga_en_riesgo_pen)}</b> de carga en riesgo</span>
        <span><b>${k.decisiones}</b> decisiones IA</span>
        ${ev ? `<span class="rs-live-ev sev-${esc(ev.severidad)}"><i class="fa-solid ${esc(ev.icon)}"></i> ${esc(ev.titulo)} · ${esc(ev.lugar)}</span>` : ""}`;
    } catch (e) { /* el resumen funciona aunque el gemelo no responda */ }
  }

  async function reload() {
    await Promise.all([loadKpis(), loadTendencia(), loadLineas(), loadCorredores()]);
  }

  async function init() {
    buildKpis();
    await loadPerfil();
    const linea = new URLSearchParams(window.location.search).get("linea");
    if (linea && LINEA[linea]) $("fLinea").value = linea;
    await reload();
    ["fLinea", "fAnio", "fTransporte"].forEach((id) => $(id).addEventListener("change", reload));
    pollLive();
    setInterval(pollLive, 4000);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
