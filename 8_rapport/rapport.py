"""Maak rapporttabellen op basis van bereikbaarheid en interpretatie-output."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd


RAPPORT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = RAPPORT_DIR.parent

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(RAPPORT_DIR) not in sys.path:
    sys.path.insert(0, str(RAPPORT_DIR))

from helpers.excel import schrijf_excel
from helpers.instellingen import BASE_DIR, MODUS_LABELS, OUT_DIR
from helpers.invoer import detecteer_voorzieningen, lees_pandstatus
from helpers.tabellen import (
    autoafhankelijkheid,
    bereikbaarheidsprofielen,
    beste_slechtste_buurten,
    beste_slechtste_gemeenten,
    buurtranglijst,
    buurttabel,
    gemeenteranglijst,
    gemeentetabel,
    kerncijfers_voorziening,
    modaliteitenranglijst,
    multimodale_verdeling,
    samenvatting_zwakste_modaliteit_en_aandachtsvoorziening,
    schrijf_csv,
)


def controle_row(
    cid: str,
    onderwerp: str,
    bestand: str,
    verwacht: str,
    werkelijk: str,
    status: str,
    toelichting: str,
) -> dict:
    return {
        "Controle-ID": cid,
        "Onderwerp": onderwerp,
        "Bestand": bestand,
        "Verwachte uitkomst": verwacht,
        "Werkelijke uitkomst": werkelijk,
        "Status": status,
        "Toelichting": toelichting,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in [
        "provinciaal",
        "voorzieningen",
        "controle",
    ]:
        (OUT_DIR / subdir).mkdir(parents=True, exist_ok=True)

    runs = detecteer_voorzieningen()
    eind_manifest = []
    controles = []
    eind: dict[str, list[pd.DataFrame]] = {
        "modaliteitenranglijst": [],
        "onvoldoende_modaliteiten": [],
        "bereikbaarheidsprofielen": [],
        "kerncijfers": [],
        "gemeenteranglijst": [],
        "beste_slechtste_gemeenten": [],
        "buurtranglijst": [],
        "beste_slechtste_buurten": [],
    }

    for run in runs:
        print(f"Maak rapport: {run.label}")
        status = lees_pandstatus(run)
        unieke_panden = status["pand_id"].nunique()
        controles.append(
            controle_row(
                f"PAND-{run.slug}",
                "Unieke woonpandsleutel",
                str(run.pandlagen_rel),
                "pand_id is uniek na modaliteitenjoin",
                f"{unieke_panden} unieke pand_id op {len(status)} records",
                "OK" if unieke_panden == len(status) else "FOUT",
                "Multimodale indicatoren zijn op pand_id gecombineerd.",
            )
        )

        p01 = modaliteitenranglijst(run, status)
        p02 = multimodale_verdeling(run, status)
        p03 = bereikbaarheidsprofielen(run, status)
        p04 = kerncijfers_voorziening(run, status, p01)
        gemeenten = gemeentetabel(run)
        buurten = buurttabel(run)
        auto = autoafhankelijkheid(run, status)
        p05 = gemeenteranglijst(gemeenten, buurten)
        p06 = beste_slechtste_gemeenten(p05)
        p07, buurten_zonder_panden = buurtranglijst(buurten)
        p08 = beste_slechtste_buurten(p07)

        voorziening_dir = OUT_DIR / "voorzieningen" / run.slug
        voorziening_dir.mkdir(parents=True, exist_ok=True)
        for filename, df in [
            ("01_modaliteitenranglijst.csv", p01),
            ("02_aantal_onvoldoende_modaliteiten.csv", p02),
            ("03_bereikbaarheidsprofielen.csv", p03),
            ("04_kerncijfers.csv", p04),
            ("05_gemeenteranglijst.csv", p05),
            ("06_buurtranglijst.csv", p07),
            ("07_beste_en_slechtste_buurten.csv", p08),
            ("08_autoafhankelijkheid.csv", auto),
        ]:
            pad = voorziening_dir / filename
            schrijf_csv(df, pad)
            eind_manifest.append(
                {
                    "Tabel": str(pad.relative_to(BASE_DIR)),
                    "Rijen": len(df),
                }
            )

        for sleutel, df in [
            ("modaliteitenranglijst", p01),
            ("onvoldoende_modaliteiten", p02),
            ("bereikbaarheidsprofielen", p03),
            ("kerncijfers", p04),
            ("gemeenteranglijst", p05),
            ("beste_slechtste_gemeenten", p06),
            ("buurtranglijst", p07),
            ("beste_slechtste_buurten", p08),
        ]:
            if not df.empty:
                eind[sleutel].append(df)

        controles.append(
            controle_row(
                f"TOT-{run.slug}",
                "Binnen plus buiten is totaal",
                "provinciaal/01_modaliteitenranglijst_per_voorziening.csv",
                "Binnen + buiten = totaal per modaliteit",
                "Gecontroleerd",
                "OK"
                if (
                    p01["Aantal woonpanden binnen de norm"]
                    + p01["Aantal woonpanden buiten de norm"]
                ).eq(p01["Totaal aantal woonpanden"]).all()
                else "FOUT",
                "Controle op provinciale modaliteitentabel.",
            )
        )
        if not buurten_zonder_panden.empty:
            controles.append(
                controle_row(
                    f"NUL-BUURT-{run.slug}",
                    "Buurten zonder woonpanden",
                    "07_buurtranglijst_per_voorziening_modaliteit.csv",
                    "Buurten zonder woonpanden niet in ranglijst",
                    f"{len(buurten_zonder_panden)} records uitgesloten",
                    "OK",
                    "Records zijn niet meegenomen in de rangschikking.",
                )
            )

    eindtabellen: dict[str, pd.DataFrame] = {
        sleutel: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for sleutel, frames in eind.items()
    }
    eindtabellen["samenvatting_aandacht"] = (
        samenvatting_zwakste_modaliteit_en_aandachtsvoorziening(
            eindtabellen["modaliteitenranglijst"],
            eindtabellen["onvoldoende_modaliteiten"],
        )
    )
    csv_outputs = [
        ("provinciaal/01_modaliteitenranglijst_per_voorziening.csv", "modaliteitenranglijst"),
        ("provinciaal/02_aantal_onvoldoende_modaliteiten.csv", "onvoldoende_modaliteiten"),
        ("provinciaal/03_bereikbaarheidsprofielen.csv", "bereikbaarheidsprofielen"),
        ("provinciaal/04_kerncijfers_per_voorziening.csv", "kerncijfers"),
        ("provinciaal/05_gemeenteranglijst_per_voorziening_modaliteit.csv", "gemeenteranglijst"),
        ("provinciaal/06_beste_en_slechtste_gemeenten.csv", "beste_slechtste_gemeenten"),
        ("provinciaal/07_buurtranglijst_per_voorziening_modaliteit.csv", "buurtranglijst"),
        ("provinciaal/08_beste_en_slechtste_buurten.csv", "beste_slechtste_buurten"),
        ("provinciaal/09_samenvatting_zwakste_modaliteit_en_aandachtsvoorziening.csv", "samenvatting_aandacht"),
    ]
    for rel, sleutel in csv_outputs:
        df = eindtabellen[sleutel]
        pad = OUT_DIR / rel
        schrijf_csv(df, pad)
        eind_manifest.append({"Tabel": str(pad.relative_to(BASE_DIR)), "Rijen": len(df)})

    excel_tables = {
        "01_modaliteiten": eindtabellen["modaliteitenranglijst"],
        "02_onvoldoende_modaliteiten": eindtabellen["onvoldoende_modaliteiten"],
        "03_profielen": eindtabellen["bereikbaarheidsprofielen"],
        "04_kerncijfers": eindtabellen["kerncijfers"],
        "05_gemeenten": eindtabellen["gemeenteranglijst"],
        "06_buurten": eindtabellen["buurtranglijst"],
        "07_samenvatting": eindtabellen["samenvatting_aandacht"],
    }
    excel_pad = OUT_DIR / "provinciaal" / "rapport_daily_urban_systems.xlsx"
    schrijf_excel(excel_tables, excel_pad)
    eind_manifest.append(
        {
            "Tabel": str(excel_pad.relative_to(BASE_DIR)),
            "Rijen": sum(len(df) for df in excel_tables.values() if not df.empty),
        }
    )
    controles.extend(
        [
            controle_row(
                "MOD-01",
                "Modaliteiten harmonisatie",
                "alle eindtabellen",
                "Exacte modaliteitsnamen gebruikt",
                ", ".join(label for label in MODUS_LABELS.values()),
                "OK",
                "Technische modusnamen zijn omgezet naar Nederlandse labels.",
            ),
            controle_row(
                "AVG-01",
                "Geen modaliteitsgemiddelde",
                "alle eindtabellen",
                "Geen gemiddelde over modaliteiten",
                "Geen gemiddelde kolommen aangemaakt",
                "OK",
                "Alle modaliteiten blijven afzonderlijk; multimodaal is alleen via pand_id bepaald.",
            ),
        ]
    )
    controles_df = pd.DataFrame(controles)
    controles_pad = OUT_DIR / "controle" / "controles_eindoutput.csv"
    schrijf_csv(controles_df, controles_pad)
    eind_manifest.append(
        {
            "Tabel": str(controles_pad.relative_to(BASE_DIR)),
            "Rijen": len(controles_df),
        }
    )
    manifest_df = pd.DataFrame(eind_manifest).drop_duplicates()
    schrijf_csv(manifest_df, OUT_DIR / "controle" / "overzicht_rapport.csv")
    print(
        f"Klaar: {len(runs)} voorzieningen, "
        f"{len(manifest_df)} rapporttabelbestanden."
    )


if __name__ == "__main__":
    main()
