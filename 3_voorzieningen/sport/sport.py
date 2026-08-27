"""
Valideer OSM/WFS-sportvoorzieningen met BAG-panden.

Input:
- 3_voorzieningen/raw/sport/sport.geojson
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson

Output:
- 0_layers/processed/3_voorzieningen/sport/sport.gpkg
- 3_voorzieningen/processed/sport/sport.csv
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
    MAX_AFSTAND_METER,
)


# %% Stap 2: sportvoorzieningen en BAG-panden lezen
def lees_sportvoorzieningen():
    input_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "raw"
        / "sport"
        / "sport.geojson"
    )
    if not input_pad.exists():
        raise FileNotFoundError(f"Sportvoorzieningenbestand niet gevonden: {input_pad}")

    print(f"Lees sportvoorzieningen: {input_pad}")
    sport = gpd.read_file(input_pad)

    if sport.crs is None:
        sport = sport.set_crs(CRS_WGS84)

    sport = sport.to_crs(CRS_RD)
    sport = sport[sport.geometry.notna()].copy()
    sport = sport[~sport.geometry.is_empty].copy()

    sport["sport_id"] = range(1, len(sport) + 1)
    sport["sport_lon"] = sport.to_crs(CRS_WGS84).geometry.x.round(8)
    sport["sport_lat"] = sport.to_crs(CRS_WGS84).geometry.y.round(8)

    return sport


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


# %% Stap 3: sportvoorzieningen aan BAG-panden koppelen
def koppel_binnen_pand(sport, panden):
    print("Koppel sportvoorzieningen die binnen een BAG-pand vallen")
    gekoppeld = gpd.sjoin(
        sport,
        panden,
        how="left",
        predicate="within",
    )
    gekoppeld = gekoppeld.drop(columns=["index_right"], errors="ignore")
    gekoppeld["bag_match_type"] = pd.NA
    gekoppeld.loc[gekoppeld["pand_id"].notna(), "bag_match_type"] = "within"
    gekoppeld["bag_afstand_meter"] = 0.0

    return gekoppeld


def koppel_nearest(sport_gekoppeld, panden, max_afstand_meter):
    zonder_match = sport_gekoppeld[
        sport_gekoppeld["pand_id"].isna()
    ].copy()

    if zonder_match.empty:
        return sport_gekoppeld

    print(f"Koppel overige sportvoorzieningen aan nearest BAG-pand binnen {max_afstand_meter} m")

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

    met_match = sport_gekoppeld[
        sport_gekoppeld["pand_id"].notna()
    ].copy()

    kolommen = sport_gekoppeld.columns.union(nearest.columns)
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
def voeg_status_toe(sport):
    sport["bag_gevalideerd"] = sport["pand_id"].notna()
    sport["bag_afstand_meter"] = pd.to_numeric(
        sport["bag_afstand_meter"],
        errors="coerce",
    ).round(2)

    return sport


# %% Stap 5: output schrijven
def schrijf_output(sport):
    output_layers = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "sport"
    )
    output_csv = BASE_DIR / "3_voorzieningen" / "processed" / "sport"
    output_layers.mkdir(parents=True, exist_ok=True)
    output_csv.mkdir(parents=True, exist_ok=True)

    gpkg_pad = output_layers / "sport.gpkg"
    csv_pad = output_csv / "sport.csv"

    sport_wgs84 = sport.to_crs(CRS_WGS84)
    sport_wgs84.to_file(
        gpkg_pad,
        layer="sport",
        driver="GPKG",
    )
    sport_wgs84.drop(columns="geometry").to_csv(csv_pad, index=False)

    print(f"Opgeslagen: {gpkg_pad}")
    print(f"Opgeslagen: {csv_pad}")


# %% Stap 6: workflow uitvoeren
def main():
    sport = lees_sportvoorzieningen()
    panden = lees_panden(JAAR)

    gekoppeld = koppel_binnen_pand(sport, panden)
    gekoppeld = koppel_nearest(gekoppeld, panden, MAX_AFSTAND_METER)
    gekoppeld = voeg_status_toe(gekoppeld)

    print(f"Sportvoorzieningen totaal: {len(gekoppeld)}")
    print(f"BAG-gevalideerd: {int(gekoppeld['bag_gevalideerd'].sum())}")
    print(f"Geen BAG-match: {int((~gekoppeld['bag_gevalideerd']).sum())}")
    print(gekoppeld["bag_match_type"].value_counts(dropna=False).to_string())

    schrijf_output(gekoppeld)


if __name__ == "__main__":
    main()
