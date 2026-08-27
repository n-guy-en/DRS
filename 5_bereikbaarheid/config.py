"""Runconfiguratie voor bereikbaarheidsanalyses.

Pas in dit bestand de voorzieningen en algemene instellingen aan. Start daarna:

    python3 5_bereikbaarheid/bop.py
"""

from __future__ import annotations

import sys
from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parent
if str(CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(CONFIG_DIR))

from helpers.instellingen import (
    DEFAULT_RUNTIME_CONFIG,
    ONDERWIJS_NIVEAU_NAMEN,
    PRESETS,
    RuntimeConfig,
)


# Kies hier welke voorzieningen je wilt berekenen.
# Beschikbaar: 
# - supermarkt
# - apotheek
# - huisarts
# - ziekenhuis
# - recreatief_groen,
# - sport
# - ov
# - onderwijs
VOORZIENINGEN = [
    #"supermarkt",
    #"ov",
    #"ziekenhuis",
    #"apotheek",
    #"huisarts",
    #"recreatief_groen",
    #"sport",
    "onderwijs"
]

# Alleen gebruikt wanneer "onderwijs" in VOORZIENINGEN staat.
# Beschikbaar:
# - basisonderwijs
# - vo
# - mbo
# - hbo
# - wo
# - vmbo
# - mavo
# - havo
# - vwo
# - pro
# - brugjaar
ONDERWIJS_NIVEAUS = "wo"

# Algemene runinstellingen voor alle gekozen voorzieningen.
# Kies bij modi uit:
# - "all" voor lopen, fiets, auto, ov_lopen en ov_fiets
# - "lopen"
# - "fiets"
# - "auto"
# - "ov_lopen"
# - "ov_fiets"
# - een kommalijst, bijvoorbeeld "fiets,ov_fiets"
# Multimodaal wordt vernieuwd zodra alle vijf modaliteitsbestanden bestaan.
# Je mag modaliteiten dus ook los draaien, bijvoorbeeld eerst "fiets" en later "ov_fiets".
RUN = RuntimeConfig(
    pand_selectie="woonpanden",
    modi="fiets,auto,ov_lopen,ov_fiets",
    max_snap_meter=250.0,
    gebruik_pandpolygonen=True,
    max_parkeer_loop_min=10.0,
    max_ov_transfer_meter=250.0,
    ov_datum=DEFAULT_RUNTIME_CONFIG.ov_datum,
    ov_starttijd="00:00:00",
    ov_eindtijd="23:59:59",
    ov_stap_minuten=15,
    min_overstap_min=3.0,
)

# Pandniveau-flowmaps zijn zwaar. Zet alleen aan wanneer je deze kaartlagen nodig hebt.
# Als PAND_FLOWMAPS = True, wordt de flowmap direct na elke gekozen modaliteit gemaakt.
PAND_FLOWMAPS = True

# Voorbeeldroutes zijn alleen bedoeld als controlelaag.
# Zet uit wanneer je alleen de normale outputlagen nodig hebt.
VOORBEELDROUTES = False


def controleer_config() -> None:
    onbekend = sorted(set(VOORZIENINGEN) - set(PRESETS))
    if onbekend:
        raise ValueError(
            "Onbekende voorzieningen in 5_bereikbaarheid/config.py: "
            + ", ".join(onbekend)
            + ". Kies uit: "
            + ", ".join(PRESETS)
        )
    if "onderwijs" in VOORZIENINGEN and ONDERWIJS_NIVEAUS != "all":
        niveaus = [deel.strip() for deel in ONDERWIJS_NIVEAUS.split(",") if deel.strip()]
        onbekende_niveaus = sorted(set(niveaus) - set(ONDERWIJS_NIVEAU_NAMEN))
        if onbekende_niveaus:
            raise ValueError(
                "Onbekende onderwijsniveaus in 5_bereikbaarheid/config.py: "
                + ", ".join(onbekende_niveaus)
                + ". Kies uit: "
                + ", ".join(ONDERWIJS_NIVEAU_NAMEN)
            )
