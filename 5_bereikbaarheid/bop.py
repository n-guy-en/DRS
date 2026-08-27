"""Start de centrale bereikbaarheidsworkflow."""

from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path


BEREIKBAARHEID_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BEREIKBAARHEID_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(BEREIKBAARHEID_DIR) not in sys.path:
    sys.path.insert(0, str(BEREIKBAARHEID_DIR))

import config as run_config


def main() -> None:
    run_config.controleer_config()
    workflow = import_module("5_bereikbaarheid.helpers.workflow")

    for voorziening in run_config.VOORZIENINGEN:
        print(f"\n=== Bereikbaarheid: {voorziening} ===")
        if voorziening == "onderwijs":
            workflow.run_bereikbaarheid(
                voorziening,
                run_config.ONDERWIJS_NIVEAUS,
                runtime_config=run_config.RUN,
                maak_pand_flowmaps=run_config.PAND_FLOWMAPS,
                maak_voorbeeldroutes=run_config.VOORBEELDROUTES,
            )
        else:
            workflow.run_bereikbaarheid(
                voorziening,
                runtime_config=run_config.RUN,
                maak_pand_flowmaps=run_config.PAND_FLOWMAPS,
                maak_voorbeeldroutes=run_config.VOORBEELDROUTES,
            )


if __name__ == "__main__":
    main()
