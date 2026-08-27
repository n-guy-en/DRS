"""Tekst- en code-normalisatie voor OV-koppelingen."""

import re

import pandas as pd


def tekst_normaal(waarde):
    """Normaliseer tekst voor simpele matching."""
    if pd.isna(waarde):
        return ""

    tekst = str(waarde).lower().strip()
    tekst = tekst.replace("fryslân", "friesland")
    tekst = re.sub(r"[^a-z0-9]+", " ", tekst)
    tekst = re.sub(r"\s+", " ", tekst)
    return tekst.strip()


def lijn_id_normaal(waarde):
    """Normaliseer lijnnummer/lijncode voor OV_LIJNEN matching."""
    tekst = str(waarde).strip().upper()

    if tekst in ["", "NAN", "NONE", "<NA>"]:
        return ""

    if tekst.isdigit():
        return str(int(tekst))

    return tekst


def vervoermiddel_naar_mode(vervoermiddel):
    """Bepaal mode uit OV_LIJNEN vervoermiddel."""
    tekst = tekst_normaal(vervoermiddel)

    if "bus" in tekst:
        return "bus"

    if "trein" in tekst:
        return "train"

    if "veer" in tekst or "boot" in tekst or "ferry" in tekst:
        return "ferry"

    return "unknown"


def unieke_tekst(waarden):
    """Maak een korte, gesorteerde tekst van unieke waarden."""
    unieke_waarden = []

    for waarde in waarden:
        if pd.isna(waarde):
            continue

        tekst = str(waarde).strip()

        if tekst == "" or tekst.lower() in ["nan", "none", "<na>"]:
            continue

        unieke_waarden.append(tekst)

    return ", ".join(sorted(set(unieke_waarden)))
