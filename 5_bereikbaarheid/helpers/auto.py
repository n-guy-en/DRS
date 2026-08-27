"""Autobereikbaarheid via parkeren en lopen naar voorziening."""

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

from .instellingen import (
    BASE_DIR,
    CRS_RD,
    VIRTUAL_DOEL,
    WANDEL_METER_PER_MIN,
    parkeer_idx_kolom,
    parkeer_loop_bron_kolom,
    parkeer_loop_kolom,
    parkeer_luchtlijn_idx_kolom,
    parkeer_luchtlijn_meter_kolom,
    voorzieningen_label,
    verkeersnetwerk_pad,
)
from importlib import import_module

puntrepresentatie = import_module("5_bereikbaarheid.helpers.geometrie").puntrepresentatie
from .netwerk import (
    Routenetwerk,
    afstanden_en_target_idx_naar_targets,
    doelkosten_vanaf_edge_snap,
    graph_met_doelen,
    koppel_panden_aan_afstanden,
    routekosten_vanaf_edge_snap,
    snap_points_naar_edges,
    voeg_voorzieninggegevens_toe,
)


def lees_parkeerdoelen() -> gpd.GeoDataFrame:
    parkeren_pad = verkeersnetwerk_pad("parkeren")
    parkeergarage_pad = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "4_netwerk"
        / "verkeerstypen"
        / "parkeergarage.geojson"
    )

    print(f"Lees parkeren: {parkeren_pad}")
    parkeren = gpd.read_file(parkeren_pad).to_crs(CRS_RD)
    parkeren = puntrepresentatie(parkeren)
    parkeren["parkeer_bron"] = "NWB_parkeren"

    parkeerdoelen = [parkeren]

    if parkeergarage_pad.exists():
        print(f"Lees parkeergarages: {parkeergarage_pad}")
        parkeergarages = gpd.read_file(parkeergarage_pad).to_crs(CRS_RD)
        parkeergarages = puntrepresentatie(parkeergarages)
        parkeergarages["parkeer_bron"] = "RDW_parkeergarage"
        parkeerdoelen.append(parkeergarages)
    else:
        print(f"Geen parkeergaragelaag gevonden: {parkeergarage_pad}")

    parkeerdoelen = gpd.GeoDataFrame(
        pd.concat(parkeerdoelen, ignore_index=True, sort=False),
        geometry="geometry",
        crs=CRS_RD,
    )

    print(f"Parkeerdoelen totaal: {len(parkeerdoelen)}")
    return parkeerdoelen


def bereken_parkeer_targets(
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
    max_parkeer_loop_min: float,
) -> gpd.GeoDataFrame:
    parkeren = lees_parkeerdoelen()

    voorziening_snap = snap_points_naar_edges(
        voorzieningen,
        loopnetwerk,
        "doel",
        max_snap_meter,
    )
    loop_graph = graph_met_doelen(
        loopnetwerk,
        voorziening_snap,
        "doel",
    )
    loop_afstanden = nx.single_source_dijkstra_path_length(
        loop_graph.reverse(copy=True),
        VIRTUAL_DOEL,
        weight="weight",
    )

    parkeer_snap = snap_points_naar_edges(
        parkeren,
        loopnetwerk,
        "parkeer_loop",
        max_snap_meter,
    )
    parkeer_route = routekosten_vanaf_edge_snap(
        parkeer_snap,
        "parkeer_loop",
        loop_afstanden,
        loopnetwerk.snap_meter_per_min,
    )
    parkeren = parkeren.join(parkeer_snap)
    parkeren[parkeer_loop_kolom()] = parkeer_route[
        "parkeer_loop_totale_reistijd_min"
    ]
    netwerk_voorziening_idx = []
    for node in parkeer_route["parkeer_loop_node"]:
        if node is None or (isinstance(node, float) and pd.isna(node)):
            netwerk_voorziening_idx.append(np.nan)
            continue
        try:
            pad_nodes = nx.shortest_path(
                loop_graph,
                source=node,
                target=VIRTUAL_DOEL,
                weight="weight",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            netwerk_voorziening_idx.append(np.nan)
            continue
        netwerk_voorziening_idx.append(
            loop_graph[pad_nodes[-2]][VIRTUAL_DOEL].get("target_idx", np.nan)
        )
    parkeren[parkeer_idx_kolom()] = netwerk_voorziening_idx

    max_loopafstand_meter = max_parkeer_loop_min * WANDEL_METER_PER_MIN
    parkeren_voor_join = gpd.GeoDataFrame(
        {"_idx": parkeren.index.to_numpy()},
        geometry=parkeren.geometry.to_numpy(),
        crs=CRS_RD,
    )
    voorzieningen_voor_join = gpd.GeoDataFrame(
        {"_voorziening_idx": voorzieningen.index.to_numpy()},
        geometry=voorzieningen.to_crs(CRS_RD).geometry.to_numpy(),
        crs=CRS_RD,
    )
    nearest_voorziening = gpd.sjoin_nearest(
        parkeren_voor_join,
        voorzieningen_voor_join,
        how="left",
        max_distance=max_loopafstand_meter,
        distance_col=parkeer_luchtlijn_meter_kolom(),
    )
    nearest_voorziening = nearest_voorziening.sort_values(
        ["_idx", parkeer_luchtlijn_meter_kolom()],
        na_position="last",
    )
    nearest_voorziening = nearest_voorziening.drop_duplicates("_idx", keep="first")
    nearest_voorziening = nearest_voorziening.set_index("_idx").reindex(parkeren.index)
    parkeren[parkeer_luchtlijn_idx_kolom()] = nearest_voorziening[
        "_voorziening_idx"
    ].to_numpy()
    parkeren[parkeer_luchtlijn_meter_kolom()] = nearest_voorziening[
        parkeer_luchtlijn_meter_kolom()
    ].to_numpy()
    parkeren[parkeer_loop_bron_kolom()] = "loopnetwerk"
    parkeren.loc[
        parkeren[parkeer_loop_kolom()].isna(),
        parkeer_loop_bron_kolom(),
    ] = ""
    fallback_tijd_min = (
        parkeren[parkeer_luchtlijn_meter_kolom()] / WANDEL_METER_PER_MIN
    )
    fallback_mask = (
        fallback_tijd_min.notna()
        & (
            parkeren[parkeer_loop_kolom()].isna()
            | (fallback_tijd_min < parkeren[parkeer_loop_kolom()])
        )
    )
    parkeren.loc[fallback_mask, parkeer_loop_kolom()] = (
        fallback_tijd_min.loc[fallback_mask]
    )
    parkeren.loc[fallback_mask, parkeer_idx_kolom()] = parkeren.loc[
        fallback_mask,
        parkeer_luchtlijn_idx_kolom(),
    ]
    parkeren.loc[
        fallback_mask,
        parkeer_loop_bron_kolom(),
    ] = "luchtlijn_fallback"

    parkeren.loc[
        parkeren[parkeer_loop_kolom()].isna()
        | (parkeren[parkeer_loop_kolom()] > max_parkeer_loop_min),
        parkeer_loop_kolom(),
    ] = np.nan

    parkeren = parkeren[parkeren[parkeer_loop_kolom()].notna()].copy()
    parkeren[parkeer_loop_kolom()] = parkeren[
        parkeer_loop_kolom()
    ].round(2)
    print(f"Parkeerdoelen binnen loopgrens: {len(parkeren)}")
    if parkeren.empty:
        raise ValueError(
            f"Geen parkeerlocaties gekoppeld aan {voorzieningen_label()}."
        )
    return parkeren

def bereken_auto(
    panden: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    autonetwerk: Routenetwerk,
    loopnetwerk: Routenetwerk,
    norm_min: float,
    max_snap_meter: float,
    max_parkeer_loop_min: float,
    parkeer_targets: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    if parkeer_targets is None:
        parkeer_targets = bereken_parkeer_targets(
            voorzieningen,
            loopnetwerk,
            max_snap_meter,
            max_parkeer_loop_min,
        )
    parkeer_auto_snap = snap_points_naar_edges(
        parkeer_targets,
        autonetwerk,
        "doel",
        max_snap_meter,
    )
    parkeer_targets = parkeer_targets.join(parkeer_auto_snap)
    doel_snap = doelkosten_vanaf_edge_snap(
        parkeer_targets,
        "doel",
        autonetwerk.snap_meter_per_min,
    )
    doel_snap["doel_kosten_vanaf_u_min"] = (
        doel_snap["doel_kosten_vanaf_u_min"]
        + parkeer_targets[parkeer_loop_kolom()]
    )
    doel_snap["doel_kosten_vanaf_v_min"] = (
        doel_snap["doel_kosten_vanaf_v_min"]
        + parkeer_targets[parkeer_loop_kolom()]
    )
    afstanden, target_idx_per_node = afstanden_en_target_idx_naar_targets(
        autonetwerk,
        doel_snap,
        "doel",
    )
    resultaat = koppel_panden_aan_afstanden(
        panden,
        autonetwerk,
        afstanden,
        "auto",
        norm_min,
        max_snap_meter,
        target_idx_per_node=target_idx_per_node,
    )
    resultaat = resultaat.rename(columns={"target_idx_auto": "parkeer_idx_auto"})
    resultaat["target_idx_auto"] = resultaat["parkeer_idx_auto"].map(
        parkeer_targets[parkeer_idx_kolom()]
    )
    resultaat = voeg_voorzieninggegevens_toe(
        resultaat,
        voorzieningen,
        "target_idx_auto",
    )
    return resultaat
