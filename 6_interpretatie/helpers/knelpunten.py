"""Maak per buurt de interpretatielaag met onvoldoende modaliteiten."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from . import tekorten
from .invoer import lees_buurten, normaliseer_gemeentecode, schrijf_csv, schrijf_gpkg
from .instellingen import OUTPUT_DIR, output_voorzieningnaam


KNELPUNT_STIJL = {
    "0_modaliteiten_onvoldoende": ("#2ca25f", "#176c3c"),
    "1_modaliteit_onvoldoende": ("#ffd84d", "#9b7b1c"),
    "2_modaliteiten_onvoldoende": ("#fdae61", "#a85f1d"),
    "3_modaliteiten_onvoldoende": ("#f46d43", "#9f3d25"),
    "4_modaliteiten_onvoldoende": ("#d73027", "#7f1d1d"),
    "5_modaliteiten_onvoldoende": ("#7f0000", "#4d0000"),
    "datacontrole_uitvoeren": ("#79706e", "#4f4a48"),
}
STANDAARD_STIJL = ("#79706e", "#4f4a48")


def aantal_modaliteiten_categorie(aantal) -> str:
    if pd.isna(aantal):
        return "datacontrole_uitvoeren"
    aantal = int(aantal)
    if aantal == 1:
        return "1_modaliteit_onvoldoende"
    return f"{aantal}_modaliteiten_onvoldoende"


def aantal_modaliteiten_label(aantal) -> str:
    if pd.isna(aantal):
        return "Geen woningen"
    aantal = int(aantal)
    if aantal == 0:
        return "Alle modaliteiten voldoen"
    if aantal == 1:
        return "1 modaliteit onvoldoende"
    if aantal == 5:
        return "Geen modaliteit voldoet"
    return f"{aantal} modaliteiten onvoldoende"


def voeg_knelpuntkleuren_toe(kaart: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    kaart = kaart.copy()
    categorie = kaart["aantal_modaliteiten_onvoldoende"].apply(aantal_modaliteiten_categorie)
    kaart["aantal_modaliteiten_label"] = kaart[
        "aantal_modaliteiten_onvoldoende"
    ].apply(aantal_modaliteiten_label)
    kaart["legenda_label"] = kaart["aantal_modaliteiten_label"]
    stijl = categorie.map(KNELPUNT_STIJL)
    kaart["fill"] = stijl.map(
        lambda waarde: waarde[0] if isinstance(waarde, tuple) else STANDAARD_STIJL[0]
    )
    kaart["stroke"] = stijl.map(
        lambda waarde: waarde[1] if isinstance(waarde, tuple) else STANDAARD_STIJL[1]
    )
    kaart["fill-opacity"] = 0.72
    kaart["stroke-width"] = 0.6
    return kaart


def hernoem_percentagekolommen(df: pd.DataFrame) -> pd.DataFrame:
    hernoem = {
        "percentage_binnen_norm_lopen": "pct_lopen",
        "percentage_binnen_norm_fiets": "pct_fiets",
        "percentage_binnen_norm_auto": "pct_auto",
        "percentage_binnen_norm_ov_lopen": "pct_ov_lopen",
        "percentage_binnen_norm_ov_fiets": "pct_ov_fiets",
        "beste_percentage_binnen_norm": "beste_pct",
        "slechtste_percentage_binnen_norm": "slechtste_pct",
    }
    return df.rename(columns=hernoem)


def compacte_diagnosekolommen(df: pd.DataFrame) -> pd.DataFrame:
    df = hernoem_percentagekolommen(df)
    kolommen = [
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
        "panden_aantal",
        "pct_lopen",
        "pct_fiets",
        "pct_auto",
        "pct_ov_lopen",
        "pct_ov_fiets",
        "beste_modus",
        "beste_pct",
        "slechtste_modus",
        "slechtste_pct",
        "aantal_modaliteiten_onvoldoende",
        "aantal_modaliteiten_label",
        "modaliteiten_onvoldoende",
        "ernstklasse",
    ]
    kolommen = [kolom for kolom in kolommen if kolom in df.columns]
    return df[kolommen].copy()


def beperk_kaartkolommen(kaart: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    kaart = hernoem_percentagekolommen(kaart)
    kolommen = [
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
        "panden_aantal",
        "pct_lopen",
        "pct_fiets",
        "pct_auto",
        "pct_ov_lopen",
        "pct_ov_fiets",
        "beste_modus",
        "beste_pct",
        "slechtste_modus",
        "slechtste_pct",
        "aantal_modaliteiten_onvoldoende",
        "legenda_label",
        "aantal_modaliteiten_label",
        "modaliteiten_onvoldoende",
        "ernstklasse",
        "fill",
        "stroke",
        "fill-opacity",
        "stroke-width",
        "geometry",
    ]
    kolommen = [kolom for kolom in kolommen if kolom in kaart.columns]
    return kaart[kolommen].copy()


def normaliseer_merge_sleutels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for kolom in ["buurtcode", "buurtnaam", "gemeentenaam"]:
        if kolom in df.columns:
            df[kolom] = df[kolom].astype(str).str.strip()
    if "gemeentecode" in df.columns:
        df["gemeentecode"] = normaliseer_gemeentecode(df["gemeentecode"])
    return df


def main(diagnose: pd.DataFrame | None = None) -> None:
    if diagnose is None:
        diagnose = tekorten.maak_tekortdiagnose()
    else:
        diagnose = diagnose.copy()

    naam = output_voorzieningnaam()
    bestandsnaam = f"{naam}_modaliteiten_onvoldoende"

    csv_pad = OUTPUT_DIR / "knelpunten" / f"{bestandsnaam}.csv"
    schrijf_csv(compacte_diagnosekolommen(diagnose), csv_pad, index=False)
    print(f"Opgeslagen: {csv_pad}")

    buurten = normaliseer_merge_sleutels(lees_buurten())
    diagnose = normaliseer_merge_sleutels(diagnose)
    kaart = buurten.merge(
        diagnose,
        on=["buurtcode", "buurtnaam", "gemeentecode", "gemeentenaam"],
        how="left",
    )
    kaart = voeg_knelpuntkleuren_toe(kaart)
    kaart = beperk_kaartkolommen(kaart)
    schrijf_gpkg(
        kaart,
        OUTPUT_DIR / "knelpunten" / f"{bestandsnaam}.gpkg",
        bestandsnaam,
    )


if __name__ == "__main__":
    main()
