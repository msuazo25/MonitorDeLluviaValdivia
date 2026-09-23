# Visor de Lluvia · Valdivia

App Streamlit que compara la lluvia observada en estaciones con el
super-ensamble de pronóstico. Se actualiza sola: descarga los datos al abrirse y
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

## Ajustes frecuentes

- Estaciones, grupos y colores: `ESTACIONES` y `GRUPOS` en `fuentes.py`.
- Modelos del pronóstico y sus colores: `MODELOS`, `COLOR_MODELO` e `INFO_MODELO` en `fuentes.py`.
- Período: barra lateral. Horizontes rápidos (últimas y próximas 12, 24, 36 o 72 h;
  72 h es lo que cubren VIPNet y el ensamble) o fechas del evento (por defecto
  22/09 12:00 → 25/09 00:00).
