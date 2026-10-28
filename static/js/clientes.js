(function () {
  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function riskBadge(pct) {
    const sem = pct >= 50 ? "rojo" : pct >= 25 ? "amarillo" : "verde";
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${gdFormatPct(pct)}</span>`;
  }

  async function loadSectores() {
    const { sectors } = await RansaAPI.get("/api/clients/sectors");
    const labels = sectors.map((s) => s.sector_cliente);

    new Chart(document.getElementById("chartSectores"), {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data: sectors.map((s) => s.total_embarques),
          backgroundColor: ["#3d63ff", "#ff7a1a", "#eab308", "#e11d48", "#8b5cf6", "#16a34a", "#0ea5e9", "#f97316"],
          borderWidth: 0,
        }],
      },
      options: { plugins: { legend: { position: "right", labels: { color: cssVar("--gd-text-muted"), font: { size: 10.5 }, boxWidth: 10 } } } },
    });

    new Chart(document.getElementById("chartOtifSector"), {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "OTIF (%)",
          data: sectors.map((s) => s.otif_pct),
          backgroundColor: sectors.map((s) => (s.otif_pct >= 90 ? "#16a34a" : s.otif_pct >= 75 ? "#eab308" : "#e11d48")),
          borderRadius: 5,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle"), font: { size: 10 } } },
          y: { min: 0, max: 100, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
        },
      },
    });
  }

  async function loadSegments() {
    const { segments } = await RansaAPI.get("/api/clients/segments");
    document.getElementById("gdClientesTotal").textContent = `${segments.length} segmentos de cliente`;
    document.getElementById("gdClientesBody").innerHTML = segments.map((s) => `
      <tr>
        <td><strong>${s.sector_cliente}</strong></td>
        <td>${s.prioridad_cliente}</td>
        <td>${gdFormatNumber(s.total_embarques, 0)}</td>
        <td>${gdFormatPct(s.otif_pct)}</td>
        <td>${s.cumple_sla ? '<span class="gd-badge verde">Cumple</span>' : '<span class="gd-badge rojo">Bajo SLA</span>'}</td>
        <td>${gdFormatNumber(s.leadtime_promedio_dias)} d</td>
        <td>${gdFormatPEN(s.costo_promedio_pen)}</td>
        <td>${gdFormatPct(s.fill_rate_pct)}</td>
        <td>${gdFormatPct(s.nivel_servicio_pct)}</td>
        <td>${riskBadge(s.riesgo_promedio_pct)}</td>
        <td><a href="/monitoreo?sector_cliente=${encodeURIComponent(s.sector_cliente)}&prioridad_cliente=${encodeURIComponent(s.prioridad_cliente)}" class="gd-btn gd-btn-outline gd-btn-sm">Ver embarques</a></td>
      </tr>`).join("");
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await Promise.all([loadSectores(), loadSegments()]);
  });
})();
