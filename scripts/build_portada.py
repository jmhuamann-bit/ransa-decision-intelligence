"""
Genera la portada pública de GitHub Pages (docs/index.html) a partir de scripts/portada_template.html.

La portada carga al instante desde https://jmhuamann-bit.github.io/ransa-decision-intelligence/, dibuja el
Perú con la red vial real (la misma silueta del login), despierta el servidor de Render y entra sola
a la plataforma como visitante.

Ejecutar:  python scripts/build_portada.py [url_de_la_app]
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.web import _login_network  # noqa: E402

APP_URL = (sys.argv[1] if len(sys.argv) > 1 else "https://ransa-decision-intelligence.onrender.com").rstrip("/")
TEMPLATE = os.path.join(BASE_DIR, "scripts", "portada_template.html")
OUT_DIR = os.path.join(BASE_DIR, "docs")


def main() -> None:
    red = _login_network()
    # silueta continua (como en el login) + trazo discontinuo animado encima que sugiere el flujo de carga
    base = "".join(
        f'<path d="{p["d"]}" stroke="{p["color"]}" stroke-width="{p["w"]}" opacity="{round(p["o"] * .45, 2)}"/>'
        for p in red["paths"])
    flujo = "".join(
        f'<path d="{p["d"]}" stroke="{p["color"]}" stroke-width="{p["w"]}" opacity="{p["o"]}"/>'
        for p in red["paths"] if p["color"] != "#c7d2e8")  # las rutas aéreas quedan solo de fondo
    paths = (f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{base}</g>'
             f'<g class="flujo" fill="none" stroke-linecap="round" stroke-linejoin="round">{flujo}</g>')
    nodos = "".join(f'<circle cx="{n["x"]}" cy="{n["y"]}" r="{n["r"]}" fill="#ffffff" opacity=".9"/>' for n in red["nodes"])
    html = open(TEMPLATE, encoding="utf-8").read()
    html = html.replace("__RED__", paths).replace("__NODOS__", nodos).replace("__APP__", APP_URL)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    open(os.path.join(OUT_DIR, ".nojekyll"), "w").close()  # GitHub Pages sirve los archivos tal cual
    print(f"OK: docs/index.html ({len(html) // 1024} KB) → la portada entra a {APP_URL}")


if __name__ == "__main__":
    main()
