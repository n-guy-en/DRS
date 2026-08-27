"""Netwerkroutes voor pandstromen uit de bereikbaarheidsrun."""

from __future__ import annotations

import importlib
import sys
from ast import literal_eval

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.geometry import LineString, Point

from .invoer import panden_pad
from .instellingen import BASE_DIR, CRS_RD, current_config, voorziening


if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


bereikbaarheid_config = importlib.import_module(
    "5_bereikbaarheid.helpers.instellingen"
)
config = current_config()
bereikbaarheid_config.configure(config.naam, config.onderwijsniveau)
bereikbaarheid_netwerk = importlib.import_module(
    "5_bereikbaarheid.helpers.netwerk"
)
bereikbaarheid_auto = importlib.import_module(
    "5_bereikbaarheid.helpers.auto"
)
bereikbaarheid_ov = importlib.import_module(
    "5_bereikbaarheid.helpers.ov"
)


NAAM = voorziening()

def reistijd_kolom(modus: str) -> str:
    return f"reistijd_{NAAM}_{modus}_min"


SNAP_METER_PER_MIN = {
    "lopen": bereikbaarheid_config.WANDEL_METER_PER_MIN,
    "fiets": bereikbaarheid_config.FIETS_METER_PER_MIN,
    "auto": bereikbaarheid_config.AUTO_SNAP_METER_PER_MIN,
}

NETWERK_NAAM = {
    "lopen": "voetganger_osm",
    "fiets": "fiets_osm",
    "auto": "personenauto",
}

OV_ACCESS_MODUS = {
    "ov_lopen": "lopen",
    "ov_fiets": "fiets",
}


def bouw_edge_lookup(netwerk):
    edge_lookup = {}
    for edge in netwerk.edges.itertuples(index=False):
        edge_lookup.setdefault((edge.u, edge.v), edge)
        edge_lookup.setdefault((edge.v, edge.u), edge)
    return edge_lookup


def ontbrekende_node(waarde) -> bool:
    if waarde is None:
        return True
    try:
        return bool(pd.isna(waarde))
    except (TypeError, ValueError):
        return False


def parse_node(waarde):
    if ontbrekende_node(waarde):
        return None
    if isinstance(waarde, tuple):
        return waarde
    if isinstance(waarde, str):
        tekst = waarde.strip()
        if tekst.startswith("(") and tekst.endswith(")"):
            try:
                node = literal_eval(tekst)
            except (SyntaxError, ValueError):
                return waarde
            if isinstance(node, tuple) and len(node) == 2:
                return tuple(float(deel) for deel in node)
    return waarde


def route_geometrie_tussen_nodes(pad_nodes: list, edge_lookup: dict) -> list[dict]:
    records = []
    for volgorde, (van, naar) in enumerate(zip(pad_nodes, pad_nodes[1:]), start=1):
        edge = edge_lookup.get((van, naar))
        if edge is None:
            geom = LineString([Point(van), Point(naar)])
            reistijd = pd.NA
            edge_id = pd.NA
        else:
            geom = edge.geometry
            if getattr(edge, "u") != van:
                geom = LineString(list(geom.coords)[::-1])
            reistijd = edge.edge_reistijd_min
            edge_id = edge.edge_id
        records.append(
            {
                "route_order": volgorde,
                "edge_id": edge_id,
                "segment_type": "netwerk",
                "segment_lengte_meter": round(float(geom.length), 2),
                "reistijd_min": reistijd,
                "geometry": geom,
            }
        )
    return records


def route_naar_target(
    start: gpd.GeoDataFrame,
    target: gpd.GeoDataFrame,
    target_snap: pd.DataFrame,
    netwerk,
    modus: str,
    target_idx: int,
    edge_lookup: dict,
) -> gpd.GeoDataFrame:
    if start.empty or target.empty or target_idx not in target_snap.index:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    start_rij = start.iloc[0]
    bron_node = start_rij.get("pand_node")
    doelkosten = bereikbaarheid_netwerk.doelkosten_vanaf_edge_snap(
        target_snap.loc[[target_idx]],
        "doel",
        netwerk.snap_meter_per_min,
    )
    if doelkosten.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    doelrij = doelkosten.loc[target_idx]
    start_kandidaten = []
    if not ontbrekende_node(bron_node):
        start_kandidaten.append((bron_node, 0.0))
    elif {"pand_u", "pand_v", "pand_edge_lengte_meter", "pand_edge_reistijd_min"} <= set(
        start.columns
    ):
        lengte = pd.to_numeric(
            pd.Series([start_rij.get("pand_edge_lengte_meter")]),
            errors="coerce",
        ).iloc[0]
        reistijd = pd.to_numeric(
            pd.Series([start_rij.get("pand_edge_reistijd_min")]),
            errors="coerce",
        ).iloc[0]
        positie = pd.to_numeric(
            pd.Series([start_rij.get("pand_positie_meter")]),
            errors="coerce",
        ).iloc[0]
        snap_meter = pd.to_numeric(
            pd.Series([start_rij.get("pand_snap_meter")]),
            errors="coerce",
        ).iloc[0]
        snap_kosten = 0.0 if pd.isna(snap_meter) else float(snap_meter) / netwerk.snap_meter_per_min
        if pd.notna(lengte) and lengte > 0 and pd.notna(reistijd) and pd.notna(positie):
            fractie = float(positie) / float(lengte)
            if bool(start_rij.get("pand_heen_toegestaan", False)):
                start_kandidaten.append(
                    (
                        parse_node(start_rij.get("pand_v")),
                        (1 - fractie) * float(reistijd) + snap_kosten,
                    )
                )
            if bool(start_rij.get("pand_terug_toegestaan", False)):
                start_kandidaten.append(
                    (
                        parse_node(start_rij.get("pand_u")),
                        fractie * float(reistijd) + snap_kosten,
                    )
                )

    start_kandidaten = [
        (node, kosten)
        for node, kosten in start_kandidaten
        if not ontbrekende_node(node) and pd.notna(kosten)
    ]
    if not start_kandidaten:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    kandidaten = []
    for node_kolom, kosten_kolom in [
        ("doel_u", "doel_kosten_vanaf_u_min"),
        ("doel_v", "doel_kosten_vanaf_v_min"),
    ]:
        doel_node = doelrij.get(node_kolom)
        doel_kosten = doelrij.get(kosten_kolom)
        if ontbrekende_node(doel_node) or pd.isna(doel_kosten):
            continue
        for start_node, start_kosten in start_kandidaten:
            try:
                pad_nodes = nx.shortest_path(
                    netwerk.graph,
                    source=start_node,
                    target=doel_node,
                    weight="weight",
                )
                netwerkkosten = nx.path_weight(netwerk.graph, pad_nodes, weight="weight")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            totale_kosten = (
                float(start_kosten)
                + float(netwerkkosten)
                + float(doel_kosten)
            )
            kandidaten.append((totale_kosten, pad_nodes, start_node, doel_node))

    if not kandidaten:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    _, pad_nodes, gekozen_start_node, laatste_node = min(
        kandidaten,
        key=lambda kandidaat: kandidaat[0],
    )
    start_rij = start_rij.copy()
    start_rij["pand_node"] = gekozen_start_node
    records = route_geometrie_tussen_nodes(pad_nodes, edge_lookup)
    records = bereikbaarheid_netwerk.voeg_start_snap_segmenten_toe(
        records,
        start_rij,
        netwerk,
    )
    records = bereikbaarheid_netwerk.voeg_target_snap_segmenten_toe(
        records,
        target.iloc[0],
        target_snap.loc[target_idx],
        netwerk,
        laatste_node,
    )
    if not records:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    route = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)
    route["modus"] = modus
    route["pand_id"] = start_rij.get("pand_id", "")
    route["pand_idx"] = start_rij.name
    tijd_kolom = reistijd_kolom(modus)
    route["route_reistijd_min"] = start_rij.get(tijd_kolom, pd.NA)
    route["target_idx"] = target_idx
    return bereikbaarheid_netwerk.voeg_route_lengte_toe(route)


def lees_bereikbaarheids_panden(modus: str) -> gpd.GeoDataFrame:
    panden = gpd.read_file(panden_pad(modus)).to_crs(CRS_RD)
    if "pand_node" in panden.columns:
        panden["pand_node"] = panden["pand_node"].apply(parse_node)
    return panden


def bouw_ov_basis_graph(stops: gpd.GeoDataFrame, max_transfer_meter: float):
    graph = nx.DiGraph()
    route_edges = bereikbaarheid_ov.lees_ov_route_edges(stops)
    for ov_edge in route_edges.itertuples(index=False):
        attrs = {
            "weight": float(ov_edge.route_travel_time_min),
            "segment_type": "ov_rit",
            "edge_id": getattr(ov_edge, "edge_id", pd.NA),
            "reistijd_min": float(ov_edge.route_travel_time_min),
            "geometry": ov_edge.geometry,
            "mode": getattr(ov_edge, "mode", ""),
            "operator": getattr(ov_edge, "operator", ""),
            "line_id": getattr(ov_edge, "line_id", ""),
            "route_id": getattr(ov_edge, "route_id", ""),
            "from_stop_id": getattr(ov_edge, "from_stop_id", ""),
            "from_stop_name": getattr(ov_edge, "from_stop_name", ""),
            "to_stop_id": getattr(ov_edge, "to_stop_id", ""),
            "to_stop_name": getattr(ov_edge, "to_stop_name", ""),
        }
        bereikbaarheid_ov.voeg_edge_met_attrs_toe(
            graph,
            str(ov_edge.from_node_id),
            str(ov_edge.to_node_id),
            attrs,
        )

    stops_index = stops.set_index(stops["node_id"].astype(str), drop=False)
    for van, naar, kosten in bereikbaarheid_ov.ov_transfer_edges(
        stops,
        max_transfer_meter,
    ):
        van = str(van)
        naar = str(naar)
        if van not in stops_index.index or naar not in stops_index.index:
            continue
        van_geom = stops_index.at[van, "geometry"]
        naar_geom = stops_index.at[naar, "geometry"]
        if van_geom is None or naar_geom is None or van_geom.is_empty or naar_geom.is_empty:
            continue
        bereikbaarheid_ov.voeg_edge_met_attrs_toe(
            graph,
            van,
            naar,
            {
                "weight": float(kosten),
                "segment_type": "ov_transfer_lopen",
                "edge_id": pd.NA,
                "reistijd_min": float(kosten),
                "geometry": LineString([van_geom, naar_geom]),
            },
        )
    return graph


def ov_graph_naar_voorziening(
    basis_graph,
    stops,
    voorzieningen,
    voorziening_idx,
    loopnetwerk,
    max_snap_meter,
):
    graph = basis_graph.copy()
    graph.add_node(bereikbaarheid_config.VIRTUAL_DOEL)
    egress_info = bereikbaarheid_ov.ov_egress_naar_voorziening_info(
        stops,
        voorzieningen.loc[[voorziening_idx]],
        loopnetwerk,
        max_snap_meter,
    )
    for node_id, rij in egress_info.iterrows():
        bereikbaarheid_ov.voeg_edge_met_attrs_toe(
            graph,
            str(node_id),
            bereikbaarheid_config.VIRTUAL_DOEL,
            {
                "weight": float(rij["egress_tijd_min"]),
                "segment_type": f"ov_egress_naar_{NAAM}",
                "reistijd_min": float(rij["egress_tijd_min"]),
            },
        )
    return graph


def bouw_netwerken(modi: set[str]):
    netwerken = {}
    for modus in sorted(modi):
        if modus not in NETWERK_NAAM:
            continue
        netwerken[modus] = bereikbaarheid_netwerk.lees_verkeersnetwerk(
            NETWERK_NAAM[modus],
            SNAP_METER_PER_MIN[modus],
        )
    return netwerken
