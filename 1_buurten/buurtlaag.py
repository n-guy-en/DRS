"""Maak de basislaag met Friese buurten."""

# %% Stap 1: imports en instellingen
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "1_buurten" / "raw"
OUTPUT = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "1_buurten"
    / "buurten_basis.gpkg"
)

# %% Configuratie
# Zet JAAR op None om automatisch nieuwste Buurten_<jaar>.gpkg te gebruiken.
JAAR = None

BUURTEN_BESTAND_PATTERN = re.compile(r"^Buurten_(\d{4})\.gpkg$")

FRYSLAN_GEMEENTEN = {
    "0059",
    "0060",
    "0072",
    "0074",
    "0080",
    "0085",
    "0086",
    "0088",
    "0090",
    "0093",
    "0096",
    "0098",
    "0737",
    "1891",
    "1900",
    "1940",
    "1949",
    "1970",
}

KOLOM_HERNOEMEN = {
    "bu_code": "buurtcode",
    "bu_naam": "buurtnaam",
    "gm_code": "gemeentecode",
    "gm_naam": "gemeentenaam",
}

VEREISTE_KOLOMMEN = [
    "buurtcode",
    "buurtnaam",
    "gemeentecode",
    "gemeentenaam",
    "water",
    "jaar",
    "geometry",
]

OPTIONELE_KOLOMMEN = [
    "aantal_inwoners",
    "aantal_huishoudens",
    "bevolkingsdichtheid_inwoners_per_km2",
    "oppervlakte_land_in_ha",
    "oppervlakte_water_in_ha",
    "omgevingsadressendichtheid",
]


# %% Stap 2: inputbestand bepalen
def vind_buurtbestanden() -> list[tuple[int, Path]]:
    """Geef beschikbare buurtbestanden terug, gesorteerd op jaar."""
    bestanden: list[tuple[int, Path]] = []

    for pad in RAW_DIR.glob("Buurten_*.gpkg"):
        match = BUURTEN_BESTAND_PATTERN.fullmatch(pad.name)
        if match:
            bestanden.append((int(match.group(1)), pad))

    return sorted(bestanden)


def kies_input_pad(jaar: int | None = None) -> Path:
    """Selecteer het gevraagde of meest recente buurtbestand."""
    buurtbestanden = vind_buurtbestanden()

    if not buurtbestanden:
        raise FileNotFoundError(
            f"Geen Buurten_<jaar>.gpkg gevonden in {RAW_DIR}"
        )

    if jaar is None:
        return buurtbestanden[-1][1]

    for bestand_jaar, pad in buurtbestanden:
        if bestand_jaar == jaar:
            return pad

    beschikbare_jaren = ", ".join(
        str(bestand_jaar)
        for bestand_jaar, _ in buurtbestanden
    )
    raise FileNotFoundError(
        f"Geen Buurten_{jaar}.gpkg gevonden in {RAW_DIR}. "
        f"Beschikbare jaren: {beschikbare_jaren}"
    )


# %% Stap 3: buurten inlezen en opschonen
def lees_buurten(input_pad: Path) -> gpd.GeoDataFrame:
    """Lees de buurtenlaag uit het GeoPackage."""
    lagen = gpd.list_layers(input_pad)["name"].tolist()

    if "buurten" in lagen:
        laag = "buurten"
    elif len(lagen) == 1:
        laag = lagen[0]
    else:
        beschikbare_lagen = ", ".join(lagen)
        raise ValueError(
            "Laag 'buurten' ontbreekt en het GeoPackage bevat meerdere "
            f"lagen: {beschikbare_lagen}"
        )

    return gpd.read_file(input_pad, layer=laag)


def normaliseer_kolommen(
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Normaliseer kolomnamen en pas bekende hernoemingen toe."""
    genormaliseerd = gdf.copy()
    genormaliseerd.columns = (
        genormaliseerd.columns
        .str.lower()
        .str.strip()
        .str.replace(" ", "_", regex=False)
    )

    return genormaliseerd.rename(columns=KOLOM_HERNOEMEN)


def normaliseer_gemeentecode(serie: pd.Series) -> pd.Series:
    """Normaliseer gemeentecodes naar vier cijfers zonder GM-prefix."""
    genormaliseerd = (
        serie.astype("string")
        .str.strip()
        .str.upper()
        .str.removeprefix("GM")
    )

    geldig_formaat = genormaliseerd.str.fullmatch(
        r"\d{1,4}",
        na=False,
    )

    return genormaliseerd.where(geldig_formaat).str.zfill(4)


def controleer_kolommen(gdf: gpd.GeoDataFrame) -> None:
    """Controleer of vereiste en optionele kolommen aanwezig zijn."""
    ontbrekend = [
        kolom
        for kolom in VEREISTE_KOLOMMEN
        if kolom not in gdf.columns
    ]

    if ontbrekend:
        raise ValueError(
            "Verplichte kolommen ontbreken: "
            f"{', '.join(ontbrekend)}"
        )

    ontbrekend_optioneel = [
        kolom
        for kolom in OPTIONELE_KOLOMMEN
        if kolom not in gdf.columns
    ]

    if ontbrekend_optioneel:
        print(
            "Optionele kolommen niet aanwezig:",
            ", ".join(ontbrekend_optioneel),
        )


def controleer_fryslan_selectie(
    gdf: gpd.GeoDataFrame,
) -> None:
    """Controleer de volledigheid van de Friese buurtenselectie."""
    if gdf.empty:
        raise ValueError("Fryslân filter levert geen buurten op.")

    if gdf.crs is None:
        raise ValueError("Fryslân selectie heeft geen CRS.")

    if gdf.geometry.isna().any() or gdf.geometry.is_empty.any():
        raise ValueError(
            "Fryslân selectie bevat ontbrekende of lege geometrieën."
        )

    ongeldige_geometrie = ~gdf.geometry.is_valid
    if ongeldige_geometrie.any():
        raise ValueError(
            "Fryslân selectie bevat "
            f"{ongeldige_geometrie.sum()} ongeldige geometrieën."
        )

    dubbele_buurtcodes = gdf["buurtcode"].duplicated(keep=False)
    if dubbele_buurtcodes.any():
        dubbele_codes = sorted(
            gdf.loc[dubbele_buurtcodes, "buurtcode"]
            .astype(str)
            .unique()
        )
        raise ValueError(
            "Fryslân selectie bevat dubbele buurtcodes: "
            f"{', '.join(dubbele_codes)}"
        )

    aantal_gemeenten = gdf["gemeentecode"].nunique()

    if aantal_gemeenten != len(FRYSLAN_GEMEENTEN):
        gemeenten = ", ".join(
            sorted(gdf["gemeentenaam"].astype(str).unique())
        )
        raise ValueError(
            "Onverwacht aantal Friese gemeenten: "
            f"{aantal_gemeenten} in plaats van "
            f"{len(FRYSLAN_GEMEENTEN)}. "
            f"Gevonden gemeenten: {gemeenten}"
        )


def filter_fryslan(
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Normaliseer gemeentecodes en selecteer buurten in Fryslân."""
    if "gemeentecode" not in gdf.columns:
        raise ValueError(
            "Kolom 'gemeentecode' ontbreekt. "
            "Filteren op Fryslân is niet mogelijk."
        )

    genormaliseerd = gdf.copy()
    genormaliseerd["gemeentecode"] = normaliseer_gemeentecode(
        genormaliseerd["gemeentecode"]
    )

    friesland = genormaliseerd[
        genormaliseerd["gemeentecode"].isin(FRYSLAN_GEMEENTEN)
    ].copy()

    print("Buurten na Fryslân-filter:", len(friesland))
    print(
        "Friese gemeenten:",
        friesland["gemeentecode"].nunique(),
    )

    controleer_fryslan_selectie(friesland)

    return friesland


# %% Stap 4: workflow uitvoeren
def main() -> None:
    """Bouw en schrijf de basislaag met Friese buurten."""
    input_pad = kies_input_pad(jaar=JAAR)

    print(f"Input: {input_pad}")
    print(f"Output: {OUTPUT}")

    gdf = lees_buurten(input_pad)

    print("Aantal kolommen origineel:", len(gdf.columns))

    gdf = normaliseer_kolommen(gdf)
    controleer_kolommen(gdf)
    gdf = filter_fryslan(gdf)

    gewenste_kolommen = (
        VEREISTE_KOLOMMEN[:-1]
        + OPTIONELE_KOLOMMEN
        + ["geometry"]
    )

    beschikbare_outputkolommen = [
        kolom
        for kolom in gewenste_kolommen
        if kolom in gdf.columns
    ]

    gdf_clean = gdf[beschikbare_outputkolommen].copy()

    print(
        "Aantal kolommen behouden:",
        len(gdf_clean.columns),
    )
    print(
        "Behouden kolommen:",
        ", ".join(gdf_clean.columns),
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    gdf_clean.to_file(
        OUTPUT,
        layer="buurten_basis",
        driver="GPKG",
    )

    print(f"Opgeslagen als: {OUTPUT}")


if __name__ == "__main__":
    main()
