# %% Stap 1: imports en instellingen
from pathlib import Path

from nwb.helpers.normalisatie import (
    controleer_kolommen,
    laad_geopandas,
    normaliseer_kolomnamen,
)
from nwb.helpers.instellingen import (
    standaard_lagen_output_map,
    standaard_output_map,
    standaard_parkeerpunten_pad,
    standaard_parkeervlakken_pad,
    standaard_rijstroken_pad,
    standaard_snelheden_pad,
    standaard_verkeerstypen_pad,
    standaard_water_buurten_pad,
    standaard_wegcategorie_pad,
    project_dir,
)
from nwb.helpers.export import (
    exporteer_parkeerlagen,
    exporteer_verkeerstypen,
    publiceer_onderzoekslagen,
)
from nwb.helpers.invoer import (
    laad_parkeerdata,
    laad_rijstroken,
    laad_snelheden_basis,
    laad_wegcategorieen,
    laad_waterbuurten,
    voeg_verkeerstypen_toe,
    voeg_wegcategorieen_toe,
)
from nwb.helpers.netwerk import (
    maak_waterlijn_mask,
    voeg_netwerkattributen_toe,
)
from nwb.helpers.osm import (
    schrijf_fietsroutes_samenvoeging,
    schrijf_looproutes_samenvoeging,
)
from nwb.helpers.filter import filter_wkd_bronnen


BRON = standaard_verkeerstypen_pad()
WEGCATEGORIE = standaard_wegcategorie_pad()
SNELHEDEN = standaard_snelheden_pad()
RIJSTROKEN = standaard_rijstroken_pad()
PARKEERPUNTEN = standaard_parkeerpunten_pad()
PARKEERVLAKKEN = standaard_parkeervlakken_pad()
OUTPUT = standaard_output_map()
OSM_WALK_EDGES = (
    project_dir()
    / "4_netwerk"
    / "processed"
    / "OSM"
    / "walk_edges.gpkg"
)
OSM_BIKE_EDGES = (
    project_dir()
    / "4_netwerk"
    / "processed"
    / "OSM"
    / "bike_edges.gpkg"
)
WATER_BUURTEN = standaard_water_buurten_pad()
LOOPROUTE_SAMENVOEGING = True
FIETSROUTE_SAMENVOEGING = True

# Stap 2: workflow uitvoeren
def main():
    gpd = laad_geopandas()
    bron_pad = Path(BRON)
    output_map = Path(OUTPUT)
    output_map.mkdir(parents=True, exist_ok=True)

    print("Filter landelijke WKD-bronnen naar Friese lagen...")
    filter_wkd_bronnen(
        buurten_pad=Path(WATER_BUURTEN),
    )

    print(f"Lees bron: {bron_pad}")
    verkeerstypen = normaliseer_kolomnamen(gpd.read_file(bron_pad))
    controleer_kolommen(verkeerstypen)

    print(f"Lees snelheden als netwerkbasis: {SNELHEDEN}")
    gdf = laad_snelheden_basis(gpd, Path(SNELHEDEN))
    gdf = voeg_verkeerstypen_toe(gdf, verkeerstypen)

    print(f"Lees wegcategorieen: {WEGCATEGORIE}")
    wegcategorieen = laad_wegcategorieen(gpd, Path(WEGCATEGORIE))
    gdf = voeg_wegcategorieen_toe(gdf, wegcategorieen)

    print(f"Lees rijstroken: {RIJSTROKEN}")
    rijstroken = laad_rijstroken(gpd, Path(RIJSTROKEN))

    print("Lees parkeerpunten en parkeervlakken...")
    parkeerpunten, parkeervlakken, parkeren = laad_parkeerdata(
        gpd,
        Path(PARKEERPUNTEN),
        Path(PARKEERVLAKKEN),
    )
    parkeren_pad = exporteer_parkeerlagen(
        gpd,
        parkeerpunten,
        parkeervlakken,
        output_map,
    )
    print(f"Opgeslagen: {parkeren_pad}")

    print("Koppel rijstroken en parkeren aan wegvakken...")
    gdf = voeg_netwerkattributen_toe(gdf, rijstroken, parkeren)

    print("Bepaal waterlijnen die niet in landgebonden verkeerstypen horen...")
    waterbuurten = laad_waterbuurten(
        gpd,
        Path(WATER_BUURTEN),
    )
    waterlijn_mask = maak_waterlijn_mask(gdf, waterbuurten)

    print("Exporteer JSON per verkeerstype...")
    export_paden = exporteer_verkeerstypen(gdf, output_map, waterlijn_mask)
    for pad in export_paden.values():
        print(f"Opgeslagen: {pad}")

    if LOOPROUTE_SAMENVOEGING:
        voetganger_gdf = gpd.read_file(export_paden["voetganger"])
        samenvoeg_pad = schrijf_looproutes_samenvoeging(
            gpd,
            voetganger_gdf,
            Path(OSM_WALK_EDGES),
            output_map,
        )
        print(f"Opgeslagen: {samenvoeg_pad}")

    if FIETSROUTE_SAMENVOEGING:
        fiets_gdf = gpd.read_file(export_paden["fiets"])
        samenvoeg_pad = schrijf_fietsroutes_samenvoeging(
            gpd,
            fiets_gdf,
            Path(OSM_BIKE_EDGES),
            output_map,
        )
        print(f"Opgeslagen: {samenvoeg_pad}")

    print("Publiceer onderzoekslagen naar 0_layers...")
    gepubliceerde_paden = publiceer_onderzoekslagen(
        output_map,
        standaard_lagen_output_map(),
    )
    for pad in gepubliceerde_paden:
        print(f"Gepubliceerd: {pad}")


if __name__ == "__main__":
    main()
