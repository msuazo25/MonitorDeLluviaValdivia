"""
Detección de eventos de lluvia en el archivo observado.

Criterio (todo sobre la lluvia horaria promedio de cada zona, como en el Visor):
  * Hora lluviosa: alguna zona con >= UMBRAL_HORA mm en la hora.
  * Episodio: horas lluviosas separadas por menos de SECO_H horas secas. La
    ventana va desde el inicio de la primera hora lluviosa hasta el fin de la
    última ("desde que empezó a llover hasta el final").
  * Evento: episodio en que alguna zona acumula >= UMBRAL_MM en alguna
    ventana de VENTANA_H horas.
  * Cerrado: hay SECO_H horas de datos sin lluvia después del final; recién
    ahí se genera el informe.
Lo ya cubierto por eventos del catálogo se descuenta (un episodio que sigue
después de un evento informado a mano se evalúa solo desde el fin de ese evento).
"""
import numpy as np
import pandas as pd

from . import comun as K

UMBRAL_HORA = 0.5        # mm en la hora, promedio de la zona
SECO_H = 12              # horas sin lluvia que separan episodios
UMBRAL_MM = 50.0         # mm acumulados en la zona
VENTANA_H = 96           # 4 días


def lluvia_zonas(obs):
    """Promedio horario de cada zona (hora UTC que termina), horas completas."""
    P = obs.pivot_table(index="hora_utc", columns="estacion", values="mm")
    P = P.reindex(pd.date_range(P.index.min(), P.index.max(), freq="h"))
    return pd.DataFrame({z: P[[e for e in est if e in P]].mean(axis=1)
                         for z, est in K.EST_ZONA.items()})


def episodios(Z, desde=None):
    """Lista de (inicio, fin) en UTC: inicio = comienzo de la primera hora lluviosa."""
    Z = Z if desde is None else Z[Z.index > desde]
    horas = Z.index[(Z.max(axis=1) >= UMBRAL_HORA).values]
    out = []
    for h in horas:
        if out and (h - out[-1][1]) <= pd.Timedelta(hours=SECO_H):
            out[-1][1] = h
        else:
            out.append([h, h])
    return [(a - pd.Timedelta(hours=1), b) for a, b in out]


def maximo_ventana(Z, ini, fin):
    """Máximo acumulado en VENTANA_H horas dentro de (ini, fin], por zona."""
    s = Z[(Z.index > ini) & (Z.index <= fin)].fillna(0)
    return s.rolling(VENTANA_H, min_periods=1).sum().max()


def detecta(archivo, catalogo, dias=45, ahora=None):
    """Eventos cerrados y nuevos: lista de dict(inicio, fin, max96) en UTC."""
    ahora = ahora or pd.Timestamp.now('UTC').tz_localize(None).floor("h")
    obs = archivo.observado(ahora - pd.Timedelta(days=dias), ahora)
    if obs.empty:
        return []
    Z = lluvia_zonas(obs)
    ultimo = obs.hora_utc.max()
    cubiertos = [(pd.Timestamp(a), pd.Timestamp(b))
                 for a, b in zip(catalogo.get("inicio_utc", []), catalogo.get("fin_utc", []))]
    nuevos = []
    for ini, fin in episodios(Z):
        # descuenta lo cubierto por eventos ya informados
        for a, b in cubiertos:
            if a < fin and b > ini:
                resto = episodios(Z[Z.index <= fin], desde=b) if b < fin else []
                if not resto:
                    ini = None
                    break
                ini, fin = resto[0][0], resto[-1][1]
        if ini is None or (ultimo - fin) < pd.Timedelta(hours=SECO_H):
            continue
        mx = maximo_ventana(Z, ini, fin)
        if np.nanmax(mx.values) >= UMBRAL_MM:
            nuevos.append(dict(inicio=ini, fin=fin, max96=mx.round(1).to_dict()))
    return nuevos
