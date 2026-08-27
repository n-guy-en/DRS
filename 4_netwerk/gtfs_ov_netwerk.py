"""
GTFS OV-netwerk bouwen met reistijden.

Doel:
- Vanaf scratch een betrouwbaar OV-netwerk maken uit GTFS.
- Geschikt voor bus, trein en ferry/boot.
- Reistijd komt uit stop_times.txt.
- Richting komt uit trips.txt via direction_id en trip_id.
- Shapes worden gebruikt voor kaartlijnen/tooltips, niet om haltevolgorde te gokken.
- OV_LIJNEN/OV_HALTES GeoJSON zijn optioneel voor validatie/verrijking.

Verwachte GTFS-bestanden in RAW_DIR:
- agency.txt
- routes.txt
- trips.txt
- stops.txt
- stop_times.txt
- calendar_dates.txt
- shapes.txt optioneel

Outputs:
- gtfs_ov_netwerk/line_total_summary.csv
- gtfs_ov_netwerk/trip_total_summary.csv
- gtfs_ov_netwerk/validatie/validatie_*.csv
- gtfs_ov_netwerk/validatie/tussenbestanden/*.csv
- gtfs_ov_netwerk/validatie/kaartcontrole/*.geojson
- 0_layers/processed/4_netwerk/ov/line_total_travel_times.geojson
- 0_layers/processed/4_netwerk/ov/line_total_stop_points.geojson
"""

# %% Stap 1: imports en instellingen
from ov.helpers.instellingen import (
    KAARTCONTROLE_DIR,
    LAGEN_DIR,
    OUTPUT_DIR,
    RAW_DIR,
    TUSSENBESTANDEN_DIR,
    VALIDATIE_DIR,
    VERPLICHTE_GTFS_BESTANDEN,
    maak_output_mappen,
)
from ov.helpers.edges import maak_network_edges
from ov.helpers.invoer import lees_gtfs_invoer
from ov.helpers.invoer import valideer_gtfs_invoer
from ov.helpers.kaartlagen import schrijf_kaartlagen
from ov.helpers.samenvatting import (
    maak_lijn_en_rit_samenvattingen,
    maak_route_segment_summary,
)
from ov.helpers.validatie import (
    controleer_gtfs_kolommen,
    schrijf_network_edges_tijdvalidatie,
    schrijf_stop_times_tijdvalidatie,
)
from ov.helpers.verwerking import (
    verwerk_routes,
    verwerk_stops,
    verwerk_stop_times,
    verwerk_trips,
)


ROUTE_SEGMENT_SUMMARY = None
LINE_TOTAL_TRAVEL_TIMES = None
TRIP_TOTAL_TRAVEL_TIMES = None


def zoek_segment(line_id, van_stop, mode=None):
    """Zoek volgende haltes vanaf een stop binnen een lijn."""
    resultaat = ROUTE_SEGMENT_SUMMARY.copy()

    resultaat = resultaat[
        resultaat["line_id"].astype(str) == str(line_id)
    ].copy()

    if mode is not None:
        resultaat = resultaat[
            resultaat["mode"].astype(str) == str(mode)
        ].copy()

    van_norm = str(van_stop).lower()

    resultaat = resultaat[
        resultaat["from_stop_name"]
        .astype(str)
        .str.lower()
        .str.contains(van_norm, na=False)
    ].copy()

    resultaat = resultaat.sort_values(
        ["travel_time_min", "aantal_trips"],
        ascending=[True, False],
    )

    print("Aantal gevonden segmenten:", len(resultaat))
    print(
        resultaat[
            [
                "mode",
                "line_id",
                "direction_id",
                "trip_headsign",
                "from_stop_name",
                "to_stop_name",
                "travel_time_min",
                "aantal_trips",
            ]
        ].head(30)
    )

    return resultaat


def zoek_reistijd(van_stop, naar_stop, line_id=None, mode=None):
    """Zoek totale reistijd van beginhalte naar eindhalte per lijnrit."""
    resultaat = LINE_TOTAL_TRAVEL_TIMES.copy()

    van_norm = str(van_stop).lower()
    naar_norm = str(naar_stop).lower()

    resultaat = resultaat[
        resultaat["from_stop_name"]
        .astype(str)
        .str.lower()
        .str.contains(van_norm, na=False)
        & resultaat["to_stop_name"]
        .astype(str)
        .str.lower()
        .str.contains(naar_norm, na=False)
    ].copy()

    if line_id is not None:
        resultaat = resultaat[
            resultaat["line_id"].astype(str) == str(line_id)
        ].copy()

    if mode is not None:
        resultaat = resultaat[
            resultaat["mode"].astype(str) == str(mode)
        ].copy()

    resultaat = resultaat.sort_values(
        ["total_travel_time_min", "aantal_stops"],
        ascending=[True, True],
    )

    print("Aantal gevonden routes:", len(resultaat))
    print(
        resultaat[
            [
                "mode",
                "line_id",
                "direction_id",
                "trip_headsign",
                "from_stop_name",
                "to_stop_name",
                "aantal_stops",
                "total_travel_time_min",
            ]
        ].head(30)
    )

    return resultaat


def zoek_totale_rit(van_stop, naar_stop, line_id=None, mode=None):
    """Zoek totale reistijd van volledige GTFS-ritten."""
    resultaat = TRIP_TOTAL_TRAVEL_TIMES.copy()

    van_norm = str(van_stop).lower()
    naar_norm = str(naar_stop).lower()

    resultaat = resultaat[
        resultaat["trip_from_stop_name"]
        .astype(str)
        .str.lower()
        .str.contains(van_norm, na=False)
        & resultaat["trip_to_stop_name"]
        .astype(str)
        .str.lower()
        .str.contains(naar_norm, na=False)
    ].copy()

    if line_id is not None:
        resultaat = resultaat[
            resultaat["line_id"].astype(str) == str(line_id)
        ].copy()

    if mode is not None:
        resultaat = resultaat[
            resultaat["mode"].astype(str) == str(mode)
        ].copy()

    resultaat = resultaat.sort_values(
        ["trip_total_travel_time_min", "trip_aantal_stops"],
        ascending=[True, True],
    )

    print("Aantal gevonden volledige ritten:", len(resultaat))
    print(
        resultaat[
            [
                "mode",
                "line_id",
                "direction_id",
                "trip_headsign",
                "trip_from_stop_name",
                "trip_to_stop_name",
                "trip_aantal_stops",
                "trip_total_travel_time_min",
            ]
        ].head(30)
    )

    return resultaat


def main() -> None:
    maak_output_mappen()
    valideer_gtfs_invoer()

    print("Stap 1 klaar: instellingen gezet")
    print("Raw map:", RAW_DIR)
    print("Output map:", OUTPUT_DIR)
    print("Stap 2 klaar: hulpfuncties beschikbaar")


    # %% Stap 3: GTFS-bestanden inlezen
    gtfs_invoer = lees_gtfs_invoer()
    agency = gtfs_invoer["agency"]
    routes = gtfs_invoer["routes"]
    trips = gtfs_invoer["trips"]
    stops = gtfs_invoer["stops"]
    stop_times = gtfs_invoer["stop_times"]
    shapes = gtfs_invoer["shapes"]
    haltes_frl = gtfs_invoer["haltes_frl"]
    lijnen_frl = gtfs_invoer["lijnen_frl"]
    bestandscontrole = gtfs_invoer["bestandscontrole"]

    print("Stap 3 klaar: GTFS-bestanden ingelezen")
    print(bestandscontrole)


    # %% Stap 4: kolommen controleren
    controleer_gtfs_kolommen(agency, routes, trips, stops, stop_times)

    print("Stap 4 klaar: verplichte kolommen gecontroleerd")


    # %% Stap 5: routes verwerken
    routes_processed = verwerk_routes(routes, agency)


    # %% Stap 6: trips verwerken
    trips_processed = verwerk_trips(trips, routes_processed)


    # %% Stap 7: stops verwerken
    stops_processed = verwerk_stops(stops, haltes_frl)


    # %% Stap 8: stop_times verwerken en tijdvenster valideren
    stop_times_processed, _ = verwerk_stop_times(
        stop_times,
        trips_processed,
        stops_processed,
    )
    schrijf_stop_times_tijdvalidatie(stop_times_processed)


    # %% Stap 9: netwerk-edges maken uit opeenvolgende stop_times
    network_edges = maak_network_edges(stop_times_processed)
    schrijf_network_edges_tijdvalidatie(network_edges)

    print("Stap 9 klaar: network_edges gemaakt")
    print("Network edges per mode:")
    if network_edges.empty:
        print("Geen network_edges gemaakt.")
    else:
        print(network_edges["mode"].value_counts(dropna=False))


    # %% Stap 10: segment-samenvatting maken
    route_segment_summary = maak_route_segment_summary(network_edges)


    # %% Stap 11: reistijd per exacte lijnverbinding
    (
        line_total_travel_times,
        line_total_summary,
        trip_total_travel_times,
        trip_total_summary,
    ) = maak_lijn_en_rit_samenvattingen(
        network_edges,
        stop_times_processed,
        trips_processed,
    )


    # %% Stap 12 t/m 17: kaartlagen maken
    kaartlagen_resultaat = schrijf_kaartlagen(
        line_total_summary,
        trip_total_summary,
        route_segment_summary,
        stops_processed,
        trips_processed,
        shapes,
        lijnen_frl,
    )
    trip_total_route_features = kaartlagen_resultaat["trip_total_route_features"]
    stop_points_geojson = kaartlagen_resultaat["stop_points_geojson"]
    tooltip_features = kaartlagen_resultaat["tooltip_features"]
    friesland_stop_edges = kaartlagen_resultaat["friesland_stop_edges"]


    # %% Stap 18: validatie
    edges_missing_times = network_edges[
        network_edges["travel_time_min"].isna()
    ].copy()

    edges_negative_times = network_edges[
        network_edges["travel_time_min"].notna()
        & (network_edges["travel_time_min"] < 0)
    ].copy()

    edges_zero_times = network_edges[
        network_edges["travel_time_min"].notna()
        & (network_edges["travel_time_min"] == 0)
    ].copy()

    edges_gtfs_zero_times = network_edges[
        network_edges["travel_time_original_min"].notna()
        & (network_edges["travel_time_original_min"] == 0)
    ].copy()

    trips_met_minder_dan_twee_stops = (
        stop_times_processed
        .groupby("trip_id", dropna=False)
        .agg(aantal_stops=("stop_id", "count"))
        .reset_index()
    )

    trips_met_minder_dan_twee_stops = trips_met_minder_dan_twee_stops[
        trips_met_minder_dan_twee_stops["aantal_stops"] < 2
    ]

    missing_coordinates = stops_processed[
        stops_processed["stop_lat"].isna()
        | stops_processed["stop_lon"].isna()
    ].copy()

    stops_zonder_halte = stops_processed[
        stops_processed["stop_lat"].notna()
        & stops_processed["stop_lon"].notna()
        & ~stops_processed["in_friesland"].fillna(False)
    ].copy()

    edges_missing_times.to_csv(
        VALIDATIE_DIR / "validatie_edges_missing_times.csv",
        index=False,
    )

    edges_negative_times.to_csv(
        VALIDATIE_DIR / "validatie_edges_negative_times.csv",
        index=False,
    )

    edges_zero_times.to_csv(
        VALIDATIE_DIR / "validatie_edges_zero_times.csv",
        index=False,
    )

    edges_gtfs_zero_times.to_csv(
        VALIDATIE_DIR / "validatie_edges_gtfs_zero_times.csv",
        index=False,
    )

    trips_met_minder_dan_twee_stops.to_csv(
        VALIDATIE_DIR / "validatie_trips_met_minder_dan_twee_stops.csv",
        index=False,
    )

    missing_coordinates.to_csv(
        VALIDATIE_DIR / "validatie_missing_coordinates.csv",
        index=False,
    )

    stops_zonder_halte.to_csv(
        VALIDATIE_DIR / "validatie_stops_zonder_frl_halte.csv",
        index=False,
    )

    print("Stap 18 klaar: validatiebestanden gemaakt")
    print("Edges missing times:", len(edges_missing_times))
    print("Edges negative times:", len(edges_negative_times))
    print("Edges zero times:", len(edges_zero_times))
    print("Edges met originele GTFS-reistijd 0:", len(edges_gtfs_zero_times))
    print("Trips met minder dan twee stops:", len(trips_met_minder_dan_twee_stops))
    print("Stops met missende coördinaten:", len(missing_coordinates))
    print("GTFS-stops zonder Friese halte:", len(stops_zonder_halte))


    global ROUTE_SEGMENT_SUMMARY, LINE_TOTAL_TRAVEL_TIMES, TRIP_TOTAL_TRAVEL_TIMES
    ROUTE_SEGMENT_SUMMARY = route_segment_summary
    LINE_TOTAL_TRAVEL_TIMES = line_total_travel_times
    TRIP_TOTAL_TRAVEL_TIMES = trip_total_travel_times

    print("Stap 19 klaar: zoekfuncties beschikbaar")

    verwachte_outputs = [
        OUTPUT_DIR / "line_total_summary.csv",
        OUTPUT_DIR / "trip_total_summary.csv",
        TUSSENBESTANDEN_DIR / "routes_processed.csv",
        TUSSENBESTANDEN_DIR / "trips_processed.csv",
        TUSSENBESTANDEN_DIR / "stops_processed.csv",
        TUSSENBESTANDEN_DIR / "stop_times_processed.csv",
        TUSSENBESTANDEN_DIR / "network_edges.csv",
        TUSSENBESTANDEN_DIR / "route_segment_summary.csv",
        TUSSENBESTANDEN_DIR / "line_total_travel_times.csv",
        TUSSENBESTANDEN_DIR / "trip_total_travel_times.csv",
        VALIDATIE_DIR / "validatie_missing_files.csv",
        VALIDATIE_DIR / "validatie_tijden_stop_times.csv",
        VALIDATIE_DIR / "validatie_tijden_network_edges.csv",
        VALIDATIE_DIR / "validatie_edges_gtfs_zero_times.csv",
        VALIDATIE_DIR / "validatie_edges_zero_times.csv",
        LAGEN_DIR / "line_total_stop_points.geojson",
        LAGEN_DIR / "line_total_travel_times.geojson",
        KAARTCONTROLE_DIR / "trip_total_routes.geojson",
        KAARTCONTROLE_DIR / "shapes_routes.geojson",
        KAARTCONTROLE_DIR / "segment_tooltip.geojson",
        KAARTCONTROLE_DIR / "friesland_stop_edges.geojson",
    ]

    ontbrekende_outputs = [
        str(pad)
        for pad in verwachte_outputs
        if not pad.exists()
    ]

    validatieproblemen = (
        len(
            bestandscontrole[
                bestandscontrole["bestand"].isin(VERPLICHTE_GTFS_BESTANDEN)
                & ~bestandscontrole["bestaat"]
            ]
        )
        + len(edges_missing_times)
        + len(edges_negative_times)
        + len(trips_met_minder_dan_twee_stops)
        + len(missing_coordinates)
    )

    validatie_aandachtspunten = len(edges_gtfs_zero_times)

    print("\nEindcontrole:")
    print("Aantal routes:", len(routes_processed))
    print("Aantal trips:", len(trips_processed))
    print("Aantal stops:", len(stops_processed))
    print("Aantal network_edges:", len(network_edges))
    print("Aantal totale lijnritten:", len(line_total_travel_times))
    print("Aantal totale GTFS-ritten:", len(trip_total_travel_times))
    print("Aantal totale GTFS-rit GeoJSON features:", len(trip_total_route_features))
    print("Aantal segmenten in tooltip GeoJSON:", len(tooltip_features))
    print("Aantal halte-edges:", len(friesland_stop_edges))
    print("Aantal haltepunten GeoJSON:", len(stop_points_geojson["features"]))
    print("Aantal validatieproblemen:", validatieproblemen)
    print("Aantal validatie-aandachtspunten:", validatie_aandachtspunten)

    if ontbrekende_outputs:
        print("Ontbrekende outputs:", ontbrekende_outputs)
    else:
        print("Alle verwachte outputs bestaan.")

    print("\nVoorbeelden:")
    print('zoek_segment("3", "Leeuwarden")')
    print('zoek_reistijd("Leeuwarden", "Drachten", line_id="320")')
    print('zoek_totale_rit("Leeuwarden", "Drachten", line_id="320")')

    print("\nScript klaar.")



if __name__ == "__main__":
    main()
