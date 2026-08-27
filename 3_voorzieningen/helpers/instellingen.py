"""Vaste instellingen voor voorzieningenverwerking."""

from pathlib import Path
import runpy


BASE_DIR = Path(__file__).resolve().parents[2]
VOORZIENINGEN_DIR = BASE_DIR / "3_voorzieningen"


def lees_bag_analysejaar() -> int:
    """Lees het analysejaar uit de BAG-config."""
    bag_config = runpy.run_path(str(BASE_DIR / "2_bag" / "config.py"))
    return int(bag_config["ANALYSEJAAR"])


CRS_RD = "EPSG:28992"
CRS_WGS84 = "EPSG:4326"

JAAR = lees_bag_analysejaar()
BAG_PEILDATUM = f"{JAAR}-12-31"
MAX_AFSTAND_METER = 50.0
GELDIGE_PAND_STATUSSEN = {
    "Pand in gebruik",
    "Verbouwing pand",
}
