"""Maak OV-haltes en stations als voorziening uit de netwerklaag.

Bron:
- 0_layers/processed/4_netwerk/ov/line_total_stop_points.geojson

Output:
- 3_voorzieningen/raw/ov/ov_haltes.geojson
- 3_voorzieningen/processed/ov/ov_haltes.gpkg
- 0_layers/processed/3_voorzieningen/ov/ov_haltes.gpkg
"""

from __future__ import annotations

from pathlib import Path
import sys

import geopandas as gpd


VOORZIENINGEN_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(VOORZIENINGEN_DIR))

from helpers.instellingen import BASE_DIR, CRS_WGS84  
from helpers.validatie import valideer_kolommen  


BRON_PAD = (
    BASE_DIR
    / "0_layers"
    / "processed"
    / "4_netwerk"
    / "ov"
    / "line_total_stop_points.geojson"
)
RAW_DIR = BASE_DIR / "3_voorzieningen" / "raw" / "ov"
PROCESSED_DIR = BASE_DIR / "3_voorzieningen" / "processed" / "ov"
LAYERS_DIR = BASE_DIR / "0_layers" / "processed" / "3_voorzieningen" / "ov"

RAW_PAD = RAW_DIR / "ov_haltes.geojson"
PROCESSED_PAD = PROCESSED_DIR / "ov_haltes.gpkg"
LAYERS_PAD = LAYERS_DIR / "ov_haltes.gpkg"
LAYER = "ov_haltes"
VEREISTE_OV_KOLOMMEN = {"node_id", "stop_names", "modes", "geometry"}


def normaliseer_ov_haltes(haltes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    valideer_kolommen(haltes, VEREISTE_OV_KOLOMMEN, "OV-stoplaag")
    haltes = haltes[haltes.geometry.notna()].copy()
    haltes = haltes[~haltes.geometry.is_empty].copy()

    haltes["ov_id"] = haltes["node_id"].astype(str)
    haltes["ov_naam"] = haltes["stop_names"].fillna("").astype(str).str.strip()
    haltes.loc[haltes["ov_naam"].eq(""), "ov_naam"] = haltes.loc[
        haltes["ov_naam"].eq(""),
        "ov_id",
    ]
    haltes["naam"] = haltes["ov_naam"]
    haltes["ov_type"] = haltes["modes"].fillna("").astype(str).str.strip()
    haltes["ov_adres"] = haltes["ov_naam"]
    haltes["ov_lon"] = haltes.to_crs(CRS_WGS84).geometry.x
    haltes["ov_lat"] = haltes.to_crs(CRS_WGS84).geometry.y

    voorkeurskolommen = [
        "ov_id",
        "ov_naam",
        "naam",
        "ov_type",
        "ov_adres",
        "ov_lon",
        "ov_lat",
        "node_id",
        "stop_ids",
        "stop_names",
        "officiele_halte_id",
        "officiele_halte_naam",
        "modes",
        "operators",
        "agency_ids",
        "line_ids",
        "aantal_lijnen",
        "aantal_routes",
        "aantal_verbindingen",
        "geometry_source",
        "tooltip",
        "geometry",
    ]
    kolommen = [kolom for kolom in voorkeurskolommen if kolom in haltes.columns]
    return haltes[kolommen].copy()


def main() -> None:
    if not BRON_PAD.exists():
        raise FileNotFoundError(
            f"OV-stoplaag ontbreekt: {BRON_PAD}. Run eerst 4_netwerk/gtfs_ov_netwerk.py."
        )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    haltes = gpd.read_file(BRON_PAD)
    haltes = normaliseer_ov_haltes(haltes)

    tijdelijk_raw = RAW_PAD.with_suffix(".tmp.geojson")
    tijdelijk_raw.unlink(missing_ok=True)
    haltes.to_file(tijdelijk_raw, driver="GeoJSON")
    tijdelijk_raw.replace(RAW_PAD)
    print(f"Opgeslagen: {RAW_PAD}")

    tijdelijk_processed = PROCESSED_PAD.with_name("ov_haltes.tmp.gpkg")
    tijdelijk_processed.unlink(missing_ok=True)
    haltes.to_file(tijdelijk_processed, layer=LAYER, driver="GPKG")
    tijdelijk_processed.replace(PROCESSED_PAD)
    print(f"Opgeslagen: {PROCESSED_PAD} ({LAYER})")

    tijdelijk_layers = LAYERS_PAD.with_name("ov_haltes.tmp.gpkg")
    tijdelijk_layers.unlink(missing_ok=True)
    haltes.to_file(tijdelijk_layers, layer=LAYER, driver="GPKG")
    tijdelijk_layers.replace(LAYERS_PAD)
    print(f"Opgeslagen in 0_layers: {LAYERS_PAD} ({LAYER})")
    print(f"OV-haltes/stations: {len(haltes)}")


if __name__ == "__main__":
    main()
