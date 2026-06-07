import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from data import CAUSAS_COLORES
from page_context import cargar_datos_filtrados

filtros, df = cargar_datos_filtrados()
variable = filtros["variable"]

@st.cache_data(show_spinner=False)
def crear_heatmap_decadas(df, variable):
    df = df.copy()
    meses = list(range(1, 13))
    labels = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    if variable == "Núm. incendios":
        pivot = (
            df.groupby(["decade", "month"])["id"].count()
            .unstack(fill_value=0)
            .reindex(columns=meses, fill_value=0)
        )
        subtitulo = "incendios"
    else:
        pivot = (
            df.groupby(["decade", "month"])["superficie"].sum()
            .unstack(fill_value=0)
            .reindex(columns=meses, fill_value=0)
        )
        subtitulo = "superficie quemada"

    totals = pivot.sum(axis=1)
    pivot_norm = pivot.div(totals.where(totals > 0, other=1), axis=0)

    fig = px.imshow(
        pivot_norm, labels=dict(x="Mes", y="Década", color="Proporción"),
        x=labels, y=[f"{int(d)}s" for d in pivot_norm.index],
        color_continuous_scale="YlOrRd", aspect="auto", template="simple_white",
    )
    fig.update_traces(
        hovertemplate="Década: %{y}<br>Mes: %{x}<br>Proporción: %{z:.1%}<extra></extra>"
    )
    fig.update_layout(
        title=dict(text=f"Estacionalidad de {subtitulo} por década",
                   font_size=14, font_color="#2D2D2D"),
        coloraxis_colorbar=dict(title="Proporción", thickness=12, len=0.85),
        margin=dict(t=45, b=40, l=70, r=80), height=280,
    )
    return fig

@st.cache_data(show_spinner=False)
def crear_barras_apiladas(df, variable, normalizado=False):
    orden = ["Conato (<1 ha)", "Pequeño (1-25 ha)",
             "Grande (25-500 ha)", "GIF (>500 ha)"]
    colores = {
        "Conato (<1 ha)": "#FFF3CD", "Pequeño (1-25 ha)": "#F5A623",
        "Grande (25-500 ha)": "#E8751A", "GIF (>500 ha)": "#D23624",
    }

    col = "id" if variable == "Núm. incendios" else "superficie"
    agg = "count" if variable == "Núm. incendios" else "sum"

    resumen = (
        df.dropna(subset=["tamano"])
        .groupby(["year", "tamano"], observed=True)[col]
        .agg(agg)
        .reset_index(name="valor")
    )

    if normalizado:
        totals = resumen.groupby("year")["valor"].transform("sum")
        resumen = resumen.copy()
        resumen["valor"] = (resumen["valor"] / totals * 100).round(2)
        ytitle = "Porcentaje (%)"
    else:
        ytitle = variable

    fig = px.bar(
        resumen, x="year", y="valor", color="tamano",
        category_orders={"tamano": orden}, color_discrete_map=colores,
        labels={"year": "Año", "valor": ytitle, "tamano": "Tamaño"}, template="simple_white",
    )
    fig.update_layout(
        title=dict(text=f"{variable} por año y tamaño del incendio",
                   font_size=14, font_color="#2D2D2D"),
        legend_title_text="Tamaño", margin=dict(t=45, b=40, l=60, r=20), barmode="stack",
    )
    if normalizado:
        fig.update_yaxes(ticksuffix="%", range=[0, 100])
    return fig

@st.cache_data(show_spinner=False)
def crear_evolucion_filtrada(df, variable):
    if variable == "Núm. incendios":
        serie = df.groupby("year")["id"].count().reset_index(name="valor")
    else:
        serie = df.groupby("year")["superficie"].sum().reset_index(name="valor")

    # int ticks eje X
    all_years = serie["year"].tolist()
    step = max(1, round(len(all_years) / 12))
    tickvals = all_years[::step]
    if all_years and all_years[-1] != tickvals[-1]:
        tickvals.append(all_years[-1])

    idx_max = serie["valor"].idxmax()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=serie["year"], y=serie["valor"], mode="lines",
        line=dict(color="#D23624", width=2), name=variable,
        hovertemplate="<b>%{x}</b><br>" + variable + ": %{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[serie.loc[idx_max, "year"]], y=[serie.loc[idx_max, "valor"]],
        mode="markers+text", marker=dict(color="#D23624", size=10),
        text=[f"Max: {serie.loc[idx_max, 'valor']:,.0f}"], textposition="top center",
        showlegend=False,
    ))

    # media movil 5 years
    if len(serie) >= 5:
        serie["ma5"] = serie["valor"].rolling(5, center=True).mean()
        fig.add_trace(go.Scatter(
            x=serie["year"], y=serie["ma5"], mode="lines",
            line=dict(color="#888888", width=2.5, dash="dot"),
            name="Media móvil 5 años", opacity=0.8,
            hovertemplate="<b>%{x}</b><br>Media 5 años: %{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text=f"Evolución de {variable.lower()}",
                   font_size=14, font_color="#2D2D2D"),
        xaxis_title="Año", yaxis_title=variable,
        template="simple_white", margin=dict(t=45, b=40, l=60, r=20),
    )
    fig.update_xaxes(tickvals=tickvals, ticktext=[str(int(y)) for y in tickvals])
    return fig

@st.cache_data(show_spinner=False)
def crear_treemap_causas(df, variable):
    col = "id" if variable == "Núm. incendios" else "superficie"
    agg = "count" if variable == "Núm. incendios" else "sum"

    resumen = (
        df.groupby("causa_nombre")[col].agg(agg)
        .reset_index(name="valor")
        .dropna(subset=["causa_nombre"])
    )

    fig = px.treemap(
        resumen, path=["causa_nombre"], values="valor",
        color="causa_nombre", color_discrete_map=CAUSAS_COLORES,
        labels={"causa_nombre": "Causa", "valor": variable}, template="simple_white",
    )
    fig.update_traces(
        hovertemplate="<b>%{label}</b><br>" + variable + ": %{value:,.0f}<br>"
                      "Proporción: %{percentRoot:.1%}<extra></extra>",
        textinfo="label+percent root",
    )
    fig.update_layout(
        title=dict(text=f"Distribución por causa — {variable}",
                   font_size=14, font_color="#2D2D2D"),
        margin=dict(t=45, b=10, l=10, r=10), height=300,
    )
    return fig

@st.cache_data(show_spinner=False)
def crear_scatter_gastos(df):
    sub = df[ (df["gastos"] > 0) & (df["superficie"] > 0) & df["causa_nombre"].notna()].copy()
    sampled = sub.sample(min(len(sub), 5000), random_state=42)

    fig = px.scatter(
        sampled, x="gastos", y="superficie", 
        color="causa_nombre", color_discrete_map=CAUSAS_COLORES,
        opacity=0.5, log_x=True, log_y=True,
        labels={
            "gastos": "Gastos de extinción (€)",
            "superficie": "Superficie quemada (ha)",
            "causa_nombre": "Causa",
        },
        template="simple_white", hover_data={"municipio": True, "fecha": True},
    )

    fig.update_layout(
        title=dict(text="Gastos de extinción vs. superficie quemada",
                   font_size=14, font_color="#2D2D2D"),
        margin=dict(t=45, b=40, l=60, r=20),
    )
    return fig

@st.cache_data(show_spinner=False)
def crear_violin_causas(df):
    sub = df[(df["superficie"] > 0) & df["causa_nombre"].notna()].copy()

    # limitar outliers
    p95 = sub["superficie"].quantile(0.95)
    sub = sub[sub["superficie"] <= p95]

    fig = px.violin(
        sub, x="causa_nombre", y="superficie",
        color="causa_nombre", color_discrete_map=CAUSAS_COLORES,
        labels={"causa_nombre": "Causa", "superficie": "Superficie (ha)"},
        template="simple_white", box=True, points=False,
    )
    fig.update_layout(
        title=dict(text="Distribución de superficie quemada por causa",
                   font_size=14, font_color="#2D2D2D"),
        showlegend=False, margin=dict(t=45, b=80, l=60, r=20), xaxis_title="",
    )
    return fig


st.title("Dashboard")

tab_temporal, tab_causas = st.tabs(["Análisis temporal", "Análisis de causas"])

with tab_temporal:
    with st.container(border=True):
        st.markdown("#### Estacionalidad y tendencias")
        col_a, col_b = st.columns([1, 1])
        with col_a:
            fig_heatmap = crear_heatmap_decadas(df, variable)
            st.plotly_chart(fig_heatmap, width='stretch')
        with col_b:
            normalizado = st.toggle("Normalizado (100%)", key="barras_norm")
            fig_barras = crear_barras_apiladas(df, variable, normalizado)
            st.plotly_chart(fig_barras, width='stretch')

    with st.container(border=True):
        fig_evol = crear_evolucion_filtrada(df, variable)
        st.plotly_chart(fig_evol, width='stretch')

with tab_causas:
    st.markdown("#### Distribución y correlaciones por causa")

    with st.container(border=True):
        col_c, col_d = st.columns([1, 1])
        with col_c:
            fig_treemap = crear_treemap_causas(df, variable)
            st.plotly_chart(fig_treemap, width='stretch')
        with col_d:
            fig_violin = crear_violin_causas(df)
            st.plotly_chart(fig_violin, width='stretch')

    with st.container(border=True):
        fig_scatter = crear_scatter_gastos(df)
        st.plotly_chart(fig_scatter, width='stretch')
