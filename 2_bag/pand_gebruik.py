"""
Maak een BAG-pandlaag met gebruiksdoelen uit VBO-relaties.

Input:
- 2_bag/bag_frl_xml/vbo_pand_koppeling.csv
- 0_layers/processed/2_bag/bag_panden.gpkg

Output:
- 2_bag/processed/bag_pand_gebruik_<jaar>.csv
- 0_layers/processed/2_bag/bag_panden.gpkg
"""

# %% Stap 1: imports en instellingen
from pathlib import Path

import geopandas as gpd
import pandas as pd

from config import BASE_DIR, ANALYSEJAAR

KOPPELTABEL_PAD = (
    BASE_DIR
    / "2_bag"
    / "bag_frl_xml"
    / "vbo_pand_koppeling.csv"
)
OUTPUT_CSV_DIR = BASE_DIR / "2_bag" / "processed"
OUTPUT_GPKG_DIR = BASE_DIR / "0_layers" / "processed" / "2_bag"

VBO_KOLOMMEN = [
    "pand_id",
    "verblijfsobject_id",
    "gebruiksdoelen",
    "verblijfsobject_status",
    "oppervlakte",
    "vbo_voorkomen_id",
    "vbo_begin_geldigheid",
    "vbo_eind_geldigheid",
]
VBO_DTYPES = {
    "pand_id": "string",
    "verblijfsobject_id": "string",
    "gebruiksdoelen": "string",
    "verblijfsobject_status": "string",
    "oppervlakte": "string",
    "vbo_voorkomen_id": "string",
    "vbo_begin_geldigheid": "string",
    "vbo_eind_geldigheid": "string",
}
VEREISTE_PAND_KOLOMMEN = ["pand_id", "geometry"]
VERRIJKINGSKOLOMMEN = [
    "vbo_aantal",
    "vbo_in_gebruik_aantal",
    "vbo_woonfunctie_aantal",
    "vbo_oppervlakte_totaal",
    "vbo_woonoppervlakte_totaal",
    "gebruiksdoelen",
    "is_woonpand",
]


# %% Stap 2: VBO-relaties lezen en voorbereiden
def bevat_woonfunctie(series: pd.Series) -> pd.Series:
    """Geef aan welke gebruiksdoelen een woonfunctie bevatten."""
    return series.fillna("").str.contains(
        "woonfunctie",
        case=False,
        regex=False,
    )


def panden_pad() -> Path:
    """Geef het pad naar de centrale BAG-pandlaag."""
    return OUTPUT_GPKG_DIR / "bag_panden.gpkg"


def controleer_kolommen(
    data: pd.DataFrame,
    kolommen: list[str],
    bron: str,
) -> None:
    """Controleer of alle vereiste kolommen aanwezig zijn."""
    ontbrekend = [kolom for kolom in kolommen if kolom not in data.columns]
    if ontbrekend:
        raise ValueError(
            f"Verplichte kolommen ontbreken in {bron}: "
            f"{', '.join(ontbrekend)}"
        )


def lees_vbo_relaties() -> pd.DataFrame:
    """Lees de VBO-pandrelaties uit de BAG-koppeltabel."""
    if not KOPPELTABEL_PAD.exists():
        raise FileNotFoundError(
            f"VBO-PND koppeltabel niet gevonden: {KOPPELTABEL_PAD}"
        )

    print(f"Lees VBO-PND relaties: {KOPPELTABEL_PAD}")
    vbo = pd.read_csv(
        KOPPELTABEL_PAD,
        usecols=VBO_KOLOMMEN,
        dtype=VBO_DTYPES,
    )
    controleer_kolommen(vbo, VBO_KOLOMMEN, str(KOPPELTABEL_PAD))
    return vbo


def normaliseer_oppervlakte(series: pd.Series) -> pd.Series:
    """Zet VBO-oppervlakten om naar numerieke waarden in m2."""
    return (
        series.astype("string")
        .str.replace(",", ".", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
    )


def selecteer_vbo_relaties_in_jaar(
    vbo: pd.DataFrame,
    jaar: int,
) -> pd.DataFrame:
    """Selecteer VBO-voorkomens die geldig zijn op de eindejaarspeildatum."""
    geselecteerd = vbo.copy()
    geselecteerd["vbo_begin_geldigheid"] = pd.to_datetime(
        geselecteerd["vbo_begin_geldigheid"],
        errors="coerce",
    )
    geselecteerd["vbo_eind_geldigheid"] = pd.to_datetime(
        geselecteerd["vbo_eind_geldigheid"],
        errors="coerce",
    )

    peildatum = pd.Timestamp(year=jaar, month=12, day=31)
    geldig = (
        geselecteerd["vbo_begin_geldigheid"].notna()
        & (geselecteerd["vbo_begin_geldigheid"] <= peildatum)
        & (
            geselecteerd["vbo_eind_geldigheid"].isna()
            | (geselecteerd["vbo_eind_geldigheid"] > peildatum)
        )
    )
    geselecteerd = geselecteerd.loc[geldig].copy()

    geselecteerd = geselecteerd.sort_values(
        [
            "pand_id",
            "verblijfsobject_id",
            "vbo_begin_geldigheid",
            "vbo_voorkomen_id",
        ],
        na_position="first",
    )

    dubbele_relaties = geselecteerd.duplicated(
        ["pand_id", "verblijfsobject_id"],
        keep="last",
    )
    if dubbele_relaties.any():
        print(
            "Dubbele geldige pand-VBO relaties verwijderd:",
            int(dubbele_relaties.sum()),
        )

    geselecteerd = geselecteerd.drop_duplicates(
        ["pand_id", "verblijfsobject_id"],
        keep="last",
    )

    if geselecteerd.empty:
        raise ValueError(f"Geen geldige VBO-relaties gevonden voor {jaar}.")

    print(f"Geldige VBO-PND relaties voor {jaar}: {len(geselecteerd)}")
    return geselecteerd


# %% Stap 3: gebruiksdoelen per pand samenvatten
def voeg_vbo_indicatoren_toe(vbo: pd.DataFrame) -> pd.DataFrame:
    """Voeg indicatoren voor actieve VBO's en woonfuncties toe."""
    resultaat = vbo.copy()
    resultaat["is_vbo_in_gebruik"] = (
        resultaat["verblijfsobject_status"]
        .fillna("")
        .str.match(r"^Verblijfsobject in gebruik", case=False)
    )
    resultaat["heeft_woonfunctie"] = bevat_woonfunctie(
        resultaat["gebruiksdoelen"]
    )
    return resultaat


def maak_gebruiksdoelen_per_pand(vbo: pd.DataFrame) -> pd.DataFrame:
    """Combineer unieke gebruiksdoelen per pand."""
    return (
        vbo.dropna(subset=["gebruiksdoelen"])
        .assign(
            gebruiksdoelen=lambda df: df["gebruiksdoelen"].str.split(";")
        )
        .explode("gebruiksdoelen")
        .assign(
            gebruiksdoelen=lambda df: df["gebruiksdoelen"].str.strip()
        )
        .loc[lambda df: df["gebruiksdoelen"].ne("")]
        .dropna(subset=["gebruiksdoelen"])
        .groupby("pand_id", as_index=False)["gebruiksdoelen"]
        .agg(lambda waarden: ";".join(sorted(set(waarden))))
    )


def maak_gebruik_samenvatting(vbo: pd.DataFrame) -> pd.DataFrame:
    """Vat de geldige VBO-relaties per pand samen."""
    vbo = vbo.copy()
    vbo["oppervlakte_m2"] = pd.to_numeric(
        normaliseer_oppervlakte(vbo["oppervlakte"]),
        errors="coerce",
    )
    vbo["woonoppervlakte_m2"] = vbo["oppervlakte_m2"].where(
        vbo["heeft_woonfunctie"],
        other=0.0,
    )

    doelen_per_pand = maak_gebruiksdoelen_per_pand(vbo)
    samenvatting = (
        vbo.groupby("pand_id")
        .agg(
            vbo_aantal=("verblijfsobject_id", "nunique"),
            vbo_in_gebruik_aantal=("is_vbo_in_gebruik", "sum"),
            vbo_woonfunctie_aantal=("heeft_woonfunctie", "sum"),
            vbo_oppervlakte_totaal=("oppervlakte_m2", "sum"),
            vbo_woonoppervlakte_totaal=("woonoppervlakte_m2", "sum"),
        )
        .reset_index()
        .merge(doelen_per_pand, on="pand_id", how="left")
    )
    samenvatting["is_woonpand"] = (
        samenvatting["vbo_woonfunctie_aantal"] > 0
    )
    samenvatting["vbo_oppervlakte_totaal"] = samenvatting[
        "vbo_oppervlakte_totaal"
    ].round(2)
    samenvatting["vbo_woonoppervlakte_totaal"] = samenvatting[
        "vbo_woonoppervlakte_totaal"
    ].round(2)
    return samenvatting


# %% Stap 4: pandcentroids verrijken
def verrijk_centroids(samenvatting: pd.DataFrame) -> gpd.GeoDataFrame:
    """Voeg de VBO-samenvatting toe aan de centrale pandlaag."""
    input_pad = panden_pad()
    if not input_pad.exists():
        raise FileNotFoundError(
            f"BAG-pandcentroids niet gevonden: {input_pad}"
        )

    print(f"Lees BAG-pandcentroids: {input_pad}")
    panden = gpd.read_file(input_pad, layer="bag_panden")
    controleer_kolommen(panden, VEREISTE_PAND_KOLOMMEN, str(input_pad))

    panden["pand_id"] = panden["pand_id"].astype("string")
    panden = panden.drop(
        columns=[
            kolom
            for kolom in VERRIJKINGSKOLOMMEN
            if kolom in panden.columns
        ],
        errors="ignore",
    )

    resultaat = panden.merge(
        samenvatting,
        on="pand_id",
        how="left",
        validate="one_to_one",
    )
    resultaat["is_woonpand"] = resultaat["is_woonpand"].fillna(False)
    for kolom in ["vbo_oppervlakte_totaal", "vbo_woonoppervlakte_totaal"]:
        if kolom in resultaat.columns:
            resultaat[kolom] = resultaat[kolom].fillna(0.0)
    return resultaat


# %% Stap 5: output schrijven
def schrijf_output(
    samenvatting: pd.DataFrame,
    panden: gpd.GeoDataFrame,
    jaar: int,
) -> None:
    """Schrijf de gebruikssamenvatting en verrijkte pandlaag."""
    OUTPUT_CSV_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_GPKG_DIR.mkdir(parents=True, exist_ok=True)

    csv_pad = OUTPUT_CSV_DIR / f"bag_pand_gebruik_{jaar}.csv"
    gpkg_pad = panden_pad()
    tijdelijk_pad = OUTPUT_GPKG_DIR / "bag_panden.tmp.gpkg"

    samenvatting.to_csv(csv_pad, index=False)
    if tijdelijk_pad.exists():
        tijdelijk_pad.unlink()

    panden.to_file(
        tijdelijk_pad,
        layer="bag_panden",
        driver="GPKG",
    )
    tijdelijk_pad.replace(gpkg_pad)

    woonpanden = int(panden["is_woonpand"].sum())
    print(f"Opgeslagen: {csv_pad}")
    print(f"Opgeslagen: {gpkg_pad}")
    print(f"Panden totaal in centroidlaag: {len(panden)}")
    print(f"Woonpanden in centroidlaag: {woonpanden}")


# %% Stap 6: workflow uitvoeren
def main() -> None:
    """Verrijk de pandlaag met VBO-gebruik voor het ingestelde jaar."""
    vbo = lees_vbo_relaties()
    vbo = selecteer_vbo_relaties_in_jaar(vbo, ANALYSEJAAR)
    vbo = voeg_vbo_indicatoren_toe(vbo)
    samenvatting = maak_gebruik_samenvatting(vbo)
    panden = verrijk_centroids(samenvatting)
    schrijf_output(samenvatting, panden, ANALYSEJAAR)


if __name__ == "__main__":
    main()
