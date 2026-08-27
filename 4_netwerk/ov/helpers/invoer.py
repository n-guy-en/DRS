"""Invoer voor de GTFS/OV-netwerkworkflow."""

import geopandas as gpd
import pandas as pd

from .instellingen import (
    AGENCY_FILE,
    CALENDAR_DATES_FILE,
    CALENDAR_FILE,
    CRS_RD,
    OV_HALTES_FRL_FILE,
    OV_LIJNEN_FRL_FILE,
    ROUTES_FILE,
    SHAPES_FILE,
    STOPS_FILE,
    STOP_TIMES_FILE,
    TRIPS_FILE,
    VALIDATIE_DIR,
    VERPLICHTE_GTFS_BESTANDEN,
)
from .haltes import lees_friese_haltes
from .tekst import lijn_id_normaal, tekst_normaal, vervoermiddel_naar_mode


AGENCY_KOLOMMEN = [
    "agency_id",
    "agency_name",
]

ROUTES_KOLOMMEN = [
    "agency_id",
    "route_id",
    "route_short_name",
    "route_long_name",
    "route_type",
]

TRIPS_KOLOMMEN = [
    "route_id",
    "service_id",
    "trip_id",
    "trip_headsign",
    "direction_id",
    "shape_id",
]

STOPS_KOLOMMEN = [
    "stop_id",
    "stop_name",
    "stop_lat",
    "stop_lon",
    "platform_code",
]

STOP_TIMES_KOLOMMEN = [
    "trip_id",
    "arrival_time",
    "departure_time",
    "stop_id",
    "stop_sequence",
]

CALENDAR_DATES_KOLOMMEN = [
    "service_id",
    "date",
    "exception_type",
]

CALENDAR_KOLOMMEN = [
    "service_id",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "start_date",
    "end_date",
]

SHAPES_KOLOMMEN = [
    "shape_id",
    "shape_pt_lat",
    "shape_pt_lon",
    "shape_pt_sequence",
]


def lees_csv_bestand(pad, verplicht=True, kolommen=None):
    """Lees een GTFS txt/csv-bestand."""
    if not pad.exists():
        print("Niet gevonden:", pad.name)

        if verplicht:
            return None

        return pd.DataFrame()

    usecols = None
    if kolommen is not None:
        header = pd.read_csv(pad, nrows=0).columns.tolist()
        usecols = [kolom for kolom in kolommen if kolom in header]

    dataframe = pd.read_csv(
        pad,
        dtype="object",
        usecols=usecols,
        low_memory=False,
    )

    print("Ingelezen:", pad.name, dataframe.shape)
    return dataframe


def lees_lijnen_friesland():
    if OV_LIJNEN_FRL_FILE.exists():
        lijnen_frl = gpd.read_file(OV_LIJNEN_FRL_FILE)
        lijnen_bounds = lijnen_frl.total_bounds
        if (
            lijnen_frl.crs is None
            or lijnen_bounds[0] > 1000
            or lijnen_bounds[1] > 1000
        ):
            lijnen_frl = lijnen_frl.set_crs(
                CRS_RD,
                allow_override=True,
            )
        else:
            lijnen_frl = lijnen_frl.to_crs(CRS_RD)

        lijnen_frl["mode"] = lijnen_frl[
            "Vervoermiddel"
        ].apply(vervoermiddel_naar_mode)
        lijnen_frl["line_id_norm"] = lijnen_frl[
            "Lijnnummer"
        ].apply(lijn_id_normaal)
        lijnen_frl["vervoerder_norm"] = lijnen_frl[
            "Vervoerder"
        ].apply(tekst_normaal)
        lijnen_frl["routenaam_norm"] = lijnen_frl[
            "Routenaam"
        ].apply(tekst_normaal)
        print("Ingelezen: OV_LIJNEN_FRL_ACTUEEL.json", lijnen_frl.shape)
        return lijnen_frl

    print("Niet gevonden: OV_LIJNEN_FRL_ACTUEEL.json")
    return gpd.GeoDataFrame(geometry=[], crs=CRS_RD)


def maak_bestandscontrole():
    return pd.DataFrame(
        [
            {"bestand": "agency.txt", "bestaat": AGENCY_FILE.exists()},
            {"bestand": "routes.txt", "bestaat": ROUTES_FILE.exists()},
            {"bestand": "trips.txt", "bestaat": TRIPS_FILE.exists()},
            {"bestand": "stops.txt", "bestaat": STOPS_FILE.exists()},
            {"bestand": "stop_times.txt", "bestaat": STOP_TIMES_FILE.exists()},
            {"bestand": "calendar_dates.txt", "bestaat": CALENDAR_DATES_FILE.exists()},
            {"bestand": "calendar.txt", "bestaat": CALENDAR_FILE.exists()},
            {"bestand": "shapes.txt", "bestaat": SHAPES_FILE.exists()},
            {
                "bestand": "OV_HALTES_FRL_ACTUEEL.json",
                "bestaat": OV_HALTES_FRL_FILE.exists(),
            },
            {
                "bestand": "OV_LIJNEN_FRL_ACTUEEL.json",
                "bestaat": OV_LIJNEN_FRL_FILE.exists(),
            },
        ]
    )


def valideer_gtfs_invoer() -> None:
    if not (STOP_TIMES_FILE.exists()):
        raise FileNotFoundError(
            "GTFS-map ontbreekt of bevat geen stop_times.txt: "
            f"{STOP_TIMES_FILE.parent}. Gebruik exact deze mapnaam "
            "voor reproduceerbaarheid."
        )


def controleer_gtfs_bestanden(bestandscontrole, stop_times):
    bestandscontrole.to_csv(
        VALIDATIE_DIR / "validatie_missing_files.csv",
        index=False,
    )

    if stop_times is None:
        raise FileNotFoundError(
            "stop_times.txt ontbreekt. Dit bestand is verplicht voor "
            "haltevolgorde en reistijden."
        )

    verplichte_bestanden = bestandscontrole[
        bestandscontrole["bestand"].isin(VERPLICHTE_GTFS_BESTANDEN)
        & (~bestandscontrole["bestaat"])
    ]

    if not verplichte_bestanden.empty:
        raise FileNotFoundError(
            "Verplichte GTFS-bestanden ontbreken: "
            + ", ".join(verplichte_bestanden["bestand"].tolist())
        )


def lees_gtfs_invoer():
    agency = lees_csv_bestand(AGENCY_FILE, kolommen=AGENCY_KOLOMMEN)
    routes = lees_csv_bestand(ROUTES_FILE, kolommen=ROUTES_KOLOMMEN)
    trips = lees_csv_bestand(TRIPS_FILE, kolommen=TRIPS_KOLOMMEN)
    stops = lees_csv_bestand(STOPS_FILE, kolommen=STOPS_KOLOMMEN)
    stop_times = lees_csv_bestand(STOP_TIMES_FILE, kolommen=STOP_TIMES_KOLOMMEN)
    lees_csv_bestand(
        CALENDAR_DATES_FILE,
        verplicht=False,
        kolommen=CALENDAR_DATES_KOLOMMEN,
    )
    lees_csv_bestand(
        CALENDAR_FILE,
        verplicht=False,
        kolommen=CALENDAR_KOLOMMEN,
    )
    shapes = lees_csv_bestand(
        SHAPES_FILE,
        verplicht=False,
        kolommen=SHAPES_KOLOMMEN,
    )
    haltes_frl = lees_friese_haltes(OV_HALTES_FRL_FILE)
    lijnen_frl = lees_lijnen_friesland()
    bestandscontrole = maak_bestandscontrole()

    controleer_gtfs_bestanden(bestandscontrole, stop_times)

    return {
        "agency": agency,
        "routes": routes,
        "trips": trips,
        "stops": stops,
        "stop_times": stop_times,
        "shapes": shapes,
        "haltes_frl": haltes_frl,
        "lijnen_frl": lijnen_frl,
        "bestandscontrole": bestandscontrole,
    }
