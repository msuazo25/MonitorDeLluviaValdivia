"""
Métricas de un evento, sobre bloques de 6 h alineados a UTC (00-06, 06-12,
12-18, 18-24; JMA solo entrega así). Solo cuentan los bloques enteros dentro de
la ventana; los totales del evento usan la ventana exacta, hora a hora.

  * Plazo de un bloque = fin del bloque - inicio de la corrida (solo bloques
    enteramente posteriores al inicio).
  * Zona = promedio de las estaciones del grupo (observado: estaciones con el
    bloque completo; pronóstico: celdas de esas estaciones).
  * Determinista: error absoluto. Ensamble: CRPS (igual peso por modelo en el
    super-ensamble). Para un solo valor el CRPS es el error absoluto: misma escala.
  * PIT: percentil ponderado de lo observado dentro del ensamble.

La tabla `MET` (una fila por corrida, modelo, unidad y bloque) se guarda como
metricas_bloques.csv y se junta entre eventos.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import comun as K

MIN_COBERTURA = 0.85     # fracción de horas con dato para usar el total de una estación


def bloques6(df, valor, claves):
    """Suma por bloque de 6 h (identificado por su fin); NaN si falta alguna hora."""
    d = df.copy()
    d["fin"] = d.hora_utc.dt.ceil("6h")
    g = d.groupby(claves + ["fin"])[valor].agg(["sum", "count"]).reset_index()
    g.loc[g["count"] < 6, "sum"] = np.nan
    return g.drop(columns="count").rename(columns={"sum": valor})


def crps(x, w, y):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x)
    x, w = x[ok], w[ok] / w[ok].sum()
    return np.sum(w * np.abs(x - y)) - 0.5 * np.sum(np.outer(w, w) * np.abs(x[:, None] - x[None, :]))


def pit(x, w, y):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x)
    x, w = x[ok], w[ok] / w[ok].sum()
    return 100 * (np.sum(w[x < y]) + 0.5 * np.sum(w[x == y]))


def _unidades_ens(g):
    """{unidad: miembros x bloques} de una corrida de un modelo de ensamble. El punto
    "valdivia" (archivo previo al 24/09 y copias) se compara con la zona ciudad."""
    out = {}
    if (g.punto == "valdivia").all():
        out["zona_ciudad"] = g.pivot(index="miembro", columns="fin", values="pp")
    else:
        for z in K.ZONAS:
            gz = g[g.punto.isin(K.EST_ZONA[z])]
            if len(gz):
                out[f"zona_{z}"] = gz.groupby(["miembro", "fin"]).pp.mean().unstack()
    return out


def calcula(obs_h, det_h, ens_h, ini, fin, evento):
    horas = int((fin - ini) / pd.Timedelta(hours=1))
    obs_b = bloques6(obs_h, "mm", ["estacion"])
    OBS = obs_b.pivot(index="fin", columns="estacion", values="mm")
    OBS = OBS[(OBS.index - pd.Timedelta(hours=6) >= ini) & (OBS.index <= fin)]
    OBS_Z = pd.DataFrame({z: OBS[[e for e in K.EST_ZONA[z] if e in OBS]].mean(axis=1)
                          for z in K.ZONAS})
    fines_ok = set(OBS.index)

    det_b = bloques6(det_h, "pp", ["modelo", "init", "estacion"]) if len(det_h) else \
        pd.DataFrame(columns=["modelo", "init", "estacion", "fin", "pp"])
    det_b = det_b[(det_b.fin - pd.Timedelta(hours=6) >= det_b.init) & det_b.fin.isin(fines_ok)]
    ens_b = bloques6(ens_h, "pp", ["modelo", "init", "init_aprox", "punto", "miembro"]) \
        if len(ens_h) else pd.DataFrame(columns=["modelo", "init", "init_aprox", "punto",
                                                 "miembro", "fin", "pp"])
    ens_b = ens_b[(ens_b.fin - pd.Timedelta(hours=6) >= ens_b.init) & ens_b.fin.isin(fines_ok)]

    def o_de(u, f):
        if u.startswith("zona_"):
            z = u[5:]
            return OBS_Z.at[f, z] if f in OBS_Z.index else np.nan
        return OBS.at[f, u] if (f in OBS.index and u in OBS) else np.nan

    filas = []
    for (m, c), g in det_b.groupby(["modelo", "init"]):
        P = g.pivot(index="fin", columns="estacion", values="pp")
        for f, fila in P.iterrows():
            plazo = (f - c) / pd.Timedelta(hours=1)
            for u, v in list(fila.items()) + [(f"zona_{z}", fila[[e for e in K.EST_ZONA[z]
                                                                  if e in fila]].mean())
                                              for z in K.ZONAS]:
                o = o_de(u, f)
                filas.append(dict(tipo="determinista", modelo=m, init=c, init_aprox=False,
                                  unidad=u, fin=f, plazo_h=plazo, pron=v, obs=o,
                                  error=abs(v - o), pit=np.nan))

    por_corrida = {}
    for (m, c, aprox), g in ens_b.groupby(["modelo", "init", "init_aprox"]):
        for u, M in _unidades_ens(g).items():
            por_corrida.setdefault((c, aprox, u), {})[m] = M
            for f in M.columns:
                o, x = o_de(u, f), M[f].values
                w = np.full(len(x), 1 / len(x))
                ok = np.isfinite(o)
                filas.append(dict(tipo="ensamble", modelo=m, init=c, init_aprox=aprox, unidad=u,
                                  fin=f, plazo_h=(f - c) / pd.Timedelta(hours=1),
                                  pron=np.nanmedian(x), obs=o,
                                  error=crps(x, w, o) if ok else np.nan,
                                  pit=pit(x, w, o) if ok else np.nan))

    # super-ensamble: modelos con inicio en la misma "ronda" de 12 h, >= 3 de 4
    rondas = {}
    for (c, aprox, u), mods in por_corrida.items():
        r = rondas.setdefault((c.floor("12h"), u), [{}, False])
        r[0].update(mods)
        r[1] |= bool(aprox)
    SUPER = {}
    for (r, u), (mods, aprox) in rondas.items():
        if len(mods) < 3:
            continue
        fines = sorted(set.intersection(*[set(M.columns) for M in mods.values()]))
        if not fines:
            continue
        X = np.vstack([M[fines].values for M in mods.values()])
        W = np.concatenate([np.full(len(M), 1 / (len(mods) * len(M))) for M in mods.values()])
        SUPER[(r, u)] = (fines, X, W)
        for j, f in enumerate(fines):
            o = o_de(u, f)
            ok = np.isfinite(o)
            filas.append(dict(tipo="ensamble", modelo="super", init=r, init_aprox=aprox,
                              unidad=u, fin=f, plazo_h=(f - r) / pd.Timedelta(hours=1),
                              pron=K.F.cuantiles(X[:, j], W, [50])[0], obs=o,
                              error=crps(X[:, j], W, o) if ok else np.nan,
                              pit=pit(X[:, j], W, o) if ok else np.nan))

    cols = ["tipo", "modelo", "init", "init_aprox", "unidad", "fin", "plazo_h", "pron", "obs",
            "error", "pit"]
    MET = pd.DataFrame(filas, columns=cols)
    MET.insert(0, "evento", evento)

    # totales por estación en la ventana exacta (hora a hora)
    tot = []
    for e in K.F.ESTACIONES:
        oe = obs_h[obs_h.estacion == e["id"]]
        tot.append(dict(estacion=e["id"], zona=e["grupo"], mm=oe.mm.sum() if len(oe) else np.nan,
                        horas=len(oe), cobertura=len(oe) / horas))
    TOT = pd.DataFrame(tot)
    return SimpleNamespace(ini=ini, fin=fin, horas=horas, evento=evento, obs_h=obs_h,
                           det_h=det_h, ens_h=ens_h, OBS=OBS, OBS_Z=OBS_Z, det_b=det_b,
                           ens_b=ens_b, SUPER=SUPER, MET=MET, TOT=TOT)


def zona_horaria(R):
    """Lluvia horaria promedio de cada zona en la ventana (hora UTC que termina)."""
    P = R.obs_h.pivot_table(index="hora_utc", columns="estacion", values="mm")
    P = P.reindex(pd.date_range(R.ini + pd.Timedelta(hours=1), R.fin, freq="h"))
    return pd.DataFrame({z: P[[e for e in K.EST_ZONA[z] if e in P]].mean(axis=1)
                         for z in K.ZONAS})


def total_previas(R, est, antes_h=36):
    """Total pronosticado para una estación por cada modelo determinista (promedio de
    sus corridas de las `antes_h` h previas al inicio), sumado solo en las horas con
    dato observado."""
    d = R.det_h
    d = d[(d.init <= R.ini) & (d.init >= R.ini - pd.Timedelta(hours=antes_h))]
    horas = set(R.obs_h[R.obs_h.estacion == est].hora_utc)
    pe = d[(d.estacion == est) & d.hora_utc.isin(horas)]
    return pe.groupby(["modelo", "init"]).pp.sum().groupby("modelo").mean()


def cociente_resto(R, z, min_obs=10.0):
    """Pronosticado / observado de lo que quedaba del evento, por corrida y modelo
    (deterministas) y cuantiles del super-ensamble. Se usa la ventana exacta hora a
    hora para los deterministas y los bloques de 6 h para los ensambles."""
    Zh = zona_horaria(R)[z]
    det = []
    for (m, c), g in R.det_h.groupby(["modelo", "init"]):
        P = g[g.estacion.isin(K.EST_ZONA[z])].groupby("hora_utc").pp.mean()
        P = P[P.index > c]
        o = Zh.reindex(P.index)
        ok = o.notna().values & np.isfinite(P.values)
        if ok.any() and o[ok].sum() >= min_obs:
            det.append(dict(modelo=m, init=c, f=P.values[ok].sum(), o=o.values[ok].sum()))
    det = pd.DataFrame(det, columns=["modelo", "init", "f", "o"])
    det["r"] = det.f / det.o
    sup = []
    for (r, u), (fines, X, W) in sorted(R.SUPER.items()):
        if u != f"zona_{z}":
            continue
        o = R.OBS_Z.loc[fines, z]
        ok = o.notna().values
        if o[ok].sum() < min_obs:
            continue
        q = K.F.cuantiles(X[:, ok].sum(axis=1) / o[ok].sum(), W, [10, 50, 90])
        sup.append(dict(init=r, p10=q[0], p50=q[1], p90=q[2]))
    return det, pd.DataFrame(sup, columns=["init", "p10", "p50", "p90"])
