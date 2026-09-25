"""Constantes, horas y acceso al archivo (rama `datos`) de la verificación."""
import io
import json
import sys
import time
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fuentes as F  # noqa: E402  estaciones y zonas del Visor

TZ = ZoneInfo("America/Santiago")
ZONAS = list(F.GRUPOS)
EST_ZONA = {g: [e["id"] for e in F.ESTACIONES if e["grupo"] == g] for g in ZONAS}
ZONA_EST = {e["id"]: e["grupo"] for e in F.ESTACIONES}
NOMBRE_EST = {e["id"]: e["nombre"].split(" (")[0] for e in F.ESTACIONES}

# modelos deterministas con corridas pasadas en la Single Runs API de Open-Meteo
# (GEM no está; JMA entrega la lluvia en bloques de 6 h)
MODELOS_DET = ["ecmwf_ifs025", "gfs_global", "icon_global", "meteofrance_arpege_world",
               "ukmo_global_deterministic_10km", "jma_gsm"]
NOMBRE_DET = {"ecmwf_ifs025": "ECMWF IFS", "gfs_global": "GFS", "icon_global": "ICON",
              "meteofrance_arpege_world": "ARPEGE", "ukmo_global_deterministic_10km": "UKMO",
              "jma_gsm": "JMA GSM"}
COLOR_DET = {"ecmwf_ifs025": "#0173B2", "gfs_global": "#D55E00", "icon_global": "#029E73",
             "meteofrance_arpege_world": "#8C6D31", "ukmo_global_deterministic_10km": "#7F7F7F",
             "jma_gsm": "#CC78BC"}
NOMBRE_ENS = {"gfs025": "GEFS", "ecmwf_ifs025": "IFS-ENS", "icon_global": "ICON-EPS",
              "gem_global": "GEPS", "super": "Super-ensamble"}
# modelo determinista "hermano" de cada ensamble (para el color)
HERMANO = {"gfs025": "gfs_global", "ecmwf_ifs025": "ecmwf_ifs025",
           "icon_global": "icon_global", "gem_global": "jma_gsm"}

REPO = "msuazo25/MonitorDeLluviaValdivia"
RAW = f"https://raw.githubusercontent.com/{REPO}/datos"
API_ARBOL = f"https://api.github.com/repos/{REPO}/git/trees/datos?recursive=1"
UA = {"User-Agent": "verificacion-lluvia-valdivia"}


def pide(url, reintentos=3, bruto=False, datos=None):
    for i in range(reintentos):
        try:
            req = urllib.request.Request(url, data=datos, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                b = r.read()
                return b if bruto else json.loads(b)
        except Exception:                                        # noqa: BLE001
            if i == reintentos - 1:
                raise
            time.sleep(3 * (i + 1))


def a_local(t):
    """UTC sin zona -> hora de Chile sin zona (escalar, o DatetimeIndex si es Series o índice)."""
    if isinstance(t, (pd.Series, pd.Index)):
        return pd.DatetimeIndex(t).tz_localize("UTC").tz_convert(TZ).tz_localize(None)
    return pd.Timestamp(t).tz_localize("UTC").tz_convert(TZ).tz_localize(None)


def a_utc(t):
    """Hora de Chile sin zona -> UTC sin zona."""
    return pd.Timestamp(t).tz_localize(TZ).tz_convert("UTC").tz_localize(None)


def txt_local(t, fmt="%d/%m %H:%M"):
    return f"{a_local(t):{fmt}}"


class Archivo:
    """Rama `datos` del Visor: una copia local (GitHub Actions) o la web."""

    def __init__(self, ruta=None):
        self.ruta = Path(ruta) if ruta else None

    def leer(self, rel):
        if self.ruta:
            p = self.ruta / rel
            return p.read_bytes() if p.exists() else None
        try:
            return pide(f"{RAW}/{rel}", bruto=True)
        except Exception:                                        # noqa: BLE001
            return None

    def listar(self, prefijo):
        if self.ruta:
            return sorted(p.relative_to(self.ruta).as_posix()
                          for p in (self.ruta / prefijo).rglob("*") if p.is_file())
        return sorted(a["path"] for a in pide(API_ARBOL)["tree"]
                      if a["path"].startswith(prefijo) and a["type"] == "blob")

    def observado(self, desde, hasta):
        """Lluvia horaria por estación (hora UTC que termina) en (desde, hasta]."""
        meses = pd.period_range(f"{desde:%Y-%m}", f"{hasta:%Y-%m}", freq="M")
        partes = [pd.read_csv(io.BytesIO(b), parse_dates=["hora_utc"])
                  for b in (self.leer(f"observado/{m}.csv") for m in meses) if b]
        if not partes:
            return pd.DataFrame(columns=["hora_utc", "estacion", "mm"])
        o = pd.concat(partes).drop_duplicates(["hora_utc", "estacion"], keep="last")
        return o[(o.hora_utc > desde) & (o.hora_utc <= hasta)].reset_index(drop=True)
