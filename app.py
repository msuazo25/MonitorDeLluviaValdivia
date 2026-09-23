"""
Seguimiento de la lluvia en Valdivia y Corral: observado vs. pronóstico.

Se actualiza sola: los datos se descargan al abrir la página y se guardan en
caché por 1 hora. Clic en una estación del mapa = los gráficos muestran solo
esa estación.

    streamlit run app.py
"""
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import fuentes as F

st.set_page_config(page_title="Visor de Lluvia - Valdivia", page_icon="🌧️", layout="wide")

CUENTA = "@el_lluviologo"
AQUI = Path(__file__).resolve().parent
AZUL, BANDA, ROJO = "#1F5A96", "rgba(157,191,221,.55)", "#B5323C"
NIVELES = [(10, "débil", "#C9DCEE"), (25, "moderada", "#6FA3D2"),
           (np.inf, "fuerte", "#1F4E8C")]
# eje de tiempo corto y sin inclinar (se lee bien en celular)
EJE_T = dict(tickformat="%d/%m<br>%H:%M", nticks=6, tickangle=0)
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}")
ESCALA_MAPA = [(25, "#FFF3B0"), (50, "#B8E186"), (75, "#41B6C4"),
               (100, "#2C7FB8"), (150, "#8856A7"), (np.inf, "#E7298A")]

# ajustes para celular: métricas en 2x2 y botones de estación en varias filas
st.markdown("""<style>
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div { flex-wrap: wrap; }
@media (max-width: 640px) {
  .st-key-metricas [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .5rem 1rem; }
  .st-key-metricas [data-testid="stColumn"] {
    flex: 1 1 calc(50% - 1rem) !important; min-width: calc(50% - 1rem) !important; }
  .st-key-metricas [data-testid="stMetricValue"] { font-size: 1.7rem; }
  h2 { font-size: 1.7rem !important; }
}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ datos
@st.cache_data(ttl=3600, show_spinner="Descargando estaciones…")
def carga_estaciones(hora_clave, usuario_dmc, token_dmc):
    """hora_clave solo sirve para renovar la caché cada hora."""
    series, avisos = {}, []
    for e in F.ESTACIONES:
        try:
            if e["fuente"] == "vipnet":
                series[e["id"]] = F.vipnet(e["codigo"])
            elif e["fuente"] == "dmc":
                if not (usuario_dmc and token_dmc):
                    continue
                series[e["id"]] = F.dmc(e["codigo"], usuario_dmc, token_dmc)
                for av in series[e["id"]].attrs.get("avisos", []):
                    avisos.append(f"{e['nombre']} (parcial): {av}")
        except Exception as ex:                                  # noqa: BLE001
            msg = str(ex)
            for s in (token_dmc, usuario_dmc):                   # nunca mostrar credenciales
                if s:
                    msg = msg.replace(s, "***")
            avisos.append(f"{e['nombre']}: {msg.split('?')[0][:160]}")
    return series, avisos, F.ahora_local()


@st.cache_data(ttl=3600, show_spinner="Descargando pronóstico…")
def carga_ensamble(hora_clave):
    t, pp, raf = F.ensamble()
    return t, pp, raf, F.ahora_local()


def secreto(clave):
    """st.secrets (nube o .streamlit/ del directorio de arranque) y, si no,
    .streamlit/secrets.toml junto a este archivo."""
    try:
        v = st.secrets.get(clave, "")
        if v:
            return v
    except Exception:                                            # noqa: BLE001
        pass
    import tomllib
    ruta = AQUI / ".streamlit" / "secrets.toml"
    try:
        return tomllib.loads(ruta.read_text(encoding="utf-8")).get(clave, "")
    except Exception:                                            # noqa: BLE001
        return ""


@st.cache_resource
def _logo_b64():
    import base64
    return base64.b64encode((AQUI / "recursos" / "logo_lab_blanco.png").read_bytes()).decode()


def logo_lab(ancho=230):
    """Logo del laboratorio que se adapta solo al tema: el logo blanco con
    mix-blend-mode "difference" queda negro sobre fondo claro y blanco sobre
    fondo oscuro, sin esperar a que la app se vuelva a ejecutar."""
    st.markdown(f'<img src="data:image/png;base64,{_logo_b64()}" alt="Laboratorio de '
                f'Dendrocronología y Cambio Global, UACh" style="width:{ancho}px;'
                'max-width:100%;margin-bottom:.8rem;mix-blend-mode:difference">', unsafe_allow_html=True)


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.markdown("### Ajustes")
    d0 = st.date_input("Inicio del evento", datetime(2026, 9, 22))
    h0 = st.time_input("Hora de inicio", datetime(2026, 9, 22, 12, 0).time())
    d1 = st.date_input("Fin del evento", datetime(2026, 9, 25))
    inicio = pd.Timestamp(datetime.combine(d0, h0))
    fin = pd.Timestamp(datetime.combine(d1, datetime.min.time()))
    if st.button("Forzar actualización"):
        st.cache_data.clear()
    st.caption("Los datos se renuevan solos cada hora.")

hora_clave = F.ahora_local().strftime("%Y%m%d%H")
series, avisos, t_obs = carga_estaciones(hora_clave, secreto("DMC_USUARIO"),
                                         secreto("DMC_TOKEN"))
t, PP, RAF, t_pron = carga_ensamble(hora_clave)
ahora = pd.Timestamp(t_obs).floor("h")
est = {e["id"]: e for e in F.ESTACIONES}
activas = [e for e in F.ESTACIONES if e["id"] in series and not series[e["id"]].empty]

# acumulado del evento por estacion (hasta la ultima medicion)
totales = {}
for e in activas:
    o = series[e["id"]]
    ev = o[(o.hora_local > inicio) & (o.hora_local <= fin)]
    totales[e["id"]] = (ev.mm.sum(), ev.hora_local.max() if len(ev) else None)

# pronostico en la ventana del evento
sel_t = (t > inicio - pd.Timedelta(hours=1)) & (t <= fin)
ts, P = t[sel_t], PP[:, sel_t]
med = np.nanmedian(P, 0)
p10, p90 = np.nanpercentile(P, [10, 90], axis=0)
acum = np.nancumsum(np.where(ts > inicio, P, 0.0), axis=1)
a10, a50, a90 = np.nanpercentile(acum, [10, 50, 90], axis=0)
resto = np.nansum(np.where((ts > ahora) & (ts <= fin), P, 0.0), axis=1)
r10, r50, r90 = np.percentile(resto, [10, 50, 90])

# ------------------------------------------------------------------ encabezado
col_tit, col_logo = st.columns([5, 1.3], vertical_alignment="center")
col_tit.markdown("## Visor de Lluvia · Valdivia")
col_tit.markdown("Observado y pronóstico en Valdivia y Corral")
col_tit.caption(f"Actualizado {t_obs:%d/%m %H:%M} (hora de Chile) · evento desde el "
                f"{DIAS[inicio.weekday()].lower()} {inicio:%d/%m %H:%M} · {CUENTA}")
with col_logo:
    logo_lab()

sin_credencial = [e["nombre"] for e in F.ESTACIONES
                  if e["fuente"] == "dmc" and e["id"] not in series]
c = st.container(key="metricas").columns(4)
for col, g in zip(c[:3], F.GRUPOS):
    v = [totales[e["id"]][0] for e in activas if e["grupo"] == g]
    txt = "—" if not v else (f"{min(v):.0f}–{max(v):.0f}" if len(v) > 1
                             else f"{v[0]:.0f}")
    col.metric(f"Observado* {g} (mm)", txt,
               help=None if v else "Estación de la DMC: requiere credenciales.")
c[3].metric(f"Faltan desde las {ahora:%H} h (mm)", f"{r50:.0f}",
            f"rango {r10:.0f}–{r90:.0f}", delta_color="off")

# ------------------------------------------------------------------ mapa
col_mapa, col_graf = st.columns([5, 7], gap="medium")
with col_mapa:
    st.markdown("**Acumulado observado\\*** · elige una estación en los botones bajo el mapa")
    lat = [e["lat"] for e in activas]
    lon = [e["lon"] for e in activas]
    mm = [totales[e["id"]][0] for e in activas]
    colores = [next(c for lim, c in ESCALA_MAPA if v < lim) for v in mm]
    fmap = go.Figure(go.Scattermap(
        lat=lat, lon=lon, mode="markers+text",
        marker=dict(size=16, color=colores),
        text=[f"{e['nombre'].replace(' (DMC)', '')} {v:.0f}" for e, v in zip(activas, mm)],
        textposition="middle right",
        textfont=dict(color="white", size=12),
        customdata=[e["id"] for e in activas],
        hovertemplate="%{text} mm<extra></extra>"))
    fmap.update_layout(
        map=dict(style="white-bg", center=dict(lat=-39.80, lon=-73.32), zoom=8.3,
                 layers=[dict(sourcetype="raster", source=[ESRI], below="traces")]),
        margin=dict(l=0, r=0, t=0, b=0), height=440, showlegend=False,
        clickmode="event+select")
    evento = st.plotly_chart(fmap, on_select="rerun", selection_mode="points",
                             key="mapa", config={"displayModeBar": False})
    st.caption("Colores: < 25 · 25–50 · 50–75 · 75–100 · 100–150 · > 150 mm. "
               "Imagen: Esri World Imagery.")

    # seleccion: botones (funcionan en celular) o clic en el mapa
    opciones = {"Grupos": None} | {e["nombre"].replace(" (DMC)", ""): e["id"]
                                   for e in activas}
    boton = st.pills("Ver", list(opciones), default="Grupos", key="pick",
                     label_visibility="collapsed")
    if sin_credencial:
        st.caption(f"Sin datos de {', '.join(sin_credencial)}: la DMC exige usuario "
                   "y token (registro gratuito); se activan al configurarlos.")

elegida = opciones.get(boton) if boton else None
try:
    pts = evento.selection.points
    if pts:
        cd = pts[0].get("customdata")
        elegida = cd[0] if isinstance(cd, list) else cd
except Exception:                                                # noqa: BLE001
    pass

# ------------------------------------------------------------------ graficos
with col_graf:
    if elegida:
        st.markdown(f"**{est[elegida]['nombre']}** · "
                    f"{totales[elegida][0]:.0f} mm desde el inicio. "
                    "Elige «Grupos» para volver a la vista por grupo.")
        curvas = [(est[elegida]["nombre"], [series[elegida]],
                   F.GRUPOS.get(est[elegida]["grupo"], "#111"))]
    else:
        curvas = []
        for g, colg in F.GRUPOS.items():
            miembros = [series[e["id"]] for e in activas if e["grupo"] == g]
            if miembros:
                curvas.append((f"{g} ({len(miembros)} est.)", miembros, colg))

    # (a) por hora
    fa = go.Figure()
    fa.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[p90, p10[::-1]],
                            fill="toself", fillcolor=BANDA, line=dict(width=0),
                            name="pronóstico p10–p90", hoverinfo="skip"))
    fa.add_trace(go.Bar(x=ts, y=med, marker_color=AZUL, name="pronóstico mediana",
                        opacity=.85))
    for nombre, miembros, colg in curvas:
        tab = pd.concat([F.horaria(o) for o in miembros], axis=1)
        tab = tab[(tab.index > inicio) & (tab.index <= ahora)]
        fa.add_trace(go.Scatter(x=tab.index, y=tab.mean(axis=1), mode="lines",
                                line=dict(color=colg, width=2.4),
                                name=f"observado* {nombre}"))
    fa.add_vline(x=ahora, line_color=ROJO, line_width=1.5)
    fa.update_layout(title="Precipitación por hora (mm)", height=300,
                     margin=dict(l=10, r=10, t=40, b=10), bargap=.15,
                     legend=dict(orientation="h", y=-.2), hovermode="x unified")
    fa.update_xaxes(**EJE_T)
    st.plotly_chart(fa, config={"displayModeBar": False})

    # (b) acumulado
    fb = go.Figure()
    fb.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[a90, a10[::-1]],
                            fill="toself", fillcolor=BANDA, line=dict(width=0),
                            name="pronóstico p10–p90", hoverinfo="skip"))
    fb.add_trace(go.Scatter(x=ts, y=a50, line=dict(color=AZUL, width=3),
                            name="pronóstico mediana"))
    for nombre, miembros, colg in curvas:
        for o in miembros:
            ev = o[(o.hora_local > inicio) & (o.hora_local <= fin)]
            fb.add_trace(go.Scatter(x=[inicio, *ev.hora_local], y=[0, *ev.mm.cumsum()],
                                    line=dict(color=colg, width=1.6),
                                    name=f"observado* {nombre}", showlegend=False))
    fb.add_vline(x=ahora, line_color=ROJO, line_width=1.5)
    fb.update_layout(title=dict(text="Acumulado desde el inicio (mm)",
                                subtitle=dict(text=f"pronóstico total {a50[-1]:.0f} mm "
                                                   f"({a10[-1]:.0f}–{a90[-1]:.0f})")),
                     height=290, margin=dict(l=10, r=10, t=60, b=10),
                     showlegend=False, hovermode="x unified")
    fb.update_xaxes(**EJE_T)
    st.plotly_chart(fb, config={"displayModeBar": False})

# ------------------------------------------------------------------ tarjetas 6 h
st.markdown("**Lluvia esperada cada 6 horas** (mediana del pronóstico; rango p10–p90)")
bloques, b0 = [], inicio.floor("6h")
while b0 < fin:
    b1 = b0 + pd.Timedelta(hours=6)
    m = (t > b0) & (t <= b1)
    q = np.percentile(np.nansum(PP[:, m], axis=1), [10, 50, 90])
    rf = np.percentile(np.nanmax(RAF[:, m], axis=1), 50) if RAF is not None else None
    bloques.append((b0, b1, q, rf))
    b0 = b1
html = ['<div style="display:flex;flex-wrap:wrap;gap:8px">']
for b0, b1, (q10, q50, q90), rf in bloques:
    pasado, actual = b1 <= ahora, b0 <= ahora < b1
    col = next(c for lim, _, c in NIVELES if q50 < lim)
    borde = f"2px solid {ROJO}" if actual else "1px solid #D6D2CA"
    obs = ""
    if pasado:
        partes = []
        for g, colg in F.GRUPOS.items():
            v = [series[e["id"]][(series[e["id"]].hora_local > b0) &
                                 (series[e["id"]].hora_local <= b1)].mm.sum()
                 for e in activas if e["grupo"] == g]
            if v:
                partes.append(f'<span style="color:{colg}">{g} '
                              f'{min(v):.0f}{"–%.0f" % max(v) if len(v) > 1 else ""}</span>')
        obs = "<br>".join(partes)
    fin_h = "24" if b1.hour == 0 else f"{b1:%H}"
    html.append(
        f'<div style="flex:1 1 92px;max-width:130px;border:{borde};border-radius:10px;'
        f'padding:8px 6px;text-align:center;opacity:{.55 if pasado else 1};'
        f'font-family:sans-serif">'
        f'<div style="font-weight:700">{DIAS[b0.weekday()]} {b0.day}</div>'
        f'<div style="font-size:12px;color:#666">{b0:%H}–{fin_h} h</div>'
        f'<div style="font-size:26px;font-weight:800;color:{col}">{q50:.0f}</div>'
        f'<div style="font-size:11px;color:#666">mm · {q10:.0f}–{q90:.0f}</div>'
        f'<div style="font-size:11px;margin-top:4px;font-weight:700">{obs}</div>'
        + (f'<div style="font-size:11px;color:#5B4B8A">ráfaga {rf:.0f} km/h</div>'
           if rf is not None and not pasado else "")
        + ("<div style='font-size:10px;color:white;background:%s;border-radius:4px;"
           "margin-top:4px'>AHORA</div>" % ROJO if actual else "")
        + "</div>")
html.append("</div>")
st.markdown("".join(html), unsafe_allow_html=True)

# ------------------------------------------------------------------ pie
faltan = [e["nombre"] for e in F.ESTACIONES if e not in activas]
st.divider()
st.caption(
    f"**Pronóstico:** super-ensamble de {PP.shape[0]} miembros (GEFS, IFS-ENS, ICON-EPS "
    f"y GEPS, vía Open-Meteo), consultado el {t_pron:%d/%m %H:%M}. "
    "Intensidad descriptiva, no equivale a alertas oficiales: seguir siempre a "
    "SENAPRED, DMC y la Municipalidad.  \n"
    "**\\* Observado:** red VIPNet (DGA/MOP)"
    + (" y DMC" if any(e["fuente"] == "dmc" for e in activas) else "")
    + ". Datos preliminares, pendientes de control de calidad. Grupos: "
    + "; ".join(f"{g} ({', '.join(e['nombre'] for e in F.ESTACIONES if e['grupo'] == g)})"
                for g in F.GRUPOS) + "."
    + (f"  \nSin datos en esta actualización: {', '.join(faltan)}." if faltan else ""))
if avisos:
    with st.expander("Avisos de descarga"):
        st.write("\n".join(f"- {a}" for a in avisos))

st.divider()
col_cred, col_logo2 = st.columns([4, 1.3], vertical_alignment="center")
col_cred.markdown(
    "Implementado por **Manuel Suazo** · Laboratorio de Dendrocronología y Cambio "
    "Global, Universidad Austral de Chile  \n"
    "[manu.suazo@gmail.com](mailto:manu.suazo@gmail.com) · Instagram: "
    f"[{CUENTA}](https://www.instagram.com/{CUENTA.lstrip('@')}/)")
with col_logo2:
    logo_lab()
