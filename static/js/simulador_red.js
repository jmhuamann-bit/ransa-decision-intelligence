(function () {
  let opciones = null, escenarioSel = null, chartRed = null;

  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

  function renderEscenarios() {
    document.getElementById("escGrid").innerHTML = opciones.escenarios.map((e) => `
      <div class="gd-esc-item" data-id="${e.id}" title="${e.descripcion}">
        <i class="fa-solid ${e.icon}"></i><span>${e.nombre}</span>
      </div>`).join("");

    document.querySelectorAll("#escGrid .gd-esc-item").forEach((el) => {
      el.addEventListener("click", () => {
        document.querySelectorAll("#escGrid .gd-esc-item").forEach((o) => o.classList.remove("active"));
        el.classList.add("active");
        escenarioSel = opciones.escenarios.find((e) => e.id === el.dataset.id);
        renderObjetivo();
      });
    });
  }

  function renderObjetivo() {
    const wrap = document.getElementById("escObjetivoWrap");
    if (!escenarioSel || !escenarioSel.requiere_objetivo) { wrap.style.display = "none"; return; }
    wrap.style.display = "block";
    const esNodo = escenarioSel.scope === "nodo";
    const esPuerto = escenarioSel.id === "cerrar_puerto";
    const lista = esPuerto ? opciones.puertos : esNodo ? opciones.nodos : opciones.corredores;
    document.getElementById("escObjetivoLabel").textContent = esPuerto ? "Puerto a cerrar" : esNodo ? "Nodo afectado" : "Corredor afectado";
    document.getElementById("escObjetivo").innerHTML = lista.map((v) => `<option value="${v}">${v}</option>`).join("");
  }

  function deltaCls(valor, invertir) {
    if (valor === 0) return "neutral";
    const malo = invertir ? valor > 0 : valor < 0;
    return malo ? "bad" : "good";
  }

  function impactItem(label, base, sim, deltaTxt, cls) {
    return `<div class="gd-impact-item">
      ${label}
      <div class="base">${base}</div>
      <div class="sim">${sim}</div>
      <div class="delta ${cls}">${deltaTxt}</div>
    </div>`;
  }

  function renderResultado(r) {
    document.getElementById("redEmptyState").style.display = "none";
    document.getElementById("redResult").style.display = "block";

    document.getElementById("redTitulo").innerHTML = `<i class="fa-solid ${r.escenario.icon} me-1"></i> ${r.escenario.nombre}${r.objetivo ? ` — ${r.objetivo}` : ""}`;
    document.getElementById("redSub").textContent = r.escenario.descripcion;
    document.getElementById("redAfectados").innerHTML =
      `<span class="gd-dot rojo"></span>${gdFormatNumber(r.afectados.embarques, 0)} embarques afectados (${gdFormatPct(r.afectados.pct_red)} de la red)`;

    const b = r.baseline, s = r.simulado, d = r.deltas;
    document.getElementById("redImpacto").innerHTML = [
      impactItem("OTIF", gdFormatPct(b.otif_pct), gdFormatPct(s.otif_pct), `${d.otif_pts > 0 ? "+" : ""}${d.otif_pts} pts`, deltaCls(d.otif_pts, false)),
      impactItem("Lead Time", `${gdFormatNumber(b.leadtime_dias)} d`, `${gdFormatNumber(s.leadtime_dias)} d`, `${d.leadtime_pct > 0 ? "+" : ""}${d.leadtime_pct}%`, deltaCls(d.leadtime_pct, true)),
      impactItem("Costo total", gdFormatPEN(b.costo_total_pen), gdFormatPEN(s.costo_total_pen), `${d.costo_pct > 0 ? "+" : ""}${d.costo_pct}% · ${gdFormatPEN(d.sobrecosto_pen)}`, deltaCls(d.costo_pct, true)),
      impactItem("CO₂", `${gdFormatNumber(b.co2_ton)} ton`, `${gdFormatNumber(s.co2_ton)} ton`, `${d.co2_pct > 0 ? "+" : ""}${d.co2_pct}%`, deltaCls(d.co2_pct, true)),
      impactItem("Riesgo promedio", gdFormatPct(b.riesgo_pct), gdFormatPct(s.riesgo_pct), `${d.riesgo_pts > 0 ? "+" : ""}${d.riesgo_pts} pts`, deltaCls(d.riesgo_pts, true)),
      impactItem("Clientes críticos", "—", gdFormatNumber(r.afectados.clientes_criticos, 0), `${gdFormatNumber(r.afectados.corredores, 0)} corredores`, "neutral"),
    ].join("");

    document.getElementById("redRecomendacion").innerHTML =
      `<i class="fa-solid fa-robot me-1"></i><b>Recomendación del AI Copilot:</b> ${r.recomendacion}`;

    renderChart(r);
  }

  function renderChart(r) {
    const b = r.baseline, s = r.simulado;
    // Normalizamos a índice 100 = línea base, para poder comparar magnitudes distintas.
    const idx = (base, sim) => (base ? Math.round((sim / base) * 100) : 100);
    const labels = ["OTIF", "Lead Time", "Costo", "CO₂", "Riesgo"];
    const baseData = [100, 100, 100, 100, 100];
    const simData = [
      idx(b.otif_pct, s.otif_pct), idx(b.leadtime_dias, s.leadtime_dias),
      idx(b.costo_total_pen, s.costo_total_pen), idx(b.co2_ton, s.co2_ton), idx(b.riesgo_pct, s.riesgo_pct),
    ];
    if (chartRed) chartRed.destroy();
    chartRed = new Chart(document.getElementById("chartRedComparativo"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Línea base (=100)", data: baseData, backgroundColor: "#94a3b8", borderRadius: 4 },
          { label: "Escenario simulado", data: simData, backgroundColor: "#e11d48", borderRadius: 4 },
        ],
      },
      options: {
        plugins: {
          legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 } } },
          tooltip: { callbacks: { label: (c) => `${c.dataset.label}: índice ${c.parsed.y}` } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") } },
          y: { grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "Índice (base = 100)" } },
        },
      },
    });
  }

  async function simular() {
    if (!escenarioSel) { alert("Selecciona un escenario primero."); return; }
    const btn = document.getElementById("btnSimularRed");
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Simulando...';
    try {
      const payload = { escenario: escenarioSel.id };
      if (escenarioSel.requiere_objetivo) payload.objetivo = document.getElementById("escObjetivo").value;
      const r = await RansaAPI.post("/api/simulator/network", payload);
      renderResultado(r);
    } catch (err) {
      alert(err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-play"></i> Simular escenario';
    }
  }

  function wireTabs() {
    document.querySelectorAll("#simTabs .gd-seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#simTabs .gd-seg-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const red = btn.dataset.tab === "red";
        document.getElementById("simTabRed").style.display = red ? "block" : "none";
        document.getElementById("simTabEmbarque").style.display = red ? "none" : "block";
      });
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    wireTabs();
    try {
      opciones = await RansaAPI.get("/api/simulator/network-options");
      renderEscenarios();
    } catch (err) {
      document.getElementById("escGrid").innerHTML = `<div class="text-muted" style="font-size:12px;">No se pudieron cargar los escenarios: ${err.message}</div>`;
    }
    document.getElementById("btnSimularRed").addEventListener("click", simular);
  });
})();
