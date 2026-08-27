import pandas as pd

from .normalisatie import naar_getal, normaliseer_ja_nee
from .instellingen import (
    EXPORT_DROP_KOLOMMEN,
    EXPORT_KOLOMMEN,
    GEMOTORISEERDE_AANVULLING,
    ONBEKENDE_WEGCATEGORIEEN,
    PARKEREN_RELEVANT,
    RIJSTROKEN_RELEVANT,
    RICHTING_BRONKOLOMMEN,
    STANDAARD_SNELHEID_KMH,
)


def schrijf_geojson_met_unieke_feature_ids(gdf, pad):
    resultaat = gdf.reset_index(drop=True).copy()
    if "id" in resultaat.columns and "bron_id" not in resultaat.columns:
        resultaat["bron_id"] = resultaat["id"]
    resultaat["id"] = resultaat.index.astype(str)
    resultaat.to_file(pad, driver="GeoJSON")


def voeg_netwerkattributen_toe(gdf, rijstroken, parkeren):
    resultaat = gdf.merge(rijstroken, on="wvk_id", how="left")
    resultaat = resultaat.merge(parkeren, on="wvk_id", how="left")
    return resultaat


def voeg_reiskosten_toe(gdf, verkeerstype):
    resultaat = gdf.copy()
    if resultaat.empty:
        resultaat["lengte_meter"] = []
        resultaat["snelheid_kmh_gebruikt"] = []
        resultaat["reistijd_min"] = []
        return resultaat

    if resultaat.crs is None:
        raise ValueError("CRS ontbreekt; lengte en reistijd kunnen niet worden berekend.")

    geometrie_lengte = resultaat.to_crs("EPSG:28992").geometry.length
    if "lengte_meter" in resultaat:
        bron_lengte = naar_getal(resultaat["lengte_meter"])
        resultaat["lengte_meter"] = bron_lengte.fillna(geometrie_lengte)
    else:
        resultaat["lengte_meter"] = geometrie_lengte

    standaard_snelheid = STANDAARD_SNELHEID_KMH.get(verkeerstype, 50.0)

    if verkeerstype in GEMOTORISEERDE_AANVULLING and "max_snelheid_kmh" in resultaat:
        bron_snelheid = naar_getal(resultaat["max_snelheid_kmh"])
        resultaat["snelheid_kmh_gebruikt"] = bron_snelheid.fillna(standaard_snelheid)
    else:
        resultaat["snelheid_kmh_gebruikt"] = standaard_snelheid

    meter_per_min = resultaat["snelheid_kmh_gebruikt"] * 1000 / 60
    resultaat["reistijd_min"] = resultaat["lengte_meter"] / meter_per_min
    return resultaat


def richting_masks(gdf):
    if "richting_bron" not in gdf.columns:
        beide = pd.Series(True, index=gdf.index)
        return beide, beide

    richting = normaliseer_ja_nee(gdf["richting_bron"])
    heen = richting.isin(["B", "H"]) | ~richting.isin(["B", "H", "T"])
    terug = richting.isin(["B", "T"]) | ~richting.isin(["B", "H", "T"])
    return heen, terug


def mist_alle_verkeerstypen(gdf):
    heeft_verkeerstype = None
    for kolom in RICHTING_BRONKOLOMMEN:
        kolom_heeft_toegang = normaliseer_ja_nee(gdf[kolom]) == "J"
        if heeft_verkeerstype is None:
            heeft_verkeerstype = kolom_heeft_toegang
        else:
            heeft_verkeerstype = heeft_verkeerstype | kolom_heeft_toegang

    if heeft_verkeerstype is None:
        return pd.Series(True, index=gdf.index)
    return ~heeft_verkeerstype


def mist_betekenisvolle_wegcategorie(gdf):
    if "wegcategorieen" not in gdf.columns:
        return pd.Series(True, index=gdf.index)

    def is_onbekend(waarden):
        if not isinstance(waarden, list):
            return True
        schoon = {
            str(waarde).strip().lower()
            for waarde in waarden
            if str(waarde).strip()
        }
        return not schoon or schoon <= ONBEKENDE_WEGCATEGORIEEN

    return gdf["wegcategorieen"].map(is_onbekend)


def onbekende_basisweg_mask(gdf):
    return mist_alle_verkeerstypen(gdf) & mist_betekenisvolle_wegcategorie(gdf)


def toegang_masks(gdf, h_ja, t_ja, waterlijn_mask):
    """Bepaal toegang per verkeerstype.

    Officiele h/t-kolommen zijn leidend. Alleen als een wegvak in geen enkel
    verkeerstype voorkomt en geen betekenisvolle wegcategorie heeft, vult de
    snelhedenbasis het netwerk aan met richting uit KENM_RICHT.
    """
    bron_toegankelijk = h_ja | t_ja
    aanvulling_onbekend = onbekende_basisweg_mask(gdf) & ~waterlijn_mask
    richting_heen, richting_terug = richting_masks(gdf)
    toegang = (bron_toegankelijk | aanvulling_onbekend) & ~waterlijn_mask

    heen_toegestaan = (h_ja | (aanvulling_onbekend & richting_heen)) & toegang
    terug_toegestaan = (t_ja | (aanvulling_onbekend & richting_terug)) & toegang

    return (
        toegang,
        bron_toegankelijk,
        aanvulling_onbekend,
        heen_toegestaan,
        terug_toegestaan,
    )


def maak_exportklaar(gdf):
    drop_kolommen = [kolom for kolom in EXPORT_DROP_KOLOMMEN if kolom in gdf.columns]
    resultaat = gdf.drop(columns=drop_kolommen)
    keep_kolommen = [kolom for kolom in EXPORT_KOLOMMEN if kolom in resultaat.columns]
    return resultaat[keep_kolommen]


def pas_voertuigkolommen_toe(gdf, verkeerstype):
    resultaat = gdf.copy()

    rijstrook_kolommen = ["rijstroken_aantal"]
    parkeer_kolommen = [
        "parkeerpunten_aantal",
        "parkeervlakken_aantal",
        "parkeervlakken_oppervlak_m2",
        "parkeren_gekoppeld",
    ]

    if verkeerstype in RIJSTROKEN_RELEVANT:
        for kolom in rijstrook_kolommen:
            if kolom in resultaat.columns:
                resultaat[kolom] = resultaat[kolom].fillna(0).astype(int)
    else:
        resultaat = resultaat.drop(
            columns=[kolom for kolom in rijstrook_kolommen if kolom in resultaat.columns]
        )

    if verkeerstype in PARKEREN_RELEVANT:
        for kolom in ("parkeerpunten_aantal", "parkeervlakken_aantal"):
            if kolom in resultaat.columns:
                resultaat[kolom] = resultaat[kolom].fillna(0).astype(int)
        if "parkeervlakken_oppervlak_m2" in resultaat.columns:
            resultaat["parkeervlakken_oppervlak_m2"] = resultaat[
                "parkeervlakken_oppervlak_m2"
            ].fillna(0.0)
        resultaat["parkeren_gekoppeld"] = (
            resultaat.get("parkeerpunten_aantal", 0)
            + resultaat.get("parkeervlakken_aantal", 0)
        ) > 0
    else:
        resultaat = resultaat.drop(
            columns=[kolom for kolom in parkeer_kolommen if kolom in resultaat.columns]
        )

    return resultaat


def maak_waterlijn_mask(gdf, waterbuurten):
    if gdf.crs is None:
        raise ValueError("CRS ontbreekt in verkeerstypen-bron.")
    if waterbuurten.crs is None:
        raise ValueError("CRS ontbreekt in waterbuurten.")

    gdf_projected = gdf.to_crs(waterbuurten.crs)
    punten_op_lijn = gdf_projected.geometry.representative_point()
    water_union = waterbuurten.geometry.union_all()
    return punten_op_lijn.within(water_union)
