from __future__ import annotations

from pathlib import Path

import pandas as pd

from .instellingen import (
    MODI,
    MODUS_POSITIE,
    VoorzieningRun,
    bereikbaarheidsklasse,
    zichtbaar_ja_nee,
)
from .invoer import lees_buurten, lees_gemeenten

def norm_label(status: pd.DataFrame, modus: str) -> str:
    waarden = sorted(pd.to_numeric(status[f"norm_{modus}"], errors="coerce").dropna().unique())
    if not waarden:
        return ""
    if len(waarden) == 1:
        return f"{waarden[0]:g}"
    return "varieert: " + "/".join(f"{waarde:g}" for waarde in waarden)


def schrijf_csv(df: pd.DataFrame, pad: Path) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(pad, index=False)


def provinciale_modaliteiten(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    rows = []
    totaal = len(status)
    for modus_item in MODI:
        modus = modus_item[0]
        label = modus_item[2]
        binnen = int(status[f"binnen_{modus}"].sum())
        buiten = int(totaal - binnen)
        rows.append(
            {
                "Voorziening": run.label,
                "Modaliteit": label,
                "Reistijdnorm in minuten": norm_label(status, modus),
                "Totaal aantal woonpanden": totaal,
                "Woonpanden binnen de norm": binnen,
                "Woonpanden buiten de norm": buiten,
                "Percentage binnen de norm": round(binnen / totaal * 100, 1) if totaal else 0,
                "Percentage buiten de norm": round(buiten / totaal * 100, 1) if totaal else 0,
            }
        )
    return pd.DataFrame(rows)


def woonpanden_onvoldoende_modaliteiten(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    totaal = len(status)
    rows = []
    counts = status["aantal_modaliteiten_onvoldoende"].value_counts().to_dict()
    for aantal in range(0, 6):
        n = int(counts.get(aantal, 0))
        rows.append(
            {
                "Voorziening": run.label,
                "Aantal onvoldoende modaliteiten": aantal,
                "Aantal woonpanden": n,
                "Percentage woonpanden": round(n / totaal * 100, 1) if totaal else 0,
            }
        )
    return pd.DataFrame(rows)


def gemeentetabel(run: VoorzieningRun) -> pd.DataFrame:
    frames = []
    for modus_item in MODI:
        modus = modus_item[0]
        code = modus_item[1]
        df = lees_gemeenten(run, modus, code)
        if "panden_niet_binnen_norm" not in df.columns:
            df["panden_niet_binnen_norm"] = df["panden_aantal"] - df["panden_binnen_norm"]
        df["percentage_niet_binnen_norm"] = (
            df["panden_niet_binnen_norm"] / df["panden_aantal"] * 100
        ).round(1)
        frames.append(
            df[
                [
                    "Voorziening",
                    "gemeentecode",
                    "gemeentenaam",
                    "Modaliteit",
                    "panden_aantal",
                    "panden_binnen_norm",
                    "panden_niet_binnen_norm",
                    "percentage_binnen_norm",
                    "percentage_niet_binnen_norm",
                    "panden_bereikbaar",
                    "panden_niet_bereikbaar",
                    "reistijd_mediaan_min",
                    "reistijd_p90_min",
                ]
            ].rename(
                columns={
                    "gemeentecode": "Gemeentecode",
                    "gemeentenaam": "Gemeentenaam",
                    "panden_aantal": "Totaal aantal woonpanden",
                    "panden_binnen_norm": "Woonpanden binnen de norm",
                    "panden_niet_binnen_norm": "Woonpanden buiten de norm",
                    "percentage_binnen_norm": "Percentage binnen de norm",
                    "percentage_niet_binnen_norm": "Percentage buiten de norm",
                    "panden_bereikbaar": "Woonpanden met reistijd",
                    "panden_niet_bereikbaar": "Woonpanden zonder reistijd",
                    "reistijd_mediaan_min": "Mediaan reistijd in minuten",
                    "reistijd_p90_min": "P90 reistijd in minuten",
                }
            )
        )
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(
        ["Voorziening", "Modaliteit", "Woonpanden buiten de norm"],
        ascending=[True, True, False],
    )


def buurttabel(run: VoorzieningRun) -> pd.DataFrame:
    frames = []
    for modus_item in MODI:
        modus = modus_item[0]
        code = modus_item[1]
        df = lees_buurten(run, modus, code)
        df["panden_niet_binnen_norm"] = df["panden_aantal"] - df["panden_binnen_norm"]
        df["percentage_niet_binnen_norm"] = (
            df["panden_niet_binnen_norm"] / df["panden_aantal"] * 100
        ).round(1)
        df["Onder 80 procent woondekking"] = df["percentage_binnen_norm"].lt(80.0)
        frames.append(
            df[
                [
                    "Voorziening",
                    "gemeentecode",
                    "gemeentenaam",
                    "buurtcode",
                    "buurtnaam",
                    "Modaliteit",
                    "panden_aantal",
                    "panden_binnen_norm",
                    "panden_niet_binnen_norm",
                    "percentage_binnen_norm",
                    "percentage_niet_binnen_norm",
                    "panden_met_reistijd",
                    "percentage_met_reistijd",
                    "reistijd_mediaan_min",
                    "reistijd_p90_min",
                    "Onder 80 procent woondekking",
                ]
            ].rename(
                columns={
                    "gemeentecode": "Gemeentecode",
                    "gemeentenaam": "Gemeentenaam",
                    "buurtcode": "Buurtcode",
                    "buurtnaam": "Buurtnaam",
                    "panden_aantal": "Totaal aantal woonpanden",
                    "panden_binnen_norm": "Woonpanden binnen de norm",
                    "panden_niet_binnen_norm": "Woonpanden buiten de norm",
                    "percentage_binnen_norm": "Percentage binnen de norm",
                    "percentage_niet_binnen_norm": "Percentage buiten de norm",
                    "panden_met_reistijd": "Woonpanden met reistijd",
                    "percentage_met_reistijd": "Percentage met reistijd",
                    "reistijd_mediaan_min": "Mediaan reistijd in minuten",
                    "reistijd_p90_min": "P90 reistijd in minuten",
                }
            )
        )
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(
        [
            "Voorziening",
            "Modaliteit",
            "Percentage binnen de norm",
            "Woonpanden buiten de norm",
        ],
        ascending=[True, True, True, False],
    )


def autoafhankelijkheid(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    groep = ["gemeentecode", "gemeentenaam", "buurtcode", "buurtnaam"]
    agg = (
        status.groupby(groep, dropna=False)
        .agg(
            **{
                "Totaal aantal woonpanden": ("pand_id", "count"),
                "Woonpanden waarvoor alleen auto voldoet": ("alleen_auto_voldoet", "sum"),
                "Woonpanden zonder auto bereikbaar": ("zonder_auto_bereikbaar", "sum"),
                "Woonpanden waarvoor lopen of fiets voldoet": ("lopen_of_fiets_voldoet", "sum"),
                "Woonpanden waarvoor alleen OV voldoet": ("alleen_ov_voldoet", "sum"),
                "Woonpanden waarvoor geen enkele modaliteit voldoet": (
                    "geen_enkele_modaliteit_voldoet",
                    "sum",
                ),
            }
        )
        .reset_index()
    )
    for col in [
        "Woonpanden waarvoor alleen auto voldoet",
        "Woonpanden zonder auto bereikbaar",
        "Woonpanden waarvoor lopen of fiets voldoet",
        "Woonpanden waarvoor alleen OV voldoet",
        "Woonpanden waarvoor geen enkele modaliteit voldoet",
    ]:
        label = col.removeprefix("Woonpanden waarvoor ").removeprefix(
            "Woonpanden "
        )
        agg[f"Percentage {label}"] = (
            agg[col] / agg["Totaal aantal woonpanden"] * 100
        ).round(1)
    agg["Voorziening"] = run.label
    agg = agg.rename(
        columns={
            "gemeentecode": "Gemeentecode",
            "gemeentenaam": "Gemeentenaam",
            "buurtcode": "Buurtcode",
            "buurtnaam": "Buurtnaam",
        }
    )
    return agg.sort_values(
        ["Percentage alleen auto voldoet", "Woonpanden waarvoor alleen auto voldoet"],
        ascending=[False, False],
    )


def modaliteitenranglijst(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    df = provinciale_modaliteiten(run, status).rename(
        columns={
            "Woonpanden binnen de norm": "Aantal woonpanden binnen de norm",
            "Percentage binnen de norm": "Percentage woonpanden binnen de norm",
            "Woonpanden buiten de norm": "Aantal woonpanden buiten de norm",
            "Percentage buiten de norm": "Percentage woonpanden buiten de norm",
        }
    )
    df["Bereikbaarheidsklasse"] = df[
        "Percentage woonpanden binnen de norm"
    ].map(bereikbaarheidsklasse)
    beste_buiten = df["Percentage woonpanden buiten de norm"].min()
    df["Verschil met beste modaliteit in procentpunten"] = (
        df["Percentage woonpanden buiten de norm"] - beste_buiten
    ).round(1)
    df["_modaliteit_pos"] = df["Modaliteit"].map(MODUS_POSITIE)
    df = df.sort_values(
        [
            "Voorziening",
            "Percentage woonpanden buiten de norm",
            "Aantal woonpanden buiten de norm",
            "_modaliteit_pos",
        ],
        ascending=[True, False, False, True],
    ).copy()
    df["Positie van slecht naar goed"] = df.groupby("Voorziening").cumcount() + 1
    cols = [
        "Voorziening",
        "Positie van slecht naar goed",
        "Modaliteit",
        "Reistijdnorm in minuten",
        "Totaal aantal woonpanden",
        "Aantal woonpanden binnen de norm",
        "Percentage woonpanden binnen de norm",
        "Aantal woonpanden buiten de norm",
        "Percentage woonpanden buiten de norm",
        "Bereikbaarheidsklasse",
        "Verschil met beste modaliteit in procentpunten",
    ]
    return df[cols]


def samenvatting_zwakste_modaliteit_en_aandachtsvoorziening(
    modaliteiten: pd.DataFrame,
    onvoldoende: pd.DataFrame,
) -> pd.DataFrame:
    if modaliteiten.empty:
        return pd.DataFrame()
    ranglijst = modaliteiten.copy()
    ranglijst["Zwakste modaliteit binnen voorziening"] = ranglijst[
        "Positie van slecht naar goed"
    ].eq(1).map(zichtbaar_ja_nee)
    if not onvoldoende.empty:
        alle_modaliteiten = onvoldoende[
            onvoldoende["Aantal modaliteiten buiten de norm"].eq(len(MODI))
        ][["Voorziening", "Aantal unieke woonpanden", "Percentage van alle woonpanden"]].rename(
            columns={
                "Aantal unieke woonpanden": "Woonpanden buiten alle modaliteiten",
                "Percentage van alle woonpanden": "Percentage woonpanden buiten alle modaliteiten",
            }
        )
        ranglijst = ranglijst.merge(alle_modaliteiten, on="Voorziening", how="left")
    else:
        ranglijst["Woonpanden buiten alle modaliteiten"] = pd.NA
        ranglijst["Percentage woonpanden buiten alle modaliteiten"] = pd.NA

    ranglijst = ranglijst.sort_values(
        [
            "Modaliteit",
            "Percentage woonpanden buiten de norm",
            "Aantal woonpanden buiten de norm",
            "Percentage woonpanden buiten alle modaliteiten",
        ],
        ascending=[True, False, False, False],
    ).copy()
    ranglijst["Positie binnen modaliteit"] = ranglijst.groupby("Modaliteit").cumcount() + 1
    ranglijst["Aandachtsvoorziening binnen modaliteit"] = ranglijst[
        "Positie binnen modaliteit"
    ].eq(1).map(zichtbaar_ja_nee)
    ranglijst["Toelichting"] = (
        "Rangschikking per modaliteit op percentage woonpanden buiten de norm. "
        "De kolom 'Zwakste modaliteit binnen voorziening' markeert "
        "de slechtste modaliteit per voorziening."
    )
    cols = [
        "Modaliteit",
        "Positie binnen modaliteit",
        "Aandachtsvoorziening binnen modaliteit",
        "Voorziening",
        "Zwakste modaliteit binnen voorziening",
        "Positie van slecht naar goed",
        "Reistijdnorm in minuten",
        "Totaal aantal woonpanden",
        "Aantal woonpanden buiten de norm",
        "Percentage woonpanden buiten de norm",
        "Bereikbaarheidsklasse",
        "Woonpanden buiten alle modaliteiten",
        "Percentage woonpanden buiten alle modaliteiten",
        "Toelichting",
    ]
    return ranglijst[[col for col in cols if col in ranglijst.columns]]


def multimodale_verdeling(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    omschrijving = {
        0: "0 modaliteiten buiten de norm",
        1: "1 modaliteit buiten de norm",
        2: "2 modaliteiten buiten de norm",
        3: "3 modaliteiten buiten de norm",
        4: "4 modaliteiten buiten de norm",
        5: "Alle 5 modaliteiten buiten de norm",
    }
    df = woonpanden_onvoldoende_modaliteiten(run, status).rename(
        columns={
            "Aantal onvoldoende modaliteiten": "Aantal modaliteiten buiten de norm",
            "Aantal woonpanden": "Aantal unieke woonpanden",
            "Percentage woonpanden": "Percentage van alle woonpanden",
        }
    )
    df["Omschrijving"] = df["Aantal modaliteiten buiten de norm"].map(omschrijving)
    return df[
        [
            "Voorziening",
            "Aantal modaliteiten buiten de norm",
            "Omschrijving",
            "Aantal unieke woonpanden",
            "Percentage van alle woonpanden",
        ]
    ]


def bereikbaarheidsprofielen(run: VoorzieningRun, status: pd.DataFrame) -> pd.DataFrame:
    totaal = len(status)
    profielen = [
        (
            "Alle modaliteiten binnen de norm",
            status["alle_modaliteiten_voldoen"],
            "Alle vijf modaliteiten voldoen voor hetzelfde unieke woonpand.",
        ),
        (
            "Minimaal een modaliteit binnen de norm",
            status["aantal_modaliteiten_voldoende"].gt(0),
            "Minimaal een van de vijf modaliteiten voldoet voor hetzelfde unieke woonpand.",
        ),
        (
            "Geen enkele modaliteit binnen de norm",
            status["geen_enkele_modaliteit_voldoet"],
            "Geen van de vijf modaliteiten voldoet voor hetzelfde unieke woonpand.",
        ),
        (
            "Alleen auto binnen de norm",
            status["alleen_auto_voldoet"],
            "Auto voldoet; lopen, fiets, OV met lopen en OV met fiets voldoen niet.",
        ),
        (
            "Lopen of fiets binnen de norm",
            status["lopen_of_fiets_voldoet"],
            "Lopen of fiets voldoet voor hetzelfde unieke woonpand.",
        ),
        (
            "Zonder auto binnen de norm",
            status["zonder_auto_bereikbaar"],
            "Lopen, fiets, OV met lopen of OV met fiets voldoet.",
        ),
        (
            "Alleen OV met lopen of OV met fiets binnen de norm",
            status["alleen_ov_voldoet"],
            "OV met lopen of OV met fiets voldoet; lopen, fiets en auto voldoen niet.",
        ),
    ]
    rows = []
    for naam, mask, definitie in profielen:
        aantal = int(mask.sum())
        rows.append(
            {
                "Voorziening": run.label,
                "Bereikbaarheidsprofiel": naam,
                "Aantal unieke woonpanden": aantal,
                "Percentage van alle woonpanden": round(aantal / totaal * 100, 1) if totaal else 0,
                "Definitie": definitie,
            }
        )
    return pd.DataFrame(rows)


def aantal_voorzieningslocaties() -> int | str:
    return ""


def kerncijfers_voorziening(
    run: VoorzieningRun,
    status: pd.DataFrame,
    modaliteiten: pd.DataFrame,
) -> pd.DataFrame:
    slechtste = modaliteiten.sort_values(
        ["Percentage woonpanden buiten de norm", "Aantal woonpanden buiten de norm"],
        ascending=[False, False],
    ).iloc[0]
    beste = modaliteiten.sort_values(
        ["Percentage woonpanden buiten de norm", "Aantal woonpanden buiten de norm"],
        ascending=[True, True],
    ).iloc[0]
    totaal = len(status)
    geen = int(status["geen_enkele_modaliteit_voldoet"].sum())
    alleen_auto = int(status["alleen_auto_voldoet"].sum())
    return pd.DataFrame(
        [
            {
                "Voorziening": run.label,
                "Aantal voorzieningslocaties": aantal_voorzieningslocaties(),
                "Totaal aantal woonpanden": totaal,
                "Aantal woonpanden buiten alle modaliteiten": geen,
                "Percentage woonpanden buiten alle modaliteiten": (
                    round(geen / totaal * 100, 1) if totaal else 0
                ),
                "Aantal woonpanden uitsluitend bereikbaar met auto": alleen_auto,
                "Percentage woonpanden uitsluitend bereikbaar met auto": (
                    round(alleen_auto / totaal * 100, 1) if totaal else 0
                ),
                "Slechtste modaliteit": slechtste["Modaliteit"],
                "Aantal woonpanden buiten de norm bij slechtste modaliteit": slechtste[
                    "Aantal woonpanden buiten de norm"
                ],
                "Percentage woonpanden buiten de norm bij slechtste modaliteit": slechtste[
                    "Percentage woonpanden buiten de norm"
                ],
                "Beste modaliteit": beste["Modaliteit"],
                "Aantal woonpanden buiten de norm bij beste modaliteit": beste[
                    "Aantal woonpanden buiten de norm"
                ],
                "Percentage woonpanden buiten de norm bij beste modaliteit": beste[
                    "Percentage woonpanden buiten de norm"
                ],
            }
        ]
    )


def verrijk_gemeenten(gemeenten: pd.DataFrame, buurten: pd.DataFrame) -> pd.DataFrame:
    buurt_stats = (
        buurten[buurten["Totaal aantal woonpanden"].gt(0)]
        .groupby(["Voorziening", "Modaliteit", "Gemeentecode", "Gemeentenaam"], dropna=False)
        .agg(
            **{
                "Totaal aantal buurten met woonpanden": ("Buurtcode", "nunique"),
                "Aantal buurten onder de grens van 80%": (
                    "Onder 80 procent woondekking",
                    lambda s: int(s.astype(bool).sum()),
                ),
            }
        )
        .reset_index()
    )
    df = gemeenten.merge(
        buurt_stats,
        on=["Voorziening", "Modaliteit", "Gemeentecode", "Gemeentenaam"],
        how="left",
    )
    df["Totaal aantal buurten met woonpanden"] = df[
        "Totaal aantal buurten met woonpanden"
    ].fillna(0).astype(int)
    df["Aantal buurten onder de grens van 80%"] = df[
        "Aantal buurten onder de grens van 80%"
    ].fillna(0).astype(int)
    df["Percentage buurten onder de grens van 80%"] = (
        df["Aantal buurten onder de grens van 80%"]
        / df["Totaal aantal buurten met woonpanden"].replace(0, pd.NA)
        * 100
    ).fillna(0).round(1)
    df["Bereikbaarheidsklasse"] = df["Percentage binnen de norm"].map(bereikbaarheidsklasse)
    return df


def gemeenteranglijst(gemeenten: pd.DataFrame, buurten: pd.DataFrame) -> pd.DataFrame:
    df = verrijk_gemeenten(gemeenten, buurten).copy()
    df = df[df["Totaal aantal woonpanden"].gt(0)].copy()
    rel = df.sort_values(
        [
            "Voorziening",
            "Modaliteit",
            "Percentage buiten de norm",
            "Woonpanden buiten de norm",
            "Gemeentenaam",
        ],
        ascending=[True, True, False, False, True],
    )
    rel_pos = rel.groupby(["Voorziening", "Modaliteit"]).cumcount() + 1
    df["Positie relatief"] = pd.Series(rel_pos.to_numpy(), index=rel.index)
    abs_df = df.sort_values(
        [
            "Voorziening",
            "Modaliteit",
            "Woonpanden buiten de norm",
            "Percentage buiten de norm",
            "Gemeentenaam",
        ],
        ascending=[True, True, False, False, True],
    )
    abs_pos = abs_df.groupby(["Voorziening", "Modaliteit"]).cumcount() + 1
    df["Positie absolute impact"] = pd.Series(abs_pos.to_numpy(), index=abs_df.index)
    df = df.rename(
        columns={
            "Woonpanden binnen de norm": "Aantal woonpanden binnen de norm",
            "Percentage binnen de norm": "Percentage woonpanden binnen de norm",
            "Woonpanden buiten de norm": "Aantal woonpanden buiten de norm",
            "Percentage buiten de norm": "Percentage woonpanden buiten de norm",
        }
    )
    cols = [
        "Voorziening",
        "Modaliteit",
        "Positie relatief",
        "Positie absolute impact",
        "Gemeentecode",
        "Gemeentenaam",
        "Totaal aantal woonpanden",
        "Aantal woonpanden binnen de norm",
        "Percentage woonpanden binnen de norm",
        "Aantal woonpanden buiten de norm",
        "Percentage woonpanden buiten de norm",
        "Totaal aantal buurten met woonpanden",
        "Aantal buurten onder de grens van 80%",
        "Percentage buurten onder de grens van 80%",
        "Bereikbaarheidsklasse",
    ]
    return df[cols].sort_values(["Voorziening", "Modaliteit", "Positie relatief"])


def beste_slechtste_gemeenten(ranglijst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (voorziening, modaliteit), groep in ranglijst.groupby(
        ["Voorziening", "Modaliteit"],
        dropna=False,
    ):
        geldig = groep[groep["Totaal aantal woonpanden"].gt(0)]
        selecties = [
            ("Slechtste gemeente relatief", geldig.sort_values("Positie relatief").head(1)),
            (
                "Beste gemeente relatief",
                geldig.sort_values(
                    "Positie relatief",
                    ascending=False,
                ).head(1),
            ),
            ("Grootste absolute impact", geldig.sort_values("Positie absolute impact").head(1)),
            (
                "Kleinste absolute impact",
                geldig.sort_values(
                    "Positie absolute impact",
                    ascending=False,
                ).head(1),
            ),
        ]
        for naam, selectie in selecties:
            for positie, (_, rij) in enumerate(selectie.iterrows(), start=1):
                rows.append(
                    {
                        "Voorziening": voorziening,
                        "Modaliteit": modaliteit,
                        "Type selectie": naam,
                        "Positie": positie,
                        "Gemeentenaam": rij["Gemeentenaam"],
                        "Totaal aantal woonpanden": rij["Totaal aantal woonpanden"],
                        "Aantal woonpanden buiten de norm": rij[
                            "Aantal woonpanden buiten de norm"
                        ],
                        "Percentage woonpanden buiten de norm": rij[
                            "Percentage woonpanden buiten de norm"
                        ],
                        "Aantal buurten onder 80%": rij["Aantal buurten onder de grens van 80%"],
                    }
                )
    return pd.DataFrame(rows)


def buurtranglijst(buurten: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = buurten.copy()
    nul = df[df["Totaal aantal woonpanden"].fillna(0).le(0)].copy()
    df = df[df["Totaal aantal woonpanden"].gt(0)].copy()
    df["Bereikbaarheidsklasse"] = df["Percentage binnen de norm"].map(bereikbaarheidsklasse)
    df["Onder de grens van 80%"] = df["Percentage binnen de norm"].lt(80.0).map(zichtbaar_ja_nee)
    rel = df.sort_values(
        [
            "Voorziening",
            "Modaliteit",
            "Percentage buiten de norm",
            "Woonpanden buiten de norm",
            "Buurtnaam",
        ],
        ascending=[True, True, False, False, True],
    )
    rel_pos = rel.groupby(["Voorziening", "Modaliteit"]).cumcount() + 1
    df["Positie relatief"] = pd.Series(rel_pos.to_numpy(), index=rel.index)
    abs_df = df.sort_values(
        [
            "Voorziening",
            "Modaliteit",
            "Woonpanden buiten de norm",
            "Percentage buiten de norm",
            "Buurtnaam",
        ],
        ascending=[True, True, False, False, True],
    )
    abs_pos = abs_df.groupby(["Voorziening", "Modaliteit"]).cumcount() + 1
    df["Positie absolute impact"] = pd.Series(abs_pos.to_numpy(), index=abs_df.index)
    df = df.rename(
        columns={
            "Woonpanden binnen de norm": "Aantal woonpanden binnen de norm",
            "Percentage binnen de norm": "Percentage woonpanden binnen de norm",
            "Woonpanden buiten de norm": "Aantal woonpanden buiten de norm",
            "Percentage buiten de norm": "Percentage woonpanden buiten de norm",
        }
    )
    cols = [
        "Voorziening",
        "Modaliteit",
        "Positie relatief",
        "Positie absolute impact",
        "Buurtcode",
        "Buurtnaam",
        "Gemeentecode",
        "Gemeentenaam",
        "Totaal aantal woonpanden",
        "Aantal woonpanden binnen de norm",
        "Percentage woonpanden binnen de norm",
        "Aantal woonpanden buiten de norm",
        "Percentage woonpanden buiten de norm",
        "Bereikbaarheidsklasse",
        "Onder de grens van 80%",
    ]
    return df[cols].sort_values(["Voorziening", "Modaliteit", "Positie relatief"]), nul


def beste_slechtste_buurten(ranglijst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (voorziening, modaliteit), groep in ranglijst.groupby(
        ["Voorziening", "Modaliteit"],
        dropna=False,
    ):
        selecties = [
            ("Top 10 slechtste buurten relatief", groep.sort_values("Positie relatief").head(10)),
            (
                "Top 10 slechtste buurten absolute impact",
                groep.sort_values("Positie absolute impact").head(10),
            ),
            (
                "Top 10 beste buurten relatief",
                groep.sort_values(
                    "Positie relatief",
                    ascending=False,
                ).head(10),
            ),
        ]
        for naam, selectie in selecties:
            for positie, (_, rij) in enumerate(selectie.iterrows(), start=1):
                rows.append(
                    {
                        "Voorziening": voorziening,
                        "Modaliteit": modaliteit,
                        "Type ranglijst": naam,
                        "Positie": positie,
                        "Gemeentenaam": rij["Gemeentenaam"],
                        "Buurtnaam": rij["Buurtnaam"],
                        "Totaal aantal woonpanden": rij["Totaal aantal woonpanden"],
                        "Aantal woonpanden buiten de norm": rij[
                            "Aantal woonpanden buiten de norm"
                        ],
                        "Percentage woonpanden buiten de norm": rij[
                            "Percentage woonpanden buiten de norm"
                        ],
                        "Bereikbaarheidsklasse": rij["Bereikbaarheidsklasse"],
                        "Kleine buurt": "",
                    }
                )
    return pd.DataFrame(rows)
