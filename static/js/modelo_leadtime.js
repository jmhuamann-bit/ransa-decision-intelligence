(function () {
  let M = null, chartScree = null, chartAportes = null;
  const FACTOR_COLORS = ["#3d63ff", "#ff7a1a", "#e11d48", "#8b5cf6", "#eab308"];

  function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  const nf = (v, d = 6) => Number(v).toFixed(d);

  function renderEcuacion() {
    const r = M.regresion;
    let html = `<span class="dep">LeadTime_Real_Dias</span> = <span class="coef">${nf(r.intercepto)}</span>`;
    r.coeficientes.forEach((c) => {
      const signo = c.coef >= 0 ? "+" : "−";
      const cls = c.coef >= 0 ? "pos" : "neg";
      html += `<br>&nbsp;&nbsp;&nbsp;&nbsp;${signo} <span class="coef ${cls}">${nf(Math.abs(c.coef))}</span> × <span class="fac">${c.factor}</span>`;
    });
    document.getElementById("ltEcuacion").innerHTML = html;
  }

  function renderKpis() {
    const r = M.regresion, v = M.validacion, d = M.dataset;
    // R² y los errores se pasan ya formateados: el formato por unidad redondea a 1 decimal
    // y aquí la precisión importa (0.4657 no es "0.5"; 0.527 días no es "0.5").
    document.getElementById("ltKpiRow").innerHTML = [
      gdKpiTile({ icon: "fa-bullseye", bg: "gd-bg-success", label: "R² (ajuste completo)", value: gdFormatNumber(r.r2, 4), sub: `Ajustado ${gdFormatNumber(r.r2_ajustado, 4)}`, col: "col-6 col-lg-2" }),
      gdKpiTile({ icon: "fa-vials", bg: "gd-bg-blue", label: "R² en test (20%)", value: gdFormatNumber(v.r2_test, 4), sub: "Datos no vistos", col: "col-6 col-lg-2" }),
      gdKpiTile({ icon: "fa-ruler", bg: "gd-bg-accent", label: "RMSE", value: `${gdFormatNumber(v.rmse_dias, 3)} días`, sub: "Error cuadrático medio", col: "col-6 col-lg-2" }),
      gdKpiTile({ icon: "fa-ruler-horizontal", bg: "gd-bg-accent", label: "MAE", value: `${gdFormatNumber(v.mae_dias, 3)} días`, sub: "Error absoluto medio", col: "col-6 col-lg-2" }),
      gdKpiTile({ icon: "fa-percent", bg: "gd-bg-warning", label: "MAPE", value: gdFormatPct(v.mape_pct), sub: "Ver limitaciones", col: "col-6 col-lg-2" }),
      gdKpiTile({ icon: "fa-database", bg: "gd-bg-blue", label: "Observaciones", value: gdFormatNumber(d.observaciones, 0), sub: `${d.variables_acp} variables → 5 factores`, col: "col-6 col-lg-2" }),
    ].join("");
  }

  function renderVif() {
    const m = M.multicolinealidad;
    document.getElementById("ltVifResumen").innerHTML = `
      <div class="gd-vif-box antes">Variables originales con VIF &gt; 10<b>${m.vif_originales_sobre_10} de ${m.total_variables}</b>
        <small>Multicolinealidad severa: muchas variables miden lo mismo (VIF &gt; 10 es el umbral habitual).</small></div>
      <div class="gd-vif-box despues">VIF de los 5 factores del ACP<b>${m.vif_factores.map((v) => gdFormatNumber(v, 2)).join(" · ")}</b>
        <small>Los componentes son ortogonales por construcción: el ACP eliminó por completo la multicolinealidad.</small></div>`;

    document.getElementById("ltVifBody").innerHTML = m.top_vif_originales.map((v) => `
      <tr><td style="font-family:'JetBrains Mono',monospace;font-size:11.5px;">${v.variable}</td>
      <td class="text-end"><span class="gd-badge ${v.vif > 10 ? "rojo" : v.vif > 5 ? "amarillo" : "verde"}">${gdFormatNumber(v.vif, 1)}</span></td></tr>`).join("");

    document.getElementById("ltVifHelp").innerHTML = gdGlossaryIcon("VIF",
      "Factor de Inflación de la Varianza: mide cuánto se infla el error de un coeficiente porque esa variable está correlacionada con las demás. VIF > 10 indica multicolinealidad severa: el modelo no puede separar el efecto de cada variable. Un VIF de 1 significa que la variable es totalmente independiente del resto.");
  }

  function renderScree() {
    const comps = M.acp.componentes;
    if (chartScree) chartScree.destroy();
    chartScree = new Chart(document.getElementById("ltChartScree"), {
      data: {
        labels: comps.map((c) => `F${c.n}`),
        datasets: [
          { type: "bar", label: "Autovalor", data: comps.map((c) => c.autovalor), backgroundColor: FACTOR_COLORS, borderRadius: 4, yAxisID: "y" },
          { type: "line", label: "% varianza explicada", data: comps.map((c) => c.pct_varianza), borderColor: "#64748b", backgroundColor: "transparent", yAxisID: "y1", tension: .3, pointRadius: 3 },
        ],
      },
      options: {
        plugins: {
          legend: { position: "bottom", labels: { color: cssVar("--gd-text-muted"), font: { size: 11 }, boxWidth: 12 } },
          tooltip: { callbacks: { afterBody: (items) => comps[items[0].dataIndex].etiqueta_real } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") } },
          y: { grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "Autovalor" } },
          y1: { position: "right", grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "% varianza" } },
        },
      },
    });
  }

  function renderFactores() {
    const coefs = M.regresion.coeficientes;
    document.getElementById("ltFactores").innerHTML = M.acp.componentes.map((c, i) => {
      const coef = coefs[i];
      const maxCarga = Math.max(...c.variables_dominantes.map((v) => Math.abs(v.carga)));
      const cargas = c.variables_dominantes.slice(0, 6).map((v) => {
        const pct = Math.round(Math.abs(v.carga) / maxCarga * 100);
        return `<div class="gd-load">
          <span class="gd-load-name" title="${v.variable}">${v.variable}</span>
          <span class="gd-load-bar"><span class="gd-load-fill" style="width:${pct}%;background:${FACTOR_COLORS[i]};"></span></span>
          <span class="gd-load-val">${v.carga.toFixed(2)}</span></div>`;
      }).join("");
      return `
        <div class="col-12 col-md-6 col-xl-4">
          <div class="gd-factor-card">
            <div class="gd-factor-head">
              <div class="gd-factor-n" style="background:${FACTOR_COLORS[i]};">F${c.n}</div>
              <div style="min-width:0;">
                <div class="gd-factor-name">${coef.factor}</div>
                <div class="gd-factor-real">${c.etiqueta_real}</div>
              </div>
              <div class="gd-factor-coef">coef.<b class="${coef.coef >= 0 ? "pos" : "neg"}">${coef.coef >= 0 ? "+" : "−"}${nf(Math.abs(coef.coef), 4)}</b></div>
            </div>
            <div class="gd-factor-meta">
              Autovalor ${gdFormatNumber(c.autovalor, 2)} · explica ${gdFormatPct(c.pct_varianza)} de la varianza ·
              ${coef.coef >= 0 ? "sube" : "baja"} el Lead Time ${gdFormatNumber(Math.abs(coef.coef), 3)} días por cada +1 desv. estándar
            </div>
            ${cargas}
          </div>
        </div>`;
    }).join("");
  }

  function renderSliders() {
    document.getElementById("ltSliders").innerHTML = M.regresion.coeficientes.map((c, i) => `
      <div class="gd-slider-row">
        <label for="f${i}"><span>${c.etiqueta_real}</span><b id="f${i}v">0.0</b></label>
        <input type="range" class="form-range" id="f${i}" min="-3" max="3" step="0.1" value="0" data-factor="${c.factor}">
      </div>`).join("") +
      `<button class="gd-btn gd-btn-outline gd-btn-sm w-100 mt-2" id="ltReset"><i class="fa-solid fa-rotate-left"></i> Volver a la operación promedio</button>`;

    M.regresion.coeficientes.forEach((c, i) => {
      document.getElementById(`f${i}`).addEventListener("input", (e) => {
        document.getElementById(`f${i}v`).textContent = parseFloat(e.target.value).toFixed(1);
        recalcular();
      });
    });
    document.getElementById("ltReset").addEventListener("click", () => {
      M.regresion.coeficientes.forEach((c, i) => {
        document.getElementById(`f${i}`).value = 0;
        document.getElementById(`f${i}v`).textContent = "0.0";
      });
      recalcular();
    });
  }

  async function recalcular() {
    const factores = {};
    M.regresion.coeficientes.forEach((c, i) => { factores[c.factor] = parseFloat(document.getElementById(`f${i}`).value); });
    const r = await RansaAPI.post("/api/leadtime/predict", { factores });

    const diff = r.leadtime_estimado_dias - r.media_historica;
    document.getElementById("ltResultado").innerHTML = `
      <div class="val">${gdFormatNumber(r.leadtime_estimado_dias, 2)} <span style="font-size:20px;">días</span></div>
      <div class="lbl">Lead Time estimado</div>
      <div class="cmp">Media histórica: ${gdFormatNumber(r.media_historica, 2)} días ·
        <b style="color:${diff > 0 ? "var(--gd-danger)" : diff < 0 ? "var(--gd-success)" : "var(--gd-text-muted)"};">
        ${diff > 0 ? "+" : ""}${gdFormatNumber(diff, 2)} días</b></div>`;

    if (chartAportes) chartAportes.destroy();
    chartAportes = new Chart(document.getElementById("ltChartAportes"), {
      type: "bar",
      data: {
        labels: r.aportes.map((a, i) => `F${i + 1}`),
        datasets: [{ label: "Aporte al Lead Time (días)", data: r.aportes.map((a) => a.aporte_dias), backgroundColor: FACTOR_COLORS, borderRadius: 4 }],
      },
      options: {
        indexAxis: "y",
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { title: (it) => r.aportes[it[0].dataIndex].etiqueta_real,
            label: (c) => `${c.parsed.x >= 0 ? "+" : ""}${c.parsed.x.toFixed(3)} días` } },
        },
        scales: {
          x: { grid: { color: cssVar("--gd-border") }, ticks: { color: cssVar("--gd-text-subtle") }, title: { display: true, text: "Días sobre el intercepto" } },
          y: { grid: { display: false }, ticks: { color: cssVar("--gd-text-subtle") } },
        },
      },
    });
  }

  function renderNotas() {
    const a = M.acp, d = M.dataset, v = M.validacion;
    const notas = [
      ["ok", `<b>Factores nombrados por sus cargas.</b> Cada factor recibe el tema que domina sus 12 variables con mayor carga (geografía andina, clima y riesgo natural, conflictividad, macroeconomía, operación y costos…) y su signo se orienta para que la variable dominante cargue en positivo. Así el nombre siempre corresponde a lo que el factor mide.`],
      ["ok", `<b>Validación honesta.</b> ${v.metodo}: R² en test = ${v.r2_test} frente a ${M.regresion.r2} en el ajuste completo — <b>no hay sobreajuste</b>. Tras el ACP, los 5 factores tienen VIF = 1: la multicolinealidad de las ${d.variables_acp} variables originales desaparece.`],
      ["info", `<b>El criterio de Kaiser retendría ${a.kaiser_real} componentes.</b> Se conservan 5 por parsimonia, interpretabilidad y para comparar directamente con el prototipo anterior (que usa 5). Los 5 factores explican ${gdFormatPct(a.varianza_acumulada_pct)} de la varianza total.`],
      ["warn", `<b>R² = ${M.regresion.r2}: la red peruana es más heterogénea.</b> El Lead Time va de horas (distribución urbana en Lima) a varios días (cabotaje y navegación amazónica), y ese salto lo explica sobre todo el modo de transporte, que el ACP no ve por ser categórico. Este modelo es para <b>entender qué factores empujan el Lead Time</b>; para predecir viaje a viaje, el Simulador usa un regresor <b>Gradient Boosting</b>${M.ml_regresor && M.ml_regresor.leadtime_real_dias ? ` con <b>R² = ${M.ml_regresor.leadtime_real_dias.r2}</b> y MAE = ${gdFormatNumber(M.ml_regresor.leadtime_real_dias.mae, 3)} días en datos de prueba` : ""}.`],
      ["warn", `<b>El MAPE (${gdFormatPct(v.mape_pct)}) exagera el error.</b> El Lead Time baja hasta ${M.objetivo.min} días en entregas urbanas, y un error porcentual sobre valores tan pequeños se dispara. Son más honestos el <b>MAE (${gdFormatNumber(v.mae_dias, 3)} días)</b> y el <b>RMSE (${gdFormatNumber(v.rmse_dias, 3)} días)</b>, frente a una media de ${M.objetivo.media} días.`],
      ["info", `<b>Fuente de datos.</b> ${d.archivo} (${gdFormatNumber(d.observaciones, 0)} × ${d.variables_totales}, simulado). Entran al ACP ${d.variables_acp} variables numéricas; se excluyen ${(d.excluidas_por_faltantes || []).length} que solo existen para un modo (vuelos, buques, río) por tener más de 60% de faltantes, y ${d.imputadas_por_mediana.length} con faltantes menores se imputan por la mediana.`],
    ];
    const icon = { ok: "fa-circle-check", warn: "fa-triangle-exclamation", info: "fa-circle-info" };
    document.getElementById("ltNotas").innerHTML = notas.map(([t, txt]) =>
      `<div class="gd-nota"><i class="fa-solid ${icon[t]} ${t}"></i><div>${txt}</div></div>`).join("");
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      M = await RansaAPI.get("/api/leadtime/model");
    } catch (err) {
      document.getElementById("ltNoModel").style.display = "flex";
      return;
    }
    document.getElementById("ltContent").style.display = "block";
    document.getElementById("ltNvars").textContent = M.dataset.variables_acp;
    renderEcuacion();
    renderKpis();
    renderVif();
    renderScree();
    renderFactores();
    renderSliders();
    renderNotas();
    await recalcular();
    gdInitTooltips(document);
  });
})();
