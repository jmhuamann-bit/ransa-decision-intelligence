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


@bp.get("/monitoreo")
@login_required
def monitoreo():
    return render_template("monitoreo.html", active_page="monitoreo")


@bp.get("/gemelo")
@login_required
def gemelo():
    return redirect(url_for("web.torre"))


@bp.get("/live")
@login_required
def live():
    return redirect(url_for("web.torre"))


@bp.get("/mapa")
@login_required
def mapa():
    return redirect(url_for("web.torre"))


@bp.get("/predicciones")
@login_required
def predicciones():
    return render_template("predicciones.html", active_page="predicciones")


@bp.get("/riesgo-24h")
@login_required
def riesgo_24h():
    return render_template("riesgo_24h.html", active_page="riesgo_24h")


@bp.get("/forecast-48h")
@login_required
def forecast_48h():
    return render_template("forecast_48h.html", active_page="forecast_48h")


@bp.get("/modelo-leadtime")
@login_required
def modelo_leadtime():
    return render_template("modelo_leadtime.html", active_page="modelo_leadtime")


@bp.get("/contingencias")
@login_required
def contingencias():
    return render_template("contingencias.html", active_page="contingencias")


@bp.get("/embarques")
@login_required
def embarques():
    return render_template("embarques.html", active_page="embarques")


@bp.get("/clientes")
@login_required
def clientes():
    return render_template("clientes.html", active_page="clientes")


@bp.get("/simulador")
@login_required
def simulador():
    return render_template("simulador.html", active_page="simulador")


@bp.get("/chat")
@login_required
def chat():
    return render_template("chat.html", active_page="chat")


@bp.get("/kpis")
@login_required
def kpis_page():
    return render_template("kpis.html", active_page="kpis")


@bp.get("/reportes")
@login_required
def reportes():
    return render_template("reportes.html", active_page="reportes")


@bp.get("/configuracion")
@login_required
def configuracion():
    return render_template("configuracion.html", active_page="configuracion")


@bp.get("/perfil")
@login_required
def perfil():
    return render_template("perfil.html", active_page="perfil")


@bp.get("/ayuda")
@login_required
def ayuda():
    return render_template("ayuda.html", active_page="ayuda")
