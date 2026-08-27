from .normalisatie import (
    naar_getal,
    normaliseer_ja_nee,
    normaliseer_kolomnamen,
    tekstkolom,
    unieke_tekst,
)
from .instellingen import RICHTING_BRONKOLOMMEN


def laad_wegcategorieen(gpd, wegcategorie_pad):
    wegcategorie = normaliseer_kolomnamen(gpd.read_file(wegcategorie_pad))
    if "wvk_id" not in wegcategorie.columns or "weg_cat" not in wegcategorie.columns:
        raise ValueError("Wegcategoriebron moet kolommen 'WVK_ID' en 'WEG_CAT' bevatten.")

    wegcategorie["weg_cat_norm"] = (
        wegcategorie["weg_cat"].fillna("").astype(str).str.strip().str.lower()
    )
    categorieen = (
        wegcategorie.groupby("wvk_id")["weg_cat_norm"]
        .apply(lambda waarden: sorted(set(waarde for waarde in waarden if waarde)))
        .reset_index(name="wegcategorieen")
    )
    categorieen["wegcategorie"] = categorieen["wegcategorieen"].map(
        lambda waarden: "; ".join(waarden)
    )
    return categorieen


def voeg_wegcategorieen_toe(gdf, wegcategorieen):
    if "wvk_id" not in gdf.columns:
        raise ValueError("Verkeerstypenbron mist kolom 'wvk_id'.")

    resultaat = gdf.merge(
        wegcategorieen[["wvk_id", "wegcategorieen", "wegcategorie"]],
        on="wvk_id",
        how="left",
    )
    resultaat["wegcategorieen"] = resultaat["wegcategorieen"].map(
        lambda waarde: waarde if isinstance(waarde, list) else []
    )
    resultaat["wegcategorie"] = resultaat["wegcategorie"].fillna("")
    return resultaat


def voeg_snelheid_kolommen_toe(snelheden):
    snelheden = snelheden.copy()
    if "wvk_id" not in snelheden.columns or "maxshd" not in snelheden.columns:
        raise ValueError("Snelhedenbron moet kolommen 'WVK_ID' en 'MAXSHD' bevatten.")

    snelheden["maxshd_num"] = naar_getal(snelheden["maxshd"])
    if "maxshd_alt" in snelheden.columns:
        snelheden["maxshd_alt_num"] = naar_getal(snelheden["maxshd_alt"])
    else:
        snelheden["maxshd_alt_num"] = None
    if "maxshd_adv" in snelheden.columns:
        snelheden["maxshd_adv_num"] = naar_getal(snelheden["maxshd_adv"])
    else:
        snelheden["maxshd_adv_num"] = None

    snelheden["max_snelheid_kmh"] = snelheden[
        ["maxshd_num", "maxshd_alt_num", "maxshd_adv_num"]
    ].max(axis=1, skipna=True)
    if "lengte" in snelheden.columns:
        snelheden["lengte_meter"] = naar_getal(snelheden["lengte"])
    else:
        snelheden["lengte"] = ""
        snelheden["lengte_meter"] = None
    if "stt_naam" not in snelheden.columns:
        snelheden["stt_naam"] = ""
    return snelheden


def laad_snelheden_basis(gpd, snelheden_pad):
    snelheden = normaliseer_kolomnamen(gpd.read_file(snelheden_pad))
    if "wvk_id" not in snelheden.columns or "maxshd" not in snelheden.columns:
        raise ValueError("Snelhedenbron moet kolommen 'WVK_ID' en 'MAXSHD' bevatten.")
    if snelheden.crs is None:
        raise ValueError("CRS ontbreekt in snelhedenbron.")

    snelheden = voeg_snelheid_kolommen_toe(snelheden)
    if "wvk_begdat" in snelheden.columns:
        snelheden["begindat"] = snelheden["wvk_begdat"]
    elif "begindat" not in snelheden.columns:
        snelheden["begindat"] = None
    if "fk_veld1" in snelheden.columns:
        snelheden["bron_id"] = snelheden["fk_veld1"]
    elif "bron_id" not in snelheden.columns:
        snelheden["bron_id"] = snelheden["id"] if "id" in snelheden.columns else None
    if "id" not in snelheden.columns:
        snelheden["id"] = snelheden["wvk_id"]

    snelheden["straatnaam"] = tekstkolom(snelheden, "stt_naam")
    snelheden["baansoort"] = tekstkolom(snelheden, "bst_code")
    snelheden["richting_bron"] = tekstkolom(snelheden, "kenm_richt")

    return snelheden[
        [
            "id",
            "wvk_id",
            "begindat",
            "bron_id",
            "straatnaam",
            "baansoort",
            "richting_bron",
            "lengte_meter",
            "max_snelheid_kmh",
            "geometry",
        ]
    ].copy()


def laad_snelheden(gpd, snelheden_pad):
    snelheden = normaliseer_kolomnamen(gpd.read_file(snelheden_pad))
    if "wvk_id" not in snelheden.columns or "maxshd" not in snelheden.columns:
        raise ValueError("Snelhedenbron moet kolommen 'WVK_ID' en 'MAXSHD' bevatten.")
    snelheden = voeg_snelheid_kolommen_toe(snelheden)

    aggregatie = (
        snelheden.groupby("wvk_id")
        .agg(
            straatnaam=("stt_naam", unieke_tekst),
            lengte_meter=("lengte_meter", "max"),
            max_snelheid_kmh=("max_snelheid_kmh", "max"),
        )
        .reset_index()
    )
    return aggregatie


def aggregeer_verkeerstypen(gdf):
    gdf = gdf[["wvk_id", *RICHTING_BRONKOLOMMEN]].copy()
    for kolom in RICHTING_BRONKOLOMMEN:
        gdf[kolom] = (normaliseer_ja_nee(gdf[kolom]) == "J").astype("uint8")

    aggregatie = gdf.groupby("wvk_id", as_index=False)[RICHTING_BRONKOLOMMEN].max()
    for kolom in RICHTING_BRONKOLOMMEN:
        aggregatie[kolom] = aggregatie[kolom].map({1: "J", 0: "N"})
    return aggregatie


def voeg_verkeerstypen_toe(gdf, verkeerstypen):
    resultaat = gdf.merge(
        aggregeer_verkeerstypen(verkeerstypen),
        on="wvk_id",
        how="left",
    )
    for kolom in RICHTING_BRONKOLOMMEN:
        resultaat[kolom] = resultaat[kolom].fillna("N")
    return resultaat


def laad_rijstroken(gpd, rijstroken_pad):
    rijstroken = normaliseer_kolomnamen(gpd.read_file(rijstroken_pad))
    if "wvk_id" not in rijstroken.columns or "rijstrkn" not in rijstroken.columns:
        raise ValueError("Rijstrokenbron moet kolommen 'WVK_ID' en 'RIJSTRKN' bevatten.")

    rijstroken["rijstroken_aantal"] = naar_getal(rijstroken["rijstrkn"])
    return (
        rijstroken.groupby("wvk_id")
        .agg(rijstroken_aantal=("rijstroken_aantal", "max"))
        .reset_index()
    )


def laad_parkeerlaag(gpd, parkeer_pad):
    parkeren = normaliseer_kolomnamen(gpd.read_file(parkeer_pad))
    if "wvk_id" not in parkeren.columns:
        raise ValueError(f"Parkeerbron mist kolom 'WVK_ID': {parkeer_pad}")
    if "id" not in parkeren.columns:
        parkeren["id"] = parkeren.index.astype(str)
    parkeren = parkeren.to_crs("EPSG:4326")
    return parkeren


def laad_parkeerdata(gpd, parkeerpunten_pad, parkeervlakken_pad):
    parkeerpunten = laad_parkeerlaag(gpd, parkeerpunten_pad)
    parkeervlakken = laad_parkeerlaag(gpd, parkeervlakken_pad)

    parkeerpunten_samenvatting = (
        parkeerpunten.groupby("wvk_id")
        .agg(parkeerpunten_aantal=("id", "count"))
        .reset_index()
    )

    if "oppervlak" in parkeervlakken.columns:
        parkeervlakken["parkeervlak_oppervlak_m2"] = naar_getal(
            parkeervlakken["oppervlak"]
        )
    else:
        parkeervlakken["parkeervlak_oppervlak_m2"] = 0.0

    parkeervlakken_samenvatting = (
        parkeervlakken.groupby("wvk_id")
        .agg(
            parkeervlakken_aantal=("id", "count"),
            parkeervlakken_oppervlak_m2=("parkeervlak_oppervlak_m2", "sum"),
        )
        .reset_index()
    )

    parkeren = parkeerpunten_samenvatting.merge(
        parkeervlakken_samenvatting,
        on="wvk_id",
        how="outer",
    )
    return parkeerpunten, parkeervlakken, parkeren


def laad_waterbuurten(gpd, water_buurten_pad):
    water_buurten = normaliseer_kolomnamen(gpd.read_file(water_buurten_pad))
    if "water" not in water_buurten.columns:
        raise ValueError(
            "Kolom 'water' ontbreekt in waterbuurten. "
            "Run eerst: python3 1_buurten/buurtlaag.py"
        )

    water_mask = (
        water_buurten["water"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("JA")
    )
    return water_buurten.loc[water_mask].copy()
