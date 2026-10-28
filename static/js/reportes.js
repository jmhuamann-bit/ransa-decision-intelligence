(function () {
  function tile(icon, bg, label, value) {
    return `
      <div class="col-6 col-lg-3">
        <div class="gd-kpi">
          <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
          <div class="gd-kpi-label">${label}</div>
          <div class="gd-kpi-value">${value}</div>
        </div>
      </div>`;
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const k = await RansaAPI.get("/api/dashboard/kpis");
    document.getElementById("gdReportKpiRow").innerHTML = [
      tile("fa-truck-fast", "gd-bg-blue", "Embarques", gdFormatNumber(k.total_embarques, 0)),
      tile("fa-bullseye", "gd-bg-success", "OTIF", gdFormatPct(k.otif_pct)),
      tile("fa-clock", "gd-bg-accent", "Lead Time", `${gdFormatNumber(k.lead_time_promedio_dias)} días`),
      tile("fa-sack-dollar", "gd-bg-warning", "Costo total", gdFormatPEN(k.costo_total_pen)),
    ].join("");
  });
})();
