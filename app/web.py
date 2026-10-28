"""Blueprint de paginas (renderizado de plantillas). Los datos siempre llegan via fetch() a /api/*."""
from functools import lru_cache

from flask import Blueprint, current_app, redirect, render_template, url_for
from flask_login import current_user, login_required

bp = Blueprint("web", __name__)


@lru_cache(maxsize=1)
def _login_network() -> dict:
    """Silueta del Perú dibujada con la red vial real (para el panel visual del login)."""
    from app.services import geo_data
    lon0, lon1, lat0, lat1 = -81.6, -68.4, -18.6, -0.2
    sx, sy = 400 / (lon1 - lon0), 520 / (lat1 - lat0)

    def xy(lat, lon):
        return round((lon - lon0) * sx, 1), round((lat1 - lat) * sy, 1)

    colors = {"Carretero": ("#ff7a1a", 1.6, .85), "Marítimo": ("#3d63ff", 1.2, .7),
              "Fluvial": ("#22d3ee", 1.4, .8), "Aéreo": ("#c7d2e8", .8, .35)}
    paths = []
    for r in geo_data.all_routes():
        if r.get("alterna_de"):
            continue
        geom = r["geometry"]
        step = max(1, len(geom) // 40)
        pts = [xy(*g) for g in geom[::step]] + [xy(*geom[-1])]
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        c, w, o = colors.get(r["modo"], ("#fff", 1, .5))
        paths.append({"d": d, "color": c, "w": w, "o": o})
    nodes = []
    for n in geo_data.get_network()["nodes"]:
        x, y = xy(n["lat"], n["lon"])
        nodes.append({"x": x, "y": y, "r": 4.2 if "hub" in n["roles"] else 2.4})
    return {"paths": paths, "nodes": nodes}


@bp.get("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("web.torre"))
    return redirect(url_for("web.login_page"))


@bp.get("/torre")
@login_required
def torre():
    return render_template("torre.html", active_page="torre")


@bp.get("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("web.torre"))
    return render_template("login.html", login_network=_login_network(),
                           demo_mode=current_app.config.get("DEMO_MODE", False))


@bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", active_page="dashboard")


@bp.get("/riesgo")
@login_required
def riesgo():
    return render_template("riesgo.html", active_page="riesgo")


@bp.get("/simulador")
@login_required
def simulador():
    return render_template("simulador.html", active_page="simulador")


@bp.get("/modelos")
@login_required
def modelos():
    return render_template("modelos.html", active_page="modelos")


@bp.get("/embarques")
@login_required
def embarques():
    return render_template("embarques.html", active_page="embarques")


@bp.get("/perfil")
@login_required
def perfil():
    return render_template("perfil.html", active_page="perfil")


@bp.get("/ayuda")
@login_required
def ayuda():
    return render_template("ayuda.html", active_page="ayuda")


# Rutas de la versión anterior (más módulos): se fusionaron para simplificar la plataforma y
# redirigen a su nuevo lugar para que ningún enlace guardado quede roto.
_REDIRECCIONES = {
    "/gemelo": ("web.torre", {}), "/live": ("web.torre", {}), "/mapa": ("web.torre", {}),
    "/contingencias": ("web.torre", {}), "/chat": ("web.torre", {}),
    "/monitoreo": ("web.embarques", {}),
    "/riesgo-24h": ("web.riesgo", {}), "/forecast-48h": ("web.riesgo", {"vista": "48h"}),
    "/predicciones": ("web.modelos", {}), "/modelo-leadtime": ("web.modelos", {"vista": "leadtime"}),
    "/kpis": ("web.dashboard", {}), "/clientes": ("web.dashboard", {}), "/reportes": ("web.dashboard", {}),
    "/configuracion": ("web.perfil", {}),
}


def _redireccion(destino: str, params: dict):
    def view():
        return redirect(url_for(destino, **params))
    return view


for _ruta, (_destino, _params) in _REDIRECCIONES.items():
    bp.add_url_rule(_ruta, endpoint="old_" + _ruta.strip("/").replace("-", "_"),
                    view_func=login_required(_redireccion(_destino, _params)))
