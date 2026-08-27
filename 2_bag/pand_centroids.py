"""
Maak BAG-pandcentroids en koppel deze aan buurten.

Input:
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
- 0_layers/processed/1_buurten/buurten_basis.gpkg

Output:
- 0_layers/processed/2_bag/bag_panden.gpkg
"""

# %% Stap 1: imports en instellingen
import geopandas as gpd

from config import (
    BASE_DIR,
    CRS_RD,
    CRS_WGS84,
    ANALYSEJAAR,
)

VEREISTE_PAND_KOLOMMEN = ["pand_id", "pand_status", "geometry"]
VEREISTE_BUURT_KOLOMMEN = [
    "buurtcode",
    "buurtnaam",
    "gemeentecode",
    "gemeentenaam",
    "geometry",
]


# %% Stap 2: BAG-panden lezen
def controleer_kolommen(
    gdf: gpd.GeoDataFrame,
    kolommen: list[str],
    bron: str,
) -> None:
    """Controleer of alle vereiste kolommen aanwezig zijn."""
    ontbrekend = [kolom for kolom in kolommen if kolom not in gdf.columns]
    if ontbrekend:
        raise ValueError(
            f"Verplichte kolommen ontbreken in {bron}: "
            f"{', '.join(ontbrekend)}"
        )


def controleer_geometrie(
    gdf: gpd.GeoDataFrame,
    bron: str,
) -> gpd.GeoDataFrame:
    """Verwijder lege geometrieën en weiger ongeldige geometrieën."""
    geldig = gdf.geometry.notna() & ~gdf.geometry.is_empty
    opgeschoond = gdf.loc[geldig].copy()

    ongeldige_geometrie = ~opgeschoond.geometry.is_valid
    if ongeldige_geometrie.any():
        raise ValueError(
            f"{bron} bevat {int(ongeldige_geometrie.sum())} "
            "ongeldige geometrieën."
        )

    return opgeschoond


def lees_panden(jaar: int) -> gpd.GeoDataFrame:
    """Lees pandpolygonen en zet deze om naar RD-centroids."""
    input_panden = (
        BASE_DIR
        / "2_bag"
        / "bag_frl_xml"
        / "per_jaar"
        / f"pnd_fryslan_{jaar}.geojson"
    )

    if not input_panden.exists():
        raise FileNotFoundError(
            f"BAG-pandbestand niet gevonden: {input_panden}"
        )

    print(f"Lees BAG-panden: {input_panden}")
    panden = gpd.read_file(input_panden)
    controleer_kolommen(panden, VEREISTE_PAND_KOLOMMEN, str(input_panden))

    if panden.crs is None:
        raise ValueError(f"BAG-pandbestand heeft geen CRS: {input_panden}")

    panden = controleer_geometrie(panden, str(input_panden)).to_crs(CRS_RD)
    panden = panden[panden["pand_status"] == "Pand in gebruik"].copy()

    panden["jaar"] = jaar
    panden["pand_oppervlakte_m2"] = panden.geometry.area.round(2)
    panden["geometry"] = panden.geometry.centroid
    panden["pand_x"] = panden.geometry.x.round(3)
    panden["pand_y"] = panden.geometry.y.round(3)

    panden_wgs84 = panden.to_crs(CRS_WGS84)
    panden["pand_lon"] = panden_wgs84.geometry.x.round(8)
    panden["pand_lat"] = panden_wgs84.geometry.y.round(8)

    return panden


# %% Stap 3: buurten lezen
def lees_buurten() -> gpd.GeoDataFrame:
    """Lees de Friese buurtenlaag in RD New."""
    input_buurten = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "1_buurten"
        / "buurten_basis.gpkg"
    )

    if not input_buurten.exists():
        raise FileNotFoundError(
            f"Buurtbestand niet gevonden: {input_buurten}"
        )

    print(f"Lees buurten: {input_buurten}")
    buurten = gpd.read_file(input_buurten)
    controleer_kolommen(buurten, VEREISTE_BUURT_KOLOMMEN, str(input_buurten))

    if buurten.crs is None:
        raise ValueError(f"Buurtbestand heeft geen CRS: {input_buurten}")

    buurten = controleer_geometrie(buurten, str(input_buurten)).to_crs(CRS_RD)

    buurtkolommen = [
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
        "aantal_inwoners",
        "aantal_huishoudens",
        "geometry",
    ]
    beschikbare_kolommen = [
        kolom for kolom in buurtkolommen if kolom in buurten.columns
    ]

    return buurten[beschikbare_kolommen].copy()


def controleer_buurtkoppeling(gekoppeld: gpd.GeoDataFrame) -> None:
    """Controleer dat ieder pand precies één buurtkoppeling heeft."""

    ontbrekend = int(gekoppeld["buurtcode"].isna().sum())
    if ontbrekend:
        raise ValueError(
            f"{ontbrekend} panden zijn niet aan een buurt gekoppeld."
        )


def koppel_panden_aan_buurten(
    panden: gpd.GeoDataFrame,
    buurten: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """Koppel ieder pandcentroid aan één buurt."""
    print("Koppel pand-centroids aan buurten")

    gekoppeld = gpd.sjoin(
        panden,
        buurten,
        how="left",
        predicate="within",
    ).drop(columns=["index_right"], errors="ignore")
    controleer_buurtkoppeling(gekoppeld)
    return gekoppeld


# %% Stap 4: output schrijven
def schrijf_output(pand_centroids: gpd.GeoDataFrame, jaar: int) -> None:
    """Schrijf de pandcentroids atomair naar een GeoPackage."""
    output_bag = BASE_DIR / "0_layers" / "processed" / "2_bag"
    output_bag.mkdir(parents=True, exist_ok=True)

    panden_pad = output_bag / "bag_panden.gpkg"
    tijdelijk_pad = output_bag / "bag_panden.tmp.gpkg"
    pand_centroids_wgs84 = pand_centroids.to_crs(CRS_WGS84)

    if tijdelijk_pad.exists():
        tijdelijk_pad.unlink()

    pand_centroids_wgs84.to_file(
        tijdelijk_pad,
        layer="bag_panden",
        driver="GPKG",
    )
    tijdelijk_pad.replace(panden_pad)

    print(f"Opgeslagen voor {jaar}: {panden_pad}")


# %% Stap 5: workflow uitvoeren
def main() -> None:
    """Maak de verrijkte pandcentroidlaag voor het ingestelde jaar."""
    panden = lees_panden(ANALYSEJAAR)
    buurten = lees_buurten()
    pand_centroids = koppel_panden_aan_buurten(panden, buurten)

    totaal_panden = len(pand_centroids)
    gekoppelde_panden = pand_centroids["buurtcode"].notna().sum()

    print(f"Panden in gebruik: {totaal_panden}")
    print(f"Panden gekoppeld aan buurt: {gekoppelde_panden}")

    schrijf_output(pand_centroids, ANALYSEJAAR)


if __name__ == "__main__":
    main()
