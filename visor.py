"""
Página principal del visor: lluvia observada en Valdivia y Corral frente al
pronóstico. Se actualiza sola: los datos se descargan al abrir la página y se
guardan en caché por 1 hora. Se lanza desde app.py (navegación).
"""
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import fuentes as F
import graficos as G
import tarjeta as T

CUENTA = "@el_lluviologo"
AQUI = Path(__file__).resolve().parent
AZUL, BANDA, ROJO = "#1F5A96", "rgba(157,191,221,.55)", "#B5323C"
NIVELES = [(10, "débil", "#C9DCEE"), (25, "moderada", "#6FA3D2"),
           (np.inf, "fuerte", "#1F4E8C")]
# eje de tiempo corto y sin inclinar (se lee bien en celular)
EJE_T = dict(tickformat="%d/%m<br>%H:%M", nticks=6, tickangle=0)
# modos del pronóstico (ver metodologia.py)
MODOS = {"super": "Super-ensamble", "modelo": "Por modelo"}
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
ESRI = ("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        "MapServer/tile/{z}/{y}/{x}")
# escala de un solo tono (azules) para no confundirse con los colores de zona
ESCALA_MAPA = [(25, "#DEEBF7"), (50, "#9ECAE1"), (75, "#6BAED6"),
               (100, "#3182BD"), (150, "#08519C"), (np.inf, "#08306B")]



GRIS_BANDA = "rgba(150,150,150,.25)"
# selector de zona y observado en la vista "por modelo" (más vivo que F.GRUPOS)
ZONAS = {"costa": ":material/waves:", "ciudad": ":material/location_city:",
         "interior": ":material/landscape:"}
VIVO = {"costa": "#00B5B8", "ciudad": "#FF7A00", "interior": "#9446F0"}


def corto(nombre):
    """Nombre sin la red entre paréntesis, para el mapa y los botones."""
    return nombre.split(" (")[0]


def rgba(hexcolor, alfa):
    h = hexcolor.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alfa})"


def barra(boton):
    """Barra de Plotly con solo el botón para volver al zoom inicial (siempre
    visible: en el celular no hay "pasar el mouse")."""
    return {"displayModeBar": True, "displaylogo": False, "modeBarButtons": [[boton]]}


# ajustes para celular: métricas en 2x2 y botones de estación en varias filas
st.markdown("""<style>
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div { flex-wrap: wrap; }
@media (max-width: 640px) {
  .st-key-metricas [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .5rem 1rem; }
  .st-key-metricas [data-testid="stColumn"] {
    flex: 1 1 100% !important; min-width: 100% !important; }
  .st-key-metricas [data-testid="stMetricValue"] { font-size: 1.6rem; }
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
            elif e["fuente"] == "inia":
                series[e["id"]] = F.inia(e["codigo"], e["nombre_inia"])
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
def carga_ensamble(hora_clave, estaciones):
    """estaciones (ids de F.ESTACIONES) forma parte de la clave de la caché: si
    cambia la lista, un servidor ya andando no sirve lo guardado con la lista
    antigua (PP tiene una fila por estación)."""
    t, pp, raf, mod_pp, mod_raf = F.ensamble()
    return t, pp, raf, mod_pp, mod_raf, F.ahora_local()


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
HORIZONTES = [12, 24, 36, 72]      # h; 72 = lo que cubren VIPNet (atrás) y el ensamble

with st.sidebar:
    st.markdown("### Ajustes")
    st.markdown("**Horizontes rápidos**")
    # por defecto: 72 h hacia atrás y 72 h hacia adelante desde la hora actual
    atras = st.segmented_control("Hacia atrás (últimas)", HORIZONTES, key="atras",
                                 default=72, format_func=lambda h: f"{h} h")
    adelante = st.segmented_control("Hacia adelante (próximas)", HORIZONTES, key="adelante",
                                    default=72, format_func=lambda h: f"{h} h")
    st.caption("Sin horizonte elegido se usan las fechas de abajo. "
               "Toca de nuevo un botón para quitarlo.")
    # rango de fechas: parte de la última hora completa (p. ej. 9:58 -> 9:00)
    ya = pd.Timestamp(F.ahora_local()).floor("h")
    st.markdown("**Rango de fechas**")
    d0 = st.date_input("Día de inicio", ya.date(), disabled=bool(atras))
    h0 = st.time_input("Hora de inicio", ya.time(), disabled=bool(atras))
    fin0 = ya + pd.Timedelta(hours=72)
    d1 = st.date_input("Día de fin", fin0.date(), disabled=bool(adelante))
    h1 = st.time_input("Hora de fin", fin0.time(), disabled=bool(adelante))
    inicio = (ya - pd.Timedelta(hours=atras) if atras
              else pd.Timestamp(datetime.combine(d0, h0)))
    fin = (ya + pd.Timedelta(hours=adelante) if adelante
           else pd.Timestamp(datetime.combine(d1, h1)))
    if fin <= inicio:
        st.error("El fin del período debe ser posterior al inicio.")
        st.stop()
    st.caption(f"Período: {DIAS[inicio.weekday()].lower()} {inicio:%d/%m %H:%M} → "
               f"{DIAS[fin.weekday()].lower()} {fin:%d/%m %H:%M}")
    if st.button("Forzar actualización"):
        st.cache_data.clear()
    st.caption("Los datos se renuevan solos cada hora.")

hora_clave = F.ahora_local().strftime("%Y%m%d%H")
series, avisos, t_obs = carga_estaciones(hora_clave, secreto("DMC_USUARIO"),
                                         secreto("DMC_TOKEN"))
IDS = tuple(e["id"] for e in F.ESTACIONES)
t, PP, RAF, MP, MR, t_pron = carga_ensamble(hora_clave, IDS)
if PP.ndim != 3 or PP.shape[0] != len(IDS):     # caché de una versión anterior
    carga_ensamble.clear()
    t, PP, RAF, MP, MR, t_pron = carga_ensamble(hora_clave, IDS)
# el selector se dibuja más abajo, pero su valor hace falta ya para las cifras
if st.session_state.get("modo") not in MODOS:          # sin elegir (o valor antiguo)
    st.session_state["modo"] = "super"
modo = st.session_state["modo"]
# super-ensamble: cada modelo pesa lo mismo (ver metodologia.py)
W = F.pesos(MP, "igual")
WR = F.pesos(MR, "igual") if RAF is not None else None
ahora = pd.Timestamp(t_obs).floor("h")
est = {e["id"]: e for e in F.ESTACIONES}
activas = [e for e in F.ESTACIONES if e["id"] in series and not series[e["id"]].empty]
FILA = {e["id"]: k for k, e in enumerate(F.ESTACIONES)}      # fila de PP y RAF


def pronostico(ids):
    """Pronóstico (miembros x horas) promediado, miembro a miembro, sobre la
    celda de cada estación de ids; con una estación, su propia celda."""
    k = [FILA[i] for i in ids]
    return PP[k].mean(axis=0), (RAF[k].mean(axis=0) if RAF is not None else None)


# acumulado del evento por estacion (hasta la ultima medicion)
totales = {}
for e in activas:
    o = series[e["id"]]
    ev = o[(o.hora_local > inicio) & (o.hora_local <= fin)]
    totales[e["id"]] = (ev.mm.sum(), ev.hora_local.max() if len(ev) else None)

# ventana del evento y lo que falta desde ahora, por grupo
sel_t = (t > inicio - pd.Timedelta(hours=1)) & (t <= fin)
ts = t[sel_t]
falta_t = (ts > ahora) & (ts <= fin)
ids_grupo = {g: [e["id"] for e in F.ESTACIONES if e["grupo"] == g] for g in F.GRUPOS}
resto_grupo = {g: F.cuantiles(np.nansum(np.where(falta_t, pronostico(ids)[0][:, sel_t], 0.0),
                                        axis=1), W, [10, 50, 90])
               for g, ids in ids_grupo.items()}

# ------------------------------------------------------------------ encabezado
col_tit, col_logo = st.columns([5, 1.3], vertical_alignment="center")
col_tit.markdown("## Visor de Lluvia · Valdivia")
col_tit.markdown("Observado y pronóstico en Valdivia y Corral")
col_tit.caption(f"Actualizado {t_obs:%d/%m %H:%M} (hora de Chile) · período "
                f"{DIAS[inicio.weekday()].lower()} {inicio:%d/%m %H:%M} → "
                f"{DIAS[fin.weekday()].lower()} {fin:%d/%m %H:%M} · {CUENTA}")
with col_logo:
    logo_lab()

sin_credencial = [e["nombre"] for e in F.ESTACIONES
                  if e["fuente"] == "dmc" and e["id"] not in series]
# textos del período: "las últimas 72 h" / "para las próximas 72 h"
h_atras = int(round((ahora - inicio) / pd.Timedelta(hours=1)))
h_adelante = int(round((fin - ahora) / pd.Timedelta(hours=1)))
TXT_ATRAS = (f"las últimas {h_atras} h" if h_atras > 0
             else f"desde el {inicio:%d/%m %H:%M}")
TXT_ADELANTE = (f"para las próximas {h_adelante} h" if h_adelante > 0
                else "(el período ya terminó)")
c = st.container(key="metricas").columns(3)
for col, g in zip(c, F.GRUPOS):
    v = [totales[e["id"]][0] for e in activas if e["grupo"] == g]
    txt = "—" if not v else (f"{min(v):.0f}–{max(v):.0f}" if len(v) > 1
                             else f"{v[0]:.0f}")
    q10, q50, q90 = resto_grupo[g]
    col.metric(f"{g.capitalize()} · observado* {TXT_ATRAS} (mm)", txt,
               f"Pronóstico de {q50:.0f} mm ({q10:.0f}–{q90:.0f}) {TXT_ADELANTE}",
               delta_color="off", delta_arrow="off",
               help="Observado: rango entre las estaciones del grupo. Pronóstico: desde "
                    "ahora hasta el fin del período, mediana (p10–p90)."
                    + ("" if v else " Estación de la DMC: requiere credenciales."))

# ------------------------------------------------------------------ zona
st.markdown("**Zona**")
zona = st.segmented_control(
    "Zona", list(F.GRUPOS), key="zona", default="ciudad", required=True,
    format_func=lambda g: f"{ZONAS[g]} {g.capitalize()}", label_visibility="collapsed",
    width="stretch")
# cada botón elegido con el color de su grupo
st.markdown("<style>.st-key-zona button{min-height:2.8rem;font-weight:600}" + "".join(
    f".st-key-zona button:nth-of-type({k + 1}){{color:{colg}}}"
    f".st-key-zona button:nth-of-type({k + 1})[aria-checked='true']"
    f"{{background:{colg}!important;border-color:{colg}!important}}"
    f".st-key-zona button:nth-of-type({k + 1})[aria-checked='true'] *{{color:white}}"
    for k, colg in enumerate(F.GRUPOS.values())) + "</style>", unsafe_allow_html=True)
colz = F.GRUPOS[zona]

# ------------------------------------------------------------------ mapa
col_mapa, col_graf = st.columns([5, 7], gap="medium")
with col_mapa:
    st.markdown("**Acumulado observado\\*** · toca una estación para verla sola")
    lat = [e["lat"] for e in activas]
    lon = [e["lon"] for e in activas]
    mm = [totales[e["id"]][0] for e in activas]
    colores = [next(c for lim, c in ESCALA_MAPA if v < lim) for v in mm]
    # anillo del color de la zona elegida y borde blanco para todas
    fmap = go.Figure(go.Scattermap(
        lat=[e["lat"] for e in activas if e["grupo"] == zona],
        lon=[e["lon"] for e in activas if e["grupo"] == zona], mode="markers",
        marker=dict(size=27, color=colz), hoverinfo="skip"))
    fmap.add_trace(go.Scattermap(lat=lat, lon=lon, mode="markers",
                                 marker=dict(size=20, color="white"), hoverinfo="skip"))
    textos = [f"{corto(e['nombre'])} {v:.0f}" for e, v in zip(activas, mm)]
    fmap.add_trace(go.Scattermap(                  # traza 2: la que se toca (ver abajo)
        lat=lat, lon=lon, mode="markers", marker=dict(size=16, color=colores),
        text=textos, customdata=[e["id"] for e in activas],
        hovertemplate="%{text} mm<extra></extra>"))
    # nombres: a la derecha, salvo que F.ESTACIONES diga otra posición porque
    # chocan con otra estación o se salen del mapa (Scattermap no acepta una
    # posición por punto: una traza por posición)
    # (el mapa oculta las etiquetas que se tapan entre sí)
    for lado in sorted({e.get("etiqueta", "middle right") for e in activas}):
        k = [i for i, e in enumerate(activas) if e.get("etiqueta", "middle right") == lado]
        # y un pequeño corrimiento (grados) hacia el lado del texto
        dlat, dlon = {"middle right": (0, .007), "middle left": (0, -.007),
                      "bottom center": (-.008, 0)}.get(lado, (0, 0))
        fmap.add_trace(go.Scattermap(
            lat=[lat[i] + dlat for i in k], lon=[lon[i] + dlon for i in k], mode="markers+text",
            # marcador invisible: solo "text" no se dibuja en Scattermap, y su tamaño
            # separa el texto del círculo (Plotly lo aleja según el marcador)
            marker=dict(size=42, opacity=0),
            text=[textos[i] for i in k], textposition=lado,
            textfont=dict(color="white", size=12), hoverinfo="skip"))
    fmap.update_layout(
        map=dict(style="white-bg", center=dict(lat=-39.80, lon=-73.32), zoom=8.3,
                 layers=[dict(sourcetype="raster", source=[ESRI], below="traces")]),
        margin=dict(l=0, r=0, t=0, b=0), height=440, showlegend=False,
        modebar=dict(bgcolor="rgba(255,255,255,.9)", color="#333", activecolor="#000"),
        clickmode="event+select")
    evento = st.plotly_chart(fmap, on_select="rerun", selection_mode="points",
                             key="mapa", config=barra("resetViewMap"))
    st.caption("Azul más oscuro = más lluvia: < 25 · 25–50 · 50–75 · 75–100 · "
               "100–150 · > 150 mm. Anillo: estaciones de la zona elegida. "
               "Imagen: Esri World Imagery.")

    # seleccion: botones (funcionan en celular) o clic en el mapa
    toda = f"Toda la zona {zona}"
    opciones = {toda: None} | {corto(e["nombre"]): e["id"]
                               for e in activas if e["grupo"] == zona}
    boton = st.pills("Ver", list(opciones), default=toda, key=f"pick_{zona}",
                     label_visibility="collapsed")
    if sin_credencial:
        st.caption(f"Sin datos de {', '.join(sin_credencial)}: la DMC exige usuario "
                   "y token (registro gratuito); se activan al configurarlos.")

elegida = opciones.get(boton) if boton else None
try:
    pts = evento.selection.points
    if pts and pts[0].get("curve_number", 2) == 2:
        cd = pts[0].get("customdata")
        elegida = cd[0] if isinstance(cd, list) else cd
except Exception:                                                # noqa: BLE001
    pass

# pronóstico de la zona (promedio de las celdas de sus estaciones) o de la estación
if elegida:
    Pz, Rz = pronostico([elegida])
    donde = f"{est[elegida]['nombre']} (celda de la estación)"
else:
    Pz, Rz = pronostico(ids_grupo[zona])
    n_z = len(ids_grupo[zona])
    donde = f"zona {zona} (" + (f"celdas de {n_z} estaciones)" if n_z > 1 else "celda de su estación)")
P = Pz[:, sel_t]
p10, med, p90 = F.cuantiles(P, W, [10, 50, 90])
acum = np.nancumsum(np.where(ts > inicio, P, 0.0), axis=1)
a10, a50, a90 = F.cuantiles(acum, W, [10, 50, 90])
r10, r50, r90 = F.cuantiles(np.nansum(np.where(falta_t, P, 0.0), axis=1), W, [10, 50, 90])

# mismo resumen para cada modelo por separado
por_modelo = []
for m, nombre_m in F.MODELOS.items():
    fila = MP == m
    if not fila.any():
        continue
    wm = np.full(fila.sum(), 1.0 / fila.sum())
    por_modelo.append(dict(
        id=m, nombre=nombre_m, color=F.COLOR_MODELO[m], n=int(fila.sum()),
        hora=F.cuantiles(P[fila], wm, [10, 50, 90]),
        acum=F.cuantiles(acum[fila], wm, [10, 50, 90])))

# mismo eje y en las tres zonas, para compararlas al cambiar de una a otra:
# el techo es el máximo de lo que se dibujaría en cualquiera de ellas (en este
# modo de pronóstico). Una estación sola usa su propio techo.
def techos(P_v, ids_obs):
    """(máx. por hora, máx. acumulado) del pronóstico P_v (miembros x horas de
    la ventana) y de lo observado en ids_obs."""
    h = [F.cuantiles(P_v, W, [90])[0]]
    fin_ac = np.nansum(np.where(ts > inicio, P_v, 0.0), axis=1)   # el acumulado
    a = [F.cuantiles(fin_ac, W, [90])]                           # crece: basta el final
    if modo == "modelo":
        for m in F.MODELOS:
            fila = MP == m
            if fila.any():
                wm = np.full(fila.sum(), 1.0 / fila.sum())
                h.append(F.cuantiles(P_v[fila], wm, [50])[0])
                a.append(F.cuantiles(fin_ac[fila], wm, [90]))
    hs = [F.horaria(series[i]) for i in ids_obs if i in totales]
    hs = [x[(x.index > inicio) & (x.index <= ahora)] for x in hs]
    if hs:
        h.append(pd.concat(hs, axis=1).mean(axis=1).values)   # por hora: la media
        a += [totales[i][0] for i in ids_obs if i in totales]  # acumulado: cada una
    return (max(np.nanmax(np.r_[x]) if np.size(x) else 0 for x in h),
            max(np.nanmax(np.r_[x]) for x in a))


todos = ([techos(PP[FILA[elegida]][:, sel_t], [elegida])] if elegida else
         [techos(pronostico(ids)[0][:, sel_t], ids) for ids in ids_grupo.values()])
TECHO_H = 1.08 * max(x[0] for x in todos)
TECHO_A = 1.08 * max(x[1] for x in todos)

# observado: más grueso y vivo sobre los modelos en pastel
ANCHO_OBS = 3.6 if modo == "modelo" else 2.4
COLOR_OBS = VIVO if modo == "modelo" else F.GRUPOS

# ------------------------------------------------------------------ descargas
quien = (est[elegida]["nombre"] if elegida
         else f"zona {zona} (media de estaciones)")
sub_desc = (f"Valdivia y Corral · {quien} · {inicio:%d/%m %H:%M} → {fin:%d/%m %H:%M} · "
            f"actualizado {t_obs:%d/%m %H:%M} (hora de Chile)")
TXT_PESO = "igual peso por modelo"
pie_desc = (f"* Observado: VIPNet (DGA/MOP), DMC y Red Agrometeorológica INIA, datos "
            f"preliminares.\nPronóstico: "
            f"{PP.shape[1]} miembros de GEFS, IFS-ENS, ICON-EPS y GEPS (Open-Meteo) en {donde}, "
            f"super-ensamble con {TXT_PESO}; consultado el {t_pron:%d/%m %H:%M}.\n"
            f"Visor de Lluvia · Valdivia — Manuel Suazo, Laboratorio de Dendrocronología "
            f"y Cambio Global, UACh · {CUENTA}")


def descargas(nombre, funcion, *args):
    """Botones PNG (600 dpi) y PDF; el archivo se dibuja recién al apretar."""
    base = f"visor_lluvia_valdivia_{nombre}_{t_obs:%Y%m%d_%H%M}"
    fila = st.container(horizontal=True, gap="small")
    for fmt, mime in (("png", "image/png"), ("pdf", "application/pdf")):
        fila.download_button(
            f"{fmt.upper()}" + (" 600 dpi" if fmt == "png" else ""),
            data=lambda fmt=fmt: funcion(fmt, *args), file_name=f"{base}.{fmt}",
            mime=mime, icon=":material/download:", on_click="ignore",
            key=f"dl_{nombre}_{fmt}")


# ------------------------------------------------------------------ graficos
with col_graf:
    fila_modo = st.container(horizontal=True, vertical_alignment="bottom", gap="medium")
    fila_modo.segmented_control(
        "Pronóstico", list(MODOS), key="modo", format_func=MODOS.get,
        help="Super-ensamble: los 4 modelos combinados, cada uno con el mismo peso. "
             "Por modelo: cada modelo por separado.")
    fila_modo.page_link("metodologia.py", label="¿Cómo se calcula?",
                        icon=":material/help:")
    if elegida:
        st.markdown(f"**{est[elegida]['nombre']}** · "
                    f"{totales[elegida][0]:.0f} mm desde el inicio. Pronóstico en la "
                    f"celda de la estación. Elige «{toda}» para volver a la zona.")
        grupo_c = est[elegida]["grupo"]
        curvas = [(est[elegida]["nombre"], [series[elegida]], grupo_c)]
    else:
        miembros = [series[e["id"]] for e in activas if e["grupo"] == zona]
        n_est = len(ids_grupo[zona])
        st.markdown(f"**Zona {zona}** · pronóstico promediado sobre la celda de "
                    f"{'cada una de sus ' + str(n_est) + ' estaciones' if n_est > 1 else 'su estación'}.")
        curvas = [(f"{zona} ({len(miembros)} est.)", miembros, zona)] if miembros else []

    # (a) por hora
    obs_h, obs_a = [], []
    fa = go.Figure()
    if modo == "modelo":
        fa.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[p90, p10[::-1]],
                                fill="toself", fillcolor=GRIS_BANDA, line=dict(width=0),
                                name="super-ensamble p10–p90", hoverinfo="skip"))
        for d in por_modelo:
            fa.add_trace(go.Scatter(x=ts, y=d["hora"][1], mode="lines",
                                    line=dict(color=d["color"], width=2.2),
                                    name=f"{d['nombre']} mediana"))
    else:
        fa.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[p90, p10[::-1]],
                                fill="toself", fillcolor=BANDA, line=dict(width=0),
                                name="pronóstico p10–p90", hoverinfo="skip"))
        fa.add_trace(go.Bar(x=ts, y=med, marker_color=AZUL, name="pronóstico mediana",
                            opacity=.85))
    for nombre, miembros, g in curvas:
        tab = pd.concat([F.horaria(o) for o in miembros], axis=1)
        tab = tab[(tab.index > inicio) & (tab.index <= ahora)]
        obs_h.append((nombre, tab.index, tab.mean(axis=1).values, COLOR_OBS[g]))
        fa.add_trace(go.Scatter(x=tab.index, y=tab.mean(axis=1), mode="lines",
                                line=dict(color=COLOR_OBS[g], width=ANCHO_OBS),
                                name=f"observado* {nombre}"))
    fa.add_vline(x=ahora, line_color=ROJO, line_width=1.5)
    fa.update_layout(title=f"Precipitación por hora (mm) · {elegida and est[elegida]['nombre'] or zona}",
                     height=400 if modo == "modelo" else 360,
                     margin=dict(l=10, r=10, t=40, b=10), bargap=.15,
                     legend=dict(orientation="h", y=-.36 if modo == "modelo" else -.3,
                                 yanchor="top"), hovermode="x unified")
    fa.update_xaxes(**EJE_T)
    fa.update_yaxes(range=[0, TECHO_H])
    st.plotly_chart(fa, config=barra("resetScale2d"))
    descargas("por_hora", G.por_hora, ts, p10, p90, med, obs_h, ahora,
              sub_desc, pie_desc,
              [(d["nombre"], ts, *d["hora"], d["color"]) for d in por_modelo]
              if modo == "modelo" else None, ANCHO_OBS / 2, TECHO_H)

    # (b) acumulado
    fb = go.Figure()
    if modo == "modelo":
        for d in por_modelo:
            q10, q50, q90 = d["acum"]
            fb.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[q90, q10[::-1]],
                                    fill="toself", fillcolor=rgba(d["color"], .22),
                                    line=dict(width=0), hoverinfo="skip", showlegend=False))
            fb.add_trace(go.Scatter(x=ts, y=q50, name=d["nombre"],
                                    line=dict(color=d["color"], width=2.4)))
    else:
        fb.add_trace(go.Scatter(x=np.r_[ts, ts[::-1]], y=np.r_[a90, a10[::-1]],
                                fill="toself", fillcolor=BANDA, line=dict(width=0),
                                name="pronóstico p10–p90", hoverinfo="skip"))
        fb.add_trace(go.Scatter(x=ts, y=a50, line=dict(color=AZUL, width=3),
                                name="pronóstico mediana"))
    for nombre, miembros, g in curvas:
        for o in miembros:
            ev = o[(o.hora_local > inicio) & (o.hora_local <= fin)]
            obs_a.append((nombre, [inicio, *ev.hora_local], [0, *ev.mm.cumsum()], COLOR_OBS[g]))
            fb.add_trace(go.Scatter(x=[inicio, *ev.hora_local], y=[0, *ev.mm.cumsum()],
                                    line=dict(color=COLOR_OBS[g], width=ANCHO_OBS * .75),
                                    name=f"observado* {nombre}", showlegend=False))
    fb.add_vline(x=ahora, line_color=ROJO, line_width=1.5)
    fb.update_layout(title=dict(text="Acumulado desde el inicio (mm)",
                                subtitle=dict(text=f"pronóstico total {a50[-1]:.0f} mm "
                                                   f"({a10[-1]:.0f}–{a90[-1]:.0f}), "
                                                   "super-ensamble")),
                     height=340 if modo == "modelo" else 290,
                     margin=dict(l=10, r=10, t=60, b=10),
                     showlegend=modo == "modelo", hovermode="x unified",
                     legend=dict(orientation="h", y=-.3, yanchor="top"))
    fb.update_xaxes(**EJE_T)
    fb.update_yaxes(range=[0, TECHO_A])
    st.plotly_chart(fb, config=barra("resetScale2d"))
    descargas("acumulado", G.acumulado, ts, a10, a50, a90, obs_a, ahora,
              f"{sub_desc} · pronóstico total {a50[-1]:.0f} mm "
              f"({a10[-1]:.0f}–{a90[-1]:.0f})", pie_desc,
              [(d["nombre"], ts, *d["acum"], d["color"]) for d in por_modelo]
              if modo == "modelo" else None, ANCHO_OBS / 2, TECHO_A)

    if modo == "modelo":
        st.markdown(f"**Total pronosticado en el período, por modelo** · {elegida and est[elegida]['nombre'] or 'zona ' + zona}")
        st.dataframe(pd.DataFrame([{
            "Modelo": d["nombre"], "Miembros": d["n"],
            "Mediana (mm)": round(float(d["acum"][1][-1])),
            "p10–p90 (mm)": f"{d['acum'][0][-1]:.0f}–{d['acum'][2][-1]:.0f}",
            "Peso en el super-ensamble": f"{100 / len(por_modelo):.0f}%",
        } for d in por_modelo]), hide_index=True, width="stretch")

# ------------------------------------------------------------------ tarjetas 6 h
lugar = est[elegida]["nombre"] if elegida else f"zona {zona}"
st.markdown(f"**Lluvia esperada cada 6 horas · {lugar}** (mediana del super-ensamble con "
            f"{TXT_PESO}; rango p10–p90)")
ids_obs = [elegida] if elegida else [e["id"] for e in activas if e["grupo"] == zona]
ids_obs = [i for i in ids_obs if i in totales]
bloques, b0 = [], inicio.floor("6h")
while b0 < fin:
    b1 = b0 + pd.Timedelta(hours=6)
    m = (t > b0) & (t <= b1)
    q = F.cuantiles(np.nansum(Pz[:, m], axis=1), W, [10, 50, 90])
    rf = (F.cuantiles(np.nanmax(Rz[:, m], axis=1), WR, [50])[0]
          if Rz is not None else None)
    bloques.append((b0, b1, q, rf))
    b0 = b1
html = ['<div style="display:flex;flex-wrap:wrap;gap:8px">']
for b0, b1, (q10, q50, q90), rf in bloques:
    pasado, actual = b1 <= ahora, b0 <= ahora < b1
    col = next(c for lim, _, c in NIVELES if q50 < lim)
    borde = f"2px solid {ROJO}" if actual else "1px solid #D6D2CA"
    obs = ""
    if pasado and ids_obs:
        v = [series[i][(series[i].hora_local > b0) & (series[i].hora_local <= b1)].mm.sum()
             for i in ids_obs]
        obs = (f'<span style="color:{colz}">obs. {min(v):.0f}'
               f'{"–%.0f" % max(v) if len(v) > 1 else ""}</span>')
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

# ------------------------------------------------------------------ compartir
datos_tarjeta = dict(
    t_obs=pd.Timestamp(t_obs), inicio=inicio, fin=fin, ahora=ahora,
    grupos=[(g, colg,
             min(v) if (v := [totales[e["id"]][0] for e in activas if e["grupo"] == g]) else None,
             max(v) if v else None, len(v))
            for g, colg in F.GRUPOS.items()],
    lugar=lugar, txt_atras=TXT_ATRAS, txt_adelante=TXT_ADELANTE, resto=(r10, r50, r90), ts=ts, a10=a10, a50=a50, a90=a90,
    obs=[([inicio, *ev.hora_local], [0, *ev.mm.cumsum()], F.GRUPOS[est[i]["grupo"]])
         for i in ids_obs
         for ev in [series[i][(series[i].hora_local > inicio) & (series[i].hora_local <= fin)]]],
    peso=TXT_PESO, cuenta=CUENTA)
st.markdown(f"**Compartir** · tarjeta con las cifras de este momento, {lugar} (PNG, 600 dpi)")
fila_t = st.container(horizontal=True, gap="small")
for tipo, rotulo in (("feed", "Publicación 4:5"), ("historia", "Historia 9:16")):
    fila_t.download_button(
        rotulo, data=lambda tipo=tipo: T.tarjeta("png", tipo, datos_tarjeta),
        file_name=f"visor_lluvia_valdivia_{tipo}_{t_obs:%Y%m%d_%H%M}.png", mime="image/png",
        icon=":material/share:", on_click="ignore", key=f"tarjeta_{tipo}")

# ------------------------------------------------------------------ pie
faltan = [e["nombre"] for e in F.ESTACIONES if e not in activas]
st.divider()
st.caption(
    f"**Pronóstico:** {PP.shape[1]} miembros de GEFS, IFS-ENS, ICON-EPS y GEPS (vía "
    f"Open-Meteo) en la celda de cada estación, promediados por zona; super-ensamble con "
    f"{TXT_PESO}; consultado el {t_pron:%d/%m %H:%M}. "
    "Intensidad descriptiva, no equivale a alertas oficiales: seguir siempre a "
    "SENAPRED, DMC y la Municipalidad.  \n"
    "**\\* Observado:** red VIPNet (DGA/MOP)"
    + (", DMC" if any(e["fuente"] == "dmc" for e in activas) else "")
    + (" y Red Agrometeorológica INIA (agrometeorologia.cl, colaboración entre INIA y "
       "las instituciones en convenio; Austral: UACh-INIA)"
       if any(e["fuente"] == "inia" for e in activas) else "")
    + ". Datos preliminares, pendientes de control de calidad. Zonas: "
    + "; ".join(f"{g} ({', '.join(e['nombre'] for e in F.ESTACIONES if e['grupo'] == g)})"
                for g in F.GRUPOS) + "."
    + (f"  \nSin datos en esta actualización: {', '.join(faltan)}." if faltan else ""))
st.page_link("metodologia.py", label="Metodología: fuentes, cálculos y limitaciones",
             icon=":material/menu_book:")
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
