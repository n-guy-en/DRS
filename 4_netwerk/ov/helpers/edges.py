"""Maak OV-netwerkedges uit opeenvolgende GTFS-stop_times."""

import pandas as pd

from .instellingen import (
    BUS_NUL_REISTIJD_SECONDEN,
    HANDMATIGE_REISTIJD_CORRECTIES,
    NEEM_GRENSSEGMENTEN_MEE,
    TUSSENBESTANDEN_DIR,
)
from .geometrie import haversine_meter
from .tekst import tekst_normaal


def maak_network_edges(stop_times_processed):
    """Maak directe halte-naar-halte edges met GTFS-reistijden."""
    edge_basis = stop_times_processed.sort_values(
        ["trip_id", "stop_sequence"]
    ).copy()

    volgende_kolommen = [
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "stop_sequence",
        "arrival_time",
        "arrival_seconds",
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

    for kolom in volgende_kolommen:
        edge_basis["next_" + kolom] = edge_basis.groupby("trip_id")[kolom].shift(-1)

    network_edges = edge_basis[
        edge_basis["next_stop_id"].notna()
    ].copy()

    if NEEM_GRENSSEGMENTEN_MEE:
        network_edges = network_edges[
            network_edges["in_friesland"].fillna(False)
            | network_edges["next_in_friesland"].fillna(False)
        ].copy()
    else:
        network_edges = network_edges[
            network_edges["in_friesland"].fillna(False)
            & network_edges["next_in_friesland"].fillna(False)
        ].copy()

    network_edges["travel_time_min"] = (
        (
            network_edges["next_arrival_seconds"]
            - network_edges["departure_seconds"]
        )
        / 60
    ).round(2)

    network_edges.loc[
        network_edges["next_arrival_seconds"].isna()
        | network_edges["departure_seconds"].isna(),
        "travel_time_min",
    ] = pd.NA

    network_edges["travel_time_original_min"] = network_edges["travel_time_min"]
    network_edges["travel_time_source"] = "gtfs_stop_times"
    network_edges["travel_time_correction_note"] = ""

    _pas_handmatige_reistijdcorrecties_toe(network_edges)
    _corrigeer_bus_nul_reistijden(network_edges)
    _voeg_reistijdcontrole_toe(network_edges)
    _voeg_afstand_en_id_toe(network_edges)

    network_edges = _selecteer_en_hernoem_edge_kolommen(network_edges)

    network_edges.to_csv(
        TUSSENBESTANDEN_DIR / "network_edges.csv",
        index=False,
    )
    return network_edges


def _pas_handmatige_reistijdcorrecties_toe(network_edges):
    for correctie in HANDMATIGE_REISTIJD_CORRECTIES:
        halte_a_norm = tekst_normaal(correctie["halte_a"])
        halte_b_norm = tekst_normaal(correctie["halte_b"])

        from_norm = network_edges["stop_name"].apply(tekst_normaal)
        to_norm = network_edges["next_stop_name"].apply(tekst_normaal)

        correctie_mask = (
            network_edges["operator"].astype(str).eq(correctie["operator"])
            & network_edges["line_id"].astype(str).isin(correctie["line_ids"])
            & (
                (
                    from_norm.str.contains(halte_a_norm, na=False)
                    & to_norm.str.contains(halte_b_norm, na=False)
                )
                | (
                    from_norm.str.contains(halte_b_norm, na=False)
                    & to_norm.str.contains(halte_a_norm, na=False)
                )
            )
        )

        network_edges.loc[
            correctie_mask,
            "travel_time_min",
        ] = correctie["travel_time_min"]
        network_edges.loc[
            correctie_mask,
            "travel_time_source",
        ] = "manual_correction"
        network_edges.loc[
            correctie_mask,
            "travel_time_correction_note",
        ] = correctie["reden"]


def _corrigeer_bus_nul_reistijden(network_edges):
    bus_nul_reistijd_mask = (
        network_edges["mode"].astype(str).eq("bus")
        & network_edges["travel_time_min"].notna()
        & network_edges["travel_time_min"].eq(0)
    )

    network_edges.loc[
        bus_nul_reistijd_mask,
        "travel_time_min",
    ] = BUS_NUL_REISTIJD_SECONDEN / 60
    network_edges.loc[
        bus_nul_reistijd_mask,
        "travel_time_source",
    ] = "minimum_reistijd_bus"
    network_edges.loc[
        bus_nul_reistijd_mask,
        "travel_time_correction_note",
    ] = (
        "GTFS heeft vertrek en aankomst in dezelfde minuut; "
        f"vervangen door {BUS_NUL_REISTIJD_SECONDEN} seconden."
    )


def _voeg_reistijdcontrole_toe(network_edges):
    network_edges["travel_time_correction_delta_min"] = (
        network_edges["travel_time_min"]
        - network_edges["travel_time_original_min"]
    )

    network_edges["travel_time_original_sec"] = (
        network_edges["travel_time_original_min"] * 60
    ).round().astype("Int64")
    network_edges["travel_time_sec"] = (
        network_edges["travel_time_min"] * 60
    ).round().astype("Int64")
    network_edges["travel_time_correction_delta_sec"] = (
        network_edges["travel_time_sec"]
        - network_edges["travel_time_original_sec"]
    ).astype("Int64")


def _voeg_afstand_en_id_toe(network_edges):
    network_edges["straight_distance_m"] = network_edges.apply(
        lambda rij: haversine_meter(
            rij["stop_lat"],
            rij["stop_lon"],
            rij["next_stop_lat"],
            rij["next_stop_lon"],
        ),
        axis=1,
    )
    network_edges["straight_distance_m"] = network_edges[
        "straight_distance_m"
    ].round(1)

    network_edges["edge_id"] = (
        network_edges["mode"].astype(str)
        + "_"
        + network_edges["line_id"].astype(str)
        + "_"
        + network_edges["trip_id"].astype(str)
        + "_"
        + network_edges["stop_sequence"].astype("Int64").astype(str)
    )


def _selecteer_en_hernoem_edge_kolommen(network_edges):
    network_edges = network_edges.drop(
        columns=["arrival_time", "arrival_seconds"],
    )

    network_edges = network_edges.rename(
        columns={
            "stop_id": "from_stop_id",
            "stop_name": "from_stop_name",
            "stop_lat": "from_stop_lat",
            "stop_lon": "from_stop_lon",
            "stop_sequence": "from_stop_sequence",
            "in_friesland": "from_in_friesland",
            "halte_id": "from_halte_id",
            "halte_naam": "from_halte_naam",
            "halte_type": "from_halte_type",
            "halte_lijnen": "from_halte_lijnen",
            "halte_vervoerders": "from_halte_vervoerders",
            "halte_gemeente": "from_halte_gemeente",
            "halte_provincie": "from_halte_provincie",
            "halte_afstand_m": "from_halte_afstand_m",
            "halte_x": "from_halte_x",
            "halte_y": "from_halte_y",
            "next_stop_id": "to_stop_id",
            "next_stop_name": "to_stop_name",
            "next_stop_lat": "to_stop_lat",
            "next_stop_lon": "to_stop_lon",
            "next_stop_sequence": "to_stop_sequence",
            "next_in_friesland": "to_in_friesland",
            "next_halte_id": "to_halte_id",
            "next_halte_naam": "to_halte_naam",
            "next_halte_type": "to_halte_type",
            "next_halte_lijnen": "to_halte_lijnen",
            "next_halte_vervoerders": "to_halte_vervoerders",
            "next_halte_gemeente": "to_halte_gemeente",
            "next_halte_provincie": "to_halte_provincie",
            "next_halte_afstand_m": "to_halte_afstand_m",
            "next_halte_x": "to_halte_x",
            "next_halte_y": "to_halte_y",
            "next_arrival_time": "arrival_time",
            "next_arrival_seconds": "arrival_seconds",
        }
    )

    return network_edges[
        [
            "edge_id",
            "mode",
            "operator",
            "route_id",
            "line_id",
            "route_long_name",
            "trip_id",
            "service_id",
            "direction_id",
            "trip_headsign",
            "shape_id",
            "from_stop_id",
            "from_stop_name",
            "from_stop_lat",
            "from_stop_lon",
            "from_in_friesland",
            "from_halte_id",
            "from_halte_naam",
            "from_halte_type",
            "from_halte_gemeente",
            "from_halte_provincie",
            "from_halte_afstand_m",
            "from_halte_x",
            "from_halte_y",
            "to_stop_id",
            "to_stop_name",
            "to_stop_lat",
            "to_stop_lon",
            "to_in_friesland",
            "to_halte_id",
            "to_halte_naam",
            "to_halte_type",
            "to_halte_gemeente",
            "to_halte_provincie",
            "to_halte_afstand_m",
            "to_halte_x",
            "to_halte_y",
            "from_stop_sequence",
            "to_stop_sequence",
            "departure_time",
            "arrival_time",
            "departure_seconds",
            "arrival_seconds",
            "travel_time_original_min",
            "travel_time_original_sec",
            "travel_time_min",
            "travel_time_sec",
            "travel_time_correction_delta_min",
            "travel_time_correction_delta_sec",
            "travel_time_source",
            "travel_time_correction_note",
            "straight_distance_m",
        ]
    ].copy()
