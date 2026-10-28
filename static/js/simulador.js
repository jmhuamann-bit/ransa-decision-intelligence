(function () {
  let chartComparativo;

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function fillSelect(id, values, selected) {
    const sel = document.getElementById(id);
    sel.innerHTML = values.map((v) => `<option value="${v}" ${v === selected ? "selected" : ""}>${v}</option>`).join("");
  }

  function currentPayload() {
    return {
      corredor_logistico: document.getElementById("simCorredor").value,
      tipo_transporte: document.getElementById("simTransporte").value,
      tipo_vehiculo: document.getElementById("simVehiculo").value,
      tipo_carga: document.getElementById("simCarga").value,
      prioridad_cliente: document.getElementById("simPrioridad").value,
      peso_toneladas: parseFloat(document.getElementById("simPeso").value) || 0,
      volumen_m3: parseFloat(document.getElementById("simVolumen").value) || 0,
      disponibilidad_flota_pct: parseFloat(document.getElementById("simFlota").value) || 0,
      alerta_senamhi: document.getElementById("simClima").value,
      estado_via: document.getElementById("simVia").value,
    };
  }

  function resultTile(icon, bg, label, value, sub) {
    return `
      <div class="col-6">
        <div class="gd-kpi">
          <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
          <div class="gd-kpi-label">${label}</div>
          <div class="gd-kpi-value">${value}</div>
          ${sub ? `<div class="gd-kpi-delta" style="color:var(--gd-text-muted);">${sub}</div>` : ""}
        </div>
      </div>`;
  }

  function riskTone(nivel) {
    if (nivel === "Critico" || nivel === "Alto") return "gd-bg-danger";
    if (nivel === "Medio") return "gd-bg-warning";
    return "gd-bg-success";
  }

  function renderResult(result) {
    document.getElementById("gdSimResultRow").innerHTML = [
      resultTile("fa-clock", "gd-bg-blue", "Nuevo Lead Time", result.leadtime_dias !== null ? `${gdFormatNumber(result.leadtime_dias)} días` : "—"),
      resultTile("fa-sack-dollar", "gd-bg-accent", "Nuevo Costo", result.costo_pen !== null ? gdFormatPEN(result.costo_pen) : "—"),
      resultTile("fa-bullseye", "gd-bg-success", "OTIF Esperado", gdFormatPct(result.otif_esperado_pct)),
      resultTile(result.nivel_riesgo === "Bajo" ? "fa-shield-halved" : "fa-triangle-exclamation", riskTone(result.nivel_riesgo), "Nivel de Riesgo", `${result.nivel_riesgo === "Critico" ? "Crítico" : result.nivel_riesgo} (${gdFormatPct(result.prob_riesgo_incumplimiento)})`),
    ].join("");

    renderComparativo(result);
  }

  function renderComparativo(result) {
    const subtitle = document.getElementById("gdSimBaselineSubtitle");
    const ctx = document.getElementById("chartComparativo");
    if (!result.baseline) {
      subtitle.textContent = "Selecciona un corredor con datos históricos para comparar";
      if (chartComparativo) { chartComparativo.destroy(); chartComparativo = null; }
      return;
    }
    subtitle.textContent = `Basado en ${gdFormatNumber(result.baseline.muestras, 0)} embarques históricos de este corredor`;

    const labels = ["Lead Time (días)", "OTIF (%)"];
    const historico = [result.baseline.leadtime_dias_historico, result.baseline.otif_pct_historico];
    const simulado = [result.leadtime_dias, result.otif_esperado_pct];

    if (chartComparativo) chartComparativo.destroy();
    chartComparativo = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Histórico del corredor", data: historico, backgroundColor: "#94a3b8", borderRadius: 4 },
          { label: "Escenario simulado", data: simulado, backgroundColor: "#ff7a1a", borderRadius: 4 },
        ],
      },
      options: {
        plugins: { legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") } },
          y: { grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
        },
      },
    });
  }

  async function recalcular() {
    try {
      const result = await RansaAPI.post("/api/simulator/predict", currentPayload());
      renderResult(result);
    } catch (err) {
      document.getElementById("gdSimResultRow").innerHTML = `<div class="col-12"><div class="gd-empty-state"><i class="fa-solid fa-triangle-exclamation"></i><div>${err.message}</div></div></div>`;
    }
  }

  const debouncedRecalcular = gdDebounce(recalcular, 350);

  async function init() {
    let options;
    try {
      options = await RansaAPI.get("/api/simulator/options");
    } catch (err) {
      document.getElementById("gdSimNoModel").style.display = "flex";
      document.getElementById("gdSimContent").style.display = "none";
      return;
    }

    // Escenario inicial representativo de la red peruana: Carretera Central (cruza Ticlio, 4.818 m)
    fillSelect("simCorredor", options.corredor_logistico, "Lima - Huancayo");
    fillSelect("simTransporte", options.tipo_transporte, "Carretero");
    fillSelect("simVehiculo", options.tipo_vehiculo, "Tractocamión T3S3 (30 t)");
    fillSelect("simCarga", options.tipo_carga, "Consumo masivo (seca)");
    fillSelect("simPrioridad", options.prioridad_cliente, "Alta");
    fillSelect("simClima", options.alerta_senamhi, "Naranja");
    fillSelect("simVia", options.estado_via, "Regular");

    document.getElementById("simPeso").value = 24;
    document.getElementById("simVolumen").value = 70;
    document.getElementById("simFlota").value = 85;
    document.getElementById("simFlotaValor").textContent = "85%";

    const inputs = ["simCorredor", "simTransporte", "simVehiculo", "simCarga", "simPrioridad",
      "simPeso", "simVolumen", "simClima", "simVia"];
    inputs.forEach((id) => document.getElementById(id).addEventListener("change", debouncedRecalcular));

    const flota = document.getElementById("simFlota");
    flota.addEventListener("input", () => {
      document.getElementById("simFlotaValor").textContent = `${flota.value}%`;
      debouncedRecalcular();
    });
    document.getElementById("simPeso").addEventListener("input", debouncedRecalcular);
    document.getElementById("simVolumen").addEventListener("input", debouncedRecalcular);

    try {
      await recalcular();
      document.getElementById("gdSimNoModel").style.display = "none";
      document.getElementById("gdSimContent").style.display = "flex";
    } catch (err) {
      document.getElementById("gdSimNoModel").style.display = "flex";
      document.getElementById("gdSimContent").style.display = "none";
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
