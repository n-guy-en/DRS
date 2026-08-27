import shutil

from .normalisatie import normaliseer_ja_nee
from .instellingen import ONDERZOEK_VERKEERSTYPEN, VERKEERSTYPEN
from .netwerk import (
    maak_exportklaar,
    pas_voertuigkolommen_toe,
    schrijf_geojson_met_unieke_feature_ids,
    toegang_masks,
    voeg_reiskosten_toe,
)


def exporteer_parkeerlagen(gpd, parkeerpunten, parkeervlakken, output_map):
    import pandas as pd

    publicatie_drop_kolommen = [
        "van",
        "wegnummer",
        "kilomtrrng",
        "tot",
        "oppervlak",
        "parkeervlak_oppervlak_m2",
    ]

    parkeerpunten = parkeerpunten.copy()
    parkeervlakken = parkeervlakken.copy()
    parkeerpunten["parkeer_type"] = "parkeerpunt"
    parkeervlakken["parkeer_type"] = "parkeervlak"

    parkeren_pad = output_map / "parkeren.json"

    parkeren = gpd.GeoDataFrame(
        pd.concat([parkeerpunten, parkeervlakken], ignore_index=True),
        crs="EPSG:4326",
    )
    parkeren = parkeren.drop(
        columns=publicatie_drop_kolommen,
        errors="ignore",
    )
    schrijf_geojson_met_unieke_feature_ids(parkeren, parkeren_pad)

    return parkeren_pad


def exporteer_verkeerstypen(gdf, output_map, waterlijn_mask):
    export_paden = {}

    for naam, (h_kolom, t_kolom) in VERKEERSTYPEN.items():
        h_ja = normaliseer_ja_nee(gdf[h_kolom]) == "J"
        t_ja = normaliseer_ja_nee(gdf[t_kolom]) == "J"
        (
            export_mask,
            _,
            _,
            heen_toegestaan,
            terug_toegestaan,
        ) = toegang_masks(gdf, h_ja, t_ja, waterlijn_mask)

        selectie = gdf.loc[export_mask].copy()
        selectie_index = selectie.index

        selectie["verkeerstype"] = naam
        selectie["heen_toegestaan"] = heen_toegestaan.loc[selectie_index].astype(bool)
        selectie["terug_toegestaan"] = terug_toegestaan.loc[selectie_index].astype(bool)
        selectie["beide_richtingen_toegestaan"] = (
            selectie["heen_toegestaan"] & selectie["terug_toegestaan"]
        )

        selectie = pas_voertuigkolommen_toe(selectie, naam)
        selectie = voeg_reiskosten_toe(selectie, naam)

        pad = output_map / f"{naam}.json"
        schrijf_geojson_met_unieke_feature_ids(maak_exportklaar(selectie), pad)
        export_paden[naam] = pad

    return export_paden


def publiceer_onderzoekslagen(output_map, lagen_map):
    lagen_map.mkdir(parents=True, exist_ok=True)
    gepubliceerde_paden = []

    for naam in sorted(ONDERZOEK_VERKEERSTYPEN):
        bron_pad = output_map / f"{naam}.json"
        doel_pad = lagen_map / f"{naam}.json"

        if not bron_pad.exists():
            print(f"Onderzoekslaag ontbreekt en is niet gepubliceerd: {bron_pad}")
            continue

        shutil.copy2(bron_pad, doel_pad)
        gepubliceerde_paden.append(doel_pad)

    return gepubliceerde_paden
