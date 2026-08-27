"""Configuratie en vaste paden voor het GTFS/OV-netwerk."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]

RAW_ROOT_DIR = BASE_DIR / "raw" / "GTFS"
RAW_DIR = RAW_ROOT_DIR / "gtfs-openov-nl"

PROCESSED_DIR = BASE_DIR / "processed" / "GTFS"
OUTPUT_DIR = PROCESSED_DIR / "gtfs_ov_netwerk"
VALIDATIE_DIR = OUTPUT_DIR / "validatie"
TUSSENBESTANDEN_DIR = VALIDATIE_DIR / "tussenbestanden"
KAARTCONTROLE_DIR = VALIDATIE_DIR / "kaartcontrole"
LAGEN_DIR = BASE_DIR.parent / "0_layers" / "processed" / "4_netwerk" / "ov"

AGENCY_FILE = RAW_DIR / "agency.txt"
ROUTES_FILE = RAW_DIR / "routes.txt"
TRIPS_FILE = RAW_DIR / "trips.txt"
STOPS_FILE = RAW_DIR / "stops.txt"
STOP_TIMES_FILE = RAW_DIR / "stop_times.txt"
CALENDAR_DATES_FILE = RAW_DIR / "calendar_dates.txt"
CALENDAR_FILE = RAW_DIR / "calendar.txt"
SHAPES_FILE = RAW_DIR / "shapes.txt"
OV_HALTES_FRL_FILE = RAW_ROOT_DIR / "OV_HALTES_FRL_ACTUEEL.json"
OV_LIJNEN_FRL_FILE = RAW_ROOT_DIR / "OV_LIJNEN_FRL_ACTUEEL.json"

CRS_WGS84 = "EPSG:4326"
CRS_RD = "EPSG:28992"

ROUTE_TYPE_NAAR_MODE = {
    "2": "train",
    "3": "bus",
    "4": "ferry",
}
TOEGESTANE_ROUTE_TYPES = [int(route_type) for route_type in ROUTE_TYPE_NAAR_MODE]
TOEGESTANE_OPERATORS = [
    "Arriva",
    "NS",
    "Qbuzz",
    "Wagenborg Passagiersdiensten",
    "Rederij Doeksen",
]

MAX_AFSTAND_GTFS_TOT_HALTE_M = 250
MAX_AFSTAND_HALTE_TOT_OV_LIJN_M = 250
NEEM_GRENSSEGMENTEN_MEE = True
HANDMATIGE_REISTIJD_CORRECTIES = []
BUS_NUL_REISTIJD_SECONDEN = 30

VERPLICHTE_GTFS_BESTANDEN = [
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stops.txt",
    "stop_times.txt",
    "calendar_dates.txt",
]


def maak_output_mappen() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATIE_DIR.mkdir(parents=True, exist_ok=True)
    TUSSENBESTANDEN_DIR.mkdir(parents=True, exist_ok=True)
    KAARTCONTROLE_DIR.mkdir(parents=True, exist_ok=True)
    LAGEN_DIR.mkdir(parents=True, exist_ok=True)
