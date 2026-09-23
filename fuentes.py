"""
Descarga de datos para la app: estaciones (VIPNet/DGA y, con credenciales,
DMC) y super-ensamble de Open-Meteo.

Todas las funciones devuelven horas en hora de Chile (UTC-3, sin zona) y el
acumulado del intervalo que TERMINA en la marca de tiempo.
"""
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

TZ_CHILE = -3
UA = {"User-Agent": "seguimiento-lluvia-valdivia (divulgacion; contacto en la app)"}

# grupo None = solo aparece en el mapa
ESTACIONES = [
    dict(id="corral", nombre="Corral", grupo="costa", fuente="vipnet",
         codigo="10200001-3", lat=-39.8908, lon=-73.4258),
    dict(id="curinanco", nombre="Curiñanco", grupo="costa", fuente="vipnet",
         codigo="10010001-0", lat=-39.7103, lon=-73.3961),
    dict(id="chaihuin", nombre="Chaihuín", grupo="costa", fuente="vipnet",
         codigo="10210001-8", lat=-39.9519, lon=-73.5758),
    dict(id="llancahue", nombre="Llancahue", grupo="ciudad", fuente="vipnet",
         codigo="10123004-K", lat=-39.8561, lon=-73.1786),
    dict(id="islateja", nombre="Isla Teja (DMC)", grupo="ciudad", fuente="dmc",
         codigo="390015", lat=-39.8072, lon=-73.2517),
    dict(id="pichoy", nombre="Pichoy (DMC)", grupo="interior", fuente="dmc",
         codigo="390006", lat=-39.6506, lon=-73.0808),
    dict(id="corral_essal", nombre="Corral ESSAL (DMC)", grupo="costa", fuente="dmc",
         codigo="390043", lat=-39.8881, lon=-73.4406),
]
GRUPOS = {"costa": "#00797C", "ciudad": "#E0701A", "interior": "#6B3FA0"}

LAT, LON = -39.8142, -73.2459
MODELOS = {"gfs025": "GEFS", "ecmwf_ifs025": "IFS-ENS",
           "icon_global": "ICON-EPS", "gem_global": "GEPS"}
# línea punteada en los gráficos "por modelo"
COLOR_MODELO = {"gfs025": "#E377C2", "ecmwf_ifs025": "#34495E",
                "icon_global": "#7A8B1F", "gem_global": "#C9A227"}
# para la página de metodología (documentación de Open-Meteo Ensemble API)
INFO_MODELO = {
    "gfs025": ("GEFS", "NOAA/NCEP (EE. UU.)", 31, "0,25° (~25 km), cada 3 h", "cada 6 h"),
    "ecmwf_ifs025": ("IFS-ENS", "ECMWF (Europa)", 51, "0,25° (~25 km), cada 3 h", "cada 6 h"),
    "icon_global": ("ICON-EPS", "DWD (Alemania)", 40, "~26 km, cada 1 h", "cada 12 h"),
    "gem_global": ("GEPS", "ECCC (Canadá)", 21, "0,25° (~25 km), cada 3 h", "cada 12 h"),
}


def ahora_local():
    return (datetime.now(timezone.utc) + timedelta(hours=TZ_CHILE)).replace(tzinfo=None)


# ------------------------------------------------------------------ VIPNet
def vipnet(codigo, horas=72):
    """Serie cada 30 min de una estacion VIPNet (DGA). Publico, sin clave."""
    t = ahora_local()
    cuerpo = {"codigoEstacion": codigo, "tipoEstacion": 0, "fetchHour": t.hour,
              "fetchDay": f"{t:%Y-%m-%d}", "hoursRange": horas}
    r = requests.post("https://vipnet.mop.gob.cl/v1/vipnet/estacion/valores",
                      json=cuerpo, headers=UA, timeout=60)
    r.raise_for_status()
    d = r.json().get("data", [])
    if not d:
        return pd.DataFrame(columns=["hora_local", "mm"])
    df = pd.DataFrame({
        "hora_local": pd.to_datetime([x["fecha"]["$date"] for x in d]).tz_localize(None)
        + pd.Timedelta(hours=TZ_CHILE),
        "mm": [float(x.get("instantaneo") or 0.0) for x in d]})
    return df.sort_values("hora_local").reset_index(drop=True)


# ------------------------------------------------------------------ DMC
URL_DMC = "https://climatologia.meteochile.gob.cl/application/servicios/getDatosRecientesEma"


def _dmc_pide(ruta, usuario, token, intentos=3):
    for k in range(intentos):
        try:
            return _dmc_pide_una(ruta, usuario, token)
        except Exception:                                        # noqa: BLE001
            if k == intentos - 1:
                raise
            time.sleep(2 * (k + 1))


def _dmc_pide_una(ruta, usuario, token):
    r = requests.get(f"{URL_DMC}/{ruta}", params={"usuario": usuario, "token": token},
                     headers=UA, timeout=90)
    if not r.ok:                                  # sin la URL: lleva el token
        raise ValueError(f"DMC respondió HTTP {r.status_code} ({ruta})")
    try:
        j = r.json()
    except ValueError:
        raise ValueError(f"DMC no devolvió JSON ({ruta}): {r.text[:80]!r}") from None
    datos = (j.get("datosEstaciones") or {}).get("datos") or []
    if not datos:
        raise ValueError(f"DMC ({ruta}): {j.get('status') or j.get('mensaje') or 'respuesta sin datos'}")
    return datos


def _mm(v):
    return np.nan if v in (None, "") else float(str(v).replace("mm", "").strip())


def dmc(codigo, usuario, token, dias=3):
    """Serie de una EMA de la DMC (usuario + token personales).

    Junta el mes en curso (y el anterior si hace falta), cada 15 min, con las
    12 h recientes minuto a minuto. La lluvia por intervalo sale de las
    diferencias de "aguaCaida24Horas" (acumulado que se reinicia a las 12:01
    UTC), que sirve igual para ambas resoluciones. Horas en UTC -> Chile."""
    hoy = datetime.now(timezone.utc)
    desde = hoy - timedelta(days=dias)
    rutas = {f"{codigo}/{hoy:%Y/%m}"}
    if desde.month != hoy.month:
        rutas.add(f"{codigo}/{desde:%Y/%m}")
    datos, errores = [], []
    for ruta in sorted(rutas) + [codigo]:
        try:
            datos += _dmc_pide(ruta, usuario, token)
        except Exception as ex:                                  # noqa: BLE001
            errores.append(str(ex)[:80])
    if not datos:
        raise ValueError("; ".join(errores) or "DMC sin datos")
    df = pd.DataFrame({"hora_utc": pd.to_datetime([x["momento"] for x in datos]),
                       "a24": [_mm(x.get("aguaCaida24Horas")) for x in datos]})
    df = (df.dropna().drop_duplicates("hora_utc").sort_values("hora_utc")
          .loc[lambda d: d.hora_utc >= pd.Timestamp(desde).tz_localize(None)])
    inc = df.a24.diff()
    # al reiniciarse el acumulado (baja), lo caido es el valor nuevo
    df["mm"] = np.where(inc < 0, df.a24, inc).clip(min=0)
    df = df.iloc[1:]
    df["hora_local"] = df.hora_utc + pd.Timedelta(hours=TZ_CHILE)
    # todo a pasos regulares de 15 min (el tramo minutario se agrega)
    g = df.groupby(df.hora_local.dt.ceil("15min"))["mm"].sum()
    out = pd.DataFrame({"hora_local": g.index, "mm": g.values})
    out.attrs["avisos"] = errores          # fallas parciales (p. ej. falto el mes)
    return out


# ------------------------------------------------------------------ util
def horaria(o):
    """Suma a horas completas (hora que termina); descarta horas parciales."""
    if o.empty:
        return pd.Series(dtype=float)
    paso = o.hora_local.diff().median()
    por_hora = max(int(round(pd.Timedelta(hours=1) / paso)), 1) if pd.notna(paso) else 1
    g = o.groupby(o.hora_local.dt.ceil("h"))["mm"].agg(["sum", "count"])
    return g.loc[g["count"] >= por_hora, "sum"]


# ------------------------------------------------------------------ Open-Meteo
def pesos(modelos, modo):
    """Peso de cada miembro. "igual": cada modelo suma 1/K (K modelos) y se
    reparte entre sus miembros; "miembro": todos los miembros pesan 1/N."""
    modelos = np.asarray(modelos)
    if modo == "miembro":
        w = np.ones(len(modelos))
    else:
        cuenta = {m: (modelos == m).sum() for m in np.unique(modelos)}
        w = np.array([1.0 / cuenta[m] for m in modelos])
    return w / w.sum()


def cuantiles(X, w, qs):
    """Percentiles ponderados de X (miembros x tiempo, o vector de miembros).

    Ordena los miembros, ubica cada uno en el punto medio de su peso
    acumulado e interpola; con pesos iguales coincide con np.percentile
    (método "hazen"). Los NaN no cuentan."""
    X = np.asarray(X, float)
    vector = X.ndim == 1
    X = X[:, None] if vector else X
    qs = np.atleast_1d(qs) / 100.0
    out = np.full((len(qs), X.shape[1]), np.nan)
    for j in range(X.shape[1]):
        ok = np.isfinite(X[:, j])
        if not ok.any():
            continue
        x, ww = X[ok, j], np.asarray(w)[ok]
        o = np.argsort(x)
        x, ww = x[o], ww[o] / ww[o].sum()
        pos = np.cumsum(ww) - ww / 2
        out[:, j] = np.interp(qs, pos, x)
    return out[:, 0] if vector else out


# carpeta de cada modelo en los metadatos de Open-Meteo (hora de inicio de la corrida)
META_MODELO = {"gfs025": "ncep_gefs025", "ecmwf_ifs025": "ecmwf_ifs025_ensemble",
               "icon_global": "dwd_icon_eps", "gem_global": "cmc_gem_geps"}


def corrida(m):
    """Hora de inicio (UTC, sin zona) de la última corrida disponible del modelo."""
    r = requests.get(f"https://ensemble-api.open-meteo.com/data/{META_MODELO[m]}/static/meta.json",
                     headers=UA, timeout=30)
    r.raise_for_status()
    return pd.Timestamp(r.json()["last_run_initialisation_time"], unit="s")


def ensamble_modelo(m, pasado=3, dias=4):
    """Un modelo del ensamble: t (hora de Chile), precipitación y ráfaga
    (miembros x horas). Devuelve None si Open-Meteo no responde."""
    r = requests.get("https://ensemble-api.open-meteo.com/v1/ensemble", params=dict(
        latitude=LAT, longitude=LON, models=m,
        hourly="precipitation,wind_gusts_10m", past_days=pasado,
        forecast_days=dias, timezone="UTC"), headers=UA, timeout=90)
    if not r.ok:
        return None
    h = r.json()["hourly"]
    t = pd.to_datetime(h["time"]) + pd.Timedelta(hours=TZ_CHILE)

    def mat(var):
        k = sorted(c for c in h if c == var or c.startswith(var + "_member"))
        M = np.array([[np.nan if v is None else v for v in h[c]] for c in k], float)
        return M[np.isfinite(M).any(axis=1)] if M.size else M
    return t, mat("precipitation"), mat("wind_gusts_10m")


def ensamble(pasado=3, dias=4):
    """Super-ensamble horario (precipitacion y rafaga) de 4 centros.

    Devuelve t, pp, raf, mod_pp, mod_raf: mod_* dice de qué modelo es cada
    fila (miembro) de pp y de raf."""
    pp, raf, mod_pp, mod_raf, t = [], [], [], [], None
    for m in MODELOS:
        res = ensamble_modelo(m, pasado, dias)
        if res is None:
            continue
        t, p, g = res
        if p.size:
            pp.append(p)
            mod_pp += [m] * len(p)
        if g.size:
            raf.append(g)
            mod_raf += [m] * len(g)
    if not pp:
        raise RuntimeError("Open-Meteo no respondió")
    return (t, np.vstack(pp), (np.vstack(raf) if raf else None),
            np.array(mod_pp), np.array(mod_raf))
