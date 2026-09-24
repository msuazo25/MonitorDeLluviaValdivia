# Archivo de datos del Visor de Lluvia · Valdivia

Rama escrita automáticamente cada hora por `.github/workflows/archivo.yml`
(rama `main`). No editar a mano.

- `observado/AAAA-MM.csv`: lluvia horaria por estación (`hora_utc` = hora UTC
  en que termina el intervalo; `mm`). Datos preliminares de VIPNet (DGA) y DMC.
- `pronostico/<modelo>/AAAAMMDDHH.parquet`: cada corrida del ensamble
  (Open-Meteo), todos los miembros, desde la hora de inicio (UTC) en adelante;
  columnas `hora_utc`, `estacion`, `miembro`, `pp` (mm/h), `raf` (km/h).
  Desde el 24-09-2026 cada corrida trae la celda de cada estación (columna
  `estacion`, mismos id que en `observado/`). Las corridas anteriores no tienen
  esa columna y son del punto de Valdivia (-39.8142, -73.2459).
- `indice.json`: última corrida guardada de cada modelo.

Sirve para verificar los pronósticos contra lo observado.
