/* ¿De dónde se extrae la data? — escucha simulada de fuentes y su efecto en la probabilidad de contingencia. */
(function () {
  const POLL_MS = 20000;
  const $ = (id) => document.getElementById(id);
  const esc = (t) => { const d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; };
  const pct = (v) => `${gdFormatNumber(v, 1)} %`;
  const pp = (v) => gdFormatNumber(v, 1);
  const miles = (v) => gdFormatNumber(Math.round(v), 0);
  const APORTA = {
    oficial: "Confirma el evento: avisos SENAMHI, reportes INDECI/COEN, estado de vías de Provías, DHN",
    policia: "Confirma en campo: partes de la PNP y Policía de Carreteras",
    medios: "Difusión y contexto: TV, radio y diarios regionales",
    facebook: "Alertas tempranas de grupos de transportistas y vecinos",
    instagram: "Reels e historias de páginas de noticias locales",
    tiktok: "Videos en el lugar: lo primero que aparece, pero con más ruido",
  };

  let data = null, FU = {}, horizonte = "", fuente = "";
  const expandidos = new Set();
  const vistos = new Map();
  const contadores = {};

  // ------------------------------------------------------------------ fuentes
  function renderFuentes() {
    $("fxFuentes").innerHTML = data.fuentes.map((f) => `
      <button class="fx-src ${fuente === f.id ? "active" : ""}" data-src="${f.id}" style="--c:${f.color}" title="Filtrar el sustento por ${esc(f.nombre)}">
        <span class="fx-src-top"><span class="fx-src-ico"><i class="${f.icon}"></i></span><span class="fx-src-live"><span></span>En línea</span></span>
        <b>${esc(f.nombre)}</b><small>${esc(f.detalle)}</small>
        <span class="fx-src-num" data-anal="${f.id}">${miles(contadores[f.id].v)}</span><small>analizadas hoy</small>
        <span class="fx-src-foot"><span>${miles(f.relevantes_12h)} relevantes · 12 h</span><span>peso ${f.peso.toFixed(2)}</span></span>
      </button>`).join("");
  }

  function totales() {
    const anal = Object.values(contadores).reduce((s, c) => s + c.v, 0);
    const rel = data.fuentes.reduce((s, f) => s + f.relevantes_12h, 0);
    const ventana = data.fuentes.reduce((s, f) => s + f.ritmo_min * 60 * data.metodo.ventana_h, 0);
    $("fxTotAnal").textContent = miles(anal);
    $("fxTotRel").textContent = miles(rel);
    $("fxTotDesc").textContent = pct(Math.max(0, 100 - rel / Math.max(1, ventana) * 100));
  }

  // ------------------------------------------------------------------ eventos
  function evItem(x) {
    return `<div class="fx-item">
      <span class="fx-item-ico" style="color:${x.color}"><i class="${x.icon}"></i></span>
      <div class="fx-item-body">
        <div class="fx-item-top"><b>${esc(x.autor)}</b><span>${esc(x.hace)}</span></div>
        <div class="fx-item-txt">${esc(x.texto)}</div>
        <div class="fx-item-meta"><span class="fx-rep">repetida ${x.repeticiones}× desde ${esc(x.desde)}</span> · ${esc(x.alcance)}<span class="fx-sim">simulado</span></div>
      </div>
    </div>`;
  }

  function evCard(e) {
    const aportes = e.aportes.filter((a) => a.pp > 0);
    const barra = aportes.map((a) => `<span style="width:${a.pp}%;background:${FU[a.fuente].color}" title="${esc(FU[a.fuente].nombre)}: +${pp(a.pp)} pp"></span>`).join("");
    const confirmacion = e.confirmado
      ? `<span class="fx-badge ok"><i class="fa-solid fa-circle-check"></i> Confirmado por ${esc(e.confirmado_por.slice(0, 2).join(" y "))}</span>`
      : `<span class="fx-badge warn"><i class="fa-solid fa-triangle-exclamation"></i> Solo redes: sin confirmación oficial</span>`;
    const tendencia = e.cambio_3h_pp >= 0.5 ? `<span class="fx-trend up">▲ +${pp(e.cambio_3h_pp)} pp en 3 h</span>`
      : e.cambio_3h_pp <= -0.5 ? `<span class="fx-trend down">▼ ${pp(e.cambio_3h_pp)} pp en 3 h</span>` : `<span class="fx-trend">estable en 3 h</span>`;
    const evs = fuente ? e.evidencias.filter((x) => x.fuente === fuente) : e.evidencias;
    const abierto = expandidos.has(e.id);
    const lista = evs.slice(0, abierto ? 10 : 3).map(evItem).join("") || `<div class="fx-empty">Sin noticias de ${esc(FU[fuente].nombre)} para este evento.</div>`;
    const vista = e.horizonte === "24 h" ? "24h" : "48h";
    return `<article class="fx-ev">
      <div class="fx-ev-main">
        <div class="fx-ev-head">
          <span class="fx-ev-ico" style="background:${e.color}"><i class="fa-solid ${e.icon}"></i></span>
          <div class="fx-ev-name"><b>${esc(e.titulo)}</b><small>${esc(e.lugar)} · ${esc(e.corredor)}</small></div>
          <span class="fx-h h${vista}">${e.horizonte}</span>
        </div>
        <div class="fx-prob">
          <div class="fx-prob-big">${pct(e.prob_final)}</div>
          <div class="fx-prob-txt">probabilidad de ocurrencia en las próximas ${e.horizonte}<br>
            base del modelo ${pct(e.prob_base)} · <b>+${pp(e.delta_pp)} pp por señales</b></div>
        </div>
        <div class="fx-bar" role="img" aria-label="Base ${pct(e.prob_base)} más ${pp(e.delta_pp)} puntos por señales"><span class="base" style="width:${e.prob_base}%"></span>${barra}</div>
        <div class="fx-aportes">${aportes.map((a) => `<span title="${esc(FU[a.fuente].nombre)}"><i class="${FU[a.fuente].icon}" style="color:${FU[a.fuente].color}"></i> +${pp(a.pp)}</span>`).join("") || "<span>Sin aporte adicional: la base ya es máxima</span>"}</div>
        <div class="fx-badges">${confirmacion}${tendencia}
          <span class="fx-badge"><i class="fa-solid fa-clone"></i> ${e.menciones_total} noticias · ${miles(e.publicaciones_total)} publicaciones · hasta ${e.repeticiones_max}×</span></div>
        <a class="fx-link" href="/riesgo?vista=${vista}">Ver en Riesgo 24–48 h <i class="fa-solid fa-arrow-right"></i></a>
      </div>
      <div class="fx-ev-sust">
        <div class="fx-sust-title">Sustento <small>· de dónde sale</small></div>
        ${lista}
        ${evs.length > 3 ? `<button class="fx-more" data-more="${e.id}">${abierto ? "Ver menos" : `Ver ${Math.min(10, evs.length)} noticias`}</button>` : ""}
      </div>
    </article>`;
  }

  function renderEventos() {
    const lista = data.eventos.filter((e) => !horizonte || e.horizonte === horizonte);
    const n24 = data.eventos.filter((e) => e.horizonte === "24 h").length;
    $("fxEvSub").textContent = `${data.eventos.length} eventos (${n24} a 24 h · ${data.eventos.length - n24} a 48 h) · se actualiza cada 20 s`
      + (fuente ? ` · sustento filtrado por ${FU[fuente].nombre}` : "");
    $("fxEventos").innerHTML = lista.map(evCard).join("");
  }

  // ------------------------------------------------------------------ extracción en vivo
  function renderStream() {
    const items = data.flujo.filter((x) => !fuente || x.fuente === fuente).slice(0, 25);
    const primeraVez = vistos.size === 0;
    $("fxStream").innerHTML = items.map((x, i) => {
      const nuevo = !primeraVez && vistos.get(x.id) !== x.ts;
      return `<div class="fx-st ${nuevo ? "nuevo" : ""}" style="${nuevo ? `animation-delay:${i * 120}ms` : ""}">
        <span class="fx-st-ico" style="background:${x.color}"><i class="${x.icon}"></i></span>
        <div class="fx-st-body">
          <div class="fx-st-top"><b>${esc(x.fuente_nombre)}</b> · ${esc(x.autor)}<span>${esc(x.hace)}</span></div>
          <div class="fx-st-txt">${esc(x.texto)}</div>
          <div class="fx-st-tags"><span>→ ${esc(x.evento)} · ${esc(x.lugar)}</span><span>${x.horizonte}</span><span>${x.repeticiones}×</span>${nuevo ? '<span class="nuevo">nuevo</span>' : ""}</div>
        </div>
      </div>`;
    }).join("") || '<div class="fx-empty">Esperando publicaciones…</div>';
    data.flujo.forEach((x) => vistos.set(x.id, x.ts));
    $("fxStreamSub").textContent = `${data.flujo.length} publicaciones relevantes recientes${fuente ? ` · ${FU[fuente].nombre}` : ""}`;
  }

  // ------------------------------------------------------------------ método
  function renderMetodo() {
    $("fxPesos").innerHTML = data.fuentes.map((f) => `<tr>
      <td><i class="${f.icon} me-2" style="color:${f.color}"></i>${esc(f.nombre)}</td>
      <td><div class="fx-peso"><div class="fx-peso-bar"><span style="width:${f.peso * 100}%;background:${f.color}"></span></div><b>${f.peso.toFixed(2)}</b></div></td>
      <td class="fx-aporta">${esc(APORTA[f.id] || "")}</td></tr>`).join("");
    const e = [...data.eventos].sort((a, b) => b.delta_pp - a.delta_pp)[0];
    if (!e) return;
    const pasos = e.aportes.filter((a) => a.pp > 0).map((a) => `+ ${esc(FU[a.fuente].nombre)} <b>${pp(a.pp)} pp</b>`).join(" ");
    $("fxEjemplo").innerHTML = `<b>Ejemplo resuelto · ${esc(e.titulo)} en ${esc(e.lugar)} (${e.horizonte})</b><br>
      Base del modelo <b>${pct(e.prob_base)}</b> ${pasos} = <b>${pct(e.prob_final)}</b>.
      ${e.menciones_total} noticias únicas circularon ${miles(e.publicaciones_total)} veces; la más repetida, ${e.repeticiones_max} veces.`;
  }

  // ------------------------------------------------------------------ ciclo
  async function cargar() {
    try { data = await RansaAPI.get("/api/fuentes/senales"); } catch (err) { return; }
    FU = Object.fromEntries(data.fuentes.map((f) => [f.id, f]));
    data.fuentes.forEach((f) => { contadores[f.id] = { v: f.analizadas_hoy, r: f.ritmo_min / 60 }; });
    renderFuentes();
    totales();
    renderEventos();
    renderStream();
    renderMetodo();
  }

  function tick() {
    if (!data) return;
    Object.values(contadores).forEach((c) => { c.v += c.r; });
    document.querySelectorAll("[data-anal]").forEach((el) => { el.textContent = miles(contadores[el.dataset.anal].v); });
    totales();
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("fxHorizonte").addEventListener("click", (ev) => {
      const b = ev.target.closest("button[data-h]");
      if (!b) return;
      horizonte = b.dataset.h;
      document.querySelectorAll("#fxHorizonte button").forEach((x) => x.classList.toggle("active", x === b));
      renderEventos();
    });
    $("fxFuentes").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-src]");
      if (!b) return;
      fuente = fuente === b.dataset.src ? "" : b.dataset.src;
      renderFuentes(); renderEventos(); renderStream();
    });
    $("fxEventos").addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-more]");
      if (!b) return;
      if (expandidos.has(b.dataset.more)) expandidos.delete(b.dataset.more); else expandidos.add(b.dataset.more);
      renderEventos();
    });
    cargar();
    setInterval(cargar, POLL_MS);
    setInterval(tick, 1000);
  });
})();
