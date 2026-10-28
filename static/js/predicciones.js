(function () {
  let chartRoc, chartImportancia;

  function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function metricTile(icon, bg, label, value, sub) {
    return `
      <div class="col-6 col-lg-2">
        <div class="gd-kpi">
          <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
          <div class="gd-kpi-label">${label}</div>
          <div class="gd-kpi-value">${value}</div>
          ${sub ? `<div class="gd-kpi-delta" style="color:var(--gd-text-muted);">${sub}</div>` : ""}
        </div>
      </div>`;
  }

  function renderMetrics(model) {
    const m = model.metrics;
    document.getElementById("gdMetricRow").innerHTML = [
      metricTile("fa-bullseye", "gd-bg-blue", "Accuracy", gdFormatPct(m.accuracy * 100)),
      metricTile("fa-crosshairs", "gd-bg-accent", "Precision", gdFormatPct(m.precision * 100)),
      metricTile("fa-magnifying-glass", "gd-bg-success", "Recall", gdFormatPct(m.recall * 100)),
      metricTile("fa-scale-balanced", "gd-bg-warning", "F1 Score", gdFormatPct(m.f1_score * 100)),
      metricTile("fa-chart-area", "gd-bg-danger", "AUC", gdFormatNumber(m.auc, 3)),
      metricTile("fa-database", "gd-bg-blue", "Muestras", gdFormatNumber(model.n_muestras_entrenamiento + model.n_muestras_prueba, 0), `${gdFormatNumber(model.n_muestras_prueba,0)} de prueba`),
    ].join("");
  }

  function renderRoc(roc) {
    const ctx = document.getElementById("chartRoc");
    const points = roc.fpr.map((x, i) => ({ x, y: roc.tpr[i] }));
    const diag = [{ x: 0, y: 0 }, { x: 1, y: 1 }];
    if (chartRoc) chartRoc.destroy();
    chartRoc = new Chart(ctx, {
      type: "line",
      data: {
        datasets: [
          { label: "Modelo", data: points, borderColor: "#ff7a1a", backgroundColor: "rgba(255,122,26,.1)", fill: true, tension: .2, pointRadius: 0, borderWidth: 2 },
          { label: "Aleatorio (referencia)", data: diag, borderColor: cssVar("--gd-text-subtle"), borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5 },
        ],
      },
      options: {
        parsing: false,
        scales: {
          x: { type: "linear", min: 0, max: 1, title: { display: true, text: "Tasa de falsos positivos" }, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
          y: { min: 0, max: 1, title: { display: true, text: "Tasa de verdaderos positivos" }, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
        },
        plugins: { legend: { labels: { color: cssVar("--gd-text-muted"), font: { size: 11 } } } },
      },
    });
  }

  function renderConfusion(cm) {
    const total = cm.verdaderos_negativos + cm.falsos_positivos + cm.falsos_negativos + cm.verdaderos_positivos;
    const cell = (value, label, tone) => `
      <div class="${tone}" style="border-radius:10px;padding:16px;text-align:center;">
        <div style="font-size:22px;font-weight:800;">${gdFormatNumber(value, 0)}</div>
        <div style="font-size:11px;font-weight:600;margin-top:2px;">${label}</div>
        <div style="font-size:10.5px;opacity:.75;">${gdFormatPct((value / total) * 100)}</div>
      </div>`;
    document.getElementById("gdConfusionMatrix").innerHTML = `
      <div class="row g-2">
        <div class="col-6">${cell(cm.verdaderos_negativos, "Predijo cumple / Cumplió", "gd-bg-success")}</div>
        <div class="col-6">${cell(cm.falsos_positivos, "Predijo incumple / Cumplió", "gd-bg-warning")}</div>
        <div class="col-6">${cell(cm.falsos_negativos, "Predijo cumple / Incumplió", "gd-bg-danger")}</div>
        <div class="col-6">${cell(cm.verdaderos_positivos, "Predijo incumple / Incumplió", "gd-bg-blue")}</div>
      </div>
      <div style="font-size:11px;color:var(--gd-text-muted);margin-top:10px;text-align:center;">
        Total conjunto de prueba: ${gdFormatNumber(total, 0)} embarques
      </div>`;
  }

  function renderImportancia(items, algoritmo) {
    const ctx = document.getElementById("chartImportancia");
    const permutacion = algoritmo !== "logistic_regression";
    document.getElementById("gdImportSub").textContent = permutacion
      ? "Top 15 variables por importancia de permutación: cuánto cae el AUC si se desordena cada variable"
      : "Top 15 variables con mayor efecto en la predicción (coeficiente estandarizado)";
    const sorted = [...items].reverse();
    const labels = sorted.map((i) => i.variable.length > 32 ? i.variable.slice(0, 32) + "…" : i.variable);
    const data = sorted.map((i) => i.coeficiente);
    const colors = sorted.map((i) => permutacion ? "#ff7a1a" : i.direccion === "aumenta_riesgo" ? "#e11d48" : "#16a34a");
    if (chartImportancia) chartImportancia.destroy();
    chartImportancia = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ data, backgroundColor: colors, borderRadius: 4 }] },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: permutacion ? "Caída de AUC al permutar la variable" : "Coeficiente (+ aumenta riesgo, - lo reduce)" }, grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") } },
          y: { grid: { display: false }, ticks: { color: cssVar("--gd-text-muted"), font: { size: 10.5 } } },
        },
      },
    });
  }

  async function loadTopRiesgo() {
    const { items } = await RansaAPI.get("/api/predictions/top-riesgo");
    const tbody = document.getElementById("gdTopRiesgoBody");
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">Sin datos</td></tr>`;
      return;
    }
    tbody.innerHTML = items.map((i) => {
      const badge = i.prob_riesgo_incumplimiento >= 75 ? "rojo" : i.prob_riesgo_incumplimiento >= 50 ? "rojo" : i.prob_riesgo_incumplimiento >= 25 ? "amarillo" : "verde";
      return `<tr>
        <td class="gd-mono">${i.id_viaje}</td>
        <td>${i.corredor_logistico || "—"}</td>
        <td><span class="gd-badge ${badge}"><span class="gd-dot ${badge}"></span>${gdFormatPct(i.prob_riesgo_incumplimiento)}</span></td>
        <td>${i.otif_real ? '<span class="gd-badge verde">Cumplió</span>' : '<span class="gd-badge rojo">Incumplió</span>'}</td>
      </tr>`;
    }).join("");
  }

  async function loadModel() {
    const { model } = await RansaAPI.get("/api/predictions/model");
    if (!model) {
      document.getElementById("gdNoModel").style.display = "flex";
      document.getElementById("gdModelContent").style.display = "none";
      return;
    }
    document.getElementById("gdNoModel").style.display = "none";
    document.getElementById("gdModelContent").style.display = "block";

    document.getElementById("gdAlgoLabel").textContent = model.algoritmo_label;
    document.getElementById("gdFechaEntrenamiento").textContent = gdFormatDate(model.creado_en);
    document.getElementById("gdVersion").textContent = model.version;

    renderMetrics(model);
    renderRoc(model.curva_roc);
    renderConfusion(model.matriz_confusion);
    renderImportancia(model.importancia_variables, model.algoritmo);
    await Promise.all([loadTopRiesgo(), loadRuns()]);
  }

  async function loadRuns() {
    const { runs } = await RansaAPI.get("/api/predictions/runs");
    const best = runs.reduce((b, r) => (!b || (r.metrics.auc || 0) > (b.metrics.auc || 0) ? r : b), null);
    document.getElementById("gdRunsBody").innerHTML = runs.map((r) => {
      const m = r.metrics;
      const delta = (m.auc - 0.748) * 100;
      return `<tr>
        <td><b>${r.algoritmo_label}</b><div style="font-size:11px;color:var(--gd-text-muted);">versión ${r.version}</div></td>
        <td class="text-end"><b>${gdFormatNumber(m.auc, 3)}</b> <span style="font-size:11px;color:${delta >= 0 ? "var(--gd-success)" : "var(--gd-danger)"};">${delta >= 0 ? "+" : ""}${gdFormatNumber(delta, 1)} pts vs línea base</span></td>
        <td class="text-end">${gdFormatPct(m.accuracy * 100)}</td><td class="text-end">${gdFormatPct(m.recall * 100)}</td>
        <td class="text-end">${gdFormatPct(m.precision * 100)}</td><td class="text-end">${gdFormatPct(m.f1_score * 100)}</td>
        <td>${r.activo ? '<span class="gd-badge verde"><span class="gd-dot verde"></span>Activo</span>' : (best && best.id === r.id ? '<span class="gd-badge amarillo">Mejor AUC</span>' : '<span class="gd-badge">En reserva</span>')}</td>
        <td class="text-end">${r.activo ? "" : `<button class="gd-btn gd-btn-outline gd-btn-sm" data-activate="${r.id}">Activar</button>`}</td>
      </tr>`;
    }).join("");
    document.querySelectorAll("[data-activate]").forEach((b) => b.addEventListener("click", async () => {
      b.disabled = true; b.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      try { await RansaAPI.post(`/api/predictions/activate/${b.dataset.activate}`); await loadModel(); }
      catch (err) { alert(err.message); b.disabled = false; b.textContent = "Activar"; }
    }));
  }

  async function trainModel(button) {
    const original = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Entrenando (1–2 min)...';
    try {
      const sel = document.getElementById("selAlgoritmo");
      await RansaAPI.post("/api/predictions/train", { algoritmo: sel ? sel.value : "todos" });
      await loadModel();
    } catch (err) {
      alert(err.message || "No fue posible entrenar el modelo.");
    } finally {
      button.disabled = false;
      button.innerHTML = original;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await loadModel();
    const btn = document.getElementById("btnReentrenar");
    if (btn) btn.addEventListener("click", () => trainModel(btn));
    const btnVacio = document.getElementById("btnEntrenarVacio");
    if (btnVacio) btnVacio.addEventListener("click", () => trainModel(btnVacio));
  });
})();
