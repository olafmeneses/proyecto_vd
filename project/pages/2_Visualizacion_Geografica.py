import json
import branca.colormap as bcm
import folium
import matplotlib as mpl
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
import streamlit as st
from folium.plugins import HeatMapWithTime
from streamlit_folium import st_folium, folium_static

from data import (
    CAUSAS_COLORES, COMUNIDADES, COMUNIDAD_INE, PROVINCIAS, PROVINCIAS_POR_COMUNIDAD,
    agregar_datos, cargar_geo,
)
from page_context import cargar_datos_filtrados

filtros, df = cargar_datos_filtrados()
variable = filtros["variable"]

CENTRO_ESPANA = [40.4, -3.7]
FORMATOS_NIVEL = {"comunidades": "CC. AA.", "provincias": "Provincias", "municipios": "Municipios"}
NOMBRE_POR_NIVEL = {"comunidades": "comunidad", "provincias": "provincia", "municipios": "municipio"}
CCAA_ID_POR_NOMBRE = {nombre: ccaa_id for ccaa_id, nombre in COMUNIDADES.items()}
PROVINCIA_ID_POR_NOMBRE = {nombre: prov_id for prov_id, nombre in PROVINCIAS.items()}

def obtener_id(nombre, mapping, exclude="Todas"):
    return mapping.get(nombre) if nombre != exclude else None

def obtener_id_ccaa(ccaa_nombre):
    return obtener_id(ccaa_nombre, CCAA_ID_POR_NOMBRE, "Toda España")

def obtener_id_provincia(provincia_nombre):
    return obtener_id(provincia_nombre, PROVINCIA_ID_POR_NOMBRE, "Todas")

def cargar_geo_con_id(nivel):
    gdf = cargar_geo(nivel)
    gdf["id_geo"] = pd.to_numeric(gdf["id"], errors="coerce")
    return gdf

def obtener_centro(fila):
    bounds = fila.total_bounds
    return [float((bounds[1] + bounds[3]) / 2), float((bounds[0] + bounds[2]) / 2)]

def obtener_fila_geo(nivel, id_geo):
    if id_geo is None:
        return None

    fila = cargar_geo_con_id(nivel)
    fila = fila[fila["id_geo"] == id_geo]
    return None if fila.empty else fila

@st.cache_data(show_spinner=False)
def preparar_coropleta(df, variable, nivel, id_provincia=None, id_ccaa=None):
    resumen = agregar_datos(df, nivel, variable)
    gdf = cargar_geo_con_id(nivel)

    centro, zoom = CENTRO_ESPANA, 6

    if nivel == "municipios":
        if id_provincia is not None:
            gdf = gdf[gdf["id_geo"].fillna(0).astype(int) // 1000 == id_provincia].copy()
            centro, zoom = None, 9
        elif id_ccaa is not None:
            ids_prov = set(PROVINCIAS_POR_COMUNIDAD.get(id_ccaa, []))
            gdf = gdf[gdf["id_geo"].fillna(0).astype(int).floordiv(1000).isin(ids_prov)].copy()
            centro, zoom = None, 8
    elif nivel == "provincias" and id_ccaa is not None:
        ids_prov = set(PROVINCIAS_POR_COMUNIDAD.get(id_ccaa, []))
        gdf = gdf[gdf["id_geo"].isin(ids_prov)].copy()
        centro, zoom = None, 7

    merged = gdf.merge(
        resumen.assign(id_ine=resumen["id_ine"].astype(float)),
        left_on="id_geo", right_on="id_ine", how="left",
    )

    merged["valor"] = merged["valor"].fillna(0)
    if merged.crs and merged.crs.to_epsg() != 4326:
        merged = merged.to_crs(epsg=4326)

    # norm y colores
    pos = merged["valor"][merged["valor"] > 0]
    vmin = float(np.nanpercentile(pos, 5)) if not pos.empty else 0.0
    vmax = float(np.nanpercentile(pos, 95)) if not pos.empty else 1.0
    vmax = max(vmax, vmin + 1)

    cmap = mpl.colormaps["YlOrRd"]
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    merged["color_mapa"] = [
        mcolors.to_hex(cmap(norm(v))) if v > 0 else "#F0F0F0"
        for v in merged["valor"]
    ]

    # metadatos
    col_nombre = "name" if "name" in merged.columns else NOMBRE_POR_NIVEL.get(nivel, "")
    merged["nombre_mapa"] = merged.get(col_nombre, pd.Series("", index=merged.index)).fillna("").astype(str)
    merged["valor_mapa"] = merged["valor"]

    if centro is None:
        centro = obtener_centro(merged)

    geojson = json.loads(merged[["geometry", "nombre_mapa", "color_mapa", "valor_mapa"]].to_json())
    return geojson, centro, zoom, variable, vmin, vmax

def crear_coropleta(df, variable, nivel, id_provincia=None, id_ccaa=None):
    geojson, centro, zoom, etiqueta, vmin, vmax = preparar_coropleta(
        df, variable, nivel, id_provincia, id_ccaa
    )

    m = folium.Map(
        location=centro, zoom_start=zoom,
        tiles="CartoDB positron", prefer_canvas=True,
    )

    # barra de color en el mapa base
    colorbar = bcm.LinearColormap(
        ["#FFFF80", "#FEC44F", "#FF6600", "#CC2200"],
        vmin=vmin, vmax=vmax, caption=etiqueta,
    )
    colorbar.add_to(m)

    # capa de datos en FeatureGroup para actualizaciones eficientes
    fg = folium.FeatureGroup(name="coropleta")
    folium.GeoJson(
        geojson,
        style_function=lambda f: {
            "fillColor": f["properties"].get("color_mapa", "#F0F0F0"),
            "color": "#AAAAAA", "weight": 0.5, "fillOpacity": 0.75,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["nombre_mapa", "valor_mapa"],
            aliases=["Territorio:", etiqueta + ":"],
            localize=True, sticky=False,
            style="font-family:sans-serif;font-size:13px;",
        ),
    ).add_to(fg)

    return m, fg, centro, zoom

@st.cache_data(show_spinner=False)
def geojson_contorno(ccaa_nombre, provincia_nombre):
    if provincia_nombre != "Todas":
        fila = obtener_fila_geo("provincias", obtener_id_provincia(provincia_nombre))
    elif ccaa_nombre != "Toda España":
        fila = obtener_fila_geo("comunidades", COMUNIDAD_INE.get(obtener_id_ccaa(ccaa_nombre)))
    else:
        return None
    if fila is None:
        return None
    return json.loads(fila[["geometry"]].to_json())

@st.cache_data(show_spinner=False)
def preparar_heatmap(df):
    sub = df.dropna(subset=["lat", "lng"]).copy()
    sub = sub[sub["superficie"] > 5]  # filtrar incendios > 5 ha

    if sub.empty:
        return None, None

    anios = sorted(sub["year"].unique())
    heat_data = [sub[sub["year"] == a][["lat", "lng"]].values.tolist() for a in anios]
    indices = [str(int(a)) for a in anios]
    return heat_data, indices

def crear_heatmap_tiempo(df):
    heat_data, indices = preparar_heatmap(df)

    if heat_data is None:
        return None

    m = folium.Map(
        location=[40.0, -3.5], zoom_start=6,
        tiles="CartoDB dark_matter", prefer_canvas=True,
    )

    HeatMapWithTime(
        heat_data, index=indices, auto_play=True, min_speed=1, speed_step=1,
        max_opacity=0.85, radius=7, gradient={"0.3": "#FFFF00", "0.6": "#FF8800", "1.0": "#CC1100"},
    ).add_to(m)

    return m

@st.cache_data(show_spinner=False)
def preparar_gif(df):
    mask = (df["superficie"] > 500) & df["lat"].notna() & df["lng"].notna()
    gif = df[mask].copy()
    gif = gif[gif["lat"].between(-90, 90) & gif["lng"].between(-20, 10)]

    if gif.empty:
        return None

    cols = ["lat", "lng", "superficie", "municipio", "fecha", "causa_nombre", "muertos", "heridos", "gastos"]
    return gif[cols].reset_index(drop=True)

def crear_puntos_gif(df, ccaa_nombre="Toda España", provincia_nombre="Todas"):
    gif = preparar_gif(df)

    if gif is None:
        return None, None

    m = folium.Map(
        location=[40.0, -3.5], zoom_start=6,
        tiles="CartoDB positron", prefer_canvas=True,
    )

    # marcadores en FeatureGroup para actualizaciones eficientes
    fg = folium.FeatureGroup(name="grandes_incendios")

    # contorno de la selección activa (primero para que quede bajo los puntos)
    contorno = geojson_contorno(ccaa_nombre, provincia_nombre)
    if contorno is not None:
        folium.GeoJson(
            contorno,
            style_function=lambda f: {
                "fillColor": "#333333", "fillOpacity": 0.08,
                "color": "#222222", "weight": 1.5,
            },
        ).add_to(fg)

    for _, row in gif.iterrows():
        color = CAUSAS_COLORES.get(row["causa_nombre"], "#888888")
        radio = max(4, min(22, np.sqrt(row["superficie"]) / 4))

        popup_html = f"""
        <div style="font-family:sans-serif;font-size:12px;min-width:200px">
          <b>{row['municipio']}</b><br>
          Fecha: {str(row['fecha'])[:10]}<br>
          Superficie: <b>{row['superficie']:,.0f} ha</b><br>
          Causa: {row['causa_nombre']}<br>
          Muertos/Heridos: {int(row['muertos'])}/{int(row['heridos'])}<br>
          Gastos: {row['gastos']:,.0f} €
        </div>
        """

        folium.CircleMarker(
            location=[row["lat"], row["lng"]], radius=radio,
            color="#2D2D2D", weight=0.8, fill=True,
            fill_color=color, fill_opacity=0.75,
            tooltip=f"{row['municipio']} — {row['superficie']:,.0f} ha",
            popup=folium.Popup(popup_html, max_width=240),
        ).add_to(fg)

    # leyenda de causas en el mapa base
    causas_html = "".join([
        f'<div><span style="display:inline-block;width:12px;height:12px;'
        f'border-radius:50%;background:{color};margin-right:6px"></span>{causa}</div>'
        for causa, color in CAUSAS_COLORES.items()
    ])

    leyenda_html = f"""
    <div style="position:fixed;bottom:40px;left:40px;z-index:1000;
                background:white;padding:12px 16px;border-radius:6px;
                border:1px solid #ddd;font-family:sans-serif;font-size:12px">
      <b>Causa del incendio</b><hr style="margin:5px 0;border-color:#D23624">
      {causas_html}
    </div>
    """
    m.get_root().html.add_child(folium.Element(leyenda_html))

    return m, fg


@st.cache_data(show_spinner=False)
def calcular_centro_zoom(ccaa_nombre, provincia_nombre, nivel="comunidades"):
    if provincia_nombre != "Todas":
        fila = obtener_fila_geo("provincias", obtener_id_provincia(provincia_nombre))
        if fila is not None:
            return obtener_centro(fila), 9

    if ccaa_nombre != "Toda España" and nivel != "comunidades":
        fila = obtener_fila_geo("comunidades", COMUNIDAD_INE.get(obtener_id_ccaa(ccaa_nombre)))
        if fila is not None:
            zoom = 8 if nivel == "municipios" else 7
            return obtener_centro(fila), zoom

    return CENTRO_ESPANA, 6

st.title("Visualización geográfica")

ccaa_sel = filtros["ccaa"]
provincia_sel = filtros["provincia"]

# sync filtros y nivel territorial
if "prev_filtros" not in st.session_state:
    st.session_state["prev_filtros"] = (filtros["ccaa"], filtros["provincia"])

if (filtros["ccaa"], filtros["provincia"]) != st.session_state["prev_filtros"]:
    if filtros["provincia"] != "Todas":
        st.session_state["nivel_coropleta"] = "municipios"
    elif filtros["ccaa"] != "Toda España":
        st.session_state["nivel_coropleta"] = "provincias"
    else:
        st.session_state["nivel_coropleta"] = "comunidades"
    st.session_state["prev_filtros"] = (filtros["ccaa"], filtros["provincia"])

st.session_state.setdefault("nivel_coropleta", "comunidades")

# id CCAA activa (None si toda spain)
id_ccaa = obtener_id_ccaa(ccaa_sel)

col_tipo, col_nivel = st.columns([3, 2])

with col_tipo:
    tipo_mapa = st.segmented_control(
        "Tipo de mapa",
        ["Coropleta por territorio", "Densidad temporal (heatmap)", "Grandes incendios (GIF)"],
        default="Coropleta por territorio",
        key="tipo_mapa",
        required=True,
    )

with col_nivel:
    nivel = st.segmented_control(
        "Nivel territorial",
        ["comunidades", "provincias", "municipios"],
        format_func=lambda x: FORMATOS_NIVEL[x],
        key="nivel_coropleta",
        disabled=(tipo_mapa != "Coropleta por territorio"),
    )

if tipo_mapa == "Coropleta por territorio":
    # id_prov solo cuando nivel municipios + provincia en sidebar
    id_prov = obtener_id_provincia(provincia_sel) if nivel == "municipios" else None

    if nivel == "municipios" and provincia_sel == "Todas":
        st.caption("Mostrar todos los municipios puede tardar unos segundos.")

    centro, zoom = calcular_centro_zoom(ccaa_sel, provincia_sel, nivel)

    with st.spinner("Preparando mapa de coropletas..."):
        m_coro, fg_coro, _, _ = crear_coropleta(df, variable, nivel, id_prov, id_ccaa)

    with st.container(border=True):
        st_folium(
            m_coro, center=centro, zoom=zoom,
            feature_group_to_add=fg_coro, width="stretch",
            height=560, returned_objects=[], key="mapa_coropleta",
        )

elif tipo_mapa == "Densidad temporal (heatmap)":
    st.markdown(
        "Evolución de la densidad de incendios (> 5 ha.) **por años**. "
        "Usa los controles del mapa para reproducir la animación."
    )
    with st.spinner("Construyendo heatmap animado..."):
        m_heat = crear_heatmap_tiempo(df)

    with st.container(border=True):
        if m_heat:
            folium_static(m_heat, height=560, width="stretch")
        else:
            st.warning("No hay registros con coordenadas disponibles en la selección actual.")

else:  # "Grandes incendios (GIF)"
    st.markdown(
        "Incendios con superficie **superior a 500 ha** con coordenadas disponibles. "
        "El radio del círculo es proporcional a la raíz cuadrada de la superficie. "
        "Haz clic en un punto para ver el detalle."
    )
    # centrar en provincia > CCAA > España (nivel "provincias" para que CCAA haga zoom)
    centro_gif, zoom_gif = calcular_centro_zoom(ccaa_sel, provincia_sel, "provincias")

    with st.spinner("Cargando puntos de GIF..."):
        m_gif, fg_gif = crear_puntos_gif(df, ccaa_sel, provincia_sel)

    with st.container(border=True):
        if m_gif is not None:
            st_folium(
                m_gif, center=centro_gif, zoom=zoom_gif, feature_group_to_add=fg_gif,
                width="stretch", height=560, returned_objects=[], key="mapa_gif",
            )
        else:
            st.warning("No hay grandes incendios con coordenadas en la selección actual.")
