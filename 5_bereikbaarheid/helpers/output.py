"""Samenvatting, kaartkleuren en wegschrijven van resultaten."""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from .instellingen import (
    BASE_DIR,
    CRS_WGS84,
    KLEUREN,
    MODUS_CODES,
    bereikbaar_kolom as maak_bereikbaar_kolom,
    binnen_kolom as maak_binnen_kolom,
    norm_kolom,
    output_basis_dir,
    tabel_output_basis_dir,
    tijd_kolom as maak_tijd_kolom,
    voorbeeldroute_pad,
    current_config,
    voorziening,
)


MULTIMODAAL_MODUS = "multimodaal"
MULTIMODAAL_CODE = "mul"

MODUS_LABELS = {
    "lopen": "Lopen",
    "fiets": "Fiets",
    "auto": "Auto",
    "ov_lopen": "OV met lopen",
    "ov_fiets": "OV met fiets",
}

ALLE_MODI = set(MODUS_CODES)

PANDSTATUS_STIJL = {
    "binnen_norm": "#2ca25f",
    "buiten_norm": "#de2d26",
    "geen_betrouwbare_route": "#9e9e9e",
}

PAND_PUBLICATIE_DROP_KOLOMMEN = {
    "pand_status",
    "norm_status",
    "pand_documentdatum",
    "pand_documentnummer",
    "pand_geconstateerd",
    "pand_voorkomen_id",
    "pand_begin_geldigheid",
    "pand_eind_geldigheid",
    "pand_tijdstip_registratie",
    "pand_eind_registratie",
    "pand_tijdstip_registratie_lv",
    "pand_tijdstip_eind_registratie_lv",
    "pand_edge_id",
    "pand_u",
    "pand_v",
    "pand_edge_lengte_meter",
    "pand_heen_toegestaan",
    "pand_terug_toegestaan",
    "pand_positie_meter",
    "pand_node",
    "parkeer_idx_auto",
    "target_idx_auto",
    "gekozen_parkeer_idx_auto",
    "gekozen_target_idx_auto",
    "kleur_klasse",
    "stroke_width",
    "fill_opacity",
}


def tijdelijk_pad(pad: Path) -> Path:
    return pad.with_name(f".{pad.stem}.tmp{pad.suffix}")


def schrijf_gpkg_atomic(
    gdf: gpd.GeoDataFrame,
    pad: Path,
    layer: str,
    driver: str = "GPKG",
) -> None:
    tmp_pad = tijdelijk_pad(pad)
    if tmp_pad.exists():
        tmp_pad.unlink()
    gdf.to_file(tmp_pad, layer=layer, driver=driver)
    tmp_pad.replace(pad)


def schrijf_csv_atomic(dataframe: pd.DataFrame, pad: Path) -> None:
    tmp_pad = tijdelijk_pad(pad)
    dataframe.to_csv(tmp_pad, index=False)
    tmp_pad.replace(pad)


def opgeschoonde_pandkaart(
    panden: gpd.GeoDataFrame,
    modus: str,
) -> gpd.GeoDataFrame:
    """Verwijder interne analysevelden uit publicatiekaartlagen."""

    drop_kolommen = set(PAND_PUBLICATIE_DROP_KOLOMMEN)
    drop_kolommen.add(f"target_idx_{modus}")
    drop_kolommen.add(f"{voorziening()}_idx")
    drop_kolommen.update(
        kolom
        for kolom in panden.columns
        if kolom.endswith("_idx")
        or kolom.startswith("target_idx_")
        or kolom.startswith("ov_stop_idx_")
        or (kolom.startswith("gekozen_") and kolom.endswith("_idx"))
    )
    bestaande_drop_kolommen = [
        kolom for kolom in drop_kolommen if kolom in panden.columns
    ]
    resultaat = panden.drop(columns=bestaande_drop_kolommen).copy()
    hernoemingen = {
        kolom: kolom.removeprefix("gekozen_")
        for kolom in resultaat.columns
        if kolom.startswith("gekozen_")
    }
    return resultaat.rename(columns=hernoemingen)


def opgeschoonde_buurtkaart(buurten: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    drop_kolommen = [
        kolom
        for kolom in buurten.columns
        if kolom == "water"
        or (kolom.startswith("heeft_") and "analyse" in kolom)
    ]
    return buurten.drop(columns=drop_kolommen)


def pandlaag_prefix(modus: str) -> str:
    naam = current_config().onderwijsniveau or voorziening()
    return f"{naam}_{MODUS_CODES[modus]}"


def multimodale_pandlaag_prefix() -> str:
    naam = current_config().onderwijsniveau or voorziening()
    return f"{naam}_{MULTIMODAAL_CODE}"


def buurtlaag_prefix() -> str:
    return current_config().onderwijsniveau or voorziening()


def panden_output_pad(modus: str) -> Path:
    return output_basis_dir() / modus / f"{pandlaag_prefix(modus)}.gpkg"


def laad_bestaande_modaliteit(modus: str) -> gpd.GeoDataFrame | None:
    pad = panden_output_pad(modus)
    if not pad.exists():
        return None
    return gpd.read_file(pad)


def vul_ontbrekende_modaliteiten_aan(
    resultaten_per_modus: dict[str, gpd.GeoDataFrame],
) -> dict[str, gpd.GeoDataFrame]:
    """Gebruik bestaande modaliteitsoutput voor multimodaal bij losse runs."""

    resultaten = dict(resultaten_per_modus)
    for modus in MODUS_CODES:
        if modus in resultaten:
            continue
        panden = laad_bestaande_modaliteit(modus)
        if panden is not None:
            resultaten[modus] = panden
    return resultaten


def schrijf_voorbeeld_gpkg_atomic(
    route: gpd.GeoDataFrame,
    punten: gpd.GeoDataFrame | None,
    pad: Path,
) -> None:
    tmp_pad = tijdelijk_pad(pad)
    if tmp_pad.exists():
        tmp_pad.unlink()
    route.to_file(tmp_pad, layer="route_segmenten", driver="GPKG")
    if punten is not None and not punten.empty:
        punten.to_file(tmp_pad, layer="route_punten", driver="GPKG")
    tmp_pad.replace(pad)


def maak_buurtsamenvatting(panden: gpd.GeoDataFrame, modus: str) -> pd.DataFrame:
    tijd_kolom = maak_tijd_kolom(modus)
    bereikbaar_kolom = maak_bereikbaar_kolom(modus)
    binnen_kolom = maak_binnen_kolom(modus)

    samenvatting = (
        panden.groupby(["buurtcode", "buurtnaam", "gemeentecode", "gemeentenaam"])
        .agg(
            panden_aantal=("pand_id", "count"),
            panden_met_reistijd=(bereikbaar_kolom, "sum"),
            panden_binnen_norm=(binnen_kolom, "sum"),
            reistijd_mediaan_min=(tijd_kolom, "median"),
            reistijd_p90_min=(tijd_kolom, lambda s: s.quantile(0.9)),
        )
        .reset_index()
    )
    samenvatting["percentage_met_reistijd"] = (
        samenvatting["panden_met_reistijd"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_binnen_norm"] = (
        samenvatting["panden_binnen_norm"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting[["reistijd_mediaan_min", "reistijd_p90_min"]] = samenvatting[
        ["reistijd_mediaan_min", "reistijd_p90_min"]
    ].round(2)
    samenvatting["modus"] = modus
    samenvatting["modaliteit_code"] = MODUS_CODES[modus]
    return samenvatting


def maak_gemeentesamenvatting(panden: gpd.GeoDataFrame, modus: str) -> pd.DataFrame:
    tijd_kolom = maak_tijd_kolom(modus)
    bereikbaar_kolom = maak_bereikbaar_kolom(modus)
    binnen_kolom = maak_binnen_kolom(modus)

    samenvatting = (
        panden.groupby(["gemeentecode", "gemeentenaam"])
        .agg(
            panden_aantal=("pand_id", "count"),
            panden_bereikbaar=(bereikbaar_kolom, "sum"),
            panden_binnen_norm=(binnen_kolom, "sum"),
            reistijd_mediaan_min=(tijd_kolom, "median"),
            reistijd_p90_min=(tijd_kolom, lambda s: s.quantile(0.9)),
        )
        .reset_index()
    )
    samenvatting["panden_niet_bereikbaar"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_bereikbaar"]
    )
    samenvatting["panden_niet_binnen_norm"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_binnen_norm"]
    )
    samenvatting["percentage_bereikbaar"] = (
        samenvatting["panden_bereikbaar"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_niet_bereikbaar"] = (
        samenvatting["panden_niet_bereikbaar"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_binnen_norm"] = (
        samenvatting["panden_binnen_norm"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_niet_binnen_norm"] = (
        samenvatting["panden_niet_binnen_norm"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting[["reistijd_mediaan_min", "reistijd_p90_min"]] = samenvatting[
        ["reistijd_mediaan_min", "reistijd_p90_min"]
    ].round(2)
    samenvatting["modus"] = modus
    samenvatting["modaliteit_code"] = MODUS_CODES[modus]

    kolommen = [
        "gemeentecode",
        "gemeentenaam",
        "modus",
        "modaliteit_code",
        "panden_aantal",
        "panden_bereikbaar",
        "panden_niet_bereikbaar",
        "percentage_bereikbaar",
        "percentage_niet_bereikbaar",
        "panden_binnen_norm",
        "panden_niet_binnen_norm",
        "percentage_binnen_norm",
        "percentage_niet_binnen_norm",
        "reistijd_mediaan_min",
        "reistijd_p90_min",
    ]
    return samenvatting[kolommen]


def bepaal_klasse_en_kleur(percentage):
    if pd.isna(percentage):
        return "geen data", "#bdbdbd"

    for ondergrens, bovengrens, label, kleur in KLEUREN:
        if ondergrens <= percentage < bovengrens:
            return label, kleur

    return "geen data", "#bdbdbd"


def voeg_buurtkleuren_toe(buurten: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    resultaat = buurten.copy()
    klassen_en_kleuren = resultaat["percentage_binnen_norm"].apply(
        bepaal_klasse_en_kleur
    )
    resultaat["bereikbaarheid_klasse"] = [
        waarde[0] for waarde in klassen_en_kleuren
    ]
    resultaat["kleur_hex"] = [
        waarde[1] for waarde in klassen_en_kleuren
    ]

    resultaat["fill"] = resultaat["kleur_hex"]
    resultaat["stroke"] = "#555555"
    resultaat["stroke-width"] = 0.25
    resultaat["fill-opacity"] = 0.60
    return resultaat


def normaliseer_pand_id(serie: pd.Series) -> pd.Series:
    return serie.astype(str).str.strip().str.removesuffix(".0")


def voeg_normstatus_stijl_toe(
    panden: gpd.GeoDataFrame,
    modus: str,
) -> gpd.GeoDataFrame:
    resultaat = panden.copy()
    bereikbaar_kolom = maak_bereikbaar_kolom(modus)
    binnen_kolom = maak_binnen_kolom(modus)

    bereikbaar = resultaat[bereikbaar_kolom].fillna(False).astype(bool)
    binnen = resultaat[binnen_kolom].fillna(False).astype(bool)

    resultaat["norm_status"] = "buiten_norm"
    resultaat.loc[binnen, "norm_status"] = "binnen_norm"
    resultaat.loc[~bereikbaar, "norm_status"] = "geen_betrouwbare_route"
    resultaat["fill"] = resultaat["norm_status"].map(PANDSTATUS_STIJL)
    resultaat["stroke"] = "#ffffff"
    resultaat["stroke-width"] = 0.15
    resultaat["fill-opacity"] = 0.85
    return resultaat


def maak_pandpolygonen_met_analyse(
    panden: gpd.GeoDataFrame,
    pandpolygonen: gpd.GeoDataFrame,
    modus: str | None = None,
) -> gpd.GeoDataFrame:
    if "pand_id" not in pandpolygonen.columns:
        raise ValueError("Kolom 'pand_id' ontbreekt in de BAG-pandpolygonen.")

    analyse_panden = (
        opgeschoonde_pandkaart(panden, modus)
        if modus is not None
        else panden
    )
    analyse = analyse_panden.drop(columns="geometry").copy()
    analyse["_pand_id_norm"] = normaliseer_pand_id(analyse["pand_id"])
    analyse["_volgorde"] = range(len(analyse))

    polygonen = pandpolygonen[["pand_id", "geometry"]].copy()
    polygonen["_pand_id_norm"] = normaliseer_pand_id(polygonen["pand_id"])
    dubbel = polygonen["_pand_id_norm"].duplicated(keep=False)
    if dubbel.any():
        aantal = int(dubbel.sum())
        raise ValueError(
            f"BAG-pandpolygonen bevatten {aantal} dubbele pand_id's. "
            "Kan binnen/buiten-norm polygonen niet eenduidig maken."
        )

    resultaat = analyse.merge(
        polygonen[["_pand_id_norm", "geometry"]],
        on="_pand_id_norm",
        how="left",
    ).sort_values("_volgorde")
    ontbrekend = resultaat["geometry"].isna()
    if ontbrekend.any():
        aantal = int(ontbrekend.sum())
        raise ValueError(
            f"Voor {aantal} doorgerekende panden ontbreekt een BAG-polygon. "
            "De polygonexport zou dan niet exact overeenkomen met de pandlaag."
        )

    resultaat = resultaat.drop(columns=["_pand_id_norm", "_volgorde"])
    return gpd.GeoDataFrame(resultaat, geometry="geometry", crs=pandpolygonen.crs)


def normaliseer_gemeentecode(serie: pd.Series) -> pd.Series:
    return (
        serie.astype(str)
        .str.strip()
        .str.upper()
        .str.removeprefix("GM")
        .str.zfill(4)
    )


def maak_buurtpolygonen(samenvatting: pd.DataFrame, modus: str) -> gpd.GeoDataFrame:
    buurten_pad = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "1_buurten"
        / "buurten_basis.gpkg"
    )
    buurten = gpd.read_file(buurten_pad, layer="buurten_basis")
    if "water" not in buurten.columns:
        raise ValueError(
            "Kolom 'water' ontbreekt in buurten_basis.gpkg. "
            "Run eerst: python3 1_buurten/buurtlaag.py"
        )
    if "gemeentecode" not in buurten.columns:
        raise ValueError("Kolom 'gemeentecode' ontbreekt in buurten_basis.gpkg.")

    analyse_gemeenten = set(normaliseer_gemeentecode(samenvatting["gemeentecode"]))
    buurten_gemeentecode = normaliseer_gemeentecode(buurten["gemeentecode"])
    buurten = buurten[buurten_gemeentecode.isin(analyse_gemeenten)].copy()
    if buurten.empty:
        raise ValueError(
            "Geen buurtpolygonen gevonden voor de gemeenten in de analyse."
        )

    buurten["is_waterbuurt"] = (
        buurten["water"].astype(str).str.strip().str.upper().eq("JA")
    )

    merge_kolommen = [
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
    ]
    polygonen = buurten.merge(samenvatting, on=merge_kolommen, how="left")
    polygonen[f"heeft_{voorziening()}analyse_{modus}"] = polygonen[
        "panden_aantal"
    ].notna()
    polygonen["modaliteit_code"] = MODUS_CODES.get(modus, MULTIMODAAL_CODE)
    return polygonen[~polygonen["is_waterbuurt"].fillna(False)].drop(
        columns=["is_waterbuurt"]
    )


def multimodale_tijd_kolom() -> str:
    return f"reistijd_{voorziening()}_multimodaal_min"


def multimodale_norm_kolom() -> str:
    return f"norm_{voorziening()}_multimodaal_min"


def multimodale_bereikbaar_kolom() -> str:
    return f"{voorziening()}_multimodaal_bereikbaar"


def multimodale_binnen_kolom() -> str:
    return f"binnen_norm_{voorziening()}_multimodaal"


def unieke_panden_index(panden: gpd.GeoDataFrame, modus: str) -> pd.DataFrame:
    data = panden.drop(columns="geometry").copy()
    data["_pand_id_norm"] = normaliseer_pand_id(data["pand_id"])
    dubbel = data["_pand_id_norm"].duplicated(keep=False)
    if dubbel.any():
        aantal = int(dubbel.sum())
        raise ValueError(
            f"{aantal} dubbele pand_id's in resultaat voor {modus}. "
            "Kan multimodale laag niet eenduidig maken."
        )
    return data.set_index("_pand_id_norm", drop=False)


def modus_met_minimum(tijden: pd.DataFrame, geldig: pd.DataFrame) -> pd.Series:
    keuze_tijden = tijden.where(geldig)
    heeft_keuze = keuze_tijden.notna().any(axis=1)
    keuze = pd.Series(pd.NA, index=tijden.index, dtype="object")
    if heeft_keuze.any():
        keuze.loc[heeft_keuze] = keuze_tijden.loc[heeft_keuze].idxmin(axis=1)
    return keuze


def voeg_multimodale_stijl_toe(panden: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    resultaat = panden.copy()
    bereikbaar = resultaat[multimodale_bereikbaar_kolom()].fillna(False).astype(bool)
    binnen = resultaat[multimodale_binnen_kolom()].fillna(False).astype(bool)

    resultaat["norm_status"] = "buiten_norm"
    resultaat.loc[binnen, "norm_status"] = "binnen_norm"
    resultaat.loc[~bereikbaar, "norm_status"] = "geen_betrouwbare_route"
    resultaat["fill"] = resultaat["norm_status"].map(PANDSTATUS_STIJL)
    resultaat["stroke"] = "#ffffff"
    resultaat["stroke-width"] = 0.15
    resultaat["fill-opacity"] = 0.85
    return resultaat


def maak_multimodale_panden(
    resultaten_per_modus: dict[str, gpd.GeoDataFrame],
) -> gpd.GeoDataFrame:
    modi = [modus for modus in resultaten_per_modus if modus in MODUS_CODES]
    if not modi:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_WGS84)

    eerste = resultaten_per_modus[modi[0]]
    basis_kolommen = [
        "pand_id",
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
        "is_woonpand",
        "gebruiksdoelen",
        "geometry",
    ]
    basis_kolommen = [kolom for kolom in basis_kolommen if kolom in eerste.columns]
    resultaat = eerste[basis_kolommen].copy()
    resultaat["_pand_id_norm"] = normaliseer_pand_id(resultaat["pand_id"])
    resultaat["_volgorde"] = range(len(resultaat))
    resultaat_index = resultaat["_pand_id_norm"]

    tijden = pd.DataFrame(index=resultaat.index)
    normen = pd.DataFrame(index=resultaat.index)
    bereikbaar = pd.DataFrame(index=resultaat.index)
    binnen = pd.DataFrame(index=resultaat.index)

    for modus in modi:
        data = unieke_panden_index(resultaten_per_modus[modus], modus)
        data = data.reindex(resultaat_index.to_numpy())
        tijden[modus] = pd.to_numeric(
            data[maak_tijd_kolom(modus)],
            errors="coerce",
        ).to_numpy()
        normen[modus] = pd.to_numeric(
            data[norm_kolom(modus)],
            errors="coerce",
        ).to_numpy()
        bereikbaar[modus] = (
            data[maak_bereikbaar_kolom(modus)].fillna(False).astype(bool)
        ).to_numpy()
        binnen[modus] = (
            data[maak_binnen_kolom(modus)].fillna(False).astype(bool)
        ).to_numpy()

    snelste_modus = modus_met_minimum(tijden, bereikbaar)
    beste_binnen_modus = modus_met_minimum(tijden, binnen)
    gekozen_modus = beste_binnen_modus.fillna(snelste_modus)

    resultaat["modus"] = MULTIMODAAL_MODUS
    resultaat["modaliteit_code"] = MULTIMODAAL_CODE
    resultaat["beschikbare_modi"] = ", ".join(modi)
    resultaat["aantal_modaliteiten_bereikbaar"] = bereikbaar.sum(axis=1).astype(int)
    resultaat["aantal_modaliteiten_binnen_norm"] = binnen.sum(axis=1).astype(int)
    resultaat["snelste_modus"] = snelste_modus
    resultaat["snelste_modaliteit"] = snelste_modus.map(MODUS_LABELS)
    resultaat["gekozen_multimodale_modus"] = gekozen_modus
    resultaat["gekozen_multimodale_modaliteit"] = gekozen_modus.map(MODUS_LABELS)
    resultaat[multimodale_bereikbaar_kolom()] = bereikbaar.any(axis=1)
    resultaat[multimodale_binnen_kolom()] = binnen.any(axis=1)

    resultaat[multimodale_tijd_kolom()] = pd.NA
    resultaat[multimodale_norm_kolom()] = pd.NA
    for modus in modi:
        mask = gekozen_modus.eq(modus)
        resultaat.loc[mask, multimodale_tijd_kolom()] = tijden.loc[mask, modus]
        resultaat.loc[mask, multimodale_norm_kolom()] = normen.loc[mask, modus]

    resultaat["multimodale_keuze_type"] = "geen_route"
    resultaat.loc[
        resultaat[multimodale_bereikbaar_kolom()]
        & ~resultaat[multimodale_binnen_kolom()],
        "multimodale_keuze_type",
    ] = "snelste_bereikbare_modus_buiten_norm"
    resultaat.loc[
        resultaat[multimodale_binnen_kolom()],
        "multimodale_keuze_type",
    ] = "snelste_binnen_norm_modus"
    resultaat["multimodale_methode"] = (
        "binnen_norm_als_minstens_een_geselecteerde_modaliteit_voldoet"
    )
    for kolom in [multimodale_tijd_kolom(), multimodale_norm_kolom()]:
        resultaat[kolom] = pd.to_numeric(
            resultaat[kolom],
            errors="coerce",
        ).round(2)
    resultaat = resultaat.drop(columns=["_pand_id_norm", "_volgorde"])
    return voeg_multimodale_stijl_toe(
        gpd.GeoDataFrame(resultaat, geometry="geometry", crs=eerste.crs)
    )


def dominante_modus_per_gebied(
    panden: gpd.GeoDataFrame,
    groep: list[str],
) -> pd.DataFrame:
    keuze = panden[
        panden["gekozen_multimodale_modus"].fillna("").astype(str).str.strip().ne("")
    ].copy()
    if keuze.empty:
        return pd.DataFrame(columns=groep)

    telling = (
        keuze.groupby(groep + ["gekozen_multimodale_modus"], dropna=False)
        .agg(panden_met_modus=("pand_id", "count"))
        .reset_index()
        .sort_values(
            groep + ["panden_met_modus"],
            ascending=[True] * len(groep) + [False],
        )
    )
    dominant = telling.groupby(groep, dropna=False).head(1).copy()
    dominant = dominant.rename(
        columns={
            "gekozen_multimodale_modus": "dominante_multimodale_modus",
            "panden_met_modus": "panden_dominante_multimodale_modus",
        }
    )
    dominant["dominante_multimodale_modaliteit"] = dominant[
        "dominante_multimodale_modus"
    ].map(MODUS_LABELS)
    return dominant


def maak_multimodale_buurtsamenvatting(
    panden: gpd.GeoDataFrame,
) -> pd.DataFrame:
    tijd_kolom = multimodale_tijd_kolom()
    bereikbaar_kolom = multimodale_bereikbaar_kolom()
    binnen_kolom = multimodale_binnen_kolom()

    groep = ["buurtcode", "buurtnaam", "gemeentecode", "gemeentenaam"]
    samenvatting = (
        panden.groupby(groep, dropna=False)
        .agg(
            panden_aantal=("pand_id", "count"),
            panden_bereikbaar=(bereikbaar_kolom, "sum"),
            panden_binnen_norm=(binnen_kolom, "sum"),
            reistijd_mediaan_min=(tijd_kolom, "median"),
            reistijd_p90_min=(tijd_kolom, lambda s: s.quantile(0.9)),
            mediaan_modaliteiten_binnen_norm=(
                "aantal_modaliteiten_binnen_norm",
                "median",
            ),
        )
        .reset_index()
    )
    samenvatting["panden_niet_bereikbaar"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_bereikbaar"]
    )
    samenvatting["panden_niet_binnen_norm"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_binnen_norm"]
    )
    samenvatting["percentage_bereikbaar"] = (
        samenvatting["panden_bereikbaar"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_binnen_norm"] = (
        samenvatting["panden_binnen_norm"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting[["reistijd_mediaan_min", "reistijd_p90_min"]] = samenvatting[
        ["reistijd_mediaan_min", "reistijd_p90_min"]
    ].round(2)
    samenvatting["modus"] = MULTIMODAAL_MODUS
    samenvatting["modaliteit_code"] = MULTIMODAAL_CODE
    dominant = dominante_modus_per_gebied(panden, groep)
    return samenvatting.merge(dominant, on=groep, how="left")


def maak_multimodale_gemeentesamenvatting(
    panden: gpd.GeoDataFrame,
) -> pd.DataFrame:
    tijd_kolom = multimodale_tijd_kolom()
    bereikbaar_kolom = multimodale_bereikbaar_kolom()
    binnen_kolom = multimodale_binnen_kolom()

    groep = ["gemeentecode", "gemeentenaam"]
    samenvatting = (
        panden.groupby(groep, dropna=False)
        .agg(
            panden_aantal=("pand_id", "count"),
            panden_bereikbaar=(bereikbaar_kolom, "sum"),
            panden_binnen_norm=(binnen_kolom, "sum"),
            reistijd_mediaan_min=(tijd_kolom, "median"),
            reistijd_p90_min=(tijd_kolom, lambda s: s.quantile(0.9)),
        )
        .reset_index()
    )
    samenvatting["panden_niet_bereikbaar"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_bereikbaar"]
    )
    samenvatting["panden_niet_binnen_norm"] = (
        samenvatting["panden_aantal"] - samenvatting["panden_binnen_norm"]
    )
    samenvatting["percentage_bereikbaar"] = (
        samenvatting["panden_bereikbaar"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting["percentage_binnen_norm"] = (
        samenvatting["panden_binnen_norm"] / samenvatting["panden_aantal"] * 100
    ).round(1)
    samenvatting[["reistijd_mediaan_min", "reistijd_p90_min"]] = samenvatting[
        ["reistijd_mediaan_min", "reistijd_p90_min"]
    ].round(2)
    samenvatting["modus"] = MULTIMODAAL_MODUS
    samenvatting["modaliteit_code"] = MULTIMODAAL_CODE
    dominant = dominante_modus_per_gebied(panden, groep)
    return samenvatting.merge(dominant, on=groep, how="left")


def schrijf_output(
    panden: gpd.GeoDataFrame,
    modus: str,
    pandpolygonen: gpd.GeoDataFrame | None = None,
) -> None:
    output_dir = output_basis_dir() / modus
    tabel_output_dir = tabel_output_basis_dir() / modus
    output_dir.mkdir(parents=True, exist_ok=True)
    tabel_output_dir.mkdir(parents=True, exist_ok=True)
    code = MODUS_CODES[modus]

    samenvatting = maak_buurtsamenvatting(panden, modus)
    gemeentesamenvatting = maak_gemeentesamenvatting(panden, modus)
    buurtpolygonen = maak_buurtpolygonen(samenvatting, modus)
    buurtpolygonen_kleur = voeg_buurtkleuren_toe(buurtpolygonen)

    prefix = pandlaag_prefix(modus)
    panden_pad = output_dir / f"{prefix}.gpkg"
    norm_status_pad = output_dir / f"{prefix}_norm_status.gpkg"
    binnen_pad = output_dir / f"{prefix}_binnen_norm.gpkg"
    niet_pad = output_dir / f"{prefix}_buiten_norm.gpkg"
    buurtlaag_naam = f"{buurtlaag_prefix()}_buurten_{code}_kleur"
    buurtpolygonen_kleur_pad = output_dir / f"{buurtlaag_naam}.gpkg"
    buurten_csv_pad = tabel_output_dir / f"buurten_{code}.csv"
    gemeenten_csv_pad = tabel_output_dir / f"gemeenten_{code}.csv"

    binnen_kolom = maak_binnen_kolom(modus)
    panden_kaart = voeg_normstatus_stijl_toe(panden, modus)
    binnen = panden_kaart[panden_kaart[binnen_kolom].astype(bool)].copy()
    niet = panden_kaart[~panden_kaart[binnen_kolom].astype(bool)].copy()
    buurtpolygonen_publicatie = opgeschoonde_buurtkaart(buurtpolygonen_kleur)

    schrijf_gpkg_atomic(
        opgeschoonde_pandkaart(panden_kaart, modus).to_crs(CRS_WGS84),
        panden_pad,
        layer=prefix,
    )
    if pandpolygonen is None:
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(panden_kaart, modus).to_crs(CRS_WGS84),
            norm_status_pad,
            layer=f"{prefix}_norm_status",
        )
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(binnen, modus).to_crs(CRS_WGS84),
            binnen_pad,
            layer=f"{prefix}_binnen_norm",
        )
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(niet, modus).to_crs(CRS_WGS84),
            niet_pad,
            layer=f"{prefix}_buiten_norm",
        )
    else:
        panden_polygonen = maak_pandpolygonen_met_analyse(
            panden_kaart,
            pandpolygonen,
            modus,
        )
        resultaat_binnen = panden_polygonen[
            panden_polygonen[binnen_kolom].astype(bool)
        ].copy()
        resultaat_niet = panden_polygonen[
            ~panden_polygonen[binnen_kolom].astype(bool)
        ].copy()
        schrijf_gpkg_atomic(
            panden_polygonen.to_crs(CRS_WGS84),
            norm_status_pad,
            layer=f"{prefix}_norm_status",
        )
        schrijf_gpkg_atomic(
            resultaat_binnen.to_crs(CRS_WGS84),
            binnen_pad,
            layer=f"{prefix}_binnen_norm",
        )
        schrijf_gpkg_atomic(
            resultaat_niet.to_crs(CRS_WGS84),
            niet_pad,
            layer=f"{prefix}_buiten_norm",
        )

    schrijf_gpkg_atomic(
        buurtpolygonen_publicatie.to_crs(CRS_WGS84),
        buurtpolygonen_kleur_pad,
        layer=buurtlaag_naam,
    )
    schrijf_csv_atomic(samenvatting, buurten_csv_pad)
    schrijf_csv_atomic(gemeentesamenvatting, gemeenten_csv_pad)

    tijd_kolom = maak_tijd_kolom(modus)
    print(f"Opgeslagen: {panden_pad}")
    print(f"Opgeslagen: {norm_status_pad}")
    print(f"Opgeslagen: {binnen_pad}")
    print(f"Opgeslagen: {niet_pad}")
    print(f"Opgeslagen: {buurtpolygonen_kleur_pad}")
    print(f"Opgeslagen: {buurten_csv_pad}")
    print(f"Opgeslagen: {gemeenten_csv_pad}")
    print(f"Panden met reistijd ({modus}): {int(panden[tijd_kolom].notna().sum())}")
    print(f"Panden binnen norm ({modus}): {int(panden[binnen_kolom].sum())}")


def schrijf_multimodale_output(
    resultaten_per_modus: dict[str, gpd.GeoDataFrame],
    pandpolygonen: gpd.GeoDataFrame | None = None,
) -> None:
    resultaten_per_modus = vul_ontbrekende_modaliteiten_aan(resultaten_per_modus)
    ontbrekende_modi = sorted(ALLE_MODI - set(resultaten_per_modus))
    if ontbrekende_modi:
        print(
            "Multimodale bereikbaarheidsoutput overgeslagen; "
            "niet alle modaliteitsbestanden zijn aanwezig. "
            f"Ontbreekt: {', '.join(ontbrekende_modi)}"
        )
        return

    panden = maak_multimodale_panden(resultaten_per_modus)
    if panden.empty:
        print("Geen multimodale bereikbaarheidsoutput gemaakt.")
        return

    output_dir = output_basis_dir() / MULTIMODAAL_MODUS
    tabel_output_dir = tabel_output_basis_dir() / MULTIMODAAL_MODUS
    output_dir.mkdir(parents=True, exist_ok=True)
    tabel_output_dir.mkdir(parents=True, exist_ok=True)

    samenvatting = maak_multimodale_buurtsamenvatting(panden)
    gemeentesamenvatting = maak_multimodale_gemeentesamenvatting(panden)
    buurtpolygonen = maak_buurtpolygonen(samenvatting, MULTIMODAAL_MODUS)
    buurtpolygonen_kleur = voeg_buurtkleuren_toe(buurtpolygonen)

    prefix = multimodale_pandlaag_prefix()
    panden_pad = output_dir / f"{prefix}.gpkg"
    norm_status_pad = output_dir / f"{prefix}_norm_status.gpkg"
    binnen_pad = output_dir / f"{prefix}_binnen_norm.gpkg"
    niet_pad = output_dir / f"{prefix}_buiten_norm.gpkg"
    buurtlaag_naam = f"{buurtlaag_prefix()}_buurten_mul_kleur"
    buurtpolygonen_kleur_pad = output_dir / f"{buurtlaag_naam}.gpkg"
    buurten_csv_pad = tabel_output_dir / "buurten_mul.csv"
    gemeenten_csv_pad = tabel_output_dir / "gemeenten_mul.csv"

    binnen_kolom = multimodale_binnen_kolom()
    binnen = panden[panden[binnen_kolom].astype(bool)].copy()
    niet = panden[~panden[binnen_kolom].astype(bool)].copy()
    buurtpolygonen_publicatie = opgeschoonde_buurtkaart(buurtpolygonen_kleur)

    schrijf_gpkg_atomic(
        opgeschoonde_pandkaart(panden, MULTIMODAAL_MODUS).to_crs(CRS_WGS84),
        panden_pad,
        layer=prefix,
    )
    if pandpolygonen is None:
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(panden, MULTIMODAAL_MODUS).to_crs(CRS_WGS84),
            norm_status_pad,
            layer=f"{prefix}_norm_status",
        )
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(binnen, MULTIMODAAL_MODUS).to_crs(CRS_WGS84),
            binnen_pad,
            layer=f"{prefix}_binnen_norm",
        )
        schrijf_gpkg_atomic(
            opgeschoonde_pandkaart(niet, MULTIMODAAL_MODUS).to_crs(CRS_WGS84),
            niet_pad,
            layer=f"{prefix}_buiten_norm",
        )
    else:
        panden_polygonen = maak_pandpolygonen_met_analyse(
            panden,
            pandpolygonen,
            MULTIMODAAL_MODUS,
        )
        resultaat_binnen = panden_polygonen[
            panden_polygonen[binnen_kolom].astype(bool)
        ].copy()
        resultaat_niet = panden_polygonen[
            ~panden_polygonen[binnen_kolom].astype(bool)
        ].copy()
        schrijf_gpkg_atomic(
            panden_polygonen.to_crs(CRS_WGS84),
            norm_status_pad,
            layer=f"{prefix}_norm_status",
        )
        schrijf_gpkg_atomic(
            resultaat_binnen.to_crs(CRS_WGS84),
            binnen_pad,
            layer=f"{prefix}_binnen_norm",
        )
        schrijf_gpkg_atomic(
            resultaat_niet.to_crs(CRS_WGS84),
            niet_pad,
            layer=f"{prefix}_buiten_norm",
        )

    schrijf_gpkg_atomic(
        buurtpolygonen_publicatie.to_crs(CRS_WGS84),
        buurtpolygonen_kleur_pad,
        layer=buurtlaag_naam,
    )
    schrijf_csv_atomic(samenvatting, buurten_csv_pad)
    schrijf_csv_atomic(gemeentesamenvatting, gemeenten_csv_pad)

    print(f"Opgeslagen: {panden_pad}")
    print(f"Opgeslagen: {norm_status_pad}")
    print(f"Opgeslagen: {binnen_pad}")
    print(f"Opgeslagen: {niet_pad}")
    print(f"Opgeslagen: {buurtpolygonen_kleur_pad}")
    print(f"Opgeslagen: {buurten_csv_pad}")
    print(f"Opgeslagen: {gemeenten_csv_pad}")
    print(
        "Panden binnen norm (multimodaal): "
        f"{int(panden[binnen_kolom].sum())}"
    )


def schrijf_voorbeeldroute(
    route: gpd.GeoDataFrame,
    modus: str,
    punten: gpd.GeoDataFrame | None = None,
) -> None:
    if route is None or route.empty:
        print(f"Geen voorbeeldroute beschikbaar voor {modus}.")
        return

    pad = voorbeeldroute_pad(modus)
    pad.parent.mkdir(parents=True, exist_ok=True)
    punten_wgs84 = (
        punten.to_crs(CRS_WGS84)
        if punten is not None and not punten.empty
        else None
    )
    schrijf_voorbeeld_gpkg_atomic(route.to_crs(CRS_WGS84), punten_wgs84, pad)
    print(f"Opgeslagen voorbeeldroute ({modus}): {pad}")
