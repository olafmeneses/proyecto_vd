from data import cargar_datos, filtrar_datos
from sidebar import get_sidebar_filters

def cargar_datos_filtrados():
    filtros = get_sidebar_filters()
    df_total = cargar_datos()
    df = filtrar_datos(
        df_total, filtros["ccaa"], filtros["provincia"],
        filtros["anio_min"], filtros["anio_max"],
    )
    return filtros, df

def obtener_zona_titulo(filtros):
    return filtros["provincia"] if filtros["provincia"] != "Todas" else filtros["ccaa"]
