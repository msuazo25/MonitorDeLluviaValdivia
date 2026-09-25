# Visor de Lluvia · Valdivia

App Streamlit que compara la lluvia observada en estaciones con el
super-ensamble de pronóstico, por zona (costa, ciudad, interior): el pronóstico
de cada zona promedia las celdas del modelo donde caen sus estaciones. Se actualiza sola: descarga los datos al abrirse y
los guarda en caché 1 hora.

## Correr en tu computador

```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

(`python -m` evita el error «streamlit no se reconoce» cuando la carpeta
Scripts de Python no está en el PATH.)

## Fuentes

| Fuente | Estaciones | Acceso |
|---|---|---|
| VIPNet (DGA/MOP) | Corral, Curiñanco, Chaihuín, Llancahue | público, sin clave |
| DMC | Isla Teja, Pichoy, Corral ESSAL | usuario + token (registro gratuito en climatologia.meteochile.gob.cl) |
| Red Agrometeorológica INIA <img src="recursos/logo_agromet_inia.png" alt="Red Agrometeorológica de INIA" height="16"> | Austral (UACh-INIA), Las Lomas | público (consulta de agrometeorologia.cl); INIA pide citar la fuente y mostrar el logo de la red |
| Open-Meteo Ensemble | pronóstico (GEFS, IFS-ENS, ICON-EPS, GEPS) | público, uso no comercial |

Si falta alguna estación, revisar el expander «Avisos de descarga».

## Credenciales

Crear `.streamlit/secrets.toml` (no se sube a GitHub):

```toml
DMC_USUARIO = "tu_correo"
DMC_TOKEN = "tu_token"
```

En Streamlit Community Cloud, lo mismo va en *App settings → Secrets*.

## Publicar (Streamlit Community Cloud, gratis)

1. Crear un repositorio en GitHub con esta carpeta (`app.py`, `visor.py`, `metodologia.py`, `fuentes.py`, `graficos.py`, `recursos/`, `packages.txt`,
   `requirements.txt`, `README.md`).
2. Entrar a share.streamlit.io con la cuenta de GitHub → *Create app* →
   elegir el repositorio y `app.py`.
3. Pegar las credenciales en *Secrets*.
4. Compartir el enlace `https://<nombre>.streamlit.app`.

La app se duerme tras unos días sin visitas; la primera visita la despierta.

## Estructura

- `app.py`: punto de entrada; solo arma la navegación entre páginas.
- `visor.py`: página principal (observado vs. pronóstico).
- `metodologia.py`: fuentes, cálculos y limitaciones. Mantenerla al día si
  cambian los cálculos.
- `fuentes.py`: descarga de estaciones y del ensamble, pesos y percentiles
  ponderados del super-ensamble.
- `graficos.py`: versiones descargables (PNG 600 dpi / PDF) de los gráficos.
- `tarjeta.py`: tarjeta para redes (publicación 4:5 e historia 9:16, respetando
  las zonas que tapa Instagram).

## Archivo de datos (verificación)

Una tarea de GitHub Actions (`.github/workflows/archivo.yml`) corre cada hora
`tareas/archivar.py` y guarda en la rama **`datos`** lo observado en cada
estación y cada corrida nueva del ensamble en la celda de cada estación (ver
el README de esa rama).

- Para incluir las estaciones de la DMC, agregar `DMC_USUARIO` y `DMC_TOKEN` en
  *Settings → Secrets and variables → Actions* del repositorio.
- Se puede correr a mano en *Actions → Archivo de datos → Run workflow*.
- GitHub pausa las tareas programadas tras 60 días sin actividad en el
  repositorio; avisa por correo y se reactiva con un clic.

## Ajustes frecuentes

- Estaciones, zonas y colores: `ESTACIONES` y `GRUPOS` en `fuentes.py`; íconos de
  zona, colores vivos del observado y escala del mapa en `visor.py` (`ZONAS`,
  `VIVO`, `ESCALA_MAPA`).
- Modelos del pronóstico y sus colores: `MODELOS`, `COLOR_MODELO` e `INFO_MODELO` en `fuentes.py`.
- Período: barra lateral. Horizontes rápidos (últimas y próximas 12, 24, 36 o 72 h;
  72 h es lo que cubren VIPNet y el ensamble; por defecto 72 h hacia atrás y 72 h
  hacia adelante desde la última hora completa) o «Rango de fechas».
