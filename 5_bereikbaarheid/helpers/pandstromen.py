"""Pandniveau-flowmap naar de gekozen voorziening.

Deze module rekent bewust geen routes naar alle voorzieningen. De gekozen
voorziening komt uit de bereikbaarheidsoutput van `5_bereikbaarheid`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd

from .invoer import lees_voorzieningen
from .instellingen import (
    CRS_RD,
    CRS_WGS84,
    output_basis_dir,
    tabel_output_basis_dir,
    voorziening,
)
from .routes import (
    OV_ACCESS_MODUS,
    bouw_edge_lookup,
    bouw_netwerken,
    bouw_ov_basis_graph,
    lees_bereikbaarheids_panden,
    route_naar_target,
    ov_graph_naar_voorziening,
    bereikbaarheid_netwerk,
    bereikbaarheid_auto,
    bereikbaarheid_ov,
    bereikbaarheid_config,
)


NAAM = voorziening()
ID_KOLOM = f"{NAAM}_id"
NAAM_KOLOM = f"{NAAM}_naam"
AANTAL_KOLOM = f"aantal_{NAAM}"
IDS_KOLOM = f"{NAAM}_ids"
NAMEN_KOLOM = f"{NAAM}_namen"
VOORZIENING_IDX_KOLOM = f"{NAAM}_idx"

def reistijd_kolom(modus: str) -> str:
    return f"reistijd_{NAAM}_{modus}_min"

def binnen_norm_kolom(modus: str) -> str:
    return f"binnen_norm_{NAAM}_{modus}"

def parkeer_loop_kolom() -> str:
    return f"loop_vanaf_parkeren_{NAAM}_min"


DIRECTE_MODI = {"lopen", "fiets"}
AUTO_MODI = {"auto"}
OV_MODI = {"ov_lopen", "ov_fiets"}
ONDERSTEUNDE_MODI = DIRECTE_MODI | AUTO_MODI | OV_MODI
FLOW_KLASSEN = [
    ("1 pandroute", 0.35, "#9e9e9e", 0.22),
    ("2-40 pandroutes", 1.1, "#00c853", 0.60),
    ("41-100 pandroutes", 2.2, "#8eea32", 0.78),
    ("101-250 pandroutes", 3.6, "#ffd400", 0.90),
    ("251-500 pandroutes", 5.0, "#ff7a1a", 0.97),
    (">500 pandroutes", 6.5, "#ff1a1a", 1.0),
]
FLOW_DREMPELS = [1, 40, 100, 250, 500]


def schrijf_gpkg(gdf: gpd.GeoDataFrame, pad: Path, layer: str) -> None:
    pad = Path(pad)
    pad.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{pad.stem}.", dir=pad.parent) as tmpdir:
        tijdelijk_pad = Path(tmpdir) / pad.name
        gdf.to_file(tijdelijk_pad, layer=layer, driver="GPKG")
        tijdelijk_pad.replace(pad)

    try:
        relatief_pad = pad.relative_to(tabel_output_basis_dir())
    except ValueError:
        print(f"Opgeslagen: {pad} ({layer})", flush=True)
        return

    laag_pad = output_basis_dir() / relatief_pad
    publicatie = gdf.to_crs(CRS_WGS84) if gdf.crs is not None else gdf
    laag_pad.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{laag_pad.stem}.", dir=laag_pad.parent) as tmpdir:
        tijdelijk_pad = Path(tmpdir) / laag_pad.name
        publicatie.to_file(tijdelijk_pad, layer=layer, driver="GPKG")
        tijdelijk_pad.replace(laag_pad)
    print(f"Opgeslagen in 0_layers: {laag_pad} ({layer})", flush=True)


def pas_flow_stijl_toe(flowmap: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    flowmap = flowmap.copy()
    # Vaste drempels houden stromenkaarten onderling vergelijkbaar.
    drempels = FLOW_DREMPELS

    def stijl(aantal_panden: int) -> tuple[str, float, str, float]:
        for drempel, klasse in zip(drempels, FLOW_KLASSEN):
            if aantal_panden <= drempel:
                return klasse
        return FLOW_KLASSEN[-1]

    stijlen = flowmap["aantal_panden"].astype(int).apply(stijl)
    flowmap["flow_klasse"] = stijlen.map(lambda waarde: waarde[0])
    flowmap["flow_lijndikte"] = stijlen.map(lambda waarde: waarde[1])
    flowmap["flow_kleur"] = stijlen.map(lambda waarde: waarde[2])
    flowmap["flow_opacity"] = stijlen.map(lambda waarde: waarde[3])
    flowmap["stroke"] = flowmap["flow_kleur"]
    flowmap["stroke-width"] = flowmap["flow_lijndikte"]
    flowmap["stroke-opacity"] = flowmap["flow_opacity"]
    flowmap["z_index"] = flowmap["aantal_panden"].astype(int)
    grenzen = []
    ondergrens = 1
    for drempel, klasse in zip(drempels, FLOW_KLASSEN):
        label = klasse[0]
        if ondergrens == drempel:
            grenzen.append(f"{label} = {drempel}")
        else:
            grenzen.append(f"{label} = {ondergrens}-{drempel}")
        ondergrens = drempel + 1
    grenzen.append(f"{FLOW_KLASSEN[-1][0]} > {drempels[-1]}")
    flowmap["flow_drempels"] = "; ".join(grenzen)
    flowmap["flow_label"] = (
        flowmap["aantal_panden"].astype(str)
        + " pandroutes over dit segment"
    )
    return flowmap


def print_voortgang(modus: str, teller: int, totaal: int, pand_id) -> None:
    print(
        f"[{modus}] pandroute {teller}/{totaal} - pand_id={pand_id}",
        flush=True,
    )


def pand_selectie(
    panden: gpd.GeoDataFrame,
    modus: str,
    max_panden: int | None,
    buurtcode: str | None = None,
) -> gpd.GeoDataFrame:
    tijd_kolom = reistijd_kolom(modus)
    selectie = panden[
        panden[VOORZIENING_IDX_KOLOM].notna()
        & panden[tijd_kolom].notna()
    ].copy()
    if buurtcode is not None:
        selectie = selectie[selectie["buurtcode"].astype(str).eq(buurtcode)].copy()
    if max_panden is not None:
        selectie = selectie.head(max_panden).copy()
    return selectie


def pandroute_records(
    pand: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    target_snap: pd.DataFrame,
    netwerk,
    edge_lookup: dict,
    modus: str,
) -> gpd.GeoDataFrame:
    voorziening_idx = pand[VOORZIENING_IDX_KOLOM].dropna()
    if voorziening_idx.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    voorziening_idx = int(float(voorziening_idx.iloc[0]))
    if voorziening_idx not in voorzieningen.index:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    route = route_naar_target(
        pand,
        voorzieningen.loc[[voorziening_idx]],
        target_snap,
        netwerk,
        modus,
        voorziening_idx,
        edge_lookup,
    )
    if route.empty:
        return route

    return voeg_pand_metadata(route, pand, modus, voorziening_idx)


def voeg_pand_metadata(
    route: gpd.GeoDataFrame,
    pand: gpd.GeoDataFrame,
    modus: str,
    voorziening_idx: int,
) -> gpd.GeoDataFrame:
    route = route.copy()
    route["buurtcode"] = pand["buurtcode"].iloc[0]
    route["buurtnaam"] = pand["buurtnaam"].iloc[0]
    route["gemeentenaam"] = pand["gemeentenaam"].iloc[0]
    route[VOORZIENING_IDX_KOLOM] = voorziening_idx
    route[ID_KOLOM] = pand[ID_KOLOM].iloc[0]
    route[NAAM_KOLOM] = pand[NAAM_KOLOM].iloc[0]
    route["binnen_norm"] = bool(
        pand[binnen_norm_kolom(modus)].fillna(False).iloc[0]
    )
    return route


def auto_pandroute_records(
    pand: gpd.GeoDataFrame,
    voorzieningen: gpd.GeoDataFrame,
    parkeer_targets: gpd.GeoDataFrame,
    parkeer_auto_snap: pd.DataFrame,
    parkeer_loop_snap: pd.DataFrame,
    voorziening_loop_snap: pd.DataFrame,
    netwerken: dict,
    edge_lookups: dict,
) -> gpd.GeoDataFrame:
    parkeer_idx = pand["parkeer_idx_auto"].dropna()
    voorziening_idx = pand[VOORZIENING_IDX_KOLOM].dropna()
    if parkeer_idx.empty or voorziening_idx.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    parkeer_idx = int(float(parkeer_idx.iloc[0]))
    voorziening_idx = int(float(voorziening_idx.iloc[0]))
    if parkeer_idx not in parkeer_targets.index or voorziening_idx not in voorzieningen.index:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    autoroute = route_naar_target(
        pand,
        parkeer_targets.loc[[parkeer_idx]],
        parkeer_auto_snap,
        netwerken["auto"],
        "auto",
        parkeer_idx,
        edge_lookups["auto"],
    )

    parkeer_start = parkeer_targets.loc[[parkeer_idx]].copy()
    parkeer_start = parkeer_start.join(parkeer_loop_snap.loc[[parkeer_idx]])
    parkeer_start["pand_id"] = pand["pand_id"].iloc[0]
    parkeer_start[f"reistijd_{NAAM}_auto_loop_min"] = parkeer_start[
        parkeer_loop_kolom()
    ]
    looproute = route_naar_target(
        parkeer_start,
        voorzieningen.loc[[voorziening_idx]],
        voorziening_loop_snap,
        netwerken["lopen"],
        "auto_loop",
        voorziening_idx,
        edge_lookups["lopen"],
    )
    if not looproute.empty:
        looproute["segment_type"] = f"loop_parkeerplek_naar_{NAAM}"
        looproute["modus"] = "auto"
        looproute["pand_id"] = pand["pand_id"].iloc[0]
        looproute["route_reistijd_min"] = pand[reistijd_kolom("auto")].iloc[0]

    delen = [
        deel
        for deel in [autoroute, looproute]
        if deel is not None and not deel.empty
    ]
    if not delen:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    route = gpd.GeoDataFrame(pd.concat(delen, ignore_index=True), geometry="geometry", crs=CRS_RD)
    route["route_order"] = range(1, len(route) + 1)
    route = bereikbaarheid_netwerk.voeg_route_lengte_toe(route)
    return voeg_pand_metadata(route, pand, "auto", voorziening_idx)


def ov_pandroute_records(
    pand: gpd.GeoDataFrame,
    modus: str,
    voorzieningen: gpd.GeoDataFrame,
    stops: gpd.GeoDataFrame,
    ov_basis_graph,
    ov_graph_cache: dict,
    stop_target_snaps: dict,
    stop_loop_starts: gpd.GeoDataFrame,
    voorziening_loop_snap: pd.DataFrame,
    netwerken: dict,
    edge_lookups: dict,
    max_snap_meter: float,
) -> gpd.GeoDataFrame:
    access_modus = OV_ACCESS_MODUS[modus]
    stop_kolom = f"ov_stop_idx_{modus}"
    if stop_kolom not in pand.columns:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    stop_idx = pand[stop_kolom].dropna()
    voorziening_idx = pand[VOORZIENING_IDX_KOLOM].dropna()
    if stop_idx.empty or voorziening_idx.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    stop_idx = int(float(stop_idx.iloc[0]))
    voorziening_idx = int(float(voorziening_idx.iloc[0]))
    if stop_idx not in stops.index or voorziening_idx not in voorzieningen.index:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    accessroute = route_naar_target(
        pand,
        stops.loc[[stop_idx]],
        stop_target_snaps[access_modus],
        netwerken[access_modus],
        modus,
        stop_idx,
        edge_lookups[access_modus],
    )
    if accessroute.empty:
        return accessroute
    accessroute["segment_type"] = "access_naar_opstaphalte"
    accessroute["ov_start_stop_idx"] = stop_idx

    start_node_id = str(stops.at[stop_idx, "node_id"])
    if voorziening_idx not in ov_graph_cache:
        try:
            ov_graph_cache[voorziening_idx] = ov_graph_naar_voorziening(
                ov_basis_graph,
                stops,
                voorzieningen,
                voorziening_idx,
                netwerken["lopen"],
                max_snap_meter,
            )
        except ValueError as fout:
            print(
                f"[{modus}] route overgeslagen: OV-doel {voorziening_idx} "
                f"kan niet aan loopnetwerk worden gekoppeld ({fout})",
                flush=True,
            )
            ov_graph_cache[voorziening_idx] = None
    ov_graph = ov_graph_cache[voorziening_idx]
    if ov_graph is None:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    if ov_graph.has_edge(start_node_id, bereikbaarheid_config.VIRTUAL_DOEL):
        ov_graph = ov_graph.copy()
        ov_graph.remove_edge(start_node_id, bereikbaarheid_config.VIRTUAL_DOEL)
    try:
        pad_nodes = nx.shortest_path(
            ov_graph,
            source=start_node_id,
            target=bereikbaarheid_config.VIRTUAL_DOEL,
            weight="weight",
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    if len(pad_nodes) < 2:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    eind_node_id = str(pad_nodes[-2])
    eind_stop = stops[stops["node_id"].astype(str).eq(eind_node_id)]
    if eind_stop.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    eind_stop_idx = eind_stop.index[0]

    ov_records = bereikbaarheid_ov.ov_route_records(ov_graph, pad_nodes)
    if not ov_records:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    ov_route = gpd.GeoDataFrame(ov_records, geometry="geometry", crs=CRS_RD)
    ov_route["modus"] = modus
    ov_route["pand_id"] = pand["pand_id"].iloc[0]
    ov_route["pand_idx"] = pand.index[0]
    ov_route["route_reistijd_min"] = pand[reistijd_kolom(modus)].iloc[0]
    ov_route["ov_start_stop_idx"] = stop_idx
    ov_route["ov_eind_stop_idx"] = eind_stop_idx
    ov_route["target_idx"] = voorziening_idx

    egress_start = stop_loop_starts.loc[[eind_stop_idx]]
    egress_route = route_naar_target(
        egress_start,
        voorzieningen.loc[[voorziening_idx]],
        voorziening_loop_snap,
        netwerken["lopen"],
        f"{modus}_egress",
        voorziening_idx,
        edge_lookups["lopen"],
    )
    if not egress_route.empty:
        egress_route["segment_type"] = f"ov_egress_naar_{NAAM}"
        egress_route["modus"] = modus
        egress_route["pand_id"] = pand["pand_id"].iloc[0]
        egress_route["route_reistijd_min"] = pand[reistijd_kolom(modus)].iloc[0]
        egress_route["ov_start_stop_idx"] = stop_idx
        egress_route["ov_eind_stop_idx"] = eind_stop_idx
        egress_route["target_idx"] = voorziening_idx

    delen = [accessroute, ov_route]
    if not egress_route.empty:
        delen.append(egress_route)
    route = gpd.GeoDataFrame(pd.concat(delen, ignore_index=True), geometry="geometry", crs=CRS_RD)
    route["route_order"] = range(1, len(route) + 1)
    route = bereikbaarheid_netwerk.voeg_route_lengte_toe(route)
    return voeg_pand_metadata(route, pand, modus, voorziening_idx)


def segment_key(row: dict) -> tuple[str, str, str]:
    edge_id = row.get("edge_id")
    if pd.notna(edge_id):
        sleutel = str(edge_id)
    else:
        geom = row.get("geometry")
        sleutel = geom.wkb_hex if geom is not None else ""
    return (
        str(row.get("segment_type", "")),
        sleutel,
        str(row.get("buurtcode", "")),
    )


def update_segmenten(segmenten: dict, route: gpd.GeoDataFrame) -> None:
    if route.empty:
        return

    gezien_in_route = set()

    for row in route.itertuples(index=False):
        row_dict = row._asdict()
        key = segment_key(row_dict)
        if key in gezien_in_route:
            continue
        gezien_in_route.add(key)
        if key not in segmenten:
            segmenten[key] = {
                "segment_type": row_dict.get("segment_type"),
                "segment_lengte_meter": row_dict.get("segment_lengte_meter"),
                "edge_id": row_dict.get("edge_id"),
                "buurtcode": row_dict.get("buurtcode"),
                "buurtnaam": row_dict.get("buurtnaam"),
                "gemeentenaam": row_dict.get("gemeentenaam"),
                "geometry": row_dict.get("geometry"),
                "aantal_panden": 0,
                "aantal_panden_binnen_norm": 0,
                "aantal_panden_buiten_norm": 0,
                IDS_KOLOM: set(),
                NAMEN_KOLOM: set(),
            }
        segment = segmenten[key]
        segment["aantal_panden"] += 1
        if bool(row_dict.get("binnen_norm")):
            segment["aantal_panden_binnen_norm"] += 1
        else:
            segment["aantal_panden_buiten_norm"] += 1

        voorziening_id = row_dict.get(ID_KOLOM)
        voorziening_naam = row_dict.get(NAAM_KOLOM)
        if pd.notna(voorziening_id):
            segment[IDS_KOLOM].add(str(voorziening_id))
        if pd.notna(voorziening_naam):
            segment[NAMEN_KOLOM].add(str(voorziening_naam))


def segmenten_naar_gdf(segmenten: dict, modus: str) -> gpd.GeoDataFrame:
    records = []
    for segment in segmenten.values():
        aantal = int(segment["aantal_panden"])
        records.append(
            {
                "modus": modus,
                "buurtcode": segment["buurtcode"],
                "buurtnaam": segment["buurtnaam"],
                "gemeentenaam": segment["gemeentenaam"],
                "segment_type": segment["segment_type"],
                "aantal_panden": aantal,
                "aantal_panden_binnen_norm": int(segment["aantal_panden_binnen_norm"]),
                "aantal_panden_buiten_norm": int(segment["aantal_panden_buiten_norm"]),
                AANTAL_KOLOM: len(segment[IDS_KOLOM]),
                IDS_KOLOM: ", ".join(sorted(segment[IDS_KOLOM])),
                NAMEN_KOLOM: ", ".join(sorted(segment[NAMEN_KOLOM])),
                "geometry": segment["geometry"],
            }
        )
    flowmap = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)
    return pas_flow_stijl_toe(flowmap)


def maak_pand_flowmap(
    modus: str,
    max_panden: int | None = None,
    bewaar_individuele_routes: bool = False,
    max_snap_meter: float = 250.0,
    buurtcode: str | None = None,
    schrijf_bestand: bool = True,
    panden_bereikbaarheid: gpd.GeoDataFrame | None = None,
    voorzieningen_data: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    if modus not in ONDERSTEUNDE_MODI:
        raise ValueError(
            "Pandniveau-flowmap ondersteunt deze modi: "
            + ", ".join(sorted(ONDERSTEUNDE_MODI))
        )

    bron_panden = (
        lees_bereikbaarheids_panden(modus)
        if panden_bereikbaarheid is None
        else panden_bereikbaarheid
    )
    panden = pand_selectie(bron_panden, modus, max_panden, buurtcode=buurtcode)
    if panden.empty:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    print(
        f"[{modus}] start pandniveau-flowmap voor {len(panden)} panden",
        flush=True,
    )
    voorzieningen = lees_voorzieningen() if voorzieningen_data is None else voorzieningen_data
    print(f"[{modus}] {NAAM} geladen: {len(voorzieningen)}", flush=True)
    if modus in DIRECTE_MODI:
        netwerk_modi = {modus}
    elif modus == "auto":
        netwerk_modi = {"auto", "lopen"}
    else:
        netwerk_modi = {OV_ACCESS_MODUS[modus], "lopen"}

    netwerken = bouw_netwerken(netwerk_modi)
    edge_lookups = {
        netwerk_modus: bouw_edge_lookup(netwerk)
        for netwerk_modus, netwerk in netwerken.items()
    }
    lookup_richtingen = sum(len(edge_lookup) for edge_lookup in edge_lookups.values())
    print(f"[{modus}] edge lookup opgebouwd: {lookup_richtingen} richtingen", flush=True)

    target_snap = None
    parkeer_targets = None
    parkeer_auto_snap = None
    parkeer_loop_snap = None
    voorziening_loop_snap = None
    ov_stops = None
    ov_basis_graph = None
    ov_graph_cache = {}
    stop_target_snaps = {}
    stop_loop_starts = None

    if modus in DIRECTE_MODI:
        target_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            voorzieningen,
            netwerken[modus],
            "doel",
            max_snap_meter,
        )
        print(f"[{modus}] voorzieningen aan netwerk gesnapt", flush=True)
    elif modus == "auto":
        print(f"[{modus}] parkeerdoelen voorbereiden", flush=True)
        parkeer_targets = bereikbaarheid_auto.bereken_parkeer_targets(
            voorzieningen,
            netwerken["lopen"],
            max_snap_meter,
            10.0,
        )
        parkeer_auto_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            parkeer_targets,
            netwerken["auto"],
            "doel",
            max_snap_meter,
        )
        parkeer_loop_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            parkeer_targets,
            netwerken["lopen"],
            "pand",
            max_snap_meter,
        )
        voorziening_loop_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            voorzieningen,
            netwerken["lopen"],
            "doel",
            max_snap_meter,
        )
        print(f"[{modus}] parkeerdoelen en voorziening-snaps klaar", flush=True)
    else:
        print(f"[{modus}] OV-stops en OV-routegraph voorbereiden", flush=True)
        ov_stops = bereikbaarheid_ov.lees_ov_stops()
        ov_basis_graph = bouw_ov_basis_graph(ov_stops, max_snap_meter)
        access_modus = OV_ACCESS_MODUS[modus]
        stop_target_snaps[access_modus] = bereikbaarheid_netwerk.snap_points_naar_edges(
            ov_stops,
            netwerken[access_modus],
            "doel",
            max_snap_meter,
        )
        stop_loop_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            ov_stops,
            netwerken["lopen"],
            "pand",
            max_snap_meter,
        )
        stop_loop_starts = ov_stops.join(stop_loop_snap)
        voorziening_loop_snap = bereikbaarheid_netwerk.snap_points_naar_edges(
            voorzieningen,
            netwerken["lopen"],
            "doel",
            max_snap_meter,
        )
        print(f"[{modus}] OV-voorbereiding klaar", flush=True)

    route_delen = []
    segmenten = {}
    totaal = len(panden)
    for teller, (idx, rij) in enumerate(panden.iterrows(), start=1):
        if teller == 1 or teller % 1000 == 0 or teller == totaal:
            print_voortgang(modus, teller, totaal, rij.get("pand_id", idx))
        pand = panden.loc[[idx]]
        if modus in DIRECTE_MODI:
            route = pandroute_records(
                pand,
                voorzieningen,
                target_snap,
                netwerken[modus],
                edge_lookups[modus],
                modus,
            )
        elif modus == "auto":
            route = auto_pandroute_records(
                pand,
                voorzieningen,
                parkeer_targets,
                parkeer_auto_snap,
                parkeer_loop_snap,
                voorziening_loop_snap,
                netwerken,
                edge_lookups,
            )
        else:
            route = ov_pandroute_records(
                pand,
                modus,
                voorzieningen,
                ov_stops,
                ov_basis_graph,
                ov_graph_cache,
                stop_target_snaps,
                stop_loop_starts,
                voorziening_loop_snap,
                netwerken,
                edge_lookups,
                max_snap_meter,
            )
        if not route.empty:
            update_segmenten(segmenten, route)
            if bewaar_individuele_routes:
                route_delen.append(route)

    if not segmenten:
        print(f"[{modus}] geen pandroutes gevonden; geen flowmap geschreven", flush=True)
        return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)

    print(
        f"[{modus}] pandroutes verwerkt; aggregeer {len(segmenten)} segmenten",
        flush=True,
    )
    output_suffix = f"{modus}_test_{max_panden}" if max_panden is not None else modus
    if bewaar_individuele_routes and schrijf_bestand:
        routes = gpd.GeoDataFrame(pd.concat(route_delen, ignore_index=True), crs=CRS_RD)
        pad = tabel_output_basis_dir() / "pandstromen" / f"pand_{NAAM}_routes_{output_suffix}.gpkg"
        schrijf_gpkg(routes, pad, f"pand_{NAAM}_routes_{output_suffix}")

    flowmap = segmenten_naar_gdf(segmenten, modus)
    if schrijf_bestand:
        pad = tabel_output_basis_dir() / "pandstromen" / f"pand_{NAAM}_flowmap_{output_suffix}.gpkg"
        schrijf_gpkg(flowmap, pad, f"pand_{NAAM}_flowmap_{output_suffix}")
    print(f"[{modus}] klaar: {len(flowmap)} flowsegmenten", flush=True)
    return flowmap
