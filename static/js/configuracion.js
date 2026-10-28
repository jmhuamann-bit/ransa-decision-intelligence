(function () {
  let modalUsuario;

  function switchTab(tab) {
    document.querySelectorAll(".gd-config-tab").forEach((el) => (el.style.display = "none"));
    document.getElementById(`tab-${tab}`).style.display = "block";
    document.querySelectorAll("#gdConfigTabs .nav-link").forEach((el) => el.classList.toggle("active", el.dataset.tab === tab));
  }

  async function loadUsers() {
    try {
      const { users, roles } = await RansaAPI.get("/api/admin/users");
      document.getElementById("gdUsersTotal").textContent = `${users.length} usuarios registrados`;
      document.getElementById("gdUsersBody").innerHTML = users.map((u) => `
        <tr>
          <td>${u.nombre_completo}</td>
          <td>${u.email}</td>
          <td><span class="gd-badge gris">${u.rol}</span></td>
          <td>${u.cargo || "—"}</td>
          <td>${u.activo ? '<span class="gd-badge verde">Activo</span>' : '<span class="gd-badge rojo">Inactivo</span>'}</td>
          <td><button class="gd-btn gd-btn-outline gd-btn-sm btn-toggle-user" data-id="${u.id}" data-activo="${u.activo}">${u.activo ? "Desactivar" : "Activar"}</button></td>
        </tr>`).join("");

      document.getElementById("uRol").innerHTML = roles.map((r) => `<option value="${r}">${r}</option>`).join("");

      document.querySelectorAll(".btn-toggle-user").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await RansaAPI.put(`/api/admin/users/${btn.dataset.id}`, { activo: btn.dataset.activo !== "true" });
            await loadUsers();
          } catch (err) { alert(err.message); }
        });
      });
    } catch (err) {
      document.getElementById("gdUsersBody").innerHTML = `<tr><td colspan="6"><div class="gd-empty-state"><i class="fa-solid fa-lock"></i><div>${err.message}</div></div></td></tr>`;
    }
  }

  async function loadAiSettings() {
    const data = await RansaAPI.get("/api/admin/ai-settings");
    document.getElementById("gdUmbral").textContent = `${data.umbral_alerta_critica_pct}%`;
    const modeloEl = document.getElementById("gdModeloActivo");
    if (!data.modelo_activo) {
      modeloEl.innerHTML = `<div class="gd-empty-state"><i class="fa-solid fa-brain"></i><div>Sin modelo entrenado</div></div>`;
      return;
    }
    const m = data.modelo_activo;
    modeloEl.innerHTML = `
      <div class="gd-label">Algoritmo</div><div class="mb-2">${m.algoritmo} (v${m.version})</div>
      <div class="gd-label">Métricas (conjunto de prueba)</div>
      <div>AUC ${m.metrics.auc} · Accuracy ${gdFormatPct(m.metrics.accuracy*100)} · Recall ${gdFormatPct(m.metrics.recall*100)}</div>
      <div class="gd-label mt-2">Entrenado</div><div>${gdFormatDate(m.creado_en)}</div>`;
  }

  async function loadIntegrations() {
    const { integrations } = await RansaAPI.get("/api/admin/integrations");
    document.getElementById("gdIntegracionesRow").innerHTML = integrations.map((i) => `
      <div class="col-12 col-md-6 col-xl-4">
        <div class="gd-card h-100">
          <div class="gd-card-body">
            <div class="d-flex justify-content-between align-items-start">
              <div class="gd-kpi-icon gd-bg-blue"><i class="fa-solid ${i.icono}"></i></div>
              <span class="gd-badge ${i.estado === 'Configurado' ? 'verde' : 'gris'}">${i.estado}</span>
            </div>
            <div style="font-weight:700;margin-top:10px;">${i.nombre}</div>
            <div style="font-size:12px;color:var(--gd-text-muted);margin-top:4px;">${i.descripcion}</div>
          </div>
        </div>
      </div>`).join("");
  }

  async function loadAuditLogs() {
    try {
      const { logs } = await RansaAPI.get("/api/admin/audit-logs");
      document.getElementById("gdAuditBody").innerHTML = logs.length ? logs.map((l) => `
        <tr>
          <td>${gdFormatDate(l.creado_en)}</td>
          <td>${l.usuario_email || "—"}</td>
          <td><span class="gd-badge gris">${l.accion}</span></td>
          <td>${l.entidad || "—"} ${l.entidad_id || ""}</td>
          <td style="white-space:normal;">${l.detalle || "—"}</td>
        </tr>`).join("") : `<tr><td colspan="5" class="text-center text-muted py-4">Sin registros</td></tr>`;
    } catch (err) {
      document.getElementById("gdAuditBody").innerHTML = `<tr><td colspan="5"><div class="gd-empty-state"><i class="fa-solid fa-lock"></i><div>${err.message}</div></div></td></tr>`;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    modalUsuario = new bootstrap.Modal(document.getElementById("modalUsuario"));

    document.querySelectorAll("#gdConfigTabs .nav-link").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    document.getElementById("btnNuevoUsuario").addEventListener("click", () => {
      document.getElementById("gdUserFormError").style.display = "none";
      ["uNombre", "uEmail", "uPassword", "uCargo"].forEach((id) => (document.getElementById(id).value = ""));
      modalUsuario.show();
    });

    document.getElementById("btnGuardarUsuario").addEventListener("click", async () => {
      const errBox = document.getElementById("gdUserFormError");
      try {
        await RansaAPI.post("/api/admin/users", {
          nombre_completo: document.getElementById("uNombre").value,
          email: document.getElementById("uEmail").value,
          password: document.getElementById("uPassword").value,
          rol: document.getElementById("uRol").value,
          cargo: document.getElementById("uCargo").value,
        });
        modalUsuario.hide();
        await loadUsers();
      } catch (err) {
        errBox.textContent = err.message;
        errBox.style.display = "block";
      }
    });

    await Promise.all([loadUsers(), loadAiSettings(), loadIntegrations(), loadAuditLogs()]);
  });
})();
