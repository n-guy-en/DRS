"""Tijdhulpen voor GTFS."""

import pandas as pd


def gtfs_tijd_naar_seconden(tijd_waarde):
    """Zet GTFS tijd HH:MM:SS om naar seconden.

    GTFS mag tijden boven 24:00:00 hebben.
    """
    if pd.isna(tijd_waarde):
        return None

    tekst = str(tijd_waarde).strip()

    if tekst == "":
        return None

    delen = tekst.split(":")

    if len(delen) != 3:
        return None

    try:
        uren = int(delen[0])
        minuten = int(delen[1])
        seconden = int(delen[2])
    except ValueError:
        return None

    return uren * 3600 + minuten * 60 + seconden


def seconden_naar_tijd(seconden):
    """Zet seconden terug naar HH:MM:SS."""
    if pd.isna(seconden):
        return ""

    seconden = int(seconden)
    uren = seconden // 3600
    rest = seconden % 3600
    minuten = rest // 60
    sec = rest % 60

    return f"{uren:02d}:{minuten:02d}:{sec:02d}"

