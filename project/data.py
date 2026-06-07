import os
import pandas as pd
import geopandas as gpd
import numpy as np
import streamlit as st

DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DIR, "data")
GEO_CACHE = os.path.join(DATA, "geo_cache")
_URL_ATLAS = "https://unpkg.com/es-atlas@0.6.0/es/municipalities.json"

# mapeos idcomunidad a nombres y códigos INE
COMUNIDADES = {1: "País Vasco", 2: "Cataluña", 3: "Galicia", 4: "Andalucía", 5: "Asturias", 6: "Cantabria", 7: "La Rioja", 8: "Murcia", 9: "Com. Valenciana", 10: "Aragón", 11: "Castilla-La Mancha", 12: "Canarias", 13: "Navarra", 14: "Extremadura", 15: "Baleares", 16: "Madrid", 17: "Castilla y León", 18: "Ceuta"}
COMUNIDAD_INE = {1: 16, 2: 9, 3: 12, 4: 1, 5: 3, 6: 6, 7: 17, 8: 14, 9: 10, 10: 2, 11: 8, 12: 5, 13: 15, 14: 11, 15: 4, 16: 13, 17: 7, 18: 18}

# idprovincia a nombres Y comunidad a lista de provs
PROVINCIAS = {1: "Álava", 2: "Albacete", 3: "Alicante", 4: "Almería", 5: "Ávila", 6: "Badajoz", 7: "Baleares", 8: "Barcelona", 9: "Burgos", 10: "Cáceres", 11: "Cádiz", 12: "Castellón", 13: "Ciudad Real", 14: "Córdoba", 15: "A Coruña", 16: "Cuenca", 17: "Girona", 18: "Granada", 19: "Guadalajara", 20: "Guipúzcoa", 21: "Huelva", 22: "Huesca", 23: "Jaén", 24: "León", 25: "Lleida", 26: "La Rioja", 27: "Lugo", 28: "Madrid", 29: "Málaga", 30: "Murcia", 31: "Navarra", 32: "Ourense", 33: "Asturias", 34: "Palencia", 35: "Las Palmas", 36: "Pontevedra", 37: "Salamanca", 38: "S.C. Tenerife", 39: "Cantabria", 40: "Segovia", 41: "Sevilla", 42: "Soria", 43: "Tarragona", 44: "Teruel", 45: "Toledo", 46: "Valencia", 47: "Valladolid", 48: "Vizcaya", 49: "Zamora", 50: "Zaragoza", 51: "Ceuta"}
PROVINCIAS_POR_COMUNIDAD = {1: [1, 20, 48], 2: [8, 17, 25, 43], 3: [15, 27, 32, 36], 4: [4, 11, 14, 18, 21, 23, 29, 41], 5: [33], 6: [39], 7: [26], 8: [30], 9: [3, 12, 46], 10: [22, 44, 50], 11: [2, 13, 16, 19, 45], 12: [35, 38], 13: [31], 14: [6, 10], 15: [7], 16: [28], 17: [5, 9, 24, 34, 37, 40, 42, 47, 49], 18: [51] }

# causas a nombres y colores
CAUSAS = {1: "Rayo", 2: "Negligencia/Accidental", 3: "Intencionado", 4: "Desconocida", 5: "Reproducción", 6: "Otras"}
CAUSAS_COLORES = {"Rayo": "#F5A623", "Negligencia/Accidental": "#E8751A", "Intencionado": "#D23624", "Reproducción": "#9B2335", "Desconocida": "#888888", "Otras": "#BBBBBB"}

@st.cache_data(show_spinner=False)
def cargar_datos():
    df = pd.read_csv(os.path.join(DATA, "fires-all.csv"), low_memory=False)
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.dropna(subset=["fecha"])

    df["year"] = df["fecha"].dt.year
    df["month"] = df["fecha"].dt.month
    df["decade"] = (df["year"] // 10) * 10

    # mappings
    df["comunidad"] = df["idcomunidad"].map(COMUNIDADES)
    df["provincia"] = df["idprovincia"].map(PROVINCIAS)
    df["causa_nombre"] = df["causa"].map(CAUSAS)
    df["ine_comunidad"] = df["idcomunidad"].map(COMUNIDAD_INE)
    
    # bins
    df["tamano"] = pd.cut(df["superficie"], bins=[-np.inf, 0, 1, 25, 500, np.inf], 
                          labels=["Sin datos", "Conato (<1 ha)", "Pequeño (1-25 ha)", "Grande (25-500 ha)", "GIF (>500 ha)"])
    
    df["ine_municipio"] = (df["idprovincia"] * 1000 + df["idmunicipio"].fillna(0)).replace(0, np.nan)
    df[["time_ext", "time_ctrl"]] = df[["time_ext", "time_ctrl"]].replace(0, np.nan)
    
    return df

@st.cache_data(show_spinner=False)
def cargar_geo(nivel="provincias"):
    os.makedirs(GEO_CACHE, exist_ok=True)
    cache = os.path.join(GEO_CACHE, f"{nivel}.geojson")
    
    if os.path.exists(cache):
        return gpd.read_file(cache)

    layer_map = {"provincias": "provinces", "comunidades": "autonomous_regions", "municipios": "municipalities"}
    gdf = gpd.read_file(_URL_ATLAS, layer=layer_map.get(nivel, "provinces"))
    
    gdf["id"] = pd.to_numeric(gdf["id"], errors="coerce").astype("Int64")
    gdf.to_file(cache, driver="GeoJSON")
    return gdf

@st.cache_data(show_spinner=False)
def filtrar_datos(df, ccaa, provincia, anio_min, anio_max):
    mask = df["year"].between(anio_min, anio_max)
    if ccaa != "Toda España":
        mask &= (df["comunidad"] == ccaa)
    if provincia != "Todas":
        mask &= (df["provincia"] == provincia)
    return df[mask].copy()

@st.cache_data(show_spinner=False)
def agregar_datos(df, nivel, variable):
    config = {
        "comunidades": {"id": "ine_comunidad", "name": "comunidad"},
        "provincias": {"id": "idprovincia", "name": "provincia"},
        "municipios": {"id": "ine_municipio", "name": "municipio"}
    }
    
    target = config[nivel]
    val_col = "id" if variable == "Núm. incendios" else "superficie"
    agg_func = "count" if variable == "Núm. incendios" else "sum"

    return (
        df.groupby([target["id"], target["name"]])
        .agg(valor=(val_col, agg_func))
        .reset_index()
        .rename(columns={target["id"]: "id_ine"})
    )
