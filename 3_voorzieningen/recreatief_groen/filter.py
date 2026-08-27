# %% Stap 1: imports
from pathlib import Path
import geopandas as gpd
import pandas as pd

# %% Stap 2: paden
BASE_DIR = Path(__file__).resolve().parents[2]
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"
PROCESSED_DIR = VOORZIENINGEN_DIR / "processed"
RECREATIEF_GROEN_PROCESSED_DIR = PROCESSED_DIR / "recreatief_groen"
INPUT_CSV = RECREATIEF_GROEN_PROCESSED_DIR / "recreatief_groen.csv"
INPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "recreatief_groen"
    / "recreatief_groen.gpkg"
)
OUTPUT_CSV = RECREATIEF_GROEN_PROCESSED_DIR / "recreatief_groen_groot.csv"
OUTPUT_GPKG = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "3_voorzieningen"
    / "recreatief_groen"
    / "recreatief_groen_groot.gpkg"
)


# %% Stap 3: instellingen
# Uitsluiten van privé-eigendom en niet-toegankelijk groen
UITSLUITEN_NAAM_BEVAT = [
    "privé",
    "private",
    "achtertuin",
    "volkstuinvereniging", # volkstuinen zijn vaak afgesloten percelen voor individuele huurders
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


def is_geschikt_groen(row):
    access = normaliseer_tekst(row.get("access"))
    if access in ["private", "no", "members_only"]:
        return False

    private = normaliseer_tekst(row.get("private"))
    if private in ["yes", "true"]:
        return False

    garden_type = normaliseer_tekst(row.get("garden:type")) or normaliseer_tekst(
        row.get("garden_type")
    )
    if garden_type in ["private", "residential"]:
        return False

    name = normaliseer_tekst(row.get("name"))
    for uitsluiten in UITSLUITEN_NAAM_BEVAT:
        if uitsluiten in name:
            return False

    match_type = normaliseer_tekst(row.get("match_type"))

    if match_type == "leisure_garden" and name == "":
        return False

    geldige_types = {
        "leisure_park",
        "landuse_recreation_ground",
        "leisure_garden",
        "leisure_playground",
        "boundary_national_park",
        "leisure_nature_reserve"
    }

    if match_type in geldige_types:
        return True

    return False


def filter_recreatief_groen(df, csv_df=None):
    df = df.copy()
    
    # Merge validation columns if csv_df is provided
    id_kolom = "recreatief_groen_id"
    if csv_df is not None and id_kolom in df.columns and id_kolom in csv_df.columns:
        geom = df.geometry
        df[id_kolom] = df[id_kolom].astype(str)
        csv_df_temp = csv_df.copy()
        csv_df_temp[id_kolom] = csv_df_temp[id_kolom].astype(str)
        cols_to_use = csv_df_temp.columns.difference(df.columns).tolist() + [id_kolom]
        df = df.merge(csv_df_temp[cols_to_use], on=id_kolom, how="left")
        df.geometry = geom

    df["is_openbaar"] = df.apply(
        is_geschikt_groen,
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
    groen = pd.read_csv(INPUT_CSV, dtype={"pand_id": "string"})

    print(f"Aantal recreatief groen features totaal: {len(groen)}")

    groot_groen = filter_recreatief_groen(groen)

    groot_groen.to_csv(OUTPUT_CSV, index=False)

    groen_gpkg = gpd.read_file(INPUT_GPKG, layer="recreatief_groen")
    groot_groen_gpkg = filter_recreatief_groen(groen_gpkg, csv_df=groen)
    groot_groen_gpkg.to_file(
        OUTPUT_GPKG,
        layer="recreatief_groen_groot",
        driver="GPKG",
    )

    print("\nSelectie recreatief groen:")
    print(f"Aantal geselecteerd: {len(groot_groen)}")
    print(f"Percentage behouden: {len(groot_groen)/len(groen)*100:.1f}%")
    
    if "match_type" in groot_groen.columns:
        print("\nVerdeling per type:")
        print(groot_groen["match_type"].fillna("(leeg)").value_counts().to_string())

    print(f"\nOpgeslagen: {OUTPUT_CSV}")
    print(f"Opgeslagen: {OUTPUT_GPKG}")


if __name__ == "__main__":
    main()
