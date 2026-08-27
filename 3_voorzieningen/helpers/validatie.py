"""Kleine validatiehelpers voor voorzieningenbronnen."""

from collections.abc import Iterable

import pandas as pd


def valideer_kolommen(
    df: pd.DataFrame,
    verplichte_kolommen: Iterable[str],
    bron: str,
) -> None:
    """Controleer of een ingelezen bron alle verplichte kolommen bevat."""
    ontbrekende_kolommen = set(verplichte_kolommen) - set(df.columns)
    if ontbrekende_kolommen:
        raise KeyError(
            f"{bron} mist kolommen: " + ", ".join(sorted(ontbrekende_kolommen))
        )
