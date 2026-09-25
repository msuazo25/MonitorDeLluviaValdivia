"""Informe en PDF: fondo blanco, Arial 12 (texto) y 14 (títulos), logo del laboratorio.
El texto se arma solo a partir de las métricas, en tono descriptivo."""
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from . import comun as K
from . import figuras as FG
from . import metricas as M

LOGO = Path(__file__).resolve().parent.parent / "recursos" / "logo_lab_negro.png"
ANCHO_TXT = 17 * cm


# ------------------------------------------------------------------ fuentes y estilos
def _registra():
    for peso, nombre in (("normal", "Texto"), ("bold", "TextoBold")):
        ruta = font_manager.findfont(font_manager.FontProperties(family=FG.FUENTE, weight=peso))
        pdfmetrics.registerFont(TTFont(nombre, ruta))
    pdfmetrics.registerFontFamily("Texto", normal="Texto", bold="TextoBold",
                                  italic="Texto", boldItalic="TextoBold")


_registra()
CUERPO = ParagraphStyle("cuerpo", fontName="Texto", fontSize=12, leading=16, alignment=TA_LEFT,
                        spaceAfter=6)
TITULO = ParagraphStyle("titulo", parent=CUERPO, fontName="TextoBold", fontSize=14, leading=18,
                        spaceBefore=12, spaceAfter=6, keepWithNext=True)
PIE = ParagraphStyle("pie", parent=CUERPO, spaceBefore=4, spaceAfter=12)
CELDA = ParagraphStyle("celda", parent=CUERPO, spaceAfter=0, leading=14)


def n(x, d=0):
    """Número con coma decimal."""
    if x is None or not np.isfinite(x):
        return "–"
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",")


def pct(x):
    return f"{100 * x:.0f} %"


def lista(items):
    return ListFlowable([ListItem(Paragraph(t, CUERPO), leftIndent=12, bulletColor="black")
                         for t in items], bulletType="bullet", start="•", leftIndent=12,
                        bulletFontName="Texto", bulletFontSize=12)


def figura(ruta, num, texto, ancho=ANCHO_TXT, alto_max=18.5 * cm):
    from PIL import Image as PI
    w, h = PI.open(ruta).size
    ancho = min(ancho, alto_max * w / h)             # que figura y leyenda quepan en una página
    return KeepTogether([Image(str(ruta), width=ancho, height=ancho * h / w),
                         Paragraph(f"<b>Figura {num}.</b> {texto}", PIE)])


def tabla(filas, anchos, negrita_primera=True):
    datos = [[Paragraph(f"<b>{c}</b>" if (i == 0 and negrita_primera) else str(c), CELDA)
              for c in fila] for i, fila in enumerate(filas)]
    t = Table(datos, colWidths=anchos, hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# ------------------------------------------------------------------ cifras del resumen
def cifras(R, filas_est):
    Zh = M.zona_horaria(R)
    c = {"zona_total": Zh.sum(min_count=1).to_dict()}
    ok = R.TOT[R.TOT.cobertura >= M.MIN_COBERTURA]
    c["est_min"] = ok.loc[ok.mm.idxmin()] if len(ok) else None
    c["est_max"] = ok.loc[ok.mm.idxmax()] if len(ok) else None
    if R.OBS_Z.notna().any().any():
        z6 = R.OBS_Z.stack()
        (f6, zz6) = z6.idxmax()
        c["max6"] = (z6.max(), zz6, f6)
    # cociente del total: corridas de las 36 h previas y de 3-4 días antes
    c["cociente"] = {}
    for z in K.ZONAS:
        det, _ = M.cociente_resto(R, z)
        if det.empty:
            continue
        d1 = det[(det.init <= R.ini) & (det.init >= R.ini - pd.Timedelta(hours=36))]
        d4 = det[(det.init <= R.ini - pd.Timedelta(hours=60)) &
                 (det.init >= R.ini - pd.Timedelta(hours=96))]
        c["cociente"][z] = (d1.groupby("modelo").r.mean().median() if len(d1) else np.nan,
                            d4.groupby("modelo").r.mean().median() if len(d4) else np.nan,
                            d4.groupby("modelo").r.mean() if len(d4) else pd.Series(dtype=float))
    # estaciones: diferencia relativa de la mediana de los modelos
    c["estaciones"] = sorted([(e, o, m, m / o - 1) for e, o, m, _ in filas_est if o > 0],
                             key=lambda x: x[3])
    # error determinista 0-48 h en estaciones
    d = R.MET[(R.MET.tipo == "determinista") & ~R.MET.unidad.str.startswith("zona") &
              (R.MET.plazo_h <= 48)]
    c["mae48"] = d.groupby("modelo").error.mean().sort_values()
    # super-ensamble
    s = R.MET[(R.MET.modelo == "super") & R.MET.pit.notna()]
    c["super_n"] = len(s)
    c["super_fuera"] = ((s.pit < 10) | (s.pit > 90)).mean() if len(s) else np.nan
    c["super_arriba"] = (s.pit > 90).mean() if len(s) else np.nan
    zd = R.MET[(R.MET.tipo == "determinista") & R.MET.unidad.str.startswith("zona") &
               R.MET.error.notna()]
    llave = ["unidad", "fin", "init"]
    if len(s):
        comun = zd.merge(s[llave + ["error"]].assign(init=lambda x: x.init), on=["unidad", "fin"],
                         suffixes=("", "_s"))
        comun = comun[(comun.init.dt.floor("12h") == comun.init_s)]
        c["super_vs_det"] = (comun.error_s.mean(), comun.groupby("modelo").error.mean().min(),
                             comun.groupby("modelo").error.mean().idxmin()) if len(comun) else None
    # mayor error: bloque de zona con mayor diferencia observado - mediana determinista (<= 48 h)
    zz = zd[zd.plazo_h <= 48]
    if len(zz):
        g = zz.groupby(["unidad", "fin"]).agg(obs=("obs", "first"), pron=("pron", "median"))
        g["dif"] = g.obs - g.pron
        (u, f) = g.dif.abs().idxmax()
        c["peor"] = (u[5:], f, g.at[(u, f), "obs"], g.at[(u, f), "pron"])
    return c


# ------------------------------------------------------------------ documento
def genera(R, carpeta, faltan, figs, filas_est, manual=False):
    carpeta = Path(carpeta)
    c = cifras(R, filas_est)
    ini_l, fin_l = K.a_local(R.ini), K.a_local(R.fin)
    salida = carpeta / f"informe_{R.evento}.pdf"
    doc = SimpleDocTemplate(str(salida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title=f"Comprobación de pronósticos · {R.evento}",
                            author="Laboratorio de Dendrocronología y Cambio Global, UACh")
    h = []
    if LOGO.exists():
        from PIL import Image as PI
        w, hh = PI.open(LOGO).size
        h += [Image(str(LOGO), width=5.5 * cm, height=5.5 * cm * hh / w, hAlign="LEFT"),
              Spacer(1, 10)]
    h.append(Paragraph("Comprobación de pronósticos de lluvia en Valdivia", TITULO))
    h.append(Paragraph(
        f"<b>Evento:</b> {ini_l:%d/%m/%Y %H:%M} al {fin_l:%d/%m/%Y %H:%M} (hora de Chile), "
        f"{R.horas} horas.<br/>"
        "<b>Ventana:</b> " + ("fijada a mano" if manual else "detectada automáticamente, "
                              "desde que empezó a llover hasta el final") + ".<br/>"
        f"<b>Informe interno, no publicar.</b> Generado el "
        f"{K.a_local(pd.Timestamp.now('UTC').tz_localize(None)):%d/%m/%Y %H:%M}.", CUERPO))

    # --- resumen
    h.append(Paragraph("Resumen", TITULO))
    r = []
    zt = c["zona_total"]
    r.append("<b>Observado.</b> Promedio por zona: " + "; ".join(
        f"{z} {n(zt[z])} mm" for z in K.ZONAS if np.isfinite(zt.get(z, np.nan))) + "."
        + (f" Por estación, de {n(c['est_min'].mm)} mm ({K.NOMBRE_EST[c['est_min'].estacion]}) "
           f"a {n(c['est_max'].mm)} mm ({K.NOMBRE_EST[c['est_max'].estacion]})."
           if c["est_min"] is not None else ""))
    if "max6" in c:
        v, z, f = c["max6"]
        r.append(f"<b>Bloque de 6 h más lluvioso:</b> {n(v, 1)} mm en la zona {z}, "
                 f"{K.txt_local(f - pd.Timedelta(hours=6))}–{K.txt_local(f, '%H:%M')}.")
    if c["cociente"]:
        partes = []
        for z, (r1, r4, _) in c["cociente"].items():
            partes.append(f"{z} {n(r1, 2)} (3–4 días antes: {n(r4, 2)})")
        r.append("<b>Total del evento, pronosticado / observado</b> (mediana de los modelos "
                 "deterministas, corridas de las 36 h previas al inicio): " + "; ".join(partes)
                 + ". 1 = acierto; bajo 1, el pronóstico quedó corto.")
    if c["estaciones"]:
        lo, hi = c["estaciones"][0], c["estaciones"][-1]
        r.append(f"<b>Por estación</b> (mediana de los modelos, 36 h antes): la mayor "
                 f"subestimación fue en {K.NOMBRE_EST[lo[0]]} ({n(lo[2])} mm pronosticados "
                 f"frente a {n(lo[1])} observados, {n(100 * lo[3])} %) y la mayor "
                 f"sobreestimación en {K.NOMBRE_EST[hi[0]]} ({n(hi[2])} frente a "
                 f"{n(hi[1])} mm, {'+' if hi[3] > 0 else ''}{n(100 * hi[3])} %).")
    if len(c["mae48"]):
        m = c["mae48"]
        r.append(f"<b>Error en bloques de 6 h (plazos hasta 48 h, estaciones):</b> menor en "
                 f"{K.NOMBRE_DET[m.index[0]]} ({n(m.iloc[0], 1)} mm) y mayor en "
                 f"{K.NOMBRE_DET[m.index[-1]]} ({n(m.iloc[-1], 1)} mm).")
    if c["super_n"]:
        txt = (f"<b>Super-ensamble:</b> lo observado quedó fuera del rango p10–p90 en "
               f"{pct(c['super_fuera'])} de {c['super_n']} bloques (un ensamble bien calibrado: "
               f"cerca de 20 %); sobre p90 en {pct(c['super_arriba'])}.")
        if c.get("super_vs_det"):
            e_s, e_d, m_d = c["super_vs_det"]
            txt += (f" En los mismos bloques y corridas, su CRPS medio fue {n(e_s, 1)} mm, frente "
                    f"a {n(e_d, 1)} mm del mejor determinista ({K.NOMBRE_DET[m_d]}).")
        r.append(txt)
    if "peor" in c:
        z, f, o, p = c["peor"]
        r.append(f"<b>Mayor diferencia en un bloque</b> (zona, plazos hasta 48 h): zona {z}, "
                 f"{K.txt_local(f - pd.Timedelta(hours=6))}–{K.txt_local(f, '%H:%M')}: "
                 f"{n(o, 1)} mm observados y {n(p, 1)} mm en la mediana de los deterministas.")
    h.append(lista(r))

    # --- observado
    h += [PageBreak(), Paragraph("1. Lluvia observada", TITULO)]
    filas = [["Estación", "Zona", "Total (mm)", "Horas con dato"]]
    for _, t in R.TOT.iterrows():
        filas.append([K.NOMBRE_EST[t.estacion], t.zona, n(t.mm, 1),
                      f"{t.horas} de {R.horas} ({pct(t.cobertura)})"])
    h.append(tabla(filas, [4.5 * cm, 3 * cm, 3 * cm, 6.5 * cm]))
    h.append(Spacer(1, 8))
    if figs.get("observado"):
        h.append(figura(figs["observado"], 1,
                        "Arriba: lluvia horaria promedio de cada zona. Abajo: acumulado de la "
                        "zona (línea gruesa) y de cada estación (líneas finas). Datos "
                        "preliminares, sin control de calidad."))

    # --- total según la corrida
    h += [PageBreak(), Paragraph("2. Total del evento según la corrida", TITULO)]
    h.append(Paragraph(
        "Para cada corrida se compara lo que pronosticaba para el resto del evento (desde su "
        "hora de inicio hasta el final) con lo que efectivamente llovió en ese mismo lapso. "
        "Así se ve cómo cambió el pronóstico a medida que se acercaba el evento.", CUERPO))
    if figs.get("cociente"):
        h.append(figura(figs["cociente"], 2,
                        "Pronosticado / observado de lo que quedaba del evento, según la hora de "
                        "inicio de la corrida (escala logarítmica). Banda gris: ±25 %. Línea "
                        "roja: inicio del evento. Solo lapsos con al menos 10 mm observados. "
                        "Super-ensamble: igual peso por modelo; antes del 24/09 solo existe en "
                        "el punto de Valdivia y se compara con la zona ciudad."))

    # --- por estación
    h += [PageBreak(), Paragraph("3. Total del evento por estación", TITULO)]
    if figs.get("estaciones"):
        h.append(figura(figs["estaciones"], 3, alto_max=14 * cm, texto=
                        "Total observado frente al pronosticado por las corridas de las 36 h "
                        "previas al inicio. Puntos chicos: cada modelo determinista (promedio de "
                        "sus corridas); rombos: mediana de los modelos. Banda gris: ±25 %. El "
                        "pronóstico se suma solo en las horas con dato observado; entre "
                        "paréntesis, el porcentaje de horas con dato."))
        filas = [["Estación", "Observado (mm)", "Pronosticado (mm)", "Diferencia"]]
        for e, o, m, _ in sorted(filas_est, key=lambda x: K.ZONAS.index(K.ZONA_EST[x[0]])):
            filas.append([K.NOMBRE_EST[e], n(o), n(m), f"{'+' if m > o else ''}{n(100 * (m / o - 1))} %"
                          if o > 0 else "–"])
        h.append(KeepTogether(tabla(filas, [4.5 * cm, 4 * cm, 4.5 * cm, 4 * cm])))

    # --- error según plazo
    h += [PageBreak(), Paragraph("4. Error en bloques de 6 horas según el plazo", TITULO)]
    h.append(Paragraph(
        "La lluvia se agrupa en bloques de 6 horas alineados a la hora UTC (en hora de Chile: "
        f"{K.a_local(pd.Timestamp('2026-01-01 00:00')):%H}–"
        f"{K.a_local(pd.Timestamp('2026-01-01 06:00')):%H}, etc.; JMA solo entrega así). "
        "El plazo es el tiempo entre el inicio de la corrida y el fin del bloque. Para los "
        "deterministas se usa el error absoluto; para los ensambles, el CRPS, que para un solo "
        "valor es igual al error absoluto, así que ambos se comparan en milímetros.", CUERPO))
    if figs.get("plazo"):
        h.append(figura(figs["plazo"], 4, alto_max=12.8 * cm, texto=
                        "Error medio de la lluvia en 6 h según el plazo. Arriba: deterministas "
                        "en la celda de cada estación. Abajo: promedio de zona, con los "
                        "ensambles (CRPS) y el super-ensamble. Se omiten tramos con pocos casos "
                        "(menos de 10 arriba y de 3 abajo)."))
        d = R.MET[(R.MET.tipo == "determinista") & ~R.MET.unidad.str.startswith("zona")].copy()
        T = FG.tramos(R)
        d["tramo"] = pd.cut(d.plazo_h, T, labels=[f"{a}–{b} h" for a, b in zip(T, T[1:])])
        P = d.pivot_table(index="modelo", columns="tramo", values="error", aggfunc="mean",
                          observed=True)
        P = P[[t for t in P.columns[:5]]]
        filas = [["Modelo"] + list(P.columns)]
        for m in K.MODELOS_DET:
            if m in P.index:
                filas.append([K.NOMBRE_DET[m]] + [n(v, 1) for v in P.loc[m]])
        ancho = (ANCHO_TXT - 4 * cm) / max(len(P.columns), 1)
        h.append(KeepTogether([
            Paragraph("<b>Error absoluto medio en 6 h (mm), estaciones.</b>", CUERPO),
            tabla(filas, [4 * cm] + [ancho] * len(P.columns))]))

    # --- percentil
    h += [PageBreak(), Paragraph("5. Dónde cae lo observado dentro del super-ensamble", TITULO)]
    if figs.get("percentil"):
        h.append(figura(figs["percentil"], 5,
                        "Percentil de la lluvia observada en cada bloque de 6 h dentro del "
                        "super-ensamble de cada corrida. Azul: llovió menos que casi todos los "
                        "miembros; rojo: más. Blanco: entre p25 y p75. En un ensamble bien "
                        "calibrado, lo observado cae bajo p10 o sobre p90 en cerca de 20 % de los "
                        "casos."))
    else:
        h.append(Paragraph("No hay corridas de ensamble archivadas para este evento.", CUERPO))

    # --- datos y método
    h += [PageBreak(), Paragraph("6. Datos y método", TITULO)]
    corr = R.det_h.groupby(["modelo", "init"]).ngroups if len(R.det_h) else 0
    ens = R.ens_h.groupby(["modelo", "init"]).ngroups if len(R.ens_h) else 0
    h.append(lista([
        f"<b>Observado:</b> {len(K.F.ESTACIONES)} estaciones (VIPNet-DGA, DMC y red INIA), "
        "archivo horario del Visor de Lluvia. Hora que termina en cada marca.",
        "<b>Zonas:</b> " + "; ".join(f"{z}: " + ", ".join(K.NOMBRE_EST[e] for e in K.EST_ZONA[z])
                                     for z in K.ZONAS) + ". Zona = promedio de sus estaciones "
        "(observado) y de las celdas de esas estaciones (pronóstico).",
        f"<b>Deterministas:</b> {corr} corridas de las 00 y 12 UTC desde 4 días antes del inicio "
        "(Open-Meteo, Single Runs API): " + ", ".join(K.NOMBRE_DET[m] for m in K.MODELOS_DET) + ".",
        f"<b>Ensambles:</b> {ens} corridas archivadas por el Visor (GEFS, IFS-ENS, ICON-EPS, "
        "GEPS). Super-ensamble: modelos de la misma ronda de 12 h (al menos 3 de 4), igual peso "
        "por modelo.",
        "<b>Totales:</b> ventana exacta, hora a hora. <b>Bloques de 6 h:</b> solo los enteros "
        "dentro de la ventana. Estaciones con menos de 85 % de horas con dato no entran en los "
        "totales por estación.",
    ]))

    # --- limitaciones
    h.append(Paragraph("7. Limitaciones", TITULO))
    lim = ["Un solo evento no permite conclusiones: las métricas se guardan en "
           "metricas_bloques.csv para juntarlas entre eventos.",
           "Los modelos se comparan en su celda (25 a 50 km), no en el punto de la estación.",
           "Observaciones preliminares, sin control de calidad.",
           "GEM (Canadá) no tiene corridas deterministas pasadas disponibles."]
    if (R.ens_h.get("init_aprox", pd.Series(dtype=bool)) == True).any():  # noqa: E712
        lim.append("Parte de los ensambles son copias antiguas del punto de Valdivia cuya hora "
                   "de inicio se estimó (± 6 h).")
    if faltan:
        lim.append(f"Corridas deterministas no disponibles ({len(faltan)}): " + ", ".join(
            f"{K.NOMBRE_DET[m]} {K.txt_local(t, '%d/%m %H h')}" for m, t in faltan[:12])
            + ("…" if len(faltan) > 12 else "") + ".")
    h.append(lista(lim))

    def pie(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Texto", 12)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(2 * cm, 1.2 * cm, "Informe interno, no publicar")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"{doc_.page}")
        canvas.restoreState()

    doc.build(h, onFirstPage=pie, onLaterPages=pie)
    return salida


def todo(R, carpeta, faltan, manual=False):
    """Figuras + PDF. Devuelve la ruta del PDF."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    figs = {"observado": FG.observado(R, carpeta), "cociente": FG.cociente(R, carpeta),
            "plazo": FG.plazo(R, carpeta), "percentil": FG.percentil(R, carpeta)}
    figs["estaciones"], filas_est = FG.estaciones(R, carpeta)
    return genera(R, carpeta, faltan, figs, filas_est, manual)
