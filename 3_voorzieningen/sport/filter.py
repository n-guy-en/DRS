# %% Stap 1: imports
from pathlib import Path
import geopandas as gpd
import pandas as pd

# %% Stap 2: paden
BASE_DIR = Path(__file__).resolve().parents[2]
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"
PROCESSED_DIR = VOORZIENINGEN_DIR / "processed"
SPORT_PROCESSED_DIR = PROCESSED_DIR / "sport"
INPUT_CSV = SPORT_PROCESSED_DIR / "sport.csv"
INPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "sport"
    / "sport.gpkg"
)
OUTPUT_CSV = SPORT_PROCESSED_DIR / "sport_groot.csv"
OUTPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "sport"
    / "sport_groot.gpkg"
)


# %% Stap 3: instellingen
# Termen in naam of tags die wijzen op privé- of exclusief/niet-recreatief gebruik
UITSLUITEN_NAAM_BEVAT = [
    "privé",
    "private",
    "achtertuin",
    "prive",
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


def is_geschikte_sportvoorziening(row):
    # Check access tags
    access = normaliseer_tekst(row.get("access"))
    if access in ["private", "no", "members_only", "membership"]:
        return False
        
    # Check private tag
    private = normaliseer_tekst(row.get("private"))
    if private in ["yes", "true"]:
        return False

    name = normaliseer_tekst(row.get("name"))
    # Uitsluiten op basis van specifieke termen in de naam
    for uitsluiten in UITSLUITEN_NAAM_BEVAT:
        if uitsluiten in name:
            return False

    # Check leisure type
    leisure = normaliseer_tekst(row.get("leisure"))
    sport_type = normaliseer_tekst(row.get("sport"))
    
    # We houden sports_centre, pitch, sports_hall, stadium, track, swimming_pool, horse_riding
    geldige_leisure = {
        "sports_centre",
        "pitch",
        "sports_hall",
        "stadium",
        "track",
        "swimming_pool",
        "horse_riding"
    }
    
    # Als het een municipal_wfs import is (bijv. de traditionele Kaatsvelden), is het altijd geldig
    if row.get("osm_type") == "municipal_wfs" or row.get("source") == "gemeente_swf":
        return True
        
    if leisure in geldige_leisure:
        return True

    return False


def filter_sportvoorzieningen(df, csv_df=None):
    df = df.copy()

    if csv_df is not None and "sport_id" in df.columns and "sport_id" in csv_df.columns:
        geom = df.geometry
        df["sport_id"] = df["sport_id"].astype(str)
        csv_df_temp = csv_df.copy()
        csv_df_temp["sport_id"] = csv_df_temp["sport_id"].astype(str)
        cols_to_use = csv_df_temp.columns.difference(df.columns).tolist() + ["sport_id"]
        df = df.merge(csv_df_temp[cols_to_use], on="sport_id", how="left")
        df.geometry = geom

    df["is_openbaar"] = df.apply(
        is_geschikte_sportvoorziening,
        axis=1,
    )

    if "bronnen" in df.columns:
        valid_registry = df["bronnen"].apply(
            lambda x: pd.notna(x)
            and len(
                [
                    s
                    for s in str(x).split(",")
                    if s.strip() and s.strip() != "osm"
                ]
            )
            > 0
        )
    elif "betrouwbaarheid" in df.columns:
        valid_registry = (
            df["bag_gevalideerd"].apply(is_bag_gevalideerd)
            | df["betrouwbaarheid"].isin(["Goud", "Zilver"])
        )
    else:
        valid_registry = df["bag_gevalideerd"].apply(is_bag_gevalideerd)

    valid_mask = valid_registry & (
        (df["bag_match_type"] == "within")
        | ((df["bag_match_type"] == "nearest") & (df["bag_afstand_meter"] <= 50.0))
    )

    return df[df["is_openbaar"] & valid_mask].copy()


# %% Stap 5: workflow uitvoeren
def main():
    sport = pd.read_csv(INPUT_CSV, dtype={"pand_id": "string"})

    print(f"Aantal sportvoorzieningen totaal: {len(sport)}")

    groot_sport = filter_sportvoorzieningen(sport)

    groot_sport.to_csv(OUTPUT_CSV, index=False)

    sport_gpkg = gpd.read_file(INPUT_GPKG, layer="sport")
    groot_sport_gpkg = filter_sportvoorzieningen(sport_gpkg, csv_df=sport)
    groot_sport_gpkg.to_file(
        OUTPUT_GPKG,
        layer="sport_groot",
        driver="GPKG",
    )

    print("\nSelectie sportvoorzieningen:")
    print(f"Aantal geselecteerd: {len(groot_sport)}")
    print(f"Percentage behouden: {len(groot_sport)/len(sport)*100:.1f}%")
    
    if "leisure" in groot_sport.columns:
        print("\nVerdeling per leisure type:")
        print(groot_sport["leisure"].fillna("(leeg)").value_counts().to_string())

    print(f"\nOpgeslagen: {OUTPUT_CSV}")
    print(f"Opgeslagen: {OUTPUT_GPKG}")


if __name__ == "__main__":
    main()
