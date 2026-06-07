import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import cargar_datos, filtrar_datos
from page_context import obtener_zona_titulo
from sidebar import get_sidebar_filters

df_total = cargar_datos()
filtros = get_sidebar_filters()
df = filtrar_datos(
    df_total, filtros["ccaa"], filtros["provincia"],
    filtros["anio_min"], filtros["anio_max"],
)

@st.cache_data(show_spinner=False)
def calcular_metricas(df_actual, df_ref):
    n_actual = len(df_actual)
    sup_actual = df_actual["superficie"].sum()
    vic_actual = (df_actual["muertos"] + df_actual["heridos"]).sum()
    ext_actual = df_actual["time_ext"].mean()

    if df_ref.empty:
        return {
            "n": (n_actual, None), "sup": (sup_actual, None),
            "vic": (vic_actual, None), "ext": (ext_actual, None),
        }

    n_ref = len(df_ref)
    sup_ref = df_ref["superficie"].sum()
    vic_ref = (df_ref["muertos"] + df_ref["heridos"]).sum()
    ext_ref = df_ref["time_ext"].mean()

    return {
        "n": (n_actual, n_actual - n_ref),
        "sup": (sup_actual, sup_actual - sup_ref),
        "vic": (vic_actual, vic_actual - vic_ref),
        "ext": (ext_actual, (ext_actual - ext_ref) if pd.notna(ext_actual) and pd.notna(ext_ref) else None),
    }


@st.cache_data(show_spinner=False)
def crear_evolucion_temporal(df, variable):
    if variable == "Núm. incendios":
        serie = df.groupby("year")["id"].count().reset_index(name="valor")
        titulo_y = "Núm. incendios"
    else:
        serie = df.groupby("year")["superficie"].sum().reset_index(name="valor")
        titulo_y = "Superficie quemada (ha.)"

    # int ticks eje X
    all_years = serie["year"].tolist()
    step = max(1, round(len(all_years) / 12))
    tickvals = all_years[::step]
    if all_years and all_years[-1] != tickvals[-1]:
        tickvals.append(all_years[-1])

    fig = px.area(
        serie, x="year", y="valor", labels={"year": "Año", "valor": titulo_y},
        template="simple_white", color_discrete_sequence=["#D23624"],
    )
    fig.update_traces(
        line_color="#D23624", fillcolor="rgba(210, 54, 36, 0.15)",
        hovertemplate="<b>%{x}</b><br>" + titulo_y + ": %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        title=dict(text=f"Evolución anual — {titulo_y}", font_size=14, font_color="#2D2D2D"),
        xaxis_title="Año", yaxis_title=titulo_y, margin=dict(t=45, b=35, l=60, r=20),
        plot_bgcolor="white", height=280,
    )
    fig.update_xaxes(tickvals=tickvals, ticktext=[str(int(y)) for y in tickvals])
    return fig


@st.cache_data(show_spinner=False)
def crear_evolucion_mensual(df, variable, anio):
    meses_labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    if variable == "Núm. incendios":
        serie = df.groupby("month")["id"].count().reset_index(name="valor")
        titulo_y = "Núm. incendios"
    else:
        serie = df.groupby("month")["superficie"].sum().reset_index(name="valor")
        titulo_y = "Superficie quemada (ha.)"

    serie = (
        serie.set_index("month")
        .reindex(range(1, 13), fill_value=0)
        .reset_index()
    )
    serie["mes_label"] = [meses_labels[m - 1] for m in serie["month"]]

    fig = px.bar(
        serie, x="mes_label", y="valor",
        labels={"mes_label": "Mes", "valor": titulo_y},
        template="simple_white", color_discrete_sequence=["#D23624"],
    )
    fig.update_traces(
        marker_color="#D23624",
        hovertemplate="<b>%{x}</b><br>" + titulo_y + ": %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        title=dict(text=f"Evolución mensual {anio} — {titulo_y}", font_size=14, font_color="#2D2D2D"),
        xaxis_title="Mes", yaxis_title=titulo_y,
        margin=dict(t=45, b=35, l=60, r=20), height=280,
    )
    return fig


@st.cache_data(show_spinner=False)
def crear_calendario_plotly(df, variable):
    df = df.copy()
    df["dia_semana"] = df["fecha"].dt.dayofweek
    df["semana"] = df["fecha"].dt.isocalendar().week.astype(int)

    n_años = max(df["year"].nunique(), 1)

    if variable == "Núm. incendios":
        conteo = df.groupby(["dia_semana", "semana"])["id"].count()
    else:
        conteo = df.groupby(["dia_semana", "semana"])["superficie"].sum()

    conteo = conteo / n_años
    pivot = conteo.unstack(fill_value=0)
    pivot = pivot.reindex(index=range(7), columns=range(1, 54), fill_value=0)

    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

    # 0 a NaN para que celdas vacías sean gris claro
    z = np.where(pivot.values > 0, pivot.values.astype(float), np.nan)

    meses_pos = [1, 5, 9, 14, 18, 23, 27, 31, 36, 40, 44, 49]
    meses_label = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                   "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    fig = go.Figure(go.Heatmap(
        z=z, x=list(range(1, 54)), y=dias, colorscale="YlOrRd",
        xgap=1, ygap=2, showscale=True,
        colorbar=dict(
            title=dict(text=variable, side="right", font=dict(size=11)),
            thickness=12, len=0.9,
        ),
        hovertemplate="Semana %{x} · %{y}<br>Media: %{z:.2f}<extra></extra>",
    ))
    fig.update_xaxes(
        tickmode="array", tickvals=meses_pos,
        ticktext=meses_label, showgrid=False,
    )
    fig.update_yaxes(showgrid=False, autorange="reversed")
    fig.update_layout(
        title=dict(
            text=f"Media diaria de {variable.lower()} por día del año",
            font_size=14, font_color="#2D2D2D",
        ),
        height=260, margin=dict(t=45, b=30, l=50, r=70),
        plot_bgcolor="#F5F5F5", paper_bgcolor="white",
    )
    return fig

anio_min, anio_max = filtros["anio_min"], filtros["anio_max"]
un_solo_anio = anio_min == anio_max
n_años = anio_max - anio_min + 1

ref_max = anio_min - 1
ref_min = max(1968, ref_max - n_años + 1)
df_ref = filtrar_datos(df_total, filtros["ccaa"], filtros["provincia"], ref_min, ref_max)

metricas = calcular_metricas(df, df_ref)

zona_titulo = obtener_zona_titulo(filtros)

st.title("Explorador de Incendios")
st.caption(
    f"Incendios forestales en **{zona_titulo}** · {anio_min}-{anio_max}"
)
st.markdown(
    f"Exploración de **{anio_max - anio_min + 1} años** de historia de incendios "
    "forestales en España, desde los datos del EGIF."
)

def fmt_delta(d):
    if d is None or np.isnan(d):
        return None
    return f"{d:+,.0f}"

# metricas
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            "Total incendios", f"{metricas['n'][0]:,.0f}",
            delta=fmt_delta(metricas["n"][1]), delta_color="inverse",
        )
    with c2:
        st.metric(
            "Superficie quemada (ha.)", f"{metricas['sup'][0]:,.0f}",
            delta=fmt_delta(metricas["sup"][1]), delta_color="inverse",
        )
    with c3:
        vic_delta = metricas["vic"][1]
        st.metric(
            "Víctimas (muertos + heridos)", f"{int(metricas['vic'][0]):,}",
            delta=fmt_delta(vic_delta) if vic_delta else None, delta_color="inverse",
        )
    with c4:
        ext_val = metricas["ext"][0]
        ext_d = metricas["ext"][1]
        st.metric(
            "Tiempo medio extinción (min)", f"{ext_val:,.0f}" if pd.notna(ext_val) else "—",
            delta=fmt_delta(ext_d) if ext_d is not None else None, delta_color="inverse",
        )

# contexto para los deltas
with st.popover("Sobre los deltas", icon="ℹ️"):
    if un_solo_anio:
        st.write(
            f"Los deltas comparan **{anio_min}** con el año anterior **{ref_max}**. "
            "Solo se muestran cuando hay un único año seleccionado o hay datos de referencia disponibles."
        )
    else:
        if not df_ref.empty:
            st.write(
                f"Los deltas comparan el periodo **{anio_min}-{anio_max}** "
                f"con el periodo anterior **{ref_min}-{ref_max}**."
            )

col_l, col_r = st.columns([3, 2], gap="medium")
with col_l:
    with st.container(border=True):
        if un_solo_anio:
            fig_evol = crear_evolucion_mensual(df, filtros["variable"], anio_min)
        else:
            fig_evol = crear_evolucion_temporal(df, filtros["variable"])
        st.plotly_chart(fig_evol, width='stretch')

with col_r:
    with st.container(border=True):
        fig_cal = crear_calendario_plotly(df, filtros["variable"])
        st.plotly_chart(fig_cal, width='stretch')
