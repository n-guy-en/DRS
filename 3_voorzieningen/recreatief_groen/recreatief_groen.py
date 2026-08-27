"""
Valideer OSM-recreatief groen met BAG-panden.

Input:
- 3_voorzieningen/raw/recreatief_groen/recreatief_groen.geojson
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson

Output:
- 0_layers/processed/3_voorzieningen/recreatief_groen/recreatief_groen.gpkg
- 3_voorzieningen/processed/recreatief_groen/recreatief_groen.csv
"""

# %% Stap 1: imports en instellingen
from pathlib import Path
import sys

import geopandas as gpd
import pandas as pd

VOORZIENINGEN_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(VOORZIENINGEN_DIR))

from helpers.instellingen import (  
    BASE_DIR,
    CRS_RD,
    CRS_WGS84,
    GELDIGE_PAND_STATUSSEN,
    JAAR,
)

MAX_AFSTAND_METER = 150.0


# %% Stap 2: recreatief groen en BAG-panden lezen
def lees_recreatief_groen():
    input_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "raw"
        / "recreatief_groen"
        / "recreatief_groen.geojson"
    )
    if not input_pad.exists():
        raise FileNotFoundError(f"Recreatief groen bestand niet gevonden: {input_pad}")

    print(f"Lees recreatief groen: {input_pad}")
    groen = gpd.read_file(input_pad)

    if groen.crs is None:
        groen = groen.set_crs(CRS_WGS84)

    groen = groen.to_crs(CRS_RD)
    groen = groen[groen.geometry.notna()].copy()
    groen = groen[~groen.geometry.is_empty].copy()

    groen["recreatief_groen_id"] = range(1, len(groen) + 1)
    groen["recreatief_groen_lon"] = groen.to_crs(CRS_WGS84).geometry.x.round(8)
    groen["recreatief_groen_lat"] = groen.to_crs(CRS_WGS84).geometry.y.round(8)

    return groen


def lees_panden(jaar):
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


# %% Stap 3: recreatief groen aan BAG-panden koppelen
def koppel_binnen_pand(groen, panden):
    print("Koppel recreatief groen dat binnen een BAG-pand valt (bijv. kassen of specifieke gebouwen)")
    gekoppeld = gpd.sjoin(
        groen,
        panden,
        how="left",
        predicate="within",
    )
    gekoppeld = gekoppeld.drop(columns=["index_right"], errors="ignore")
    gekoppeld["bag_match_type"] = pd.NA
    gekoppeld.loc[gekoppeld["pand_id"].notna(), "bag_match_type"] = "within"
    gekoppeld["bag_afstand_meter"] = 0.0

    return gekoppeld


def koppel_nearest(groen_gekoppeld, panden, max_afstand_meter):
    zonder_match = groen_gekoppeld[
        groen_gekoppeld["pand_id"].isna()
    ].copy()

    if zonder_match.empty:
        return groen_gekoppeld

    print(f"Koppel overig recreatief groen aan dichtstbijzijnde BAG-pand binnen {max_afstand_meter} m")

    pand_attributen = panden.drop(columns="geometry").copy()
    nearest = gpd.sjoin_nearest(
        zonder_match.drop(
            columns=[
                kolom
                for kolom in pand_attributen.columns
                if kolom in zonder_match.columns
            ],
            errors="ignore",
        ),
        panden,
        how="left",
        max_distance=max_afstand_meter,
        distance_col="bag_afstand_meter",
    )
    nearest = nearest.drop(columns=["index_right"], errors="ignore")
    nearest.loc[nearest["pand_id"].notna(), "bag_match_type"] = "nearest"
    nearest.loc[nearest["pand_id"].isna(), "bag_match_type"] = "geen_match"

    met_match = groen_gekoppeld[
        groen_gekoppeld["pand_id"].notna()
    ].copy()

    kolommen = groen_gekoppeld.columns.union(nearest.columns)
    resultaat = pd.concat(
        [
            met_match.reindex(columns=kolommen),
            nearest.reindex(columns=kolommen),
        ],
        ignore_index=True,
    )
    resultaat = gpd.GeoDataFrame(resultaat, geometry="geometry", crs=CRS_RD)

    return resultaat


# %% Stap 4: validatiestatus toevoegen
def voeg_status_toe(groen):
    groen["bag_gevalideerd"] = groen["pand_id"].notna()
    groen["bag_afstand_meter"] = pd.to_numeric(
        groen["bag_afstand_meter"],
        errors="coerce",
    ).round(2)

    return groen


# %% Stap 5: output schrijven
def schrijf_output(groen):
    output_layers = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "recreatief_groen"
    )
    output_csv = BASE_DIR / "3_voorzieningen" / "processed" / "recreatief_groen"
    output_layers.mkdir(parents=True, exist_ok=True)
    output_csv.mkdir(parents=True, exist_ok=True)

    gpkg_pad = output_layers / "recreatief_groen.gpkg"
    csv_pad = output_csv / "recreatief_groen.csv"

    groen_wgs84 = groen.to_crs(CRS_WGS84)
    groen_wgs84.to_file(
        gpkg_pad,
        layer="recreatief_groen",
        driver="GPKG",
    )
    groen_wgs84.drop(columns="geometry").to_csv(csv_pad, index=False)

    print(f"Opgeslagen: {gpkg_pad}")
    print(f"Opgeslagen: {csv_pad}")


# %% Stap 6: workflow uitvoeren
def main():
    groen = lees_recreatief_groen()
    panden = lees_panden(JAAR)

    gekoppeld = koppel_binnen_pand(groen, panden)
    gekoppeld = koppel_nearest(gekoppeld, panden, MAX_AFSTAND_METER)
    gekoppeld = voeg_status_toe(gekoppeld)

    print(f"Recreatief groen totaal: {len(gekoppeld)}")
    print(f"BAG-gevalideerd: {int(gekoppeld['bag_gevalideerd'].sum())}")
    print(f"Geen BAG-match: {int((~gekoppeld['bag_gevalideerd']).sum())}")
    print(gekoppeld["bag_match_type"].value_counts(dropna=False).to_string())

    schrijf_output(gekoppeld)


if __name__ == "__main__":
    main()
