/* Cliente REST minimalista compartido por todas las paginas. */
const RansaAPI = (() => {
  async function request(path, options = {}) {
    const opts = {
      method: options.method || "GET",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      credentials: "same-origin",
    };
    if (options.body !== undefined) opts.body = JSON.stringify(options.body);

    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (e) { /* respuesta sin cuerpo JSON */ }

    if (!res.ok) {
      const message = (data && data.error) || `Error ${res.status}`;
      if (res.status === 401 && !path.includes("/auth/")) {
        window.location.href = "/login";
      }
      throw new Error(message);
    }
    return data;
  }

  return {
    get: (path) => request(path),
    post: (path, body) => request(path, { method: "POST", body }),
    put: (path, body) => request(path, { method: "PUT", body }),
    del: (path) => request(path, { method: "DELETE" }),
  };
})();

function gdFormatPEN(value) {
  if (value === null || value === undefined) return "—";
  return "S/ " + new Intl.NumberFormat("es-PE", { maximumFractionDigits: 0 }).format(value);
}
/* Soles compactos para tarjetas: S/ 1,2 M · S/ 845 mil */
function gdFormatPENShort(value) {
  if (value === null || value === undefined) return "—";
  const a = Math.abs(value);
  if (a >= 1e9) return `S/ ${gdFormatNumber(value / 1e9, 2)} mil M`;
  if (a >= 1e6) return `S/ ${gdFormatNumber(value / 1e6, 1)} M`;
  if (a >= 1e4) return `S/ ${gdFormatNumber(value / 1e3, 0)} mil`;
  return gdFormatPEN(value);
}
function gdFormatNumber(value, decimals = 1) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("es-PE", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(value);
}
function gdFormatPct(value, decimals = 1) {
  if (value === null || value === undefined) return "—";
  return `${gdFormatNumber(value, decimals)}%`;
}
function gdFormatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d)) return value;
  return new Intl.DateTimeFormat("es-PE", { year: "numeric", month: "short", day: "2-digit" }).format(d);
}
function gdInitials(name) {
  if (!name) return "?";
  return name.split(" ").filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("");
}
function gdDebounce(fn, wait = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

/* Glosario compartido: explica en lenguaje sencillo cualquier termino tecnico que
   aparezca en la plataforma, para que cualquier persona (no solo un analista de datos)
   entienda que significa. Usar gdGlossaryIcon("OTIF") junto a un termino, y llamar
   gdInitTooltips() despues de inyectar HTML dinamico (innerHTML no activa los tooltips
   de Bootstrap automaticamente). */
const GD_GLOSSARY = {
  OTIF: "On Time In Full: el pedido llegó a tiempo Y completo, según lo prometido al cliente.",
  "Fill Rate": "Porcentaje de lo que el cliente pidió que realmente se despachó (si pidió 100 y se enviaron 95, el fill rate es 95%).",
  "Lead Time": "Tiempo total real que tarda un envío desde que sale hasta que se entrega, en días.",
  "Nivel de Servicio": "Indicador que combina puntualidad, cantidad entregada y seguridad de la carga en un solo número.",
  "Probabilidad de riesgo": "Qué tan probable es, según el modelo de IA entrenado con 30.000 envíos simulados de la red peruana, que este viaje NO cumpla el tiempo y cantidad prometidos.",
  "Corredor logístico": "La ruta entre dos ciudades o puertos (por ejemplo Lima - Huancayo por la Carretera Central) por la que circulan los envíos.",
  "Índice de riesgo": "Un puntaje de 0 a 100 que resume qué tan afectado está un corredor por un tipo de problema (clima, vías, seguridad, etc.). 0 = sin afectación, 100 = afectación máxima observada históricamente.",
  ROC: "Gráfico que muestra qué tan bien distingue el modelo entre envíos que sí y que no van a cumplir — mientras más se acerca la curva a la esquina superior izquierda, mejor.",
  "Matriz de Confusión": "Tabla que compara lo que el modelo predijo contra lo que realmente pasó, para ver aciertos y errores.",
  "Coeficiente estandarizado": "Qué tanto peso le da el modelo a cada variable para hacer su predicción — mientras más alto (positivo o negativo), más influye esa variable.",
  "Riesgo Global": "Promedio del riesgo de todos los envíos activos en este momento, combinado con qué tantos ya tienen un problema en curso.",
  "Probabilidad estimada (24h)": "Estimación de qué tan probable es que ocurra este tipo de evento en las próximas 24 horas en este corredor, calculada a partir de qué tan seguido ha pasado históricamente en esa misma ruta.",
  "Gemelo digital": "Réplica virtual de la operación: cada unidad recorre la vía real del Perú con su velocidad según pendiente y altitud, y los eventos (huaicos, bloqueos, oleajes) la afectan como en la realidad.",
  "Huaico": "Flujo repentino de lodo y piedras que baja por las quebradas en temporada de lluvias y puede cortar una carretera por horas o días.",
  "Vaciante": "Época de aguas bajas en los ríos amazónicos (ago–oct): las chatas deben reducir carga o navegar más lento por falta de calado.",
  "SENAMHI": "Servicio Nacional de Meteorología e Hidrología del Perú: emite avisos amarillos, naranjas y rojos por lluvias, heladas o nevadas.",
};

function gdGlossaryIcon(term, customText) {
  const text = customText || GD_GLOSSARY[term] || term;
  return `<i class="fa-solid fa-circle-info gd-help" data-bs-toggle="tooltip" data-bs-placement="top" title="${text.replace(/"/g, "&quot;")}"></i>`;
}

function gdInitTooltips(container) {
  const root = container || document;
  root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
    if (window.bootstrap && !bootstrap.Tooltip.getInstance(el)) {
      new bootstrap.Tooltip(el);
    }
  });
}

/* Formatea un valor numérico según su unidad (usado por las fichas contextuales). */
function gdFormatByUnit(value, unit) {
  switch (unit) {
    case "int": return gdFormatNumber(value, 0);
    case "pct": return gdFormatPct(value);
    case "cop": return gdFormatPEN(value);
    case "pen": return gdFormatPEN(value);
    case "ton": return `${gdFormatNumber(value)} ton`;
    case "dias": return `${gdFormatNumber(value)} días`;
    case "h": return `${gdFormatNumber(value)} h`;
    default: return gdFormatNumber(value);
  }
}

/* Tarjeta KPI reutilizable (patrón compartido por Dashboard, Live, Torre, etc.). */
function gdKpiTile({ icon, bg, label, value, unit, sub, col }) {
  const shown = unit !== undefined ? gdFormatByUnit(value, unit) : value;
  return `
    <div class="${col || "col-6 col-lg-3"}">
      <div class="gd-kpi">
        <div class="gd-kpi-icon ${bg}"><i class="fa-solid ${icon}"></i></div>
        <div class="gd-kpi-label">${label}</div>
        <div class="gd-kpi-value">${shown}</div>
        ${sub ? `<div class="gd-kpi-delta" style="color:var(--gd-text-muted);">${sub}</div>` : ""}
      </div>
    </div>`;
}

/* Pestañas de página (?vista=…): muestra el panel [data-vista-pane] elegido, recuerda la vista en la URL y
   avisa a mapas y gráficos (resize + gd:vista) para que recalculen su tamaño al hacerse visibles. */
function gdPageTabs(segId, hints) {
  const seg = document.getElementById(segId);
  if (!seg) return;
  const hint = seg.parentElement.querySelector(".gd-page-hint");
  const botones = [...seg.querySelectorAll("[data-vista]")];
  function show(vista, recordar) {
    botones.forEach((b) => b.classList.toggle("active", b.dataset.vista === vista));
    document.querySelectorAll("[data-vista-pane]").forEach((p) => { p.style.display = p.dataset.vistaPane === vista ? "" : "none"; });
    if (hint) hint.textContent = (hints || {})[vista] || "";
    if (recordar) {
      const u = new URL(window.location.href);
      u.searchParams.set("vista", vista);
      history.replaceState(null, "", u);
    }
    setTimeout(() => {
      window.dispatchEvent(new Event("resize"));
      window.dispatchEvent(new CustomEvent("gd:vista", { detail: vista }));
    }, 40);
  }
  botones.forEach((b) => b.addEventListener("click", () => show(b.dataset.vista, true)));
  const pedida = new URLSearchParams(window.location.search).get("vista");
  show(botones.some((b) => b.dataset.vista === pedida) ? pedida : botones[0].dataset.vista, false);
}

/* Contador animado: lleva el número mostrado en `el` hasta `to` (formato con `fmt`). */
function gdCountUp(el, to, fmt, ms = 900) {
  if (!el) return;
  const from = Number(el.dataset.v || 0);
  const t0 = performance.now();
  el.dataset.v = to;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt(to); return; }
  function step(t) {
    const k = Math.min(1, (t - t0) / ms);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (to - from) * e);
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
