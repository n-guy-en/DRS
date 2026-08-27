# %% Stap 1: imports
from pathlib import Path

import geopandas as gpd
import pandas as pd


# %% Stap 2: paden
BASE_DIR = Path(__file__).resolve().parents[2]
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"
PROCESSED_DIR = VOORZIENINGEN_DIR / "processed"
HUISARTS_PROCESSED_DIR = PROCESSED_DIR / "huisarts"
INPUT_CSV = HUISARTS_PROCESSED_DIR / "huisarts.csv"
INPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "huisarts"
    / "huisarts.gpkg"
)
OUTPUT_CSV = HUISARTS_PROCESSED_DIR / "huisarts_groot.csv"
OUTPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "huisarts"
    / "huisarts_groot.gpkg"
)


# %% Stap 3: instellingen
# Sleutelwoorden die wijzen op een huisartsenpraktijk of gezondheidscentrum
HUISARTS_SLEUTELWOORDEN = [
    "huisarts",
    "huisartsen",
    "huisartsenpraktijk",
    "huisartsenmaatschap",
    "gezondheidscentrum",
    "medisch centrum",
    "dokter",
    "dokters",
    "praktijk",
    "maatschap",
]

# Sleutelwoorden van specialisten die we willen uitsluiten van huisartsen
UITSLUITEN_NAAM_BEVAT = [
    "tandarts",
    "dierenarts",
    "fysiotherapie",
    "fysio",
    "huidtherapie",
    "orthodontie",
    "logopedie",
    "psycholoog",
    "acupunctuur",
    "podotherapie",
    "dierenkliniek",
    "kliniek voor gezelschapsdieren",
    "oogarts",
    "verloskundigen",
    "ehbo",
    "ggd",
    "ggz",
    "neuropsychiatrie",
    "pedicure",
    "voetverzorging",
    "voetzorg",
    "leren",
    "pynter",
    "ziekenhuis",
    "ambulance",
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


def is_huisartsenpraktijk(row):
    name = normaliseer_tekst(row.get("name"))
    amenity = normaliseer_tekst(row.get("amenity"))
    healthcare = normaliseer_tekst(row.get("healthcare"))
    speciality = normaliseer_tekst(row.get("healthcare:speciality"))

    # Uitsluiten van specifieke specialisten
    for uitsluiten in UITSLUITEN_NAAM_BEVAT:
        if uitsluiten in name:
            return False

    # Als de specialiteit expliciet general practice is, is het goed
    if speciality == "general" or "general" in speciality:
        return True

    # Als de naam huisarts-gerelateerd is
    for woord in HUISARTS_SLEUTELWOORDEN:
        if woord in name:
            return True

    # Als de amenity doctors is en er geen uitsluitingen in de naam zitten
    if amenity == "doctors" or healthcare == "doctor":
        # We vereisen ofwel een naam-match of we nemen hem bij verstek aan
        # als de naam leeg is of geen bekende uitsluiting bevat.
        if not name or any(w in name for w in HUISARTS_SLEUTELWOORDEN):
            return True
        # Indien doctors maar geen specifieke huisartsennaam en niet uitgesloten,
        # dan nemen we hem als GP aan tenzij het een duidelijke specialist is.
        return True

    return False


def filter_huisartsen(df):
    df = df.copy()
    df["is_groot_huisarts"] = df.apply(
        is_huisartsenpraktijk,
        axis=1,
    )
    df["_bag_gevalideerd_bool"] = df["bag_gevalideerd"].apply(is_bag_gevalideerd)

    return df[
        df["is_groot_huisarts"]
        & df["_bag_gevalideerd_bool"]
    ].drop(columns=["_bag_gevalideerd_bool"]).copy()


# %% Stap 5: workflow uitvoeren
def main():
    huisartsen = pd.read_csv(INPUT_CSV, dtype={"pand_id": "string"})

    print(f"Aantal huisartsen totaal: {len(huisartsen)}")

    print_unieke_waarden(huisartsen, "name")

    grote_huisartsen = filter_huisartsen(huisartsen)

    grote_huisartsen.to_csv(OUTPUT_CSV, index=False)

    huisartsen_gpkg = gpd.read_file(INPUT_GPKG, layer="huisarts")
    grote_huisartsen_gpkg = filter_huisartsen(huisartsen_gpkg)
    grote_huisartsen_gpkg.to_file(
        OUTPUT_GPKG,
        layer="huisarts_groot",
        driver="GPKG",
    )

    print("\nSelectie huisartsenpraktijken:")
    print(f"Aantal geselecteerd: {len(grote_huisartsen)}")
    print(
        grote_huisartsen["name"]
        .fillna("(onbekende naam)")
        .astype(str)
        .str.strip()
        .value_counts()
        .head(20)
        .to_string()
    )
    print(f"\nOpgeslagen: {OUTPUT_CSV}")
    print(f"Opgeslagen: {OUTPUT_GPKG}")


if __name__ == "__main__":
    main()
