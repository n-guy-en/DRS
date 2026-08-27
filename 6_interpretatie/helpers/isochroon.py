"""Maak netwerkisochronen voor de actieve interpretatievoorziening.

De laag is bedoeld als begrijpelijke kaartvisualisatie naast de
bereikbaarheidsuitkomsten. Voor exacte panduitspraken blijft de
pandniveau-output uit `5_bereikbaarheid` leidend.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import sys
from pathlib import Path

import geopandas as gpd
import networkx as nx
import pandas as pd
from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, MultiPolygon, Point, Polygon
from shapely.validation import make_valid

from . import instellingen as dus_config
from .invoer import lees_voorzieningen as lees_dus_voorzieningen
from .invoer import schrijf_csv


BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_geometrie = import_module("5_bereikbaarheid.helpers.geometrie")
lijnstukken = _geometrie.lijnstukken
node_key = _geometrie.node_key

CRS_RD = dus_config.CRS_RD
CRS_WGS84 = dus_config.CRS_WGS84

MAX_SNAP_METER = 250.0

# Fallback-netwerkisochronen: buffer bereikbare netwerksegmenten tot een kaartvlak.
ISOCHRONE_BUFFER_METER = 350.0

# Fallback-netwerkisochronen: rond het kaartvlak cartografisch af en voeg kleine gaten samen.
GENERALISEER_BUFFER_METER = 250.0

SIMPLIFY_METER = 50.0
VIRTUAL_TARGET = "__isochroon_doel__"
GEBRUIK_EXACTE_PANDISOCHRONEN = True

# Exacte pandisochronen: buffer pandpolygonen binnen de norm tot een leesbare vlek.
PANDVLEK_BUFFER_METER = 150.0

# Exacte pandisochronen: rond de pandvlek af zodat losse panden één kaartbeeld vormen.
PANDVLEK_GENERALISEER_METER = 60.0

PANDVLEK_SIMPLIFY_METER = 20.0

OV_DATUM = dus_config.OV_DATUM
OV_STARTTIJD = dus_config.OV_STARTTIJD
OV_EINDTIJD = dus_config.OV_EINDTIJD
OV_STAP_MINUTEN = dus_config.OV_STAP_MINUTEN
MIN_OVERSTAP_MIN = dus_config.MIN_OVERSTAP_MIN
MAX_OV_TRANSFER_METER = dus_config.MAX_OV_TRANSFER_METER

MODI = {
    "lopen": {
        "netwerk": "voetganger_osm",
        "snap_meter_per_min": 80.0,
    },
    "fiets": {
        "netwerk": "fiets_osm",
        "snap_meter_per_min": 250.0,
    },
    "auto": {
        "netwerk": "personenauto",
        "snap_meter_per_min": 50.0 * 1000.0 / 60.0,
    },
    "ov_lopen": {
        "access_netwerk": "voetganger_osm",
        "snap_meter_per_min": 80.0,
    },
    "ov_fiets": {
        "access_netwerk": "fiets_osm",
        "snap_meter_per_min": 250.0,
    },
}

BAND_KLEUREN = [
    ("#2b8cbe", "#045a8d", 0.75),
    ("#7bccc4", "#2b8cbe", 0.60),
    ("#edf8b1", "#7bccc4", 0.50),
]


@dataclass(frozen=True)
class IsochroonCasus:
    voorziening: str
    label: str
    drempels_min: tuple[float, ...]
    norm_label: str


NETWERK_CACHE = {}
OV_PROFIEL_CACHE = {}


def tijdelijk_pad(pad: Path) -> Path:
    return pad.with_name(f".{pad.stem}.tmp{pad.suffix}")


def schrijf_geojson_atomic(gdf: gpd.GeoDataFrame, pad: Path) -> None:
    tmp_pad = tijdelijk_pad(pad)
    if tmp_pad.exists():
        tmp_pad.unlink()
    gdf.to_file(tmp_pad, driver="GeoJSON")
    tmp_pad.replace(pad)


def lees_netwerk(naam: str) -> tuple[nx.DiGraph, gpd.GeoDataFrame]:
    if naam in NETWERK_CACHE:
        return NETWERK_CACHE[naam]

    bereik_config = import_module("5_bereikbaarheid.helpers.instellingen")
    pad = bereik_config.verkeersnetwerk_pad(naam)
    print(f"Lees netwerk voor isochroon: {naam}", flush=True)
    bron_edges = gpd.read_file(
        pad,
        columns=[
            "heen_toegestaan",
            "terug_toegestaan",
            "reistijd_min",
            "lengte_meter",
            "geometry",
        ],
    ).to_crs(CRS_RD)

    graph = nx.DiGraph()
    records = []
    for rij in bron_edges.itertuples(index=False):
        delen = lijnstukken(rij.geometry)
        if not delen:
            continue
        totale_lengte = sum(max(deel.length, 0.0) for deel in delen)
        if totale_lengte <= 0:
            continue
        reistijd = float(rij.reistijd_min)
        heen = bool(rij.heen_toegestaan)
        terug = bool(rij.terug_toegestaan)

        for deel in delen:
            coords = list(deel.coords)
            if len(coords) < 2:
                continue
            u = node_key(Point(coords[0]))
            v = node_key(Point(coords[-1]))
            deel_reistijd = reistijd * (deel.length / totale_lengte)
            if heen:
                graph.add_edge(u, v, weight=deel_reistijd)
            if terug:
                graph.add_edge(v, u, weight=deel_reistijd)
            records.append(
                {
                    "u": u,
                    "v": v,
                    "edge_lengte_meter": float(deel.length),
                    "edge_reistijd_min": float(deel_reistijd),
                    "heen_toegestaan": heen,
                    "terug_toegestaan": terug,
                    "geometry": deel,
                }
            )

    edges = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)
    NETWERK_CACHE[naam] = (graph, edges)
    return graph, edges


def snap_targets_naar_netwerk(
    targets: gpd.GeoDataFrame,
    edges: gpd.GeoDataFrame,
    snap_meter_per_min: float,
    extra_kosten_kolom: str | None = None,
) -> pd.DataFrame:
    nearest = gpd.sjoin_nearest(
        targets[["geometry"]],
        edges[
            [
                "u",
                "v",
                "edge_lengte_meter",
                "edge_reistijd_min",
                "heen_toegestaan",
                "terug_toegestaan",
                "geometry",
            ]
        ],
        how="left",
        max_distance=MAX_SNAP_METER,
        distance_col="snap_meter",
    )
    nearest = nearest[nearest["index_right"].notna()].copy()
    if nearest.empty:
        return pd.DataFrame()

    target_geom = targets.geometry.reindex(nearest.index)
    edge_geom = edges.geometry.reindex(
        nearest["index_right"].astype(int).to_numpy()
    )
    posities = [
        float(edge.project(target))
        for target, edge in zip(target_geom, edge_geom)
    ]
    snap = pd.DataFrame(index=nearest.index)
    snap["u"] = nearest["u"].to_numpy()
    snap["v"] = nearest["v"].to_numpy()
    snap["edge_lengte_meter"] = pd.to_numeric(
        nearest["edge_lengte_meter"],
        errors="coerce",
    ).to_numpy()
    snap["edge_reistijd_min"] = pd.to_numeric(
        nearest["edge_reistijd_min"],
        errors="coerce",
    ).to_numpy()
    snap["heen_toegestaan"] = (
        nearest["heen_toegestaan"].fillna(False).astype(bool).to_numpy()
    )
    snap["terug_toegestaan"] = (
        nearest["terug_toegestaan"].fillna(False).astype(bool).to_numpy()
    )
    snap["snap_meter"] = pd.to_numeric(
        nearest["snap_meter"],
        errors="coerce",
    ).to_numpy()
    snap["positie_meter"] = posities
    extra = (
        pd.to_numeric(targets.loc[snap.index, extra_kosten_kolom], errors="coerce")
        if extra_kosten_kolom
        else pd.Series(0.0, index=snap.index)
    )
    snap["extra_kosten_min"] = extra.fillna(0.0).to_numpy()
    snap["snap_kosten_min"] = snap["snap_meter"] / snap_meter_per_min

    fractie = snap["positie_meter"] / snap["edge_lengte_meter"]
    snap["kosten_vanaf_u_min"] = (
        fractie * snap["edge_reistijd_min"]
        + snap["snap_kosten_min"]
        + snap["extra_kosten_min"]
    ).where(snap["heen_toegestaan"])
    snap["kosten_vanaf_v_min"] = (
        (1 - fractie) * snap["edge_reistijd_min"]
        + snap["snap_kosten_min"]
        + snap["extra_kosten_min"]
    ).where(snap["terug_toegestaan"])
    return snap


def afstanden_naar_targets(
    graph: nx.DiGraph,
    target_snap: pd.DataFrame,
    max_drempel: float,
) -> dict:
    werkgraph = graph.copy()
    werkgraph.add_node(VIRTUAL_TARGET)
    for rij in target_snap.itertuples(index=False):
        for node, kosten in [
            (rij.u, rij.kosten_vanaf_u_min),
            (rij.v, rij.kosten_vanaf_v_min),
        ]:
            if pd.isna(kosten) or float(kosten) < 0:
                continue
            if werkgraph.has_edge(node, VIRTUAL_TARGET):
                if float(kosten) < werkgraph[node][VIRTUAL_TARGET]["weight"]:
                    werkgraph[node][VIRTUAL_TARGET]["weight"] = float(kosten)
            else:
                werkgraph.add_edge(node, VIRTUAL_TARGET, weight=float(kosten))
    return nx.single_source_dijkstra_path_length(
        werkgraph.reverse(copy=True),
        VIRTUAL_TARGET,
        cutoff=max_drempel,
        weight="weight",
    )


def norm_voor_modus(modus: str) -> float:
    bereik_config = import_module("5_bereikbaarheid.helpers.instellingen")
    onderwijsniveau = (
        dus_config.ONDERWIJS_NIVEAU
        if dus_config.voorziening() == "onderwijs"
        else None
    )
    bereik_config.configure(dus_config.voorziening(), onderwijsniveau)
    return float(bereik_config.MODUS_CONFIG[modus]["norm_min"])


def drempels_voor_norm(norm_min: float) -> tuple[float, ...]:
    if norm_min <= 15 and norm_min % 5 == 0:
        return tuple(float(waarde) for waarde in range(5, int(norm_min) + 1, 5))
    if norm_min <= 30 and norm_min % 10 == 0:
        return tuple(float(waarde) for waarde in range(10, int(norm_min) + 1, 10))
    return (
        round(norm_min / 3, 1),
        round(norm_min * 2 / 3, 1),
        float(norm_min),
    )


def huidige_casus(modus: str) -> IsochroonCasus:
    norm_min = norm_voor_modus(modus)
    voorziening = dus_config.voorziening()
    label = dus_config.voorziening_label().replace("_", " ").capitalize()
    soort = "dagelijkse voorziening" if norm_min <= 15 else "regiovoorziening"
    return IsochroonCasus(
        voorziening=voorziening,
        label=label,
        drempels_min=drempels_voor_norm(norm_min),
        norm_label=f"{soort} binnen {norm_min:g} minuten",
    )


def stijl_voor_band(
    casus: IsochroonCasus,
    drempel: float,
    vorige_drempel: float,
) -> tuple[str, str, str, float]:
    index = list(casus.drempels_min).index(drempel)
    fill, stroke, fill_opacity = BAND_KLEUREN[min(index, len(BAND_KLEUREN) - 1)]
    return f"{vorige_drempel:g}-{drempel:g} min", fill, stroke, fill_opacity


def verwijder_gaten(geometry):
    if geometry is None or geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon":
        return Polygon(geometry.exterior)
    if geometry.geom_type == "MultiPolygon":
        return MultiPolygon([Polygon(poly.exterior) for poly in geometry.geoms])
    if geometry.geom_type == "GeometryCollection":
        polygonen = [
            verwijder_gaten(deel)
            for deel in geometry.geoms
            if deel.geom_type in {"Polygon", "MultiPolygon"}
        ]
        polygonen = [
            poly for poly in polygonen if poly is not None and not poly.is_empty
        ]
        if not polygonen:
            return GeometryCollection()
        return MultiPolygon(
            [
                poly
                for item in polygonen
                for poly in (
                    item.geoms if item.geom_type == "MultiPolygon" else [item]
                )
            ]
        )
    return geometry


def valide_geometrie(geometry):
    if geometry is None or geometry.is_empty:
        return geometry
    try:
        geometry = make_valid(geometry)
    except GEOSException:
        geometry = geometry.buffer(0)
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    return geometry


def maak_gebied_uit_edges(edges: gpd.GeoDataFrame):
    gebied = edges.geometry.buffer(ISOCHRONE_BUFFER_METER).union_all()
    if GENERALISEER_BUFFER_METER > 0:
        gebied = gebied.buffer(GENERALISEER_BUFFER_METER).buffer(
            -GENERALISEER_BUFFER_METER
        )
    gebied = verwijder_gaten(gebied)
    gebied = valide_geometrie(gebied)
    if SIMPLIFY_METER > 0:
        gebied = gebied.simplify(SIMPLIFY_METER, preserve_topology=True)
    gebied = valide_geometrie(gebied)
    return gebied


def verschil_geometrie(cumulatief_gebied, vorige_gebied):
    if vorige_gebied is None:
        return cumulatief_gebied
    try:
        return cumulatief_gebied.difference(vorige_gebied, grid_size=1.0)
    except GEOSException:
        return valide_geometrie(cumulatief_gebied).difference(
            valide_geometrie(vorige_gebied),
            grid_size=1.0,
        )


def maak_isochroon_records(
    casus: IsochroonCasus,
    modus: str,
    afstanden: dict,
    edges: gpd.GeoDataFrame,
) -> list[dict]:
    records = []
    vorige_gebied = None
    vorige_drempel = 0.0
    for drempel in casus.drempels_min:
        bereikbaar = edges[
            edges[["u", "v"]].apply(
                lambda rij: min(
                    afstanden.get(rij["u"], float("inf")),
                    afstanden.get(rij["v"], float("inf")),
                )
                <= drempel,
                axis=1,
            )
        ].copy()
        if bereikbaar.empty:
            continue
        cumulatief_gebied = maak_gebied_uit_edges(bereikbaar)
        geometry = verschil_geometrie(cumulatief_gebied, vorige_gebied)
        if geometry is None or geometry.is_empty:
            vorige_gebied = cumulatief_gebied
            vorige_drempel = drempel
            continue
        geometry = geometry.buffer(0)
        kleur_klasse, fill, stroke, fill_opacity = stijl_voor_band(
            casus,
            drempel,
            vorige_drempel,
        )
        records.append(
            {
                "voorziening": casus.voorziening,
                "voorziening_label": casus.label,
                "modus": modus,
                "band_van_min": vorige_drempel,
                "band_tot_min": drempel,
                "drempel_min": drempel,
                "max_norm_min": max(casus.drempels_min),
                "norm_label": casus.norm_label,
                "ov_datum": OV_DATUM if modus.startswith("ov_") else "",
                "ov_tijdvenster": (
                    f"{OV_STARTTIJD}-{OV_EINDTIJD}"
                    if modus.startswith("ov_")
                    else ""
                ),
                "isochrone_buffer_meter": ISOCHRONE_BUFFER_METER,
                "generalisatie_meter": GENERALISEER_BUFFER_METER,
                "kleur_klasse": kleur_klasse,
                "fill": fill,
                "stroke": stroke,
                "fill-opacity": fill_opacity,
                "stroke-width": 0.8,
                "stroke-opacity": 1.0,
                "geometry": geometry,
            }
        )
        vorige_gebied = cumulatief_gebied
        vorige_drempel = drempel
    return records


def pandstatus_pad(modus: str) -> Path:
    code = dus_config.MODI[modus]["code"]
    naam = (
        dus_config.ONDERWIJS_NIVEAU
        if dus_config.VOORZIENING == "onderwijs"
        else dus_config.VOORZIENING
    )
    return dus_config.BEREIKBAARHEID_DIR / modus / f"{naam}_{code}_norm_status.gpkg"


def lees_pandstatus(modus: str) -> gpd.GeoDataFrame | None:
    pad = pandstatus_pad(modus)
    if not pad.exists():
        return None
    panden = gpd.read_file(pad)
    if panden.crs is None:
        panden = panden.set_crs(CRS_WGS84)
    return panden.to_crs(CRS_RD)


def polygon_delen(geometry) -> list:
    if geometry is None or geometry.is_empty:
        return []
    geometry = valide_geometrie(geometry)
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return [deel for deel in geometry.geoms if deel is not None and not deel.is_empty]
    if geometry.geom_type == "GeometryCollection":
        delen = []
        for deel in geometry.geoms:
            if deel.geom_type in {"Polygon", "MultiPolygon"}:
                delen.extend(polygon_delen(deel))
        return delen
    return []


def maak_exacte_pandisochroon_records(
    casus: IsochroonCasus,
    modus: str,
    panden: gpd.GeoDataFrame,
) -> list[dict]:
    """Maak isochroonbanden uit de exacte pandstatus-output."""

    tijd_kolom = f"reistijd_{casus.voorziening}_{modus}_min"
    binnen_kolom = f"binnen_norm_{casus.voorziening}_{modus}"
    if tijd_kolom not in panden.columns or binnen_kolom not in panden.columns:
        return []

    panden = panden[
        panden[binnen_kolom].fillna(False).astype(bool)
        & pd.to_numeric(panden[tijd_kolom], errors="coerce").notna()
        & panden.geometry.notna()
        & ~panden.geometry.is_empty
    ].copy()
    if panden.empty:
        return []

    panden["_reistijd_min"] = pd.to_numeric(panden[tijd_kolom], errors="coerce")
    records = []
    vorige_ids: set = set()
    vorige_drempel = 0.0
    for drempel in casus.drempels_min:
        selectie = panden[panden["_reistijd_min"] <= drempel].copy()
        if selectie.empty:
            continue
        selectie["_pand_id"] = selectie["pand_id"].astype(str)
        huidige_ids = set(selectie["_pand_id"])
        band = selectie[~selectie["_pand_id"].isin(vorige_ids)].copy()
        if band.empty:
            vorige_ids = huidige_ids
            vorige_drempel = drempel
            continue

        kleur_klasse, fill, stroke, fill_opacity = stijl_voor_band(
            casus,
            drempel,
            vorige_drempel,
        )
        geometry = band.geometry.buffer(PANDVLEK_BUFFER_METER).union_all()
        if PANDVLEK_GENERALISEER_METER > 0:
            geometry = geometry.buffer(PANDVLEK_GENERALISEER_METER).buffer(
                -PANDVLEK_GENERALISEER_METER
            )
        if PANDVLEK_SIMPLIFY_METER > 0:
            geometry = geometry.simplify(
                PANDVLEK_SIMPLIFY_METER,
                preserve_topology=True,
            )
        geometry = valide_geometrie(geometry)
        for deelnummer, geometry in enumerate(polygon_delen(geometry), start=1):
            records.append(
                {
                    "voorziening": casus.voorziening,
                    "voorziening_label": casus.label,
                    "modus": modus,
                    "vlek_id": f"{modus}_{drempel:g}_{deelnummer}",
                    "band_van_min": vorige_drempel,
                    "band_tot_min": drempel,
                    "drempel_min": drempel,
                    "max_norm_min": max(casus.drempels_min),
                    "norm_label": casus.norm_label,
                    "ov_datum": OV_DATUM if modus.startswith("ov_") else "",
                    "ov_tijdvenster": (
                        f"{OV_STARTTIJD}-{OV_EINDTIJD}"
                        if modus.startswith("ov_")
                        else ""
                    ),
                    "isochrone_buffer_meter": PANDVLEK_BUFFER_METER,
                    "generalisatie_meter": PANDVLEK_GENERALISEER_METER,
                    "simplify_meter": PANDVLEK_SIMPLIFY_METER,
                    "kleur_klasse": kleur_klasse,
                    "fill": fill,
                    "stroke": stroke,
                    "fill-opacity": fill_opacity,
                    "stroke-width": 0.8,
                    "stroke-opacity": 1.0,
                    "aantal_panden": int(len(band)),
                    "geometry": geometry,
                }
            )
        vorige_ids = huidige_ids
        vorige_drempel = drempel
    return records


def maak_exacte_pandisochroon(
    casus: IsochroonCasus,
    modus: str,
) -> gpd.GeoDataFrame:
    panden = lees_pandstatus(modus)
    if panden is None:
        return gpd.GeoDataFrame(geometry="geometry", crs=CRS_RD)
    records = maak_exacte_pandisochroon_records(casus, modus, panden)
    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)


def maak_directe_netwerkisochronen(
    casus: IsochroonCasus,
    modus: str,
) -> gpd.GeoDataFrame:
    netwerknaam = MODI[modus]["netwerk"]
    graph, edges = lees_netwerk(netwerknaam)
    voorzieningen = lees_dus_voorzieningen()
    snap = snap_targets_naar_netwerk(
        voorzieningen,
        edges,
        MODI[modus]["snap_meter_per_min"],
    )
    afstanden = afstanden_naar_targets(graph, snap, max(casus.drempels_min))
    records = maak_isochroon_records(
        casus,
        modus,
        afstanden,
        edges,
    )
    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)


def ov_profielen(
    casus: IsochroonCasus,
) -> tuple[gpd.GeoDataFrame, dict[str, dict[str, float]]]:
    if casus.voorziening in OV_PROFIEL_CACHE:
        return OV_PROFIEL_CACHE[casus.voorziening]

    bereik_config = import_module("5_bereikbaarheid.helpers.instellingen")
    bereik_invoer = import_module("5_bereikbaarheid.helpers.invoer")
    bereik_netwerk = import_module("5_bereikbaarheid.helpers.netwerk")
    bereik_ov = import_module("5_bereikbaarheid.helpers.ov")

    bereik_config.configure(casus.voorziening)
    stops = bereik_ov.lees_ov_stops()
    voorzieningen = bereik_invoer.lees_voorzieningen()
    loopnetwerk = bereik_netwerk.lees_verkeersnetwerk("voetganger_osm", 80.0)
    profielen = bereik_ov.ov_reistijdprofielen_vanaf_stops(
        stops=stops,
        voorzieningen=voorzieningen,
        loopnetwerk=loopnetwerk,
        max_snap_meter=MAX_SNAP_METER,
        max_transfer_meter=MAX_OV_TRANSFER_METER,
        ov_datum=OV_DATUM,
        starttijd=OV_STARTTIJD,
        eindtijd=OV_EINDTIJD,
        stap_minuten=OV_STAP_MINUTEN,
        min_overstap_min=MIN_OVERSTAP_MIN,
    )
    OV_PROFIEL_CACHE[casus.voorziening] = (stops, profielen)
    return stops, profielen


def maak_ov_netwerkisochronen(
    casus: IsochroonCasus,
    modus: str,
) -> gpd.GeoDataFrame:
    if casus.voorziening == "ov":
        return maak_directe_netwerkisochronen(
            casus,
            "lopen" if modus == "ov_lopen" else "fiets",
        ).assign(
            modus=modus,
        )

    access_netwerknaam = MODI[modus]["access_netwerk"]
    graph, edges = lees_netwerk(access_netwerknaam)
    stops, profielen = ov_profielen(casus)
    stops = stops.copy()
    stops["ov_tijd_min"] = stops["node_id"].astype(str).map(
        {
            node_id: profiel["mediaan"]
            for node_id, profiel in profielen.items()
        }
    )
    stops = stops[stops["ov_tijd_min"].notna()].copy()
    snap = snap_targets_naar_netwerk(
        stops,
        edges,
        MODI[modus]["snap_meter_per_min"],
        extra_kosten_kolom="ov_tijd_min",
    )
    afstanden = afstanden_naar_targets(graph, snap, max(casus.drempels_min))
    records = maak_isochroon_records(
        casus,
        modus,
        afstanden,
        edges,
    )
    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)


def maak_isochroon(casus: IsochroonCasus, modus: str) -> gpd.GeoDataFrame:
    if GEBRUIK_EXACTE_PANDISOCHRONEN:
        exacte_laag = maak_exacte_pandisochroon(casus, modus)
        if not exacte_laag.empty:
            return exacte_laag

    if modus.startswith("ov_"):
        return maak_ov_netwerkisochronen(casus, modus)
    return maak_directe_netwerkisochronen(casus, modus)


def union_gebieden(geometrien):
    geometrien = [
        geometry
        for geometry in geometrien
        if geometry is not None and not geometry.is_empty
    ]
    if not geometrien:
        return GeometryCollection()
    return valide_geometrie(gpd.GeoSeries(geometrien, crs=CRS_RD).union_all())


def maak_multimodale_isochroon(
    casus: IsochroonCasus,
    lagen: list[gpd.GeoDataFrame],
) -> gpd.GeoDataFrame:
    """Combineer modaliteiten als best-beschikbare bereikbaarheid."""
    if not lagen:
        return gpd.GeoDataFrame(geometry="geometry", crs=CRS_RD)

    bron = gpd.GeoDataFrame(
        pd.concat(lagen, ignore_index=True),
        geometry="geometry",
        crs=CRS_RD,
    )
    bron = bron[bron.geometry.notna() & ~bron.geometry.is_empty].copy()
    if bron.empty:
        return gpd.GeoDataFrame(geometry="geometry", crs=CRS_RD)

    bevat_ov = bron["modus"].str.startswith("ov_").any()
    beschikbare_modi = ", ".join(sorted(bron["modus"].dropna().unique()))
    drempels = tuple(
        sorted(pd.to_numeric(bron["drempel_min"], errors="coerce").dropna().unique())
    )
    records = []
    vorige_gebied = None
    vorige_drempel = 0.0
    for drempel in drempels:
        cumulatief_gebied = union_gebieden(
            bron.loc[bron["drempel_min"] <= drempel, "geometry"]
        )
        if cumulatief_gebied.is_empty:
            continue
        geometry = verschil_geometrie(cumulatief_gebied, vorige_gebied)
        if geometry is None or geometry.is_empty:
            vorige_gebied = cumulatief_gebied
            vorige_drempel = drempel
            continue

        kleur_klasse, fill, stroke, fill_opacity = stijl_voor_band(
            IsochroonCasus(
                voorziening=casus.voorziening,
                label=casus.label,
                drempels_min=drempels,
                norm_label=casus.norm_label,
            ),
            float(drempel),
            vorige_drempel,
        )
        records.append(
            {
                "voorziening": casus.voorziening,
                "voorziening_label": casus.label,
                "modus": "multimodaal",
                "beschikbare_modi": beschikbare_modi,
                "band_van_min": vorige_drempel,
                "band_tot_min": float(drempel),
                "drempel_min": float(drempel),
                "max_norm_min": max(drempels),
                "norm_label": (
                    f"{casus.norm_label}; bereik via minstens een "
                    "geselecteerde modaliteit"
                ),
                "ov_datum": OV_DATUM if bevat_ov else "",
                "ov_tijdvenster": (
                    f"{OV_STARTTIJD}-{OV_EINDTIJD}"
                    if bevat_ov
                    else ""
                ),
                "isochrone_buffer_meter": ISOCHRONE_BUFFER_METER,
                "generalisatie_meter": GENERALISEER_BUFFER_METER,
                "kleur_klasse": kleur_klasse,
                "fill": fill,
                "stroke": stroke,
                "fill-opacity": fill_opacity,
                "stroke-width": 1.2,
                "stroke-opacity": 1.0,
                "geometry": geometry.buffer(0),
            }
        )
        vorige_gebied = cumulatief_gebied
        vorige_drempel = float(drempel)

    return gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)


def main() -> None:
    out_dir = dus_config.OUTPUT_DIR / "isochroon"
    layer_dir = dus_config.LAYERS_DIR / "isochroon"
    out_dir.mkdir(parents=True, exist_ok=True)
    layer_dir.mkdir(parents=True, exist_ok=True)

    geselecteerde_modi = dus_config.parse_modi()
    alle_lagen = []
    for modus in geselecteerde_modi:
        casus = huidige_casus(modus)
        print(f"Maak isochroon: {casus.voorziening} - {modus}", flush=True)
        laag = maak_isochroon(casus, modus)
        if laag.empty:
            print(f"Geen isochroonoutput voor {casus.voorziening} - {modus}")
            continue
        laag = gpd.GeoDataFrame(laag, geometry="geometry", crs=CRS_RD)
        laag_wgs84 = laag.to_crs(CRS_WGS84)

        naam = f"isochroon_{casus.voorziening}_{modus}"
        schrijf_geojson_atomic(laag_wgs84, layer_dir / f"{naam}.geojson")
        schrijf_csv(
            laag.drop(columns="geometry"),
            out_dir / f"{naam}.csv",
            index=False,
        )
        print(f"Opgeslagen: {layer_dir / f'{naam}.geojson'}")
        print(f"Opgeslagen: {out_dir / f'{naam}.csv'}")
        alle_lagen.append(laag)

    if not alle_lagen:
        print("Geen isochroonlagen gemaakt.")
        return

    voorziening = dus_config.voorziening()
    if dus_config.alle_modi_geselecteerd(geselecteerde_modi):
        multimodaal = maak_multimodale_isochroon(
            huidige_casus(geselecteerde_modi[0]),
            alle_lagen,
        )
        if not multimodaal.empty:
            naam = f"isochroon_{voorziening}_multimodaal"
            schrijf_geojson_atomic(
                multimodaal.to_crs(CRS_WGS84),
                layer_dir / f"{naam}.geojson",
            )
            schrijf_csv(
                multimodaal.drop(columns="geometry"),
                out_dir / f"{naam}.csv",
                index=False,
            )
            print(f"Opgeslagen: {layer_dir / f'{naam}.geojson'}")
            print(f"Opgeslagen: {out_dir / f'{naam}.csv'}")
    else:
        ontbrekend = sorted(set(dus_config.MODI) - set(geselecteerde_modi))
        print(
            "Multimodale isochroon overgeslagen; "
            "niet alle modaliteiten zijn in deze run aanwezig. "
            f"Ontbreekt: {', '.join(ontbrekend)}",
            flush=True,
        )

    print(f"Klaar: isochronen voor {voorziening}")


if __name__ == "__main__":
    main()
