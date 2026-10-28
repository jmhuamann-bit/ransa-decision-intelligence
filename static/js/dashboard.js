(function () {
  let chartTendencia, chartRiesgo;

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function kpiTile({ icon, bg, label, value, sub }) {
    return `
      <div class="col-6 col-lg-3">
        <div class="gd-kpi">
          <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
          <div class="gd-kpi-label">${label}</div>
          <div class="gd-kpi-value">${value}</div>
          ${sub ? `<div class="gd-kpi-delta" style="color:var(--gd-text-muted);">${sub}</div>` : ""}
        </div>
      </div>`;
  }

  async function loadKpis() {
    const anio = document.getElementById("fAnio").value;
    const transporte = document.getElementById("fTransporte").value;
    const qs = new URLSearchParams();
    if (anio) qs.set("anio", anio);
    if (transporte) qs.set("tipo_transporte", transporte);

    const k = await RansaAPI.get(`/api/dashboard/kpis?${qs.toString()}`);

    document.getElementById("gdKpiRow").innerHTML = [
      kpiTile({ icon: "fa-truck-fast", bg: "gd-bg-blue", label: "Embarques", value: gdFormatNumber(k.total_embarques, 0), sub: `${gdFormatNumber(k.incidentes_totales,0)} incidentes registrados` }),
      kpiTile({ icon: "fa-clock", bg: "gd-bg-accent", label: "Lead Time promedio", value: `${gdFormatNumber(k.lead_time_promedio_dias)} días`, sub: "Tiempo real de entrega" }),
      kpiTile({ icon: "fa-bullseye", bg: "gd-bg-success", label: "OTIF", value: gdFormatPct(k.otif_pct), sub: `Fill rate ${gdFormatPct(k.fill_rate_pct)}` }),
      kpiTile({ icon: "fa-sack-dollar", bg: "gd-bg-warning", label: "Costo promedio", value: gdFormatPEN(k.costo_promedio_pen), sub: `Total ${gdFormatPEN(k.costo_total_pen)}` }),
      kpiTile({ icon: "fa-leaf", bg: "gd-bg-success", label: "CO₂ estimado", value: `${gdFormatNumber(k.co2_toneladas)} ton`, sub: "Basado en consumo de combustible" }),
      kpiTile({ icon: "fa-gauge", bg: "gd-bg-blue", label: "Nivel de servicio", value: gdFormatPct(k.nivel_servicio_pct), sub: "Indicador compuesto" }),
      kpiTile({ icon: "fa-triangle-exclamation", bg: "gd-bg-danger", label: "Contingencias activas", value: gdFormatNumber(k.contingencias_activas, 0), sub: "Alertas abiertas" }),
      kpiTile({ icon: "fa-shield-halved", bg: "gd-bg-danger", label: "Riesgo alto/crítico", value: gdFormatNumber(k.distribucion_riesgo.alto_critico, 0), sub: `de ${gdFormatNumber(k.total_embarques,0)} embarques` }),
    ].join("");

    renderRiesgo(k.distribucion_riesgo);
  }

  function renderRiesgo(dist) {
    const ctx = document.getElementById("chartRiesgo");
    const data = [dist.bajo, dist.medio, dist.alto_critico];
    if (chartRiesgo) { chartRiesgo.data.datasets[0].data = data; chartRiesgo.update(); return; }
    chartRiesgo = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["Bajo", "Medio", "Alto / Crítico"],
        datasets: [{ data, backgroundColor: ["#16a34a", "#eab308", "#e11d48"], borderWidth: 0 }],
      },
      options: {
        cutout: "68%",
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 }, padding: 14 } } },
      },
    });
  }

  async function loadTendencia() {
    const { tendencia } = await RansaAPI.get("/api/dashboard/tendencia");
    const labels = tendencia.map((t) => `${t.mes.slice(0, 3)} ${t.anio}`);
    const leadTime = tendencia.map((t) => t.lead_time_promedio);
    const otif = tendencia.map((t) => t.otif_pct);

    const ctx = document.getElementById("chartTendencia");
    chartTendencia = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Lead Time (días)", data: leadTime, borderColor: "#3d63ff", backgroundColor: "rgba(61,99,255,.08)",
            yAxisID: "y", tension: .35, fill: true, pointRadius: 2,
          },
          {
            label: "OTIF (%)", data: otif, borderColor: "#ff7a1a", backgroundColor: "rgba(255,122,26,.08)",
            yAxisID: "y1", tension: .35, fill: true, pointRadius: 2,
          },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 10 } } },
          y: { position: "left", grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "Días" } },
          y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") }, min: 0, max: 100, title: { display: true, text: "%" } },
        },
      },
    });
  }

  async function loadCorredores() {
    const { corredores } = await RansaAPI.get("/api/dashboard/corredores-riesgo");
    const tbody = document.querySelector("#tblCorredores tbody");
    if (!corredores.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">Sin datos suficientes</td></tr>`;
      return;
    }
    tbody.innerHTML = corredores.map((c) => {
      const badge = c.riesgo_promedio_pct >= 60 ? "rojo" : c.riesgo_promedio_pct >= 30 ? "amarillo" : "verde";
      return `<tr>
        <td><strong>${c.corredor}</strong></td>
        <td>${gdFormatNumber(c.total_embarques, 0)}</td>
        <td>${gdFormatPct(c.otif_pct)}</td>
        <td><span class="gd-badge ${badge}"><span class="gd-dot ${badge}"></span>${gdFormatPct(c.riesgo_promedio_pct)}</span></td>
      </tr>`;
    }).join("");
  }

  async function loadActividad() {
    const { actividad } = await RansaAPI.get("/api/dashboard/actividad-reciente");
    const box = document.getElementById("gdActividad");
    if (!actividad.length) {
      box.innerHTML = `<div class="gd-empty-state"><i class="fa-regular fa-circle-check"></i><div>Sin alertas registradas</div></div>`;
      return;
    }
    box.innerHTML = actividad.map((a) => {
      const color = a.severidad === "Critica" ? "rojo" : a.severidad === "Alta" ? "amarillo" : "verde";
      return `<div class="d-flex gap-3 py-2" style="border-bottom:1px solid var(--gd-border);">
        <span class="gd-dot ${color}" style="margin-top:6px;"></span>
        <div class="flex-grow-1">
          <div style="font-size:13px;font-weight:600;">${a.titulo}</div>
          <div style="font-size:12px;color:var(--gd-text-muted);">${a.descripcion || ""}</div>
          <div style="font-size:11px;color:var(--gd-text-subtle);margin-top:2px;">${gdFormatDate(a.creado_en)}</div>
        </div>
      </div>`;
    }).join("");
  }

  async function init() {
    await Promise.all([loadKpis(), loadTendencia(), loadCorredores(), loadActividad()]);
    document.getElementById("fAnio").addEventListener("change", loadKpis);
    document.getElementById("fTransporte").addEventListener("change", loadKpis);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
