(function () {
  let state = { page: 1, page_size: 25, total_pages: 1 };

  const filterIds = {
    fSector: "sector_cliente", fTransporte: "tipo_transporte", fPrioridad: "prioridad_cliente",
    fRiesgo: "nivel_riesgo", fDeptoOrigen: "departamento_origen", fDeptoDestino: "departamento_destino",
    fCorredor: "corredor_logistico",
  };

  function currentFilters() {
    const f = { busqueda: document.getElementById("fBusqueda").value, otif: document.getElementById("fOtif").value,
      fecha_desde: document.getElementById("fFechaDesde").value, fecha_hasta: document.getElementById("fFechaHasta").value };
    for (const [id, key] of Object.entries(filterIds)) f[key] = document.getElementById(id).value;
    return f;
  }

  async function loadFilterOptions() {
    const opts = await RansaAPI.get("/api/monitoring/filters");
    for (const [id, key] of Object.entries(filterIds)) {
      const sel = document.getElementById(id);
      const values = opts[key] || [];
      sel.innerHTML = `<option value="">Todos</option>` + values.map((v) => `<option value="${v}">${v}</option>`).join("");
    }
  }

  function semaforo(sem, texto) {
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${texto}</span>`;
  }

  async function loadData(resetPage = false) {
    if (resetPage) state.page = 1;
    const filters = currentFilters();
    const qs = new URLSearchParams();
    Object.entries(filters).forEach(([k, v]) => { if (v) qs.set(k, v); });
    qs.set("page", state.page);
    qs.set("page_size", state.page_size);

    const tbody = document.getElementById("gdMonitoreoBody");
    tbody.innerHTML = `<tr><td colspan="13" class="text-center py-4 text-muted">Cargando...</td></tr>`;

    const data = await RansaAPI.get(`/api/monitoring/shipments?${qs.toString()}`);
    state.total_pages = data.total_pages;

    document.getElementById("gdTotalResultados").textContent = `${gdFormatNumber(data.total, 0)} embarques encontrados`;
    document.getElementById("gdPaginaInfo").textContent = `Página ${data.page} de ${data.total_pages}`;

    if (!data.items.length) {
      tbody.innerHTML = `<tr><td colspan="13"><div class="gd-empty-state"><i class="fa-regular fa-folder-open"></i><div>No se encontraron embarques con estos filtros</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map((s) => `
      <tr>
        <td class="gd-mono">${s.id_viaje}</td>
        <td>${gdFormatDate(s.fecha)}</td>
        <td>${s.sector_cliente || "—"}</td>
        <td>${s.ciudad_origen || "—"}</td>
        <td>${s.ciudad_destino || "—"}</td>
        <td>${s.corredor_logistico || "—"}</td>
        <td>${s.tipo_transporte || "—"}</td>
        <td>${s.prioridad_cliente || "—"}</td>
        <td>${gdFormatNumber(s.tiempo_programado_horas, 1)}</td>
        <td>${gdFormatNumber(s.leadtime_real_dias, 2)} d</td>
        <td>${s.otif ? '<span class="gd-badge verde">Cumplido</span>' : '<span class="gd-badge rojo">Incumplido</span>'}</td>
        <td>${gdFormatPEN(s.costo_total_pen)}</td>
        <td>${semaforo(s.semaforo, s.nivel_riesgo || "—")}</td>
      </tr>`).join("");
  }

  function applyUrlFilters() {
    const params = new URLSearchParams(window.location.search);
    for (const [id, key] of Object.entries(filterIds)) {
      if (params.has(key)) document.getElementById(id).value = params.get(key);
    }
    if (params.has("busqueda")) document.getElementById("fBusqueda").value = params.get("busqueda");
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await loadFilterOptions();
    applyUrlFilters();
    await loadData(true);

    const debouncedReload = gdDebounce(() => loadData(true), 400);
    document.getElementById("fBusqueda").addEventListener("input", debouncedReload);
    ["fSector", "fTransporte", "fPrioridad", "fRiesgo", "fDeptoOrigen", "fDeptoDestino", "fCorredor", "fOtif", "fFechaDesde", "fFechaHasta"]
      .forEach((id) => document.getElementById(id).addEventListener("change", () => loadData(true)));

    document.getElementById("btnLimpiar").addEventListener("click", () => {
      document.getElementById("fBusqueda").value = "";
      document.getElementById("fOtif").value = "";
      document.getElementById("fFechaDesde").value = "";
      document.getElementById("fFechaHasta").value = "";
      Object.keys(filterIds).forEach((id) => (document.getElementById(id).value = ""));
      loadData(true);
    });

    document.getElementById("btnAnterior").addEventListener("click", () => {
      if (state.page > 1) { state.page -= 1; loadData(); }
    });
    document.getElementById("btnSiguiente").addEventListener("click", () => {
      if (state.page < state.total_pages) { state.page += 1; loadData(); }
    });

    document.getElementById("btnExportarCsv").addEventListener("click", () => {
      const filters = currentFilters();
      const qs = new URLSearchParams();
      Object.entries(filters).forEach(([k, v]) => { if (v) qs.set(k, v); });
      window.location.href = `/api/monitoring/shipments.csv?${qs.toString()}`;
    });
  });
})();
