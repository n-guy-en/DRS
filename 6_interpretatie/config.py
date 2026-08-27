"""Runconfiguratie voor interpretatielagen.

Pas in dit bestand de voorzieningen en interpretatie-instellingen aan. Start daarna:

    python3 6_interpretatie/interpretatie.py
"""

from __future__ import annotations


# Kies hier welke voorzieningen je wilt verwerken.
# Beschikbaar: supermarkt, apotheek, huisarts, ziekenhuis, recreatief_groen,
# sport, ov, onderwijs.
VOORZIENINGEN = [
    "supermarkt",
    #"ov",
    "ziekenhuis",
]

TOEGESTANE_VOORZIENINGEN = {
    "supermarkt",
    "apotheek",
    "huisarts",
    "ziekenhuis",
    "onderwijs",
    "ov",
    "recreatief_groen",
    "sport",
}

# Alleen gebruikt wanneer "onderwijs" in VOORZIENINGEN staat.
# Gebruik "all" voor alle niveaus, of een lijst zoals ["vmbo", "havo"].
ONDERWIJS_NIVEAUS = "all"

TOEGESTANE_ONDERWIJSNIVEAUS = {
    "basisonderwijs",
    "vo",
    "vmbo",
    "mavo",
    "havo",
    "vwo",
    "pro",
    "brugjaar",
    "mbo",
    "hbo",
    "wo",
}

# "all" of kommalijst zoals "lopen,fiets,auto".
INTERPRETATIE_MODI = "all"


def gekozen_onderwijsniveaus() -> list[str]:
    if ONDERWIJS_NIVEAUS == "all":
        return sorted(TOEGESTANE_ONDERWIJSNIVEAUS)
    return list(ONDERWIJS_NIVEAUS)


def controleer_config() -> None:
    onbekend = sorted(set(VOORZIENINGEN) - TOEGESTANE_VOORZIENINGEN)
    if onbekend:
        raise ValueError(
            "Onbekende voorzieningen in 6_interpretatie/config.py: "
            + ", ".join(onbekend)
            + ". Kies uit: "
            + ", ".join(sorted(TOEGESTANE_VOORZIENINGEN))
        )
    if "onderwijs" in VOORZIENINGEN:
        onbekende_niveaus = sorted(
            set(gekozen_onderwijsniveaus()) - TOEGESTANE_ONDERWIJSNIVEAUS
        )
        if onbekende_niveaus:
            raise ValueError(
                "Onbekende onderwijsniveaus in 6_interpretatie/config.py: "
                + ", ".join(onbekende_niveaus)
                + ". Kies uit: "
                + ", ".join(sorted(TOEGESTANE_ONDERWIJSNIVEAUS))
            )
