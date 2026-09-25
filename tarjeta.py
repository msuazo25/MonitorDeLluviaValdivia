"""
Tarjeta para redes con las cifras del momento (matplotlib, modo claro).

    feed      4:5  (1080 x 1350 en pantalla)  -> 7,2 x 9,0 in a 600 dpi
    historia  9:16 (1080 x 1920 en pantalla)  -> 5,4 x 9,6 in a 600 dpi

En la historia el contenido evita las zonas que tapa la interfaz de
Instagram: arriba ~250 px, abajo desde ~1620 px y la columna derecha
(x > 965 px) desde y ~1250 px (medidas sobre 1080 x 1920).
"""
import io

import matplotlib.dates as mdates
import matplotlib.image as mpimg
import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch

import graficos as G                        # tipografía y logo compartidos

PAPEL, TINTA, GRIS = "#FAF9F6", "#2A2A2A", "#6A6A6A"
AZUL, BANDA, ROJO = "#1F5A96", "#9DBFDD", "#B5323C"
FORMATOS = {"feed": (7.2, 9.0), "historia": (5.4, 9.6)}
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _fecha(t):
    return f"{DIAS[t.weekday()]} {t:%d/%m %H:%M}"


def tarjeta(formato, tipo, d):
    """Devuelve los bytes de la tarjeta.

    d: t_obs, inicio, fin, ahora, grupos [(nombre, color, mínimo, máximo, n)],
       lugar, txt_atras, txt_adelante, resto (p10, p50, p90), ts, a10, a50, a90, obs [(x, y, color)], peso, cuenta.
    """
    W, H = FORMATOS[tipo]
    fig = Figure(figsize=(W, H), facecolor=PAPEL)
    historia = tipo == "historia"
    # márgenes en fracción de la figura
    x0 = 0.08
    x1 = 0.86 if historia else 0.92               # historia: libre la columna derecha
    arriba = 1 - 290 / 1920 if historia else 0.95
    abajo = 1 - 1600 / 1920 if historia else 0.035
    ancho_txt = x1 - x0

    def texto(y, s, **kw):
        kw.setdefault("color", TINTA)
        return fig.text(x0, y, s, va="top", **kw)

    esc = 0.92 if historia else 1.0
    esc_v = W / H / (7.2 / 9.0)             # misma altura física en ambas proporciones
    y = arriba
    texto(y, "Lluvia en Valdivia y Corral", fontsize=19 * esc, fontweight="bold")
    y -= 0.045 if historia else 0.05
    texto(y, f"{_fecha(d['inicio'])} → {_fecha(d['fin'])}\n"
             f"actualizado {_fecha(d['t_obs'])} (hora de Chile)",
          fontsize=9 * esc, color=GRIS, linespacing=1.45)

    # observado por grupo
    y -= 0.06 if historia else 0.08
    texto(y, f"Observado* {d['txt_atras']} (mm)", fontsize=10 * esc, fontweight="bold")
    y -= 0.035 if historia else 0.04
    fila = 0.044 if historia else 0.058
    for nombre, color, vmin, vmax, n in d["grupos"]:
        valor = "—" if vmin is None else (f"{vmin:.0f}–{vmax:.0f}" if n > 1 else f"{vmin:.0f}")
        fig.patches.append(FancyBboxPatch(
            (x0, y - 0.027 * esc_v), 0.012, 0.024 * esc_v, boxstyle="round,pad=0,rounding_size=0.004",
            transform=fig.transFigure, fc=color, ec="none"))
        fig.text(x0 + 0.03, y - 0.004, nombre, fontsize=12 * esc, color=TINTA, va="top")
        fig.text(x1, y + 0.004, valor, fontsize=24 * esc, fontweight="bold", color=color,
                 va="top", ha="right")
        y -= fila

    # pronóstico restante
    y -= 0.012
    r10, r50, r90 = d["resto"]
    texto(y, f"Pronóstico {d['lugar']} {d['txt_adelante']}", fontsize=10 * esc,
          fontweight="bold")
    y -= 0.035 if historia else 0.04
    fig.text(x0, y, f"{r50:.0f} mm", fontsize=30 * esc, fontweight="bold", color=AZUL, va="top")
    fig.text(x1, y - 0.012, f"mediana\nrango {r10:.0f}–{r90:.0f} mm", fontsize=9 * esc,
             color=GRIS, va="top", ha="right", linespacing=1.4)

    # mini gráfico del acumulado
    y -= 0.07 if historia else 0.09
    alto = (y - abajo - (0.14 if historia else 0.19))
    ax = fig.add_axes([x0 + 0.06, y - alto, ancho_txt - 0.06, alto])
    ax.set_facecolor("none")
    ax.fill_between(d["ts"], d["a10"], d["a90"], color=BANDA, alpha=.6, lw=0)
    ax.plot(d["ts"], d["a50"], color=AZUL, lw=1.8)
    for xx, yy, col in d["obs"]:
        ax.plot(xx, yy, color=col, lw=1.0)
    ax.axvline(d["ahora"], color=ROJO, lw=0.9)
    ax.set_xlim(d["ts"][0], d["ts"][-1])
    ax.set_ylim(0, None)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#E3E1DC", lw=.5)
    ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.tick_params(labelsize=7 * esc, length=2, width=.5, colors=GRIS)
    ax.set_title(f"Acumulado (mm), {d['lugar']}: estaciones y pronóstico",
                 fontsize=7.5 * esc, color=GRIS, loc="left", pad=4)

    # pie
    lg = mpimg.imread(G.LOGO)
    an_logo = 0.34 if historia else 0.3
    al_logo = an_logo * lg.shape[0] / lg.shape[1] * W / H
    y_logo = abajo + (0.055 if historia else 0.085)
    ax_l = fig.add_axes([x0, y_logo, an_logo, al_logo])
    ax_l.imshow(lg)
    ax_l.axis("off")
    fig.text(x1, y_logo + al_logo / 2, f"Visor de Lluvia · Valdivia\n{d['cuenta']}",
             fontsize=8.5 * esc, color=TINTA, ha="right", va="center", linespacing=1.5)
    fig.text(x0, abajo, "* Datos preliminares de VIPNet (DGA), DMC y red INIA. Pronóstico: super-ensamble\n"
                        f"GEFS, IFS-ENS, ICON-EPS y GEPS (Open-Meteo), {d['peso']}.\n"
                        "No reemplaza las alertas oficiales de SENAPRED y la DMC.",
             fontsize=5.8 * esc, color=GRIS, va="bottom", linespacing=1.45)

    b = io.BytesIO()
    fig.savefig(b, format=formato, dpi=G.DPI, facecolor=PAPEL)
    return b.getvalue()
