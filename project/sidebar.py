import streamlit as st
from data import COMUNIDADES, PROVINCIAS_POR_COMUNIDAD, PROVINCIAS

DEFAULT_FILTROS = {
    "ccaa": "Toda España", "provincia": "Todas",
    "anios": (1999, 2023), "variable": "Núm. incendios",
}

WIDGET_KEYS = {clave: f"sidebar_{clave}" for clave in DEFAULT_FILTROS}
OPCIONES_CCAA = ["Toda España"] + sorted(COMUNIDADES.values())
OPCIONES_VARIABLE = ["Núm. incendios", "Superficie (ha.)"]

CCAA_ID_POR_NOMBRE = {nombre: ccaa_id for ccaa_id, nombre in COMUNIDADES.items()}
PROVINCIA_A_CCAA = {
    PROVINCIAS[prov_id]: COMUNIDADES[ccaa_id]
    for ccaa_id, prov_ids in PROVINCIAS_POR_COMUNIDAD.items()
    for prov_id in prov_ids
}

def get_opciones_provincia(ccaa):
    if ccaa == "Toda España":
        provincias = sorted(PROVINCIAS.values())
    else:
        id_ccaa = CCAA_ID_POR_NOMBRE.get(ccaa)
        provincias = sorted(
            PROVINCIAS[prov_id]
            for prov_id in PROVINCIAS_POR_COMUNIDAD.get(id_ccaa, [])
        )
    return ["Todas", *provincias]

def init_sidebar_field(clave, opciones=None, sync_widget=False):
    valor = st.session_state.get(clave, DEFAULT_FILTROS[clave])
    if opciones and valor not in opciones:
        valor = DEFAULT_FILTROS[clave]
    st.session_state[clave] = valor

    if sync_widget:
        widget_key = WIDGET_KEYS[clave]
        widget_valor = st.session_state.get(widget_key, valor)
        if opciones and widget_valor not in opciones:
            widget_valor = valor
        st.session_state[widget_key] = widget_valor

    return valor


def init_sidebar_state(sync_widgets=False):
    ccaa = init_sidebar_field("ccaa", OPCIONES_CCAA, sync_widgets)
    init_sidebar_field("provincia", get_opciones_provincia(ccaa), sync_widgets)
    init_sidebar_field("anios", sync_widget=sync_widgets)
    init_sidebar_field("variable", OPCIONES_VARIABLE, sync_widgets)


def on_ccaa_change():
    ccaa = st.session_state.get(WIDGET_KEYS["ccaa"], DEFAULT_FILTROS["ccaa"])
    st.session_state["ccaa"] = ccaa

    provincia = st.session_state.get("provincia", DEFAULT_FILTROS["provincia"])
    opciones_prov = get_opciones_provincia(ccaa)
    if provincia not in opciones_prov:
        provincia = DEFAULT_FILTROS["provincia"]

    st.session_state["provincia"] = provincia
    st.session_state[WIDGET_KEYS["provincia"]] = provincia


def on_provincia_change():
    provincia = st.session_state.get(WIDGET_KEYS["provincia"], DEFAULT_FILTROS["provincia"])
    st.session_state["provincia"] = provincia

    if provincia == "Todas":
        return

    ccaa_nombre = PROVINCIA_A_CCAA.get(provincia)
    if ccaa_nombre is not None:
        st.session_state["ccaa"] = ccaa_nombre
        st.session_state[WIDGET_KEYS["ccaa"]] = ccaa_nombre


def current_sidebar_filters():
    anio_min, anio_max = st.session_state.get("anios", DEFAULT_FILTROS["anios"])
    return {
        "ccaa": st.session_state.get("ccaa", DEFAULT_FILTROS["ccaa"]),
        "provincia": st.session_state.get("provincia", DEFAULT_FILTROS["provincia"]),
        "anio_min": anio_min, "anio_max": anio_max,
        "variable": st.session_state.get("variable", DEFAULT_FILTROS["variable"]),
    }


def get_sidebar_filters():
    init_sidebar_state()
    return current_sidebar_filters()


def render_sidebar():
    st.markdown("<style>div[data-testid='stMarkdownContainer']>hr {margin-top: 1px; margin-bottom: 1px;}</style>", unsafe_allow_html=True)
    init_sidebar_state(sync_widgets=True)

    with st.sidebar:
        st.markdown("#### 📍 Ubicación")
        ccaa = st.selectbox(
            "Comunidad Autónoma", options=OPCIONES_CCAA, key=WIDGET_KEYS["ccaa"],
            on_change=on_ccaa_change, help="Filtra a nivel de comunidad autónoma."
        )

        opciones_prov = get_opciones_provincia(ccaa)

        provincia = st.selectbox(
            "Provincia", opciones_prov, key=WIDGET_KEYS["provincia"],
            on_change=on_provincia_change, help="Las opciones de provincia se actualizan según la CCAA seleccionada."
        )

        st.divider()

        st.markdown("#### 📊 Métrica a analizar")
        variable = st.segmented_control(
            "Variable", options=OPCIONES_VARIABLE, key=WIDGET_KEYS["variable"],
            required=True, label_visibility="collapsed"
        )

        st.divider()

        st.markdown("#### 📅 Período de tiempo")
        anios = st.slider(
            "Rango de años", min_value=1968, max_value=2023,
            key=WIDGET_KEYS["anios"], help="Desliza para acotar los años de estudio."
        )
        
        diff = anios[1] - anios[0] + 1
        diff_info = f"**Año seleccionado: {anios[0]}**" if diff == 1 else f"**{diff} años seleccionados**"
        st.info(diff_info, icon="⏱️")
        
        st.divider()

        st.markdown(
            """
            <div style='color: #888888; font-size: 0.85em;'>
                <b>Fuente:</b> EGIF. Ministerio de Agricultura, Pesca y Alimentación
            </div>
            """, 
            unsafe_allow_html=True
        )

    st.session_state.update({
        "ccaa": ccaa, "provincia": provincia,
        "variable": variable, "anios": anios,
    })

    return current_sidebar_filters()
