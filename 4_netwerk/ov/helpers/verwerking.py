"""Verwerkingsstappen voor GTFS-tabellen."""

import pandas as pd

from .instellingen import (
    ROUTE_TYPE_NAAR_MODE,
    TOEGESTANE_OPERATORS,
    TOEGESTANE_ROUTE_TYPES,
    TUSSENBESTANDEN_DIR,
)
from .haltes import koppel_gtfs_stops_aan_haltes
from .tijd import gtfs_tijd_naar_seconden


def verwerk_routes(routes, agency):
    routes_processed = routes.copy()

    routes_processed["route_type"] = routes_processed["route_type"].astype(str)
    routes_processed["route_type_nummer"] = pd.to_numeric(
        routes_processed["route_type"],
        errors="coerce",
    )
    routes_processed["mode"] = routes_processed["route_type"].map(
        ROUTE_TYPE_NAAR_MODE
    ).fillna("unknown")

    routes_processed = routes_processed[
        routes_processed["route_type_nummer"].isin(TOEGESTANE_ROUTE_TYPES)
    ].copy()

    if "agency_id" not in routes_processed.columns:
        routes_processed["agency_id"] = ""

    if "agency_id" not in agency.columns:
        agency["agency_id"] = ""

    routes_processed = routes_processed.merge(
        agency[["agency_id", "agency_name"]],
        on="agency_id",
        how="left",
    )

    routes_processed["operator"] = routes_processed["agency_name"].fillna(
        routes_processed["agency_id"]
    )

    routes_processed = routes_processed[
        routes_processed["operator"].isin(TOEGESTANE_OPERATORS)
    ].copy()

    routes_processed["route_short_name"] = routes_processed[
        "route_short_name"
    ].replace(r"^\s*$", pd.NA, regex=True)

    routes_processed["line_id"] = routes_processed["route_short_name"].fillna(
        routes_processed["route_id"]
    )

    routes_processed = routes_processed[
        [
            "route_id",
            "line_id",
            "route_long_name",
            "route_type",
            "mode",
            "operator",
        ]
    ].copy()

    routes_processed.to_csv(
        TUSSENBESTANDEN_DIR / "routes_processed.csv",
        index=False,
    )

    print("Stap 5 klaar: routes verwerkt")
    print("Routes per mode:")
    print(routes_processed["mode"].value_counts(dropna=False))
    return routes_processed


def verwerk_trips(trips, routes_processed):
    trips_processed = trips.copy()

    trips_processed = trips_processed.merge(
        routes_processed[
            [
                "route_id",
                "line_id",
                "route_long_name",
                "route_type",
                "mode",
                "operator",
            ]
        ],
        on="route_id",
        how="inner",
    )

    if "shape_id" not in trips_processed.columns:
        trips_processed["shape_id"] = ""

    if "trip_headsign" not in trips_processed.columns:
        trips_processed["trip_headsign"] = ""

    if "direction_id" not in trips_processed.columns:
        trips_processed["direction_id"] = ""

    trips_processed.to_csv(
        TUSSENBESTANDEN_DIR / "trips_processed.csv",
        index=False,
    )

    print("Stap 6 klaar: trips verwerkt")
    print("Trips per mode:")
    print(trips_processed["mode"].value_counts(dropna=False))
    return trips_processed


def verwerk_stops(stops, haltes_frl):
    stops_processed = stops.copy()

    stops_processed["stop_lat"] = pd.to_numeric(
        stops_processed["stop_lat"],
        errors="coerce",
    )

    stops_processed["stop_lon"] = pd.to_numeric(
        stops_processed["stop_lon"],
        errors="coerce",
    )

    stops_processed = koppel_gtfs_stops_aan_haltes(
        stops_processed,
        haltes_frl,
    )

    stops_processed.to_csv(
        TUSSENBESTANDEN_DIR / "stops_processed.csv",
        index=False,
    )

    print("Stap 7 klaar: stops verwerkt")
    print("Stops:", len(stops_processed))
    print("GTFS-stops gematcht met Friese haltes:")
    print(stops_processed["in_friesland"].value_counts(dropna=False))
    return stops_processed


def stop_attribuutkolommen(stops_processed):
    basis = [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
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
    if "platform_code" in stops_processed.columns:
        return basis[:4] + ["platform_code"] + basis[4:]
    return basis


def verwerk_stop_times(stop_times, trips_processed, stops_processed):
    stop_times_processed = stop_times.copy()

    stop_times_processed["stop_sequence"] = pd.to_numeric(
        stop_times_processed["stop_sequence"],
        errors="coerce",
    )

    stop_times_processed = stop_times_processed.merge(
        trips_processed[
            [
                "trip_id",
                "route_id",
                "line_id",
                "route_long_name",
                "mode",
                "operator",
                "direction_id",
                "trip_headsign",
                "shape_id",
                "service_id",
            ]
        ],
        on="trip_id",
        how="inner",
    )

    stop_times_processed["arrival_seconds"] = stop_times_processed[
        "arrival_time"
    ].apply(gtfs_tijd_naar_seconden)

    stop_times_processed["departure_seconds"] = stop_times_processed[
        "departure_time"
    ].apply(gtfs_tijd_naar_seconden)

    stop_times_processed = stop_times_processed.merge(
        stops_processed[stop_attribuutkolommen(stops_processed)],
        on="stop_id",
        how="left",
    )

    friesland_trip_ids = stop_times_processed.loc[
        stop_times_processed["in_friesland"].fillna(False),
        "trip_id",
    ].drop_duplicates()

    stop_times_processed = stop_times_processed[
        stop_times_processed["trip_id"].isin(friesland_trip_ids)
    ].copy()

    stop_times_processed = stop_times_processed.sort_values(
        ["trip_id", "stop_sequence"]
    ).copy()

    stop_times_processed.to_csv(
        TUSSENBESTANDEN_DIR / "stop_times_processed.csv",
        index=False,
    )

    print("Stap 8 klaar: stop_times gekoppeld en verwerkt")
    print("Trips met minimaal één Friese halte:", len(friesland_trip_ids))
    print("Stop_times per mode:")
    print(stop_times_processed["mode"].value_counts(dropna=False))
    return stop_times_processed, friesland_trip_ids
