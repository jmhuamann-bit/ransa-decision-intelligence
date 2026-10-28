(function () {
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function formatBubble(text) {
    return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  }

  function addMessage(role, text) {
    const container = document.getElementById("gdChatMessages");
    const wrap = document.createElement("div");
    wrap.className = `gd-chat-msg ${role}`;
    wrap.innerHTML = `
      <div class="gd-chat-avatar ${role}">${role === "bot" ? '<i class="fa-solid fa-robot"></i>' : (window.gdCurrentUser ? gdInitials(window.gdCurrentUser.nombre_completo) : "TU")}</div>
      <div class="gd-chat-bubble">${formatBubble(text)}</div>
    `;
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    return wrap;
  }

  function addTyping() {
    const container = document.getElementById("gdChatMessages");
    const wrap = document.createElement("div");
    wrap.className = "gd-chat-msg bot";
    wrap.id = "gdChatTyping";
    wrap.innerHTML = `
      <div class="gd-chat-avatar bot"><i class="fa-solid fa-robot"></i></div>
      <div class="gd-chat-bubble"><i class="fa-solid fa-ellipsis fa-fade"></i></div>
    `;
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
  }

  function removeTyping() {
    const el = document.getElementById("gdChatTyping");
    if (el) el.remove();
  }

  async function sendMessage(text) {
    if (!text.trim()) return;
    addMessage("user", text);
    document.getElementById("gdChatInput").value = "";
    addTyping();
    try {
      const result = await RansaAPI.post("/api/chat/message", { mensaje: text });
      removeTyping();
      addMessage("bot", result.respuesta);
    } catch (err) {
      removeTyping();
      addMessage("bot", "Ocurrió un error al procesar tu pregunta: " + err.message);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    addMessage("bot", "¡Hola! Soy el copiloto de RANSA. Puedo ayudarte con OTIF, Lead Time, contingencias, "
      + "predicciones de riesgo, clientes o el estado de un embarque específico. ¿En qué te ayudo?");

    document.getElementById("gdChatSend").addEventListener("click", () => sendMessage(document.getElementById("gdChatInput").value));
    document.getElementById("gdChatInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMessage(document.getElementById("gdChatInput").value);
    });
    document.querySelectorAll(".gd-chat-chip").forEach((chip) => {
      chip.addEventListener("click", () => sendMessage(chip.textContent));
    });
  });
})();
