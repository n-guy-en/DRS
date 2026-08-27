"""
Selectie- en koppelfuncties voor BAG Fryslân.

Deze module bevat de inhoudelijke BAG-workflow:
WPL -> OPR -> NUM -> VBO -> PND

De functies selecteren BAG-objecten voor Fryslân en maken de koppeltabel tussen
panden, verblijfsobjecten, nummeraanduidingen, openbare ruimtes en woonplaatsen.
"""

import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

import pandas as pd

from helpers.bag_geojson import schrijf_geojson
from helpers.bag_xml import (
    iter_bag_objecten,
    lokale_naam,
    vind_eerste_tekst,
    vind_alle_teksten,
    vind_object,
    schrijf_xml,
)


PND_KOLOMMEN = [
    "zip_bestand",
    "xml_bestand",
    "pand_id",
    "bouwjaar",
    "pand_status",
    "pand_documentdatum",
    "pand_documentnummer",
    "pand_geconstateerd",
    "pand_voorkomen_id",
    "pand_begin_geldigheid",
    "pand_eind_geldigheid",
    "pand_tijdstip_registratie",
    "pand_eind_registratie",
    "pand_tijdstip_registratie_lv",
    "pand_tijdstip_eind_registratie_lv",
    "pand_geometrie_poslist",
]


def is_geldig_in_jaar(row, jaar):
    """Controleer of een pandvoorkomen geldig is aan het einde van het jaar."""
    # Bewust eindejaarspeildatum: de jaarlaag moet panden bevatten die aan het
    # einde van het analysejaar bestonden, zoals toegelicht in de README.
    peildatum = f"{jaar}-12-31"
    begin = row["pand_begin_geldigheid"]
    eind = row["pand_eind_geldigheid"]

    return (
        pd.notna(begin)
        and begin <= peildatum
        and (pd.isna(eind) or eind == "" or eind > peildatum)
    )


def bepaal_friese_woonplaats_ids(bag_dir, friese_gemeenten, jaren):
    """Bepaal woonplaats_ids die in de gekozen jaren bij Friese gemeenten horen."""
    print("Stap 1: Friese woonplaatsen bepalen")

    relatie_bestanden = sorted(bag_dir.glob("GEM-WPL-RELATIE-*-*.xml"))

    if not relatie_bestanden:
        raise FileNotFoundError(
            f"Geen GEM-WPL-RELATIE XML gevonden in {bag_dir}."
        )

    relatie_bestand = max(relatie_bestanden, key=lambda pad: pad.name)
    if len(relatie_bestanden) > 1:
        print(
            "Meerdere relatiebestanden gevonden; gebruik nieuwste naam:",
            relatie_bestand.name,
        )

    rows = []

    for _, elem in ET.iterparse(relatie_bestand, events=("end",)):
        if lokale_naam(elem.tag) != "GemeenteWoonplaatsRelatie":
            continue

        ids = vind_alle_teksten(elem, "identificatie")

        if len(ids) >= 2:
            rows.append({
                "woonplaats_id": ids[0].zfill(4),
                "gemeentecode": ids[1].zfill(4),
                "begin": vind_eerste_tekst(elem, "begindatumTijdvakGeldigheid"),
                "eind": vind_eerste_tekst(elem, "einddatumTijdvakGeldigheid"),
                "status": vind_eerste_tekst(elem, "status"),
            })

        elem.clear()

    relaties = pd.DataFrame(
        rows,
        columns=[
            "woonplaats_id",
            "gemeentecode",
            "begin",
            "eind",
            "status",
        ],
    )
    if relaties.empty:
        raise ValueError(
            f"Geen gemeente-woonplaatsrelaties gevonden in {relatie_bestand}."
        )

    relaties["begin"] = pd.to_datetime(relaties["begin"], errors="coerce")
    relaties["eind"] = pd.to_datetime(relaties["eind"], errors="coerce")

    woonplaats_ids = set()

    for jaar in jaren:
        # De woonplaats-gemeenterelatie selecteert welke Friese woonplaatsen
        # in de jaargang horen; de PND-voorkomens zelf worden later per
        # eindejaarspeildatum geselecteerd.
        peildatum = pd.Timestamp(f"{jaar}-01-01")

        geldig = relaties[
            relaties["gemeentecode"].isin(friese_gemeenten)
            & (relaties["begin"] <= peildatum)
            & (
                relaties["eind"].isna()
                | (relaties["eind"] > peildatum)
            )
            & (relaties["status"] == "definitief")
        ]

        woonplaats_ids.update(geldig["woonplaats_id"])

    print(f"Friese woonplaatsen: {len(woonplaats_ids)}")
    return woonplaats_ids


def lees_woonplaatsen(bag_dir, woonplaats_ids, max_xml_bestanden=None, print_iedere=50):
    """Lees WPL-objecten voor de geselecteerde woonplaatsen."""
    print("Stap 2: WPL lezen")

    rows = []

    for zip_pad in sorted(bag_dir.glob("9999WPL*.zip")):
        for _, elem in iter_bag_objecten(zip_pad, max_xml_bestanden, print_iedere):
            obj = vind_object(elem, "Woonplaats")

            if obj is None:
                continue

            woonplaats_id = (
                vind_eerste_tekst(obj, "identificatie") or ""
            ).zfill(4)

            if woonplaats_id in woonplaats_ids:
                rows.append({
                    "woonplaats_id": woonplaats_id,
                    "woonplaats_naam": vind_eerste_tekst(obj, "naam"),
                })

    wpl_df = pd.DataFrame(
        rows,
        columns=["woonplaats_id", "woonplaats_naam"],
    )

    wpl_df = wpl_df.drop_duplicates("woonplaats_id")

    print(f"WPL records: {len(wpl_df)}")
    return wpl_df


def lees_openbare_ruimtes(
    bag_dir,
    woonplaats_ids,
    wpl_df,
    max_xml_bestanden=None,
    print_iedere=50,
):
    """Lees OPR-objecten voor de geselecteerde woonplaatsen."""
    print("Stap 3: OPR lezen")

    rows = []

    for zip_pad in sorted(bag_dir.glob("9999OPR*.zip")):
        for _, elem in iter_bag_objecten(zip_pad, max_xml_bestanden, print_iedere):
            obj = vind_object(elem, "OpenbareRuimte")

            if obj is None:
                continue

            woonplaats_id = vind_eerste_tekst(obj, "WoonplaatsRef")

            if woonplaats_id in woonplaats_ids:
                rows.append({
                    "openbare_ruimte_id": vind_eerste_tekst(obj, "identificatie"),
                    "openbare_ruimte_naam": vind_eerste_tekst(obj, "naam"),
                    "openbare_ruimte_type": vind_eerste_tekst(obj, "type"),
                    "woonplaats_id": woonplaats_id,
                })

    opr_df = pd.DataFrame(
        rows,
        columns=[
            "openbare_ruimte_id",
            "openbare_ruimte_naam",
            "openbare_ruimte_type",
            "woonplaats_id",
        ],
    )

    opr_df = opr_df.drop_duplicates("openbare_ruimte_id")
    opr_df = opr_df.merge(wpl_df, on="woonplaats_id", how="left")

    print(f"OPR records: {len(opr_df)}")
    return opr_df


def lees_nummeraanduidingen(
    bag_dir,
    openbare_ruimte_ids,
    max_xml_bestanden=None,
    print_iedere=50,
):
    """Lees NUM-objecten voor de geselecteerde openbare ruimtes."""
    print("Stap 4: NUM lezen")

    rows = []

    for zip_pad in sorted(bag_dir.glob("9999NUM*.zip")):
        for _, elem in iter_bag_objecten(zip_pad, max_xml_bestanden, print_iedere):
            obj = vind_object(elem, "Nummeraanduiding")

            if obj is None:
                continue

            openbare_ruimte_id = vind_eerste_tekst(obj, "OpenbareRuimteRef")

            if openbare_ruimte_id in openbare_ruimte_ids:
                rows.append({
                    "nummeraanduiding_id": vind_eerste_tekst(obj, "identificatie"),
                    "openbare_ruimte_id": openbare_ruimte_id,
                    "huisnummer": vind_eerste_tekst(obj, "huisnummer"),
                    "huisletter": vind_eerste_tekst(obj, "huisletter"),
                    "huisnummertoevoeging": vind_eerste_tekst(
                        obj,
                        "huisnummertoevoeging",
                    ),
                    "postcode": vind_eerste_tekst(obj, "postcode"),
                    "nummeraanduiding_status": vind_eerste_tekst(obj, "status"),
                })

    num_df = pd.DataFrame(
        rows,
        columns=[
            "nummeraanduiding_id",
            "openbare_ruimte_id",
            "huisnummer",
            "huisletter",
            "huisnummertoevoeging",
            "postcode",
            "nummeraanduiding_status",
        ],
    )

    num_df = num_df.drop_duplicates("nummeraanduiding_id")

    print(f"NUM records: {len(num_df)}")
    return num_df


def lees_verblijfsobjecten(
    bag_dir,
    nummeraanduiding_ids,
    max_xml_bestanden=None,
    print_iedere=50,
):
    """Lees VBO-objecten en koppel deze aan panden."""
    print("Stap 5: VBO lezen")

    rows = []

    for zip_pad in sorted(bag_dir.glob("9999VBO*.zip")):
        for _, elem in iter_bag_objecten(zip_pad, max_xml_bestanden, print_iedere):
            obj = vind_object(elem, "Verblijfsobject")

            if obj is None:
                continue

            nummeraanduiding_id = vind_eerste_tekst(obj, "NummeraanduidingRef")

            if nummeraanduiding_id not in nummeraanduiding_ids:
                continue

            pos = (vind_eerste_tekst(obj, "pos") or "").split()

            for pand_id in vind_alle_teksten(obj, "PandRef"):
                rows.append({
                    "pand_id": pand_id,
                    "verblijfsobject_id": vind_eerste_tekst(obj, "identificatie"),
                    "nummeraanduiding_id": nummeraanduiding_id,
                    "gebruiksdoelen": ";".join(
                        vind_alle_teksten(obj, "gebruiksdoel")
                    ),
                    "oppervlakte": vind_eerste_tekst(obj, "oppervlakte"),
                    "verblijfsobject_status": vind_eerste_tekst(obj, "status"),
                    "vbo_voorkomen_id": vind_eerste_tekst(
                        obj,
                        "voorkomenidentificatie",
                    ),
                    "vbo_begin_geldigheid": vind_eerste_tekst(
                        obj,
                        "beginGeldigheid",
                    ),
                    "vbo_eind_geldigheid": vind_eerste_tekst(
                        obj,
                        "eindGeldigheid",
                    ),
                    "vbo_tijdstip_registratie": vind_eerste_tekst(
                        obj,
                        "tijdstipRegistratie",
                    ),
                    "vbo_eind_registratie": vind_eerste_tekst(
                        obj,
                        "eindRegistratie",
                    ),
                    "vbo_tijdstip_registratie_lv": vind_eerste_tekst(
                        obj,
                        "tijdstipRegistratieLV",
                    ),
                    "vbo_tijdstip_eind_registratie_lv": vind_eerste_tekst(
                        obj,
                        "tijdstipEindRegistratieLV",
                    ),
                    "vbo_documentdatum": vind_eerste_tekst(
                        obj,
                        "documentdatum",
                    ),
                    "vbo_documentnummer": vind_eerste_tekst(
                        obj,
                        "documentnummer",
                    ),
                    "vbo_geconstateerd": vind_eerste_tekst(
                        obj,
                        "geconstateerd",
                    ),
                    "vbo_x": pos[0] if len(pos) >= 2 else None,
                    "vbo_y": pos[1] if len(pos) >= 2 else None,
                })

    vbo_df = pd.DataFrame(
        rows,
        columns=[
            "pand_id",
            "verblijfsobject_id",
            "nummeraanduiding_id",
            "gebruiksdoelen",
            "oppervlakte",
            "verblijfsobject_status",
            "vbo_voorkomen_id",
            "vbo_begin_geldigheid",
            "vbo_eind_geldigheid",
            "vbo_tijdstip_registratie",
            "vbo_eind_registratie",
            "vbo_tijdstip_registratie_lv",
            "vbo_tijdstip_eind_registratie_lv",
            "vbo_documentdatum",
            "vbo_documentnummer",
            "vbo_geconstateerd",
            "vbo_x",
            "vbo_y",
        ],
    )

    print(f"VBO-PND koppelingen: {len(vbo_df)}")
    return vbo_df


def maak_koppeltabel(vbo_df, num_df, opr_df, output_pad):
    """Maak en schrijf de koppeltabel VBO -> NUM -> OPR -> WPL."""
    print("Stap 6: koppeltabel maken")

    koppeling_df = (
        vbo_df
        .merge(num_df, on="nummeraanduiding_id", how="left")
        .merge(opr_df, on="openbare_ruimte_id", how="left")
    )

    koppeling_df = koppeling_df.drop_duplicates()

    output_pad.parent.mkdir(parents=True, exist_ok=True)
    koppeling_df.to_csv(output_pad, index=False)

    print(f"Koppeltabel geschreven: {output_pad}")
    print(f"Koppelingen: {len(koppeling_df)}")
    print(f"Pand ids voor PND-filter: {koppeling_df['pand_id'].nunique()}")

    return koppeling_df


def maak_pand_row(zip_pad, xml_naam, obj):
    """Maak een rij met BAG-pandkenmerken."""
    return {
        "zip_bestand": zip_pad.name,
        "xml_bestand": xml_naam,
        "pand_id": vind_eerste_tekst(obj, "identificatie"),
        "bouwjaar": vind_eerste_tekst(obj, "oorspronkelijkBouwjaar"),
        "pand_status": vind_eerste_tekst(obj, "status"),
        "pand_documentdatum": vind_eerste_tekst(obj, "documentdatum"),
        "pand_documentnummer": vind_eerste_tekst(obj, "documentnummer"),
        "pand_geconstateerd": vind_eerste_tekst(obj, "geconstateerd"),
        "pand_voorkomen_id": vind_eerste_tekst(obj, "voorkomenidentificatie"),
        "pand_begin_geldigheid": vind_eerste_tekst(obj, "beginGeldigheid"),
        "pand_eind_geldigheid": vind_eerste_tekst(obj, "eindGeldigheid"),
        "pand_tijdstip_registratie": vind_eerste_tekst(
            obj,
            "tijdstipRegistratie",
        ),
        "pand_eind_registratie": vind_eerste_tekst(obj, "eindRegistratie"),
        "pand_tijdstip_registratie_lv": vind_eerste_tekst(
            obj,
            "tijdstipRegistratieLV",
        ),
        "pand_tijdstip_eind_registratie_lv": vind_eerste_tekst(
            obj,
            "tijdstipEindRegistratieLV",
        ),
        "pand_geometrie_poslist": vind_eerste_tekst(obj, "posList"),
    }


def exporteer_panden(
    bag_dir,
    koppeling_df,
    jaren,
    output_xml_dir,
    output_jaar_dir,
    max_pnd_xml_bestanden=None,
    print_iedere=50,
    schrijf_tussen_xml=True,
):
    """Exporteer PND-objecten die via VBO aan Fryslân gekoppeld zijn."""
    print("Stap 7: PND exporteren")

    output_xml_dir.mkdir(parents=True, exist_ok=True)
    output_jaar_dir.mkdir(parents=True, exist_ok=True)

    pand_ids = set(koppeling_df["pand_id"].dropna())
    if not pand_ids:
        raise ValueError("De koppeltabel bevat geen pand_ids voor de PND-selectie.")

    rows_per_jaar = {jaar: [] for jaar in jaren}
    xml_per_jaar = {jaar: [] for jaar in jaren}
    xml_count = 0
    limiet_bereikt = False

    for zip_pad in sorted(bag_dir.glob("9999PND*.zip")):
        if limiet_bereikt:
            break

        with zipfile.ZipFile(zip_pad) as zip_file:
            xml_bestanden = [
                naam
                for naam in zip_file.namelist()
                if naam.lower().endswith(".xml")
            ]
            totaal_xml = len(xml_bestanden)

            for lokaal_nummer, xml_naam in enumerate(xml_bestanden, start=1):
                if (
                    max_pnd_xml_bestanden is not None
                    and xml_count >= max_pnd_xml_bestanden
                ):
                    limiet_bereikt = True
                    break

                xml_count += 1

                if (
                    lokaal_nummer == 1
                    or lokaal_nummer == totaal_xml
                    or (print_iedere and xml_count % print_iedere == 0)
                ):
                    print(
                        f"Lees PND: {xml_count} totaal "
                        f"({lokaal_nummer}/{totaal_xml} in {zip_pad.name})",
                        flush=True,
                    )

                pnd_rows = []
                pnd_xml = []

                with zip_file.open(xml_naam) as xml_file:
                    for _, elem in ET.iterparse(xml_file, events=("end",)):
                        if lokale_naam(elem.tag) != "bagObject":
                            continue

                        obj = vind_object(elem, "Pand")

                        if obj is None:
                            elem.clear()
                            continue

                        pand_id = vind_eerste_tekst(obj, "identificatie")

                        if pand_id not in pand_ids:
                            elem.clear()
                            continue

                        row = maak_pand_row(zip_pad, xml_naam, obj)
                        pnd_rows.append(row)

                        if schrijf_tussen_xml:
                            pnd_xml.append(deepcopy(elem))

                        for jaar in jaren:
                            if is_geldig_in_jaar(row, jaar):
                                rows_per_jaar[jaar].append(row.copy())
                                xml_per_jaar[jaar].append(deepcopy(elem))

                        elem.clear()

                if not pnd_rows or not schrijf_tussen_xml:
                    continue

                output_naam = (
                    f"{zip_pad.stem}__{Path(xml_naam).stem}.xml"
                )
                output_xml_pad = output_xml_dir / output_naam
                schrijf_xml(output_xml_pad, pnd_xml)

                print(
                    f"XML geschreven: {output_xml_pad} "
                    f"({len(pnd_rows)} panden)"
                )

    print("Per jaar exporteren")

    for jaar in jaren:
        print(f"Jaar: {jaar}")

        pnd_jaar_df = pd.DataFrame(
            rows_per_jaar[jaar],
            columns=PND_KOLOMMEN,
        )

        pnd_jaar_df = pnd_jaar_df.merge(
            koppeling_df,
            on="pand_id",
            how="left",
        )

        csv_pad = output_jaar_dir / f"pnd_fryslan_{jaar}.csv"
        xml_pad = output_jaar_dir / f"pnd_fryslan_{jaar}.xml"
        geojson_pad = output_jaar_dir / f"pnd_fryslan_{jaar}.geojson"

        pnd_jaar_df.to_csv(csv_pad, index=False)
        print(f"CSV geschreven: {csv_pad}")

        if xml_per_jaar[jaar]:
            schrijf_xml(xml_pad, xml_per_jaar[jaar])
            print(f"XML geschreven: {xml_pad}")
            schrijf_geojson(geojson_pad, xml_per_jaar[jaar], jaar)
