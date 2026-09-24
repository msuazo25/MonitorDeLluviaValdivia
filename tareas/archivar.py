"""
Archivo de datos para la verificación de pronósticos. Lo corre cada hora la
tarea de GitHub Actions (.github/workflows/archivo.yml) sobre una copia de la
rama `datos`:

    observado/AAAA-MM.csv            lluvia horaria por estación (hora UTC que termina)
    pronostico/<modelo>/AAAAMMDDHH.parquet
                                     cada corrida nueva de cada modelo: todos los
                                     miembros, desde la hora de inicio en adelante,
                                     en la celda de cada estación (columna
                                     "estacion"; las corridas anteriores al
                                     24-09-2026 no la tienen y son del punto de
                                     Valdivia, F.LAT/F.LON)
    indice.json                      última corrida guardada de cada modelo

    python tareas/archivar.py <carpeta de la rama datos>

Las credenciales de la DMC se leen de DMC_USUARIO y DMC_TOKEN (Secrets del
repositorio); sin ellas se archivan solo las estaciones VIPNet e INIA.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fuentes as F  # noqa: E402

A_UTC = pd.Timedelta(hours=-F.TZ_CHILE)          # hora de Chile -> UTC


def archiva_observado(base):
    usuario, token = os.environ.get("DMC_USUARIO"), os.environ.get("DMC_TOKEN")
    filas, avisos = [], []
    for e in F.ESTACIONES:
        try:
            if e["fuente"] == "vipnet":
                o = F.vipnet(e["codigo"])
            elif e["fuente"] == "inia":
                o = F.inia(e["codigo"], e["nombre_inia"])
            elif usuario and token:
                o = F.dmc(e["codigo"], usuario, token)
            else:
                avisos.append(f"{e['id']}: sin credenciales DMC")
                continue
        except Exception as ex:                                  # noqa: BLE001
            msg = str(ex)
            for s in (token, usuario):                           # nunca imprimir credenciales
                if s:
                    msg = msg.replace(s, "***")
            avisos.append(f"{e['id']}: {msg[:120]}")
            continue
        h = F.horaria(o)                                         # solo horas completas
        filas.append(pd.DataFrame({"hora_utc": h.index + A_UTC, "estacion": e["id"],
                                   "mm": h.values.round(2)}))
    if not filas:
        return 0, avisos
    nuevo = pd.concat(filas)
    carpeta = base / "observado"
    carpeta.mkdir(parents=True, exist_ok=True)
    n = 0
    for mes, parte in nuevo.groupby(nuevo.hora_utc.dt.strftime("%Y-%m")):
        ruta = carpeta / f"{mes}.csv"
        if ruta.exists():
            parte = pd.concat([pd.read_csv(ruta, parse_dates=["hora_utc"]), parte])
        # una estación puede corregir valores recientes: gana el último
        parte = (parte.drop_duplicates(["hora_utc", "estacion"], keep="last")
                 .sort_values(["hora_utc", "estacion"]))
        parte.to_csv(ruta, index=False, date_format="%Y-%m-%d %H:%M")
        n += len(parte)
    return n, avisos


def archiva_pronostico(base):
    ruta_ind = base / "indice.json"
    indice = json.loads(ruta_ind.read_text()) if ruta_ind.exists() else {}
    hechos, avisos = [], []
    for m in F.MODELOS:
        try:
            ini = F.corrida(m)
            if indice.get(m) == f"{ini:%Y%m%d%H}":
                continue                                         # esa corrida ya está
            res = F.ensamble_modelo(m, pasado=1, dias=5,
                                    puntos=[(e["lat"], e["lon"]) for e in F.ESTACIONES])
            if res is None:
                raise RuntimeError("Open-Meteo no respondió")
            t, pp, raf = res
            t_utc = pd.DatetimeIndex(t) + A_UTC
            sel = t_utc >= ini
            con_raf = raf.shape[:2] == pp.shape[:2]        # no todos los modelos traen ráfaga
            filas = []
            for i, e in enumerate(F.ESTACIONES):             # pp: estaciones x miembros x horas
                for k in range(pp.shape[1]):
                    filas.append(pd.DataFrame({
                        "hora_utc": t_utc[sel], "estacion": e["id"], "miembro": k,
                        "pp": pp[i, k, sel].astype("float32"),
                        "raf": raf[i, k, sel].astype("float32") if con_raf else float("nan")}))
            df = pd.concat(filas, ignore_index=True)
            carpeta = base / "pronostico" / m
            carpeta.mkdir(parents=True, exist_ok=True)
            df.to_parquet(carpeta / f"{ini:%Y%m%d%H}.parquet", index=False, compression="zstd")
            indice[m] = f"{ini:%Y%m%d%H}"
            hechos.append(f"{m} {ini:%Y-%m-%d %H} UTC ({pp.shape[1]} miembros, "
                          f"{pp.shape[0]} estaciones)")
        except Exception as ex:                                  # noqa: BLE001
            avisos.append(f"{m}: {str(ex)[:120]}")
    ruta_ind.write_text(json.dumps(indice, indent=1, sort_keys=True))
    return hechos, avisos


if __name__ == "__main__":
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "archivo")
    base.mkdir(parents=True, exist_ok=True)
    n, av1 = archiva_observado(base)
    hechos, av2 = archiva_pronostico(base)
    print(f"observado: {n} filas en los meses tocados")
    print("pronóstico nuevo:", "; ".join(hechos) or "ninguno")
    for a in av1 + av2:
        print("aviso:", a)
