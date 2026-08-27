"""Kleine geometriehulpen voor netwerk- en puntbewerkingen."""

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point


def puntrepresentatie(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    punten = gdf.copy()
    geometrie = []

    for geom in punten.geometry:
        if geom is None or geom.is_empty:
            geometrie.append(None)
        elif geom.geom_type == "Point":
            geometrie.append(geom)
        elif geom.geom_type in ("LineString", "MultiLineString"):
            geometrie.append(geom.interpolate(0.5, normalized=True))
        else:
            geometrie.append(geom.representative_point())

    punten = punten.set_geometry(geometrie)
    punten = punten[punten.geometry.notna()].copy()
    punten = punten[~punten.geometry.is_empty].copy()
    return punten

def lijnstukken(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return [deel for deel in geom.geoms if isinstance(deel, LineString)]
    return []

def node_key(point: Point) -> tuple[float, float]:
    return (round(point.x, 2), round(point.y, 2))
