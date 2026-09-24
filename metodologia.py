"""
Página de metodología: de dónde salen los datos y cómo se calcula cada cifra
del visor. Mantener sincronizada con fuentes.py y visor.py.
"""
import base64
from pathlib import Path

import pandas as pd
import streamlit as st

import fuentes as F

st.markdown("## Metodología")
st.caption("Cómo se obtienen y se calculan las cifras del Visor de Lluvia · Valdivia.")
st.page_link("visor.py", label="Volver al visor", icon=":material/arrow_back:")

# ------------------------------------------------------------------ observado
st.markdown("### 1. Lluvia observada")
st.markdown("""
**Estaciones.** Nueve estaciones automáticas de tres redes:

- **VIPNet, Dirección General de Aguas (MOP):** Corral, Curiñanco, Chaihuín y
  Llancahue. Se leen del mismo servicio que usa el visor público de VIPNet:
  un valor cada 30 minutos de las últimas 72 horas.
- **Dirección Meteorológica de Chile (DMC):** Isla Teja, Pichoy y Corral ESSAL.
  Se leen del servicio de datos recientes de la DMC (requiere registro). La
  DMC entrega la lluvia caída en las últimas 24 horas, acumulado que se
  reinicia a las 12:01 UTC; la lluvia de cada intervalo se obtiene como la
  diferencia entre dos lecturas consecutivas de ese acumulado y luego se suma
  en intervalos de 15 minutos.
- **Red Agrometeorológica INIA:** Austral (Valdivia, UACh-INIA) y Las Lomas
  (Máfil). Se leen de la consulta pública de agrometeorologia.cl, con la lluvia
  por hora. INIA marca cada hora por su inicio y en hora UTC−4 fija; el visor
  la pasa a la hora que termina. Se descartan las horas con datos incompletos.

**Horas.** Todo se muestra en hora de Chile (UTC−3). Cada valor horario es la
lluvia de la hora que *termina* en esa marca (por ejemplo, 14:00 = de 13:00 a
14:00). Las horas con mediciones incompletas no se usan en el gráfico por hora.

**Zonas.** Las estaciones se agrupan en tres zonas según su ubicación:
""" + "\n".join(f"- **{g}:** " + ", ".join(e["nombre"] for e in F.ESTACIONES if e["grupo"] == g)
                 for g in F.GRUPOS) + """

- *Gráfico por hora:* promedio horario de las estaciones de la zona elegida
  (o la estación elegida).
- *Cifras de arriba y tarjetas:* rango entre la estación con menos y la con
  más lluvia de la zona.
- *Gráfico acumulado:* una línea por estación de la zona, con su color.
- *Mapa:* total de cada estación en el período elegido, hasta su última
  medición, en una escala de azules (más oscuro = más lluvia); las estaciones
  de la zona elegida llevan un anillo de su color. Tramos: < 25 · 25–50 · 50–75 · 75–100 · 100–150 · > 150 mm.

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

Los datos se descargan de la **Ensemble API de Open-Meteo** en la ubicación de
cada estación: precipitación horaria y ráfaga de viento a 10 m, 3 días hacia
atrás y 4 hacia adelante. Open-Meteo entrega el valor de la **celda de la
grilla** del modelo más cercana a cada punto, no el del punto exacto.
""")
st.dataframe(pd.DataFrame([
    {"Modelo": n, "Centro": c, "Miembros": k, "Resolución": r, "Se actualiza": a}
    for n, c, k, r, a in F.INFO_MODELO.values()]), hide_index=True, width="stretch")
st.caption("Miembros y frecuencia según la documentación de Open-Meteo. Resolución: la "
           "grilla con que la API entrega cada modelo en esta zona. "
           "Los modelos con salida cada 3 h se entregan interpolados a series horarias.")

st.markdown("""
#### Pronóstico por zona

Las estaciones no caen todas en la misma celda. En los modelos de 0,25° las
nueve estaciones quedan en tres celdas: una para Isla Teja, Austral,
Llancahue y Curiñanco; otra para Corral, Corral ESSAL y Chaihuín, y otra para
Pichoy y Las Lomas. En GEPS (0,5°) quedan en cuatro celdas.

Por eso el visor compara cada zona con su propio pronóstico:

- **Zona:** para cada miembro del ensamble se promedia, hora a hora, la lluvia
  pronosticada en la celda de cada estación de la zona. Así se compara lo
  mismo que en lo observado, que también es el promedio de esas estaciones.
  Si dos estaciones comparten celda, esa celda cuenta dos veces.
- **Estación elegida:** se usa solo la celda de esa estación.

Los percentiles (ver abajo) se calculan después de promediar, sobre los
miembros ya promediados.

#### Super-ensamble: igual peso por modelo

El **super-ensamble** junta los miembros de los cuatro modelos en una sola
distribución, dando **el mismo peso a cada modelo** (25 %), sin importar
cuántos miembros tenga: cada miembro de un modelo con *n* miembros pesa
1 / (4 · *n*).

Si en cambio todos los miembros pesaran lo mismo, el modelo con más miembros
dominaría el resultado: IFS-ENS aporta 51 de 143 miembros (≈ 36 %) y GEPS
solo 21 (≈ 15 %), y eso no significa que uno sea más confiable que el otro.
Dar igual peso a cada modelo es la forma más usada al combinar sistemas de
distintos centros, porque la mejora de un conjunto multimodelo viene sobre
todo de sumar modelos distintos.

En la vista **Por modelo** se muestra la mediana de cada modelo por separado
(línea sólida en tonos pastel) y, en el acumulado, su rango p10–p90; lo
observado va encima, más grueso y en colores más vivos. Las cifras de arriba
y las tarjetas siguen usando el super-ensamble.

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
| **Cifras de arriba (por zona)** | *Observado:* rango entre estaciones de la zona. *Faltan desde las HH h:* para cada miembro se suma la lluvia pronosticada para la zona desde la hora actual hasta el fin del período; se muestran la mediana y el rango p10–p90 de esos totales. |
| **Gráfico por hora** | Pronóstico de la zona (o estación) elegida: mediana (barras) y rango p10–p90 (banda) hora a hora; línea de color: promedio observado de la zona. Línea roja: hora actual. |
| **Gráfico acumulado** | Acumulado de cada miembro desde el inicio del período; mediana y p10–p90 de esos acumulados. |
| **Tarjetas cada 6 horas** | Pronóstico de la zona (o estación) elegida: lluvia total de cada miembro en el bloque de 6 h; mediana y p10–p90. El color del número indica intensidad: débil (< 10 mm), moderada (10–25 mm) o fuerte (> 25 mm) en 6 h. **Ráfaga:** mediana de la ráfaga máxima de cada miembro en el bloque. En bloques pasados se agrega lo observado en la zona. |
| **Eje vertical** | Es el mismo en las tres zonas (el máximo de lo que se dibujaría en cualquiera de ellas en el período), para que al cambiar de zona las alturas se puedan comparar. Al elegir una estación sola, el eje se ajusta a esa estación. |
| **Horizontes rápidos** | *Últimas N h* reemplaza el inicio del período por la hora actual menos N; *próximas N h*, el fin por la hora actual más N. El máximo es 72 h: VIPNet entrega 72 h hacia atrás y el pronóstico se descarga para 4 días. |
| **Descargas** | Los gráficos se redibujan en PNG (600 dpi) o PDF, con el período, la zona o estación y el modo de pronóstico elegidos. |

Los datos se descargan al abrir la página y se guardan **una hora**; después
de ese plazo, la siguiente visita vuelve a descargarlos.
""")

# ------------------------------------------------------------------ límites
st.markdown("### 4. Limitaciones")
st.markdown("""
- **Celda vs. estación.** Aunque cada zona usa las celdas de sus estaciones,
  el pronóstico representa un promedio sobre celdas de 25 a 50 km según el
  modelo, no el punto exacto de cada estación. Los modelos globales suavizan
  el relieve, así que suelen quedarse cortos en la lluvia que refuerza la
  cordillera de la Costa.
- **Sin corrección de sesgo.** Los modelos se usan tal como vienen, sin
  ajustarlos con el historial de las estaciones.
- **Datos preliminares.** Las observaciones no tienen control de calidad.
- **No es un sistema de alerta.** Las intensidades son descriptivas y no
  equivalen a las alertas oficiales. Ante una emergencia, sigue siempre a
  SENAPRED, la Dirección Meteorológica de Chile y tu municipalidad.
""")

# ------------------------------------------------------------------ créditos
st.markdown("### 5. Fuentes y créditos")
# logo de la red INIA (lo piden al usar sus datos); fondo blanco para el tema oscuro
LOGO_INIA = base64.b64encode((Path(__file__).resolve().parent / "recursos" /
                              "logo_agromet_inia.png").read_bytes()).decode()
st.markdown("""
- Observaciones: Red Agrometeorológica INIA (agrometeorologia.cl), en
  colaboración con las instituciones en convenio con INIA (Austral: UACh)
  <img src="data:image/png;base64,""" + LOGO_INIA + """" alt="Red Agrometeorológica de INIA"
  style="height:22px;vertical-align:middle;margin-left:.3rem;background:white;padding:2px 4px;border-radius:3px">;
  red VIPNet de la Dirección General de Aguas (MOP) y red de
  estaciones automáticas de la Dirección Meteorológica de Chile.
- Pronóstico: Open-Meteo Ensemble API, con datos de NOAA/NCEP (GEFS), ECMWF
  (IFS-ENS), DWD (ICON-EPS) y ECCC (GEPS).
- Imagen del mapa: Esri World Imagery.

Implementado por **Manuel Suazo** · Laboratorio de Dendrocronología y Cambio
Global, Universidad Austral de Chile ·
[manu.suazo@gmail.com](mailto:manu.suazo@gmail.com) ·
[@el_lluviologo](https://www.instagram.com/el_lluviologo/)
""", unsafe_allow_html=True)
