"""Invoerhelpers voor DUS-analyses per voorziening."""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd

from .instellingen import (
    BASE_DIR,
    BUURT_CSV_DIR,
    BUURTEN_PAD,
    CRS_RD,
    CRS_WGS84,
    LAYERS_DIR,
    MODI,
    OUTPUT_DIR,
    VOORZIENINGEN_PAD,
    voorziening,
)


def normaliseer_id(waarde) -> str:
    if pd.isna(waarde):
        return ""
    tekst = str(waarde).strip()
    if tekst.endswith(".0"):
        tekst = tekst[:-2]
    return tekst


def controleer_kolommen(
    df: pd.DataFrame,
    verplichte_kolommen: list[str],
    bron: str,
) -> None:
    ontbrekend = [kolom for kolom in verplichte_kolommen if kolom not in df.columns]
    if ontbrekend:
        raise ValueError(
            f"Ontbrekende kolommen in {bron}: {', '.join(ontbrekend)}"
        )


def niet_lege_tekst(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def normaliseer_gemeentecode(serie: pd.Series) -> pd.Series:
    return (
        serie.astype(str)
        .str.strip()
        .str.upper()
        .str.removeprefix("GM")
        .str.zfill(4)
    )


def voorziening_label(row) -> str:
    if voorziening() == "onderwijs":
        kolommen = [
            "VESTIGINGSNAAM",
            "INSTELLINGSNAAM",
            "naam",
            "name",
            "operator",
            "short_name",
        ]
    else:
        kolommen = [
            f"{voorziening()}_naam",
            "stop_names",
            "name",
            "brand",
            "operator",
            "short_name",
        ]
    for kolom in kolommen:
        waarde = row.get(kolom)
        if pd.notna(waarde) and str(waarde).strip():
            return str(waarde).strip()
    return f"{voorziening().capitalize()} {row.get(f'{voorziening()}_id', row.name)}"


@lru_cache(maxsize=1)
def bag_woonplaatsen_per_pand() -> pd.Series:
    pad = BASE_DIR / "2_bag" / "bag_frl_xml" / "vbo_pand_koppeling.csv"
    if not pad.exists():
        return pd.Series(dtype="object")

    koppeling = pd.read_csv(
        pad,
        usecols=["pand_id", "woonplaats_naam"],
        dtype={"pand_id": "string", "woonplaats_naam": "string"},
    )
    koppeling["pand_id"] = koppeling["pand_id"].apply(normaliseer_id)
    koppeling["woonplaats_naam"] = niet_lege_tekst(koppeling["woonplaats_naam"])
    koppeling = koppeling[
        koppeling["pand_id"].ne("") & koppeling["woonplaats_naam"].ne("")
    ].copy()
    if koppeling.empty:
        return pd.Series(dtype="object")
    return koppeling.drop_duplicates("pand_id").set_index("pand_id")[
        "woonplaats_naam"
    ]


def plaats_uit_bag(gdf: gpd.GeoDataFrame) -> pd.Series:
    if "pand_id" not in gdf.columns:
        return pd.Series("", index=gdf.index)
    lookup = bag_woonplaatsen_per_pand()
    if lookup.empty:
        return pd.Series("", index=gdf.index)
    pand_id = gdf["pand_id"].apply(normaliseer_id)
    return pand_id.map(lookup).fillna("").astype(str).str.strip()


def plaats_uit_kolommen(gdf: gpd.GeoDataFrame, kolommen: list[str]) -> pd.Series:
    plaats = pd.Series("", index=gdf.index)
    for kolom in kolommen:
        if kolom not in gdf.columns:
            continue
        kandidaat = niet_lege_tekst(gdf[kolom])
        plaats = plaats.where(plaats.ne(""), kandidaat)
    return plaats


def _adres_uit_bag(gdf: gpd.GeoDataFrame) -> pd.Series | None:
    if "adres_bag" in gdf.columns:
        return gdf["adres_bag"].fillna("").astype(str).str.strip()
    return None


def _adres_uit_kolommen(gdf: gpd.GeoDataFrame, kolommen: list[str]) -> pd.Series:
    adresdelen = [
        gdf[kolom].fillna("").astype(str).str.strip()
        for kolom in kolommen
        if kolom in gdf.columns
    ]
    if not adresdelen:
        return pd.Series("", index=gdf.index)
    adres = adresdelen[0]
    for deel in adresdelen[1:]:
        adres = (adres + " " + deel).str.strip()
    return adres.str.replace(r"\s+", " ", regex=True).str.strip()


def voeg_plaats_toe(voorzieningen: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    naam = voorziening()
    plaats_kolom = f"{naam}_plaats"
    plaats = plaats_uit_bag(voorzieningen)

    if naam == "onderwijs":
        fallback_kolommen = [
            "bag_gekozen_woonplaats",
            "woonplaats_naam",
            "PLAATSNAAM",
            "bag_basis_woonplaats_naam",
        ]
    elif naam == "ov":
        fallback_kolommen = ["ov_adres", "officiele_halte_naam", "stop_names", "naam"]
    else:
        fallback_kolommen = [
            "addr:city",
            "woonplaats_naam",
            "bag_gekozen_woonplaats",
            "PLAATSNAAM",
            "name",
            "naam",
        ]

    fallback = plaats_uit_kolommen(voorzieningen, fallback_kolommen)
    plaats = plaats.where(plaats.ne(""), fallback)
    voorzieningen[plaats_kolom] = plaats.fillna("").astype(str).str.strip()
    return voorzieningen


@lru_cache(maxsize=1)
def lees_voorzieningen() -> gpd.GeoDataFrame:
    voorzieningen = gpd.read_file(VOORZIENINGEN_PAD).to_crs(CRS_RD)
    voorzieningen = voorzieningen[voorzieningen.geometry.notna()].copy()
    voorzieningen = voorzieningen[~voorzieningen.geometry.is_empty].copy()
    voorzieningen["pand_geometry"] = voorzieningen.geometry
    niet_punt = ~voorzieningen.geometry.geom_type.isin(["Point", "MultiPoint"])
    if niet_punt.any():
        voorzieningen.loc[niet_punt, "geometry"] = (
            voorzieningen.loc[niet_punt, "geometry"].representative_point()
        )

    id_kolom = f"{voorziening()}_id"
    naam_kolom = f"{voorziening()}_naam"
    adres_kolom = f"{voorziening()}_adres"

    if id_kolom not in voorzieningen.columns:
        voorzieningen[id_kolom] = range(1, len(voorzieningen) + 1)
    controleer_kolommen(voorzieningen, [id_kolom, "geometry"], str(VOORZIENINGEN_PAD))
    voorzieningen[id_kolom] = voorzieningen[id_kolom].apply(normaliseer_id)
    voorzieningen[naam_kolom] = voorzieningen.apply(voorziening_label, axis=1)

    bag_adres = _adres_uit_bag(voorzieningen)
    if bag_adres is not None:
        voorzieningen[adres_kolom] = bag_adres
    elif voorziening() == "onderwijs":
        voorzieningen[adres_kolom] = _adres_uit_kolommen(
            voorzieningen,
            [
                "bag_basis_straatnaam",
                "bag_basis_huisnummer",
                "bag_basis_woonplaats_naam",
                "STRAATNAAM",
                "HUISNUMMER-TOEVOEGING",
                "PLAATSNAAM",
            ],
        )
    else:
        voorzieningen[adres_kolom] = _adres_uit_kolommen(
            voorzieningen,
            ["addr:street", "addr:housenumber", "addr:city"],
        )
    dubbel = voorzieningen[id_kolom].duplicated(keep=False)
    if dubbel.any():
        aantal_ids = voorzieningen.loc[dubbel, id_kolom].nunique(dropna=False)
        aantal_records = int(dubbel.sum())
        print(
            f"Let op: {aantal_records} voorzieningenrecords hebben dubbele {id_kolom} "
            f"({aantal_ids} ID's). Eerste record per ID wordt gebruikt voor "
            "interpretatiekoppelingen."
        )
        voorzieningen = voorzieningen.drop_duplicates(
            subset=[id_kolom],
            keep="first",
        ).copy()
    voorzieningen = voeg_plaats_toe(voorzieningen)
    return voorzieningen


@lru_cache(maxsize=1)
def lees_buurten() -> gpd.GeoDataFrame:
    buurten = gpd.read_file(BUURTEN_PAD).to_crs(CRS_RD)
    if "water" in buurten.columns:
        buurten = buurten[
            ~buurten["water"].astype(str).str.upper().str.strip().eq("JA")
        ].copy()
    return buurten


def buurt_csv_pad(modus: str):
    config = MODI[modus]
    return BUURT_CSV_DIR / config["map"] / f"buurten_{config['code']}.csv"


def _vervang_atomic(tijdelijk_pad: Path, doel_pad: Path) -> None:
    os.replace(tijdelijk_pad, doel_pad)


def schrijf_csv(df: pd.DataFrame, pad, **kwargs) -> None:
    pad = Path(pad)
    pad.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        suffix=".csv",
        prefix=f".{pad.stem}.",
        dir=pad.parent,
        delete=False,
    ) as tijdelijk:
        tijdelijk_pad = Path(tijdelijk.name)
    try:
        df.to_csv(tijdelijk_pad, **kwargs)
        _vervang_atomic(tijdelijk_pad, pad)
    finally:
        if tijdelijk_pad.exists():
            tijdelijk_pad.unlink()


def _schrijf_gpkg_bestand(gdf: gpd.GeoDataFrame, pad: Path, layer: str) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{pad.stem}.", dir=pad.parent) as tmpdir:
        tijdelijk_pad = Path(tmpdir) / pad.name
        gdf.to_file(tijdelijk_pad, layer=layer, driver="GPKG")
        _vervang_atomic(tijdelijk_pad, pad)


def schrijf_gpkg(gdf: gpd.GeoDataFrame, pad, layer: str) -> None:
    pad = Path(pad)
    try:
        relatief_pad = pad.relative_to(OUTPUT_DIR)
    except ValueError:
        _schrijf_gpkg_bestand(gdf, pad, layer)
        print(f"Opgeslagen: {pad} ({layer})")
        return

    laag_pad = LAYERS_DIR / relatief_pad
    publicatie = gdf.to_crs(CRS_WGS84) if gdf.crs is not None else gdf
    _schrijf_gpkg_bestand(publicatie, laag_pad, layer)
    print(f"Opgeslagen in 0_layers: {laag_pad} ({layer})")
