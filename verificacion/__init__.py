"""
Comprobación de pronósticos de lluvia (uso interno).

Para cada evento de lluvia arma los datos (observado, corridas pasadas de
modelos deterministas y ensambles archivados), calcula métricas en bloques de
6 h y genera un informe en PDF. Lo corre tareas/verificar.py.

    comun.py     constantes, horas, acceso a la rama `datos`
    eventos.py   detección de eventos en el archivo observado
    datos.py     descarga y ordena los datos de un evento
    metricas.py  bloques de 6 h, error absoluto, CRPS, PIT, super-ensamble
    figuras.py   figuras del informe
    informe.py   texto y PDF
"""
