"""Koppeling tussen GTFS-segmenten en OV-lijnen."""

from .instellingen import MAX_AFSTAND_HALTE_TOT_OV_LIJN_M
from .geometrie import knip_lijn_tussen_punten, maak_rd_punt
from .tekst import lijn_id_normaal, tekst_normaal


def maak_ov_lijn_segment(line, lijnen):
    """Zoek en knip passend OV_LIJNEN segment voor een halteverbinding."""
    if lijnen.empty:
        return None

    from_point = maak_rd_punt(
        line["from_halte_x"],
        line["from_halte_y"],
        line["from_stop_lon"],
        line["from_stop_lat"],
    )
    to_point = maak_rd_punt(
        line["to_halte_x"],
        line["to_halte_y"],
        line["to_stop_lon"],
        line["to_stop_lat"],
    )

    if from_point is None or to_point is None:
        return None

    mode = str(line["mode"])
    line_id = lijn_id_normaal(line["line_id"])
    operator_norm = tekst_normaal(line["operator"])
    route_tekst = tekst_normaal(
        str(line.get("route_long_name", ""))
        + " "
        + str(line.get("trip_headsign", ""))
        + " "
        + str(line.get("from_stop_name", ""))
        + " "
        + str(line.get("to_stop_name", ""))
    )

    kandidaten = lijnen[
        lijnen["mode"].astype(str) == mode
    ].copy()

    if kandidaten.empty:
        return None

    lijnnummer_match = kandidaten[
        kandidaten["line_id_norm"].astype(str) == line_id
    ].copy()

    if not lijnnummer_match.empty:
        kandidaten = lijnnummer_match

    if operator_norm:
        operator_match = kandidaten[
            kandidaten["vervoerder_norm"].apply(
                lambda waarde: operator_norm in waarde or waarde in operator_norm
            )
        ].copy()

        if not operator_match.empty:
            kandidaten = operator_match

    beste = None

    for _, kandidaat_lijn in kandidaten.iterrows():
        routenaam_norm = kandidaat_lijn["routenaam_norm"]

        if line_id == "" and routenaam_norm:
            woorden = [
                woord
                for woord in routenaam_norm.split()
                if len(woord) >= 4
            ]
            if woorden and not any(woord in route_tekst for woord in woorden):
                continue

        geknipt = knip_lijn_tussen_punten(
            kandidaat_lijn.geometry,
            from_point,
            to_point,
        )

        if geknipt is None:
            continue

        if (
            geknipt["from_afstand_m"] > MAX_AFSTAND_HALTE_TOT_OV_LIJN_M
            or geknipt["to_afstand_m"] > MAX_AFSTAND_HALTE_TOT_OV_LIJN_M
        ):
            continue

        geknipt["ov_lijn_fid"] = kandidaat_lijn.get("fid", "")
        geknipt["ov_line_id"] = kandidaat_lijn.get("Lijnnummer", "")
        geknipt["ov_line_route_name"] = kandidaat_lijn.get("Routenaam", "")
        geknipt["ov_line_vervoerder"] = kandidaat_lijn.get("Vervoerder", "")

        if beste is None or geknipt["score"] < beste["score"]:
            beste = geknipt

    return beste
