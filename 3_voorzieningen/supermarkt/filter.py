# %% Stap 1: imports
from pathlib import Path
import sys

import pandas as pd
import geopandas as gpd


VOORZIENINGEN_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(VOORZIENINGEN_DIR))

from helpers.instellingen import BASE_DIR  
from helpers.validatie import valideer_kolommen  


# %% Stap 2: paden
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"
PROCESSED_DIR = VOORZIENINGEN_DIR / "processed"
SUPERMARKT_PROCESSED_DIR = PROCESSED_DIR / "supermarkt"
INPUT_CSV = SUPERMARKT_PROCESSED_DIR / "supermarkten.csv"
INPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "supermarkt"
    / "supermarkten.gpkg"
)
OUTPUT_CSV = SUPERMARKT_PROCESSED_DIR / "supermarkten_groot.csv"
OUTPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "supermarkt"
    / "supermarkten_groot.gpkg"
)


# %% Stap 3: instellingen
# Deze lijst bepaalt welke voorzieningen meetellen als grote supermarkt.
# Pas deze lijst aan als je ketens wilt toevoegen of uitsluiten.
GROTE_SUPERMARKT_KETENS = [
    "Albert Heijn",
    "Albert Heijn XL",
    "ALDI",
    "Dirk",
    "Jumbo",
    "Lidl",
    "PLUS",
    "Poiesz",
    "SPAR",
    "Coop"
]

UITSLUITEN_NAAM_BEVAT = [
    "pick-up",
    "pickup",
]
VEREISTE_SUPERMARKT_KOLOMMEN = {"brand", "name", "shop", "bag_gevalideerd"}


# %% Stap 4: filterfuncties
def normaliseer_tekst(waarde: object) -> str:
    if pd.isna(waarde):
        return ""

    return str(waarde).strip().lower()


def print_unieke_waarden(df: pd.DataFrame, kolom: str) -> None:
    print(f"\nUnieke waarden in kolom '{kolom}':")

    waarden = (
        df[kolom]
        .fillna("(leeg)")
        .astype(str)
        .str.strip()
        .value_counts()
        .reset_index()
    )
    waarden.columns = [kolom, "aantal"]

    print(waarden.to_string(index=False))


def is_bag_gevalideerd(waarde: object) -> bool:
    if pd.isna(waarde):
        return False
    if isinstance(waarde, bool):
        return waarde
    return str(waarde).strip().lower() in {"true", "1", "ja", "yes"}


def is_grote_supermarkt(row: pd.Series) -> bool:
    brand = normaliseer_tekst(row.get("brand"))
    name = normaliseer_tekst(row.get("name"))
    shop = normaliseer_tekst(row.get("shop"))

    if shop != "supermarket":
        return False

    for tekst in UITSLUITEN_NAAM_BEVAT:
        if tekst in name:
            return False

    for keten in GROTE_SUPERMARKT_KETENS:
        keten_norm = normaliseer_tekst(keten)

        if brand == keten_norm:
            return True

        if name == keten_norm or name.startswith(f"{keten_norm} "):
            return True

    return False


def filter_grote_supermarkten(df: pd.DataFrame) -> pd.DataFrame:
    valideer_kolommen(
        df,
        VEREISTE_SUPERMARKT_KOLOMMEN,
        "Supermarktenbestand",
    )
    df = df.copy()
    df["is_grote_supermarkt"] = df.apply(
        is_grote_supermarkt,
        axis=1,
    )
    df["_bag_gevalideerd_bool"] = df["bag_gevalideerd"].apply(is_bag_gevalideerd)

    resultaat = df[
        df["is_grote_supermarkt"]
        & df["_bag_gevalideerd_bool"]
    ].copy()
    return resultaat.drop(columns=["_bag_gevalideerd_bool"])


# %% Stap 5: workflow uitvoeren
def main() -> None:
    supermarkten = pd.read_csv(INPUT_CSV, dtype={"pand_id": "string"})

    print(f"Aantal supermarkten totaal: {len(supermarkten)}")

    print_unieke_waarden(supermarkten, "brand")
    print_unieke_waarden(supermarkten, "name")

    grote_supermarkten = filter_grote_supermarkten(supermarkten)

    tijdelijk_csv = OUTPUT_CSV.with_suffix(".tmp.csv")
    grote_supermarkten.to_csv(tijdelijk_csv, index=False)
    tijdelijk_csv.replace(OUTPUT_CSV)

    supermarkten_gpkg = gpd.read_file(INPUT_GPKG, layer="supermarkten")
    grote_supermarkten_gpkg = filter_grote_supermarkten(supermarkten_gpkg)
    tijdelijk_gpkg = OUTPUT_GPKG.with_name("supermarkten_groot.tmp.gpkg")
    tijdelijk_gpkg.unlink(missing_ok=True)
    grote_supermarkten_gpkg.to_file(
        tijdelijk_gpkg,
        layer="supermarkten_groot",
        driver="GPKG",
    )
    tijdelijk_gpkg.replace(OUTPUT_GPKG)

    print("\nSelectie grote supermarkten:")
    print(f"Aantal geselecteerd: {len(grote_supermarkten)}")
    print(
        grote_supermarkten["brand"]
        .fillna("(leeg)")
        .astype(str)
        .str.strip()
        .value_counts()
        .to_string()
    )
    print(f"\nOpgeslagen: {OUTPUT_CSV}")
    print(f"Opgeslagen: {OUTPUT_GPKG}")


if __name__ == "__main__":
    main()
