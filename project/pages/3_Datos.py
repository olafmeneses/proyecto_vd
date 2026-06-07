import streamlit as st
from page_context import cargar_datos_filtrados, obtener_zona_titulo

filtros, df = cargar_datos_filtrados()
anio_min = filtros["anio_min"]
anio_max = filtros["anio_max"]
zona_titulo = obtener_zona_titulo(filtros)

st.title("Datos")
st.caption(f"Acceso directo · {zona_titulo} · {anio_min}-{anio_max}")

# metricas resumen
with st.container(border=True):
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Registros", f"{len(df):,}")
    with m2:
        st.metric("Hectáreas quemadas", f"{df['superficie'].sum():,.0f}")
    with m3:
        st.metric("Años con datos", df["year"].nunique())

COLS_MOSTRAR = {
    "fecha": "Fecha", "year": "Año", "month": "Mes", "comunidad": "Comunidad",
    "provincia": "Provincia", "municipio": "Municipio", "superficie": "Superficie (ha.)",
    "causa_nombre": "Causa", "tamano": "Tamaño", "muertos": "Muertos",
    "heridos": "Heridos", "gastos": "Gastos extinción (€)", "time_ext": "Tiempo extinción (min)",
}

cols_disp = [c for c in COLS_MOSTRAR if c in df.columns]
df_vista = df[cols_disp].rename(columns=COLS_MOSTRAR).reset_index(drop=True)

_, col_dl = st.columns([3, 1])
with col_dl:
    csv = df_vista.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Descargar CSV", data=csv,
        file_name=f"incendios_{zona_titulo.replace(' ', '_')}_{anio_min}-{anio_max}.csv",
        mime="text/csv", width='stretch',
    )

sup_min = float(df["superficie"].min()) if len(df) else 0.0
sup_max = float(df["superficie"].max()) if len(df) else 1.0

with st.container(border=True):
    st.markdown("**Filtros adicionales**")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        causas_disp = ["Todas"] + sorted(df["causa_nombre"].dropna().unique().tolist())
        causa_sel = st.selectbox("Causa", causas_disp, key="datos_causa")
    with col_b:
        if "tamano" in df.columns:
            tamanos_disp = ["Todos"] + sorted(df["tamano"].dropna().unique().tolist())
            tamano_sel = st.selectbox("Tamaño", tamanos_disp, key="datos_tamano")
        else:
            tamano_sel = "Todos"
    with col_c:
        if sup_max > sup_min:
            sup_rango = st.slider(
                "Superficie (ha.)", min_value=sup_min, max_value=sup_max,
                value=(sup_min, sup_max), key="datos_sup",
            )
        else:
            sup_rango = (sup_min, sup_max)

df_filtrado = df_vista.copy()
if causa_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Causa"] == causa_sel]
if tamano_sel != "Todos" and "Tamaño" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Tamaño"] == tamano_sel]
df_filtrado = df_filtrado[
    df_filtrado["Superficie (ha.)"].between(sup_rango[0], sup_rango[1])
]

st.dataframe(
    df_filtrado,
    width='stretch',
    height=520,
    column_config={
        "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        "Superficie (ha.)": st.column_config.NumberColumn("Superficie (ha.)", format="%.1f"),
        "Gastos extinción (€)": st.column_config.NumberColumn("Gastos (€)", format="%,.0f"),
        "Tiempo extinción (min)": st.column_config.NumberColumn("T. extinción (min)", format="%.0f"),
    },
)
