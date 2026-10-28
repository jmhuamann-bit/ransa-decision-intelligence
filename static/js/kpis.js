(function () {
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function riskBadge(pct) {
    const sem = pct >= 50 ? "rojo" : pct >= 25 ? "amarillo" : "verde";
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${gdFormatPct(pct)}</span>`;
  }

  function renderTabla(id, items) {
    document.getElementById(id).innerHTML = items.map((r) => `
      <tr>
        <td><strong>${r.grupo || "—"}</strong></td>
        <td>${gdFormatNumber(r.total_embarques, 0)}</td>
        <td>${gdFormatPct(r.otif_pct)}</td>
        <td>${gdFormatNumber(r.leadtime_promedio_dias)} d</td>
        <td>${gdFormatPEN(r.costo_promedio_pen)}</td>
        <td>${gdFormatNumber(r.distancia_promedio_km, 0)} km</td>
        <td>${gdFormatNumber(r.combustible_promedio_galones)} gal</td>
        <td>${riskBadge(r.riesgo_promedio_pct)}</td>
      </tr>`).join("");
  }

  async function loadTablas() {
    const [transporte, prioridad] = await Promise.all([
      RansaAPI.get("/api/kpis/por-transporte"),
      RansaAPI.get("/api/kpis/por-prioridad"),
    ]);
    renderTabla("gdTablaTransporte", transporte.items);
    renderTabla("gdTablaPrioridad", prioridad.items);
  }

  async function loadTrimestral() {
    const { items } = await RansaAPI.get("/api/kpis/comparativo-trimestral");
    new Chart(document.getElementById("chartTrimestral"), {
      type: "line",
      data: {
        labels: items.map((i) => i.periodo),
        datasets: [
          { label: "OTIF (%)", data: items.map((i) => i.otif_pct), borderColor: "#ff7a1a", backgroundColor: "rgba(255,122,26,.08)", yAxisID: "y", tension: .3, fill: true, pointRadius: 2 },
          { label: "Lead Time (días ×10)", data: items.map((i) => i.leadtime_promedio_dias * 10), borderColor: "#3d63ff", tension: .3, pointRadius: 2, yAxisID: "y" },
        ],
      },
      options: {
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 10 } } },
          y: { min: 0, max: 100, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
        },
      },
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await Promise.all([loadTablas(), loadTrimestral()]);
  });
})();
