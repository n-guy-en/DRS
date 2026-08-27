"""
Valideer OSM-ziekenhuizen met BAG-panden.

Input:
- 3_voorzieningen/raw/ziekenhuis/ziekenhuis.geojson
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson

Output:
- 0_layers/processed/3_voorzieningen/ziekenhuis/ziekenhuizen.gpkg
- 3_voorzieningen/processed/ziekenhuis/ziekenhuizen.csv
"""

# %% Stap 1: imports en instellingen
from pathlib import Path
import sys

import geopandas as gpd


VOORZIENINGEN_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(VOORZIENINGEN_DIR))

from helpers.instellingen import (
    BASE_DIR,
    CRS_RD,
    CRS_WGS84,
    GELDIGE_PAND_STATUSSEN,
    JAAR,
    MAX_AFSTAND_METER,
)
from helpers.punt_bag import koppel_punten_aan_panden, voeg_bag_status_toe
from helpers.validatie import valideer_kolommen


VEREISTE_ZIEKENHUIS_KOLOMMEN = {"geometry"}
VEREISTE_PAND_KOLOMMEN = {"pand_id", "geometry"}


# %% Stap 2: ziekenhuizen en BAG-panden lezen
def lees_ziekenhuizen() -> gpd.GeoDataFrame:
    input_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "raw"
        / "ziekenhuis"
        / "ziekenhuis.geojson"
    )

    if not input_pad.exists():
        raise FileNotFoundError(
            f"Ziekenhuisbestand niet gevonden: {input_pad}. "
            "Run eerst 3_voorzieningen/ziekenhuis/fetch.py."
        )

    print(f"Lees ziekenhuizen: {input_pad}")
    ziekenhuizen = gpd.read_file(input_pad)
    valideer_kolommen(
        ziekenhuizen,
        VEREISTE_ZIEKENHUIS_KOLOMMEN,
        "Ziekenhuisbestand",
    )

    if ziekenhuizen.crs is None:
        ziekenhuizen = ziekenhuizen.set_crs(CRS_WGS84)

    ziekenhuizen = ziekenhuizen.to_crs(CRS_RD)
    ziekenhuizen = ziekenhuizen[ziekenhuizen.geometry.notna()].copy()
    ziekenhuizen = ziekenhuizen[~ziekenhuizen.geometry.is_empty].copy()

    ziekenhuizen["ziekenhuis_id"] = range(1, len(ziekenhuizen) + 1)
    ziekenhuizen["ziekenhuis_lon"] = (
        ziekenhuizen.to_crs(CRS_WGS84).geometry.x.round(8)
    )
    ziekenhuizen["ziekenhuis_lat"] = (
        ziekenhuizen.to_crs(CRS_WGS84).geometry.y.round(8)
    )

    return ziekenhuizen


def lees_panden(jaar: int) -> gpd.GeoDataFrame:
    input_pad = (
        BASE_DIR
        / "2_bag"
        / "bag_frl_xml"
        / "per_jaar"
        / f"pnd_fryslan_{jaar}.geojson"
    )

    if not input_pad.exists():
        raise FileNotFoundError(f"BAG-pandbestand niet gevonden: {input_pad}")

    print(f"Lees BAG-panden: {input_pad}")
    panden = gpd.read_file(input_pad)
    valideer_kolommen(panden, VEREISTE_PAND_KOLOMMEN, "BAG-pandbestand")

    if panden.crs is None:
        panden = panden.set_crs(CRS_WGS84)

    panden = panden.to_crs(CRS_RD)
    panden = panden[panden.geometry.notna()].copy()
    panden = panden[~panden.geometry.is_empty].copy()

    if "pand_status" in panden.columns:
        panden = panden[panden["pand_status"].isin(GELDIGE_PAND_STATUSSEN)].copy()

    kolommen = [
        "pand_id",
        "bouwjaar",
        "pand_status",
        "pand_begin_geldigheid",
        "geometry",
    ]
    kolommen = [kolom for kolom in kolommen if kolom in panden.columns]

    return panden[kolommen].copy()


# %% Stap 3: output schrijven
def schrijf_output(ziekenhuizen: gpd.GeoDataFrame) -> None:
    output_layers = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "ziekenhuis"
    )
    output_csv = BASE_DIR / "3_voorzieningen" / "processed" / "ziekenhuis"
    output_layers.mkdir(parents=True, exist_ok=True)
    output_csv.mkdir(parents=True, exist_ok=True)

    gpkg_pad = output_layers / "ziekenhuizen.gpkg"
    csv_pad = output_csv / "ziekenhuizen.csv"
    tijdelijk_gpkg_pad = output_layers / "ziekenhuizen.tmp.gpkg"
    tijdelijk_csv_pad = output_csv / "ziekenhuizen.tmp.csv"
    tijdelijk_gpkg_pad.unlink(missing_ok=True)

    ziekenhuizen_wgs84 = ziekenhuizen.to_crs(CRS_WGS84)
    ziekenhuizen_wgs84.to_file(
        tijdelijk_gpkg_pad,
        layer="ziekenhuizen",
        driver="GPKG",
    )
    ziekenhuizen_wgs84.drop(columns="geometry").to_csv(tijdelijk_csv_pad, index=False)
    tijdelijk_gpkg_pad.replace(gpkg_pad)
    tijdelijk_csv_pad.replace(csv_pad)

    print(f"Opgeslagen: {gpkg_pad}")
    print(f"Opgeslagen: {csv_pad}")


# %% Stap 4: workflow uitvoeren
def main() -> None:
    ziekenhuizen = lees_ziekenhuizen()
    panden = lees_panden(JAAR)

    gekoppeld = koppel_punten_aan_panden(
        ziekenhuizen,
        panden,
        MAX_AFSTAND_METER,
        "ziekenhuizen",
    )
    gekoppeld = voeg_bag_status_toe(gekoppeld)

    print(f"Ziekenhuizen totaal: {len(gekoppeld)}")
    print(f"BAG-gevalideerd: {int(gekoppeld['bag_gevalideerd'].sum())}")
    print(f"Geen BAG-match: {int((~gekoppeld['bag_gevalideerd']).sum())}")
    print(gekoppeld["bag_match_type"].value_counts(dropna=False).to_string())

    schrijf_output(gekoppeld)


if __name__ == "__main__":
    main()
