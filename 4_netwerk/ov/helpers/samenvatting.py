"""Samenvattingen voor het GTFS OV-netwerk."""

from .instellingen import OUTPUT_DIR, TUSSENBESTANDEN_DIR
from .tekst import unieke_tekst


PUBLICATIE_DROP_KOLOMMEN = [
    "from_stop_lat",
    "from_stop_lon",
    "to_stop_lat",
    "to_stop_lon",
    "trip_from_stop_lat",
    "trip_from_stop_lon",
    "trip_to_stop_lat",
    "trip_to_stop_lon",
    "min_total_travel_time_min",
    "max_total_travel_time_min",
    "total_travel_time_original_min",
    "total_travel_time_correction_delta_min",
    "total_travel_time_source",
    "total_travel_time_correction_note",
    "min_trip_total_travel_time_min",
    "max_trip_total_travel_time_min",
    "trip_total_travel_time_original_min",
    "trip_total_correction_delta_min",
    "trip_total_travel_time_source",
    "trip_total_travel_time_correction_note",
    "segment_geometry_source",
    "ov_lijn_fid",
    "ov_line_id",
    "ov_line_route_name",
    "ov_line_vervoerder",
    "from_halte_id",
    "from_halte_naam",
    "from_halte_x",
    "from_halte_y",
    "to_halte_id",
    "to_halte_naam",
    "to_halte_x",
    "to_halte_y",
]


def maak_ov_publicatie_output(tabel):
    """Maak OV-output leesbaar zonder interne GTFS-dubbelingen."""
    return tabel.drop(columns=PUBLICATIE_DROP_KOLOMMEN, errors="ignore")


def maak_route_segment_summary(network_edges):
    """Vat directe halte-naar-halte edges samen per lijnsegment."""
    route_segment_summary = (
        network_edges
        .groupby(
            [
                "route_id",
                "line_id",
                "route_long_name",
                "mode",
                "operator",
                "direction_id",
                "trip_headsign",
                "from_stop_id",
                "from_stop_name",
                "to_stop_id",
                "to_stop_name",
            ],
            dropna=False,
        )
        .agg(
            aantal_trips=("trip_id", "nunique"),
            eerste_vertrek=("departure_time", "min"),
            laatste_vertrek=("departure_time", "max"),
            min_travel_time_min=("travel_time_min", "min"),
            travel_time_min=("travel_time_min", "median"),
            max_travel_time_min=("travel_time_min", "max"),
            travel_time_original_min=("travel_time_original_min", "median"),
            travel_time_correction_delta_min=(
                "travel_time_correction_delta_min",
                "median",
            ),
            travel_time_source=("travel_time_source", unieke_tekst),
            travel_time_correction_note=("travel_time_correction_note", unieke_tekst),
            gemiddelde_afstand_m=("straight_distance_m", "mean"),
            from_in_friesland=("from_in_friesland", "first"),
            to_in_friesland=("to_in_friesland", "first"),
            from_halte_id=("from_halte_id", "first"),
            from_halte_naam=("from_halte_naam", "first"),
            from_halte_gemeente=("from_halte_gemeente", "first"),
            from_halte_x=("from_halte_x", "first"),
            from_halte_y=("from_halte_y", "first"),
            to_halte_id=("to_halte_id", "first"),
            to_halte_naam=("to_halte_naam", "first"),
            to_halte_gemeente=("to_halte_gemeente", "first"),
            to_halte_x=("to_halte_x", "first"),
            to_halte_y=("to_halte_y", "first"),
        )
        .reset_index()
    )

    if not route_segment_summary.empty:
        route_segment_summary["travel_time_min"] = route_segment_summary[
            "travel_time_min"
        ].round(2)

        route_segment_summary["travel_time_original_min"] = route_segment_summary[
            "travel_time_original_min"
        ].round(2)

        route_segment_summary["travel_time_correction_delta_min"] = (
            route_segment_summary["travel_time_correction_delta_min"].round(2)
        )

        route_segment_summary["gemiddelde_afstand_m"] = route_segment_summary[
            "gemiddelde_afstand_m"
        ].round(1)

    route_segment_summary.to_csv(
        TUSSENBESTANDEN_DIR / "route_segment_summary.csv",
        index=False,
    )

    print("Stap 10 klaar: segment-samenvatting gemaakt")
    print("Segment summary per mode:")
    if route_segment_summary.empty:
        print("Geen segmenten gemaakt.")
    else:
        print(route_segment_summary["mode"].value_counts(dropna=False))
    return route_segment_summary


def maak_lijnverbindingen(network_edges):
    """Maak reistijdrecords per directe lijnverbinding."""
    line_total_travel_times = network_edges[
        [
            "edge_id",
            "trip_id",
            "route_id",
            "line_id",
            "route_long_name",
            "mode",
            "operator",
            "service_id",
            "direction_id",
            "trip_headsign",
            "shape_id",
            "from_stop_id",
            "from_stop_name",
            "from_stop_lat",
            "from_stop_lon",
            "from_stop_sequence",
            "from_in_friesland",
            "from_halte_id",
            "from_halte_naam",
            "from_halte_x",
            "from_halte_y",
            "to_stop_id",
            "to_stop_name",
            "to_stop_lat",
            "to_stop_lon",
            "to_stop_sequence",
            "to_in_friesland",
            "to_halte_id",
            "to_halte_naam",
            "to_halte_x",
            "to_halte_y",
            "departure_time",
            "departure_seconds",
            "arrival_time",
            "arrival_seconds",
            "travel_time_original_min",
            "travel_time_min",
            "travel_time_correction_delta_min",
            "travel_time_source",
            "travel_time_correction_note",
            "straight_distance_m",
        ]
    ].copy()

    line_total_travel_times = line_total_travel_times.rename(
        columns={
            "departure_time": "connection_departure_time",
            "departure_seconds": "connection_departure_seconds",
            "arrival_time": "connection_arrival_time",
            "arrival_seconds": "connection_arrival_seconds",
            "travel_time_min": "total_travel_time_min",
            "travel_time_original_min": "total_travel_time_original_min",
            "travel_time_correction_delta_min": (
                "total_travel_time_correction_delta_min"
            ),
            "travel_time_source": "total_travel_time_source",
            "travel_time_correction_note": "total_travel_time_correction_note",
        }
    )

    line_total_travel_times["aantal_stops"] = 2
    line_total_travel_times["connection_sequence"] = line_total_travel_times[
        "from_stop_sequence"
    ]
    return line_total_travel_times


def maak_rittijden_basis(stop_times_processed):
    """Bereken totale reistijd per GTFS-rit uit stop_times."""
    trip_total_times = (
        stop_times_processed.sort_values(["trip_id", "stop_sequence"])
        .groupby("trip_id", dropna=False)
        .agg(
            trip_from_stop_id=("stop_id", "first"),
            trip_from_stop_name=("stop_name", "first"),
            trip_from_stop_lat=("stop_lat", "first"),
            trip_from_stop_lon=("stop_lon", "first"),
            trip_to_stop_id=("stop_id", "last"),
            trip_to_stop_name=("stop_name", "last"),
            trip_to_stop_lat=("stop_lat", "last"),
            trip_to_stop_lon=("stop_lon", "last"),
            trip_first_departure_time=("departure_time", "first"),
            trip_last_arrival_time=("arrival_time", "last"),
            trip_first_departure_seconds=("departure_seconds", "first"),
            trip_last_arrival_seconds=("arrival_seconds", "last"),
            trip_aantal_stops=("stop_id", "count"),
        )
        .reset_index()
    )

    trip_total_times["trip_total_travel_time_min"] = (
        (
            trip_total_times["trip_last_arrival_seconds"]
            - trip_total_times["trip_first_departure_seconds"]
        )
        / 60
    ).round(2)

    trip_total_times["trip_total_travel_time_original_min"] = trip_total_times[
        "trip_total_travel_time_min"
    ]
    trip_total_times["trip_total_travel_time_source"] = "gtfs_stop_times"
    trip_total_times["trip_total_travel_time_correction_note"] = ""
    return trip_total_times


def maak_ritcorrecties(network_edges):
    """Bereken reistijdcorrecties op ritniveau."""
    return (
        network_edges[
            network_edges["travel_time_correction_delta_min"].notna()
            & (network_edges["travel_time_correction_delta_min"] != 0)
        ]
        .groupby("trip_id", dropna=False)
        .agg(
            trip_total_correction_delta_min=(
                "travel_time_correction_delta_min",
                "sum",
            ),
            trip_total_travel_time_source=("travel_time_source", unieke_tekst),
            trip_total_travel_time_correction_note=(
                "travel_time_correction_note",
                unieke_tekst,
            ),
        )
        .reset_index()
    )


def pas_ritcorrecties_toe(trip_total_times, trip_reistijd_correcties):
    """Verwerk optionele correcties in de totale rittijden."""
    if trip_reistijd_correcties.empty:
        trip_total_times["trip_total_correction_delta_min"] = 0.0
        return trip_total_times

    trip_total_times = trip_total_times.merge(
        trip_reistijd_correcties,
        on="trip_id",
        how="left",
        suffixes=("", "_correctie"),
    )
    trip_total_times["trip_total_correction_delta_min"] = trip_total_times[
        "trip_total_correction_delta_min"
    ].fillna(0)
    trip_total_times["trip_total_travel_time_min"] = (
        trip_total_times["trip_total_travel_time_min"]
        + trip_total_times["trip_total_correction_delta_min"]
    ).round(2)
    correctie_mask = trip_total_times["trip_total_correction_delta_min"] != 0
    trip_total_times.loc[
        correctie_mask,
        "trip_total_travel_time_source",
    ] = trip_total_times.loc[
        correctie_mask,
        "trip_total_travel_time_source_correctie",
    ]
    trip_total_times.loc[
        correctie_mask,
        "trip_total_travel_time_correction_note",
    ] = trip_total_times.loc[
        correctie_mask,
        "trip_total_travel_time_correction_note_correctie",
    ]
    return trip_total_times.drop(
        columns=[
            "trip_total_travel_time_source_correctie",
            "trip_total_travel_time_correction_note_correctie",
        ],
        errors="ignore",
    )


def maak_trip_total_times(network_edges, stop_times_processed):
    """Maak totale rittijden inclusief correcties."""
    trip_total_times = maak_rittijden_basis(stop_times_processed)
    trip_reistijd_correcties = (
        maak_ritcorrecties(network_edges)
    )
    return pas_ritcorrecties_toe(trip_total_times, trip_reistijd_correcties)


def maak_trip_total_travel_times(trips_processed, trip_total_times):
    """Combineer ritmetadata met totale rittijden."""
    trip_total_metadata = trips_processed[
        [
            "trip_id",
            "route_id",
            "line_id",
            "route_long_name",
            "mode",
            "operator",
            "service_id",
            "direction_id",
            "trip_headsign",
            "shape_id",
        ]
    ].drop_duplicates("trip_id")

    trip_total_travel_times = trip_total_metadata.merge(
        trip_total_times,
        on="trip_id",
        how="inner",
    )

    trip_total_travel_times = trip_total_travel_times[
        [
            "trip_id",
            "route_id",
            "line_id",
            "route_long_name",
            "mode",
            "operator",
            "service_id",
            "direction_id",
            "trip_headsign",
            "shape_id",
            "trip_from_stop_id",
            "trip_from_stop_name",
            "trip_from_stop_lat",
            "trip_from_stop_lon",
            "trip_to_stop_id",
            "trip_to_stop_name",
            "trip_to_stop_lat",
            "trip_to_stop_lon",
            "trip_first_departure_time",
            "trip_last_arrival_time",
            "trip_first_departure_seconds",
            "trip_last_arrival_seconds",
            "trip_total_travel_time_original_min",
            "trip_total_travel_time_min",
            "trip_total_correction_delta_min",
            "trip_total_travel_time_source",
            "trip_total_travel_time_correction_note",
            "trip_aantal_stops",
        ]
    ].copy()

    trip_total_travel_times.to_csv(
        TUSSENBESTANDEN_DIR / "trip_total_travel_times.csv",
        index=False,
    )
    return trip_total_travel_times


def maak_trip_total_summary(trip_total_travel_times):
    """Vat totale GTFS-ritten samen voor publicatie en kaartcontrole."""
    trip_total_summary = (
        trip_total_travel_times
        .groupby(
            [
                "mode",
                "operator",
                "route_id",
                "line_id",
                "route_long_name",
                "direction_id",
                "trip_headsign",
                "trip_from_stop_id",
                "trip_from_stop_name",
                "trip_to_stop_id",
                "trip_to_stop_name",
            ],
            dropna=False,
        )
        .agg(
            aantal_trips=("trip_id", "nunique"),
            eerste_vertrek=("trip_first_departure_time", "min"),
            laatste_vertrek=("trip_first_departure_time", "max"),
            min_trip_total_travel_time_min=("trip_total_travel_time_min", "min"),
            trip_total_travel_time_min=("trip_total_travel_time_min", "median"),
            max_trip_total_travel_time_min=("trip_total_travel_time_min", "max"),
            trip_total_travel_time_original_min=(
                "trip_total_travel_time_original_min",
                "median",
            ),
            trip_total_correction_delta_min=(
                "trip_total_correction_delta_min",
                "median",
            ),
            trip_total_travel_time_source=(
                "trip_total_travel_time_source",
                unieke_tekst,
            ),
            trip_total_travel_time_correction_note=(
                "trip_total_travel_time_correction_note",
                unieke_tekst,
            ),
            min_aantal_stops=("trip_aantal_stops", "min"),
            aantal_stops=("trip_aantal_stops", "median"),
            max_aantal_stops=("trip_aantal_stops", "max"),
            shape_id=("shape_id", "first"),
            trip_from_stop_lat=("trip_from_stop_lat", "first"),
            trip_from_stop_lon=("trip_from_stop_lon", "first"),
            trip_to_stop_lat=("trip_to_stop_lat", "first"),
            trip_to_stop_lon=("trip_to_stop_lon", "first"),
        )
        .reset_index()
    )

    if not trip_total_summary.empty:
        trip_total_summary["trip_total_travel_time_min"] = trip_total_summary[
            "trip_total_travel_time_min"
        ].round(2)
        trip_total_summary["trip_total_travel_time_original_min"] = (
            trip_total_summary["trip_total_travel_time_original_min"].round(2)
        )
        trip_total_summary["trip_total_correction_delta_min"] = (
            trip_total_summary["trip_total_correction_delta_min"].round(2)
        )
        trip_total_summary["aantal_stops"] = trip_total_summary[
            "aantal_stops"
        ].round(0).astype("Int64")

    maak_ov_publicatie_output(trip_total_summary).to_csv(
        OUTPUT_DIR / "trip_total_summary.csv",
        index=False,
    )
    return trip_total_summary


def maak_line_total_summary(line_total_travel_times, trip_total_times):
    """Vat directe lijnverbindingen samen."""
    line_total_travel_times = line_total_travel_times.merge(
        trip_total_times,
        on="trip_id",
        how="left",
    )

    line_total_travel_times.to_csv(
        TUSSENBESTANDEN_DIR / "line_total_travel_times.csv",
        index=False,
    )

    line_total_summary = (
        line_total_travel_times
        .groupby(
            [
                "mode",
                "operator",
                "route_id",
                "line_id",
                "route_long_name",
                "direction_id",
                "trip_headsign",
                "from_stop_id",
                "from_stop_name",
                "to_stop_id",
                "to_stop_name",
            ],
            dropna=False,
        )
        .agg(
            aantal_trips=("trip_id", "nunique"),
            eerste_vertrek=("connection_departure_time", "min"),
            laatste_vertrek=("connection_departure_time", "max"),
            total_travel_time_min=("total_travel_time_min", "median"),
            min_total_travel_time_min=("total_travel_time_min", "min"),
            max_total_travel_time_min=("total_travel_time_min", "max"),
            total_travel_time_original_min=(
                "total_travel_time_original_min",
                "first",
            ),
            total_travel_time_correction_delta_min=(
                "total_travel_time_correction_delta_min",
                "first",
            ),
            total_travel_time_source=("total_travel_time_source", unieke_tekst),
            total_travel_time_correction_note=(
                "total_travel_time_correction_note",
                unieke_tekst,
            ),
            aantal_stops=("aantal_stops", "first"),
            trip_total_travel_time_min=("trip_total_travel_time_min", "first"),
            trip_from_stop_name=("trip_from_stop_name", "first"),
            trip_to_stop_name=("trip_to_stop_name", "first"),
            trip_aantal_stops=("trip_aantal_stops", "first"),
            shape_id=("shape_id", "first"),
            from_stop_lat=("from_stop_lat", "first"),
            from_stop_lon=("from_stop_lon", "first"),
            from_halte_id=("from_halte_id", "first"),
            from_halte_naam=("from_halte_naam", "first"),
            from_halte_x=("from_halte_x", "first"),
            from_halte_y=("from_halte_y", "first"),
            to_stop_lat=("to_stop_lat", "first"),
            to_stop_lon=("to_stop_lon", "first"),
            to_halte_id=("to_halte_id", "first"),
            to_halte_naam=("to_halte_naam", "first"),
            to_halte_x=("to_halte_x", "first"),
            to_halte_y=("to_halte_y", "first"),
        )
        .reset_index()
    )

    maak_ov_publicatie_output(line_total_summary).to_csv(
        OUTPUT_DIR / "line_total_summary.csv",
        index=False,
    )
    return line_total_travel_times, line_total_summary


def maak_lijn_en_rit_samenvattingen(
    network_edges,
    stop_times_processed,
    trips_processed,
):
    """Maak reistijdtabellen voor lijnverbindingen en volledige GTFS-ritten."""
    line_total_travel_times = maak_lijnverbindingen(network_edges)
    trip_total_times = maak_trip_total_times(network_edges, stop_times_processed)
    trip_total_travel_times = maak_trip_total_travel_times(
        trips_processed,
        trip_total_times,
    )
    trip_total_summary = maak_trip_total_summary(trip_total_travel_times)
    line_total_travel_times, line_total_summary = maak_line_total_summary(
        line_total_travel_times,
        trip_total_times,
    )

    print("Stap 11 klaar: exacte lijnverbindingen met reistijd gemaakt")
    print("Line connection records:", len(line_total_travel_times))
    print("Line total summary records:", len(line_total_summary))
    print("Trip total records:", len(trip_total_travel_times))
    print("Trip total summary records:", len(trip_total_summary))
    return (
        line_total_travel_times,
        line_total_summary,
        trip_total_travel_times,
        trip_total_summary,
    )
