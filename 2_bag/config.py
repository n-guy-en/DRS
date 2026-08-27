"""Instellingen voor de BAG-verwerking."""

from pathlib import Path


BAG_MAP = Path(__file__).resolve().parent
BASE_DIR = BAG_MAP.parent

BAG_DIR = BAG_MAP / "lvbag-extract-nl"
OUTPUT_DIR = BAG_MAP / "bag_frl_xml"
OUTPUT_XML_DIR = OUTPUT_DIR / "xml"
OUTPUT_JAAR_DIR = OUTPUT_DIR / "per_jaar"
KOPPELTABEL_PAD = OUTPUT_DIR / "vbo_pand_koppeling.csv"

CRS_RD = "EPSG:28992"
CRS_WGS84 = "EPSG:4326"

# Jaar dat je wilt analyseren. Dit jaar moet ook in BAG_EXPORT_JAREN staan.
ANALYSEJAAR = 2026

# BAG-jaargangen die worden meegenomen en geexporteerd.
BAG_EXPORT_JAREN = (2023, 2024, 2025, 2026)

# Gebruik deze limieten alleen tijdelijk tijdens ontwikkeling.
# Laat op None staan voor een volledige run.
MAX_XML_BESTANDEN = None
MAX_PND_XML_BESTANDEN = None

# Print voortgang na dit aantal XML-bestanden.
PRINT_IEDERE = 50

FRYSLAN_GEMEENTEN = {
    "0059",
    "0060",
    "0072",
    "0074",
    "0080",
    "0085",
    "0086",
    "0088",
    "0090",
    "0093",
    "0096",
    "0098",
    "0737",
    "1891",
    "1900",
    "1940",
    "1949",
    "1970",
}
