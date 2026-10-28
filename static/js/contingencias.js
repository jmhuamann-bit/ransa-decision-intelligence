(function () {
  let state = { page: 1, page_size: 20, total_pages: 1 };
  let modalNueva, modalDetalle;

  function severidadBadge(sev) {
    const map = { Critica: "rojo", Alta: "rojo", Media: "amarillo", Baja: "verde" };
    const sem = map[sev] || "gris";
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${sev === "Critica" ? "Crítica" : sev}</span>`;
  }

  function estadoBadge(estado) {
    const map = { Abierta: "rojo", "Pendiente Aprobación Directiva": "amarillo", "En Gestion": "amarillo", Comunicada: "verde", Resuelta: "verde" };
    const sem = map[estado] || "gris";
    const label = estado === "En Gestion" ? "En Gestión" : estado;
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${label}</span>`;
  }

  function tile(icon, bg, label, value) {
    return `<div class="col-6 col-lg-3"><div class="gd-kpi">
      <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
      <div class="gd-kpi-label">${label}</div><div class="gd-kpi-value">${value}</div>
    </div></div>`;
  }

  async function loadSummary() {
    const s = await RansaAPI.get("/api/contingencies/summary");
    document.getElementById("gdContSummaryRow").innerHTML = [
      tile("fa-triangle-exclamation", "gd-bg-danger", "Abiertas", gdFormatNumber(s.abiertas, 0)),
      tile("fa-screwdriver-wrench", "gd-bg-warning", "En Gestión", gdFormatNumber(s.en_gestion, 0)),
      tile("fa-circle-check", "gd-bg-success", "Resueltas", gdFormatNumber(s.resueltas, 0)),
      tile("fa-fire", "gd-bg-danger", "Críticas abiertas", gdFormatNumber(s.criticas_abiertas, 0)),
    ].join("");
  }

  function currentFilters() {
    return {
      busqueda: document.getElementById("fContBusqueda").value,
      estado: document.getElementById("fContEstado").value,
      severidad: document.getElementById("fContSeveridad").value,
      tipo: document.getElementById("fContTipo").value,
    };
  }

  async function loadTable(resetPage = false) {
    if (resetPage) state.page = 1;
    const filters = currentFilters();
    const qs = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) qs.set(k, v); });
    qs.set("page", state.page);
    qs.set("page_size", state.page_size);

    const tbody = document.getElementById("gdContBody");
    tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4 text-muted">Cargando...</td></tr>`;

    const data = await RansaAPI.get(`/api/contingencies?${qs.toString()}`);
    state.total_pages = data.total_pages;
    document.getElementById("gdContTotal").textContent = `${gdFormatNumber(data.total, 0)} registros`;
    document.getElementById("gdContPaginaInfo").textContent = `Página ${data.page} de ${data.total_pages}`;

    if (!data.items.length) {
      tbody.innerHTML = `<tr><td colspan="8"><div class="gd-empty-state"><i class="fa-regular fa-circle-check"></i><div>Sin resultados</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map((a) => `
      <tr>
        <td>${severidadBadge(a.severidad)}</td>
        <td>${a.titulo}</td>
        <td class="gd-mono">${a.id_viaje || "—"}</td>
        <td>${a.tipo === "prediccion_ia" ? "Predicción IA" : a.tipo === "plan_contingencia_ia" ? "Plan IA" : "Manual"}</td>
        <td>${a.probabilidad_pct !== null ? gdFormatPct(a.probabilidad_pct) : "—"}</td>
        <td>${estadoBadge(a.estado)}</td>
        <td>${gdFormatDate(a.creado_en)}</td>
        <td><button class="gd-btn gd-btn-outline gd-btn-sm btn-ver" data-id="${a.id}">Ver</button></td>
      </tr>`).join("");

    tbody.querySelectorAll(".btn-ver").forEach((btn) => btn.addEventListener("click", () => verDetalle(btn.dataset.id)));
  }

  async function verDetalle(id) {
    const a = await RansaAPI.get(`/api/contingencies/${id}`);
    const emb = a.embarque;
    document.getElementById("gdDetalleBody").innerHTML = `
      <div class="d-flex justify-content-between mb-2">${severidadBadge(a.severidad)} ${estadoBadge(a.estado)}</div>
      <div style="font-weight:700;margin-bottom:6px;">${a.titulo}</div>
      <div style="color:var(--gd-text-muted);margin-bottom:10px;">${a.descripcion || "Sin descripción"}</div>
      ${emb ? `
        <div class="gd-label">Embarque asociado</div>
        <div class="mb-2">${emb.id_viaje} — ${emb.ciudad_origen} → ${emb.ciudad_destino} (${emb.tipo_transporte}, prioridad ${emb.prioridad_cliente})</div>
      ` : ""}
      ${a.tipo === "plan_contingencia_ia" ? `
        <div class="gd-label">Plan de comunicación ${gdGlossaryIcon("Plan de comunicación", "Registro de a quién y cuándo se avisó de este plan de contingencia. Primero solo se avisa a los directivos; el resto de audiencias (áreas, conductor, cliente) solo se notifican cuando un directivo aprueba.")}</div>
        <div class="mb-2" style="white-space:pre-line;font-size:12.5px;background:var(--gd-surface-2);border-radius:8px;padding:10px;">${a.canal_notificacion || "—"}</div>
      ` : `
        <div class="gd-label">Canales de notificación preparados</div>
        <div class="mb-2">${a.canales_preparados.map((c) => `<span class="gd-badge gris me-1">${c}</span>`).join("")}</div>
      `}
      <div style="font-size:11.5px;color:var(--gd-text-subtle);">Creada: ${gdFormatDate(a.creado_en)}${a.resuelto_en ? " · Resuelta: " + gdFormatDate(a.resuelto_en) : ""}</div>
    `;
    gdInitTooltips(document.getElementById("gdDetalleBody"));

    const footer = document.getElementById("gdDetalleFooter");
    footer.innerHTML = "";
    if (a.estado === "Pendiente Aprobación Directiva") {
      const btnAprobar = document.createElement("button");
      btnAprobar.className = "gd-btn gd-btn-primary";
      btnAprobar.innerHTML = '<i class="fa-solid fa-check-double"></i> Aprobar y comunicar a todo el equipo';
      btnAprobar.onclick = () => aprobarPlan(a.id);
      footer.appendChild(btnAprobar);
      modalDetalle.show();
      return;
    }
    if (a.estado !== "En Gestion") {
      const btn1 = document.createElement("button");
      btn1.className = "gd-btn gd-btn-outline";
      btn1.textContent = "Marcar en gestión";
      btn1.onclick = () => cambiarEstado(a.id, "En Gestion");
      footer.appendChild(btn1);
    }
    if (a.estado !== "Resuelta") {
      const btn2 = document.createElement("button");
      btn2.className = "gd-btn gd-btn-primary";
      btn2.innerHTML = '<i class="fa-solid fa-check"></i> Resolver';
      btn2.onclick = () => cambiarEstado(a.id, "Resuelta");
      footer.appendChild(btn2);
    }
    modalDetalle.show();
  }

  async function aprobarPlan(id) {
    try {
      await RansaAPI.post(`/api/contingencies/${id}/aprobar`, {});
      modalDetalle.hide();
      await Promise.all([loadSummary(), loadTable()]);
    } catch (err) {
      alert(err.message);
    }
  }

  async function cambiarEstado(id, estado) {
    try {
      await RansaAPI.put(`/api/contingencies/${id}/estado`, { estado });
      modalDetalle.hide();
      await Promise.all([loadSummary(), loadTable()]);
    } catch (err) {
      alert(err.message);
    }
  }

  async function crearContingencia() {
    const errBox = document.getElementById("gdContFormError");
    errBox.style.display = "none";
    try {
      await RansaAPI.post("/api/contingencies", {
        titulo: document.getElementById("cTitulo").value,
        id_viaje: document.getElementById("cIdViaje").value,
        severidad: document.getElementById("cSeveridad").value,
        descripcion: document.getElementById("cDescripcion").value,
      });
      modalNueva.hide();
      document.getElementById("cTitulo").value = "";
      document.getElementById("cIdViaje").value = "";
      document.getElementById("cDescripcion").value = "";
      await Promise.all([loadSummary(), loadTable(true)]);
    } catch (err) {
      errBox.textContent = err.message;
      errBox.style.display = "block";
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    modalNueva = new bootstrap.Modal(document.getElementById("modalContingencia"));
    modalDetalle = new bootstrap.Modal(document.getElementById("modalDetalle"));

    await Promise.all([loadSummary(), loadTable(true)]);

    const debouncedReload = gdDebounce(() => loadTable(true), 400);
    document.getElementById("fContBusqueda").addEventListener("input", debouncedReload);
    ["fContEstado", "fContSeveridad", "fContTipo"].forEach((id) =>
      document.getElementById(id).addEventListener("change", () => loadTable(true)));

    document.getElementById("btnContAnterior").addEventListener("click", () => { if (state.page > 1) { state.page--; loadTable(); } });
    document.getElementById("btnContSiguiente").addEventListener("click", () => { if (state.page < state.total_pages) { state.page++; loadTable(); } });

    document.getElementById("btnNuevaContingencia").addEventListener("click", () => {
      document.getElementById("gdContFormError").style.display = "none";
      modalNueva.show();
    });
    document.getElementById("btnGuardarContingencia").addEventListener("click", crearContingencia);
  });
})();
