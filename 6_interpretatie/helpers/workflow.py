"""Gedeelde interpretatieworkflow voor een actieve voorziening."""

from __future__ import annotations

import argparse
import os
import sys
from importlib import import_module
from pathlib import Path


INTERPRETATIE_DIR = Path(__file__).resolve().parents[1]
if str(INTERPRETATIE_DIR) not in sys.path:
    sys.path.insert(0, str(INTERPRETATIE_DIR))


def stel_actieve_voorziening(
    voorziening: str,
    onderwijsniveau: str | None = None,
) -> None:
    """Zet de actieve voorziening voor deze interpretatierun."""
    os.environ["INTERPRETATIE_VOORZIENING"] = voorziening
    if onderwijsniveau:
        os.environ["INTERPRETATIE_ONDERWIJS_NIVEAU"] = onderwijsniveau


def run_interpretatie() -> None:
    instellingen = import_module("helpers.instellingen")
    tekorten = import_module("helpers.tekorten")
    knelpunten = import_module("helpers.knelpunten")
    isochroon = import_module("helpers.isochroon")

    label = instellingen.voorziening_label()
    print(f"=== Interpretatie: {label} ===", flush=True)

    print("\n=== Stap 1: tekortdiagnose ===", flush=True)
    diagnose = tekorten.main()

    print("\n=== Stap 2: modaliteiten onvoldoende ===", flush=True)
    knelpunten.main(diagnose)

    print("\n=== Stap 3: isochronen ===", flush=True)
    isochroon.main()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("voorziening")
    parser.add_argument("--onderwijsniveau", default=None)
    args = parser.parse_args()

    stel_actieve_voorziening(args.voorziening, args.onderwijsniveau)
    run_interpretatie()


if __name__ == "__main__":
    main()
