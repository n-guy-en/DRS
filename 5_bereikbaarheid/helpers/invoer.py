"""Inleesfuncties voor de voorzieningbereikbaarheidsanalyse."""

import geopandas as gpd
import pandas as pd

from .instellingen import (
    BASE_DIR,
    CRS_RD,
    CRS_WGS84,
    ONDERWIJS_NIVEAU_NAMEN,
    current_config,
    voorzieningen_label,
)
from importlib import import_module

puntrepresentatie = import_module("5_bereikbaarheid.helpers.geometrie").puntrepresentatie


def normaliseer_id(waarde) -> str:
    if pd.isna(waarde):
        return ""
    tekst = str(waarde).strip()
    if tekst.endswith(".0"):
        tekst = tekst[:-2]
    return tekst


def panden_pad(modus: str):
    from .instellingen import MODUS_CODES, current_config, output_basis_dir, voorziening

    naam = current_config().onderwijsniveau or voorziening()
    return output_basis_dir() / modus / f"{naam}_{MODUS_CODES[modus]}.gpkg"


def controleer_kolommen(
    dataframe: gpd.GeoDataFrame | pd.DataFrame,
    naam: str,
    verplichte_kolommen: list[str],
) -> None:
    ontbrekend = sorted(set(verplichte_kolommen) - set(dataframe.columns))
    if ontbrekend:
        raise ValueError(f"Kolommen ontbreken in {naam}: {ontbrekend}")


def lees_panden(jaar: int, pand_selectie: str) -> gpd.GeoDataFrame:
    if pand_selectie not in {"woonpanden", "alle_panden"}:
        raise ValueError("PAND_SELECTIE moet 'woonpanden' of 'alle_panden' zijn.")

    pad = BASE_DIR / "0_layers" / "processed" / "2_bag" / "bag_panden.gpkg"
    print(f"Lees panden: {pad}")
    panden = gpd.read_file(pad).to_crs(CRS_RD)

    controleer_kolommen(
        panden,
        "bag_panden.gpkg",
        [
            "jaar",
            "pand_id",
            "is_woonpand",
            "buurtcode",
            "buurtnaam",
            "gemeentecode",
            "gemeentenaam",
            "geometry",
        ],
    )

    jaren = pd.to_numeric(panden["jaar"], errors="coerce").dropna().astype(int).unique()
    if len(jaren) != 1 or int(jaren[0]) != int(jaar):
        raise ValueError(
            "bag_panden.gpkg komt niet overeen met JAAR. "
            f"Verwacht {jaar}, gevonden {sorted(jaren.tolist())}."
        )

    if pand_selectie == "woonpanden":
        panden = panden[panden["is_woonpand"].fillna(False).astype(bool)].copy()
        print(f"Woonpanden geselecteerd: {len(panden)}")
    elif pand_selectie == "alle_panden":
        print(f"Alle panden geselecteerd: {len(panden)}")

    return puntrepresentatie(panden)


def lees_voorzieningen() -> gpd.GeoDataFrame:
    config = current_config()

    if config.naam == "onderwijs" and config.onderwijsniveau is None:
        return lees_onderwijsvoorzieningen()

    if config.input_pad is None:
        raise FileNotFoundError(f"Geen voorzieningenpad ingesteld voor {config.naam}.")

    print(f"Lees {voorzieningen_label()}: {config.input_pad}")
    voorzieningen = gpd.read_file(config.input_pad, layer=config.layer).to_crs(CRS_RD)
    controleer_kolommen(voorzieningen, config.input_pad.name, ["geometry"])
    return puntrepresentatie(voorzieningen)


def lees_onderwijsvoorzieningen() -> gpd.GeoDataFrame:
    basis_pad = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "onderwijs"
    )
    datasets = []

    for niveau, niveau_naam in ONDERWIJS_NIVEAU_NAMEN.items():
        pad = basis_pad / niveau / f"onderwijs_{niveau}.gpkg"
        layer = f"onderwijs_{niveau}"

        if not pad.exists():
            print(f"Onderwijsniveau ontbreekt, sla over: {pad}")
            continue

        print(f"Lees onderwijsvoorzieningen {niveau}: {pad}")
        dataset = gpd.read_file(pad, layer=layer).to_crs(CRS_RD)
        controleer_kolommen(dataset, f"{pad.name}:{layer}", ["bag_gevalideerd", "geometry"])
        dataset["onderwijs_niveau"] = niveau
        dataset["onderwijs_niveau_naam"] = niveau_naam
        datasets.append(dataset)

    if not datasets:
        raise FileNotFoundError(
            f"Geen onderwijsniveau-bestanden gevonden onder: {basis_pad}"
        )

    onderwijsvoorzieningen = gpd.GeoDataFrame(
        pd.concat(datasets, ignore_index=True, sort=False),
        geometry="geometry",
        crs=CRS_RD,
    )
    onderwijsvoorzieningen = onderwijsvoorzieningen[
        onderwijsvoorzieningen["bag_gevalideerd"].fillna(False).astype(bool)
    ].copy()
    return puntrepresentatie(onderwijsvoorzieningen)


def lees_pandpolygonen(jaar: int) -> gpd.GeoDataFrame:
    pad = (
        BASE_DIR
        / "2_bag"
        / "bag_frl_xml"
        / "per_jaar"
        / f"pnd_fryslan_{jaar}.geojson"
    )
    print(f"Lees BAG-pandpolygonen: {pad}")
    panden = gpd.read_file(pad)

    if panden.crs is None:
        panden = panden.set_crs(CRS_WGS84)

    if "pand_status" in panden.columns:
        panden = panden[panden["pand_status"] == "Pand in gebruik"].copy()

    return panden
