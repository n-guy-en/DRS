from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
RAPPORT_DIR = BASE_DIR / "8_rapport"
OUT_DIR = RAPPORT_DIR / "processed" / "rapport"

bereikbaarheid_instellingen = import_module("5_bereikbaarheid.helpers.instellingen")

RAPPORT_MODUS_LABELS = {
    "lopen": "Lopen",
    "fiets": "Fiets",
    "auto": "Auto",
    "ov_lopen": "OV met lopen",
    "ov_fiets": "OV met fiets",
}
MODI = [
    (modus, code, RAPPORT_MODUS_LABELS[modus])
    for modus, code in bereikbaarheid_instellingen.MODUS_CODES.items()
]
NIET_AUTO_MODI = [modus_item[0] for modus_item in MODI if modus_item[0] != "auto"]
MODUS_LABELS = {modus_item[0]: modus_item[2] for modus_item in MODI}
MODUS_POSITIE = {
    modus_item[2]: i
    for i, modus_item in enumerate(MODI, start=1)
}


def pandlaag_bestandsnaam(analyse_naam: str, code: str, suffix: str = "") -> str:
    return f"{analyse_naam}_{code}{suffix}.gpkg"


def bestaande_pandlaag(
    run: "VoorzieningRun",
    modus: str,
    code: str,
    suffix: str = "",
) -> Path:
    return run.pandlagen_rel / modus / pandlaag_bestandsnaam(
        run.bestandsnaam_prefix,
        code,
        suffix,
    )

ONDERWIJS_LABELS = bereikbaarheid_instellingen.ONDERWIJS_NIVEAU_NAMEN
VOORZIENING_LABELS = {
    slug: config.label.capitalize()
    for slug, config in bereikbaarheid_instellingen.PRESETS.items()
    if slug != "onderwijs"
}


@dataclass(frozen=True)
class VoorzieningRun:
    slug: str
    label: str
    analyse_naam: str
    bestandsnaam_prefix: str
    bereikbaarheid_rel: Path
    pandlagen_rel: Path
    dus_rel: Path


def voorziening_label(slug: str) -> str:
    if slug.startswith("onderwijs_"):
        niveau = slug.removeprefix("onderwijs_")
        return ONDERWIJS_LABELS.get(niveau, niveau.replace("_", " ").capitalize())
    return VOORZIENING_LABELS.get(slug, slug.replace("_", " ").capitalize())


def zichtbaar_ja_nee(waarde: bool) -> str:
    return "Ja" if bool(waarde) else "Nee"


def bereikbaarheidsklasse(percentage_binnen: float | int | None) -> str:
    if pd.isna(percentage_binnen):
        return "Onvoldoende gegevens"
    waarde = float(percentage_binnen)
    if waarde >= 80.0:
        return "Goed"
    if waarde >= 60.0:
        return "Vereist aandacht"
    if waarde >= 40.0:
        return "Knelpunt"
    return "Ernstig"
