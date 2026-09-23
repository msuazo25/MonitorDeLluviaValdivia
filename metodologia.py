"""
Página de metodología: de dónde salen los datos y cómo se calcula cada cifra
del visor. Mantener sincronizada con fuentes.py y visor.py.
"""
import pandas as pd
import streamlit as st

import fuentes as F

st.markdown("## Metodología")
st.caption("Cómo se obtienen y se calculan las cifras del Visor de Lluvia · Valdivia.")
st.page_link("visor.py", label="Volver al visor", icon=":material/arrow_back:")

# ------------------------------------------------------------------ observado
st.markdown("### 1. Lluvia observada")
st.markdown("""
**Estaciones.** Siete estaciones automáticas de dos redes:

- **VIPNet, Dirección General de Aguas (MOP):** Corral, Curiñanco, Chaihuín y
  Llancahue. Se leen del mismo servicio que usa el visor público de VIPNet:
  un valor cada 30 minutos de las últimas 72 horas.
- **Dirección Meteorológica de Chile (DMC):** Isla Teja, Pichoy y Corral ESSAL.
  Se leen del servicio de datos recientes de la DMC (requiere registro). La
  DMC entrega la lluvia caída en las últimas 24 horas, acumulado que se
  reinicia a las 12:01 UTC; la lluvia de cada intervalo se obtiene como la
  diferencia entre dos lecturas consecutivas de ese acumulado y luego se suma
  en intervalos de 15 minutos.

**Horas.** Todo se muestra en hora de Chile (UTC−3). Cada valor horario es la
lluvia de la hora que *termina* en esa marca (por ejemplo, 14:00 = de 13:00 a
14:00). Las horas con mediciones incompletas no se usan en el gráfico por hora.

**Grupos.** Las estaciones se agrupan por ubicación:
""" + "\n".join(f"- **{g}:** " + ", ".join(e["nombre"] for e in F.ESTACIONES if e["grupo"] == g)
                 for g in F.GRUPOS) + """

- *Gráfico por hora:* promedio horario de las estaciones de cada grupo.
- *Cifras de arriba y tarjetas:* rango entre la estación con menos y la con
  más lluvia del grupo.
- *Gráfico acumulado:* una línea por estación, con el color de su grupo.
- *Mapa:* total de cada estación en el período elegido, hasta su última
  medición. Colores: < 25 · 25–50 · 50–75 · 75–100 · 100–150 · > 150 mm.

**Calidad.** Son datos en tiempo casi real, **preliminares y sin control de
calidad**: pueden tener vacíos, atrasos o errores que las instituciones
corrigen después.
""")

# ------------------------------------------------------------------ pronóstico
st.markdown("### 2. Pronóstico")
st.markdown(f"""
Se usan los **pronósticos por conjuntos** (*ensembles*) de cuatro centros
meteorológicos. Un pronóstico por conjuntos corre el mismo modelo muchas veces
con condiciones iniciales levemente distintas; cada corrida es un **miembro**
y la dispersión entre miembros muestra la incertidumbre del pronóstico.

Los datos se descargan de la **Ensemble API de Open-Meteo** para el punto de
Valdivia ({F.LAT:.2f}°, {F.LON:.2f}°): precipitación horaria y ráfaga de viento
a 10 m, 3 días hacia atrás y 4 hacia adelante.
""")
st.dataframe(pd.DataFrame([
    {"Modelo": n, "Centro": c, "Miembros": k, "Resolución": r, "Se actualiza": a}
    for n, c, k, r, a in F.INFO_MODELO.values()]), hide_index=True, width="stretch")
st.caption("Miembros, resolución y frecuencia según la documentación de Open-Meteo. "
           "Los modelos con salida cada 3 h se entregan interpolados a series horarias.")

st.markdown("""
#### Super-ensamble y pesos

El **super-ensamble** junta los miembros de los cuatro modelos en una sola
distribución. Hay dos formas de hacerlo, y el visor permite elegir:

- **Igual peso por modelo** (opción por defecto). Cada modelo pesa lo mismo
  (25 %), sin importar cuántos miembros tenga: cada miembro de un modelo con
  *n* miembros pesa 1 / (4 · *n*). Es la forma más usada al combinar
  sistemas de distintos centros, porque la mejora de un conjunto multimodelo
  viene sobre todo de sumar modelos distintos, y evita que el modelo con más
  miembros domine.
- **Igual peso por miembro.** Todos los miembros pesan lo mismo (1 / *N*).
  Así, el modelo con más miembros pesa más: IFS-ENS aporta 51 de 143
  miembros (≈ 36 %) y GEPS 21 (≈ 15 %).

En la vista **Por modelo** se muestra la mediana de cada modelo por separado
(línea punteada) y, en el acumulado, su rango p10–p90. Las cifras de arriba y
las tarjetas usan en ese caso el super-ensamble con igual peso por modelo.

#### Mediana y rango p10–p90

Para cada hora se ordenan los valores de todos los miembros según su peso:

- **Mediana (p50):** la mitad del peso del conjunto pronostica menos y la
  otra mitad, más.
- **p10–p90:** el rango que deja fuera el 10 % más bajo y el 10 % más alto.
  Ocho de cada diez escenarios caen dentro.

Técnicamente, cada miembro se ubica en el punto medio de su peso acumulado y
se interpola linealmente entre miembros; con pesos iguales coincide con el
percentil usual.

Los percentiles se calculan **sobre los totales de cada miembro**, no sumando
las medianas horarias: la mediana del acumulado no es la suma de las medianas
de cada hora.
""")

# ------------------------------------------------------------------ cifras
st.markdown("### 3. Cómo se calcula cada cifra")
st.markdown("""
| Elemento | Cálculo |
|---|---|
| **Faltan desde las HH h** | Para cada miembro se suma la lluvia pronosticada desde la hora actual hasta el fin del período; se muestran la mediana y el rango p10–p90 de esos totales. |
| **Gráfico por hora** | Mediana (barras) y rango p10–p90 (banda) hora a hora; líneas de colores: promedio observado de cada grupo. Línea roja: hora actual. |
| **Gráfico acumulado** | Acumulado de cada miembro desde el inicio del período; mediana y p10–p90 de esos acumulados. |
| **Tarjetas cada 6 horas** | Lluvia total de cada miembro en el bloque de 6 h; mediana y p10–p90. El color del número indica intensidad: débil (< 10 mm), moderada (10–25 mm) o fuerte (> 25 mm) en 6 h. **Ráfaga:** mediana de la ráfaga máxima de cada miembro en el bloque. En bloques pasados se agrega lo observado por grupo. |
| **Horizontes rápidos** | *Últimas N h* reemplaza el inicio del período por la hora actual menos N; *próximas N h*, el fin por la hora actual más N. El máximo es 72 h: VIPNet entrega 72 h hacia atrás y el pronóstico se descarga para 4 días. |
| **Descargas** | Los gráficos se redibujan en PNG (600 dpi) o PDF, con el período, la estación o grupo y el modo de pronóstico elegidos. |

Los datos se descargan al abrir la página y se guardan **una hora**; después
de ese plazo, la siguiente visita vuelve a descargarlos.
""")

# ------------------------------------------------------------------ límites
st.markdown("### 4. Limitaciones")
st.markdown("""
- **Punto de grilla vs. estación.** El pronóstico representa un promedio sobre
  una celda de ~25 km, no el punto exacto de cada estación. La lluvia real
  varía mucho entre costa, ciudad y cordillera; es normal que las estaciones
  de la costa superen el pronóstico o que el interior quede bajo él.
- **Sin corrección de sesgo.** Los modelos se usan tal como vienen, sin
  ajustarlos con el historial de las estaciones.
- **Datos preliminares.** Las observaciones no tienen control de calidad.
- **No es un sistema de alerta.** Las intensidades son descriptivas y no
  equivalen a las alertas oficiales. Ante una emergencia, sigue siempre a
  SENAPRED, la Dirección Meteorológica de Chile y tu municipalidad.
""")

# ------------------------------------------------------------------ créditos
st.markdown("### 5. Fuentes y créditos")
st.markdown("""
- Observaciones: red VIPNet de la Dirección General de Aguas (MOP) y red de
  estaciones automáticas de la Dirección Meteorológica de Chile.
- Pronóstico: Open-Meteo Ensemble API, con datos de NOAA/NCEP (GEFS), ECMWF
  (IFS-ENS), DWD (ICON-EPS) y ECCC (GEPS).
- Imagen del mapa: Esri World Imagery.

Implementado por **Manuel Suazo** · Laboratorio de Dendrocronología y Cambio
Global, Universidad Austral de Chile ·
[manu.suazo@gmail.com](mailto:manu.suazo@gmail.com) ·
[@el_lluviologo](https://www.instagram.com/el_lluviologo/)
""")
