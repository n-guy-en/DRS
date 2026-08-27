"""Koppeling tussen GTFS-stops en Friese haltes."""

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from .instellingen import CRS_RD, CRS_WGS84, MAX_AFSTAND_GTFS_TOT_HALTE_M


def lees_friese_haltes(pad):
    """Lees Friese OV-haltes als RD-punten."""
    if not pad.exists():
        print("Niet gevonden:", pad)
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    haltes = gpd.read_file(pad)
    bounds = haltes.total_bounds

    if haltes.crs is None or bounds[0] > 1000 or bounds[1] > 1000:
        haltes = haltes.set_crs(CRS_RD, allow_override=True)
    else:
        haltes = haltes.to_crs(CRS_RD)

    haltes = haltes[haltes.geometry.notna()].copy()
    haltes = haltes[~haltes.geometry.is_empty].copy()

    kolommen = [
        "fid",
        "Naam",
        "Type_halte",
        "Lijnen",
        "Vervoerders",
        "Gemeente",
        "Provincie",
        "geometry",
    ]
    kolommen = [kolom for kolom in kolommen if kolom in haltes.columns]
    haltes = haltes[kolommen].copy()
    haltes["halte_id"] = haltes["fid"].astype(str)

    return haltes


def koppel_gtfs_stops_aan_haltes(stops_dataframe, haltes):
    """Markeer GTFS-stops die bij Friese haltes horen."""
    stops_met_coord = stops_dataframe[
        stops_dataframe["stop_lat"].notna()
        & stops_dataframe["stop_lon"].notna()
    ].copy()

    stops_gdf = gpd.GeoDataFrame(
        stops_met_coord,
        geometry=[
            Point(lon, lat)
            for lon, lat in zip(
                stops_met_coord["stop_lon"],
                stops_met_coord["stop_lat"],
            )
        ],
        crs=CRS_WGS84,
    ).to_crs(CRS_RD)

    if haltes.empty or stops_gdf.empty:
        stops_dataframe["in_friesland"] = False
        stops_dataframe["halte_id"] = ""
        stops_dataframe["halte_naam"] = ""
        stops_dataframe["halte_afstand_m"] = pd.NA
        stops_dataframe["halte_x"] = pd.NA
        stops_dataframe["halte_y"] = pd.NA
        return stops_dataframe

    haltes_join = haltes[
        [
            "halte_id",
            "Naam",
            "Type_halte",
            "Lijnen",
            "Vervoerders",
            "Gemeente",
            "Provincie",
            "geometry",
        ]
    ].copy()
    haltes_join["halte_x"] = haltes_join.geometry.x
    haltes_join["halte_y"] = haltes_join.geometry.y

    nearest = gpd.sjoin_nearest(
        stops_gdf,
        haltes_join,
        how="left",
        max_distance=MAX_AFSTAND_GTFS_TOT_HALTE_M,
        distance_col="halte_afstand_m",
    )
    nearest = nearest.sort_values(
        ["stop_id", "halte_afstand_m"],
        na_position="last",
    )
    nearest = nearest.drop_duplicates("stop_id", keep="first")
    nearest = nearest.drop(columns=["index_right", "geometry"], errors="ignore")
    nearest = nearest.rename(
        columns={
            "Naam": "halte_naam",
            "Type_halte": "halte_type",
            "Lijnen": "halte_lijnen",
            "Vervoerders": "halte_vervoerders",
            "Gemeente": "halte_gemeente",
            "Provincie": "halte_provincie",
        }
    )
    nearest["in_friesland"] = nearest["halte_id"].notna()
    nearest["halte_afstand_m"] = nearest[
        "halte_afstand_m"
    ].round(2)

    match_kolommen = [
        "stop_id",
        "in_friesland",
        "halte_id",
        "halte_naam",
        "halte_type",
        "halte_lijnen",
        "halte_vervoerders",
        "halte_gemeente",
        "halte_provincie",
        "halte_afstand_m",
        "halte_x",
        "halte_y",
    ]

    stops_dataframe = stops_dataframe.merge(
        nearest[match_kolommen],
        on="stop_id",
        how="left",
    )
    stops_dataframe["in_friesland"] = stops_dataframe["in_friesland"].fillna(False)

    tekst_kolommen = [
        "halte_id",
        "halte_naam",
        "halte_type",
        "halte_lijnen",
        "halte_vervoerders",
        "halte_gemeente",
        "halte_provincie",
    ]
    for kolom in tekst_kolommen:
        stops_dataframe[kolom] = stops_dataframe[kolom].fillna("")

    return stops_dataframe
