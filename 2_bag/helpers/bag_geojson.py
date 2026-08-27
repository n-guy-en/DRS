"""
GeoJSON-hulpfuncties voor BAG-pandgeometrie.

Deze module bevat:
- omzetting van RD New naar WGS84;
- uitlezen van BAG-polygonen;
- schrijven van BAG-panden als GeoJSON.
"""

import json
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

from pyproj import Transformer

from helpers.bag_xml import (
    vind_eerste_element,
    vind_eerste_tekst,
    vind_object,
)


RD_NAAR_WGS84 = Transformer.from_crs(
    "EPSG:28992",
    "EPSG:4326",
    always_xy=True,
)


def rd_naar_wgs84(x: float, y: float) -> list[float]:
    """Zet RD New-coördinaten om naar GeoJSON-coördinaten."""
    lon, lat = RD_NAAR_WGS84.transform(x, y)
    return [lon, lat]


def bepaal_gml_dimensie(element: ET.Element, standaard: int = 2) -> int:
    """Bepaal de coördinaatdimensie, met 2D als BAG-veilige standaard."""
    dimensie = element.get("srsDimension")
    if dimensie in {"2", "3"}:
        return int(dimensie)

    return standaard


def maak_ring_uit_poslist(
    poslist: str | None,
    dimensie: int = 2,
) -> list[list[float]] | None:
    """Maak een GeoJSON-ring uit een BAG-posList."""
    if not poslist or dimensie not in {2, 3}:
        return None

    try:
        waarden = [float(waarde) for waarde in poslist.split()]
    except ValueError:
        return None

    if len(waarden) % dimensie != 0:
        return None

    ring = [
        rd_naar_wgs84(waarden[index], waarden[index + 1])
        for index in range(0, len(waarden), dimensie)
    ]

    if len(ring) < 4:
        return None

    if ring[0] != ring[-1]:
        ring.append(ring[0])

    return ring


def haal_pandpolygon_op(
    pand: ET.Element,
) -> list[list[list[float]]] | None:
    """Haal de polygoncoördinaten uit een BAG-pand."""
    polygon = vind_object(pand, "Polygon")

    if polygon is None:
        return None

    ringen = []
    polygon_dimensie = bepaal_gml_dimensie(polygon)

    for elem in polygon.iter():
        if elem.tag.split("}")[-1] != "LinearRing":
            continue

        poslist_element = vind_eerste_element(elem, "posList")
        if poslist_element is None:
            continue

        ring_dimensie = bepaal_gml_dimensie(
            poslist_element,
            bepaal_gml_dimensie(elem, polygon_dimensie),
        )
        ring = maak_ring_uit_poslist(
            poslist_element.text,
            ring_dimensie,
        )

        if ring:
            ringen.append(ring)

    return ringen or None


def maak_pand_eigenschappen(
    pand: ET.Element,
    jaar: int,
) -> dict[str, str | int | None]:
    """Maak de GeoJSON-properties voor een BAG-pand."""
    return {
        "jaar": jaar,
        "pand_id": vind_eerste_tekst(pand, "identificatie"),
        "bouwjaar": vind_eerste_tekst(pand, "oorspronkelijkBouwjaar"),
        "pand_status": vind_eerste_tekst(pand, "status"),
        "pand_documentdatum": vind_eerste_tekst(pand, "documentdatum"),
        "pand_documentnummer": vind_eerste_tekst(pand, "documentnummer"),
        "pand_geconstateerd": vind_eerste_tekst(pand, "geconstateerd"),
        "pand_voorkomen_id": vind_eerste_tekst(pand, "voorkomenidentificatie"),
        "pand_begin_geldigheid": vind_eerste_tekst(pand, "beginGeldigheid"),
        "pand_eind_geldigheid": vind_eerste_tekst(pand, "eindGeldigheid"),
        "pand_tijdstip_registratie": vind_eerste_tekst(
            pand,
            "tijdstipRegistratie",
        ),
        "pand_eind_registratie": vind_eerste_tekst(pand, "eindRegistratie"),
        "pand_tijdstip_registratie_lv": vind_eerste_tekst(
            pand,
            "tijdstipRegistratieLV",
        ),
        "pand_tijdstip_eind_registratie_lv": vind_eerste_tekst(
            pand,
            "tijdstipEindRegistratieLV",
        ),
    }


def schrijf_geojson(
    output_pad: Path,
    bag_objecten: Iterable[ET.Element],
    jaar: int,
) -> None:
    """Schrijf BAG-panden naar GeoJSON."""
    print(f"GeoJSON maken: {output_pad}")

    feature_count = 0
    overgeslagen_count = 0

    with output_pad.open("w", encoding="utf-8") as output_file:
        output_file.write('{"type":"FeatureCollection",')
        output_file.write('"name":')
        json.dump(output_pad.stem, output_file)
        output_file.write(',"features":[')

        for bag_object in bag_objecten:
            pand = vind_object(bag_object, "Pand")

            if pand is None:
                overgeslagen_count += 1
                continue

            coordinaten = haal_pandpolygon_op(pand)

            if not coordinaten:
                overgeslagen_count += 1
                continue

            feature = {
                "type": "Feature",
                "properties": maak_pand_eigenschappen(pand, jaar),
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coordinaten,
                },
            }

            if feature_count > 0:
                output_file.write(",")

            json.dump(
                feature,
                output_file,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            feature_count += 1

        output_file.write("]}")

    print(f"GeoJSON geschreven: {output_pad}")
    print(f"GeoJSON polygonen: {feature_count}")

    if overgeslagen_count:
        print(f"Objecten zonder polygon overgeslagen: {overgeslagen_count}")
