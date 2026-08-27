"""Bereken voorzieningbereikbaarheid voor lopen, fiets, auto en OV."""

from __future__ import annotations

import importlib
from dataclasses import replace

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString


from .auto import bereken_auto, bereken_parkeer_targets
from .instellingen import (
    CRS_RD,
    MODUS_CONFIG,
    ONDERWIJS_NIVEAU_NAMEN,
    DEFAULT_RUNTIME_CONFIG,
    RuntimeConfig,
    WANDEL_METER_PER_MIN,
    bereikbaar_kolom as maak_bereikbaar_kolom,
    binnen_kolom as maak_binnen_kolom,
    configure,
    current_config,
    netwerk_tijd_kolom,
    norm_min_voor_panden,
    norm_kolom,
    parkeer_idx_kolom,
    parkeer_loop_bron_kolom,
    parkeer_loop_kolom,
    reistijd_bron_kolom,
    reistijd_profiel_kolom,
    tijd_kolom as maak_tijd_kolom,
    voorziening,
    voorziening_resultaat_kolom,
)
from .invoer import lees_panden, lees_pandpolygonen, lees_voorzieningen
from .netwerk import (
    Routenetwerk,
    bereken_directe_modus,
    lees_verkeersnetwerk,
    voeg_route_lengte_toe,
    voorbeeldroute_naar_targets,
)
from .output import schrijf_multimodale_output, schrijf_output, schrijf_voorbeeldroute
from .ov import (
    bereken_ov_access_met_profielen,
    lees_ov_stops,
    ov_reistijdprofielen_vanaf_stops,
    voeg_ov_route_naar_voorziening_toe,
)


# %% CONFIGURATIE
JAAR = DEFAULT_RUNTIME_CONFIG.jaar
PAND_SELECTIE = DEFAULT_RUNTIME_CONFIG.pand_selectie
MODI = DEFAULT_RUNTIME_CONFIG.modi
MAX_SNAP_METER = DEFAULT_RUNTIME_CONFIG.max_snap_meter
GEBRUIK_PANDPOLYGONEN = DEFAULT_RUNTIME_CONFIG.gebruik_pandpolygonen
MAX_PARKEER_LOOP_MIN = DEFAULT_RUNTIME_CONFIG.max_parkeer_loop_min
MAX_OV_TRANSFER_METER = DEFAULT_RUNTIME_CONFIG.max_ov_transfer_meter
OV_DATUM = DEFAULT_RUNTIME_CONFIG.ov_datum
OV_STARTTIJD = DEFAULT_RUNTIME_CONFIG.ov_starttijd
OV_EINDTIJD = DEFAULT_RUNTIME_CONFIG.ov_eindtijd
OV_STAP_MINUTEN = DEFAULT_RUNTIME_CONFIG.ov_stap_minuten
MIN_OVERSTAP_MIN = DEFAULT_RUNTIME_CONFIG.min_overstap_min


def pas_runtime_config_toe(runtime_config: RuntimeConfig) -> None:
    global JAAR, PAND_SELECTIE, MODI, MAX_SNAP_METER, GEBRUIK_PANDPOLYGONEN
    global MAX_PARKEER_LOOP_MIN, MAX_OV_TRANSFER_METER, OV_DATUM
    global OV_STARTTIJD, OV_EINDTIJD, OV_STAP_MINUTEN, MIN_OVERSTAP_MIN

    JAAR = runtime_config.jaar
    PAND_SELECTIE = runtime_config.pand_selectie
    MODI = runtime_config.modi
    MAX_SNAP_METER = runtime_config.max_snap_meter
    GEBRUIK_PANDPOLYGONEN = runtime_config.gebruik_pandpolygonen
    MAX_PARKEER_LOOP_MIN = runtime_config.max_parkeer_loop_min
    MAX_OV_TRANSFER_METER = runtime_config.max_ov_transfer_meter
    OV_DATUM = runtime_config.ov_datum
    OV_STARTTIJD = runtime_config.ov_starttijd
    OV_EINDTIJD = runtime_config.ov_eindtijd
    OV_STAP_MINUTEN = runtime_config.ov_stap_minuten
    MIN_OVERSTAP_MIN = runtime_config.min_overstap_min


def parse_modi(waarde: str) -> list[str]:
    if waarde == "all":
        return ["lopen", "fiets", "auto", "ov_lopen", "ov_fiets"]
    modi = [deel.strip() for deel in waarde.split(",") if deel.strip()]
    onbekend = sorted(set(modi) - set(MODUS_CONFIG))
    if onbekend:
        raise ValueError(f"Onbekende modi: {', '.join(onbekend)}")
    return modi


def combineer_ov_met_directe_access(
    ov_resultaat: gpd.GeoDataFrame,
    direct_resultaat: gpd.GeoDataFrame,
    modus: str,
    norm_min: float,
    direct_norm_min: float,
) -> gpd.GeoDataFrame:
    tijd_kolom = maak_tijd_kolom(modus)
    bereikbaar_kolom = maak_bereikbaar_kolom(modus)
    binnen_kolom = maak_binnen_kolom(modus)
    netwerk_kolom = netwerk_tijd_kolom(modus)
    profiel_kolommen = [
        reistijd_profiel_kolom(modus, "mediaan"),
        reistijd_profiel_kolom(modus, "min"),
        reistijd_profiel_kolom(modus, "p90"),
    ]

    resultaat = ov_resultaat.copy()
    direct_resultaat = direct_resultaat.reindex(resultaat.index)
    directe_keuze_kolommen = [
        kolom
        for kolom in [
            voorziening_resultaat_kolom("id"),
            voorziening_resultaat_kolom("naam"),
            voorziening_resultaat_kolom("straat"),
            voorziening_resultaat_kolom("huisnummer"),
            voorziening_resultaat_kolom("plaats"),
            voorziening_resultaat_kolom("lon"),
            voorziening_resultaat_kolom("lat"),
            voorziening_resultaat_kolom("idx"),
        ]
        if kolom in direct_resultaat.columns
    ]
    for kolom in directe_keuze_kolommen:
        if kolom not in resultaat.columns:
            resultaat[kolom] = pd.NA

    direct_norm_reeks = norm_min_voor_panden(
        directe_modus_voor_ov(modus),
        direct_resultaat,
        direct_norm_min,
    )
    direct_tijd = direct_resultaat[tijd_kolom]
    ov_tijd = resultaat[tijd_kolom]
    direct_binnen_norm = direct_tijd <= direct_norm_reeks
    direct_is_beter = (
        direct_tijd.notna()
        & direct_binnen_norm
        & (ov_tijd.isna() | (direct_tijd < ov_tijd))
    )

    vervang_kolommen = [
        kolom
        for kolom in direct_resultaat.columns
        if kolom in resultaat.columns and kolom != "geometry"
    ]
    resultaat.loc[direct_is_beter, vervang_kolommen] = direct_resultaat.loc[
        direct_is_beter,
        vervang_kolommen,
    ]

    resultaat[reistijd_bron_kolom(modus)] = "ov"
    resultaat.loc[direct_is_beter, reistijd_bron_kolom(modus)] = "direct_access"
    resultaat.loc[
        resultaat[tijd_kolom].isna(),
        reistijd_bron_kolom(modus),
    ] = "geen_route"

    for kolom in profiel_kolommen:
        if kolom not in resultaat.columns:
            resultaat[kolom] = resultaat[tijd_kolom]
        resultaat.loc[direct_is_beter, kolom] = direct_tijd.loc[direct_is_beter]

    norm_reeks = norm_min_voor_panden(modus, resultaat, norm_min)
    resultaat[bereikbaar_kolom] = resultaat[tijd_kolom].notna()
    resultaat[binnen_kolom] = resultaat[tijd_kolom] <= norm_reeks
    resultaat[norm_kolom(modus)] = norm_reeks

    afronden = [
        "pand_snap_meter",
        "pand_positie_meter",
        "pand_edge_lengte_meter",
        netwerk_kolom,
        tijd_kolom,
        *profiel_kolommen,
    ]
    for kolom in afronden:
        if kolom in resultaat.columns:
            resultaat[kolom] = resultaat[kolom].round(2)

    return resultaat


# %% Auto- en voorbeeldroutehulpen
def directe_modus_voor_ov(modus: str) -> str:
    if modus == "ov_lopen":
        return "lopen"
    if modus == "ov_fiets":
        return "fiets"
    raise ValueError(f"Geen directe modaliteit voor {modus}.")


def voeg_auto_loopnatransport_toe(
    autoroute,
    parkeer_targets,
    voorzieningen,
    loopnetwerk,
    max_snap_meter: float,
):
    if autoroute is None or autoroute.empty or "target_idx" not in autoroute.columns:
        return autoroute

    target_idx = autoroute["target_idx"].dropna()
    if target_idx.empty:
        return autoroute

    target_idx = target_idx.iloc[0]
    if target_idx not in parkeer_targets.index:
        return autoroute

    parkeer_start = parkeer_targets.loc[[target_idx]].copy()
    loop_tijd = parkeer_start[parkeer_loop_kolom()].iloc[0]
    voorziening_idx = parkeer_start.get(
        parkeer_idx_kolom(),
        pd.Series(dtype=object),
    ).iloc[0]
    if isinstance(voorziening_idx, float) and voorziening_idx.is_integer():
        voorziening_idx = int(voorziening_idx)
    if pd.isna(voorziening_idx) or voorziening_idx not in voorzieningen.index:
        return autoroute

    parkeer_start[maak_tijd_kolom("auto_loop")] = loop_tijd
    parkeer_start[maak_binnen_kolom("auto_loop")] = True
    parkeer_start["pand_node"] = parkeer_start.get("pand_node", None)

    looproute = gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
    loop_bron = parkeer_start.get(
        parkeer_loop_bron_kolom(),
        pd.Series([""]),
    ).iloc[0]
    if loop_bron != "luchtlijn_fallback":
        loop_resultaat = bereken_directe_modus(
            parkeer_start,
            voorzieningen.loc[[voorziening_idx]],
            loopnetwerk,
            "auto_loop",
            9999.0,
            max_snap_meter,
        )
        looproute = voorbeeldroute_naar_targets(
            loop_resultaat,
            voorzieningen.loc[[voorziening_idx]],
            loopnetwerk,
            "auto_loop",
            max_snap_meter,
        )

    if looproute.empty:
        parkeer_geom = parkeer_start.to_crs(CRS_RD).geometry.iloc[0]
        voorziening_geom = voorzieningen.to_crs(CRS_RD).loc[voorziening_idx].geometry
        if (
            parkeer_geom is None
            or voorziening_geom is None
            or parkeer_geom.is_empty
            or voorziening_geom.is_empty
        ):
            return autoroute

        looproute = gpd.GeoDataFrame(
            [
                {
                    "route_order": 1,
                    "edge_id": pd.NA,
                    "segment_type": f"loop_parkeerplek_naar_{voorziening()}",
                    "segment_lengte_meter": round(
                        float(LineString([parkeer_geom, voorziening_geom]).length),
                        2,
                    ),
                    "reistijd_min": loop_tijd,
                    "modus": "auto_loop",
                    "pand_id": parkeer_start.get("pand_id", pd.Series([""])).iloc[0],
                    "pand_idx": parkeer_start.index[0],
                    "route_reistijd_min": loop_tijd,
                    "target_idx": voorziening_idx,
                    parkeer_loop_bron_kolom(): loop_bron,
                    "geometry": LineString([parkeer_geom, voorziening_geom]),
                }
            ],
            geometry="geometry",
            crs=CRS_RD,
        )

    start_order = int(autoroute["route_order"].max()) + 1
    looproute = looproute.copy()
    looproute["route_order"] = range(start_order, start_order + len(looproute))
    looproute["modus"] = "auto"
    looproute["segment_type"] = f"loop_parkeerplek_naar_{voorziening()}"
    looproute["pand_id"] = autoroute["pand_id"].iloc[0]
    looproute["pand_idx"] = autoroute["pand_idx"].iloc[0]
    looproute["route_reistijd_min"] = autoroute["route_reistijd_min"].iloc[0]
    return voeg_route_lengte_toe(pd.concat([autoroute, looproute], ignore_index=True))


def eerste_index_uit_route(route, kolom: str, masker=None):
    if route is None or route.empty or kolom not in route.columns:
        return None
    waarden = route.loc[masker, kolom] if masker is not None else route[kolom]
    waarden = waarden.dropna()
    if waarden.empty:
        return None
    waarde = waarden.iloc[0]
    if isinstance(waarde, float) and waarde.is_integer():
        return int(waarde)
    return waarde


def voeg_punt_toe(records: list[dict], punten, idx, punt_type: str, modus: str) -> None:
    if idx is None or idx not in punten.index:
        return
    rij = punten.loc[idx]
    geom = rij.geometry
    if geom is None or geom.is_empty:
        return

    record = {
        "punt_type": punt_type,
        "modus": modus,
        "bron_index": idx,
        "geometry": geom,
    }
    if "pand_id" in punten.columns:
        record["pand_id"] = rij.get("pand_id")
    if "naam" in punten.columns:
        record["naam"] = rij.get("naam")
    elif "name" in punten.columns:
        record["naam"] = rij.get("name")
    records.append(record)


def maak_voorbeeldpunten(
    route,
    panden,
    voorzieningen,
    modus: str,
    parkeer_targets=None,
    ov_stops=None,
    ov_target_is_stop: bool = False,
) -> gpd.GeoDataFrame:
    if route is None or route.empty:
        return gpd.GeoDataFrame(geometry=[], crs=panden.crs)

    records = []
    pand_idx = eerste_index_uit_route(route, "pand_idx")
    voeg_punt_toe(records, panden, pand_idx, "pand", modus)

    if modus == "auto" and parkeer_targets is not None:
        loop_masker = route.get(
            "segment_type",
            pd.Series(index=route.index, dtype=object),
        ).eq(
            f"loop_parkeerplek_naar_{voorziening()}",
        )
        parkeer_idx = eerste_index_uit_route(route, "target_idx", ~loop_masker)
        voorziening_idx = eerste_index_uit_route(route, "target_idx", loop_masker)
        voeg_punt_toe(records, parkeer_targets, parkeer_idx, "parkeerplek", modus)
        voeg_punt_toe(records, voorzieningen, voorziening_idx, voorziening(), modus)
    elif ov_target_is_stop and ov_stops is not None:
        stop_idx = eerste_index_uit_route(route, "ov_start_stop_idx")
        if stop_idx is None:
            stop_idx = eerste_index_uit_route(route, "target_idx")
        eind_stop_idx = eerste_index_uit_route(route, "ov_eind_stop_idx")
        voorziening_idx = eerste_index_uit_route(route, f"{voorziening()}_idx")

        voeg_punt_toe(records, ov_stops, stop_idx, "opstaphalte", modus)
        if eind_stop_idx is not None and eind_stop_idx != stop_idx:
            voeg_punt_toe(records, ov_stops, eind_stop_idx, "uitstaphalte", modus)
        elif eind_stop_idx is not None:
            voeg_punt_toe(records, ov_stops, eind_stop_idx, "uitstaphalte", modus)

        if voorziening_idx is not None:
            voeg_punt_toe(records, voorzieningen, voorziening_idx, voorziening(), modus)
        elif stop_idx in ov_stops.index:
            stop_gdf = ov_stops.loc[[stop_idx]]
            nearest = gpd.sjoin_nearest(
                stop_gdf.to_crs(voorzieningen.crs),
                voorzieningen,
                how="left",
                distance_col="afstand_meter",
            )
            voorziening_idx = nearest["index_right"].dropna()
            if not voorziening_idx.empty:
                voeg_punt_toe(
                    records,
                    voorzieningen,
                    voorziening_idx.iloc[0],
                    f"{voorziening()}_bij_ov_profiel",
                    modus,
                )
    else:
        voorziening_idx = eerste_index_uit_route(route, "target_idx")
        voeg_punt_toe(records, voorzieningen, voorziening_idx, voorziening(), modus)

    return gpd.GeoDataFrame(records, geometry="geometry", crs=panden.crs)


# %% Workflow uitvoeren
def run_actieve_configuratie(
    maak_pand_flowmaps: bool = False,
    maak_voorbeeldroutes: bool = False,
) -> None:
    pandstromen = None
    if maak_pand_flowmaps:
        from . import pandstromen as pandstromen_module

        pandstromen = importlib.reload(pandstromen_module)

    modi = parse_modi(MODI)
    print(
        "Instellingen: "
        f"voorziening={voorziening()}, jaar={JAAR}, pand_selectie={PAND_SELECTIE}, "
        f"modi={','.join(modi)}, ov_datum={OV_DATUM}, "
        f"ov_venster={OV_STARTTIJD}-{OV_EINDTIJD}"
    )
    panden = lees_panden(JAAR, PAND_SELECTIE)
    voorzieningen = lees_voorzieningen()
    pandpolygonen = None
    if GEBRUIK_PANDPOLYGONEN:
        pandpolygonen = lees_pandpolygonen(JAAR)

    netwerken: dict[str, Routenetwerk] = {}

    def netwerk(naam: str, snap_meter_per_min: float) -> Routenetwerk:
        if naam not in netwerken:
            netwerken[naam] = lees_verkeersnetwerk(naam, snap_meter_per_min)
        return netwerken[naam]

    loopnetwerk = None
    ov_profielen_vanaf_stop = None
    ov_stops = None
    parkeer_targets = None
    resultaten_per_modus = {}

    for modus in modi:
        print(f"\n=== Bereken {modus} ===")
        config = MODUS_CONFIG[modus]
        voorbeeldroute = None
        voorbeeldpunten = None

        if modus in {"lopen", "fiets"}:
            route_netwerk = netwerk(config["netwerk"], config["snap_meter_per_min"])
            resultaat = bereken_directe_modus(
                panden,
                voorzieningen,
                route_netwerk,
                modus,
                config["norm_min"],
                MAX_SNAP_METER,
            )
            if maak_voorbeeldroutes:
                voorbeeldroute = voorbeeldroute_naar_targets(
                    resultaat,
                    voorzieningen,
                    route_netwerk,
                    modus,
                    MAX_SNAP_METER,
                )
                voorbeeldpunten = maak_voorbeeldpunten(
                    voorbeeldroute,
                    panden,
                    voorzieningen,
                    modus,
                )
        elif modus == "auto":
            loopnetwerk = loopnetwerk or netwerk("voetganger_osm", WANDEL_METER_PER_MIN)
            autonetwerk = netwerk(config["netwerk"], config["snap_meter_per_min"])
            if parkeer_targets is None:
                parkeer_targets = bereken_parkeer_targets(
                    voorzieningen,
                    loopnetwerk,
                    MAX_SNAP_METER,
                    MAX_PARKEER_LOOP_MIN,
                )
            resultaat = bereken_auto(
                panden,
                voorzieningen,
                autonetwerk,
                loopnetwerk,
                config["norm_min"],
                MAX_SNAP_METER,
                MAX_PARKEER_LOOP_MIN,
                parkeer_targets=parkeer_targets,
            )
            if maak_voorbeeldroutes:
                voorbeeldroute = voorbeeldroute_naar_targets(
                    resultaat,
                    parkeer_targets,
                    autonetwerk,
                    modus,
                    MAX_SNAP_METER,
                )
                voorbeeldroute = voeg_auto_loopnatransport_toe(
                    voorbeeldroute,
                    parkeer_targets,
                    voorzieningen,
                    loopnetwerk,
                    MAX_SNAP_METER,
                )
                voorbeeldpunten = maak_voorbeeldpunten(
                    voorbeeldroute,
                    panden,
                    voorzieningen,
                    modus,
                    parkeer_targets=parkeer_targets,
                )
        else:
            loopnetwerk = loopnetwerk or netwerk("voetganger_osm", WANDEL_METER_PER_MIN)
            if ov_stops is None:
                ov_stops = lees_ov_stops()
            if ov_profielen_vanaf_stop is None:
                ov_profielen_vanaf_stop = ov_reistijdprofielen_vanaf_stops(
                    ov_stops,
                    voorzieningen,
                    loopnetwerk,
                    MAX_SNAP_METER,
                    MAX_OV_TRANSFER_METER,
                    OV_DATUM,
                    OV_STARTTIJD,
                    OV_EINDTIJD,
                    OV_STAP_MINUTEN,
                    MIN_OVERSTAP_MIN,
                )
            access_netwerk = netwerk(
                config["access_netwerk"],
                config["snap_meter_per_min"],
            )
            resultaat = bereken_ov_access_met_profielen(
                panden,
                ov_stops,
                voorzieningen,
                ov_profielen_vanaf_stop,
                access_netwerk,
                modus,
                config["norm_min"],
                MAX_SNAP_METER,
            )
            direct_resultaat = bereken_directe_modus(
                panden,
                voorzieningen,
                access_netwerk,
                modus,
                MODUS_CONFIG[directe_modus_voor_ov(modus)]["norm_min"],
                MAX_SNAP_METER,
            )
            resultaat = combineer_ov_met_directe_access(
                resultaat,
                direct_resultaat,
                modus,
                config["norm_min"],
                MODUS_CONFIG[directe_modus_voor_ov(modus)]["norm_min"],
            )
            if maak_voorbeeldroutes:
                bron_kolom = reistijd_bron_kolom(modus)
                direct_resultaten = resultaat[
                    resultaat[bron_kolom].eq("direct_access")
                ].copy()
                ov_resultaten = resultaat[resultaat[bron_kolom].eq("ov")].copy()
                ov_target_is_stop = False
                stops_met_profiel = None
                voorbeeldroute = gpd.GeoDataFrame(geometry=[], crs=CRS_RD)
                if not ov_resultaten.empty:
                    stops_met_profiel = ov_stops[
                        ov_stops["node_id"].astype(str).isin(ov_profielen_vanaf_stop)
                    ].copy()
                    voorbeeldroute = voorbeeldroute_naar_targets(
                        ov_resultaten,
                        stops_met_profiel,
                        access_netwerk,
                        modus,
                        MAX_SNAP_METER,
                    )
                    if not voorbeeldroute.empty:
                        voorbeeldroute["segment_type"] = "access_naar_opstaphalte"
                        voorbeeldroute = voeg_ov_route_naar_voorziening_toe(
                            voorbeeldroute,
                            ov_stops,
                            voorzieningen,
                            loopnetwerk,
                            modus,
                            MAX_SNAP_METER,
                            MAX_OV_TRANSFER_METER,
                        )
                        ov_target_is_stop = True
                if voorbeeldroute.empty and not direct_resultaten.empty:
                    voorbeeldroute = voorbeeldroute_naar_targets(
                        direct_resultaten,
                        voorzieningen,
                        access_netwerk,
                        modus,
                        MAX_SNAP_METER,
                    )
                if voorbeeldroute.empty:
                    voorbeeldroute = voorbeeldroute_naar_targets(
                        resultaat,
                        voorzieningen,
                        access_netwerk,
                        modus,
                        MAX_SNAP_METER,
                    )
                voorbeeldpunten = maak_voorbeeldpunten(
                    voorbeeldroute,
                    panden,
                    voorzieningen,
                    modus,
                    ov_stops=stops_met_profiel if ov_target_is_stop else None,
                    ov_target_is_stop=ov_target_is_stop,
                )

        schrijf_output(resultaat, modus, pandpolygonen)
        resultaten_per_modus[modus] = resultaat
        if maak_voorbeeldroutes:
            schrijf_voorbeeldroute(voorbeeldroute, modus, voorbeeldpunten)
        if pandstromen is not None:
            print(f"\n=== Pandniveau-flowmap: {modus} ===", flush=True)
            pandstromen.maak_pand_flowmap(
                modus=modus,
                max_snap_meter=MAX_SNAP_METER,
                panden_bereikbaarheid=resultaat,
                voorzieningen_data=voorzieningen,
            )

    schrijf_multimodale_output(resultaten_per_modus, pandpolygonen)


def parse_onderwijs_niveaus(waarde: str) -> list[str]:
    if waarde == "all":
        return list(ONDERWIJS_NIVEAU_NAMEN)
    niveaus = [deel.strip() for deel in waarde.split(",") if deel.strip()]
    onbekend = sorted(set(niveaus) - set(ONDERWIJS_NIVEAU_NAMEN))
    if onbekend:
        raise ValueError(f"Onbekende onderwijsniveaus: {', '.join(onbekend)}")
    return niveaus


def run_bereikbaarheid(
    voorziening_naam: str,
    onderwijs_niveaus: str = "all",
    runtime_config: RuntimeConfig | None = None,
    maak_pand_flowmaps: bool = False,
    maak_voorbeeldroutes: bool = False,
    **runtime_overrides,
) -> None:
    if runtime_config is not None or runtime_overrides:
        basis = runtime_config or DEFAULT_RUNTIME_CONFIG
        pas_runtime_config_toe(replace(basis, **runtime_overrides))

    if voorziening_naam == "onderwijs":
        for onderwijsniveau in parse_onderwijs_niveaus(onderwijs_niveaus):
            configure("onderwijs", onderwijsniveau)
            label = ONDERWIJS_NIVEAU_NAMEN[onderwijsniveau]
            print(f"\n=== Onderwijsniveau {onderwijsniveau}: {label} ===")
            run_actieve_configuratie(
                maak_pand_flowmaps=maak_pand_flowmaps,
                maak_voorbeeldroutes=maak_voorbeeldroutes,
            )
        return

    configure(voorziening_naam)
    print(f"\n=== Voorziening: {current_config().label} ===")
    run_actieve_configuratie(
        maak_pand_flowmaps=maak_pand_flowmaps,
        maak_voorbeeldroutes=maak_voorbeeldroutes,
    )
