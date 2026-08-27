"""Gedeelde instellingen voor interpretatielagen.

De bereikbaarheidsconfiguratie in `5_bereikbaarheid.helpers.instellingen` is de bron
voor voorzieningen, paden, modaliteitcodes en normen. Deze module voegt alleen
instellingen voor afgeleide interpretatielagen toe.
"""

from __future__ import annotations

import importlib
import os
import sys
import ast
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

bereikbaarheid_config = importlib.import_module("5_bereikbaarheid.helpers.instellingen")

VOORZIENING = os.environ.get(
    "INTERPRETATIE_VOORZIENING",
    os.environ.get("DUS_VOORZIENING", "supermarkt"),
)
TOEGESTANE_VOORZIENINGEN = set(bereikbaarheid_config.PRESETS)

if VOORZIENING not in TOEGESTANE_VOORZIENINGEN:
    raise ValueError(
        f"Onbekende interpretatievoorziening: {VOORZIENING}. "
        f"Kies uit: {', '.join(sorted(TOEGESTANE_VOORZIENINGEN))}"
    )

ONDERWIJS_NIVEAU_NAMEN = bereikbaarheid_config.ONDERWIJS_NIVEAU_NAMEN
ONDERWIJS_NIVEAU = os.environ.get(
    "INTERPRETATIE_ONDERWIJS_NIVEAU",
    os.environ.get("DUS_ONDERWIJS_NIVEAU", "basisonderwijs"),
)
if ONDERWIJS_NIVEAU not in ONDERWIJS_NIVEAU_NAMEN:
    raise ValueError(
        "Onbekend onderwijsniveau: "
        f"{ONDERWIJS_NIVEAU}. Kies uit: {', '.join(ONDERWIJS_NIVEAU_NAMEN)}"
    )

if VOORZIENING == "onderwijs":
    ACTIEVE_CONFIG = bereikbaarheid_config.configure("onderwijs", ONDERWIJS_NIVEAU)
    NORMEN = bereikbaarheid_config.NORMEN_PER_ONDERWIJSNIVEAU[ONDERWIJS_NIVEAU]
else:
    ACTIEVE_CONFIG = bereikbaarheid_config.configure(VOORZIENING)
    NORMEN = bereikbaarheid_config.NORMEN_PER_VOORZIENING[VOORZIENING]

CRS_RD = bereikbaarheid_config.CRS_RD
CRS_WGS84 = bereikbaarheid_config.CRS_WGS84
OV_DATUM = bereikbaarheid_config.OV_DATUM
OV_STARTTIJD = bereikbaarheid_config.DEFAULT_RUNTIME_CONFIG.ov_starttijd
OV_EINDTIJD = bereikbaarheid_config.DEFAULT_RUNTIME_CONFIG.ov_eindtijd
OV_STAP_MINUTEN = bereikbaarheid_config.DEFAULT_RUNTIME_CONFIG.ov_stap_minuten
MIN_OVERSTAP_MIN = bereikbaarheid_config.DEFAULT_RUNTIME_CONFIG.min_overstap_min
MAX_OV_TRANSFER_METER = bereikbaarheid_config.DEFAULT_RUNTIME_CONFIG.max_ov_transfer_meter
SIGNAALGRENS_PERCENTAGE = 80.0
ERNSTIGE_GRENS_PERCENTAGE = 60.0


def laad_bereikbaarheid_runtime_config() -> dict[str, object]:
    """Lees vaste RUN-waarden uit 5_bereikbaarheid/config.py zonder importconflict."""

    config_pad = BASE_DIR / "5_bereikbaarheid" / "config.py"
    if not config_pad.exists():
        return {}

    module = ast.parse(config_pad.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "RUN" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        waarden = {}
        for keyword in node.value.keywords:
            if keyword.arg is None:
                continue
            try:
                waarden[keyword.arg] = ast.literal_eval(keyword.value)
            except ValueError:
                continue
        return waarden
    return {}


_BEREIKBAARHEID_RUN = laad_bereikbaarheid_runtime_config()
OV_STARTTIJD = str(_BEREIKBAARHEID_RUN.get("ov_starttijd", OV_STARTTIJD))
OV_EINDTIJD = str(_BEREIKBAARHEID_RUN.get("ov_eindtijd", OV_EINDTIJD))
OV_STAP_MINUTEN = int(_BEREIKBAARHEID_RUN.get("ov_stap_minuten", OV_STAP_MINUTEN))
MIN_OVERSTAP_MIN = float(_BEREIKBAARHEID_RUN.get("min_overstap_min", MIN_OVERSTAP_MIN))
MAX_OV_TRANSFER_METER = float(
    _BEREIKBAARHEID_RUN.get("max_ov_transfer_meter", MAX_OV_TRANSFER_METER)
)

BUURTEN_PAD = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "1_buurten"
    / "buurten_basis.gpkg"
)

VOORZIENINGEN_PAD = ACTIEVE_CONFIG.input_pad
if VOORZIENINGEN_PAD is None:
    raise ValueError(f"Geen voorzieningenpad bekend voor {VOORZIENING}.")

if VOORZIENING == "onderwijs":
    BEREIKBAARHEID_DIR = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "5_bereikbaarheid"
        / "onderwijs"
        / ONDERWIJS_NIVEAU
    )
    BUURT_CSV_DIR = (
        BASE_DIR
        / "5_bereikbaarheid"
        / "processed"
        / "onderwijs"
        / ONDERWIJS_NIVEAU
    )
else:
    BEREIKBAARHEID_DIR = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "5_bereikbaarheid"
        / VOORZIENING
    )
    BUURT_CSV_DIR = BASE_DIR / "5_bereikbaarheid" / "processed" / VOORZIENING

OUTPUT_SUBDIR = (
    Path("onderwijs") / ONDERWIJS_NIVEAU
    if VOORZIENING == "onderwijs"
    else Path(VOORZIENING)
)
OUTPUT_DIR = BASE_DIR / "6_interpretatie" / "processed" / OUTPUT_SUBDIR
LAYERS_DIR = BASE_DIR / "0_layers" / "processed" / "6_interpretatie" / OUTPUT_SUBDIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LAYERS_DIR.mkdir(parents=True, exist_ok=True)

MODI = {
    modus: {
        "code": bereikbaarheid_config.MODUS_CODES[modus],
        "map": modus,
        "norm_min": float(NORMEN[modus]),
    }
    for modus in ["lopen", "fiets", "auto", "ov_lopen", "ov_fiets"]
}

def norm_min_voor_panden(
    modus: str,
    panden: pd.DataFrame,
    standaard_norm_min: float | None = None,
) -> pd.Series:
    return bereikbaarheid_config.norm_min_voor_panden(
        modus,
        panden,
        standaard_norm_min,
    )


def voorziening() -> str:
    return VOORZIENING


def voorziening_label() -> str:
    return ACTIEVE_CONFIG.label


def output_voorzieningnaam() -> str:
    if VOORZIENING == "onderwijs":
        return ONDERWIJS_NIVEAU
    return VOORZIENING


def parse_modi(waarde: str | None = None) -> list[str]:
    """Lees een optionele modaliteitselectie voor incrementele runs."""

    if waarde is None:
        waarde = os.environ.get(
            "INTERPRETATIE_MODI",
            os.environ.get("DUS_MODI", "all"),
        )
    if waarde == "all":
        return list(MODI)
    modi = [deel.strip() for deel in waarde.split(",") if deel.strip()]
    onbekend = sorted(set(modi) - set(MODI))
    if onbekend:
        raise ValueError(
            "Onbekende interpretatiemodaliteiten: "
            + ", ".join(onbekend)
            + ". Kies uit: "
            + ", ".join(MODI)
        )
    return [modus for modus in MODI if modus in set(modi)]


def alle_modi_geselecteerd(modi: list[str]) -> bool:
    return set(modi) == set(MODI)
