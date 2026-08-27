"""Netwerkopbouw, snapping en routekosten."""

from dataclasses import dataclass

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
from shapely.ops import substring

from .instellingen import (
    CRS_RD,
    VIRTUAL_DOEL,
    bereikbaar_kolom as maak_bereikbaar_kolom,
    binnen_kolom as maak_binnen_kolom,
    netwerk_tijd_kolom,
    norm_min_voor_panden,
    norm_kolom,
    parkeer_loop_kolom,
    tijd_kolom as maak_tijd_kolom,
    verkeersnetwerk_pad,
    voorziening_id_kolom,
    voorziening_lat_kolom,
    voorziening_lon_kolom,
    voorziening_resultaat_kolom,
)
from importlib import import_module

_geometrie = import_module("5_bereikbaarheid.helpers.geometrie")
lijnstukken = _geometrie.lijnstukken
node_key = _geometrie.node_key
puntrepresentatie = _geometrie.puntrepresentatie


@dataclass
class Routenetwerk:
    naam: str
    graph: nx.DiGraph
    nodes: gpd.GeoDataFrame
    edges: gpd.GeoDataFrame
    snap_meter_per_min: float


def controleer_kolommen(
    dataframe: gpd.GeoDataFrame | pd.DataFrame,
    naam: str,
    verplichte_kolommen: list[str],
) -> None:
    ontbrekend = sorted(set(verplichte_kolommen) - set(dataframe.columns))
    if ontbrekend:
        raise ValueError(f"Kolommen ontbreken in {naam}: {ontbrekend}")


def voeg_edge_min_toe(graph: nx.DiGraph, u, v, gewicht: float) -> None:
    if pd.isna(gewicht) or gewicht < 0:
        return
    if graph.has_edge(u, v):
        if gewicht < graph[u][v]["weight"]:
            graph[u][v]["weight"] = gewicht
    else:
        graph.add_edge(u, v, weight=float(gewicht))


def lees_verkeersnetwerk(naam: str, snap_meter_per_min: float) -> Routenetwerk:
    pad = verkeersnetwerk_pad(naam)
    print(f"Lees netwerk {naam}: {pad}")
    edges = gpd.read_file(pad).to_crs(CRS_RD)
    controleer_kolommen(
        edges,
        pad.name,
        ["heen_toegestaan", "terug_toegestaan", "reistijd_min", "geometry"],
    )

    graph = nx.DiGraph()
    nodes = {}
    edge_records = []

    for rij in edges.itertuples(index=False):
        geom = getattr(rij, "geometry")
        delen = lijnstukken(geom)
        if not delen:
            continue

        reistijd = getattr(rij, "reistijd_min", np.nan)
        lengte = getattr(rij, "lengte_meter", np.nan)
        if pd.isna(reistijd):
            if pd.isna(lengte):
                lengte = sum(deel.length for deel in delen)
            reistijd = float(lengte) / snap_meter_per_min
        else:
            reistijd = float(reistijd)

        totale_lengte = sum(max(deel.length, 0.0) for deel in delen)
        if totale_lengte <= 0:
            continue

        heen = bool(getattr(rij, "heen_toegestaan", True))
        terug = bool(getattr(rij, "terug_toegestaan", True))

        for deel in delen:
            coords = list(deel.coords)
            if len(coords) < 2:
                continue
            start = Point(coords[0])
            eind = Point(coords[-1])
            u = node_key(start)
            v = node_key(eind)
            nodes.setdefault(u, start)
            nodes.setdefault(v, eind)
            deel_reistijd = reistijd * (deel.length / totale_lengte)

            if heen:
                voeg_edge_min_toe(graph, u, v, deel_reistijd)
            if terug:
                voeg_edge_min_toe(graph, v, u, deel_reistijd)
            edge_records.append(
                {
                    "edge_id": len(edge_records),
                    "u": u,
                    "v": v,
                    "edge_lengte_meter": float(deel.length),
                    "edge_reistijd_min": float(deel_reistijd),
                    "heen_toegestaan": heen,
                    "terug_toegestaan": terug,
                    "geometry": deel,
                }
            )

    nodes_gdf = gpd.GeoDataFrame(
        {"node": list(nodes.keys())},
        geometry=list(nodes.values()),
        crs=CRS_RD,
    )
    edges_gdf = gpd.GeoDataFrame(edge_records, geometry="geometry", crs=CRS_RD)
    print(f"Netwerk {naam}: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    return Routenetwerk(naam, graph, nodes_gdf, edges_gdf, snap_meter_per_min)


def snap_points_naar_edges(
    points: gpd.GeoDataFrame,
    netwerk: Routenetwerk,
    prefix: str,
    max_snap_meter: float | None = None,
) -> pd.DataFrame:
    points_rd = puntrepresentatie(points.to_crs(CRS_RD))
    punten = gpd.GeoDataFrame(
        {"_idx": points_rd.index.to_numpy()},
        geometry=points_rd.geometry.to_numpy(),
        crs=CRS_RD,
    )
    nearest = gpd.sjoin_nearest(
        punten,
        netwerk.edges,
        how="left",
        max_distance=max_snap_meter,
        distance_col=f"{prefix}_snap_meter",
    )
    nearest = nearest.sort_values(["_idx", f"{prefix}_snap_meter"], na_position="last")
    nearest = nearest.drop_duplicates("_idx", keep="first")
    nearest_indexed = nearest.set_index("_idx").reindex(points.index)

    resultaat = pd.DataFrame(index=points.index)
    resultaat[f"{prefix}_edge_id"] = nearest_indexed["edge_id"].to_numpy()
    resultaat[f"{prefix}_u"] = nearest_indexed["u"].to_numpy()
    resultaat[f"{prefix}_v"] = nearest_indexed["v"].to_numpy()
    resultaat[f"{prefix}_edge_lengte_meter"] = nearest_indexed[
        "edge_lengte_meter"
    ].to_numpy()
    resultaat[f"{prefix}_edge_reistijd_min"] = nearest_indexed[
        "edge_reistijd_min"
    ].to_numpy()
    resultaat[f"{prefix}_heen_toegestaan"] = nearest_indexed[
        "heen_toegestaan"
    ].to_numpy()
    resultaat[f"{prefix}_terug_toegestaan"] = nearest_indexed[
        "terug_toegestaan"
    ].to_numpy()
    resultaat[f"{prefix}_snap_meter"] = nearest_indexed[f"{prefix}_snap_meter"].to_numpy()

    posities = []
    punten_reindexed = points_rd.geometry.reindex(points.index)
    for punt, edge_idx in zip(punten_reindexed, nearest_indexed["index_right"]):
        if pd.isna(edge_idx) or punt is None or punt.is_empty:
            posities.append(np.nan)
            continue
        geom = netwerk.edges.geometry.iloc[int(edge_idx)]
        posities.append(float(geom.project(punt)))

    resultaat[f"{prefix}_positie_meter"] = posities
    return resultaat


def snap_point_naar_beste_bereikbare_edge(
    punt,
    netwerk: Routenetwerk,
    afstand_per_node: dict,
    prefix: str,
    max_snap_meter: float,
) -> tuple[dict, dict] | None:
    kandidaten_idx = netwerk.edges.sindex.query(
        punt.buffer(max_snap_meter),
        predicate="intersects",
    )
    if len(kandidaten_idx) == 0:
        return None

    beste_snap = None
    beste_route = None
    beste_tijd = np.inf

    for edge_idx in kandidaten_idx:
        edge = netwerk.edges.iloc[int(edge_idx)]
        geom = edge.geometry
        if geom is None or geom.is_empty:
            continue

        snap_meter = float(geom.distance(punt))
        if snap_meter > max_snap_meter:
            continue

        lengte = float(edge.edge_lengte_meter)
        reistijd = float(edge.edge_reistijd_min)
        if lengte <= 0 or pd.isna(reistijd):
            continue

        positie = float(geom.project(punt))
        heen = bool(edge.heen_toegestaan)
        terug = bool(edge.terug_toegestaan)
        afstand_u = afstand_per_node.get(edge.u)
        afstand_v = afstand_per_node.get(edge.v)
        fractie = positie / lengte
        snap_kosten = snap_meter / netwerk.snap_meter_per_min

        opties = []
        if terug and afstand_u is not None:
            opties.append(
                (
                    fractie * reistijd + afstand_u + snap_kosten,
                    edge.u,
                    fractie * reistijd + afstand_u,
                )
            )
        if heen and afstand_v is not None:
            opties.append(
                (
                    (1 - fractie) * reistijd + afstand_v + snap_kosten,
                    edge.v,
                    (1 - fractie) * reistijd + afstand_v,
                )
            )
        if not opties:
            continue

        totale_tijd, beste_node, netwerk_tijd = min(opties, key=lambda optie: optie[0])
        if totale_tijd >= beste_tijd:
            continue

        beste_tijd = totale_tijd
        beste_snap = {
            f"{prefix}_edge_id": edge.edge_id,
            f"{prefix}_u": edge.u,
            f"{prefix}_v": edge.v,
            f"{prefix}_edge_lengte_meter": lengte,
            f"{prefix}_edge_reistijd_min": reistijd,
            f"{prefix}_heen_toegestaan": heen,
            f"{prefix}_terug_toegestaan": terug,
            f"{prefix}_snap_meter": snap_meter,
            f"{prefix}_positie_meter": positie,
        }
        beste_route = {
            f"{prefix}_node": beste_node,
            f"{prefix}_netwerkreistijd_min": netwerk_tijd,
            f"{prefix}_snap_kosten_min": snap_kosten,
            f"{prefix}_totale_reistijd_min": totale_tijd,
        }

    if beste_snap is None or beste_route is None:
        return None

    return beste_snap, beste_route


def verbeter_pand_snaps_boven_norm(
    panden: gpd.GeoDataFrame,
    netwerk: Routenetwerk,
    afstand_per_node: dict,
    pand_snap: pd.DataFrame,
    pand_route: pd.DataFrame,
    max_snap_meter: float,
    norm_min: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if max_snap_meter is None:
        return pand_snap, pand_route

    huidige_tijd = pd.to_numeric(
        pand_route["pand_totale_reistijd_min"],
        errors="coerce",
    )
    te_verbeteren = (
        pand_route["pand_netwerkreistijd_min"].isna()
        | huidige_tijd.gt(float(norm_min))
    )
    if not te_verbeteren.any():
        return pand_snap, pand_route

    panden_rd = puntrepresentatie(panden.to_crs(CRS_RD))
    verbeterd = 0
    for idx in panden_rd.index[te_verbeteren]:
        punt = panden_rd.geometry.loc[idx]
        if punt is None or punt.is_empty:
            continue

        beste = snap_point_naar_beste_bereikbare_edge(
            punt,
            netwerk,
            afstand_per_node,
            "pand",
            max_snap_meter,
        )
        if beste is None:
            continue

        verbeter_snap, verbeter_route = beste
        nieuwe_tijd = verbeter_route["pand_totale_reistijd_min"]
        oude_tijd = huidige_tijd.loc[idx]
        if pd.notna(oude_tijd) and float(nieuwe_tijd) >= float(oude_tijd):
            continue

        for kolom, waarde in verbeter_snap.items():
            pand_snap.at[idx, kolom] = waarde
        for kolom, waarde in verbeter_route.items():
            pand_route.at[idx, kolom] = waarde
        verbeterd += 1

    if verbeterd:
        print(f"Routebewuste snap verbeterde panden boven de norm: {verbeterd}")

    return pand_snap, pand_route

def doelkosten_vanaf_edge_snap(
    snap: pd.DataFrame,
    prefix: str,
    snap_meter_per_min: float,
) -> pd.DataFrame:
    lengte = pd.to_numeric(snap[f"{prefix}_edge_lengte_meter"], errors="coerce")
    reistijd = pd.to_numeric(snap[f"{prefix}_edge_reistijd_min"], errors="coerce")
    positie = pd.to_numeric(snap[f"{prefix}_positie_meter"], errors="coerce")
    snap_meter = pd.to_numeric(snap[f"{prefix}_snap_meter"], errors="coerce")
    heen = snap[f"{prefix}_heen_toegestaan"].where(
        snap[f"{prefix}_heen_toegestaan"].notna(),
        False,
    ).astype(bool)
    terug = snap[f"{prefix}_terug_toegestaan"].where(
        snap[f"{prefix}_terug_toegestaan"].notna(),
        False,
    ).astype(bool)

    fractie = positie / lengte
    kosten_vanaf_u = fractie * reistijd
    kosten_vanaf_v = (1 - fractie) * reistijd
    snap_kosten = snap_meter / snap_meter_per_min

    resultaat = snap.copy()
    resultaat[f"{prefix}_kosten_vanaf_u_min"] = np.where(
        heen,
        kosten_vanaf_u + snap_kosten,
        np.nan,
    )
    resultaat[f"{prefix}_kosten_vanaf_v_min"] = np.where(
        terug,
        kosten_vanaf_v + snap_kosten,
        np.nan,
    )
    resultaat[f"{prefix}_snap_meter"] = snap_meter
    resultaat[f"{prefix}_snap_kosten_min"] = snap_kosten
    return resultaat

def routekosten_vanaf_edge_snap(
    snap: pd.DataFrame,
    prefix: str,
    afstand_per_node: dict,
    snap_meter_per_min: float,
) -> pd.DataFrame:
    lengte = pd.to_numeric(snap[f"{prefix}_edge_lengte_meter"], errors="coerce")
    reistijd = pd.to_numeric(snap[f"{prefix}_edge_reistijd_min"], errors="coerce")
    positie = pd.to_numeric(snap[f"{prefix}_positie_meter"], errors="coerce")
    snap_meter = pd.to_numeric(snap[f"{prefix}_snap_meter"], errors="coerce")
    heen = snap[f"{prefix}_heen_toegestaan"].where(
        snap[f"{prefix}_heen_toegestaan"].notna(),
        False,
    ).astype(bool)
    terug = snap[f"{prefix}_terug_toegestaan"].where(
        snap[f"{prefix}_terug_toegestaan"].notna(),
        False,
    ).astype(bool)

    afstand_u = snap[f"{prefix}_u"].map(afstand_per_node)
    afstand_v = snap[f"{prefix}_v"].map(afstand_per_node)

    fractie = positie / lengte
    via_v = (1 - fractie) * reistijd + afstand_v
    via_u = fractie * reistijd + afstand_u
    via_v = via_v.where(heen)
    via_u = via_u.where(terug)

    opties = pd.concat(
        [
            via_u.rename("via_u"),
            via_v.rename("via_v"),
        ],
        axis=1,
    )
    beste_kosten = opties.min(axis=1, skipna=True)
    beste_is_u = opties["via_u"].le(opties["via_v"]) | opties["via_v"].isna()
    beste_node = snap[f"{prefix}_v"].where(~beste_is_u, snap[f"{prefix}_u"])
    beste_node = beste_node.where(beste_kosten.notna())

    resultaat = snap.copy()
    resultaat[f"{prefix}_node"] = beste_node
    resultaat[f"{prefix}_netwerkreistijd_min"] = beste_kosten
    resultaat[f"{prefix}_snap_kosten_min"] = snap_meter / snap_meter_per_min
    resultaat[f"{prefix}_totale_reistijd_min"] = (
        resultaat[f"{prefix}_netwerkreistijd_min"]
        + resultaat[f"{prefix}_snap_kosten_min"]
    )
    return resultaat

def afstanden_naar_targets(
    netwerk: Routenetwerk,
    target_snap: pd.DataFrame,
    prefix: str,
) -> dict:
    afstanden, _target_idx = afstanden_en_target_idx_naar_targets(
        netwerk,
        target_snap,
        prefix,
    )
    return afstanden

def afstanden_en_target_idx_naar_targets(
    netwerk: Routenetwerk,
    target_snap: pd.DataFrame,
    prefix: str,
) -> tuple[dict, dict]:
    graph = netwerk.graph.copy()
    graph.add_node(VIRTUAL_DOEL)

    kosten_kolommen = [
        f"{prefix}_kosten_vanaf_u_min",
        f"{prefix}_kosten_vanaf_v_min",
    ]
    if all(kolom in target_snap.columns for kolom in kosten_kolommen):
        geldig = target_snap
    else:
        geldig = doelkosten_vanaf_edge_snap(
            target_snap,
            prefix,
            netwerk.snap_meter_per_min,
        )
    route_kolommen = [
        f"{prefix}_u",
        f"{prefix}_v",
        f"{prefix}_kosten_vanaf_u_min",
        f"{prefix}_kosten_vanaf_v_min",
    ]
    extra_kolom = f"{prefix}_extra_kosten_min"
    if extra_kolom in geldig.columns:
        route_kolommen.append(extra_kolom)
    for idx, rij in geldig[route_kolommen].iterrows():
        for node, gewicht in [
            (rij[f"{prefix}_u"], rij[f"{prefix}_kosten_vanaf_u_min"]),
            (rij[f"{prefix}_v"], rij[f"{prefix}_kosten_vanaf_v_min"]),
        ]:
            if pd.isna(gewicht) or gewicht < 0:
                continue
            if graph.has_edge(node, VIRTUAL_DOEL):
                if gewicht < graph[node][VIRTUAL_DOEL]["weight"]:
                    graph[node][VIRTUAL_DOEL]["weight"] = float(gewicht)
                    graph[node][VIRTUAL_DOEL]["target_idx"] = idx
            else:
                graph.add_edge(
                    node,
                    VIRTUAL_DOEL,
                    weight=float(gewicht),
                    target_idx=idx,
                )

    if graph.in_degree(VIRTUAL_DOEL) == 0:
        raise ValueError(f"Geen geldige doelpunten gekoppeld aan {netwerk.naam}.")

    afstanden, paden = nx.single_source_dijkstra(
        graph.reverse(copy=True),
        VIRTUAL_DOEL,
        weight="weight",
    )
    target_idx_per_node = {}
    for node, pad_nodes in paden.items():
        if node == VIRTUAL_DOEL or len(pad_nodes) < 2:
            continue
        doel_node = pad_nodes[1]
        if graph.has_edge(doel_node, VIRTUAL_DOEL):
            target_idx_per_node[node] = graph[doel_node][VIRTUAL_DOEL].get(
                "target_idx",
                np.nan,
            )

    return afstanden, target_idx_per_node

def voeg_voorzieninggegevens_toe(
    resultaat: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    target_kolom: str,
) -> gpd.GeoDataFrame:
    """Voeg voorzieningkenmerken toe op basis van de gekozen target-index."""
    if target_kolom not in resultaat.columns:
        return resultaat

    voorziening_info = voorzieningen.copy()
    if voorziening_id_kolom() not in voorziening_info.columns:
        voorziening_info[voorziening_id_kolom()] = voorziening_info.index
    naam_kolom = None
    for kandidaat in [
        "name",
        "brand",
        "operator",
        "short_name",
        "VESTIGINGSNAAM",
        "INSTELLINGSNAAM",
        "naam",
    ]:
        if kandidaat in voorziening_info.columns:
            naam_kolom = kandidaat
            break
    if naam_kolom is None:
        voorziening_info[voorziening_resultaat_kolom("naam")] = (
            "Voorziening " + voorziening_info[voorziening_id_kolom()].astype(str)
        )
    else:
        voorziening_info[voorziening_resultaat_kolom("naam")] = voorziening_info[naam_kolom].fillna(
            voorziening_info[voorziening_id_kolom()].astype(str)
        )

    kolommen = [voorziening_id_kolom(), voorziening_resultaat_kolom("naam")]
    for kolom in [
        "addr:street",
        "addr:housenumber",
        "addr:city",
        "STRAATNAAM",
        "HUISNUMMER-TOEVOEGING",
        "PLAATSNAAM",
        voorziening_lon_kolom(),
        voorziening_lat_kolom(),
    ]:
        if kolom in voorziening_info.columns:
            kolommen.append(kolom)

    join_info = voorziening_info[kolommen].copy()
    join_info[voorziening_resultaat_kolom("idx")] = join_info.index
    join_info = join_info.rename(
        columns={
            voorziening_id_kolom(): voorziening_resultaat_kolom("id"),
            "addr:street": voorziening_resultaat_kolom("straat"),
            "addr:housenumber": voorziening_resultaat_kolom("huisnummer"),
            "addr:city": voorziening_resultaat_kolom("plaats"),
            "STRAATNAAM": voorziening_resultaat_kolom("straat"),
            "HUISNUMMER-TOEVOEGING": voorziening_resultaat_kolom("huisnummer"),
            "PLAATSNAAM": voorziening_resultaat_kolom("plaats"),
            voorziening_lon_kolom(): voorziening_resultaat_kolom("lon"),
            voorziening_lat_kolom(): voorziening_resultaat_kolom("lat"),
        }
    )

    resultaat = resultaat.merge(
        join_info,
        left_on=target_kolom,
        right_on=voorziening_resultaat_kolom("idx"),
        how="left",
    )
    return resultaat

def graph_met_doelen(
    netwerk: Routenetwerk,
    target_snap: pd.DataFrame,
    prefix: str,
) -> nx.DiGraph:
    graph = netwerk.graph.copy()
    graph.add_node(VIRTUAL_DOEL)
    geldig = doelkosten_vanaf_edge_snap(
        target_snap,
        prefix,
        netwerk.snap_meter_per_min,
    )
    route_kolommen = [
        f"{prefix}_u",
        f"{prefix}_v",
        f"{prefix}_kosten_vanaf_u_min",
        f"{prefix}_kosten_vanaf_v_min",
    ]
    extra_kolom = f"{prefix}_extra_kosten_min"
    if extra_kolom in geldig.columns:
        route_kolommen.append(extra_kolom)
    for idx, rij in geldig[route_kolommen].iterrows():
        extra_kosten = rij.get(f"{prefix}_extra_kosten_min", 0.0)
        if pd.isna(extra_kosten):
            extra_kosten = 0.0
        for node, gewicht in [
            (rij[f"{prefix}_u"], rij[f"{prefix}_kosten_vanaf_u_min"]),
            (rij[f"{prefix}_v"], rij[f"{prefix}_kosten_vanaf_v_min"]),
        ]:
            if pd.isna(gewicht) or gewicht < 0:
                continue
            gewicht = float(gewicht) + float(extra_kosten)
            if graph.has_edge(node, VIRTUAL_DOEL):
                if gewicht < graph[node][VIRTUAL_DOEL]["weight"]:
                    graph[node][VIRTUAL_DOEL]["weight"] = float(gewicht)
                    graph[node][VIRTUAL_DOEL]["target_idx"] = idx
            else:
                graph.add_edge(
                    node,
                    VIRTUAL_DOEL,
                    weight=float(gewicht),
                    target_idx=idx,
                )
    return graph

def route_geometrie_tussen_nodes(
    netwerk: Routenetwerk,
    pad_nodes: list,
) -> list[dict]:
    records = []
    edge_lookup = {}
    for edge in netwerk.edges.itertuples(index=False):
        edge_lookup.setdefault((edge.u, edge.v), edge)
        edge_lookup.setdefault((edge.v, edge.u), edge)

    volgorde = 1
    for van, naar in zip(pad_nodes, pad_nodes[1:]):
        if naar == VIRTUAL_DOEL:
            continue
        edge = edge_lookup.get((van, naar))
        if edge is None:
            p1 = Point(van)
            p2 = Point(naar)
            geom = LineString([p1, p2])
            reistijd = np.nan
            edge_id = pd.NA
        else:
            geom = edge.geometry
            if getattr(edge, "u") != van:
                coords = list(geom.coords)
                geom = LineString(coords[::-1])
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
        volgorde += 1
    return records

def lijn_record(route_order: int, segment_type: str, geom, reistijd_min=np.nan, edge_id=pd.NA):
    if geom is None or geom.is_empty or geom.length == 0:
        return None
    return {
        "route_order": route_order,
        "edge_id": edge_id,
        "segment_type": segment_type,
        "segment_lengte_meter": round(float(geom.length), 2),
        "reistijd_min": reistijd_min,
        "geometry": geom,
    }

def voeg_route_lengte_toe(route: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if route is None or route.empty:
        return route
    route = route.copy()
    if "segment_lengte_meter" not in route.columns:
        route["segment_lengte_meter"] = route.geometry.length
    else:
        route["segment_lengte_meter"] = route["segment_lengte_meter"].fillna(
            route.geometry.length
        )
    route["segment_lengte_meter"] = route["segment_lengte_meter"].round(2)
    route["route_lengte_meter"] = round(float(route["segment_lengte_meter"].sum()), 2)
    return route

def snap_punt_op_edge(edge_geom, positie_meter: float) -> Point | None:
    if edge_geom is None or edge_geom.is_empty or pd.isna(positie_meter):
        return None
    return edge_geom.interpolate(float(positie_meter))

def edge_deel_van_snap_naar_node(edge_geom, positie_meter: float, node) -> LineString | None:
    if edge_geom is None or edge_geom.is_empty or pd.isna(positie_meter):
        return None
    lengte = edge_geom.length
    if lengte <= 0:
        return None
    positie = max(0.0, min(float(positie_meter), lengte))
    coords = list(edge_geom.coords)
    start_node = node_key(Point(coords[0]))
    eind_node = node_key(Point(coords[-1]))
    if node == start_node:
        deel = substring(edge_geom, 0, positie)
        if deel.geom_type == "LineString":
            return LineString(list(deel.coords)[::-1])
        return None
    if node == eind_node:
        deel = substring(edge_geom, positie, lengte)
        return deel if deel.geom_type == "LineString" else None
    return None

def edge_deel_van_node_naar_snap(edge_geom, positie_meter: float, node) -> LineString | None:
    deel = edge_deel_van_snap_naar_node(edge_geom, positie_meter, node)
    if deel is None:
        return None
    return LineString(list(deel.coords)[::-1])

def voeg_start_snap_segmenten_toe(records, start_rij, netwerk: Routenetwerk):
    if "pand_edge_id" not in start_rij or pd.isna(start_rij["pand_edge_id"]):
        return records
    edge = netwerk.edges.loc[netwerk.edges["edge_id"].eq(start_rij["pand_edge_id"])]
    if edge.empty:
        return records
    edge = edge.iloc[0]
    start_geom = start_rij.geometry
    snap_punt = snap_punt_op_edge(edge.geometry, start_rij.get("pand_positie_meter"))
    route_order = 1
    extra = []
    if snap_punt is not None and start_geom is not None and not start_geom.is_empty:
        connector = LineString([start_geom, snap_punt])
        record = lijn_record(route_order, "snap_start_naar_netwerk", connector)
        if record:
            extra.append(record)
            route_order += 1
    deel = edge_deel_van_snap_naar_node(
        edge.geometry,
        start_rij.get("pand_positie_meter"),
        start_rij.get("pand_node"),
    )
    record = lijn_record(
        route_order,
        "deel_startedge_naar_netwerknode",
        deel,
        edge_id=edge.edge_id,
    )
    if record:
        extra.append(record)

    for idx, record in enumerate(records, start=len(extra) + 1):
        record["route_order"] = idx
    return extra + records

def voeg_target_snap_segmenten_toe(records, target_rij, target_snap_rij, netwerk: Routenetwerk, laatste_node):
    if target_snap_rij is None or pd.isna(target_snap_rij.get("doel_edge_id")):
        return records
    edge = netwerk.edges.loc[netwerk.edges["edge_id"].eq(target_snap_rij["doel_edge_id"])]
    if edge.empty:
        return records
    edge = edge.iloc[0]
    route_order = len(records) + 1
    deel = edge_deel_van_node_naar_snap(
        edge.geometry,
        target_snap_rij.get("doel_positie_meter"),
        laatste_node,
    )
    extra = []
    record = lijn_record(
        route_order,
        "deel_doel_edge_naar_punt",
        deel,
        edge_id=edge.edge_id,
    )
    if record:
        extra.append(record)
        route_order += 1

    snap_punt = snap_punt_op_edge(edge.geometry, target_snap_rij.get("doel_positie_meter"))
    target_geom = target_rij.geometry
    if snap_punt is not None and target_geom is not None and not target_geom.is_empty:
        connector = LineString([snap_punt, target_geom])
        record = lijn_record(route_order, "snap_netwerk_naar_doel", connector)
        if record:
            extra.append(record)
    return records + extra

def voorbeeldroute_naar_targets(
    panden_met_resultaat: gpd.GeoDataFrame,
    targets: gpd.GeoDataFrame,
    netwerk: Routenetwerk,
    modus: str,
    max_snap_meter: float,
    random_state: int = 42,
) -> gpd.GeoDataFrame:
    tijd_kolom = maak_tijd_kolom(modus)
    kandidaten = panden_met_resultaat[panden_met_resultaat[tijd_kolom].notna()].copy()
    if kandidaten.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    binnen_kolom = maak_binnen_kolom(modus)
    if binnen_kolom in kandidaten.columns and kandidaten[binnen_kolom].astype(bool).any():
        kandidaten = kandidaten[kandidaten[binnen_kolom].astype(bool)].copy()

    target_snap = snap_points_naar_edges(targets, netwerk, "doel", max_snap_meter)
    if parkeer_loop_kolom() in targets.columns:
        target_snap["doel_extra_kosten_min"] = targets[
            parkeer_loop_kolom()
        ].reindex(target_snap.index)
    graph = graph_met_doelen(netwerk, target_snap, "doel")

    voorbeelden = kandidaten.sample(
        n=min(len(kandidaten), 100),
        random_state=random_state,
    )
    voorbeeld = None
    records = []
    target_idx = None
    for _, kandidaat in voorbeelden.iterrows():
        try:
            pad_nodes = nx.shortest_path(
                graph,
                source=kandidaat["pand_node"],
                target=VIRTUAL_DOEL,
                weight="weight",
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            continue

        records = route_geometrie_tussen_nodes(netwerk, pad_nodes)
        if records:
            voorbeeld = kandidaat
            target_idx = graph[pad_nodes[-2]][VIRTUAL_DOEL].get("target_idx")
            laatste_node = pad_nodes[-2]
            break

    if voorbeeld is None or not records:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    records = voeg_start_snap_segmenten_toe(records, voorbeeld, netwerk)
    if target_idx in targets.index and target_idx in target_snap.index:
        records = voeg_target_snap_segmenten_toe(
            records,
            targets.loc[target_idx],
            target_snap.loc[target_idx],
            netwerk,
            laatste_node,
        )

    route = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)
    route["modus"] = modus
    route["pand_id"] = voorbeeld.get("pand_id", "")
    route["pand_idx"] = voorbeeld.name
    route["route_reistijd_min"] = voorbeeld[tijd_kolom]
    route["target_idx"] = target_idx
    return voeg_route_lengte_toe(route)

def bereken_directe_modus(
    panden: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    netwerk: Routenetwerk,
    modus: str,
    norm_min: float,
    max_snap_meter: float,
) -> gpd.GeoDataFrame:
    voorziening_snap = snap_points_naar_edges(
        voorzieningen,
        netwerk,
        "doel",
        max_snap_meter,
    )
    afstanden, target_idx_per_node = afstanden_en_target_idx_naar_targets(
        netwerk,
        voorziening_snap,
        "doel",
    )
    resultaat = koppel_panden_aan_afstanden(
        panden,
        netwerk,
        afstanden,
        modus,
        norm_min,
        max_snap_meter,
        target_idx_per_node=target_idx_per_node,
    )
    return voeg_voorzieninggegevens_toe(
        resultaat,
        voorzieningen,
        f"target_idx_{modus}",
    )

def koppel_panden_aan_afstanden(
    panden: gpd.GeoDataFrame,
    netwerk: Routenetwerk,
    afstand_per_node: dict,
    modus: str,
    norm_min: float,
    max_snap_meter: float,
    target_idx_per_node: dict | None = None,
) -> gpd.GeoDataFrame:
    tijd_kolom = maak_tijd_kolom(modus)
    bereikbaar_kolom = maak_bereikbaar_kolom(modus)
    binnen_kolom = maak_binnen_kolom(modus)

    pand_snap = snap_points_naar_edges(panden, netwerk, "pand", max_snap_meter)
    pand_route = routekosten_vanaf_edge_snap(
        pand_snap,
        "pand",
        afstand_per_node,
        netwerk.snap_meter_per_min,
    )
    pand_snap, pand_route = verbeter_pand_snaps_boven_norm(
        panden,
        netwerk,
        afstand_per_node,
        pand_snap,
        pand_route,
        max_snap_meter,
        norm_min,
    )
    resultaat = panden.join(pand_snap)
    resultaat["pand_node"] = pand_route["pand_node"]
    if target_idx_per_node is not None:
        resultaat[f"target_idx_{modus}"] = pand_route["pand_node"].map(
            target_idx_per_node
        )
    resultaat[netwerk_tijd_kolom(modus)] = pand_route[
        "pand_netwerkreistijd_min"
    ]
    resultaat[tijd_kolom] = pand_route["pand_totale_reistijd_min"]
    resultaat.loc[
        resultaat["pand_snap_meter"].isna()
        | resultaat[netwerk_tijd_kolom(modus)].isna(),
        tijd_kolom,
    ] = np.nan
    norm_reeks = norm_min_voor_panden(modus, resultaat, norm_min)
    resultaat[bereikbaar_kolom] = resultaat[tijd_kolom].notna()
    resultaat[binnen_kolom] = resultaat[tijd_kolom] <= norm_reeks
    resultaat[norm_kolom(modus)] = norm_reeks

    afronden = [
        "pand_snap_meter",
        "pand_positie_meter",
        "pand_edge_lengte_meter",
        netwerk_tijd_kolom(modus),
        tijd_kolom,
    ]
    for kolom in afronden:
        resultaat[kolom] = pd.to_numeric(resultaat[kolom], errors="coerce").round(2)

    return resultaat
