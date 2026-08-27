"""
Valideer OSM-supermarkten met BAG-panden.

Input:
- 3_voorzieningen/raw/supermarkt/supermarkt.geojson
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson

Output:
- 0_layers/processed/3_voorzieningen/supermarkt/supermarkten.gpkg
- 3_voorzieningen/processed/supermarkt/supermarkten.csv
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


VEREISTE_SUPERMARKT_KOLOMMEN = {"geometry"}
VEREISTE_PAND_KOLOMMEN = {"pand_id", "geometry"}


# %% Stap 2: supermarkten en BAG-panden lezen
def lees_supermarkten() -> gpd.GeoDataFrame:
    input_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "raw"
        / "supermarkt"
        / "supermarkt.geojson"
    )

    if not input_pad.exists():
        raise FileNotFoundError(f"Supermarktbestand niet gevonden: {input_pad}")

    print(f"Lees supermarkten: {input_pad}")
    supermarkten = gpd.read_file(input_pad)
    valideer_kolommen(
        supermarkten,
        VEREISTE_SUPERMARKT_KOLOMMEN,
        "Supermarktbestand",
    )

    if supermarkten.crs is None:
        supermarkten = supermarkten.set_crs(CRS_WGS84)

    supermarkten = supermarkten.to_crs(CRS_RD)
    supermarkten = supermarkten[supermarkten.geometry.notna()].copy()
    supermarkten = supermarkten[~supermarkten.geometry.is_empty].copy()

    supermarkten["supermarkt_id"] = range(1, len(supermarkten) + 1)
    supermarkten["supermarkt_lon"] = supermarkten.to_crs(CRS_WGS84).geometry.x.round(8)
    supermarkten["supermarkt_lat"] = supermarkten.to_crs(CRS_WGS84).geometry.y.round(8)

    return supermarkten


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
def schrijf_output(supermarkten: gpd.GeoDataFrame) -> None:
    output_layers = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "supermarkt"
    )
    output_csv = BASE_DIR / "3_voorzieningen" / "processed" / "supermarkt"
    output_layers.mkdir(parents=True, exist_ok=True)
    output_csv.mkdir(parents=True, exist_ok=True)

    gpkg_pad = output_layers / "supermarkten.gpkg"
    csv_pad = output_csv / "supermarkten.csv"
    tijdelijk_gpkg_pad = output_layers / "supermarkten.tmp.gpkg"
    tijdelijk_csv_pad = output_csv / "supermarkten.tmp.csv"
    tijdelijk_gpkg_pad.unlink(missing_ok=True)

    supermarkten_wgs84 = supermarkten.to_crs(CRS_WGS84)
    supermarkten_wgs84.to_file(
        tijdelijk_gpkg_pad,
        layer="supermarkten",
        driver="GPKG",
    )
    supermarkten_wgs84.drop(columns="geometry").to_csv(tijdelijk_csv_pad, index=False)
    tijdelijk_gpkg_pad.replace(gpkg_pad)
    tijdelijk_csv_pad.replace(csv_pad)

    print(f"Opgeslagen: {gpkg_pad}")
    print(f"Opgeslagen: {csv_pad}")


# %% Stap 4: workflow uitvoeren
def main() -> None:
    supermarkten = lees_supermarkten()
    panden = lees_panden(JAAR)

    gekoppeld = koppel_punten_aan_panden(
        supermarkten,
        panden,
        MAX_AFSTAND_METER,
        "supermarkten",
    )
    gekoppeld = voeg_bag_status_toe(gekoppeld)

    print(f"Supermarkten totaal: {len(gekoppeld)}")
    print(f"BAG-gevalideerd: {int(gekoppeld['bag_gevalideerd'].sum())}")
    print(f"Geen BAG-match: {int((~gekoppeld['bag_gevalideerd']).sum())}")
    print(gekoppeld["bag_match_type"].value_counts(dropna=False).to_string())

    schrijf_output(gekoppeld)


if __name__ == "__main__":
    main()
