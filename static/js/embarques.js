(function () {
  let state = { page: 1, page_size: 20, total_pages: 1 };
  let modal;

  function semaforo(nivel) {
    const sem = nivel === "Bajo" ? "verde" : nivel === "Medio" ? "amarillo" : "rojo";
    return `<span class="gd-badge ${sem}"><span class="gd-dot ${sem}"></span>${nivel || "—"}</span>`;
  }

  async function loadOptions() {
    const [filters, simOptions] = await Promise.all([
      RansaAPI.get("/api/monitoring/filters"),
      RansaAPI.get("/api/simulator/options"),
    ]);
    const fill = (id, values) => {
      document.getElementById(id).innerHTML = values.map((v) => `<option value="${v}">${v}</option>`).join("");
    };
    fill("fDeptoOrigen", filters.departamento_origen);
    fill("fMunOrigen", filters.ciudad_origen);
    fill("fDeptoDestino", filters.departamento_destino);
    fill("fMunDestino", filters.ciudad_destino);
    fill("fSector", filters.sector_cliente);
    fill("fTransporte", filters.tipo_transporte);
    fill("fVehiculo", filters.tipo_vehiculo);
    fill("fCarga", simOptions.tipo_carga);
    fill("fPrioridad", simOptions.prioridad_cliente);
  }

  async function loadTable() {
    const tbody = document.getElementById("gdEmbBody");
    tbody.innerHTML = `<tr><td colspan="10" class="text-center py-4 text-muted">Cargando...</td></tr>`;
    const qs = new URLSearchParams({ page: state.page, page_size: state.page_size });
    const data = await RansaAPI.get(`/api/shipments?${qs.toString()}`);
    state.total_pages = data.total_pages;
    document.getElementById("gdEmbTotal").textContent = `${gdFormatNumber(data.total, 0)} embarques`;
    document.getElementById("gdEmbPaginaInfo").textContent = `Página ${data.page} de ${data.total_pages}`;

    if (!data.items.length) {
      tbody.innerHTML = `<tr><td colspan="10"><div class="gd-empty-state"><i class="fa-regular fa-folder-open"></i><div>Sin embarques</div></div></td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map((s) => `
      <tr>
        <td class="gd-mono">${s.id_viaje}</td>
        <td>${gdFormatDate(s.fecha)}</td>
        <td>${s.corredor_logistico || "—"}</td>
        <td>${s.tipo_transporte || "—"}</td>
        <td>${s.prioridad_cliente || "—"}</td>
        <td>${s.leadtime_real_dias !== null ? gdFormatNumber(s.leadtime_real_dias, 2) + " d" : "Pendiente"}</td>
        <td>${s.otif ? '<span class="gd-badge verde">Cumplido</span>' : '<span class="gd-badge rojo">Incumplido</span>'}</td>
        <td>${gdFormatPEN(s.costo_total_pen)}</td>
        <td>${semaforo(s.nivel_riesgo)}</td>
        <td class="text-end">
          <button class="gd-icon-btn btn-editar" data-id="${s.id}" title="Editar" style="width:30px;height:30px;"><i class="fa-solid fa-pen"></i></button>
          <button class="gd-icon-btn btn-eliminar" data-id="${s.id}" data-viaje="${s.id_viaje}" title="Eliminar" style="width:30px;height:30px;"><i class="fa-solid fa-trash"></i></button>
        </td>
      </tr>`).join("");

    tbody.querySelectorAll(".btn-editar").forEach((btn) => btn.addEventListener("click", () => abrirEdicion(btn.dataset.id)));
    tbody.querySelectorAll(".btn-eliminar").forEach((btn) => btn.addEventListener("click", () => eliminar(btn.dataset.id, btn.dataset.viaje)));
  }

  function limpiarFormulario() {
    document.getElementById("formEmbarque").reset();
    document.getElementById("fId").value = "";
    document.getElementById("gdEmbFormError").style.display = "none";
    document.getElementById("fFlota").value = 85;
  }

  function abrirCreacion() {
    limpiarFormulario();
    document.getElementById("modalEmbarqueTitulo").textContent = "Nuevo Embarque";
    modal.show();
  }

  async function abrirEdicion(id) {
    limpiarFormulario();
    document.getElementById("modalEmbarqueTitulo").textContent = "Editar Embarque";
    const s = await RansaAPI.get(`/api/shipments/${id}`);
    document.getElementById("fId").value = s.id;
    document.getElementById("fFecha").value = s.fecha;
    document.getElementById("fPrioridad").value = s.prioridad_cliente;
    document.getElementById("fDeptoOrigen").value = s.departamento_origen;
    document.getElementById("fMunOrigen").value = s.ciudad_origen;
    document.getElementById("fDeptoDestino").value = s.departamento_destino;
    document.getElementById("fMunDestino").value = s.ciudad_destino;
    document.getElementById("fTransporte").value = s.tipo_transporte;
    document.getElementById("fVehiculo").value = s.tipo_vehiculo;
    document.getElementById("fCarga").value = s.tipo_carga;
    document.getElementById("fSector").value = s.sector_cliente;
    document.getElementById("fPeso").value = s.peso_toneladas;
    document.getElementById("fVolumen").value = s.volumen_m3;
    document.getElementById("fDistancia").value = s.distancia_km;
    document.getElementById("fTiempoProg").value = s.tiempo_programado_horas;
    document.getElementById("fFlota").value = s.disponibilidad_flota_pct;
    document.getElementById("fCostoTransporte").value = s.costo_transporte_pen;
    document.getElementById("fCostoPeajes").value = s.costo_peajes_pen;
    modal.show();
  }

  function payloadFromForm() {
    return {
      fecha: document.getElementById("fFecha").value,
      prioridad_cliente: document.getElementById("fPrioridad").value,
      departamento_origen: document.getElementById("fDeptoOrigen").value,
      ciudad_origen: document.getElementById("fMunOrigen").value,
      departamento_destino: document.getElementById("fDeptoDestino").value,
      ciudad_destino: document.getElementById("fMunDestino").value,
      tipo_transporte: document.getElementById("fTransporte").value,
      tipo_vehiculo: document.getElementById("fVehiculo").value,
      tipo_carga: document.getElementById("fCarga").value,
      sector_cliente: document.getElementById("fSector").value,
      peso_toneladas: parseFloat(document.getElementById("fPeso").value) || 0,
      volumen_m3: parseFloat(document.getElementById("fVolumen").value) || 0,
      distancia_km: parseFloat(document.getElementById("fDistancia").value) || 0,
      tiempo_programado_horas: parseFloat(document.getElementById("fTiempoProg").value) || 0,
      disponibilidad_flota_pct: parseFloat(document.getElementById("fFlota").value) || null,
      costo_transporte_pen: parseFloat(document.getElementById("fCostoTransporte").value) || 0,
      costo_peajes_pen: parseFloat(document.getElementById("fCostoPeajes").value) || 0,
    };
  }

  async function guardar() {
    const errBox = document.getElementById("gdEmbFormError");
    errBox.style.display = "none";
    const id = document.getElementById("fId").value;
    const payload = payloadFromForm();
    try {
      if (id) {
        await RansaAPI.put(`/api/shipments/${id}`, payload);
      } else {
        await RansaAPI.post("/api/shipments", payload);
      }
      modal.hide();
      await loadTable();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.style.display = "block";
    }
  }

  async function eliminar(id, idViaje) {
    if (!confirm(`¿Eliminar el embarque ${idViaje}? Esta acción no se puede deshacer.`)) return;
    try {
      await RansaAPI.del(`/api/shipments/${id}`);
      await loadTable();
    } catch (err) {
      alert(err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    modal = new bootstrap.Modal(document.getElementById("modalEmbarque"));
    await loadOptions();
    await loadTable();

    document.getElementById("btnNuevoEmbarque").addEventListener("click", abrirCreacion);
    document.getElementById("btnGuardarEmbarque").addEventListener("click", guardar);
    document.getElementById("btnEmbAnterior").addEventListener("click", () => { if (state.page > 1) { state.page--; loadTable(); } });
    document.getElementById("btnEmbSiguiente").addEventListener("click", () => { if (state.page < state.total_pages) { state.page++; loadTable(); } });
  });
})();
