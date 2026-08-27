"""Gedeelde configuratie voor bereikbaarheidsanalyses."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
CRS_RD = "EPSG:28992"
CRS_WGS84 = "EPSG:4326"


def lees_bag_analysejaar() -> int:
    """Lees het analysejaar uit de BAG-config."""
    bag_config = runpy.run_path(str(BASE_DIR / "2_bag" / "config.py"))
    return int(bag_config["ANALYSEJAAR"])


JAAR = lees_bag_analysejaar()

OV_DATUM = "20260616"  # YYYYMMDD, dinsdag 16 juni 2026; geldt voor alle voorzieningen

WANDEL_METER_PER_MIN = 80.0
FIETS_METER_PER_MIN = 250.0
AUTO_SNAP_METER_PER_MIN = 50.0 * 1000.0 / 60.0

MODUS_CONFIG = {
    "lopen": {
        "netwerk": "voetganger_osm",
        "snap_meter_per_min": WANDEL_METER_PER_MIN,
    },
    "fiets": {
        "netwerk": "fiets_osm",
        "snap_meter_per_min": FIETS_METER_PER_MIN,
    },
    "auto": {
        "netwerk": "personenauto",
        "snap_meter_per_min": AUTO_SNAP_METER_PER_MIN,
    },
    "ov_lopen": {
        "access_netwerk": "voetganger_osm",
        "snap_meter_per_min": WANDEL_METER_PER_MIN,
    },
    "ov_fiets": {
        "access_netwerk": "fiets_osm",
        "snap_meter_per_min": FIETS_METER_PER_MIN,
    },
}

NORMEN_PER_VOORZIENING = {
    "supermarkt": {
        "auto": 10.0,
        "fiets": 10.0,
        "ov_fiets": 15.0,
        "ov_lopen": 15.0,
        "lopen": 15.0,
    },
    "apotheek": {
        "auto": 10.0,
        "fiets": 10.0,
        "ov_fiets": 20.0,
        "ov_lopen": 20.0,
        "lopen": 15.0,
    },
    "huisarts": {
        "auto": 10.0,
        "fiets": 10.0,
        "ov_fiets": 20.0,
        "ov_lopen": 20.0,
        "lopen": 15.0,
    },
    "ziekenhuis": {
        "auto": 20.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 20.0,
    },
    "recreatief_groen": {
        "auto": 15.0,
        "fiets": 15.0,
        "ov_fiets": 15.0,
        "ov_lopen": 15.0,
        "lopen": 15.0,
    },
    "sport": {
        "auto": 30.0,
        "fiets": 30.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 30.0,
    },
    "ov": {
        "auto": 15.0,
        "fiets": 15.0,
        "ov_fiets": 15.0,
        "ov_lopen": 15.0,
        "lopen": 15.0,
    },
}

FIETS_UITZONDERING_VOORZIENINGEN = ["ov", "recreatief_groen", "sport"]
FIETS_UITZONDERING_NORM_MIN = 10.0

FIETS_UITZONDERING_GEMEENTECODES = {
    "GM1900",  # Súdwest-Fryslân
    "GM0090",  # Smallingerland
    "GM0074",  # Heerenveen
    "GM0080",  # Leeuwarden
}

NORMEN_PER_ONDERWIJSNIVEAU = {
    "basisonderwijs": {
        "auto": 10.0,
        "fiets": 10.0,
        "ov_fiets": 10.0,
        "ov_lopen": 10.0,
        "lopen": 10.0,
    },
    "vo": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "vmbo": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "mavo": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "havo": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "vwo": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "pro": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "brugjaar": {
        "auto": 15.0,
        "fiets": 25.0,
        "ov_fiets": 30.0,
        "ov_lopen": 30.0,
        "lopen": 25.0,
    },
    "mbo": {
        "auto": 25.0,
        "fiets": 25.0,
        "ov_fiets": 40.0,
        "ov_lopen": 40.0,
        "lopen": 25.0,
    },
    "hbo": {
        "auto": 35.0,
        "fiets": 25.0,
        "ov_fiets": 45.0,
        "ov_lopen": 45.0,
        "lopen": 15.0,
    },
    "wo": {
        "auto": 35.0,
        "fiets": 25.0,
        "ov_fiets": 45.0,
        "ov_lopen": 45.0,
        "lopen": 15.0,
    },
}

MODUS_CODES = {
    "lopen": "lop",
    "fiets": "fie",
    "auto": "aut",
    "ov_lopen": "ovl",
    "ov_fiets": "ovf",
}

KLEUREN = [
    (0, 20, "0-20%", "#d73027"),
    (20, 40, "20-40%", "#fc8d59"),
    (40, 60, "40-60%", "#fee08b"),
    (60, 80, "60-80%", "#d9ef8b"),
    (80, 100.000001, "80-100%", "#1a9850"),
]

ONDERWIJS_NIVEAU_NAMEN = {
    "basisonderwijs": "Basisonderwijs",
    "vo": "Voortgezet onderwijs",
    "vmbo": "VMBO",
    "mavo": "MAVO",
    "havo": "HAVO",
    "vwo": "VWO",
    "pro": "Praktijkonderwijs",
    "brugjaar": "Brugjaar",
    "mbo": "MBO",
    "hbo": "HBO",
    "wo": "WO",
}


@dataclass(frozen=True)
class VoorzieningConfig:
    naam: str
    label: str
    pluralis: str
    layer: str
    input_pad: Path | None = None
    onderwijsniveau: str | None = None

    @property
    def virtual_doel(self) -> str:
        return f"__{self.naam}_doel__"


@dataclass(frozen=True)
class RuntimeConfig:
    jaar: int = JAAR
    pand_selectie: str = "woonpanden"
    modi: str = "all"
    max_snap_meter: float = 250.0
    gebruik_pandpolygonen: bool = True
    max_parkeer_loop_min: float = 10.0
    max_ov_transfer_meter: float = 250.0
    ov_datum: str = OV_DATUM
    ov_starttijd: str = "00:00:00"
    ov_eindtijd: str = "23:59:59"
    ov_stap_minuten: int = 15
    min_overstap_min: float = 3.0


DEFAULT_RUNTIME_CONFIG = RuntimeConfig()


PRESETS = {
    "supermarkt": VoorzieningConfig(
        naam="supermarkt",
        label="supermarkt",
        pluralis="supermarkten",
        layer="supermarkten_groot",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "supermarkt"
            / "supermarkten_groot.gpkg"
        ),
    ),
    "ziekenhuis": VoorzieningConfig(
        naam="ziekenhuis",
        label="ziekenhuis",
        pluralis="ziekenhuizen",
        layer="ziekenhuizen",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "ziekenhuis"
            / "ziekenhuizen.gpkg"
        ),
    ),
    "apotheek": VoorzieningConfig(
        naam="apotheek",
        label="apotheek",
        pluralis="apotheken",
        layer="apotheek_groot",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "apotheek"
            / "apotheek_groot.gpkg"
        ),
    ),
    "huisarts": VoorzieningConfig(
        naam="huisarts",
        label="huisarts",
        pluralis="huisartsen",
        layer="huisarts_groot",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "huisarts"
            / "huisarts_groot.gpkg"
        ),
    ),
    "recreatief_groen": VoorzieningConfig(
        naam="recreatief_groen",
        label="recreatief groen",
        pluralis="recreatieve groengebieden",
        layer="recreatief_groen_groot",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "recreatief_groen"
            / "recreatief_groen_groot.gpkg"
        ),
    ),
    "sport": VoorzieningConfig(
        naam="sport",
        label="sportvoorziening",
        pluralis="sportvoorzieningen",
        layer="sport_groot",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "sport"
            / "sport_groot.gpkg"
        ),
    ),
    "ov": VoorzieningConfig(
        naam="ov",
        label="OV-halte",
        pluralis="OV-haltes",
        layer="ov_haltes",
        input_pad=(
            BASE_DIR
            / "0_layers"
            / "processed"
            / "3_voorzieningen"
            / "ov"
            / "ov_haltes.gpkg"
        ),
    ),
    "onderwijs": VoorzieningConfig(
        naam="onderwijs",
        label="onderwijs",
        pluralis="onderwijsvoorzieningen",
        layer="onderwijs",
        input_pad=None,
    ),
}

_CURRENT = PRESETS["supermarkt"]

VIRTUAL_DOEL = _CURRENT.virtual_doel
VOORZIENING = _CURRENT.naam


def configure(voorziening: str, onderwijsniveau: str | None = None) -> VoorzieningConfig:
    """Stel de actieve voorziening in voor de gedeelde helpers."""

    if voorziening not in PRESETS:
        raise ValueError(f"Onbekende voorziening: {voorziening}")

    global _CURRENT, VIRTUAL_DOEL, VOORZIENING
    basis = PRESETS[voorziening]

    if voorziening == "onderwijs" and onderwijsniveau is not None:
        if onderwijsniveau not in ONDERWIJS_NIVEAU_NAMEN:
            raise ValueError(
                "Onbekend onderwijsniveau: "
                f"{onderwijsniveau}. Kies uit: {', '.join(ONDERWIJS_NIVEAU_NAMEN)}"
            )
        basis = VoorzieningConfig(
            naam=basis.naam,
            label=basis.label,
            pluralis=basis.pluralis,
            layer=f"onderwijs_{onderwijsniveau}",
            input_pad=(
                BASE_DIR
                / "0_layers"
                / "processed"
                / "3_voorzieningen"
                / "onderwijs"
                / onderwijsniveau
                / f"onderwijs_{onderwijsniveau}.gpkg"
            ),
            onderwijsniveau=onderwijsniveau,
        )

    _CURRENT = basis
    VIRTUAL_DOEL = basis.virtual_doel
    VOORZIENING = basis.naam
    pas_normen_toe(basis)
    return _CURRENT


def pas_normen_toe(config: VoorzieningConfig) -> None:
    if config.naam == "onderwijs":
        if config.onderwijsniveau is None:
            return
        normen = NORMEN_PER_ONDERWIJSNIVEAU[config.onderwijsniveau]
    else:
        normen = NORMEN_PER_VOORZIENING[config.naam]

    for modus, norm_min in normen.items():
        if modus not in MODUS_CONFIG:
            raise ValueError(f"Norm opgegeven voor onbekende modaliteit: {modus}")
        MODUS_CONFIG[modus]["norm_min"] = float(norm_min)


pas_normen_toe(_CURRENT)


def fiets_uitzondering_mask(panden: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=panden.index)
    if "gemeentecode" in panden.columns:
        gemeentecode = panden["gemeentecode"].astype(str).str.strip().str.upper()
        mask |= gemeentecode.isin(FIETS_UITZONDERING_GEMEENTECODES)
    return mask


def norm_min_voor_panden(
    modus: str,
    panden: pd.DataFrame,
    standaard_norm_min: float | None = None,
) -> pd.Series:
    norm_min = (
        float(standaard_norm_min)
        if standaard_norm_min is not None
        else float(MODUS_CONFIG[modus]["norm_min"])
    )
    normen = pd.Series(norm_min, index=panden.index, dtype="float64")
    if voorziening() in FIETS_UITZONDERING_VOORZIENINGEN and modus == "fiets":
        normen.loc[fiets_uitzondering_mask(panden)] = FIETS_UITZONDERING_NORM_MIN
    return normen


def current_config() -> VoorzieningConfig:
    return _CURRENT


def voorziening() -> str:
    return _CURRENT.naam


def voorziening_label() -> str:
    return _CURRENT.label


def voorzieningen_label() -> str:
    return _CURRENT.pluralis


def tijd_kolom(modus: str) -> str:
    return f"reistijd_{voorziening()}_{modus}_min"


def netwerk_tijd_kolom(modus: str) -> str:
    return f"netwerkreistijd_{voorziening()}_{modus}_min"


def bereikbaar_kolom(modus: str) -> str:
    return f"{voorziening()}_{modus}_bereikbaar"


def binnen_kolom(modus: str) -> str:
    return f"binnen_norm_{voorziening()}_{modus}"


def norm_kolom(modus: str) -> str:
    return f"norm_{voorziening()}_{modus}_min"


def reistijd_bron_kolom(modus: str) -> str:
    return f"reistijd_{voorziening()}_{modus}_bron"


def reistijd_profiel_kolom(modus: str, suffix: str) -> str:
    return f"reistijd_{voorziening()}_{modus}_{suffix}_min"


def voorziening_resultaat_kolom(naam: str) -> str:
    return f"{voorziening()}_{naam}"


def voorziening_id_kolom() -> str:
    return f"{voorziening()}_id"


def voorziening_lon_kolom() -> str:
    return f"{voorziening()}_lon"


def voorziening_lat_kolom() -> str:
    return f"{voorziening()}_lat"


def parkeer_loop_kolom() -> str:
    return f"loop_vanaf_parkeren_{voorziening()}_min"


def parkeer_idx_kolom() -> str:
    return f"parkeer_{voorziening()}_idx"


def parkeer_luchtlijn_idx_kolom() -> str:
    return f"parkeer_{voorziening()}_luchtlijn_idx"


def parkeer_luchtlijn_meter_kolom() -> str:
    return f"parkeer_{voorziening()}_luchtlijn_meter"


def parkeer_loop_bron_kolom() -> str:
    return f"loop_vanaf_parkeren_{voorziening()}_bron"


def output_basis_dir() -> Path:
    pad = BASE_DIR / "0_layers" / "processed" / "5_bereikbaarheid" / voorziening()
    if _CURRENT.onderwijsniveau:
        pad = pad / _CURRENT.onderwijsniveau
    return pad


def tabel_output_basis_dir() -> Path:
    pad = BASE_DIR / "5_bereikbaarheid" / "processed" / voorziening()
    if _CURRENT.onderwijsniveau:
        pad = pad / _CURRENT.onderwijsniveau
    return pad


def voorbeeldroute_pad(modus: str) -> Path:
    naam = voorziening()
    if _CURRENT.onderwijsniveau:
        naam = f"{naam}_{_CURRENT.onderwijsniveau}"
    return (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "voorbeelden"
        / f"voorbeeldroute_{naam}_{MODUS_CODES[modus]}.gpkg"
    )


def verkeersnetwerk_pad(naam: str) -> Path:
    return (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "4_netwerk"
        / "verkeerstypen"
        / f"{naam}.json"
    )


def ov_lagen_dir() -> Path:
    return BASE_DIR / "0_layers" / "processed" / "4_netwerk" / "ov"


def ov_data_dir() -> Path:
    return BASE_DIR / "4_netwerk" / "processed" / "GTFS" / "gtfs_ov_netwerk"
