from pathlib import Path
import re
from typing import Any

import geopandas as gpd
import pandas as pd
import requests


# %% Stap 1: Instellingen
PROJECT_DIR = Path(__file__).resolve().parents[1]

GEBIED_URL = "https://opendata.rdw.nl/resource/adw6-9hsg.json"
IN_UITGANG_URL = "https://opendata.rdw.nl/resource/c653-u9z2.json"
GPS_URL = "https://opendata.rdw.nl/resource/k3dr-ge3w.json"
PARKEERADRES_URL = "https://opendata.rdw.nl/resource/ygq4-hh5q.json"

# BAG is de basislaag; daarom wordt dezelfde eindjaarspeildatum gehanteerd
# als bij de BAG-pandselectie.
PEILDATUM = pd.Timestamp("2026-12-31")
LIMIT = 50000
CRS_WGS84 = "EPSG:4326"

BAG_PANDEN_PUNTEN_PAD = (
    PROJECT_DIR
    / "0_layers"
    / "processed"
    / "2_bag"
    / "bag_panden.gpkg"
)

BAG_PANDEN_POLYGONEN_PAD = (
    PROJECT_DIR
    / "2_bag"
    / "bag_frl_xml"
    / "per_jaar"
    / "pnd_fryslan_2026.geojson"
)

BAG_ADRESSEN_PAD = (
    PROJECT_DIR
    / "2_bag"
    / "bag_frl_xml"
    / "vbo_pand_koppeling.csv"
)

output_map = (
    PROJECT_DIR
    / "0_layers"
    / "processed"
    / "4_netwerk"
    / "verkeerstypen"
)

rdw_processed_map = PROJECT_DIR / "4_netwerk" / "processed" / "RDW"

output_pad = output_map / "parkeergarage.geojson"


# %% Stap 2: Functies
def ophalen(naam: str, url: str) -> pd.DataFrame:
    print(f"Start ophalen: {naam}")

    records = []
    offset = 0

    while True:
        response = requests.get(
            url,
            params={
                "$limit": LIMIT,
                "$offset": offset,
            },
            timeout=60,
        )
        response.raise_for_status()

        batch = response.json()
        if not batch:
            break

        records.extend(batch)
        print(f"  opgehaald: {len(records):,}")

        if len(batch) < LIMIT:
            break

        offset += LIMIT

    df = pd.DataFrame(records)
    print(f"Gereed: {naam} ({len(df):,} records)")

    return df


def filter_geldig(df: pd.DataFrame, datumkolom: str) -> pd.DataFrame:
    if datumkolom not in df.columns:
        return df.copy()

    df = df.copy()
    df[datumkolom] = pd.to_datetime(
        df[datumkolom],
        errors="coerce",
        format="mixed",
    )

    return df[
        df[datumkolom].isna()
        | (df[datumkolom] >= PEILDATUM)
    ].copy()


def normaliseer_tekst(value: Any) -> str:
    if pd.isna(value):
        return ""

    value = str(value).strip().lower()
    return re.sub(r"\s+", " ", value)


def normaliseer_postcode(value: Any) -> str:
    if pd.isna(value):
        return ""

    return re.sub(r"\s+", "", str(value).upper())


def splits_huisnummer(value: Any) -> tuple[str, str, str]:
    if pd.isna(value):
        return "", "", ""

    match = re.match(r"^\s*(\d+)\s*([A-Za-z]?)\s*(.*)\s*$", str(value))
    if not match:
        return normaliseer_tekst(value), "", ""

    huisnummer = match.group(1)
    huisletter = match.group(2).upper()
    toevoeging = normaliseer_tekst(match.group(3))

    return huisnummer, huisletter, toevoeging


def voeg_adressleutel_toe(
    df: pd.DataFrame,
    straatkolom: str,
    huisnummerkolom: str,
    postcodekolom: str,
    prefix: str,
) -> pd.DataFrame:
    df = df.copy()
    huisnummerdelen = df[huisnummerkolom].apply(splits_huisnummer)

    df[f"{prefix}_straat_key"] = df[straatkolom].apply(normaliseer_tekst)
    df[f"{prefix}_huisnummer_key"] = huisnummerdelen.apply(lambda delen: delen[0])
    df[f"{prefix}_huisletter_key"] = huisnummerdelen.apply(lambda delen: delen[1])
    df[f"{prefix}_toevoeging_key"] = huisnummerdelen.apply(lambda delen: delen[2])
    df[f"{prefix}_postcode_key"] = df[postcodekolom].apply(normaliseer_postcode)

    df[f"{prefix}_adres_key"] = (
        df[f"{prefix}_postcode_key"]
        + "|"
        + df[f"{prefix}_huisnummer_key"]
        + "|"
        + df[f"{prefix}_huisletter_key"]
        + "|"
        + df[f"{prefix}_toevoeging_key"]
        + "|"
        + df[f"{prefix}_straat_key"]
    )

    return df


def normaliseer_pand_id(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(16)
    )


def maak_puntgeometrie(df: pd.DataFrame) -> list[Any]:
    punt_geometrie = gpd.points_from_xy(
        df["longitude"],
        df["latitude"],
        crs=CRS_WGS84,
    )

    geldige_punten = df["longitude"].notna() & df["latitude"].notna()

    return [
        punt if geldig else None
        for punt, geldig in zip(punt_geometrie, geldige_punten)
    ]


def controleer_kolommen(
    df: pd.DataFrame,
    naam: str,
    verplichte_kolommen: list[str],
) -> None:
    ontbrekend = sorted(set(verplichte_kolommen) - set(df.columns))
    if ontbrekend:
        raise ValueError(f"Kolommen ontbreken in {naam}: {ontbrekend}")


def main() -> None:
    # %% Stap 3: RDW-data ophalen
    gebied_df = ophalen("GEBIED", GEBIED_URL)
    in_uitgang_df = ophalen("IN-UITGANG", IN_UITGANG_URL)
    gps_df = ophalen("GPS-COORDINATEN PARKEERLOCATIE", GPS_URL)
    parkeeradres_df = ophalen("PARKEERADRES", PARKEERADRES_URL)

    print("\nAlle datasets opgehaald.")

    # %% Stap 4: Kolommen controleren
    controleer_kolommen(
        gebied_df,
        "gebied",
        ["areamanagerid", "areaid", "areadesc", "startdatearea", "enddatearea"],
    )
    controleer_kolommen(
        in_uitgang_df,
        "in_uitgang",
        [
            "entranceexitid",
            "areamanagerid",
            "areaid",
            "startdateentranceorexit",
            "alias",
            "pedestrianentrance",
            "pedestrianexit",
            "vehicleentrance",
            "vehicleexit",
            "enddateentranceorexit",
        ],
    )
    controleer_kolommen(
        gps_df,
        "gps",
        [
            "locationreferencetype",
            "locationreference",
            "startdatelocation",
            "longitude",
            "latitude",
            "enddatelocation",
        ],
    )
    controleer_kolommen(
        parkeeradres_df,
        "parkeeradres",
        [
            "parkingaddressreferencetype",
            "parkingaddressreference",
            "parkingaddresstype",
            "streetname",
            "housenumber",
            "zipcode",
            "place",
            "province",
            "country",
            "telephonenumber",
            "emailaddress",
            "faxnumber",
        ],
    )

    print("gebied:", gebied_df.columns.tolist())
    print("in_uitgang:", in_uitgang_df.columns.tolist())
    print("gps:", gps_df.columns.tolist())
    print("parkeeradres:", parkeeradres_df.columns.tolist())

    # %% Stap 5: Alleen relevante kolommen selecteren
    gebied_df = gebied_df[
        [
            "areamanagerid",
            "areaid",
            "areadesc",
            "startdatearea",
            "enddatearea",
        ]
    ].copy()

    in_uitgang_df = in_uitgang_df[
        [
            "entranceexitid",
            "areamanagerid",
            "areaid",
            "startdateentranceorexit",
            "alias",
            "pedestrianentrance",
            "pedestrianexit",
            "vehicleentrance",
            "vehicleexit",
            "enddateentranceorexit",
        ]
    ].copy()

    gps_df = gps_df[
        [
            "locationreferencetype",
            "locationreference",
            "startdatelocation",
            "longitude",
            "latitude",
            "enddatelocation",
        ]
    ].copy()

    parkeeradres_df = parkeeradres_df[
        [
            "parkingaddressreferencetype",
            "parkingaddressreference",
            "parkingaddresstype",
            "streetname",
            "housenumber",
            "zipcode",
            "place",
            "province",
            "country",
            "telephonenumber",
            "emailaddress",
            "faxnumber",
        ]
    ].copy()


    # %% Stap 6: Geldige records filteren
    gebied_df = filter_geldig(gebied_df, "enddatearea")
    in_uitgang_df = filter_geldig(in_uitgang_df, "enddateentranceorexit")
    gps_df = filter_geldig(gps_df, "enddatelocation")

    print("gebieden geldig:", len(gebied_df))
    print("in-uitgangen geldig:", len(in_uitgang_df))
    print("gps-locaties geldig:", len(gps_df))


    # %% Stap 7: Parkeergarages selecteren
    garage_regex = "garage|parkeergarage|parking"

    garages_df = gebied_df[
        gebied_df["areadesc"]
        .fillna("")
        .str.lower()
        .str.contains(garage_regex, regex=True)
    ].copy()

    print("gebieden met garage in areadesc:", len(garages_df))


    # %% Stap 8: In-/uitgangen, GPS en adres koppelen
    garage_locaties_df = in_uitgang_df.merge(
        garages_df,
        on=["areamanagerid", "areaid"],
        how="inner",
        suffixes=("_inuitgang", "_gebied"),
    )

    print("garage in-/uitgangen:", len(garage_locaties_df))

    gps_io_df = gps_df[gps_df["locationreferencetype"] == "I-O"].copy()
    parkeeradres_io_df = parkeeradres_df[
        parkeeradres_df["parkingaddressreferencetype"] == "I-O"
    ].copy()

    print("gps I-O locaties:", len(gps_io_df))
    print("parkeeradressen I-O:", len(parkeeradres_io_df))

    garage_locaties_df = garage_locaties_df.merge(
        gps_io_df,
        left_on="entranceexitid",
        right_on="locationreference",
        how="left",
    )

    garage_locaties_df = garage_locaties_df.merge(
        parkeeradres_io_df,
        left_on="entranceexitid",
        right_on="parkingaddressreference",
        how="left",
    )

    print("garage in-/uitgangen met GPS/adres:", len(garage_locaties_df))


    # %% Stap 9: Garagepunten voorbereiden
    garage_locaties_df["longitude"] = pd.to_numeric(
        garage_locaties_df["longitude"],
        errors="coerce",
    )
    garage_locaties_df["latitude"] = pd.to_numeric(
        garage_locaties_df["latitude"],
        errors="coerce",
    )

    garage_locaties_df["garage_record_id"] = range(len(garage_locaties_df))

    garage_locaties_df = voeg_adressleutel_toe(
        garage_locaties_df,
        "streetname",
        "housenumber",
        "zipcode",
        "rdw",
    )

    garages_gdf = gpd.GeoDataFrame(
        garage_locaties_df,
        geometry=maak_puntgeometrie(garage_locaties_df),
        crs=CRS_WGS84,
    )

    print("met geldige coördinaten:", garages_gdf.geometry.notna().sum())


    # %% Stap 10: BAG-panden lezen
    print("Lees BAG-pandpunten uit 0_layers")

    bag_pandpunten = gpd.read_file(
        BAG_PANDEN_PUNTEN_PAD,
        layer="bag_panden",
    )
    bag_pandpunten["pand_id"] = normaliseer_pand_id(bag_pandpunten["pand_id"])

    print("Lees BAG-pandpolygonen voor punt-in-pand-validatie")

    bag_panden = gpd.read_file(BAG_PANDEN_POLYGONEN_PAD)
    bag_panden["pand_id"] = normaliseer_pand_id(bag_panden["pand_id"])
    bag_panden = bag_panden[bag_panden.geometry.notna()].copy()
    bag_panden = bag_panden[~bag_panden.geometry.is_empty].copy()
    bag_panden = bag_panden[bag_panden["pand_status"] == "Pand in gebruik"].copy()

    bag_panden = bag_panden.merge(
        bag_pandpunten.drop(columns="geometry"),
        on="pand_id",
        how="left",
        suffixes=("", "_bag"),
    )
    bag_panden = bag_panden.to_crs(CRS_WGS84)

    print("BAG-panden:", len(bag_panden))


    # %% Stap 11: BAG-adressen lezen
    print("Lees BAG-adressen voor adresvalidatie")

    bag_adressen = pd.read_csv(
        BAG_ADRESSEN_PAD,
        dtype="string",
    )
    bag_adressen["pand_id"] = normaliseer_pand_id(bag_adressen["pand_id"])
    bag_adressen = filter_geldig(bag_adressen, "vbo_eind_geldigheid")
    bag_adressen = voeg_adressleutel_toe(
        bag_adressen,
        "openbare_ruimte_naam",
        "huisnummer",
        "postcode",
        "bag",
    )

    bag_adressen = bag_adressen[
        bag_adressen["bag_postcode_key"].ne("")
        & bag_adressen["bag_huisnummer_key"].ne("")
    ].copy()

    bag_adressen = (
        bag_adressen
        .drop_duplicates(["bag_adres_key", "pand_id"])
        .groupby("bag_adres_key", as_index=False)
        .agg(
            bag_adres_pand_ids=("pand_id", lambda waarden: ";".join(sorted(set(waarden)))),
            bag_adres_pand_aantal=("pand_id", "nunique"),
            bag_openbare_ruimte_naam=("openbare_ruimte_naam", "first"),
            bag_huisnummer=("huisnummer", "first"),
            bag_huisletter=("huisletter", "first"),
            bag_huisnummertoevoeging=("huisnummertoevoeging", "first"),
            bag_postcode=("postcode", "first"),
            bag_woonplaats_naam=("woonplaats_naam", "first"),
        )
    )

    bag_adressen["bag_adres_pand_id"] = (
        bag_adressen["bag_adres_pand_ids"]
        .str.split(";")
        .str[0]
    )

    print("BAG-adressen:", len(bag_adressen))


    # %% Stap 12: BAG-adres koppelen
    garages_gdf = garages_gdf.merge(
        bag_adressen,
        left_on="rdw_adres_key",
        right_on="bag_adres_key",
        how="left",
    )

    print("garagepunten met BAG-adresmatch:", garages_gdf["bag_adres_pand_id"].notna().sum())


    # %% Stap 13: Punt-in-pand koppelen
    garages_met_punt = garages_gdf[garages_gdf.geometry.notna()].copy()

    garages_met_punt = gpd.sjoin(
        garages_met_punt,
        bag_panden[["pand_id", "geometry"]],
        how="left",
        predicate="within",
    )
    garages_met_punt = garages_met_punt.drop(columns=["index_right"], errors="ignore")
    garages_met_punt = garages_met_punt.rename(columns={"pand_id": "punt_pand_id"})
    garages_met_punt = garages_met_punt.drop_duplicates("garage_record_id", keep="first")
    garages_met_punt["punt_valt_in_pand"] = garages_met_punt["punt_pand_id"].notna()

    punt_koppeling = garages_met_punt[
        [
            "garage_record_id",
            "punt_pand_id",
            "punt_valt_in_pand",
        ]
    ].copy()

    garages_gdf = garages_gdf.merge(
        punt_koppeling,
        on="garage_record_id",
        how="left",
    )
    garages_gdf["punt_valt_in_pand"] = garages_gdf["punt_valt_in_pand"].eq(True)

    print("garagepunten binnen BAG-pand:", garages_gdf["punt_valt_in_pand"].sum())


    # %% Stap 14: Match kiezen
    garages_gdf["heeft_punt"] = garages_gdf.geometry.notna()
    garages_gdf["bag_adres_match"] = garages_gdf["bag_adres_pand_id"].notna()
    garages_gdf["bag_adres_valideert_punt"] = pd.NA

    met_punt_en_adres = (
        garages_gdf["punt_pand_id"].notna()
        & garages_gdf["bag_adres_pand_ids"].notna()
    )

    garages_gdf.loc[met_punt_en_adres, "bag_adres_valideert_punt"] = garages_gdf.loc[
        met_punt_en_adres
    ].apply(
        lambda row: row["punt_pand_id"] in row["bag_adres_pand_ids"].split(";"),
        axis=1,
    )

    garages_gdf["match_pand_id"] = garages_gdf["punt_pand_id"]
    garages_gdf["bag_match_type"] = "geen_match"

    garages_gdf.loc[
        garages_gdf["punt_pand_id"].notna(),
        "bag_match_type",
    ] = "punt_binnen_pand"

    adres_fallback = (
        garages_gdf["match_pand_id"].isna()
        & garages_gdf["bag_adres_pand_id"].notna()
    )

    garages_gdf.loc[adres_fallback, "match_pand_id"] = garages_gdf.loc[
        adres_fallback,
        "bag_adres_pand_id",
    ]

    garages_gdf.loc[
        adres_fallback & garages_gdf["heeft_punt"],
        "bag_match_type",
    ] = "adres_fallback_punt_niet_in_pand"

    garages_gdf.loc[
        adres_fallback & ~garages_gdf["heeft_punt"],
        "bag_match_type",
    ] = "adres_fallback_geen_punt"

    garages_gdf["bag_gevalideerd"] = garages_gdf["match_pand_id"].notna()

    print("BAG match type:")
    print(garages_gdf["bag_match_type"].value_counts(dropna=False).to_string())


    # %% Stap 15: Garagepanden wegschrijven
    output_map.mkdir(parents=True, exist_ok=True)
    rdw_processed_map.mkdir(parents=True, exist_ok=True)

    garage_panden = garages_gdf[
        garages_gdf["match_pand_id"].notna()
    ].drop(columns="geometry")

    garage_panden = garage_panden.merge(
        bag_panden.rename(columns={"pand_id": "match_pand_id"}),
        on="match_pand_id",
        how="left",
        suffixes=("", "_pand"),
    )

    garage_panden = gpd.GeoDataFrame(
        garage_panden,
        geometry="geometry",
        crs=CRS_WGS84,
    )

    garage_panden = garage_panden.drop(
        columns=["rdw_adres_key", "bag_adres_key"],
        errors="ignore",
    )

    garage_panden.to_file(
        output_pad,
        driver="GeoJSON",
    )

    print(f"{len(garage_panden)} garagepanden opgeslagen in {output_pad}")



if __name__ == "__main__":
    main()
