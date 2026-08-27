import sys

from .instellingen import VERKEERSTYPEN


def laad_geopandas():
    try:
        import geopandas as gpd
    except ImportError:
        print(
            "Package ontbreekt: geopandas\n"
            "Gebruik de project-venv, bijvoorbeeld: "
            ".venv/bin/python 4_netwerk/NWB_netwerk.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return gpd


def normaliseer_ja_nee(serie):
    return serie.fillna("").astype(str).str.strip().str.upper()


def controleer_kolommen(gdf):
    ontbrekend = []
    for h_kolom, t_kolom in VERKEERSTYPEN.values():
        for kolom in (h_kolom, t_kolom):
            if kolom not in gdf.columns:
                ontbrekend.append(kolom)

    if ontbrekend:
        raise ValueError(
            "Ontbrekende kolommen in bronbestand: " + ", ".join(ontbrekend)
        )


def normaliseer_kolomnamen(gdf):
    gdf = gdf.copy()
    gdf.columns = [kolom.lower() for kolom in gdf.columns]
    return gdf


def naar_getal(serie):
    return (
        serie.fillna("")
        .astype(str)
        .str.replace(",", ".", regex=False)
        .str.extract(r"([0-9]+(?:\.[0-9]+)?)", expand=False)
        .astype(float)
    )


def unieke_tekst(waarden):
    schoon = sorted(
        set(
            str(waarde).strip()
            for waarde in waarden
            if str(waarde).strip() and str(waarde).strip().lower() != "nan"
        )
    )
    return "; ".join(schoon)


def tekstkolom(gdf, kolomnaam):
    if kolomnaam in gdf.columns:
        return gdf[kolomnaam].fillna("").astype(str)
    return ""
