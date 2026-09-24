"""
Versiones descargables (matplotlib, modo claro) de los gráficos de la app.

Se generan solo al apretar el botón de descarga: cada función devuelve los
bytes del archivo (PNG a 600 dpi o PDF vectorial).
"""
import io
from pathlib import Path

import matplotlib
import matplotlib.dates as mdates
import numpy as np
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    # Arial si está (Windows); en el servidor, equivalentes métricos
    "font.sans-serif": ["Arial", "Liberation Sans", "Helvetica", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 10, "axes.labelsize": 8,
    "pdf.fonttype": 42,
})

AZUL, BANDA, ROJO, GRIS = "#1F5A96", "#9DBFDD", "#B5323C", "#555555"
LOGO = Path(__file__).resolve().parent / "recursos" / "logo_lab_negro.png"
DPI = 600


def _base(titulo, subtitulo, pie):
    fig = Figure(figsize=(7.5, 4.1), facecolor="white")
    ax = fig.add_axes([0.075, 0.30, 0.9, 0.53])
    fig.text(0.075, 0.95, titulo, fontsize=11, fontweight="bold", va="top")
    fig.text(0.075, 0.885, subtitulo, fontsize=8, color=GRIS, va="top")
    fig.text(0.075, 0.035, pie, fontsize=5.6, color=GRIS, va="bottom", linespacing=1.4)
    if LOGO.exists():
        import matplotlib.image as mpimg
        lg = fig.add_axes([0.80, 0.905, 0.175, 0.07])
        lg.imshow(mpimg.imread(LOGO))
        lg.axis("off")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#E3E3E3", lw=.6)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M"))
    ax.tick_params(length=2.5, width=.6)
    return fig, ax


def _ahora(ax, ahora):
    ax.axvline(ahora, color=ROJO, lw=1)
    ax.text(ahora, 1.0, " ahora", transform=ax.get_xaxis_transform(), color=ROJO,
            fontsize=7, va="top", ha="left")


def _leyenda(ax, marcas):
    ax.legend(handles=marcas, ncol=min(len(marcas), 4), frameon=False, fontsize=6.3,
              loc="upper center", bbox_to_anchor=(.5, -.2), handlelength=1.6,
              columnspacing=1.2)


def _guarda(fig, formato):
    b = io.BytesIO()
    fig.savefig(b, format=formato, dpi=DPI, facecolor="white")
    return b.getvalue()


def por_hora(formato, ts, p10, p90, med, obs, ahora, subtitulo, pie, modelos=None,
             lw_obs=1.4, techo=None):
    """obs: lista de (etiqueta, x, y, color) con la media horaria observada.
    modelos: lista de (nombre, x, p10, mediana, p90, color); si viene, se dibuja
    la mediana de cada modelo sobre la banda gris del super-ensamble."""
    fig, ax = _base("Precipitación por hora (mm)", subtitulo, pie)
    ts = np.asarray(ts, dtype="datetime64[ns]")
    if modelos:
        ax.fill_between(ts, p10, p90, color="#BDBDBD", alpha=.5, lw=0)
        for _, x, _, q50, _, col in modelos:
            ax.plot(x, q50, color=col, lw=1.4)
    else:
        ax.fill_between(ts, p10, p90, color=BANDA, alpha=.6, lw=0)
        ancho = np.median(np.diff(ts)).astype("timedelta64[s]").astype(float) / 86400 * .8
        ax.bar(ts, med, width=ancho, color=AZUL, alpha=.85)
    for _, x, y, col in obs:
        ax.plot(x, y, color=col, lw=lw_obs)
    _ahora(ax, ahora)
    ax.set_xlim(ts[0], ts[-1])
    ax.set_ylim(0, techo)            # techo: mismo eje y entre zonas
    if modelos:
        marcas = [Patch(color="#BDBDBD", alpha=.5, label="super-ensamble p10–p90")]
        marcas += [Line2D([], [], color=c, lw=1.4, label=n)
                   for n, _, _, _, _, c in modelos]
    else:
        marcas = [Patch(color=BANDA, alpha=.6, label="pronóstico p10–p90"),
                  Patch(color=AZUL, alpha=.85, label="pronóstico mediana")]
    marcas += [Line2D([], [], color=c, lw=lw_obs, label=f"observado* {n}") for n, _, _, c in obs]
    _leyenda(ax, marcas)
    return _guarda(fig, formato)


def acumulado(formato, ts, a10, a50, a90, obs, ahora, subtitulo, pie, modelos=None,
              lw_obs=1.4, techo=None):
    """obs: lista de (etiqueta_grupo, x, y, color), una por estación.
    modelos: lista de (nombre, x, p10, mediana, p90, color) por modelo."""
    fig, ax = _base("Acumulado desde el inicio (mm)", subtitulo, pie)
    if modelos:
        for _, x, q10, q50, q90, col in modelos:
            ax.fill_between(x, q10, q90, color=col, alpha=.25, lw=0)
            ax.plot(x, q50, color=col, lw=1.6)
    else:
        ax.fill_between(ts, a10, a90, color=BANDA, alpha=.6, lw=0)
        ax.plot(ts, a50, color=AZUL, lw=2)
    vistos = {}
    for n, x, y, col in obs:
        ax.plot(x, y, color=col, lw=lw_obs * .8)
        vistos.setdefault(n, col)
    _ahora(ax, ahora)
    ax.set_xlim(ts[0], ts[-1])
    ax.set_ylim(0, techo)            # techo: mismo eje y entre zonas
    if modelos:
        marcas = [Line2D([], [], color=c, lw=1.6, label=f"{n} (p10–p90)")
                  for n, _, _, _, _, c in modelos]
    else:
        marcas = [Patch(color=BANDA, alpha=.6, label="pronóstico p10–p90"),
                  Line2D([], [], color=AZUL, lw=2, label="pronóstico mediana")]
    marcas += [Line2D([], [], color=c, lw=lw_obs * .8, label=f"observado* {n}")
               for n, c in vistos.items()]
    _leyenda(ax, marcas)
    return _guarda(fig, formato)
