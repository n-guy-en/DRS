"""Validatiehelpers voor de GTFS/OV-netwerkworkflow."""

import pandas as pd

from .instellingen import VALIDATIE_DIR
from .tijd import seconden_naar_tijd


def check_kolommen(dataframe, naam, kolommen):
    """Controleer verplichte kolommen en stop met duidelijke fout."""
    if dataframe is None:
        raise ValueError(f"Geen dataframe voor {naam}.")

    missend = [
        kolom
        for kolom in kolommen
        if kolom not in dataframe.columns
    ]

    if missend:
        raise ValueError(f"Missende kolommen in {naam}: {missend}")

    print("Kolomcontrole ok:", naam)


def controleer_gtfs_kolommen(agency, routes, trips, stops, stop_times):
    check_kolommen(
        agency,
        "agency",
        ["agency_id", "agency_name"],
    )

    check_kolommen(
        routes,
        "routes",
        [
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_type",
        ],
    )

    check_kolommen(
        trips,
        "trips",
        [
            "route_id",
            "trip_id",
            "service_id",
            "direction_id",
            "shape_id",
        ],
    )

    check_kolommen(
        stops,
        "stops",
        [
            "stop_id",
            "stop_name",
            "stop_lat",
            "stop_lon",
        ],
    )

    check_kolommen(
        stop_times,
        "stop_times",
        [
            "trip_id",
            "arrival_time",
            "departure_time",
            "stop_id",
            "stop_sequence",
        ],
    )


def _tijd_of_leeg(seconden):
    if pd.isna(seconden):
        return ""
    return seconden_naar_tijd(int(seconden))


def schrijf_stop_times_tijdvalidatie(stop_times_processed):
    """Schrijf overzicht van meegenomen stop_times na Friesland-filter."""
    samenvatting = (
        stop_times_processed.groupby(["mode", "operator"], dropna=False)
        .agg(
            aantal_stop_times=("stop_id", "count"),
            aantal_trips=("trip_id", "nunique"),
            eerste_departure_seconds=("departure_seconds", "min"),
            laatste_departure_seconds=("departure_seconds", "max"),
            eerste_arrival_seconds=("arrival_seconds", "min"),
            laatste_arrival_seconds=("arrival_seconds", "max"),
            ontbrekende_departure_seconds=("departure_seconds", lambda s: s.isna().sum()),
            ontbrekende_arrival_seconds=("arrival_seconds", lambda s: s.isna().sum()),
        )
        .reset_index()
    )
    for kolom in [
        "eerste_departure_seconds",
        "laatste_departure_seconds",
        "eerste_arrival_seconds",
        "laatste_arrival_seconds",
    ]:
        samenvatting[kolom.replace("_seconds", "_time")] = samenvatting[kolom].apply(
            _tijd_of_leeg
        )

    pad = VALIDATIE_DIR / "validatie_tijden_stop_times.csv"
    samenvatting.to_csv(pad, index=False)
    print(f"Opgeslagen tijdvalidatie stop_times: {pad}")
    return samenvatting


def schrijf_network_edges_tijdvalidatie(network_edges):
    """Schrijf overzicht van reistijden en correcties per mode/bron."""
    samenvatting = (
        network_edges.groupby(["mode", "travel_time_source"], dropna=False)
        .agg(
            aantal_edges=("edge_id", "count"),
            min_reistijd_min=("travel_time_min", "min"),
            mediaan_reistijd_min=("travel_time_min", "median"),
            max_reistijd_min=("travel_time_min", "max"),
            min_originele_reistijd_min=("travel_time_original_min", "min"),
            mediaan_originele_reistijd_min=("travel_time_original_min", "median"),
            max_originele_reistijd_min=("travel_time_original_min", "max"),
            aantal_origineel_nul=("travel_time_original_min", lambda s: s.eq(0).sum()),
            aantal_gecorrigeerd=("travel_time_correction_delta_min", lambda s: s.ne(0).sum()),
            eerste_vertrek_seconds=("departure_seconds", "min"),
            laatste_vertrek_seconds=("departure_seconds", "max"),
            eerste_aankomst_seconds=("arrival_seconds", "min"),
            laatste_aankomst_seconds=("arrival_seconds", "max"),
        )
        .reset_index()
    )
    for kolom in [
        "eerste_vertrek_seconds",
        "laatste_vertrek_seconds",
        "eerste_aankomst_seconds",
        "laatste_aankomst_seconds",
    ]:
        samenvatting[kolom.replace("_seconds", "_time")] = samenvatting[kolom].apply(
            _tijd_of_leeg
        )

    afronden = [
        "min_reistijd_min",
        "mediaan_reistijd_min",
        "max_reistijd_min",
        "min_originele_reistijd_min",
        "mediaan_originele_reistijd_min",
        "max_originele_reistijd_min",
    ]
    samenvatting[afronden] = samenvatting[afronden].round(2)

    pad = VALIDATIE_DIR / "validatie_tijden_network_edges.csv"
    samenvatting.to_csv(pad, index=False)
    print(f"Opgeslagen tijdvalidatie network_edges: {pad}")
    return samenvatting
