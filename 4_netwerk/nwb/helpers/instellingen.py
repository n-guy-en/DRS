from pathlib import Path
import runpy


def project_dir():
    return Path(__file__).resolve().parents[3]


def lees_bag_analysejaar() -> int:
    """Lees het analysejaar uit de BAG-config."""
    bag_config = runpy.run_path(str(project_dir() / "2_bag" / "config.py"))
    return int(bag_config["ANALYSEJAAR"])


JAAR = lees_bag_analysejaar()

VERKEERSTYPEN = {
    "voetganger": ("vtgngr_h", "vtgngr_t"),
    "fiets": ("fiets_h", "fiets_t"),
    "snorfiets": ("snrfts_h", "snrfts_t"),
    "bromfiets": ("brmfts_h", "brmfts_t"),
    "motorfiets": ("mtrfts_h", "mtrfts_t"),
    "personenauto": ("auto_h", "auto_t"),
    "motorvoertuigen_met_aanhanger": ("aanhngr_h", "aanhngr_t"),
    "vrachtauto": ("vrchtt_h", "vrchtt_t"),
    "autobus": ("autobs_h", "autobs_t"),
    "landbouwvoertuigen": ("lndbw_h", "lndbw_t"),
}

OSM_LOOP_HIGHWAYS = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "track",
}

OSM_FIETS_HIGHWAYS = {
    "cycleway",
    "path",
    "track",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "secondary",
    "primary",
}

ONBEKENDE_WEGCATEGORIEEN = {
    "",
    "onbekend",
}

GEMOTORISEERDE_AANVULLING = {
    "motorfiets",
    "personenauto",
    "motorvoertuigen_met_aanhanger",
    "vrachtauto",
    "autobus",
}

RIJSTROKEN_RELEVANT = GEMOTORISEERDE_AANVULLING

PARKEREN_RELEVANT = {
    "motorfiets",
    "personenauto",
    "motorvoertuigen_met_aanhanger",
}

ONDERZOEK_VERKEERSTYPEN = {
    "voetganger_osm",
    "fiets_osm",
    "personenauto",
    "parkeren",
}

STANDAARD_SNELHEID_KMH = {
    "voetganger": 4.8,
    "voetganger_osm": 4.8,
    "fiets": 15.0,
    "fiets_osm": 15.0,
    "snorfiets": 25.0,
    "bromfiets": 45.0,
    "motorfiets": 50.0,
    "personenauto": 50.0,
    "motorvoertuigen_met_aanhanger": 50.0,
    "vrachtauto": 50.0,
    "autobus": 50.0,
    "landbouwvoertuigen": 25.0,
}

RICHTING_BRONKOLOMMEN = [
    kolom
    for kolommen in VERKEERSTYPEN.values()
    for kolom in kolommen
]

EXPORT_DROP_KOLOMMEN = [
    "wegcategorieen",
    "richting_model",
    "richting_toegang",
    "selectie_bron",
    *RICHTING_BRONKOLOMMEN,
]

EXPORT_KOLOMMEN = [
    "id",
    "wvk_id",
    "begindat",
    "bron_id",
    "straatnaam",
    "baansoort",
    "richting_bron",
    "wegcategorie",
    "verkeerstype",
    "heen_toegestaan",
    "terug_toegestaan",
    "beide_richtingen_toegestaan",
    "lengte_meter",
    "max_snelheid_kmh",
    "snelheid_kmh_gebruikt",
    "reistijd_min",
    "rijstroken_aantal",
    "parkeerpunten_aantal",
    "parkeervlakken_aantal",
    "parkeren_gekoppeld",
    "geometry",
]


def standaard_output_map():
    return project_dir() / "4_netwerk" / "processed" / "NWB"


def standaard_lagen_output_map():
    return project_dir() / "0_layers" / "processed" / "4_netwerk" / "verkeerstypen"


def standaard_nwb_raw_map():
    return project_dir() / "4_netwerk" / "raw" / "NWB"


def standaard_wkd_bronnen_map():
    return standaard_nwb_raw_map() / "WKD"


def standaard_verkeerstypen_pad():
    return standaard_nwb_raw_map() / "verkeerstypen" / "verkeerstypen_frl.json"


def standaard_water_buurten_pad():
    return project_dir() / "0_layers" / "processed" / "1_buurten" / "buurten_basis.gpkg"


def standaard_wegcategorie_pad():
    return standaard_nwb_raw_map() / "wegcategorie" / "wegcategorie_frl.json"


def standaard_snelheden_pad():
    return standaard_nwb_raw_map() / "snelheden" / "snelheden_frl.json"


def standaard_rijstroken_pad():
    return standaard_nwb_raw_map() / "rijstroken" / "rijstroken_frl.json"


def standaard_parkeerpunten_pad():
    return standaard_nwb_raw_map() / "parkeren" / "parkeerpunten_frl.json"


def standaard_parkeervlakken_pad():
    return standaard_nwb_raw_map() / "parkeren" / "parkeervlakken_frl.json"
