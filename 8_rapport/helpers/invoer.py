from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyogrio

from .instellingen import (
    BASE_DIR,
    MODI,
    MODUS_LABELS,
    NIET_AUTO_MODI,
    VoorzieningRun,
    bestaande_pandlaag,
    voorziening_label,
)

def veilige_kolom(df: pd.DataFrame, kolom: str, default: object = "") -> pd.Series:
    if kolom in df.columns:
        return df[kolom]
    return pd.Series([default] * len(df), index=df.index)


def detecteer_voorzieningen() -> list[VoorzieningRun]:
    basis = BASE_DIR / "5_bereikbaarheid" / "processed"
    runs: list[VoorzieningRun] = []
    for pad in sorted(basis.iterdir()):
        if not pad.is_dir():
            continue
        if pad.name == "onderwijs":
            for niveau in sorted(p for p in pad.iterdir() if p.is_dir()):
                rel = Path("5_bereikbaarheid") / "processed" / "onderwijs" / niveau.name
                pand_rel = Path("0_layers") / "processed" / "5_bereikbaarheid" / "onderwijs" / niveau.name
                runs.append(
                    VoorzieningRun(
                        slug=f"onderwijs_{niveau.name}",
                        label=voorziening_label(f"onderwijs_{niveau.name}"),
                        analyse_naam="onderwijs",
                        bestandsnaam_prefix=niveau.name,
                        bereikbaarheid_rel=rel,
                        pandlagen_rel=pand_rel,
                        dus_rel=Path("6_interpretatie") / "processed" / "onderwijs" / niveau.name,
                    )
                )
        else:
            rel = Path("5_bereikbaarheid") / "processed" / pad.name
            runs.append(
                VoorzieningRun(
                    slug=pad.name,
                    label=voorziening_label(pad.name),
                    analyse_naam=pad.name,
                    bestandsnaam_prefix=pad.name,
                    bereikbaarheid_rel=rel,
                    pandlagen_rel=Path("0_layers") / "processed" / "5_bereikbaarheid" / pad.name,
                    dus_rel=Path("6_interpretatie") / "processed" / pad.name,
                )
            )

    beschikbaar = []
    for run in runs:
        compleet = True
        for modus_item in MODI:
            modus = modus_item[0]
            code = modus_item[1]
            for naam in [f"gemeenten_{code}.csv", f"buurten_{code}.csv"]:
                if not (BASE_DIR / run.bereikbaarheid_rel / modus / naam).exists():
                    compleet = False
            if not (BASE_DIR / bestaande_pandlaag(run, modus, code)).exists():
                compleet = False
        if compleet:
            beschikbaar.append(run)
    return beschikbaar


def lees_gemeenten(run: VoorzieningRun, modus: str, code: str) -> pd.DataFrame:
    pad = BASE_DIR / run.bereikbaarheid_rel / modus / f"gemeenten_{code}.csv"
    df = pd.read_csv(pad, dtype={"gemeentecode": "string"})
    df["Voorziening"] = run.label
    df["Modaliteit"] = MODUS_LABELS[modus]
    df["modus"] = modus
    return df


def lees_buurten(run: VoorzieningRun, modus: str, code: str) -> pd.DataFrame:
    pad = BASE_DIR / run.bereikbaarheid_rel / modus / f"buurten_{code}.csv"
    df = pd.read_csv(
        pad,
        dtype={"buurtcode": "string", "gemeentecode": "string"},
    )
    df["Voorziening"] = run.label
    df["Modaliteit"] = MODUS_LABELS[modus]
    df["modus"] = modus
    return df


def read_pandlaag(run: VoorzieningRun, modus: str, code: str) -> pd.DataFrame:
    rel = bestaande_pandlaag(run, modus, code)
    pad = BASE_DIR / rel
    binnen = f"binnen_norm_{run.analyse_naam}_{modus}"
    norm = f"norm_{run.analyse_naam}_{modus}_min"
    cols = [
        "pand_id",
        "buurtcode",
        "buurtnaam",
        "gemeentecode",
        "gemeentenaam",
        binnen,
        norm,
    ]
    df = pyogrio.read_dataframe(pad, columns=cols, read_geometry=False)
    df = df.rename(columns={binnen: f"binnen_{modus}", norm: f"norm_{modus}"})
    df["pand_id"] = df["pand_id"].astype("string")
    return df


def lees_pandstatus(run: VoorzieningRun) -> pd.DataFrame:
    basis_cols = ["pand_id", "buurtcode", "buurtnaam", "gemeentecode", "gemeentenaam"]
    status: pd.DataFrame | None = None
    for modus_item in MODI:
        modus = modus_item[0]
        code = modus_item[1]
        df = read_pandlaag(run, modus, code)
        cols = basis_cols + [f"binnen_{modus}", f"norm_{modus}"]
        df = df[cols].copy()
        df[f"binnen_{modus}"] = df[f"binnen_{modus}"].fillna(False).astype(bool)
        if status is None:
            status = df
        else:
            status = status.merge(
                df[["pand_id", f"binnen_{modus}", f"norm_{modus}"]],
                on="pand_id",
                how="inner",
            )
    if status is None:
        raise ValueError(f"Geen pandstatus gelezen voor {run.label}")

    binnen_cols = [f"binnen_{modus_item[0]}" for modus_item in MODI]
    status["aantal_modaliteiten_voldoende"] = status[binnen_cols].sum(axis=1)
    status["aantal_modaliteiten_onvoldoende"] = len(MODI) - status[
        "aantal_modaliteiten_voldoende"
    ]
    status["geen_enkele_modaliteit_voldoet"] = status["aantal_modaliteiten_voldoende"].eq(0)
    status["alle_modaliteiten_voldoen"] = status["aantal_modaliteiten_onvoldoende"].eq(0)
    status["alleen_auto_voldoet"] = (
        status["binnen_auto"]
        & ~status[[f"binnen_{modus}" for modus in NIET_AUTO_MODI]].any(axis=1)
    )
    status["zonder_auto_bereikbaar"] = status[
        [f"binnen_{modus}" for modus in NIET_AUTO_MODI]
    ].any(axis=1)
    status["lopen_of_fiets_voldoet"] = status[["binnen_lopen", "binnen_fiets"]].any(axis=1)
    status["alleen_ov_voldoet"] = (
        status[["binnen_ov_lopen", "binnen_ov_fiets"]].any(axis=1)
        & ~status[["binnen_lopen", "binnen_fiets", "binnen_auto"]].any(axis=1)
    )
    return status
