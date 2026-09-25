"""Figuras del informe: fondo blanco, Arial (o Liberation Sans, de métrica idéntica,
donde Arial no está instalada), 17 cm de ancho para que el texto se lea a 12 pt."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import BoundaryNorm, ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402

from . import comun as K  # noqa: E402
from . import metricas as M  # noqa: E402

ANCHO = 17 / 2.54                                   # pulgadas
TINTA, GRIS, ROJO = "#222222", "#666666", "#B5323C"
BANDA = "#E6E6E6"
COLOR_ZONA = K.F.GRUPOS


def fuente():
    """Arial si está; si no, Liberation Sans (misma métrica). Devuelve el nombre."""
    nombres = {f.name for f in font_manager.fontManager.ttflist}
    for n in ("Arial", "Liberation Sans"):
        if n in nombres:
            return n
    return "DejaVu Sans"


FUENTE = fuente()
plt.rcParams.update({
    "font.family": FUENTE, "font.size": 12, "axes.titlesize": 12, "axes.labelsize": 12,
    "xtick.labelsize": 11, "ytick.labelsize": 11, "legend.fontsize": 11,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "axes.edgecolor": TINTA, "axes.labelcolor": TINTA, "xtick.color": TINTA,
    "ytick.color": TINTA, "text.color": TINTA, "axes.spines.top": False,
    "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
})


def guarda(fig, carpeta, nombre):
    rutas = []
    for ext, kw in (("png", dict(dpi=300)), ("pdf", {})):
        p = Path(carpeta) / f"{nombre}.{ext}"
        fig.savefig(p, **kw)
        rutas.append(p)
    plt.close(fig)
    return rutas[0]


def eje_fecha(ax, horas):
    if horas <= 5 * 24:
        ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0]))
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))


# ------------------------------------------------------------------ 1. observado
def observado(R, carpeta):
    Zh = M.zona_horaria(R)
    t = K.a_local(Zh.index)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(ANCHO, 5.6), sharex=True,
                                 gridspec_kw=dict(height_ratios=[1, 1.3]))
    for z in K.ZONAS:
        a1.step(t, Zh[z].values, where="pre", color=COLOR_ZONA[z], lw=1.3, label=f"Zona {z}")
        a2.plot(t, Zh[z].fillna(0).cumsum().values, color=COLOR_ZONA[z], lw=2.4)
        for e in K.EST_ZONA[z]:
            oe = R.obs_h[R.obs_h.estacion == e].set_index("hora_utc").mm.reindex(Zh.index)
            if oe.notna().any():
                a2.plot(t, oe.fillna(0).cumsum().values, color=COLOR_ZONA[z], lw=0.8, alpha=.45)
    a1.set_ylabel("mm por hora")
    a1.set_ylim(0, None)
    a1.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, 1.2))
    a2.set_ylabel("acumulado (mm)")
    a2.set_ylim(0, None)
    a2.set_xlabel("hora de Chile")
    eje_fecha(a2, R.horas)
    a2.set_xlim(t[0] - pd.Timedelta(hours=1), t[-1])
    fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.11, hspace=0.12)
    return guarda(fig, carpeta, "1_observado")


# ------------------------------------------------------------------ 2. total según la corrida
PISO = 0.06


def cociente(R, carpeta):
    fig, axs = plt.subplots(3, 1, figsize=(ANCHO, 7.4), sharex=True)
    ini_l = K.a_local(R.ini)
    hay = False
    for ax, z in zip(axs, K.ZONAS):
        det, sup = M.cociente_resto(R, z)
        for m, g in det.groupby("modelo"):
            ax.plot(K.a_local(g.init), np.clip(g.r, PISO, None), "-o", ms=3.5, lw=1.1,
                    color=K.COLOR_DET[m])
            hay = True
        if len(sup):
            x = K.a_local(sup.init)
            ax.errorbar(x, sup.p50, yerr=[sup.p50 - sup.p10, sup.p90 - sup.p50], fmt="s",
                        color="k", ms=5, capsize=3, lw=1.2, zorder=5)
        ax.axhline(1, color=TINTA, lw=0.8)
        ax.axhspan(0.8, 1.25, color=BANDA, zorder=0)
        ax.axvline(ini_l, color=ROJO, lw=0.9, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(PISO * 0.9, 4.5)
        ax.set_yticks([PISO, 0.25, 0.5, 1, 2, 4])
        ax.set_yticklabels(["≤0,06", "0,25", "0,5", "1", "2", "4"])
        ax.minorticks_off()
        ax.set_title(f"Zona {z}")
    axs[1].set_ylabel("pronosticado / observado (lo que quedaba del evento)")
    axs[0].text(ini_l, 3.2, " inicio del evento", color=ROJO, fontsize=11)
    axs[-1].set_xlabel("inicio de la corrida (hora de Chile)")
    eje_fecha(axs[-1], 24 * 8)
    marcas = [Line2D([], [], marker="o", color=K.COLOR_DET[m], label=K.NOMBRE_DET[m])
              for m in K.MODELOS_DET if m in set(R.det_h.modelo)]
    marcas.append(Line2D([], [], marker="s", ls="", color="k",
                         label="Super-ensamble (mediana y p10–p90)"))
    fig.legend(handles=marcas, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0))
    fig.subplots_adjust(left=0.1, right=0.98, top=0.96, bottom=0.21, hspace=0.32)
    return guarda(fig, carpeta, "2_total_por_corrida") if hay else None


# ------------------------------------------------------------------ 3. total por estación
CANDIDATOS = [(9, 0, "left", "center"), (-9, 0, "right", "center"), (0, 10, "center", "bottom"),
              (0, -10, "center", "top"), (7, 7, "left", "bottom"), (7, -7, "left", "top"),
              (-7, 7, "right", "bottom"), (-7, -7, "right", "top"), (18, 0, "left", "center"),
              (-18, 0, "right", "center"), (0, 22, "center", "bottom"), (0, -22, "center", "top"),
              (14, 16, "left", "bottom"), (14, -16, "left", "top"), (-14, 16, "right", "bottom"),
              (-14, -16, "right", "top")]


def etiquetas(fig, ax, puntos):
    """Pone cada etiqueta en la primera posición candidata que no choque con otra
    etiqueta ni con un rombo; si ninguna sirve, usa la que menos se superpone."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    caja_ax = ax.get_window_extent(r)
    ocupado = []
    for x, y, _ in puntos:
        px, py = ax.transData.transform((x, y))
        ocupado.append(Bbox([[px - 8, py - 8], [px + 8, py + 8]]))
    for x, y, txt in puntos:
        mejor = None
        for dx, dy, ha, va in CANDIDATOS:
            t = ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points",
                            ha=ha, va=va, fontsize=11,
                            arrowprops=dict(arrowstyle="-", color=GRIS, lw=.6)
                            if abs(dx) + abs(dy) > 20 else None)
            b = t.get_window_extent(r).expanded(1.04, 1.1)
            dentro = caja_ax.contains(b.x0, b.y0) and caja_ax.contains(b.x1, b.y1)
            choque = sum(b.overlaps(o) for o in ocupado) + (0 if dentro else 5)
            if mejor is None or choque < mejor[0]:
                if mejor:
                    mejor[1].remove()
                mejor = (choque, t, b)
            else:
                t.remove()
            if choque == 0:
                break
        ocupado.append(mejor[2])


def estaciones(R, carpeta):
    fig, ax = plt.subplots(figsize=(ANCHO, ANCHO * 0.98))
    filas, vals = [], []
    for _, t in R.TOT.iterrows():
        if t.cobertura < M.MIN_COBERTURA:
            continue
        por_mod = M.total_previas(R, t.estacion)
        if por_mod.empty:
            continue
        for m, v in por_mod.items():
            ax.scatter(t.mm, v, s=18, color=K.COLOR_DET[m], alpha=.85, zorder=3)
        med = por_mod.median()
        ax.scatter(t.mm, med, s=110, marker="D", color=COLOR_ZONA[t.zona], edgecolor="k",
                   lw=.6, zorder=4)
        filas.append((t.estacion, t.mm, med, t.cobertura))
        vals += [t.mm, *por_mod.values]
    if not filas:
        plt.close(fig)
        return None, []
    # mismo rango en ambos ejes (la diagonal queda a 45°), acotado a los datos
    lo, hi = min(vals), max(vals)
    pad = 0.08 * (hi - lo)
    lo, hi = max(0, lo - pad), hi + pad
    x = np.array([0, hi * 2])
    ax.plot(x, x, color=TINTA, lw=.8)
    ax.fill_between(x, 0.8 * x, 1.25 * x, color=BANDA, zorder=0)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal")
    ax.set_xlabel("observado en el evento (mm)")
    ax.set_ylabel("pronosticado (mm)")
    marcas = [Line2D([], [], marker="o", ls="", color=K.COLOR_DET[m], label=K.NOMBRE_DET[m])
              for m in K.MODELOS_DET if m in set(R.det_h.modelo)]
    marcas += [Line2D([], [], marker="D", ls="", color=c, mec="k", label=f"Zona {g}")
               for g, c in COLOR_ZONA.items()]
    fig.legend(handles=marcas, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0))
    fig.subplots_adjust(left=0.12, right=0.97, top=0.98, bottom=0.25)
    etiquetas(fig, ax, [(o, med, K.NOMBRE_EST[e] + ("" if cob >= 0.999 else f" ({100 * cob:.0f} %)"))
                        for e, o, med, cob in filas])
    return guarda(fig, carpeta, "3_total_por_estacion"), filas


# ------------------------------------------------------------------ 4. error según plazo
def tramos(R):
    mx = R.MET.plazo_h.max() if len(R.MET) else 96
    b = [0, 24, 48, 72, 96, 120]
    while b[-1] < mx:
        b.append(b[-1] + (48 if b[-1] >= 120 else 24))
    return b


def plazo(R, carpeta):
    MET = R.MET.copy()
    if MET.empty:
        return None
    T = tramos(R)
    MET["tramo"] = pd.cut(MET.plazo_h, T, labels=[f"{a}–{b}" for a, b in zip(T, T[1:])])
    cats = MET.tramo.cat.categories
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(ANCHO, 5.0), sharex=True)
    d = MET[(MET.tipo == "determinista") & ~MET.unidad.str.startswith("zona")]
    for m in K.MODELOS_DET:
        g = d[d.modelo == m]
        if g.empty:
            continue
        s = g.groupby("tramo", observed=False).error.agg(["mean", "count"])
        s.loc[s["count"] < 10, "mean"] = np.nan
        a1.plot(range(len(s)), s["mean"], "-o", ms=4, color=K.COLOR_DET[m], label=K.NOMBRE_DET[m])
    a1.set_title("Deterministas, en cada estación")
    a1.legend(ncol=3, loc="upper left")
    z = MET[MET.unidad.str.startswith("zona")]
    for (tipo, m), g in z.groupby(["tipo", "modelo"]):
        s = g.groupby("tramo", observed=False).error.agg(["mean", "count"])
        s.loc[s["count"] < 3, "mean"] = np.nan
        if tipo == "determinista":
            a2.plot(range(len(s)), s["mean"], "-o", ms=3, lw=.8, alpha=.5, color=K.COLOR_DET[m])
        elif m == "super":
            a2.plot(range(len(s)), s["mean"], "-s", ms=6, lw=2.2, color="k",
                    label="Super-ensamble (CRPS)")
        else:
            a2.plot(range(len(s)), s["mean"], "--^", ms=5, lw=1.1, color=K.COLOR_DET[K.HERMANO[m]],
                    label=f"{K.NOMBRE_ENS[m]} (CRPS)")
    a2.set_title("Promedio de zona: deterministas (tenues) y ensambles")
    a2.legend(ncol=2, loc="upper left")
    for ax in (a1, a2):
        ax.set_ylim(0, None)
        ax.set_ylabel("error en 6 h (mm)")
    ymax = max(a1.get_ylim()[1], a2.get_ylim()[1]) * 1.3
    for ax in (a1, a2):
        ax.set_ylim(0, ymax)
    a2.set_xticks(range(len(cats)))
    a2.set_xticklabels(cats)
    a2.set_xlabel("plazo del bloque (horas desde el inicio de la corrida)")
    fig.subplots_adjust(left=0.1, right=0.98, top=0.94, bottom=0.14, hspace=0.3)
    return guarda(fig, carpeta, "4_error_segun_plazo")


# ------------------------------------------------------------------ 5. percentil (PIT)
def percentil(R, carpeta):
    S = R.MET[(R.MET.modelo == "super") & R.MET.pit.notna()]
    zonas = [z for z in K.ZONAS if (S.unidad == f"zona_{z}").any()]
    if not zonas:
        return None
    tablas = {z: S[S.unidad == f"zona_{z}"].pivot(index="init", columns="fin", values="pit")
              .sort_index() for z in zonas}
    fines = sorted(set().union(*[set(T.columns) for T in tablas.values()]))
    alto = sum(0.36 * len(T) + 0.9 for T in tablas.values()) + 1.4
    fig, axs = plt.subplots(len(zonas), 1, figsize=(ANCHO, alto), squeeze=False,
                            gridspec_kw=dict(height_ratios=[len(T) + 2.5 for T in tablas.values()]))
    cmap = ListedColormap(["#2166AC", "#92C5DE", "#F7F7F7", "#F4A582", "#B2182B"])
    norm = BoundaryNorm([0, 10, 25, 75, 90, 100], cmap.N)
    fs = 10 if len(fines) <= 14 else 7
    for ax, z in zip(axs[:, 0], zonas):
        T = tablas[z].reindex(columns=fines)
        im = ax.pcolormesh(np.arange(len(fines) + 1), np.arange(len(T) + 1), T.values,
                           cmap=cmap, norm=norm, edgecolors="white", lw=1)
        for i in range(T.shape[0]):
            for j in range(T.shape[1]):
                v = T.values[i, j]
                if np.isfinite(v):
                    ax.text(j + .5, i + .5, f"{v:.0f}", ha="center", va="center", fontsize=fs,
                            color="white" if (v < 10 or v > 90) else TINTA)
        ax.set_yticks(np.arange(len(T)) + .5)
        ax.set_yticklabels([K.txt_local(i) for i in T.index], fontsize=10)
        ax.invert_yaxis()
        ax.set_xticks(np.arange(len(fines)) + .5)
        ax.set_xticklabels([f"{K.a_local(pd.Timestamp(f) - pd.Timedelta(hours=6)):%d/%m\n%H}–"
                            f"{K.a_local(pd.Timestamp(f)):%H}" for f in fines], fontsize=fs)
        ax.set_title(f"Zona {z}")
        for s in ax.spines.values():
            s.set_visible(False)
    axs[-1, 0].set_xlabel("bloque de 6 h (hora de Chile)")
    fig.text(0.01, 0.5, "corrida (inicio, hora de Chile)", rotation=90, va="center")
    fig.subplots_adjust(left=0.19, right=0.86, top=1 - 0.5 / alto, bottom=1.1 / alto, hspace=0.6)
    cax = fig.add_axes([0.89, 0.3, 0.018, 0.4])
    cb = fig.colorbar(im, cax=cax, ticks=[0, 10, 25, 75, 90, 100])
    cb.set_label("percentil de lo observado")
    return guarda(fig, carpeta, "5_percentil_en_ensamble")
