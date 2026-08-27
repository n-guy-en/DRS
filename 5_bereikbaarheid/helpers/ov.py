"""OV-bereikbaarheid met voor- en natransport."""

from datetime import datetime

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from shapely.geometry import LineString

from .instellingen import (
    BASE_DIR,
    CRS_RD,
    VIRTUAL_DOEL,
    WANDEL_METER_PER_MIN,
    reistijd_profiel_kolom,
    tijd_kolom as maak_tijd_kolom,
    ov_data_dir,
    ov_lagen_dir,
    voorziening,
    voorziening_resultaat_kolom,
)
from importlib import import_module

puntrepresentatie = import_module("5_bereikbaarheid.helpers.geometrie").puntrepresentatie
from .netwerk import (
    Routenetwerk,
    afstanden_en_target_idx_naar_targets,
    bereken_directe_modus,
    doelkosten_vanaf_edge_snap,
    koppel_panden_aan_afstanden,
    voeg_voorzieninggegevens_toe,
    routekosten_vanaf_edge_snap,
    snap_points_naar_edges,
    voeg_edge_min_toe,
    voeg_route_lengte_toe,
    voorbeeldroute_naar_targets,
)


def controleer_kolommen(
    dataframe: gpd.GeoDataFrame | pd.DataFrame,
    naam: str,
    verplichte_kolommen: list[str],
) -> None:
    ontbrekend = sorted(set(verplichte_kolommen) - set(dataframe.columns))
    if ontbrekend:
        raise ValueError(f"Kolommen ontbreken in {naam}: {ontbrekend}")


def voeg_edge_met_attrs_toe(graph: nx.DiGraph, u, v, attrs: dict) -> None:
    gewicht = attrs.get("weight")
    if pd.isna(gewicht) or gewicht < 0:
        return
    if graph.has_edge(u, v) and float(gewicht) >= graph[u][v]["weight"]:
        return
    graph.add_edge(u, v, **attrs)


def lees_ov_stops() -> gpd.GeoDataFrame:
    pad = ov_lagen_dir() / "line_total_stop_points.geojson"
    print(f"Lees OV-stop-punten: {pad}")
    stops = gpd.read_file(pad).to_crs(CRS_RD)
    controleer_kolommen(stops, pad.name, ["node_id", "stop_ids", "geometry"])
    stops = puntrepresentatie(stops)
    stops["node_id"] = stops["node_id"].astype(str)
    return stops

def stop_id_mapping(stops: gpd.GeoDataFrame) -> dict[str, str]:
    mapping = {}
    for rij in stops[["node_id", "stop_ids"]].itertuples(index=False):
        for stop_id in str(rij.stop_ids).split(","):
            stop_id = stop_id.strip()
            if stop_id:
                mapping[stop_id] = rij.node_id
    return mapping

def lees_ov_edges(stops: gpd.GeoDataFrame) -> pd.DataFrame:
    pad = ov_data_dir() / "line_total_summary.csv"
    print(f"Lees OV-edges: {pad}")
    edges = pd.read_csv(
        pad,
        dtype={
            "from_stop_id": "object",
            "to_stop_id": "object",
            "line_id": "object",
            "mode": "object",
        },
        low_memory=False,
    )
    mapping = stop_id_mapping(stops)
    edges["from_node_id"] = edges["from_stop_id"].astype(str).map(mapping)
    edges["to_node_id"] = edges["to_stop_id"].astype(str).map(mapping)
    edges["travel_time_min"] = pd.to_numeric(
        edges["total_travel_time_min"],
        errors="coerce",
    )
    edges = edges[
        edges["from_node_id"].notna()
        & edges["to_node_id"].notna()
        & edges["travel_time_min"].notna()
        & (edges["travel_time_min"] > 0)
    ].copy()
    edges = (
        edges.groupby(["from_node_id", "to_node_id"], as_index=False)
        .agg(travel_time_min=("travel_time_min", "min"))
    )
    print(f"OV-edges gekoppeld aan stop-punten: {len(edges)}")
    return edges

def lees_ov_route_edges(stops: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pad = ov_lagen_dir() / "line_total_travel_times.geojson"
    print(f"Lees OV-routegeometrieen: {pad}")
    edges = gpd.read_file(pad).to_crs(CRS_RD)
    mapping = stop_id_mapping(stops)
    edges["from_node_id"] = edges["from_stop_id"].astype(str).map(mapping)
    edges["to_node_id"] = edges["to_stop_id"].astype(str).map(mapping)
    if "travel_time_min" in edges.columns:
        reistijd_kolom = "travel_time_min"
    elif "total_travel_time_min" in edges.columns:
        reistijd_kolom = "total_travel_time_min"
    else:
        raise ValueError(
            "OV-routegeometrie mist 'travel_time_min' of 'total_travel_time_min'."
        )
    edges["route_travel_time_min"] = pd.to_numeric(
        edges[reistijd_kolom],
        errors="coerce",
    )
    edges = edges[
        edges["from_node_id"].notna()
        & edges["to_node_id"].notna()
        & edges["route_travel_time_min"].notna()
        & (edges["route_travel_time_min"] > 0)
        & edges.geometry.notna()
        & ~edges.geometry.is_empty
    ].copy()
    edges = edges.sort_values("route_travel_time_min").drop_duplicates(
        ["from_node_id", "to_node_id"],
        keep="first",
    )
    print(f"OV-routegeometrieen gekoppeld aan stop-punten: {len(edges)}")
    return edges

def ov_transfer_edges(stops: gpd.GeoDataFrame, max_transfer_meter: float) -> list[tuple[str, str, float]]:
    sindex = stops.sindex
    edges = []
    for idx, geom in stops.geometry.items():
        if geom is None or geom.is_empty:
            continue
        kandidaten = sindex.query(geom.buffer(max_transfer_meter), predicate="intersects")
        van = stops.at[idx, "node_id"]
        for kandidaat in kandidaten:
            if kandidaat == idx:
                continue
            naar = stops.iloc[kandidaat]["node_id"]
            afstand = geom.distance(stops.iloc[kandidaat].geometry)
            if afstand <= max_transfer_meter:
                edges.append((van, naar, afstand / WANDEL_METER_PER_MIN))
    return edges

def ov_voorbeeld_graph(
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
    max_transfer_meter: float,
) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_node(VIRTUAL_DOEL)

    route_edges = lees_ov_route_edges(stops)
    for rij in route_edges.itertuples(index=False):
        attrs = {
            "weight": float(rij.route_travel_time_min),
            "segment_type": "ov_rit",
            "edge_id": getattr(rij, "edge_id", pd.NA),
            "reistijd_min": float(rij.route_travel_time_min),
            "geometry": rij.geometry,
            "mode": getattr(rij, "mode", ""),
            "operator": getattr(rij, "operator", ""),
            "line_id": getattr(rij, "line_id", ""),
            "route_id": getattr(rij, "route_id", ""),
            "from_stop_id": getattr(rij, "from_stop_id", ""),
            "from_stop_name": getattr(rij, "from_stop_name", ""),
            "to_stop_id": getattr(rij, "to_stop_id", ""),
            "to_stop_name": getattr(rij, "to_stop_name", ""),
        }
        voeg_edge_met_attrs_toe(graph, rij.from_node_id, rij.to_node_id, attrs)

    stops_index = stops.set_index(stops["node_id"].astype(str), drop=False)
    for van, naar, kosten in ov_transfer_edges(stops, max_transfer_meter):
        van_geom = (
            stops_index.at[str(van), "geometry"]
            if str(van) in stops_index.index
            else None
        )
        naar_geom = (
            stops_index.at[str(naar), "geometry"]
            if str(naar) in stops_index.index
            else None
        )
        if van_geom is None or naar_geom is None or van_geom.is_empty or naar_geom.is_empty:
            continue
        attrs = {
            "weight": float(kosten),
            "segment_type": "ov_transfer_lopen",
            "edge_id": pd.NA,
            "reistijd_min": float(kosten),
            "geometry": LineString([van_geom, naar_geom]),
        }
        voeg_edge_met_attrs_toe(graph, str(van), str(naar), attrs)

    egress = ov_egress_naar_voorziening(stops, voorzieningen, loopnetwerk, max_snap_meter)
    for node_id, kosten in egress.items():
        voeg_edge_met_attrs_toe(
            graph,
            str(node_id),
            VIRTUAL_DOEL,
            {
                "weight": float(kosten),
                "segment_type": f"ov_egress_naar_{voorziening()}",
                "reistijd_min": float(kosten),
            },
        )

    return graph

def ov_route_records(graph: nx.DiGraph, pad_nodes: list) -> list[dict]:
    records = []
    for volgorde, (van, naar) in enumerate(zip(pad_nodes, pad_nodes[1:]), start=1):
        if naar == VIRTUAL_DOEL:
            continue
        edge = graph[van][naar]
        geom = edge.get("geometry")
        if geom is None or geom.is_empty:
            continue
        records.append(
            {
                "route_order": volgorde,
                "edge_id": edge.get("edge_id", pd.NA),
                "segment_type": edge.get("segment_type", "ov_rit"),
                "segment_lengte_meter": round(float(geom.length), 2),
                "reistijd_min": edge.get("reistijd_min", edge.get("weight")),
                "ov_mode": edge.get("mode", ""),
                "ov_operator": edge.get("operator", ""),
                "ov_line_id": edge.get("line_id", ""),
                "ov_route_id": edge.get("route_id", ""),
                "ov_from_stop_id": edge.get("from_stop_id", ""),
                "ov_from_stop_name": edge.get("from_stop_name", ""),
                "ov_to_stop_id": edge.get("to_stop_id", ""),
                "ov_to_stop_name": edge.get("to_stop_name", ""),
                "geometry": geom,
            }
        )
    return records

def ov_egress_route_naar_voorziening(
    eind_stop,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
    modus: str,
) -> gpd.GeoDataFrame:
    egress_start = gpd.GeoDataFrame([eind_stop], geometry="geometry", crs=CRS_RD)
    egress_modus = f"{modus}_egress"
    resultaat = bereken_directe_modus(
        egress_start,
        voorzieningen,
        loopnetwerk,
        egress_modus,
        9999.0,
        max_snap_meter,
    )
    route = voorbeeldroute_naar_targets(
        resultaat,
        voorzieningen,
        loopnetwerk,
        egress_modus,
        max_snap_meter,
    )
    if route.empty:
        return route
    route = route.copy()
    route["segment_type"] = f"ov_egress_naar_{voorziening()}"
    route["modus"] = modus
    route["ov_eind_stop_idx"] = eind_stop.name
    route[f"{voorziening()}_idx"] = route["target_idx"]
    return route

def voeg_ov_route_naar_voorziening_toe(
    accessroute: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    modus: str,
    max_snap_meter: float,
    max_transfer_meter: float,
) -> gpd.GeoDataFrame:
    if (
        accessroute is None
        or accessroute.empty
        or "target_idx" not in accessroute.columns
    ):
        return accessroute

    start_stop_idx = accessroute["target_idx"].dropna()
    if start_stop_idx.empty:
        return accessroute
    start_stop_idx = start_stop_idx.iloc[0]
    if isinstance(start_stop_idx, float) and start_stop_idx.is_integer():
        start_stop_idx = int(start_stop_idx)
    if start_stop_idx not in stops.index:
        return accessroute

    start_node_id = str(stops.at[start_stop_idx, "node_id"])
    graph = ov_voorbeeld_graph(
        stops,
        voorzieningen,
        loopnetwerk,
        max_snap_meter,
        max_transfer_meter,
    )
    if graph.has_edge(start_node_id, VIRTUAL_DOEL):
        graph.remove_edge(start_node_id, VIRTUAL_DOEL)
    try:
        pad_nodes = nx.shortest_path(
            graph,
            source=start_node_id,
            target=VIRTUAL_DOEL,
            weight="weight",
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        print(f"Geen OV-routegeometrie gevonden vanaf voorbeeldhalte {start_node_id}.")
        return accessroute

    if len(pad_nodes) < 2:
        return accessroute

    eind_node_id = str(pad_nodes[-2])
    eind_stop = stops[stops["node_id"].astype(str).eq(eind_node_id)]
    if eind_stop.empty:
        return accessroute
    eind_stop = eind_stop.iloc[0]

    ov_records = ov_route_records(graph, pad_nodes)
    if not ov_records:
        return accessroute
    ov_route = gpd.GeoDataFrame(ov_records, geometry="geometry", crs=CRS_RD)
    ov_route["modus"] = modus
    ov_route["pand_id"] = (
        accessroute["pand_id"].iloc[0]
        if "pand_id" in accessroute.columns
        else ""
    )
    ov_route["pand_idx"] = (
        accessroute["pand_idx"].iloc[0]
        if "pand_idx" in accessroute.columns
        else pd.NA
    )
    ov_route["route_reistijd_min"] = accessroute["route_reistijd_min"].iloc[0]
    ov_route["ov_start_stop_idx"] = start_stop_idx
    ov_route["ov_eind_stop_idx"] = eind_stop.name

    egress_route = ov_egress_route_naar_voorziening(
        eind_stop,
        voorzieningen,
        loopnetwerk,
        max_snap_meter,
        modus,
    )
    if not egress_route.empty:
        egress_route["pand_id"] = ov_route["pand_id"].iloc[0]
        egress_route["pand_idx"] = ov_route["pand_idx"].iloc[0]
        egress_route["route_reistijd_min"] = ov_route["route_reistijd_min"].iloc[0]
        egress_route["ov_start_stop_idx"] = start_stop_idx
        egress_route["ov_eind_stop_idx"] = eind_stop.name

    accessroute = accessroute.copy()
    accessroute["ov_start_stop_idx"] = start_stop_idx
    accessroute["ov_eind_stop_idx"] = eind_stop.name
    delen = [accessroute, ov_route]
    if not egress_route.empty:
        delen.append(egress_route)
    route = pd.concat(delen, ignore_index=True)
    route["route_order"] = range(1, len(route) + 1)
    return voeg_route_lengte_toe(route)

def ov_egress_naar_voorziening(
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
) -> pd.Series:
    info = ov_egress_naar_voorziening_info(
        stops,
        voorzieningen,
        loopnetwerk,
        max_snap_meter,
    )
    return info["egress_tijd_min"].dropna()

def ov_egress_naar_voorziening_info(
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
) -> pd.DataFrame:
    voorziening_snap = snap_points_naar_edges(
        voorzieningen,
        loopnetwerk,
        "doel",
        max_snap_meter,
    )
    loop_afstanden, target_idx_per_node = afstanden_en_target_idx_naar_targets(
        loopnetwerk,
        voorziening_snap,
        "doel",
    )
    stop_snap = snap_points_naar_edges(
        stops,
        loopnetwerk,
        "stop_loop",
        max_snap_meter,
    )
    stop_route = routekosten_vanaf_edge_snap(
        stop_snap,
        "stop_loop",
        loop_afstanden,
        loopnetwerk.snap_meter_per_min,
    )
    info = pd.DataFrame(index=stops["node_id"].astype(str).to_numpy())
    info["egress_tijd_min"] = stop_route["stop_loop_totale_reistijd_min"].to_numpy()
    info[voorziening_resultaat_kolom("idx")] = (
        stop_route["stop_loop_node"].map(target_idx_per_node).to_numpy()
    )
    return info.dropna(subset=["egress_tijd_min"])

def ov_reistijd_vanaf_stops(
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
    max_transfer_meter: float,
) -> dict[str, float]:
    egress = ov_egress_naar_voorziening(stops, voorzieningen, loopnetwerk, max_snap_meter)
    edges = lees_ov_edges(stops)

    graph = nx.DiGraph()
    graph.add_node(VIRTUAL_DOEL)

    def pre(node_id: str) -> str:
        return f"pre::{node_id}"

    def post(node_id: str) -> str:
        return f"post::{node_id}"

    for rij in edges.itertuples(index=False):
        voeg_edge_min_toe(graph, pre(rij.from_node_id), post(rij.to_node_id), rij.travel_time_min)
        voeg_edge_min_toe(graph, post(rij.from_node_id), post(rij.to_node_id), rij.travel_time_min)

    for van, naar, kosten in ov_transfer_edges(stops, max_transfer_meter):
        voeg_edge_min_toe(graph, post(van), post(naar), kosten)

    for node_id, kosten in egress.items():
        voeg_edge_min_toe(graph, post(str(node_id)), VIRTUAL_DOEL, float(kosten))

    afstanden = nx.single_source_dijkstra_path_length(
        graph.reverse(copy=True),
        VIRTUAL_DOEL,
        weight="weight",
    )
    resultaat = {}
    for node_id in stops["node_id"].astype(str):
        waarde = afstanden.get(pre(node_id))
        if waarde is not None:
            resultaat[node_id] = waarde
    print(f"OV-stops met voorzieningpad inclusief OV-rit: {len(resultaat)}")
    return resultaat

def tijd_naar_seconden(waarde: str) -> int:
    delen = str(waarde).strip().split(":")
    if len(delen) != 3:
        raise ValueError(f"Ongeldige tijd: {waarde}")
    uren, minuten, seconden = [int(deel) for deel in delen]
    return uren * 3600 + minuten * 60 + seconden

def actieve_service_ids(ov_datum: str | None) -> set[str] | None:
    if not ov_datum:
        print("Geen OV-datum opgegeven; gebruik alle service_id's uit GTFS.")
        return None

    gtfs_dir = BASE_DIR / "4_netwerk" / "raw" / "GTFS" / "gtfs-openov-nl"
    calendar_pad = gtfs_dir / "calendar.txt"
    calendar_dates_pad = gtfs_dir / "calendar_dates.txt"
    actief: set[str] = set()

    if calendar_pad.exists():
        datum = datetime.strptime(str(ov_datum), "%Y%m%d")
        dag_kolom = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ][datum.weekday()]
        calendar = pd.read_csv(calendar_pad, dtype="object")
        controleer_kolommen(
            calendar,
            calendar_pad.name,
            ["service_id", "start_date", "end_date", dag_kolom],
        )
        actief.update(
            calendar.loc[
                calendar["start_date"].astype(str).le(str(ov_datum))
                & calendar["end_date"].astype(str).ge(str(ov_datum))
                & calendar[dag_kolom].astype(str).eq("1"),
                "service_id",
            ].astype(str)
        )

    if not calendar_dates_pad.exists():
        if actief:
            print(f"Actieve OV-services op {ov_datum}: {len(actief)}")
            return actief
        print(f"calendar_dates.txt niet gevonden voor datumfilter: {calendar_dates_pad}")
        return None

    calendar_dates = pd.read_csv(
        calendar_dates_pad,
        dtype={"service_id": "object", "date": "object", "exception_type": "object"},
        usecols=["service_id", "date", "exception_type"],
    )
    controleer_kolommen(
        calendar_dates,
        calendar_dates_pad.name,
        ["service_id", "date", "exception_type"],
    )
    actief.update(
        set(
            calendar_dates.loc[
                calendar_dates["date"].astype(str).eq(str(ov_datum))
                & calendar_dates["exception_type"].astype(str).eq("1"),
                "service_id",
            ].astype(str)
        )
    )
    verwijderd = set(
        calendar_dates.loc[
            calendar_dates["date"].astype(str).eq(str(ov_datum))
            & calendar_dates["exception_type"].astype(str).eq("2"),
            "service_id",
        ].astype(str)
    )
    actief -= verwijderd
    if not actief:
        raise ValueError(f"Geen actieve OV-services gevonden voor datum {ov_datum}.")
    print(f"Actieve OV-services op {ov_datum}: {len(actief)}")
    return actief

def lees_timetable_edges(
    stops: gpd.GeoDataFrame,
    ov_datum: str | None,
    start_seconden: int,
    eind_seconden: int,
) -> pd.DataFrame:
    pad = ov_data_dir() / "validatie" / "tussenbestanden" / "line_total_travel_times.csv"
    print(f"Lees tijdafhankelijke OV-ritten: {pad}")
    mapping = stop_id_mapping(stops)
    services = actieve_service_ids(ov_datum)
    kolommen = [
        "service_id",
        "trip_id",
        "from_stop_id",
        "to_stop_id",
        "connection_departure_seconds",
        "connection_arrival_seconds",
    ]
    delen = []
    for chunk in pd.read_csv(
        pad,
        usecols=kolommen,
        dtype={
            "service_id": "object",
            "trip_id": "object",
            "from_stop_id": "object",
            "to_stop_id": "object",
        },
        chunksize=500_000,
        low_memory=False,
    ):
        if services is not None:
            chunk = chunk[chunk["service_id"].astype(str).isin(services)]
        chunk["departure_seconds"] = pd.to_numeric(
            chunk["connection_departure_seconds"],
            errors="coerce",
        )
        chunk["arrival_seconds"] = pd.to_numeric(
            chunk["connection_arrival_seconds"],
            errors="coerce",
        )
        chunk = chunk[
            chunk["departure_seconds"].notna()
            & chunk["arrival_seconds"].notna()
            & (chunk["arrival_seconds"] > chunk["departure_seconds"])
            & (chunk["departure_seconds"] >= start_seconden)
            & (chunk["departure_seconds"] <= eind_seconden)
        ].copy()
        if chunk.empty:
            continue
        chunk["from_node_id"] = chunk["from_stop_id"].astype(str).map(mapping)
        chunk["to_node_id"] = chunk["to_stop_id"].astype(str).map(mapping)
        chunk = chunk[chunk["from_node_id"].notna() & chunk["to_node_id"].notna()]
        if not chunk.empty:
            delen.append(
                chunk[
                    [
                        "from_node_id",
                        "to_node_id",
                        "departure_seconds",
                        "arrival_seconds",
                    ]
                ]
            )

    if not delen:
        raise ValueError("Geen bruikbare OV-ritten gevonden binnen het opgegeven tijdvenster.")

    edges = pd.concat(delen, ignore_index=True)
    edges["departure_seconds"] = edges["departure_seconds"].round().astype(int)
    edges["arrival_seconds"] = edges["arrival_seconds"].round().astype(int)
    edges = edges.drop_duplicates()
    print(f"Tijdafhankelijke OV-ritsegmenten binnen venster: {len(edges)}")
    return edges

def event_node(node_id: str, seconde: int, state: str) -> tuple[str, int, str]:
    return (str(node_id), int(seconde), state)

def ov_reistijdprofielen_vanaf_stops(
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    loopnetwerk: Routenetwerk,
    max_snap_meter: float,
    max_transfer_meter: float,
    ov_datum: str | None,
    starttijd: str,
    eindtijd: str,
    stap_minuten: int,
    min_overstap_min: float,
) -> dict[str, dict[str, float]]:
    start_seconden = tijd_naar_seconden(starttijd)
    eind_seconden = tijd_naar_seconden(eindtijd)
    if eind_seconden <= start_seconden:
        raise ValueError("OV-eindtijd moet na OV-starttijd liggen.")
    if stap_minuten <= 0:
        raise ValueError("OV-stap-minuten moet groter zijn dan 0.")

    egress_info = ov_egress_naar_voorziening_info(
        stops,
        voorzieningen,
        loopnetwerk,
        max_snap_meter,
    )
    egress = egress_info["egress_tijd_min"]
    edges = lees_timetable_edges(stops, ov_datum, start_seconden, eind_seconden)

    graph = nx.DiGraph()
    graph.add_node(VIRTUAL_DOEL)

    stop_event_tijden: dict[str, set[int]] = {}
    for rij in edges.itertuples(index=False):
        van = str(rij.from_node_id)
        naar = str(rij.to_node_id)
        vertrek = int(rij.departure_seconds)
        aankomst = int(rij.arrival_seconds)
        stop_event_tijden.setdefault(van, set()).add(vertrek)
        stop_event_tijden.setdefault(naar, set()).add(aankomst)
        graph.add_edge(
            event_node(van, vertrek, "pre"),
            event_node(naar, aankomst, "post"),
            weight=float(aankomst - vertrek) / 60,
        )
        graph.add_edge(
            event_node(van, vertrek, "post"),
            event_node(naar, aankomst, "post"),
            weight=float(aankomst - vertrek) / 60,
        )

    for node_id, kosten in egress.items():
        node_id = str(node_id)
        stop_event_tijden.setdefault(node_id, set()).add(start_seconden)
        stop_event_tijden.setdefault(node_id, set()).add(eind_seconden)
        for tijd in list(stop_event_tijden[node_id]):
            voeg_edge_min_toe(
                graph,
                event_node(node_id, tijd, "post"),
                VIRTUAL_DOEL,
                float(kosten),
            )

    event_tijden_sorted = {
        node_id: sorted(tijden)
        for node_id, tijden in stop_event_tijden.items()
        if tijden
    }

    for node_id, tijden in event_tijden_sorted.items():
        for eerder, later in zip(tijden, tijden[1:]):
            for state in ["pre", "post"]:
                voeg_edge_min_toe(
                    graph,
                    event_node(node_id, eerder, state),
                    event_node(node_id, later, state),
                    (later - eerder) / 60,
                )

    transfer_wacht_sec = int(round(min_overstap_min * 60))
    for van, naar, loop_min in ov_transfer_edges(stops, max_transfer_meter):
        van = str(van)
        naar = str(naar)
        if van not in event_tijden_sorted or naar not in event_tijden_sorted:
            continue
        naar_tijden = event_tijden_sorted[naar]
        transfer_sec = int(round(loop_min * 60)) + transfer_wacht_sec
        for vertrek_van in event_tijden_sorted[van]:
            vroegste_naar = vertrek_van + transfer_sec
            positie = np.searchsorted(naar_tijden, vroegste_naar, side="left")
            if positie >= len(naar_tijden):
                continue
            aankomst_naar = naar_tijden[positie]
            voeg_edge_min_toe(
                graph,
                event_node(van, vertrek_van, "post"),
                event_node(naar, aankomst_naar, "post"),
                (aankomst_naar - vertrek_van) / 60,
            )

    reverse_graph = graph.reverse(copy=True)
    afstanden, paden = nx.single_source_dijkstra(
        reverse_graph,
        VIRTUAL_DOEL,
        weight="weight",
    )

    def voorziening_idx_voor_event(event) -> object:
        pad = paden.get(event)
        if not pad or len(pad) < 2:
            return np.nan
        origineel_pad = list(reversed(pad))
        for van, naar in zip(origineel_pad, origineel_pad[1:]):
            if naar == VIRTUAL_DOEL:
                stop_id = str(van[0]) if isinstance(van, tuple) else str(van)
                if stop_id in egress_info.index:
                    return egress_info.at[stop_id, voorziening_resultaat_kolom("idx")]
        return np.nan

    vertrekmomenten = list(range(start_seconden, eind_seconden + 1, stap_minuten * 60))
    profielen: dict[str, dict[str, float]] = {}
    for node_id in stops["node_id"].astype(str):
        tijden = event_tijden_sorted.get(node_id)
        waarden = []
        voorziening_idx_waarden = []
        for vertrek in vertrekmomenten:
            if tijden:
                positie = np.searchsorted(tijden, vertrek, side="left")
                if positie >= len(tijden):
                    continue
                event_tijd = tijden[positie]
                afstand = afstanden.get(event_node(node_id, event_tijd, "pre"))
                if afstand is None:
                    continue
                waarden.append((event_tijd - vertrek) / 60 + afstand)
                voorziening_idx_waarden.append(
                    voorziening_idx_voor_event(event_node(node_id, event_tijd, "pre"))
                )
        if not waarden:
            continue
        geldige_voorziening_idx = [
            waarde
            for waarde in voorziening_idx_waarden
            if pd.notna(waarde)
        ]
        voorziening_idx = (
            pd.Series(geldige_voorziening_idx).mode().iloc[0]
            if geldige_voorziening_idx
            else np.nan
        )
        profielen[node_id] = {
            "mediaan": float(np.median(waarden)),
            "min": float(np.min(waarden)),
            "p90": float(np.percentile(waarden, 90)),
            "aantal": float(len(waarden)),
            voorziening_resultaat_kolom("idx"): voorziening_idx,
        }

    print(f"OV-stops met tijdvensterprofiel: {len(profielen)}")
    return profielen

def bereken_ov_access(
    panden: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    ov_tijd_vanaf_stop: dict[str, float],
    access_netwerk: Routenetwerk,
    modus: str,
    norm_min: float,
    max_snap_meter: float,
    stop_voorziening_idx: dict[str, object] | None = None,
    voorzieningen: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    stops_met_tijd = stops[stops["node_id"].isin(ov_tijd_vanaf_stop)].copy()
    stop_snap = snap_points_naar_edges(
        stops_met_tijd,
        access_netwerk,
        "doel",
        max_snap_meter,
    )
    stops_met_tijd = stops_met_tijd.join(stop_snap)
    doel_snap = doelkosten_vanaf_edge_snap(
        stops_met_tijd,
        "doel",
        access_netwerk.snap_meter_per_min,
    )
    ov_kosten = stops_met_tijd["node_id"].map(ov_tijd_vanaf_stop)
    doel_snap["doel_kosten_vanaf_u_min"] = (
        doel_snap["doel_kosten_vanaf_u_min"] + ov_kosten
    )
    doel_snap["doel_kosten_vanaf_v_min"] = (
        doel_snap["doel_kosten_vanaf_v_min"] + ov_kosten
    )
    afstanden, target_idx_per_node = afstanden_en_target_idx_naar_targets(
        access_netwerk,
        doel_snap,
        "doel",
    )
    resultaat = koppel_panden_aan_afstanden(
        panden,
        access_netwerk,
        afstanden,
        modus,
        norm_min,
        max_snap_meter,
        target_idx_per_node=target_idx_per_node,
    )
    stop_idx_kolom = f"target_idx_{modus}"
    resultaat[f"ov_stop_idx_{modus}"] = resultaat[stop_idx_kolom]
    if stop_voorziening_idx is not None:
        stop_node_id = stops_met_tijd["node_id"].astype(str)
        resultaat[f"target_idx_{modus}"] = resultaat[
            f"ov_stop_idx_{modus}"
        ].map(stop_node_id).map(stop_voorziening_idx)
        if voorzieningen is not None:
            resultaat = voeg_voorzieninggegevens_toe(
                resultaat,
                voorzieningen,
                f"target_idx_{modus}",
            )
    return resultaat

def bereken_ov_access_met_profielen(
    panden: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    ov_profielen_vanaf_stop: dict[str, dict[str, float]],
    access_netwerk: Routenetwerk,
    modus: str,
    norm_min: float,
    max_snap_meter: float,
) -> gpd.GeoDataFrame:
    mediaan = {
        node_id: profiel["mediaan"]
        for node_id, profiel in ov_profielen_vanaf_stop.items()
    }
    stop_voorziening_idx = {
        node_id: profiel.get(voorziening_resultaat_kolom("idx"), np.nan)
        for node_id, profiel in ov_profielen_vanaf_stop.items()
    }
    resultaat = bereken_ov_access(
        panden,
        stops,
        mediaan,
        access_netwerk,
        modus,
        norm_min,
        max_snap_meter,
        stop_voorziening_idx=stop_voorziening_idx,
        voorzieningen=voorzieningen,
    )

    extra_profielen = {
        "min": "min",
        "p90": "p90",
    }
    for profiel_naam, suffix in extra_profielen.items():
        stop_tijden = {
            node_id: profiel[profiel_naam]
            for node_id, profiel in ov_profielen_vanaf_stop.items()
        }
        extra = bereken_ov_access(
            panden,
            stops,
            stop_tijden,
            access_netwerk,
            modus,
            norm_min,
            max_snap_meter,
        )
        resultaat[reistijd_profiel_kolom(modus, suffix)] = extra[
            maak_tijd_kolom(modus)
        ]

    resultaat[reistijd_profiel_kolom(modus, "mediaan")] = resultaat[
        maak_tijd_kolom(modus)
    ]
    return resultaat
