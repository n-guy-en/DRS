"""Landelijke WKD-bronnen filteren naar Friese lagen."""

from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

from .instellingen import (
    JAAR,
    standaard_nwb_raw_map,
    standaard_parkeerpunten_pad,
    standaard_parkeervlakken_pad,
    standaard_rijstroken_pad,
    standaard_snelheden_pad,
    standaard_verkeerstypen_pad,
    standaard_wegcategorie_pad,
)


@dataclass(frozen=True)
class WkdBron:
    code: str
    bronmap: str
    bestandsnaam: str
    laag: str
    output_pad: Path


def wkd_bronnen():
    return [
        WkdBron(
            "wegcategorie",
            "wegcategorie",
            "WKD_WEG_CATV2.gpkg",
            "WKD_WEG_CATV2",
            standaard_wegcategorie_pad(),
        ),
        WkdBron(
            "snelheden",
            "snelheden",
            "Snelheden.gpkg",
            "Snelheden",
            standaard_snelheden_pad(),
        ),
        WkdBron(
            "verkeerstypen",
            "verkeerstypen",
            "WKD_VRKRSTPNV2.gpkg",
            "WKD_VRKRSTPNV2",
            standaard_verkeerstypen_pad(),
        ),
        WkdBron(
            "rijstroken",
            "rijstroken",
            "WKD_RIJ_DG_STR.gpkg",
            "WKD_RIJ_DG_STR",
            standaard_rijstroken_pad(),
        ),
        WkdBron(
            "parkeerpunten",
            "parkeren",
            "WKD_Parkpunten.gpkg",
            "WKD_Parkpunten",
            standaard_parkeerpunten_pad(),
        ),
        WkdBron(
            "parkeervlakken",
            "parkeren",
            "WKD_Parkvlak.gpkg",
            "WKD_Parkvlak",
            standaard_parkeervlakken_pad(),
        ),
    ]


def bron_pad(bron):
    lokaal_pad = standaard_nwb_raw_map() / bron.bronmap / bron.bestandsnaam
    if not lokaal_pad.exists():
        raise FileNotFoundError(f"WKD-bestand ontbreekt: {lokaal_pad}")
    return lokaal_pad


def controleer_lokale_bronnen(bronnen):
    ontbrekend = [
        standaard_nwb_raw_map() / bron.bronmap / bron.bestandsnaam
        for bron in bronnen
        if not (standaard_nwb_raw_map() / bron.bronmap / bron.bestandsnaam).exists()
    ]
    if ontbrekend:
        paden = "\n".join(str(pad) for pad in ontbrekend)
        raise FileNotFoundError(
            "Geen complete lokale WKD-set gevonden. Download de GPKG's en "
            "plaats ze op deze paden:\n"
            f"{paden}"
        )


def lees_fryslan_grens(buurten_pad):
    buurten = gpd.read_file(buurten_pad).to_crs("EPSG:28992")
    if buurten.empty:
        raise ValueError(f"Geen buurten gevonden in {buurten_pad}")
    return buurten.geometry.union_all()


def filter_bron(bron, fryslan_grens):
    pad = bron_pad(bron)
    print(f"Lees {bron.code}: {pad}")

    gdf = gpd.read_file(
        pad,
        layer=bron.laag,
        bbox=fryslan_grens.bounds,
    )
    if gdf.empty:
        raise ValueError(f"Geen features gevonden voor {bron.code}")

    gdf = gdf.to_crs("EPSG:28992")
    gdf = gdf[gdf.geometry.intersects(fryslan_grens)].copy()
    gdf = gdf.to_crs("EPSG:4326")

    output_pad = bron.output_pad
    output_pad.parent.mkdir(parents=True, exist_ok=True)
    tijdelijk_pad = output_pad.with_suffix(output_pad.suffix + ".tmp")
    gdf.to_file(tijdelijk_pad, driver="GeoJSON")
    tijdelijk_pad.replace(output_pad)
    print(f"Opgeslagen: {output_pad} ({len(gdf)} features)")


def filter_wkd_bronnen(
    buurten_pad,
):
    bronnen = wkd_bronnen()
    controleer_lokale_bronnen(bronnen)
    print(f"Gebruik lokale WKD-bestanden voor bronjaar {JAAR}.")

    fryslan_grens = lees_fryslan_grens(buurten_pad)

    for bron in bronnen:
        filter_bron(bron, fryslan_grens)
