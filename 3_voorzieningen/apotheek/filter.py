# %% Stap 1: imports
from pathlib import Path

import geopandas as gpd
import pandas as pd


# %% Stap 2: paden
BASE_DIR = Path(__file__).resolve().parents[2]
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"
PROCESSED_DIR = VOORZIENINGEN_DIR / "processed"
APOTHEEK_PROCESSED_DIR = PROCESSED_DIR / "apotheek"
INPUT_CSV = APOTHEEK_PROCESSED_DIR / "apotheek.csv"
INPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "apotheek"
    / "apotheek.gpkg"
)
OUTPUT_CSV = APOTHEEK_PROCESSED_DIR / "apotheek_groot.csv"
OUTPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "apotheek"
    / "apotheek_groot.gpkg"
)


# %% Stap 3: instellingen
# Bekende apotheek-ketens of -organisaties in Nederland
APOTHEEK_KETENS = [
    "benu",
    "service apotheek",
    "alphega",
    "mediq",
    "plinthos",
    "apotheek",
]

# Uit te sluiten termen (zoals afhaalpunten die geen volledige apotheek zijn of veterinaire apotheken)
UITSLUITEN_NAAM_BEVAT = [
    "dierenapotheek",
    "afhaalkluis",
    "medicijnkluis",
]


# %% Stap 4: filterfuncties
def normaliseer_tekst(waarde):
    if pd.isna(waarde):
        return ""

    return str(waarde).strip().lower()


def is_bag_gevalideerd(waarde):
    if pd.isna(waarde):
        return False
    if isinstance(waarde, bool):
        return waarde
    return str(waarde).strip().lower() in {"true", "1", "ja", "yes"}


def print_unieke_waarden(df, kolom):
    if kolom not in df.columns:
        return
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


def is_apotheek(row):
    brand = normaliseer_tekst(row.get("brand"))
    name = normaliseer_tekst(row.get("name"))
    amenity = normaliseer_tekst(row.get("amenity"))
    healthcare = normaliseer_tekst(row.get("healthcare"))

    # Uitsluiten van specifieke termen
    for uitsluiten in UITSLUITEN_NAAM_BEVAT:
        if uitsluiten in name:
            return False

    # Check of het een apotheek is op basis van amenity of healthcare tag
    if amenity == "pharmacy" or healthcare == "pharmacy":
        return True

    # Als de naam of het merk 'apotheek' of een bekende keten bevat
    keten_tekst = f"{name} {brand}".lower()
    for keten in APOTHEEK_KETENS:
        if keten in keten_tekst:
            return True

    return False


def filter_apotheken(df):
    df = df.copy()
    df["is_groot_apotheek"] = df.apply(
        is_apotheek,
        axis=1,
    )
    df["_bag_gevalideerd_bool"] = df["bag_gevalideerd"].apply(is_bag_gevalideerd)

    return df[
        df["is_groot_apotheek"]
        & df["_bag_gevalideerd_bool"]
    ].drop(columns=["_bag_gevalideerd_bool"]).copy()


# %% Stap 5: workflow uitvoeren
def main():
    apotheken = pd.read_csv(INPUT_CSV, dtype={"pand_id": "string"})

    print(f"Aantal apotheken totaal: {len(apotheken)}")

    print_unieke_waarden(apotheken, "brand")
    print_unieke_waarden(apotheken, "name")

    grote_apotheken = filter_apotheken(apotheken)

    grote_apotheken.to_csv(OUTPUT_CSV, index=False)

    apotheken_gpkg = gpd.read_file(INPUT_GPKG, layer="apotheek")
    grote_apotheken_gpkg = filter_apotheken(apotheken_gpkg)
    grote_apotheken_gpkg.to_file(
        OUTPUT_GPKG,
        layer="apotheek_groot",
        driver="GPKG",
    )

    print("\nSelectie apotheken:")
    print(f"Aantal geselecteerd: {len(grote_apotheken)}")
    print(
        grote_apotheken["brand"]
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
