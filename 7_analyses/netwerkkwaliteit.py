"""Losse netwerkkwaliteitsanalyse voor fiets- en voetgangersnetwerk.

De analyse gebruikt bestaande netwerkoutput en labelt segmenten op basis van:
- overlap met het autonetwerk via `wvk_id` waar beschikbaar;
- geometrische overlap met het autonetwerk.

Het script schrijft aparte kaartlagen en een samenvatting naar
`7_analyses/processed/`.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
CRS_RD = "EPSG:28992"
CRS_WGS84 = "EPSG:4326"
AUTO_BUFFER_METER = 25.0
OVERLAP_BUFFER_METER = 1.0

PUBLICATIE_KOLOMMEN = [
    "id",
    "wvk_id",
    "straatnaam",
    "wegcategorie",
    "verkeerstype",
    "lengte_meter",
    "afstand_tot_autonetwerk_m",
    "kwaliteitsklasse",
    "toelichting",
    "stroke",
    "stroke-width",
    "geometry",
]

NETWERKLAGEN = [
    {
        "modaliteit": "fiets",
        "netwerk": "fiets",
    },
    {
        "modaliteit": "lopen",
        "netwerk": "voetganger",
    },
]

KWALITEIT_STIJL = {
    "vrijliggend_van_autonetwerk": ("#2ca25f", 2.0),
    "gedeeld_met_autonetwerk": ("#fdae61", 2.2),
    "onbekend": ("#969696", 1.6),
}

KWALITEIT_TOELICHTING = {
    "vrijliggend_van_autonetwerk": (
        "Segment overlapt niet met de autolaag en heeft geen gedeeld auto-wvk_id."
    ),
    "gedeeld_met_autonetwerk": (
        "Segment overlapt met de autolaag of heeft hetzelfde wvk_id als de autolaag."
    ),
    "onbekend": "Onvoldoende informatie voor een duidelijke kwaliteitsklasse.",
}


def netwerk_pad(naam: str) -> Path:
    werk_pad = BASE_DIR / "4_netwerk" / "processed" / "NWB" / f"{naam}.json"
    if werk_pad.exists():
        return werk_pad

    return (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "4_netwerk"
        / "verkeerstypen"
        / f"{naam}.json"
    )


def lees_netwerk(naam: str) -> gpd.GeoDataFrame:
    pad = netwerk_pad(naam)
    if not pad.exists():
        raise FileNotFoundError(pad)
    return gpd.read_file(pad).to_crs(CRS_RD)


def auto_overlap(segmenten: gpd.GeoDataFrame, auto: gpd.GeoDataFrame) -> pd.DataFrame:
    auto_buffer = auto[["wvk_id", "geometry"]].copy()
    auto_buffer["geometry"] = auto_buffer.geometry.buffer(OVERLAP_BUFFER_METER)
    nearest = gpd.sjoin_nearest(
        segmenten[["geometry"]],
        auto[["geometry"]],
        how="left",
        max_distance=AUTO_BUFFER_METER,
        distance_col="afstand_tot_auto_m",
    )
    nearest = nearest[~nearest.index.duplicated(keep="first")]
    overlap = gpd.sjoin(
        segmenten[["geometry"]],
        auto_buffer,
        how="left",
        predicate="intersects",
    )
    overlap = overlap[~overlap.index.duplicated(keep="first")]
    return pd.DataFrame(
        {
            "afstand_tot_auto_m": nearest["afstand_tot_auto_m"],
            "overlap_met_auto": overlap["index_right"].notna(),
            "overlap_auto_wvk_id": overlap["wvk_id"],
        }
    )


def label_segmenten(segmenten: gpd.GeoDataFrame, auto: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    segmenten = segmenten.copy()
    auto = auto.copy()

    info = auto_overlap(segmenten, auto)
    segmenten = segmenten.join(info)

    if "wvk_id" in segmenten.columns and "wvk_id" in auto.columns:
        auto_wvk_ids = set(auto["wvk_id"].dropna().astype(str))
        segmenten["zelfde_wvk_als_auto"] = (
            segmenten["wvk_id"].dropna().astype(str).isin(auto_wvk_ids)
        ).reindex(segmenten.index, fill_value=False)
    else:
        segmenten["zelfde_wvk_als_auto"] = False

    segmenten["gedeeld_met_autonetwerk"] = (
        segmenten["zelfde_wvk_als_auto"]
        | segmenten["overlap_met_auto"]
    )
    segmenten.loc[
        segmenten["gedeeld_met_autonetwerk"],
        "kwaliteitsklasse",
    ] = "gedeeld_met_autonetwerk"
    segmenten.loc[
        ~segmenten["gedeeld_met_autonetwerk"],
        "kwaliteitsklasse",
    ] = "vrijliggend_van_autonetwerk"
    return segmenten


def maak_publicatielaag(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    resultaat = gdf.copy()
    resultaat = resultaat.rename(
        columns={"afstand_tot_auto_m": "afstand_tot_autonetwerk_m"}
    )
    resultaat["toelichting"] = resultaat["kwaliteitsklasse"].map(
        KWALITEIT_TOELICHTING
    )
    stijl = resultaat["kwaliteitsklasse"].map(KWALITEIT_STIJL)
    resultaat["stroke"] = stijl.apply(lambda waarde: waarde[0])
    resultaat["stroke-width"] = stijl.apply(lambda waarde: waarde[1])

    kolommen = [kolom for kolom in PUBLICATIE_KOLOMMEN if kolom in resultaat.columns]
    return resultaat[kolommen]


def verwijder_dubbele_gedeelde_segmenten(
    gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    vrijliggend = gdf[gdf["kwaliteitsklasse"].eq("vrijliggend_van_autonetwerk")]
    gedeeld = gdf[gdf["kwaliteitsklasse"].eq("gedeeld_met_autonetwerk")]
    if vrijliggend.empty or gedeeld.empty:
        return gdf

    dichtstbij_vrijliggend = gpd.sjoin_nearest(
        gedeeld[["geometry"]],
        vrijliggend[["geometry"]],
        how="left",
        max_distance=OVERLAP_BUFFER_METER,
        distance_col="afstand_tot_vrijliggend_m",
    )
    te_verwijderen = dichtstbij_vrijliggend[
        dichtstbij_vrijliggend["afstand_tot_vrijliggend_m"].notna()
    ].index
    return gdf.drop(index=te_verwijderen)


def samenvatting(
    gdf: gpd.GeoDataFrame,
    modaliteit: str,
) -> pd.DataFrame:
    totaal = float(gdf["lengte_meter"].fillna(gdf.geometry.length).sum())
    rows = []
    for klasse, groep in gdf.groupby("kwaliteitsklasse", dropna=False):
        lengte = float(groep["lengte_meter"].fillna(groep.geometry.length).sum())
        rows.append(
            {
                "modaliteit": modaliteit,
                "kwaliteitsklasse": klasse,
                "lengte_meter": round(lengte, 1),
                "aandeel_lengte_pct": round((lengte / totaal * 100) if totaal else 0, 1),
                "aantal_segmenten": int(len(groep)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    auto = lees_netwerk("personenauto")

    out_dir = BASE_DIR / "7_analyses" / "processed" / "netwerkkwaliteit"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    samenvattingen = []
    for laag_config in NETWERKLAGEN:
        modaliteit = laag_config["modaliteit"]
        netwerknaam = laag_config["netwerk"]
        print(f"Bereken netwerkkwaliteit: {modaliteit}")

        gelabeld = label_segmenten(lees_netwerk(netwerknaam), auto)
        publicatie = verwijder_dubbele_gedeelde_segmenten(gelabeld)
        laag = maak_publicatielaag(publicatie)

        map_pad = out_dir / modaliteit
        map_pad.mkdir(parents=True, exist_ok=True)
        laag.to_crs(CRS_WGS84).to_file(
            map_pad / f"{modaliteit}_netwerkkwaliteit.gpkg",
            layer=f"{modaliteit}_netwerkkwaliteit",
            driver="GPKG",
        )
        samenvattingen.append(samenvatting(publicatie, modaliteit))
        print(f"Opgeslagen: {map_pad / f'{modaliteit}_netwerkkwaliteit.gpkg'}")

    overzicht = pd.concat(samenvattingen, ignore_index=True)
    overzicht.to_csv(out_dir / "netwerkkwaliteit_samenvatting.csv", index=False)
    print(f"Opgeslagen: {out_dir / 'netwerkkwaliteit_samenvatting.csv'}")


if __name__ == "__main__":
    main()
