# Archivo de datos del Visor de Lluvia · Valdivia

Rama escrita automáticamente cada hora por `.github/workflows/archivo.yml`
(rama `main`). No editar a mano.

- `observado/AAAA-MM.csv`: lluvia horaria por estación (`hora_utc` = hora UTC
  en que termina el intervalo; `mm`). Datos preliminares de VIPNet (DGA) y DMC.
- `pronostico/<modelo>/AAAAMMDDHH.parquet`: cada corrida del ensamble
  (Open-Meteo), todos los miembros, desde la hora de inicio (UTC) en adelante;
  columnas `hora_utc`, `miembro`, `pp` (mm/h), `raf` (km/h).
- `indice.json`: última corrida guardada de cada modelo.

Sirve para verificar los pronósticos contra lo observado.
