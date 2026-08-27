"""Geometriehulpen voor OV-lijnen en GTFS-shapes."""

import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import substring

from .instellingen import CRS_RD, CRS_WGS84


def veilige_float(waarde):
    """Converteer naar float of None."""
    try:
        return float(waarde)
    except (TypeError, ValueError):
        return None


def haversine_meter(lat1, lon1, lat2, lon2):
    """Bereken afstand in meters tussen WGS84-coördinaten."""
    lat1 = veilige_float(lat1)
    lon1 = veilige_float(lon1)
    lat2 = veilige_float(lat2)
    lon2 = veilige_float(lon2)

    if None in [lat1, lon1, lat2, lon2]:
        return None

    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a_waarde = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c_waarde = 2 * math.atan2(
        math.sqrt(a_waarde),
        math.sqrt(1 - a_waarde),
    )

    return radius * c_waarde


def maak_shape_segment(shape_lijn, from_lon, from_lat, to_lon, to_lat):
    """Knip een GTFS-shape tussen twee haltepunten."""
    if shape_lijn is None:
        return None

    if (
        pd.isna(from_lon)
        or pd.isna(from_lat)
        or pd.isna(to_lon)
        or pd.isna(to_lat)
    ):
        return None

    from_punt = Point(float(from_lon), float(from_lat))
    to_punt = Point(float(to_lon), float(to_lat))

    from_afstand = shape_lijn.project(from_punt)
    to_afstand = shape_lijn.project(to_punt)

    if from_afstand == to_afstand:
        return None

    start_afstand = min(from_afstand, to_afstand)
    eind_afstand = max(from_afstand, to_afstand)
    segment = substring(shape_lijn, start_afstand, eind_afstand)

    if segment.is_empty or segment.geom_type == "Point":
        return None

    if from_afstand > to_afstand:
        segment = LineString(list(segment.coords)[::-1])

    return segment


def lijn_delen(lijn_geom):
    """Geef LineString-delen uit LineString of MultiLineString."""
    if lijn_geom is None or lijn_geom.is_empty:
        return []

    if isinstance(lijn_geom, LineString):
        return [lijn_geom]

    if isinstance(lijn_geom, MultiLineString):
        return [
            deel
            for deel in lijn_geom.geoms
            if isinstance(deel, LineString) and not deel.is_empty
        ]

    return []


def knip_lijn_tussen_punten(lijn_geom, from_point, to_point):
    """Knip OV-lijngeometrie tussen twee haltepunten."""
    beste = None

    for deel in lijn_delen(lijn_geom):
        from_afstand = from_point.distance(deel)
        to_afstand = to_point.distance(deel)
        from_pos = deel.project(from_point)
        to_pos = deel.project(to_point)

        if from_pos == to_pos:
            continue

        score = from_afstand + to_afstand
        segment = substring(deel, min(from_pos, to_pos), max(from_pos, to_pos))

        if segment.is_empty or segment.geom_type == "Point":
            continue

        if from_pos > to_pos:
            segment = LineString(list(segment.coords)[::-1])

        kandidaat = {
            "segment": segment,
            "from_afstand_m": round(from_afstand, 2),
            "to_afstand_m": round(to_afstand, 2),
            "from_pos_m": round(from_pos, 2),
            "to_pos_m": round(to_pos, 2),
            "afstand_langs_lijn_m": round(abs(to_pos - from_pos), 1),
            "score": score,
        }

        if beste is None or kandidaat["score"] < beste["score"]:
            beste = kandidaat

    return beste


def maak_rd_punt(halte_x, halte_y, stop_lon, stop_lat):
    """Maak RD-punt; haltecoördinaten krijgen voorrang."""
    if pd.notna(halte_x) and pd.notna(halte_y):
        return Point(float(halte_x), float(halte_y))

    if pd.isna(stop_lon) or pd.isna(stop_lat):
        return None

    return gpd.GeoSeries(
        [Point(float(stop_lon), float(stop_lat))],
        crs=CRS_WGS84,
    ).to_crs(CRS_RD).iloc[0]
