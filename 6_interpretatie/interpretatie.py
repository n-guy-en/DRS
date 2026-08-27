"""Start de centrale interpretatieworkflow."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


INTERPRETATIE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = INTERPRETATIE_DIR.parent
WORKFLOW_SCRIPT = INTERPRETATIE_DIR / "helpers" / "workflow.py"

if str(INTERPRETATIE_DIR) not in sys.path:
    sys.path.insert(0, str(INTERPRETATIE_DIR))
import config as run_config  # noqa: E402


def basis_env() -> dict[str, str]:
    env = os.environ.copy()
    env["INTERPRETATIE_MODI"] = run_config.INTERPRETATIE_MODI
    return env


def run_voorziening(voorziening: str, onderwijsniveau: str | None = None) -> None:
    cmd = [sys.executable, str(WORKFLOW_SCRIPT), voorziening]
    if onderwijsniveau:
        cmd += ["--onderwijsniveau", onderwijsniveau]
    subprocess.run(cmd, cwd=PROJECT_DIR, env=basis_env(), check=True)


def main() -> None:
    run_config.controleer_config()
    for voorziening in run_config.VOORZIENINGEN:
        if voorziening == "onderwijs":
            for onderwijsniveau in run_config.gekozen_onderwijsniveaus():
                run_voorziening("onderwijs", onderwijsniveau)
        else:
            run_voorziening(voorziening)


if __name__ == "__main__":
    main()
