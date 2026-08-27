"""Ziekenhuiscasus: Sneek en Heerenveen vervallen, Joure komt erbij.

Dit script maakt een aparte voorzieningenlaag voor de casus en draait daarna
de bestaande workflows van `5_bereikbaarheid` en `6_interpretatie` voor
`ziekenhuis_joure`. De standaard ziekenhuislaag uit `3_voorzieningen` wordt
niet aangepast.
"""

from __future__ import annotations

import argparse
import os
import sys
from importlib import import_module
import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


BASE_DIR = Path(__file__).resolve().parents[1]
CASUS_NAAM = "ziekenhuis_joure"

BRON_PAD = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "ziekenhuis"
    / "ziekenhuizen.gpkg"
)
CASUS_DIR = BASE_DIR / "7_analyses" / "processed" / CASUS_NAAM
VOORZIENINGEN_DIR = CASUS_DIR / "voorzieningen"
VOORZIENINGEN_PAD = VOORZIENINGEN_DIR / "ziekenhuizen_joure.gpkg"
VOORZIENINGEN_LAYER = "ziekenhuizen_joure"

JOURE_LAT = 52.953427
JOURE_LON = 5.811821

VERVALLEN_NAMEN = {
    "antonius ziekenhuis",
    "frisius medisch centrum heerenveen",
}
VERVALLEN_PLAATSEN = {"sneek", "heerenveen"}


def verwijder_generieke_helpers_imports() -> None:
    """Voorkom dat `helpers.*` naar de verkeerde map blijft wijzen."""
    for module_naam in list(sys.modules):
        if module_naam == "helpers" or module_naam.startswith("helpers."):
            del sys.modules[module_naam]


def activeer_helpers_pad(mapnaam: str) -> None:
    """Zet de gewenste workflowmap voor imports als `helpers.instellingen`."""
    gewenste_pad = str(BASE_DIR / mapnaam)
    andere_paden = {
        str(BASE_DIR / "5_bereikbaarheid"),
        str(BASE_DIR / "6_interpretatie"),
    }
    sys.path[:] = [pad for pad in sys.path if pad not in andere_paden]
    sys.path.insert(0, gewenste_pad)
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    verwijder_generieke_helpers_imports()


def laad_bereikbaarheid_config():
    """Laad expliciet de runconfiguratie van `5_bereikbaarheid`."""
    activeer_helpers_pad("5_bereikbaarheid")
    config_pad = BASE_DIR / "5_bereikbaarheid" / "config.py"
    spec = importlib.util.spec_from_file_location(
        "bereikbaarheid_run_config",
        config_pad,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Kan bereikbaarheidsconfig niet laden: {config_pad}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def registreer_casusconfig() -> None:
    """Registreer deze analyse tijdelijk bij de gedeelde workflows."""
    activeer_helpers_pad("5_bereikbaarheid")
    instellingen = import_module("5_bereikbaarheid.helpers.instellingen")
    instellingen.PRESETS[CASUS_NAAM] = instellingen.VoorzieningConfig(
        naam=CASUS_NAAM,
        label="ziekenhuiscasus Joure",
        pluralis="ziekenhuizen casus Joure",
        layer=VOORZIENINGEN_LAYER,
        input_pad=VOORZIENINGEN_PAD,
    )
    instellingen.NORMEN_PER_VOORZIENING[CASUS_NAAM] = (
        instellingen.NORMEN_PER_VOORZIENING["ziekenhuis"]
    )


def maak_casusvoorzieningen() -> gpd.GeoDataFrame:
    """Maak de ziekenhuislaag voor de Joure-casus."""
    ziekenhuizen = gpd.read_file(BRON_PAD).to_crs("EPSG:4326")

    naam = ziekenhuizen.get("name", pd.Series("", index=ziekenhuizen.index))
    plaats = ziekenhuizen.get("addr:city", pd.Series("", index=ziekenhuizen.index))
    vervalt = (
        naam.fillna("").astype(str).str.strip().str.lower().isin(VERVALLEN_NAMEN)
        | plaats.fillna("").astype(str).str.strip().str.lower().isin(VERVALLEN_PLAATSEN)
    )
    casus = ziekenhuizen.loc[~vervalt].copy()

    joure = {kolom: pd.NA for kolom in casus.columns if kolom != "geometry"}
    joure.update(
        {
            "name": "Ziekenhuis Joure",
            "amenity": "hospital",
            "healthcare": "hospital",
            "addr:city": "Joure",
            "ziekenhuis_id": "joure",
            "ziekenhuis_lat": JOURE_LAT,
            "ziekenhuis_lon": JOURE_LON,
            "bag_gevalideerd": False,
            "match_type": "analyse_scenario",
            "bag_match_type": "analyse_scenario",
        }
    )
    joure["geometry"] = Point(JOURE_LON, JOURE_LAT)
    casus = gpd.GeoDataFrame(
        pd.concat([casus, gpd.GeoDataFrame([joure], geometry="geometry", crs="EPSG:4326")]),
        geometry="geometry",
        crs="EPSG:4326",
    )

    casus = casus.reset_index(drop=True)
    casus["ziekenhuis_joure_id"] = casus["ziekenhuis_id"].astype(str)
    casus["ziekenhuis_joure_lat"] = casus.geometry.y
    casus["ziekenhuis_joure_lon"] = casus.geometry.x

    VOORZIENINGEN_DIR.mkdir(parents=True, exist_ok=True)
    if VOORZIENINGEN_PAD.exists():
        VOORZIENINGEN_PAD.unlink()
    casus.to_file(VOORZIENINGEN_PAD, layer=VOORZIENINGEN_LAYER, driver="GPKG")

    overzicht = casus[["ziekenhuis_joure_id", "name", "addr:city"]].copy()
    overzicht.to_csv(CASUS_DIR / "ziekenhuizen_joure_overzicht.csv", index=False)
    return casus


def run_bereikbaarheid() -> None:
    activeer_helpers_pad("5_bereikbaarheid")
    bereikbaarheid_run_config = laad_bereikbaarheid_config()

    workflow = import_module("5_bereikbaarheid.helpers.workflow")
    workflow.run_bereikbaarheid(
        CASUS_NAAM,
        runtime_config=bereikbaarheid_run_config.RUN,
        maak_pand_flowmaps=bereikbaarheid_run_config.PAND_FLOWMAPS,
    )


def run_interpretatie() -> None:
    activeer_helpers_pad("6_interpretatie")
    os.environ["INTERPRETATIE_VOORZIENING"] = CASUS_NAAM
    os.environ["INTERPRETATIE_MODI"] = os.environ.get("INTERPRETATIE_MODI", "all")

    for module_naam in list(sys.modules):
        if module_naam.startswith("6_interpretatie.helpers."):
            del sys.modules[module_naam]

    workflow = import_module("6_interpretatie.helpers.workflow")
    workflow.stel_actieve_voorziening(CASUS_NAAM)
    workflow.run_interpretatie()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draai de ziekenhuiscasus met Joure als scenarioziekenhuis."
    )
    parser.add_argument(
        "--interpretatie",
        action="store_true",
        help="Maak/registreer de casuslaag en draai alleen 6_interpretatie.",
    )
    parser.add_argument(
        "--bop",
        action="store_true",
        help="Maak/registreer de casuslaag en draai alleen 5_bereikbaarheid.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    alleen_interpretatie = args.interpretatie
    if alleen_interpretatie and args.bop:
        raise ValueError("Kies --interpretatie of --bop, niet allebei.")

    casus = maak_casusvoorzieningen()
    print(f"Casusvoorzieningen opgeslagen: {VOORZIENINGEN_PAD}")
    print(casus[["ziekenhuis_joure_id", "name", "addr:city"]].to_string(index=False))
    registreer_casusconfig()

    if not alleen_interpretatie:
        print("\n=== Run 5_bereikbaarheid: ziekenhuis_joure ===")
        run_bereikbaarheid()

    if not args.bop:
        print("\n=== Run 6_interpretatie: ziekenhuis_joure ===")
        run_interpretatie()


if __name__ == "__main__":
    main()
