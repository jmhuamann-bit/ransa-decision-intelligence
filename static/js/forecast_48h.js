(function () {
  function prioridadBadge(p) {
    const cls = p === "Alta" ? "rojo" : p === "Media" ? "amarillo" : "verde";
    return `<span class="gd-badge ${cls}"><span class="gd-dot ${cls}"></span>Prioridad ${p}</span>`;
  }
  function impactoBadge(nivel) {
    const cls = nivel === "Muy Alto" ? "rojo" : nivel === "Alto" ? "amarillo" : nivel === "Medio" ? "gris" : "verde";
    return `<span class="gd-badge ${cls}"><span class="gd-dot ${cls}"></span>Impacto ${nivel}</span>`;
  }

  function scenarioCardHtml(e) {
    return `
      <div class="col-12 col-lg-6 col-xxl-4">
        <div class="gd-card gd-scenario-card">
          <div class="gd-scenario-head">
            <div class="gd-scenario-letter" style="background:${e.color};">${e.letra}</div>
            <div>
              <div class="gd-scenario-title">Escenario ${e.letra} · ${e.titulo}</div>
              <div class="gd-scenario-sub">${e.corredores_probables.join(" · ")}</div>
            </div>
            <div class="gd-scenario-prob">
              <div class="val">${gdFormatPct(e.probabilidad_48h_pct, 0)}</div>
              <div class="lbl">Prob. 48h</div>
            </div>
          </div>
          <div class="gd-scenario-body">
            <div class="d-flex gap-2 flex-wrap">${impactoBadge(e.impacto_nivel)}${prioridadBadge(e.prioridad)}</div>

            <div>
              <div class="gd-scenario-block-label"><i class="fa-solid fa-circle-question"></i> Explicación</div>
              <div class="gd-scenario-block-text">${e.explicacion}</div>
            </div>
            <div>
              <div class="gd-scenario-block-label"><i class="fa-solid fa-database"></i> Justificación (datos históricos)</div>
              <div class="gd-scenario-block-text">${e.justificacion}</div>
            </div>
            <div>
              <div class="gd-scenario-block-label"><i class="fa-solid fa-bullseye"></i> Recomendación de la IA</div>
              <div class="gd-scenario-block-text"><b>${e.recomendacion}</b></div>
            </div>
            <div>
              <div class="gd-scenario-block-label"><i class="fa-solid fa-list-check"></i> Acciones propuestas</div>
              <ol class="gd-scenario-actions">${e.acciones_propuestas.map((a) => `<li>${a}</li>`).join("")}</ol>
            </div>

            <div class="gd-scenario-metrics">
              <div class="gd-scenario-metric">Impacto económico<b>${gdFormatPEN(e.impacto_economico_estimado_pen)}</b></div>
              <div class="gd-scenario-metric">Clientes críticos<b>${gdFormatNumber(e.clientes_criticos_expuestos, 0)}</b></div>
              <div class="gd-scenario-metric">Riesgo estimado<b>${gdFormatPct(e.probabilidad_48h_pct, 0)}</b></div>
            </div>
          </div>
          <div class="gd-scenario-footer">
            <button class="gd-btn gd-btn-primary gd-btn-sm w-100 btn-planes" data-id="${e.id}">
              <i class="fa-solid fa-diagram-project"></i> Ver planes de contingencia (A/B/C/D)
            </button>
          </div>
        </div>
      </div>`;
  }

  // ---------- Centro de Contingencias Inteligente: planes A/B/C/D ----------
  let modalPlanes, planesData, escenarioActual;

  function planCardHtml(p) {
    const otifCls = p.delta_otif_pts > 0 ? "up" : p.delta_otif_pts < 0 ? "down" : "";
    const costoCls = p.delta_costo_pct > 0 ? "down" : "up";
    const riesgoCls = p.nivel_riesgo === "Bajo" ? "up" : p.nivel_riesgo === "Crítico" || p.nivel_riesgo === "Alto" ? "down" : "";
    return `
      <div class="col-12 col-md-6 col-xl-3">
        <div class="gd-plan-card ${p.recomendado ? "recomendado" : ""}">
          <div class="gd-plan-head">
            <div class="gd-plan-letra">${p.id}</div>
            <div>
              <div class="gd-plan-nombre">${p.nombre}</div>
              ${p.recomendado ? '<span class="gd-badge verde"><span class="gd-dot verde"></span>Recomendado por la IA</span>'
                              : `<span style="font-size:11px;color:var(--gd-text-subtle);">Puntaje ${p.score}/100</span>`}
            </div>
          </div>
          <div class="gd-plan-desc">${p.descripcion}</div>

          <div class="gd-plan-metrics">
            <div class="gd-plan-metric">OTIF esperado<b class="${otifCls}">${gdFormatPct(p.otif_pct)} (${p.delta_otif_pts > 0 ? "+" : ""}${p.delta_otif_pts} pts)</b></div>
            <div class="gd-plan-metric">Costo<b class="${costoCls}">${gdFormatPEN(p.costo_pen)}</b></div>
            <div class="gd-plan-metric">Tiempo<b>${gdFormatNumber(p.leadtime_dias)} días</b></div>
            <div class="gd-plan-metric">CO₂<b>${gdFormatNumber(p.co2_ton, 3)} ton</b></div>
            <div class="gd-plan-metric">Riesgo residual<b class="${riesgoCls}">${gdFormatPct(p.riesgo_pct)}</b></div>
            <div class="gd-plan-metric">Nivel de riesgo<b class="${riesgoCls}">${p.nivel_riesgo}</b></div>
          </div>

          <div class="gd-plan-label ok"><i class="fa-solid fa-plus"></i> Ventajas</div>
          <ul class="gd-plan-pros">${p.ventajas.map((v) => `<li>${v}</li>`).join("")}</ul>
          <div class="gd-plan-label no"><i class="fa-solid fa-minus"></i> Desventajas</div>
          <ul class="gd-plan-pros contra">${p.desventajas.map((v) => `<li>${v}</li>`).join("")}</ul>

          <div class="gd-plan-foot">
            <button class="gd-btn ${p.recomendado ? "gd-btn-accent" : "gd-btn-outline"} gd-btn-sm w-100 btn-notif-plan" data-plan="${p.id}">
              <i class="fa-solid fa-paper-plane"></i> Notificar a Directivos con este plan
            </button>
          </div>
        </div>
      </div>`;
  }

  async function verPlanes(escenario) {
    escenarioActual = escenario;
    document.getElementById("planesTitulo").textContent = `Planes de contingencia — ${escenario.titulo}`;
    document.getElementById("planesSub").textContent = `Corredor ${escenario.corredor_principal} · alternativas comparadas por la IA`;
    document.getElementById("planesGrid").innerHTML = `<div class="col-12 text-center py-4 text-muted">Calculando planes...</div>`;
    document.getElementById("planesBaseline").innerHTML = "";
    document.getElementById("planesJustificacion").innerHTML = "";
    modalPlanes.show();

    try {
      const qs = new URLSearchParams({ corredor: escenario.corredor_principal, categoria: escenario.categoria });
      planesData = await RansaAPI.get(`/api/strategic/plans?${qs.toString()}`);
    } catch (err) {
      document.getElementById("planesGrid").innerHTML = `<div class="col-12"><div class="gd-empty-state"><i class="fa-solid fa-triangle-exclamation"></i><div>${err.message}</div></div></div>`;
      return;
    }

    const b = planesData.baseline, s = planesData.sin_accion;
    document.getElementById("planesBaseline").innerHTML = `
      <div class="item">Línea base histórica (OTIF)<b>${gdFormatPct(b.otif_pct)}</b></div>
      <div class="item">Embarques analizados<b>${gdFormatNumber(b.muestras, 0)}</b></div>
      <div class="item danger">Sin acción — OTIF<b>${gdFormatPct(s.otif_pct)}</b></div>
      <div class="item danger">Sin acción — Costo<b>${gdFormatPEN(s.costo_pen)}</b></div>
      <div class="item danger">Sin acción — Riesgo<b>${gdFormatPct(s.riesgo_pct)} (${s.nivel_riesgo})</b></div>`;

    document.getElementById("planesGrid").innerHTML = planesData.planes.map(planCardHtml).join("");
    document.getElementById("planesJustificacion").innerHTML =
      `<i class="fa-solid fa-robot me-1"></i><b>Recomendación del AI Decision Assistant:</b> ${planesData.justificacion_recomendacion}`;

    document.querySelectorAll("#planesGrid .btn-notif-plan").forEach((btn) => {
      btn.addEventListener("click", () => notificarConPlan(btn.dataset.plan, btn));
    });
  }

  function buildPlanPayload(e, plan) {
    const acciones = e.acciones_propuestas.map((a, i) => `${i + 1}. ${a}`).join("\n");
    return {
      titulo: `Plan ${plan.id} (${plan.nombre}) — ${e.titulo} en ${e.corredor_principal}`,
      severidad: e.prioridad === "Alta" ? "Critica" : e.prioridad === "Media" ? "Alta" : "Media",
      probabilidad_pct: e.probabilidad_48h_pct,
      descripcion:
        `Escenario ${e.letra} — ${e.titulo} (${e.corredor_principal})\n\n` +
        `Explicación: ${e.explicacion}\n\nJustificación: ${e.justificacion}\n\n` +
        `PLAN SELECCIONADO: ${plan.id} — ${plan.nombre}\n${plan.descripcion}\n\n` +
        `Resultado esperado del plan:\n` +
        `• OTIF esperado: ${gdFormatPct(plan.otif_pct)} (${plan.delta_otif_pts > 0 ? "+" : ""}${plan.delta_otif_pts} pts vs. no actuar)\n` +
        `• Costo: ${gdFormatPEN(plan.costo_pen)} (${plan.delta_costo_pct > 0 ? "+" : ""}${plan.delta_costo_pct}%)\n` +
        `• Tiempo: ${gdFormatNumber(plan.leadtime_dias)} días · CO₂: ${gdFormatNumber(plan.co2_ton, 3)} ton\n` +
        `• Riesgo residual: ${gdFormatPct(plan.riesgo_pct)} (${plan.nivel_riesgo})\n\n` +
        `Ventajas: ${plan.ventajas.join(" ")}\nDesventajas: ${plan.desventajas.join(" ")}\n\n` +
        `Acciones propuestas:\n${acciones}\n\n` +
        `${planesData.justificacion_recomendacion}`,
    };
  }

  async function notificarConPlan(planId, btn) {
    const plan = planesData.planes.find((p) => p.id === planId);
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';
    try {
      await RansaAPI.post("/api/contingencies/plan-ia", buildPlanPayload(escenarioActual, plan));
      btn.innerHTML = '<i class="fa-solid fa-check"></i> Directivos notificados';
      btn.classList.remove("gd-btn-accent", "gd-btn-outline");
      btn.classList.add("gd-btn-outline");
    } catch (err) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-paper-plane"></i> Notificar a Directivos con este plan';
      alert(err.message);
    }
  }

  async function load() {
    const { escenarios } = await RansaAPI.get("/api/strategic/scenarios-48h");
    const grid = document.getElementById("scenarioGrid");
    if (!escenarios.length) {
      grid.innerHTML = `<div class="col-12"><div class="gd-empty-state"><i class="fa-regular fa-circle-check"></i><div>Sin escenarios relevantes en este momento.</div></div></div>`;
      return;
    }
    grid.innerHTML = escenarios.map(scenarioCardHtml).join("");
    grid.querySelectorAll(".btn-planes").forEach((btn) => {
      const escenario = escenarios.find((e) => e.id === btn.dataset.id);
      btn.addEventListener("click", () => verPlanes(escenario));
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    modalPlanes = new bootstrap.Modal(document.getElementById("modalPlanes"));
    load();
  });
})();
