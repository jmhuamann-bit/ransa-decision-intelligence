/* Logica comun de shell: usuario en topbar, logout, toggle sidebar movil. */
document.addEventListener("DOMContentLoaded", async () => {
  const toggle = document.getElementById("gdSidebarToggle");
  const sidebar = document.getElementById("gdSidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (e) => {
      if (window.innerWidth < 992 && sidebar.classList.contains("open") &&
          !sidebar.contains(e.target) && !toggle.contains(e.target)) {
        sidebar.classList.remove("open");
      }
    });
  }

  const logoutBtn = document.getElementById("gdLogoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      try { await RansaAPI.post("/api/auth/logout"); } catch (err) { /* noop */ }
      window.location.href = "/login";
    });
  }

  try {
    const { user } = await RansaAPI.get("/api/auth/me");
    if (user) {
      const nameEl = document.getElementById("gdUserName");
      const roleEl = document.getElementById("gdUserRole");
      const avatarEl = document.getElementById("gdUserAvatar");
      if (nameEl) nameEl.textContent = user.nombre_completo;
      if (roleEl) roleEl.textContent = user.rol;
      if (avatarEl) avatarEl.textContent = gdInitials(user.nombre_completo);
      window.gdCurrentUser = user;
    }
  } catch (err) { /* no autenticado: paginas protegidas ya redirigen via Flask-Login */ }

  wireCopilot();
});

/* ---------- RANSA AI Copilot (panel deslizable global) ---------- */
function wireCopilot() {
  const panel = document.getElementById("gdCopilotPanel");
  const backdrop = document.getElementById("gdCopilotBackdrop");
  const messages = document.getElementById("gdCopilotMessages");
  const input = document.getElementById("gdCopilotInput");
  if (!panel) return;

  let greeted = false;

  function escapeHtml(t) { const d = document.createElement("div"); d.textContent = t; return d.innerHTML; }
  function fmt(t) { return escapeHtml(t).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>"); }

  function bubble(role, text) {
    const wrap = document.createElement("div");
    wrap.className = `gd-chat-msg ${role}`;
    const avatar = role === "bot"
      ? '<i class="fa-solid fa-robot"></i>'
      : (window.gdCurrentUser ? gdInitials(window.gdCurrentUser.nombre_completo) : "TÚ");
    wrap.innerHTML = `<div class="gd-chat-avatar ${role}">${avatar}</div><div class="gd-chat-bubble">${fmt(text)}</div>`;
    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
    return wrap;
  }

  async function send(text) {
    if (!text || !text.trim()) return;
    bubble("user", text);
    input.value = "";
    const typing = bubble("bot", "…");
    typing.classList.add("typing");
    try {
      const r = await RansaAPI.post("/api/chat/message", { mensaje: text });
      typing.remove();
      bubble("bot", r.respuesta);
    } catch (err) {
      typing.remove();
      bubble("bot", "Ocurrió un error: " + err.message);
    }
  }

  function open(prefill) {
    panel.classList.add("open");
    backdrop.classList.add("open");
    panel.setAttribute("aria-hidden", "false");
    if (!greeted) {
      bubble("bot", "¡Hola! Soy el RANSA AI Copilot. Puedo analizar la red, explicar riesgos, "
        + "responder what-if (ej. \"¿qué pasa si cierro el Callao?\") y recomendar acciones. ¿En qué te ayudo?");
      greeted = true;
    }
    if (prefill) { input.value = prefill; }
    setTimeout(() => input.focus(), 60);
  }
  function close() {
    panel.classList.remove("open");
    backdrop.classList.remove("open");
    panel.setAttribute("aria-hidden", "true");
  }

  document.getElementById("gdCopilotBtn")?.addEventListener("click", () => open());
  document.getElementById("gdCopilotClose")?.addEventListener("click", close);
  backdrop.addEventListener("click", close);
  document.getElementById("gdCopilotSend")?.addEventListener("click", () => send(input.value));
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") send(input.value); });
  document.querySelectorAll("#gdCopilotChips .gd-chat-chip").forEach((chip) =>
    chip.addEventListener("click", () => send(chip.textContent)));

  // API pública para que otras vistas (Torre) abran el Copilot con una pregunta contextual.
  window.gdOpenCopilot = open;
}
