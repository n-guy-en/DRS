import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .instellingen import OSM_FIETS_HIGHWAYS, OSM_LOOP_HIGHWAYS
from .netwerk import (
    maak_exportklaar,
    schrijf_geojson_met_unieke_feature_ids,
    voeg_reiskosten_toe,
)


def parse_highway_waarde(waarde: Any) -> list[str]:
    if isinstance(waarde, list):
        return [str(item).strip().lower() for item in waarde]
    if waarde is None:
        return []

    tekst = str(waarde).strip()
    if tekst.startswith("[") and tekst.endswith("]"):
        try:
            parsed = ast.literal_eval(tekst)
        except (SyntaxError, ValueError):
            return [tekst.lower()]
        if isinstance(parsed, list):
            return [str(item).strip().lower() for item in parsed]

    return [tekst.lower()]


def heeft_osm_loop_highway(waarde: Any) -> bool:
    return bool(set(parse_highway_waarde(waarde)) & OSM_LOOP_HIGHWAYS)


def heeft_osm_fiets_highway(waarde: Any) -> bool:
    return bool(set(parse_highway_waarde(waarde)) & OSM_FIETS_HIGHWAYS)


def controleer_osm_kolommen(osm: Any, osm_edges_pad: Path) -> None:
    verplichte_kolommen = {"highway", "geometry"}
    ontbrekend = sorted(verplichte_kolommen - set(osm.columns))
    if ontbrekend:
        raise ValueError(
            f"Kolommen ontbreken in OSM-bestand {osm_edges_pad}: {ontbrekend}"
        )


def is_osm_eenrichting(row: Any) -> bool:
    for kolom in ("oneway:bicycle", "oneway"):
        if kolom not in row.index:
            continue

        waarden = parse_highway_waarde(row[kolom])
        if any(waarde in {"yes", "true", "1"} for waarde in waarden):
            return True
        if any(waarde in {"no", "false", "0"} for waarde in waarden):
            return False

    return False


def voeg_osm_richting_toe(selectie: Any, standaard_tweerichting: bool) -> Any:
    # OSM-aanvullingen zijn accesspaden; zonder expliciete eenrichtingstag
    # nemen we twee richtingen aan om bereikbaarheid niet te onderschatten.
    selectie["heen_toegestaan"] = True
    if standaard_tweerichting:
        selectie["terug_toegestaan"] = ~selectie.apply(is_osm_eenrichting, axis=1)
    else:
        selectie["terug_toegestaan"] = False
    selectie["beide_richtingen_toegestaan"] = (
        selectie["heen_toegestaan"] & selectie["terug_toegestaan"]
    )

    return selectie


def selecteer_osm_edges(
    gpd: Any,
    osm_edges_pad: Path,
    highway_filter: Callable[[Any], bool],
    verkeerstype: str,
    standaard_tweerichting: bool,
) -> Any:
    if not osm_edges_pad.exists():
        raise FileNotFoundError(f"OSM-bestand ontbreekt: {osm_edges_pad}")

    osm = gpd.read_file(osm_edges_pad)
    if osm.crs is None:
        raise ValueError(f"CRS ontbreekt in OSM-bestand: {osm_edges_pad}")
    controleer_osm_kolommen(osm, osm_edges_pad)

    selectie = osm.loc[osm["highway"].map(highway_filter)].copy()
    selectie = selectie.to_crs("EPSG:4326")
    selectie["verkeerstype"] = verkeerstype
    selectie = voeg_osm_richting_toe(selectie, standaard_tweerichting)
    selectie = voeg_reiskosten_toe(selectie, verkeerstype)

    return selectie


def selecteer_osm_looproutes(gpd: Any, osm_walk_edges_pad: Path) -> Any:
    return selecteer_osm_edges(
        gpd,
        osm_walk_edges_pad,
        heeft_osm_loop_highway,
        "voetganger_osm",
        standaard_tweerichting=True,
    )


def selecteer_osm_fietsroutes(gpd: Any, osm_bike_edges_pad: Path) -> Any:
    return selecteer_osm_edges(
        gpd,
        osm_bike_edges_pad,
        heeft_osm_fiets_highway,
        "fiets_osm",
        standaard_tweerichting=True,
    )


def schrijf_looproutes_samenvoeging(
    gpd: Any,
    voetganger_gdf: Any,
    osm_walk_edges_pad: Path,
    output_map: Path,
) -> Path:
    import pandas as pd

    print("Selecteer OSM-looproutes...")
    osm_looproutes = selecteer_osm_looproutes(gpd, osm_walk_edges_pad)

    print("Voeg volledige OSM-looproute selectie toe aan de voetgangerlaag...")
    osm_aanvulling = osm_looproutes.copy()
    osm_aanvulling["verkeerstype"] = "voetganger_osm_aanvulling"

    voetganger_merge = voetganger_gdf.to_crs("EPSG:4326")
    osm_merge = osm_aanvulling.to_crs("EPSG:4326")
    gecombineerd = gpd.GeoDataFrame(
        pd.concat([voetganger_merge, osm_merge], ignore_index=True),
        crs="EPSG:4326",
    )
    gecombineerd["verkeerstype"] = "voetganger_osm"
    gecombineerd = voeg_reiskosten_toe(gecombineerd, "voetganger_osm")
    gecombineerd_pad = output_map / "voetganger_osm.json"
    schrijf_geojson_met_unieke_feature_ids(
        maak_exportklaar(gecombineerd),
        gecombineerd_pad,
    )

    return gecombineerd_pad


def schrijf_fietsroutes_samenvoeging(
    gpd: Any,
    fiets_gdf: Any,
    osm_bike_edges_pad: Path,
    output_map: Path,
) -> Path:
    import pandas as pd

    print("Selecteer OSM-fietsroutes...")
    osm_fietsroutes = selecteer_osm_fietsroutes(gpd, osm_bike_edges_pad)

    print("Voeg OSM-fietsselectie toe aan de fietslaag...")
    osm_aanvulling = osm_fietsroutes.copy()
    osm_aanvulling["verkeerstype"] = "fiets_osm_aanvulling"

    fiets_merge = fiets_gdf.to_crs("EPSG:4326")
    osm_merge = osm_aanvulling.to_crs("EPSG:4326")
    gecombineerd = gpd.GeoDataFrame(
        pd.concat([fiets_merge, osm_merge], ignore_index=True),
        crs="EPSG:4326",
    )
    gecombineerd["verkeerstype"] = "fiets_osm"
    gecombineerd = voeg_reiskosten_toe(gecombineerd, "fiets_osm")
    gecombineerd_pad = output_map / "fiets_osm.json"
    schrijf_geojson_met_unieke_feature_ids(
        maak_exportklaar(gecombineerd),
        gecombineerd_pad,
    )

    return gecombineerd_pad
