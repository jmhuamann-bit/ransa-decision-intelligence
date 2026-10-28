(function () {
  // ================= Cola de priorización H2 =================
  async function loadH2() {
    let data;
    try { data = await RansaAPI.get("/api/prioritization/queue?limit=15"); }
    catch (err) { return; }

    document.getElementById("h2Pesos").innerHTML = data.pesos
      .map((p) => `<span class="gd-h2-peso">${p.criterio} <b>${p.peso_pct}%</b></span>`).join("");

    document.getElementById("h2Sub").textContent =
      `${gdFormatNumber(data.candidatos, 0)} embarques con riesgo ≥ ${data.umbral_riesgo_pct}% evaluados · top ${data.items.length}`;

    const tbody = document.getElementById("h2Body");
    if (!data.items.length) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="gd-empty-state"><i class="fa-regular fa-circle-check"></i><div>Sin carga en riesgo que priorizar</div></div></td></tr>`;
      return;
    }
    tbody.innerHTML = data.items.map((i) => `
      <tr>
        <td class="gd-mono">${i.rank}</td>
        <td class="gd-mono">${i.id_viaje}</td>
        <td>${i.sector_cliente || "—"}</td>
        <td>${i.corredor}</td>
        <td>${gdFormatPct(i.riesgo_pct)}</td>
        <td><b>${i.score}</b></td>
        <td><span class="gd-badge-h2 ${i.nivel}">${i.nivel}</span></td>
      </tr>`).join("");
    gdInitTooltips(document);
  }

  // ================= Comité de crisis + cronograma 72h =================
  const COMITE = [
    { n: 1, nombre: "Comité Operativo", meta: "Jefe de Operaciones · Coordinador de Transporte. Se activa en menos de 2h. Decide desvíos y reprogramación de despachos." },
    { n: 2, nombre: "Comité Táctico", meta: "Director de Operaciones · Servicio al Cliente · Seguridad. Se activa entre 2 y 12h. Aprueba cambio de modalidad y la negociación con clientes." },
    { n: 3, nombre: "Comité Estratégico (Directivo)", meta: "Gerencia General · Finanzas · Comercial. Se activa si el impacto supera las 12h o compromete clientes estratégicos. Aprueba planes de alto costo y la comunicación institucional." },
  ];

  const TIMELINE72 = [
    { h: "H+0", txt: "La IA detecta el evento y calcula probabilidad, impacto y costo en riesgo." },
    { h: "H+2", txt: "Se activa el comité correspondiente y se notifica únicamente a los directivos." },
    { h: "H+6", txt: "Directivos aprueban el plan de contingencia recomendado (A/B/C/D)." },
    { h: "H+12", txt: "Se despliega el comunicado a las áreas, al conductor y se negocia con el cliente." },
    { h: "H+24", txt: "Ejecución del plan: desvíos, cambio de modalidad o redistribución de inventario." },
    { h: "H+48", txt: "Seguimiento: se mide OTIF recuperado y se ajusta el plan si es necesario." },
    { h: "H+72", txt: "Operación normalizada y cierre con lecciones aprendidas." },
  ];

  function renderComite() {
    document.getElementById("gdComite").innerHTML = COMITE.map((c) => `
      <div class="gd-comite-item">
        <div class="gd-comite-nivel n${c.n}">${c.n}</div>
        <div><div class="gd-comite-nombre">${c.nombre}</div><div class="gd-comite-meta">${c.meta}</div></div>
      </div>`).join("");
    document.getElementById("gdTimeline72").innerHTML = TIMELINE72.map((t) => `
      <div class="gd-tl-item"><span class="gd-tl-dot"></span><div class="gd-tl-h">${t.h}</div><div class="gd-tl-txt">${t.txt}</div></div>`).join("");
  }

  // ==================================================================
  // ============  SIMULACIÓN CONECTADA · RansaEngine  ================
  //  Un solo estado compartido (trip). Cada acción de un rol muta el
  //  estado, escribe en los teléfonos afectados y actualiza el panel.
  //  Modo interactivo (tú decides) + Auto-demo (camino recomendado).
  // ==================================================================
  const $ = (id) => document.getElementById(id);

  // ---- Catálogo de motivos que el conductor puede reportar ----
  const MOTIVOS = {
    via_cerrada: { label: "La vía está cerrada", estado: "amarillo", nivel: 2, reroute: true, suave: "Cierre temporal de vía", det: "Cierre de la Carretera Central por huaico en Matucana" },
    falla:       { label: "Falla mecánica",      estado: "amarillo", nivel: 2, reroute: true, suave: "Revisión técnica del vehículo", det: "Falla mecánica del tractocamión" },
    accidente:   { label: "Hay un accidente",    estado: "amarillo", nivel: 3, reroute: true, suave: "Incidente vial en la ruta", det: "Accidente de tránsito en la vía" },
    protesta:    { label: "Hay paro / bloqueo", estado: "amarillo", nivel: 3, reroute: true, suave: "Manifestación en vía", det: "Bloqueo por manifestación social" },
    bien:        { label: "Estoy bien",          estado: "verde",    nivel: 1, reroute: false, suave: "Sin novedad", det: "El conductor reporta normalidad" },
  };

  // ---- Carga del viaje: define la ruta recomendada ----
  const CARGA = { tipo: "Medicamentos", sector: "Salud", prioridad: "CRÍTICA" };

  // ---- Rutas alternas (motor de decisiones) ----
  function computeRoutes() {
    return [
      { id: "A", nombre: "Cañete–Lunahuaná–Yauyos (PE-24)", km: "+137 km", horas: "+3 h", costo: "S/ 950", etaNew: "6:40 pm", perfil: "más rápida" },
      { id: "B", nombre: "Canta–Huayllay–La Oroya (PE-20A)", km: "+165 km", horas: "+4 h", costo: "S/ 690", etaNew: "7:40 pm", perfil: "más económica" },
      { id: "C", nombre: "Esperar reapertura (Provías)",  km: "+0 km",  horas: "+6 h", costo: "S/ 0",       etaNew: "9:15 pm", perfil: "sin desvío" },
    ];
  }
  function recommendRoute(carga) {
    if (carga.prioridad === "CRÍTICA" || carga.prioridad === "ALTA")
      return { id: "A", razon: `Carga de ${carga.sector} con prioridad ${carga.prioridad} → se elige la ruta más rápida para proteger el OTIF.` };
    if (carga.prioridad === "MEDIA")
      return { id: "B", razon: "Prioridad media → se optimiza el costo sobre el tiempo." };
    return { id: "C", razon: "Prioridad baja → conviene esperar la reapertura y evitar sobrecosto." };
  }
  function motivoSuave(key) { return (MOTIVOS[key] && MOTIVOS[key].suave) || "Novedad en ruta"; }

  // ---- KPIs del panel ----
  const WA_KPI_DEFS = [["crisis", "Nivel de crisis"], ["safe", "Conductor"], ["otifSalud", "OTIF Salud"],
    ["mode", "Transporte"], ["chat", "Consultas chatbot"], ["cost", "Sobrecosto"]];
  function waDefaultKpi() {
    return { crisis: { v: "En espera", c: "" }, safe: { v: "En ruta", c: "" }, otifSalud: { v: "—", c: "" },
      mode: { v: "Terrestre", c: "" }, chat: { v: "0", c: "" }, cost: { v: "—", c: "" } };
  }

  // ---- Runtime + estado del viaje ----
  const sim = { playing: false, auto: false, speed: 1, timers: [], remaining: 72 * 3600, clockAnim: null, autoTick: null };
  let trip = null;

  function freshTrip() {
    return {
      fase: "idle", estado: "verde", nivel: 1, carga: CARGA, motivo: null,
      detenidoMin: 18, vehiculo: { id: "RNS-T457", placa: "C7G-482", gps: "-11.8436, -76.3850", vel: "0 km/h" },
      rutas: [], recomendada: null, recomendadaRazon: "", rutaPropuesta: null, rutaConfirmada: null, rutaRechazada: null,
      esperaCliente: false, codigo: null, estacionPolicia: null, bloqueoConductor: false,
      kpi: waDefaultKpi(), bitacora: [], progreso: 0, faseTxt: "En espera de disrupción", pending: null,
    };
  }

  // ---- Utilidades de tiempo / formato ----
  function T(fn, ms) { const id = setTimeout(fn, Math.max(120, ms / sim.speed)); sim.timers.push(id); return id; }
  function clearAll() { sim.timers.forEach(clearTimeout); sim.timers = []; clearTimeout(sim.autoTick); clearInterval(sim.clockAnim); }
  function parseClock(s) { const p = s.split(":").map(Number); return p[0] * 3600 + p[1] * 60 + p[2]; }
  function fmtClock(sec) {
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    const z = (n) => String(n).padStart(2, "0");
    return `${z(h)}:${z(m)}:${z(s)}`;
  }
  function waNow() { return new Date().toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", hour12: false }); }
  function waBold(t) { return String(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); }
  function updateClock() {
    const el = $("wa-clock"); if (!el) return;
    el.textContent = fmtClock(sim.remaining);
    el.className = "wa-clock" + (trip && trip.estado === "rojo" ? " danger" : (sim.remaining > 0 && sim.remaining < 24 * 3600 ? " warn" : ""));
  }
  function animClock(to) {
    clearInterval(sim.clockAnim);
    let cur = sim.remaining; const steps = 22; const delta = (to - cur) / steps; let i = 0;
    sim.clockAnim = setInterval(() => {
      i++; cur += delta;
      if (i >= steps) { cur = to; clearInterval(sim.clockAnim); }
      sim.remaining = cur; updateClock();
    }, 45);
  }

  // ---- Bitácora ----
  function log(txt, level) { if (!trip) return; trip.bitacora.push({ t: waNow(), txt, level: level || "" }); }
  function renderLog() {
    const el = $("wa-log"); if (!el) return;
    if (!trip || !trip.bitacora.length) { el.innerHTML = `<div class="wa-log-empty">Sin eventos aún · pulsa Iniciar</div>`; return; }
    el.innerHTML = trip.bitacora.slice(-8).map((e) =>
      `<div class="wa-log-item ${e.level}"><span class="wa-log-t">${e.t}</span><span class="wa-log-x">${e.txt}</span></div>`).join("");
    el.scrollTop = el.scrollHeight;
  }

  // ---- KPIs ----
  function kset(obj) { if (!trip) return; Object.entries(obj).forEach(([k, v]) => { trip.kpi[k] = Object.assign({}, trip.kpi[k], v); }); }
  function renderKpis() {
    const el = $("wa-kpis"); if (!el) return;
    const kpi = trip ? trip.kpi : waDefaultKpi();
    el.innerHTML = WA_KPI_DEFS.map(([k, l]) => {
      const it = kpi[k] || { v: "—", c: "" };
      return `<div class="wa-kpi"><div class="wk-v ${it.c || ""}">${it.v}</div><div class="wk-l">${l}</div></div>`;
    }).join("");
  }

  // ---- Panel / mini-dashboard (se re-renderiza desde el estado) ----
  const BANNER = {
    verde: ["fa-circle-check", "Operación normal"],
    amarillo: ["fa-triangle-exclamation", "Contingencia en gestión"],
    rojo: ["fa-triangle-exclamation", "Emergencia de seguridad"],
  };
  function renderDashboard() {
    if (!trip) return;
    const est = trip.estado;
    const b = $("wa-banner");
    if (b) {
      b.className = "wa-banner " + est;
      const [ic, tx] = BANNER[est] || BANNER.verde;
      b.innerHTML = `<i class="fa-solid ${ic}"></i><div><b>${tx}</b><small>Nivel ${trip.nivel} · ${trip.faseTxt}</small></div>`;
    }
    const ph = $("wa-phase"); if (ph) ph.textContent = trip.faseTxt;
    const bar = $("wa-bar"); if (bar) bar.style.width = (trip.progreso || 0) + "%";
    const mk = $("wa-marker"); if (mk) mk.className = "wa-marker " + est;
    const pol = $("wa-police"); if (pol) pol.style.display = trip.estacionPolicia ? "flex" : "none";
    updateClock();
    renderKpis();
    renderLog();
  }
  function pulseFlow(seq) {
    (seq || []).forEach((n, i) => setTimeout(() => {
      const el = document.querySelector('.wa-node[data-node="' + n + '"]'); if (!el) return;
      el.classList.add("pulse"); setTimeout(() => el.classList.remove("pulse"), 700);
    }, i * 220));
  }

  // ---- Render de mensajes en cualquier teléfono ----
  function bubbleHTML(s) {
    const kindCls = (s.kind && s.kind !== "msg") ? " " + s.kind : "";
    const atag = s.atag ? `<span class="wa-atag">${s.atag}</span><br>` : "";
    const sender = (!s.out && s.sender) ? `<div class="wa-sender" style="color:${s.color || "#8696a0"}">${s.sender}</div>` : "";
    const check = s.out ? ' <span class="wa-check">✓✓</span>' : "";
    return `<div class="wa-bubble${kindCls}">${sender}<div class="wa-text">${atag}${waBold(s.text)}</div><div class="wa-meta">${waNow()}${check}</div></div>`;
  }
  function showTyping(bodyId, sender, color) {
    removeTyping(bodyId);
    const d = document.createElement("div");
    d.className = "wa-typing"; d.id = bodyId + "-typing";
    d.innerHTML = `<span class="wa-sender" style="color:${color || "#8696a0"};margin:0">${sender || ""}</span> <i class="dot"></i><i class="dot"></i><i class="dot"></i>`;
    const body = $(bodyId); if (!body) return;
    body.appendChild(d); body.scrollTop = body.scrollHeight;
  }
  function removeTyping(bodyId) { const t = $(bodyId + "-typing"); if (t) t.remove(); }

  // Agrega un mensaje. Los del bot muestran "escribiendo…" antes; los salientes van directos.
  function say(bodyId, s, done) {
    const body = $(bodyId);
    if (!body) { if (done) done(); return; }
    const append = () => {
      const wrap = document.createElement("div");
      wrap.className = "wa-msg " + (s.out ? "out" : "in");
      wrap.innerHTML = bubbleHTML(s);
      body.appendChild(wrap); body.scrollTop = body.scrollHeight;
      if (done) done();
    };
    if (s.out) { append(); return; }
    showTyping(bodyId, s.sender, s.color);
    T(() => { removeTyping(bodyId); append(); }, s.typ != null ? s.typ : 700);
  }
  // Reproduce una lista de mensajes en el mismo teléfono, uno tras otro.
  function sayList(bodyId, msgs, done, i) {
    i = i || 0;
    if (!sim.playing || i >= msgs.length) { if (done) done(); return; }
    say(bodyId, msgs[i], () => T(() => sayList(bodyId, msgs, done, i + 1), 240));
  }

  // ---- Botones de decisión (interactivos) ----
  function quickId(surface) { return surface === "operador" ? "wa-quick" : "wa-quick-" + surface; }
  function bodyId(surface) { return surface === "operador" ? "wa-body" : "wa-body-" + surface; }
  function setPending(surface, options) {
    if (!trip) return;
    trip.pending = { surface, options };
    const el = $(quickId(surface)); if (!el) return;
    el.innerHTML = options.map((o, i) => `<button class="wa-qbtn ${o.rec ? "rec" : ""}" data-i="${i}">${o.label}</button>`).join("");
    el.querySelectorAll(".wa-qbtn").forEach((btn) => btn.addEventListener("click", () => {
      if (!trip || !trip.pending) return;
      const opt = options[+btn.dataset.i];
      el.innerHTML = ""; trip.pending = null;
      if (opt.echo !== false) say(bodyId(surface), { out: true, text: opt.echoText || opt.label });
      T(() => dispatch(opt.action, opt), 320);
    }));
  }
  function clearPending() {
    if (trip) trip.pending = null;
    ["wa-quick", "wa-quick-conductor", "wa-quick-cliente"].forEach((id) => { const e = $(id); if (e) e.innerHTML = ""; });
  }

  // ---- Fragmentos HTML enriquecidos (dentro de burbujas) ----
  function routesTableHTML(t) {
    return `<div class="wa-routes">` + t.rutas.map((r) => {
      const rec = r.id === t.recomendada;
      return `<div class="wa-route ${rec ? "rec" : ""}">
        <div class="wa-route-id">${r.id}</div>
        <div class="wa-route-main"><b>${r.nombre}</b><small>${r.km} · ${r.horas} · ${r.costo}</small></div>
        ${rec ? '<span class="wa-route-tag">RECOMENDADA</span>' : ""}
      </div>`;
    }).join("") + `</div><div class="wa-route-reason"><i class="fa-solid fa-lightbulb"></i> ${t.recomendadaRazon}</div>`;
  }
  function emgCardHTML(t) {
    return `<div class="wa-emg">
      <div class="wa-emg-row"><span>Vehículo</span><b>${t.vehiculo.id} · ${t.vehiculo.placa}</b></div>
      <div class="wa-emg-row"><span>GPS en vivo</span><b>${t.vehiculo.gps}</b></div>
      <div class="wa-emg-row"><span>Velocidad</span><b>${t.vehiculo.vel}</b></div>
      <div class="wa-emg-row"><span>Hora</span><b>${waNow()}</b></div>
      <div class="wa-emg-row alert"><span>Apoyo cercano</span><b>${t.estacionPolicia || "—"}</b></div>
    </div>`;
  }
  function proposalHTML(r, t) {
    return `<div class="wa-emg">
      <div class="wa-emg-row"><span>Nueva ruta</span><b>${r.nombre}</b></div>
      <div class="wa-emg-row"><span>Tiempo adicional</span><b>${r.horas}</b></div>
      <div class="wa-emg-row"><span>Nuevo ETA</span><b>${r.etaNew}</b></div>
      <div class="wa-emg-row"><span>Costo adicional</span><b>${r.costo}</b></div>
    </div><div class="wa-route-reason"><i class="fa-solid fa-shield-halved"></i> ${t.recomendadaRazon}</div>`;
  }
  function lockConductor() {
    const q = $("wa-quick-conductor");
    if (q) q.innerHTML = `<div class="wa-blocked"><i class="fa-solid fa-lock"></i> Interacción bloqueada por seguridad</div>`;
  }

  // ==================  ACCIONES DEL MOTOR  ==================

  // Paso 1 — Auto-detección
  function triggerDetection() {
    if (!trip || trip.fase !== "idle") return;
    trip.fase = "detectado"; trip.estado = "amarillo"; trip.nivel = 2; trip.vehiculo.vel = "0 km/h";
    trip.faseTxt = "H0 · Anomalía detectada"; trip.progreso = 5; sim.remaining = 72 * 3600;
    kset({ crisis: { v: "Evaluando", c: "warn" } });
    log(`Anomalía: ${trip.vehiculo.id} detenido ${trip.detenidoMin} min en Matucana`, "warn");
    renderDashboard(); pulseFlow(["fuentes", "rde", "wa"]);

    say("wa-body", { kind: "alert", atag: "🚨 DETECCIÓN AUTOMÁTICA", sender: "🤖 RANSA · Torre", color: "#34B7F1",
      text: `Vehículo **${trip.vehiculo.id}** detenido **${trip.detenidoMin} min** en un punto atípico.\n📍 Matucana · Carretera Central Km 75 (Callao–Huancayo).\nCarga: **${trip.carga.tipo}** (${trip.carga.sector} · ${trip.carga.prioridad}).` });
    say("wa-body-cliente", { kind: "warn", sender: "🤖 RANSA Logística", color: "#9B5DE5",
      text: "Estimado cliente, su carga presenta una **novedad en carretera**. La estamos gestionando; no requiere ninguna acción por ahora." });
    sayList("wa-body-conductor", [
      { kind: "alert", sender: "🤖 RANSA Asistente", color: "#34B7F1",
        text: `🚨 Detectamos que tu vehículo lleva detenido **${trip.detenidoMin} minutos**.\n¿Qué está ocurriendo?` },
    ], () => setPending("conductor", [
      { label: "La vía está cerrada", action: "motivo", key: "via_cerrada", rec: true },
      { label: "Falla mecánica", action: "motivo", key: "falla" },
      { label: "Hay un accidente", action: "motivo", key: "accidente" },
      { label: "Hay paro / bloqueo", action: "motivo", key: "protesta" },
      { label: "Estoy bien", action: "motivo", key: "bien" },
    ]));
  }

  // Paso 2 — El conductor reporta el motivo → el motor calcula rutas y recomienda
  function conductorInitial(key) {
    const m = MOTIVOS[key] || MOTIVOS.via_cerrada;
    trip.motivo = key; trip.estado = m.estado; trip.nivel = m.nivel;
    log(`Conductor reporta: ${m.label}`, m.estado === "verde" ? "ok" : "warn");

    if (!m.reroute) { // "Estoy bien" → falsa alarma
      trip.fase = "resuelta"; trip.estado = "verde"; trip.faseTxt = "Falsa alarma · operación normal"; trip.progreso = 100;
      kset({ crisis: { v: "Sin evento", c: "ok" } });
      renderDashboard();
      say("wa-body-conductor", { kind: "success", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: "¡Gracias! Me alegra que todo esté bien. Continúa con precaución. 🚚" });
      say("wa-body", { kind: "success", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "✅ El conductor reporta normalidad. Falsa alarma; se cierra el evento." });
      say("wa-body-cliente", { kind: "success", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "Su carga continúa con normalidad. ETA sin cambios: **4:00 pm**. Gracias por su confianza." });
      finish(); return;
    }

    trip.rutas = computeRoutes();
    const rec = recommendRoute(trip.carga);
    trip.recomendada = rec.id; trip.recomendadaRazon = rec.razon;
    trip.fase = "codigo"; trip.faseTxt = "H0 · Motivo confirmado · rutas calculadas"; trip.progreso = 12;
    kset({ crisis: { v: "Nivel " + trip.nivel, c: trip.nivel >= 3 ? "danger" : "warn" } });
    log(`Motor evalúa 3 rutas · recomienda Ruta ${rec.id}`, "ok");
    renderDashboard(); pulseFlow(["rde", "wa", "comite"]);

    say("wa-body", { kind: "msg", sender: "🤖 RANSA · Motor de decisiones", color: "#34B7F1",
      text: `El conductor reporta **${m.label}**. Evalué 3 rutas alternas de menor impacto:` + routesTableHTML(trip) });
    sayList("wa-body-conductor", [
      { kind: "msg", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: "Entendido. El equipo ya está evaluando rutas alternas." },
      { kind: "warn", sender: "🤖 RANSA Asistente", color: "#34B7F1",
        text: "🔐 **Protocolo de seguridad.** Antes de continuar, confírmame con el código verbal:\n\n🍎 **Manzana** = todo bajo control\n🍐 **Pera** = estoy bajo amenaza" },
    ], () => setPending("conductor", [
      { label: "🍎 Manzana", action: "codigo", key: "manzana", rec: true },
      { label: "🍐 Pera", action: "codigo", key: "pera" },
    ]));
  }

  // Paso 3 — Código de seguridad
  function conductorCodigo(code) {
    trip.codigo = code;
    if (code === "manzana") {
      trip.fase = "contingencia"; trip.faseTxt = "Ruta calculada · esperando al operador"; trip.progreso = 22;
      kset({ safe: { v: "Seguro ✅", c: "ok" } });
      log("Código Manzana · conductor seguro", "ok");
      renderDashboard();
      say("wa-body-conductor", { kind: "success", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: "✅ Gracias. Mantente en un lugar seguro; te enviaré la ruta aprobada en breve." });
      say("wa-body", { kind: "success", atag: "🟢 CONDUCTOR SEGURO", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "El conductor confirmó **Manzana** (seguro). Ya puedes proponer una ruta al cliente." },
        () => setPending("operador", [
          { label: `📤 Proponer Ruta ${trip.recomendada} al cliente`, action: "propose", key: trip.recomendada, rec: true, echo: false },
        ].concat(trip.rutas.filter((r) => r.id !== trip.recomendada).map((r) => ({ label: `Proponer Ruta ${r.id} (${r.perfil})`, action: "propose", key: r.id, echo: false })))));
    } else {
      trip.fase = "emergencia"; trip.estado = "rojo"; trip.nivel = 4;
      trip.estacionPolicia = "Comisaría PNP de Matucana · 2.4 km"; trip.bloqueoConductor = true;
      trip.faseTxt = "🚨 EMERGENCIA · protocolo de seguridad"; trip.progreso = 30;
      kset({ crisis: { v: "EMERGENCIA", c: "danger" }, safe: { v: "⚠ Riesgo", c: "danger" } });
      log("Código PERA · amenaza de seguridad · nivel 4", "danger");
      renderDashboard(); pulseFlow(["wa", "comite"]);

      say("wa-body-conductor", { kind: "alert", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: "Entendido. Mantén la calma. **No respondas más mensajes.** Estamos activando el protocolo. 🔒" });
      lockConductor();
      say("wa-body", { kind: "alert", atag: "🔴 EMERGENCIA DE SEGURIDAD", sender: "🤖 RANSA · Torre", color: "#34B7F1",
        text: "El conductor activó **Pera**. Protocolo de seguridad en curso:" + emgCardHTML(trip) },
        () => setPending("operador", [{ label: "🚔 Activar protocolo policial", action: "protocol", rec: true, echo: false }]));
      say("wa-body-cliente", { kind: "warn", sender: "🤖 RANSA Logística", color: "#9B5DE5",
        text: "Estamos gestionando una **novedad operativa**. Su envío está **priorizado y protegido**. Le informaremos apenas se restablezca el tránsito." });
    }
  }

  // Paso 3b — Activar protocolo policial (rama Pera)
  function activateProtocol() {
    trip.faseTxt = "Protocolo policial activado"; trip.progreso = 55;
    log("Protocolo activado · PNP notificada · convoy en camino", "danger");
    renderDashboard();
    sayList("wa-body", [
      { kind: "msg", sender: "Coord. Seguridad", color: "#FEE440", text: `🚔 Notificando a la **${trip.estacionPolicia}**. Comparto GPS en vivo.` },
      { kind: "msg", sender: "Coord. Seguridad", color: "#FEE440", text: "Patrulla en camino · ETA 8 min. Aseguradora notificada." },
      { kind: "success", atag: "🟢 CONTROLADO", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "✅ Situación controlada por la autoridad. Conductor a salvo y carga resguardada en zona segura." },
    ], () => {
      trip.estado = "verde"; trip.nivel = 1; trip.estacionPolicia = null; trip.fase = "resuelta"; trip.faseTxt = "Emergencia contenida"; trip.progreso = 100;
      kset({ crisis: { v: "Contenida", c: "ok" }, safe: { v: "A salvo ✅", c: "ok" } });
      renderDashboard();
      say("wa-body-cliente", { kind: "success", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "La novedad fue resuelta. Su envío sigue **protegido y priorizado**; le confirmaremos la nueva hora de entrega en breve." });
      log("Emergencia contenida · cierre del evento", "ok");
      finish();
    });
  }

  // Paso 4 — El operador propone una ruta al cliente
  function operatorPropose(routeId) {
    const r = trip.rutas.find((x) => x.id === routeId) || trip.rutas[0];
    trip.rutaPropuesta = routeId; trip.esperaCliente = true; trip.fase = "propuesta";
    trip.faseTxt = `Ruta ${routeId} propuesta · esperando cliente`; trip.progreso = 40;
    log(`Operador propone Ruta ${routeId} al cliente`, "warn");
    renderDashboard();
    say("wa-body", { out: true, text: `Propongo la Ruta ${routeId} al cliente.` });
    say("wa-body", { kind: "msg", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "Propuesta enviada. Esperando la confirmación del cliente…" });
    const suave = motivoSuave(trip.motivo);
    say("wa-body-cliente", { kind: "warn", atag: "🔁 PROPUESTA DE RUTA", sender: "🤖 RANSA Logística", color: "#9B5DE5",
      text: `Para proteger su embarque ante **${suave}**, recomendamos un cambio de ruta:` + proposalHTML(r, trip) },
      () => setPending("cliente", [
        { label: "✅ Confirmar cambio", action: "confirm", rec: true },
        { label: "❌ Rechazar", action: "reject" },
      ]));
  }

  // Paso 5 — El cliente confirma
  function clientConfirm() {
    trip.rutaConfirmada = trip.rutaPropuesta; trip.esperaCliente = false; trip.fase = "confirmada";
    trip.faseTxt = `Cliente confirmó Ruta ${trip.rutaConfirmada} · desvío en ejecución`; trip.progreso = 60;
    kset({ mode: { v: "Desvío activo", c: "ok" }, cost: { v: "Autorizado", c: "warn" } });
    log(`Cliente confirmó Ruta ${trip.rutaConfirmada}`, "ok");
    renderDashboard();
    say("wa-body-cliente", { kind: "success", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "✅ Cambio confirmado. Costo adicional autorizado según acuerdo comercial. Le mantendremos informado." });
    say("wa-body", { kind: "success", atag: "✅ CLIENTE CONFIRMÓ", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: `El cliente aprobó la Ruta ${trip.rutaConfirmada}. Desvío en ejecución; notifico al conductor.` });
    say("wa-body-conductor", { kind: "success", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: `📍 **Ruta ${trip.rutaConfirmada} aprobada.** Sigue tu GPS actualizado. ¡Buen viaje y conduce con precaución!` });
    resolveTimeline();
  }

  // Paso 5 — El cliente rechaza → el operador reevalúa
  function clientReject() {
    trip.rutaRechazada = trip.rutaPropuesta; trip.rutaPropuesta = null; trip.esperaCliente = false; trip.fase = "codigo";
    trip.faseTxt = "Cliente rechazó · el operador reevalúa"; trip.progreso = 25;
    log(`Cliente rechazó Ruta ${trip.rutaRechazada}`, "warn");
    renderDashboard();
    say("wa-body-cliente", { kind: "msg", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "Entendido. Buscaremos una alternativa y le propondremos otra opción en breve." });
    say("wa-body", { kind: "warn", atag: "❌ CLIENTE RECHAZÓ", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: `El cliente rechazó la Ruta ${trip.rutaRechazada}. Propón otra ruta o espera la reapertura.` },
      () => {
        const alt = trip.rutas.filter((r) => r.id !== trip.rutaRechazada);
        setPending("operador", alt.map((r, i) => ({ label: `Proponer Ruta ${r.id} (${r.perfil})`, action: "propose", key: r.id, rec: i === 0, echo: false }))
          .concat([{ label: "⏳ Esperar reapertura", action: "esperar", echo: false }]));
      });
  }

  // El operador decide esperar la reapertura
  function operatorWait() {
    trip.fase = "resuelta"; trip.faseTxt = "Se espera la reapertura de la vía"; trip.progreso = 100;
    kset({ mode: { v: "En espera", c: "warn" } });
    log("Operador decide esperar la reapertura", "warn");
    renderDashboard();
    say("wa-body", { kind: "msg", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "Mantendremos la carga en zona segura hasta la reapertura del corredor. Monitoreo activo." });
    say("wa-body-cliente", { kind: "msg", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "Su carga permanece segura en espera de la reapertura de la vía. Le informaremos la nueva ETA." });
    finish();
  }

  // Cronograma de resolución H12 → H72 (rama confirmada)
  function resolveTimeline() {
    const steps = [
      { d: 1500, phase: "H12 · Ejecución del desvío", prog: 72, clock: "60:00:00", s: { kind: "msg", atag: "📊 H12", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "8/12 vehículos ya van por la ruta aprobada. El chatbot resolvió **47 consultas** de clientes." }, kpi: { chat: { v: "47 auto", c: "ok" } } },
      { d: 1600, phase: "H24 · Contención", prog: 82, clock: "48:00:00", s: { kind: "msg", atag: "📊 H24", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "Retail redirigido a parqueaderos seguros. Sobrecosto bajo control del Comité." }, kpi: { cost: { v: "+38%", c: "warn" } } },
      { d: 1500, phase: "H48 · Gestión aduanera", prog: 91, clock: "24:00:00", s: { kind: "success", atag: "⏳ H48", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "Ampliación de plazo en el depósito temporal del Callao aprobada (SUNAT). Sin sobrecosto de almacenaje." } },
      { d: 1500, phase: "H72 · Corredor reabierto", prog: 100, clock: "00:00:00", estado: "verde", nivel: 1, s: { kind: "success", atag: "🟢 H72 · RESUELTO", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "**Carretera Central reabierta por Provías.** Contingencia resuelta en 72h con **OTIF Salud 100%**." }, kpi: { crisis: { v: "Resuelta", c: "ok" }, otifSalud: { v: "100%", c: "ok" } } },
    ];
    let i = 0;
    const run = () => {
      if (!sim.playing) return;
      if (i >= steps.length) {
        say("wa-body-cliente", { kind: "success", atag: "📦 ENTREGA", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "✅ **Entrega completada.** Su carga llegó en buen estado. Gracias por confiar en RANSA." });
        finish(); return;
      }
      const st = steps[i++];
      T(() => {
        trip.faseTxt = st.phase; trip.progreso = st.prog; if (st.clock) animClock(parseClock(st.clock));
        if (st.estado) trip.estado = st.estado; if (st.nivel != null) trip.nivel = st.nivel;
        if (st.kpi) kset(st.kpi);
        log(st.phase, "ok"); renderDashboard();
        say("wa-body", st.s, () => run());
      }, st.d);
    };
    run();
  }

  function finish() {
    sim.playing = false; sim.auto = false; clearTimeout(sim.autoTick);
    const sub = $("wa-hsub"); if (sub) sub.textContent = "bot activo · simulación finalizada";
    setBtnLabel("wa-start", "Reiniciar");
    setBtnLabel("wa-pause", "Pausar");
    if (trip) log("Simulación finalizada", "ok"), renderLog();
  }

  // ==================  DESPACHADOR  ==================
  function dispatch(action, opt) {
    if (!trip) return;
    switch (action) {
      case "detect": triggerDetection(); break;
      case "motivo": conductorInitial(opt.key); break;
      case "codigo": conductorCodigo(opt.key); break;
      case "propose": operatorPropose(opt.key); break;
      case "protocol": activateProtocol(); break;
      case "confirm": clientConfirm(); break;
      case "reject": clientReject(); break;
      case "esperar": operatorWait(); break;
      default: break;
    }
  }

  // ==================  AUTO-DEMO  ==================
  // Reproduce solo el camino recomendado: cuando hay una decisión pendiente,
  // pulsa la opción marcada como recomendada.
  function scheduleAuto() {
    clearTimeout(sim.autoTick);
    const tick = () => {
      if (!sim.playing || !sim.auto) return;
      if (trip && trip.pending) {
        const opts = trip.pending.options;
        const pick = opts.find((o) => o.rec) || opts[0];
        const el = $(quickId(trip.pending.surface));
        if (el) { const btns = el.querySelectorAll(".wa-qbtn"); const idx = opts.indexOf(pick); if (btns[idx]) btns[idx].click(); }
      }
      sim.autoTick = setTimeout(tick, Math.max(650, 2300 / sim.speed));
    };
    sim.autoTick = setTimeout(tick, Math.max(650, 2600 / sim.speed));
  }

  // ==================  CONTROLES  ==================
  function clearBody(id, hint) {
    const el = $(id); if (!el) return;
    el.innerHTML =
      '<div class="wa-sys wa-day">HOY</div>' +
      '<div class="wa-sys wa-encrypt">🔒 Mensajes cifrados</div>' +
      (hint ? `<div class="wa-hint">${hint}</div>` : "");
  }
  function setBtnLabel(id, txt) { const b = $(id); if (b) { const sp = b.querySelector("span"); if (sp) sp.textContent = txt; else b.textContent = txt; } }

  function start(auto) {
    clearAll();
    trip = freshTrip();
    sim.playing = true; sim.auto = !!auto; sim.remaining = 72 * 3600;

    clearBody("wa-body", "Sala de Crisis · RANSA coordina la contingencia de extremo a extremo.");
    clearBody("wa-body-conductor", "Flujo conductor: detección → motivo → código de seguridad.");
    clearBody("wa-body-cliente", "Flujo cliente: notificación → propuesta de ruta → confirmar / rechazar.");
    clearPending();

    renderDashboard();
    const sub = $("wa-hsub"); if (sub) sub.textContent = auto ? "bot activo · auto-demo" : "bot activo · en vivo";
    setBtnLabel("wa-start", auto ? "En vivo…" : "En vivo…");
    setBtnLabel("wa-pause", "Pausar");
    log("Simulación iniciada · monitoreo de 12 vehículos", "ok");

    say("wa-body", { kind: "msg", sender: "🤖 RANSA · Torre", color: "#34B7F1", text: "Sala de Crisis conectada. Monitoreando **12 vehículos** en el corredor Callao–Huancayo (Carretera Central)." });
    say("wa-body-conductor", { kind: "msg", sender: "🤖 RANSA Asistente", color: "#34B7F1", text: `Hola, conductor de **${trip.vehiculo.id}**. Estoy acompañando tu viaje. Buen camino. 🚚` });
    say("wa-body-cliente", { kind: "msg", sender: "🤖 RANSA Logística", color: "#9B5DE5", text: "Su embarque de **medicamentos** está en tránsito. ETA **4:00 pm**. Le avisaremos ante cualquier novedad." });

    T(() => { if (sim.playing && trip.fase === "idle") triggerDetection(); }, 3500);
    if (auto) scheduleAuto();
  }

  function togglePause() {
    if (!trip || trip.fase === "resuelta") return;
    sim.playing = !sim.playing;
    setBtnLabel("wa-pause", sim.playing ? "Pausar" : "Reanudar");
    if (sim.playing) { if (sim.auto) scheduleAuto(); }
    else { sim.timers.forEach(clearTimeout); sim.timers = []; clearTimeout(sim.autoTick); }
  }

  function wireWa() {
    trip = null; sim.remaining = 72 * 3600;
    renderKpis(); updateClock(); renderLog();

    const bStart = $("wa-start"); if (bStart) bStart.addEventListener("click", () => start(false));
    const bAuto = $("wa-auto"); if (bAuto) bAuto.addEventListener("click", () => start(true));
    const bPause = $("wa-pause"); if (bPause) bPause.addEventListener("click", togglePause);
    const bRestart = $("wa-restart"); if (bRestart) bRestart.addEventListener("click", () => start(sim.auto));
    document.querySelectorAll(".wa-speed .spd").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".wa-speed .spd").forEach((x) => x.classList.remove("active"));
      b.classList.add("active"); sim.speed = +b.dataset.spd;
    }));
  }

  document.addEventListener("DOMContentLoaded", () => {
    renderComite();
    wireWa();
    loadH2();
  });
})();
