"""
Visor de Lluvia · Valdivia — punto de entrada (Streamlit Community Cloud
ejecuta este archivo). Solo arma la navegación entre páginas:

    visor.py        observado vs. pronóstico (página principal)
    metodologia.py  fuentes, cálculos y limitaciones

    python -m streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Visor de Lluvia - Valdivia", page_icon="🌧️", layout="wide")

st.navigation([
    st.Page("visor.py", title="Visor", icon=":material/rainy:", default=True),
    st.Page("metodologia.py", title="Metodología", icon=":material/menu_book:"),
]).run()
