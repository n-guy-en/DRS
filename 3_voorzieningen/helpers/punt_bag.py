"""BAG-koppeling voor puntvoorzieningen."""

import geopandas as gpd
import pandas as pd

from helpers.instellingen import CRS_RD


def koppel_punten_aan_panden(
    punten: gpd.GeoDataFrame,
    panden: gpd.GeoDataFrame,
    max_afstand_meter: float,
    label: str,
) -> gpd.GeoDataFrame:
    """Koppel punten eerst met within en daarna met nearest binnen afstand."""
    print(f"Koppel {label} die binnen een BAG-pand vallen")
    gekoppeld = gpd.sjoin(
        punten,
        panden,
        how="left",
        predicate="within",
    )
    gekoppeld = gekoppeld.drop(columns=["index_right"], errors="ignore")
    gekoppeld["bag_match_type"] = pd.NA
    gekoppeld.loc[gekoppeld["pand_id"].notna(), "bag_match_type"] = "within"
    gekoppeld["bag_afstand_meter"] = 0.0

    zonder_match = gekoppeld[gekoppeld["pand_id"].isna()].copy()
    if zonder_match.empty:
        return gekoppeld

    print(f"Koppel overige {label} aan nearest BAG-pand binnen {max_afstand_meter} m")
    pand_attributen = panden.drop(columns="geometry").copy()
    nearest = gpd.sjoin_nearest(
        zonder_match.drop(
            columns=[
                kolom
                for kolom in pand_attributen.columns
                if kolom in zonder_match.columns
            ],
            errors="ignore",
        ),
        panden,
        how="left",
        max_distance=max_afstand_meter,
        distance_col="bag_afstand_meter",
    )
    nearest = nearest.drop(columns=["index_right"], errors="ignore")
    nearest.loc[nearest["pand_id"].notna(), "bag_match_type"] = "nearest"
    nearest.loc[nearest["pand_id"].isna(), "bag_match_type"] = "geen_match"

    met_match = gekoppeld[gekoppeld["pand_id"].notna()].copy()
    kolommen = gekoppeld.columns.union(nearest.columns)
    resultaat = pd.concat(
        [
            met_match.reindex(columns=kolommen),
            nearest.reindex(columns=kolommen),
        ],
        ignore_index=True,
    )
    return gpd.GeoDataFrame(resultaat, geometry="geometry", crs=CRS_RD)


def voeg_bag_status_toe(voorzieningen: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Voeg BAG-validatiestatus en afgeronde afstand toe."""
    voorzieningen = voorzieningen.copy()
    voorzieningen["bag_gevalideerd"] = voorzieningen["pand_id"].notna()
    voorzieningen["bag_afstand_meter"] = pd.to_numeric(
        voorzieningen["bag_afstand_meter"],
        errors="coerce",
    ).round(2)
    return voorzieningen
