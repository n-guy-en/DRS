"""
XML-hulpfuncties voor BAG-bestanden.

Deze module bevat alleen generieke XML-logica:
- namespaces negeren;
- tekstwaarden zoeken;
- BAG-objecten uit ZIP-bestanden lezen;
- XML-bestanden schrijven.
"""

import zipfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator
from pathlib import Path


def lokale_naam(tag: str) -> str:
    """Geef de XML-tag zonder namespace terug."""
    return tag.split("}")[-1]


def vind_eerste_tekst(
    parent: ET.Element,
    naam: str,
) -> str | None:
    """Zoek de eerste tekstwaarde met deze tagnaam."""
    for elem in parent.iter():
        if lokale_naam(elem.tag) == naam:
            return elem.text
    return None


def vind_alle_teksten(
    parent: ET.Element,
    naam: str,
) -> list[str]:
    """Zoek alle tekstwaarden met deze tagnaam."""
    return [
        elem.text
        for elem in parent.iter()
        if lokale_naam(elem.tag) == naam and elem.text
    ]


def vind_object(
    parent: ET.Element,
    objectnaam: str,
) -> ET.Element | None:
    """Zoek een BAG-object binnen een bagObject."""
    for elem in parent.iter():
        if lokale_naam(elem.tag) == objectnaam:
            return elem
    return None


def vind_eerste_element(
    parent: ET.Element,
    naam: str,
) -> ET.Element | None:
    """Zoek het eerste XML-element met deze lokale tagnaam."""
    for elem in parent.iter():
        if lokale_naam(elem.tag) == naam:
            return elem
    return None


def iter_bag_objecten(
    zip_pad: Path,
    max_xml_bestanden: int | None = None,
    print_iedere: int = 50,
) -> Iterator[tuple[str, ET.Element]]:
    """Loop door bagObjecten; kopieer elementen die bewaard moeten blijven."""
    xml_count = 0

    with zipfile.ZipFile(zip_pad) as zip_file:
        xml_bestanden = [
            naam
            for naam in zip_file.namelist()
            if naam.lower().endswith(".xml")
        ]
        totaal_xml = len(xml_bestanden)

        for xml_naam in xml_bestanden:
            if max_xml_bestanden is not None and xml_count >= max_xml_bestanden:
                break

            xml_count += 1

            if (
                xml_count == 1
                or xml_count == totaal_xml
                or (print_iedere and xml_count % print_iedere == 0)
            ):
                print(f"Lees XML: {xml_count}/{totaal_xml}")

            with zip_file.open(xml_naam) as xml_file:
                for _, elem in ET.iterparse(xml_file, events=("end",)):
                    if lokale_naam(elem.tag) == "bagObject":
                        yield xml_naam, elem
                        elem.clear()


def schrijf_xml(
    output_pad: Path,
    bag_objecten: Iterable[ET.Element],
) -> None:
    """Schrijf BAG-objecten naar een XML-bestand."""
    root = ET.Element("bagObjects")

    for bag_object in bag_objecten:
        root.append(bag_object)

    tree = ET.ElementTree(root)
    tree.write(
        output_pad,
        encoding="utf-8",
        xml_declaration=True,
    )