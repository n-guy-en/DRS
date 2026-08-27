"""
BAG Fryslân verwerken.

Workflow:
1. Friese woonplaatsen bepalen.
2. WPL-objecten lezen.
3. OPR-objecten lezen.
4. NUM-objecten lezen.
5. VBO-objecten lezen.
6. VBO-NUM-OPR-WPL-koppeltabel maken.
7. PND-objecten exporteren naar CSV, XML en GeoJSON.
"""

# %% Stap 1: imports
from helpers.bag_selectie import (
    bepaal_friese_woonplaats_ids,
    lees_woonplaatsen,
    lees_openbare_ruimtes,
    lees_nummeraanduidingen,
    lees_verblijfsobjecten,
    maak_koppeltabel,
    exporteer_panden,
)
from config import (
    BAG_DIR,
    FRYSLAN_GEMEENTEN,
    BAG_EXPORT_JAREN,
    KOPPELTABEL_PAD,
    MAX_PND_XML_BESTANDEN,
    MAX_XML_BESTANDEN,
    OUTPUT_DIR,
    OUTPUT_JAAR_DIR,
    OUTPUT_XML_DIR,
    PRINT_IEDERE,
)


# %% Stap 2: workflow uitvoeren
def main() -> None:
    """Voer de BAG-workflow uit."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_XML_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JAAR_DIR.mkdir(parents=True, exist_ok=True)

    woonplaats_ids = bepaal_friese_woonplaats_ids(
        bag_dir=BAG_DIR,
        friese_gemeenten=FRYSLAN_GEMEENTEN,
        jaren=BAG_EXPORT_JAREN,
    )

    wpl_df = lees_woonplaatsen(
        bag_dir=BAG_DIR,
        woonplaats_ids=woonplaats_ids,
        max_xml_bestanden=MAX_XML_BESTANDEN,
        print_iedere=PRINT_IEDERE,
    )

    opr_df = lees_openbare_ruimtes(
        bag_dir=BAG_DIR,
        woonplaats_ids=woonplaats_ids,
        wpl_df=wpl_df,
        max_xml_bestanden=MAX_XML_BESTANDEN,
        print_iedere=PRINT_IEDERE,
    )

    openbare_ruimte_ids = set(opr_df["openbare_ruimte_id"])

    num_df = lees_nummeraanduidingen(
        bag_dir=BAG_DIR,
        openbare_ruimte_ids=openbare_ruimte_ids,
        max_xml_bestanden=MAX_XML_BESTANDEN,
        print_iedere=PRINT_IEDERE,
    )

    nummeraanduiding_ids = set(num_df["nummeraanduiding_id"])

    vbo_df = lees_verblijfsobjecten(
        bag_dir=BAG_DIR,
        nummeraanduiding_ids=nummeraanduiding_ids,
        max_xml_bestanden=MAX_XML_BESTANDEN,
        print_iedere=PRINT_IEDERE,
    )

    koppeling_df = maak_koppeltabel(
        vbo_df=vbo_df,
        num_df=num_df,
        opr_df=opr_df,
        output_pad=KOPPELTABEL_PAD,
    )

    exporteer_panden(
        bag_dir=BAG_DIR,
        koppeling_df=koppeling_df,
        jaren=BAG_EXPORT_JAREN,
        output_xml_dir=OUTPUT_XML_DIR,
        output_jaar_dir=OUTPUT_JAAR_DIR,
        max_pnd_xml_bestanden=MAX_PND_XML_BESTANDEN,
        print_iedere=PRINT_IEDERE,
    )

    print("Klaar")


if __name__ == "__main__":
    main()
