(function () {
  const root = document.documentElement;
  const stored = localStorage.getItem("gd-theme");
  if (stored) root.setAttribute("data-theme", stored);

  function applyIcon() {
    const btn = document.getElementById("gdThemeToggle");
    if (!btn) return;
    const isDark = root.getAttribute("data-theme") === "dark";
    btn.innerHTML = isDark ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyIcon();
    const btn = document.getElementById("gdThemeToggle");
    if (btn) {
      btn.addEventListener("click", () => {
        const current = root.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const next = current === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem("gd-theme", next);
        applyIcon();
        document.dispatchEvent(new CustomEvent("gd-theme-changed", { detail: { theme: next } }));
      });
    }
  });
})();
