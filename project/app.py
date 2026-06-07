import streamlit as st

from sidebar import render_sidebar

st.set_page_config(
    page_title="Explorador de Incendios",
    page_icon="🔥",
    layout="wide",
)

render_sidebar()

pages = st.navigation({"Explorador de Incendios": [
    st.Page("pages/inicio.py", title="Inicio", default=True),
    st.Page("pages/1_Dashboard.py", title="Dashboard"),
    st.Page("pages/2_Visualizacion_Geografica.py", title="Visualización Geográfica"),
    st.Page("pages/3_Datos.py", title="Datos"),
]})
pages.run()
