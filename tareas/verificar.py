"""
Comprobación de pronósticos (uso interno). Lo corre una vez al día la tarea de
GitHub Actions (.github/workflows/verificacion.yml): busca en el archivo
observado eventos de >= 50 mm en 4 días ya terminados (verificacion/eventos.py)
y, para cada uno nuevo, guarda en la rama `verificacion`:

    catalogo.csv                          un evento por fila
    eventos/<id>/informe_<id>.pdf         informe
    eventos/<id>/metricas_bloques.csv     métricas por corrida, modelo y bloque
    eventos/<id>/observado.parquet        datos usados (los deterministas no se
    eventos/<id>/determinista.parquet     pueden volver a bajar después)
    eventos/<id>/*.png, *.pdf             figuras sueltas

    python tareas/verificar.py --archivo <rama datos> --salida <rama verificacion>
    python tareas/verificar.py ... --inicio "2026-09-22 12:00" --fin "2026-09-25 10:00"
        (ventana a mano, en hora de Chile)
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verificacion import comun as K  # noqa: E402
from verificacion import datos as D  # noqa: E402
from verificacion import eventos as E  # noqa: E402
from verificacion import informe as I  # noqa: E402
from verificacion import metricas as M  # noqa: E402


def procesa(archivo, salida, ini, fin, catalogo, manual, copias=None):
    base = f"{K.a_local(ini):%Y-%m-%d}"
    eid, k = base, 2
    while eid in set(catalogo.get("id", [])):
        eid, k = f"{base}_{k}", k + 1
    carpeta = salida / "eventos" / eid
    print(f"Evento {eid}: {K.txt_local(ini)} -> {K.txt_local(fin)} (hora de Chile)")
    obs, det, ens, faltan = D.arma(archivo, ini, fin, carpeta, copias)
    print(f"  observado {len(obs)} filas; {det.groupby(['modelo', 'init']).ngroups if len(det) else 0}"
          f" corridas deterministas ({len(faltan)} no disponibles); "
          f"{ens.groupby(['modelo', 'init']).ngroups if len(ens) else 0} corridas de ensamble")
    R = M.calcula(obs, det, ens, ini, fin, eid)
    R.MET.to_csv(carpeta / "metricas_bloques.csv", index=False, date_format="%Y-%m-%d %H:%M")
    pdf = I.todo(R, carpeta, faltan, manual)
    print(f"  -> {pdf}")
    Z = E.lluvia_zonas(obs) if len(obs) else pd.DataFrame()
    mx = E.maximo_ventana(Z, ini, fin) if len(Z) else {}
    return dict(id=eid, inicio_utc=ini, fin_utc=fin, inicio_local=K.a_local(ini),
                fin_local=K.a_local(fin), horas=R.horas, ventana="manual" if manual else "auto",
                **{f"max96_{z}": round(float(mx.get(z, float("nan"))), 1) for z in K.ZONAS},
                generado_utc=pd.Timestamp.now('UTC').tz_localize(None).floor("min"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", help="copia local de la rama datos (sin ella, se lee de GitHub)")
    ap.add_argument("--salida", required=True, help="carpeta de la rama verificacion")
    ap.add_argument("--inicio", help="inicio a mano, hora de Chile (AAAA-MM-DD HH:MM)")
    ap.add_argument("--fin", help="fin a mano, hora de Chile")
    ap.add_argument("--copias", help="carpeta con copias antiguas del ensamble (opcional)")
    a = ap.parse_args()

    archivo = K.Archivo(a.archivo)
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)
    ruta_cat = salida / "catalogo.csv"
    catalogo = pd.read_csv(ruta_cat, parse_dates=["inicio_utc", "fin_utc"]) \
        if ruta_cat.exists() else pd.DataFrame()

    if a.inicio and a.fin:
        eventos = [dict(inicio=K.a_utc(a.inicio), fin=K.a_utc(a.fin), manual=True)]
    else:
        eventos = [dict(ev, manual=False) for ev in E.detecta(archivo, catalogo)]
    if not eventos:
        print("Sin eventos nuevos.")
        return
    for ev in eventos:
        fila = procesa(archivo, salida, ev["inicio"], ev["fin"], catalogo, ev["manual"], a.copias)
        catalogo = pd.concat([catalogo, pd.DataFrame([fila])], ignore_index=True)
        catalogo.to_csv(ruta_cat, index=False, date_format="%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()
