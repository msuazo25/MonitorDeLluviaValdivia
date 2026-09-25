"""
Datos de un evento, en formato largo, horas UTC (lluvia de la hora que TERMINA):

  observado     estacion, hora_utc, mm
  determinista  modelo, init, estacion, hora_utc, pp
                corridas 00 y 12 UTC desde DIAS_ANTES días antes del inicio
                hasta el fin (Open-Meteo Single Runs API), celda de cada estación
  ensamble      fuente, modelo, init, init_aprox, punto, miembro, hora_utc, pp
                corridas archivadas por el Visor (rama datos) y, si se indican,
                copias locales antiguas del punto de Valdivia (inicio estimado)
"""
import io
import json
import urllib.parse
from pathlib import Path

import numpy as np
import pandas as pd

from . import comun as K

DIAS_ANTES = 4
# retraso típico entre el inicio de una corrida y su publicación (h), y cada
# cuánto hay corridas: para estimar el inicio de las copias antiguas
RETRASO = {"gfs025": 6, "ecmwf_ifs025": 8, "icon_global": 6, "gem_global": 7}
CADA = {"gfs025": 6, "ecmwf_ifs025": 6, "icon_global": 12, "gem_global": 12}


def corridas(ini, fin):
    """00 y 12 UTC desde DIAS_ANTES días antes del inicio; la última, al menos 6 h antes
    del fin (para que cubra un bloque entero)."""
    return pd.date_range(ini.floor("12h") - pd.Timedelta(days=DIAS_ANTES),
                         fin - pd.Timedelta(hours=6), freq="12h")


def determinista(ini, fin):
    est = K.F.ESTACIONES
    lat = ",".join(f"{e['lat']:.4f}" for e in est)
    lon = ",".join(f"{e['lon']:.4f}" for e in est)
    filas, faltan = [], []
    for m in K.MODELOS_DET:
        for c in corridas(ini, fin):
            q = urllib.parse.urlencode(dict(latitude=lat, longitude=lon, models=m,
                                            hourly="precipitation", timezone="UTC",
                                            run=f"{c:%Y-%m-%dT%H:%M}"))
            try:
                j = K.pide(f"https://single-runs-api.open-meteo.com/v1/forecast?{q}")
            except Exception:                                    # noqa: BLE001
                faltan.append((m, c))
                continue
            for e, x in zip(est, j if isinstance(j, list) else [j]):
                h = x["hourly"]
                filas.append(pd.DataFrame({
                    "modelo": m, "init": c, "estacion": e["id"],
                    "hora_utc": pd.to_datetime(h["time"]),
                    "pp": np.array([np.nan if v is None else v for v in h["precipitation"]],
                                   "float32")}))
    if not filas:
        return pd.DataFrame(columns=["modelo", "init", "estacion", "hora_utc", "pp"]), faltan
    d = pd.concat(filas, ignore_index=True)
    return d[(d.hora_utc > ini) & (d.hora_utc <= fin)].reset_index(drop=True), faltan


def ensamble(archivo, ini, fin, copias=None):
    filas = []
    # (a) copias antiguas (03_openmeteo_ensamble.py): punto de Valdivia, inicio estimado
    for f in sorted(Path(copias).glob("ensamble_valdivia*.json")) if copias else []:
        j = json.load(open(f, encoding="utf-8"))
        gen = K.a_utc(pd.Timestamp(j["generado"]))
        for m, r in j["modelos"].items():
            if m not in RETRASO:
                continue
            c = (gen - pd.Timedelta(hours=RETRASO[m])).floor(f"{CADA[m]}h")
            t = pd.to_datetime(r["tiempo"])
            for k, serie in enumerate(r["precipitation"]):
                filas.append(pd.DataFrame({
                    "fuente": f.stem, "modelo": m, "init": c, "init_aprox": True,
                    "punto": "valdivia", "miembro": k, "hora_utc": t,
                    "pp": np.array([np.nan if v is None else v for v in serie], "float32")}))
    # (b) corridas archivadas por el Visor
    desde = ini.floor("12h") - pd.Timedelta(days=DIAS_ANTES)
    for p in archivo.listar("pronostico/"):
        if not p.endswith(".parquet"):
            continue
        _, m, nombre = p.split("/")
        c = pd.Timestamp(f"{nombre[:8]} {nombre[8:10]}:00")        # AAAAMMDDHH
        if not (desde <= c <= fin):
            continue
        d = pd.read_parquet(io.BytesIO(archivo.leer(p)))
        # antes del 24-09-2026 el archivo guardaba solo el punto de Valdivia
        punto = d.pop("estacion") if "estacion" in d else "valdivia"
        filas.append(pd.DataFrame({
            "fuente": "archivo_visor", "modelo": m, "init": c, "init_aprox": False,
            "punto": punto, "miembro": d.miembro, "hora_utc": d.hora_utc,
            "pp": d.pp.astype("float32")}))
    if not filas:
        return pd.DataFrame(columns=["fuente", "modelo", "init", "init_aprox", "punto",
                                     "miembro", "hora_utc", "pp"])
    e = pd.concat(filas, ignore_index=True)
    e = e[(e.hora_utc > ini) & (e.hora_utc <= fin) & (e.hora_utc > e.init)]
    # misma corrida guardada dos veces (copia y archivo): gana el archivo
    return e.sort_values("init_aprox").drop_duplicates(
        ["modelo", "init", "punto", "miembro", "hora_utc"], keep="first").reset_index(drop=True)


def arma(archivo, ini, fin, carpeta, copias=None):
    """Descarga todo y guarda en `carpeta` lo que no se puede volver a armar: lo
    observado y los deterministas (la Single Runs API no guarda las corridas
    para siempre). Los ensambles quedan en la rama datos. Devuelve
    (obs, det, ens, faltan)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    obs = archivo.observado(ini, fin)
    det, faltan = determinista(ini, fin)
    ens = ensamble(archivo, ini, fin, copias)
    for nombre, d in (("observado", obs), ("determinista", det)):
        d.to_parquet(carpeta / f"{nombre}.parquet", index=False)
    return obs, det, ens, faltan
