"""FSN-knooppuntbereikbaarheid per woonpand.

Deze losse analyse behandelt centrale FSN-OV-knooppunten als tijdelijke
voorzieningen en gebruikt de bestaande `5_bereikbaarheid`-workflow. Daarmee
wordt per woonpand in de vier FSN-gemeenten berekend of een gekozen knooppunt
binnen de norm bereikbaar is.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass
from importlib import import_module
import importlib.util
from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

CRS_WGS84 = "EPSG:4326"
FSN_GEMEENTEN = {
    "0080": "Leeuwarden",
    "0074": "Heerenveen",
    "0090": "Smallingerland / Drachten",
    "1900": "Súdwest-Fryslân / Sneek",
}

NORMEN_30_MIN = {
    "lopen": 30.0,
    "fiets": 30.0,
    "auto": 30.0,
    "ov_lopen": 30.0,
    "ov_fiets": 30.0,
}
MODI = ("lopen", "fiets", "auto", "ov_lopen", "ov_fiets")


@dataclass(frozen=True)
class Knooppunt:
    stad: str
    slug: str
    halte_ids: tuple[str, ...]
    naam: str


KNOOPPUNTEN = [
    Knooppunt(
        stad="Drachten",
        slug="drachten",
        halte_ids=("18729", "18731", "18733", "18734"),
        naam="Van Knobelsdorffplein, Drachten",
    ),
    Knooppunt(
        stad="Heerenveen",
        slug="heerenveen",
        halte_ids=("18663", "18664"),
        naam="Station Heerenveen",
    ),
    Knooppunt(
        stad="Leeuwarden",
        slug="leeuwarden",
        halte_ids=("22029", "22030", "22042"),
        naam="Station/Busstation Leeuwarden",
    ),
    Knooppunt(
        stad="Sneek",
        slug="sneek",
        halte_ids=("22223", "22224"),
        naam="Station Sneek",
    ),
]


def norm_id(waarde) -> str:
    if waarde is None or pd.isna(waarde):
        return ""
    tekst = str(waarde).strip()
    if tekst.endswith(".0"):
        tekst = tekst[:-2]
    return tekst


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bestemmingen",
        default="all",
        help="Kommalijst: drachten,heerenveen,leeuwarden,sneek of all.",
    )
    parser.add_argument(
        "--modus",
        choices=MODI,
        default="fiets",
        help="Modaliteit om te testen.",
    )
    parser.add_argument("--zonder-pandpolygonen", action="store_true")
    return parser.parse_args()


def gekozen_knooppunten(waarde: str) -> list[Knooppunt]:
    if waarde == "all":
        return KNOOPPUNTEN
    slugs = {deel.strip() for deel in waarde.split(",") if deel.strip()}
    onbekend = sorted(slugs - {k.slug for k in KNOOPPUNTEN})
    if onbekend:
        raise ValueError(f"Onbekende bestemmingen: {', '.join(onbekend)}")
    return [k for k in KNOOPPUNTEN if k.slug in slugs]


def laad_bereikbaarheid_config():
    config_pad = BASE_DIR / "5_bereikbaarheid" / "config.py"
    bereikbaarheid_dir = str(BASE_DIR / "5_bereikbaarheid")
    if bereikbaarheid_dir not in sys.path:
        sys.path.insert(0, bereikbaarheid_dir)

    spec = importlib.util.spec_from_file_location(
        "bereikbaarheid_run_config",
        config_pad,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Kan bereikbaarheidsconfig niet laden: {config_pad}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lees_ov_haltes() -> gpd.GeoDataFrame:
    pad = BASE_DIR / "0_layers" / "processed" / "4_netwerk" / "ov" / "line_total_stop_points.geojson"
    haltes = gpd.read_file(pad).to_crs(CRS_WGS84)
    haltes["halte_id_norm"] = haltes["halte_id"].apply(norm_id)
    return haltes


def maak_knooppuntlaag(knooppunt: Knooppunt, out_dir: Path) -> Path:
    haltes = lees_ov_haltes()
    selectie = haltes[
        haltes["halte_id_norm"].isin(knooppunt.halte_ids)
    ].copy()
    if selectie.empty:
        raise ValueError(f"Geen haltepunten gevonden voor {knooppunt.naam}.")

    geom = selectie.to_crs("EPSG:28992").geometry.union_all().centroid
    laag = gpd.GeoDataFrame(
        [
            {
                "naam": knooppunt.naam,
                "fsn_stad": knooppunt.stad,
                "fsn_slug": knooppunt.slug,
                "halte_ids": ",".join(knooppunt.halte_ids),
                "geometry": geom,
            }
        ],
        geometry="geometry",
        crs="EPSG:28992",
    ).to_crs(CRS_WGS84)

    out_dir.mkdir(parents=True, exist_ok=True)
    pad = out_dir / f"fsn_knooppunt_{knooppunt.slug}.gpkg"
    if pad.exists():
        pad.unlink()
    laag.to_file(pad, layer=f"fsn_knooppunt_{knooppunt.slug}", driver="GPKG")
    return pad


def registreer_fsn_voorziening(config_module, knooppunt: Knooppunt, laag_pad: Path) -> str:
    voorziening_naam = f"fsn_{knooppunt.slug}"
    config_module.PRESETS[voorziening_naam] = config_module.VoorzieningConfig(
        naam=voorziening_naam,
        label=f"FSN-knooppunt {knooppunt.stad}",
        pluralis=f"FSN-knooppunten {knooppunt.stad}",
        layer=f"fsn_knooppunt_{knooppunt.slug}",
        input_pad=laag_pad,
    )
    config_module.NORMEN_PER_VOORZIENING[voorziening_naam] = NORMEN_30_MIN.copy()
    return voorziening_naam


def maak_fsn_panden_filter(workflow_module):
    originele_lees_panden = workflow_module.lees_panden

    def lees_fsn_panden(jaar: int, pand_selectie: str):
        panden = originele_lees_panden(jaar, pand_selectie)
        gemeentecode = (
            panden["gemeentecode"]
            .astype(str)
            .str.strip()
            .str.upper()
            .str.removeprefix("GM")
            .str.zfill(4)
        )
        resultaat = panden[gemeentecode.isin(FSN_GEMEENTEN)].copy()
        print(f"FSN-woonpanden geselecteerd: {len(resultaat)}")
        return resultaat

    return lees_fsn_panden


def kopieer_output(
    voorziening_naam: str,
    knooppunt: Knooppunt,
    out_root: Path,
    case_label: str,
) -> None:
    doel = out_root / case_label / knooppunt.slug
    if doel.exists():
        shutil.rmtree(doel)
    doel.mkdir(parents=True, exist_ok=True)

    bron_tabel = BASE_DIR / "5_bereikbaarheid" / "processed" / voorziening_naam
    bron_lagen = BASE_DIR / "0_layers" / "processed" / "5_bereikbaarheid" / voorziening_naam

    if (bron_tabel / case_label).exists():
        shutil.copytree(bron_tabel / case_label, doel / "tabellen" / case_label)
    if (bron_lagen / case_label).exists():
        shutil.copytree(bron_lagen / case_label, doel / "lagen" / case_label)

    for basis, submap in [
        (bron_tabel, "tabellen"),
        (bron_lagen, "lagen"),
    ]:
        pandstromen = basis / "pandstromen"
        if pandstromen.exists():
            shutil.copytree(pandstromen, doel / submap / "pandstromen")


def schrijf_overzicht(knooppunten: list[Knooppunt], out_root: Path, case_labels: list[str]) -> None:
    rows = []
    for case_label in case_labels:
        for knooppunt in knooppunten:
            tabel_dir = out_root / case_label / knooppunt.slug / "tabellen"
            if not tabel_dir.exists():
                continue
            for csv_pad in sorted(tabel_dir.rglob("buurten_*.csv")):
                modus = csv_pad.stem.replace("buurten_", "")
                df = pd.read_csv(csv_pad)
                if df.empty or "panden_aantal" not in df.columns:
                    continue
                panden_aantal = df["panden_aantal"].sum()
                panden_binnen = df["panden_binnen_norm"].sum()
                rows.append(
                    {
                        "case": case_label,
                        "bestemming": knooppunt.stad,
                        "bestemming_knooppunt": knooppunt.naam,
                        "modus": modus,
                        "panden_aantal": int(panden_aantal),
                        "panden_binnen_norm": int(panden_binnen),
                        "percentage_binnen_norm": round(
                            panden_binnen / panden_aantal * 100 if panden_aantal else 0,
                            1,
                        ),
                        "buurten_aantal": int(len(df)),
                        "buurten_onder_80_pct": int((df["percentage_binnen_norm"] < 80).sum()),
                    }
                )
    if rows:
        pd.DataFrame(rows).to_csv(
            out_root / "fsn_knooppuntbereikbaarheid_overzicht.csv",
            index=False,
        )


def main() -> None:
    args = parse_args()
    knooppunten = gekozen_knooppunten(args.bestemmingen)
    case_label = args.modus
    out_root = BASE_DIR / "7_analyses" / "processed" / "fsn_knooppuntbereikbaarheid"
    laag_dir = out_root / "_knooppunten"
    out_root.mkdir(parents=True, exist_ok=True)

    run_config = laad_bereikbaarheid_config()
    config = import_module("5_bereikbaarheid.helpers.instellingen")
    workflow = import_module("5_bereikbaarheid.helpers.workflow")
    workflow.lees_panden = maak_fsn_panden_filter(workflow)

    print(
        "\n=== FSN-bereikbaarheid ===\n"
        f"modus={args.modus}, "
        f"ov_datum={run_config.RUN.ov_datum}, "
        f"ov_venster={run_config.RUN.ov_starttijd}-{run_config.RUN.ov_eindtijd}"
    )
    runtime_config = run_config.RuntimeConfig(
        jaar=run_config.RUN.jaar,
        pand_selectie="woonpanden",
        modi=args.modus,
        max_snap_meter=run_config.RUN.max_snap_meter,
        gebruik_pandpolygonen=(
            run_config.RUN.gebruik_pandpolygonen and not args.zonder_pandpolygonen
        ),
        max_parkeer_loop_min=run_config.RUN.max_parkeer_loop_min,
        max_ov_transfer_meter=run_config.RUN.max_ov_transfer_meter,
        ov_datum=run_config.RUN.ov_datum,
        ov_starttijd=run_config.RUN.ov_starttijd,
        ov_eindtijd=run_config.RUN.ov_eindtijd,
        ov_stap_minuten=run_config.RUN.ov_stap_minuten,
        min_overstap_min=run_config.RUN.min_overstap_min,
    )

    for knooppunt in knooppunten:
        print(f"\n=== FSN-knooppuntbereikbaarheid: {knooppunt.naam} ===")
        laag_pad = maak_knooppuntlaag(knooppunt, laag_dir)
        voorziening_naam = registreer_fsn_voorziening(config, knooppunt, laag_pad)
        workflow.run_bereikbaarheid(
            voorziening_naam,
            runtime_config=runtime_config,
            maak_pand_flowmaps=run_config.PAND_FLOWMAPS,
        )
        kopieer_output(voorziening_naam, knooppunt, out_root, case_label)

    schrijf_overzicht(knooppunten, out_root, [case_label])
    print(f"Klaar: {out_root}")


if __name__ == "__main__":
    main()
