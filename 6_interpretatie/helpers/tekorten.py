"""Combineer buurtresultaten tot een DUS-tekortdiagnose."""

from __future__ import annotations

import pandas as pd

from .invoer import buurt_csv_pad, controleer_kolommen, normaliseer_gemeentecode
from .instellingen import ERNSTIGE_GRENS_PERCENTAGE, MODI, SIGNAALGRENS_PERCENTAGE


def ernstklasse(row) -> str:
    beste = row.get("beste_percentage_binnen_norm")
    slechtste = row.get("slechtste_percentage_binnen_norm")
    onvoldoende = row.get("aantal_modaliteiten_onvoldoende", 0)
    if pd.isna(beste):
        return "geen data"
    if onvoldoende == 0:
        return "voldoende"
    if beste < ERNSTIGE_GRENS_PERCENTAGE:
        return "ernstig tekort"
    if slechtste >= ERNSTIGE_GRENS_PERCENTAGE:
        return "licht tekort"
    if onvoldoende <= 2:
        return "matig tekort"
    return "ernstig tekort"


def probleemtype(row) -> str:
    scores = {modus: row.get(f"percentage_binnen_norm_{modus}") for modus in MODI}
    geldig = {k: v for k, v in scores.items() if pd.notna(v)}
    if not geldig:
        return "geen data"
    lopen_fiets = max(
        [
            row.get("percentage_binnen_norm_lopen", 0),
            row.get("percentage_binnen_norm_fiets", 0),
        ]
    )
    ov = max(
        [
            row.get("percentage_binnen_norm_ov_lopen", 0),
            row.get("percentage_binnen_norm_ov_fiets", 0),
        ]
    )
    auto = row.get("percentage_binnen_norm_auto", 0)
    onvoldoende = [
        modus
        for modus, waarde in geldig.items()
        if pd.notna(waarde) and waarde < SIGNAALGRENS_PERCENTAGE
    ]
    if not onvoldoende:
        return "voldoende"
    if (
        lopen_fiets < ERNSTIGE_GRENS_PERCENTAGE
        and ov < ERNSTIGE_GRENS_PERCENTAGE
        and auto < ERNSTIGE_GRENS_PERCENTAGE
    ):
        return "multimodaal_tekort"
    if lopen_fiets < SIGNAALGRENS_PERCENTAGE and auto >= SIGNAALGRENS_PERCENTAGE:
        return "nabijheid_actieve_mobiliteit_tekort"
    if ov < SIGNAALGRENS_PERCENTAGE and lopen_fiets >= SIGNAALGRENS_PERCENTAGE:
        return "ov_tekort"
    if auto < SIGNAALGRENS_PERCENTAGE and lopen_fiets >= SIGNAALGRENS_PERCENTAGE:
        return "auto_tekort"
    return "gemengd_tekort"


def maak_tekortdiagnose() -> pd.DataFrame:
    basis = None
    for modus in MODI:
        pad = buurt_csv_pad(modus)
        if not pad.exists():
            raise FileNotFoundError(pad)
        df = pd.read_csv(
            pad,
            dtype={"buurtcode": "object", "gemeentecode": "object"},
        )
        kolommen = [
            "buurtcode",
            "buurtnaam",
            "gemeentecode",
            "gemeentenaam",
            "panden_aantal",
            "panden_met_reistijd",
            "panden_binnen_norm",
            "percentage_met_reistijd",
            "percentage_binnen_norm",
            "reistijd_mediaan_min",
            "reistijd_p90_min",
        ]
        controleer_kolommen(df, kolommen, str(pad))
        df["gemeentecode"] = normaliseer_gemeentecode(df["gemeentecode"])
        df = df[kolommen].rename(
            columns={
                "panden_met_reistijd": f"panden_met_reistijd_{modus}",
                "panden_binnen_norm": f"panden_binnen_norm_{modus}",
                "percentage_met_reistijd": f"percentage_met_reistijd_{modus}",
                "percentage_binnen_norm": f"percentage_binnen_norm_{modus}",
                "reistijd_mediaan_min": f"reistijd_mediaan_min_{modus}",
                "reistijd_p90_min": f"reistijd_p90_min_{modus}",
            }
        )
        if basis is None:
            basis = df
        else:
            basis = basis.merge(
                df.drop(
                    columns=[
                        "buurtnaam",
                        "gemeentecode",
                        "gemeentenaam",
                        "panden_aantal",
                    ]
                ),
                on="buurtcode",
                how="outer",
            )

    diagnose = basis.copy()
    percentage_kolommen = [f"percentage_binnen_norm_{modus}" for modus in MODI]
    diagnose["beste_percentage_binnen_norm"] = diagnose[percentage_kolommen].max(axis=1)
    diagnose["slechtste_percentage_binnen_norm"] = diagnose[percentage_kolommen].min(axis=1)
    diagnose["duurzame_percentage_binnen_norm"] = diagnose[
        [
            "percentage_binnen_norm_lopen",
            "percentage_binnen_norm_fiets",
            "percentage_binnen_norm_ov_lopen",
            "percentage_binnen_norm_ov_fiets",
        ]
    ].max(axis=1)
    diagnose["aantal_modaliteiten_onvoldoende"] = (
        diagnose[percentage_kolommen].lt(SIGNAALGRENS_PERCENTAGE).sum(axis=1)
    )
    diagnose["alle_modaliteiten_voldoende"] = diagnose["aantal_modaliteiten_onvoldoende"].eq(0)
    diagnose["modaliteiten_onvoldoende"] = diagnose.apply(
        lambda row: ", ".join(
            modus
            for modus in MODI
            if pd.notna(row.get(f"percentage_binnen_norm_{modus}"))
            and row.get(f"percentage_binnen_norm_{modus}") < SIGNAALGRENS_PERCENTAGE
        ),
        axis=1,
    )
    diagnose["beste_modus"] = diagnose[percentage_kolommen].idxmax(axis=1).str.replace(
        "percentage_binnen_norm_",
        "",
        regex=False,
    )
    diagnose["slechtste_modus"] = diagnose[percentage_kolommen].idxmin(axis=1).str.replace(
        "percentage_binnen_norm_",
        "",
        regex=False,
    )
    diagnose["probleemtype"] = diagnose.apply(probleemtype, axis=1)
    diagnose["ernstklasse"] = diagnose.apply(ernstklasse, axis=1)
    return diagnose


def main() -> pd.DataFrame:
    diagnose = maak_tekortdiagnose()
    print("Tekortdiagnose gemaakt in geheugen; geen aparte CSV opgeslagen.")
    return diagnose


if __name__ == "__main__":
    main()
