# Comprobación de pronósticos · uso interno

Rama escrita por la tarea diaria `.github/workflows/verificacion.yml` (código en
`main`: `tareas/verificar.py` y `verificacion/`). No publicar: son resultados
preliminares, pensados para juntarse entre muchos eventos.

- `catalogo.csv`: un evento por fila (ventana en UTC y hora de Chile, máximo
  acumulado en 96 h por zona, si la ventana fue automática o a mano).
- `eventos/<id>/informe_<id>.pdf`: informe del evento.
- `eventos/<id>/metricas_bloques.csv`: una fila por corrida, modelo, estación o
  zona y bloque de 6 h (pronóstico, observado, error absoluto o CRPS,
  percentil). Se junta entre eventos para las estadísticas.
- `eventos/<id>/observado.parquet`, `determinista.parquet`: datos usados. Los
  deterministas se guardan porque la API no mantiene las corridas para siempre.
- `eventos/<id>/*.png`, `*.pdf`: figuras sueltas.

Criterio de evento: alguna zona con 50 mm o más en 96 h; la ventana va desde la
primera hasta la última hora con 0,5 mm o más en alguna zona, y 12 h sin lluvia
cierran el evento.
