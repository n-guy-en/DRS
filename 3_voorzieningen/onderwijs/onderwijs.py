"""
Valideer onderwijsinstellingen met BAG-panden.

Input:
- 3_voorzieningen/processed/onderwijs/onderwijs_voor_bag.csv
- 2_bag/bag_frl_xml/vbo_pand_koppeling.csv
- 2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson

Output:
- 0_layers/processed/3_voorzieningen/onderwijs/<niveau>/onderwijs_<niveau>.gpkg
- 3_voorzieningen/processed/onderwijs/onderwijs.csv
- 3_voorzieningen/processed/onderwijs/<niveau>/onderwijs_<niveau>.csv
"""

# %% Stap 1: imports en instellingen
from pathlib import Path
import re
import sys
import unicodedata

import geopandas as gpd
import pandas as pd


VOORZIENINGEN_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(VOORZIENINGEN_DIR))

from helpers.instellingen import (  
    BAG_PEILDATUM,
    BASE_DIR,
    CRS_RD,
    CRS_WGS84,
    GELDIGE_PAND_STATUSSEN,
    JAAR,
)
from helpers.validatie import valideer_kolommen  


# De BAG-pandlaag uit 2_bag gebruikt dezelfde jaarbasis. Voor voorzieningen
# gebruiken we daarom ook 31 december, zodat VBO-adressen en panden op dezelfde
# BAG-peildatum worden beoordeeld.
PEILDATUM = pd.Timestamp(BAG_PEILDATUM)
MAX_COORDINAAT_AFSTAND_METER = 250.0
ONDERWIJS_NIVEAU = {
    "basisonderwijs": "Basisonderwijs",
    "vo": "Voortgezet onderwijs",
    "vmbo": "VMBO",
    "mavo": "MAVO",
    "havo": "HAVO",
    "vwo": "VWO",
    "pro": "Praktijkonderwijs",
    "brugjaar": "Brugjaar",
    "mbo": "MBO",
    "hbo": "HBO",
    "wo": "WO",
}
VO_SUBNIVEAU = {
    "vmbo": {"vbo", "vmbo"},
    "mavo": {"mavo"},
    "havo": {"havo"},
    "vwo": {"vwo", "ath", "atheneum"},
    "pro": {"pro"},
    "brugjaar": {"brugjaar"},
}
STRAATNAAM_AFKORTINGEN = {
    # DUO/BAG-bronnen gebruiken soms standaard Nederlandse adresafkortingen.
    "burg": "burgemeester",
    "burg.": "burgemeester",
    "str": "straat",
    "str.": "straat",
    "wg": "weg",
    "wg.": "weg",
    "ln": "laan",
    "ln.": "laan",
}
STRAATNAAM_INITIALEN = {
    # Enkele onderwijsadressen gebruiken initialen waar BAG volledige
    # voornamen bevat. Houd dit centraal zodat nieuwe initialen zichtbaar zijn.
    "b": "bartholomeus",
    "j": "johan",
    "w": "willem",
}
STRAATNAAM_SUFFIXEN = {
    # Komt voor wanneer afkortingen aan een straatnaam vastzitten, zoals
    # "Stationsstr" of "Rengersln".
    "strjitte": "straat",
    "straat": "straat",
    "str": "straat",
    "wg": "weg",
    "ln": "laan",
}
STRAATNAAM_VARIANTEN = {
    # Friese en Nederlandse schrijfwijzen worden in BAG en DUO gemengd gebruikt.
    "strjitte": "straat",
}
STRAATNAAM_WOORD_CORRECTIES = {
    # Tussenvoegsels worden vaak afgekort in onderwijsbestanden.
    "vd": "van der",
    "v": "van",
}
ONDERWIJS_VERPLICHTE_KOLOMMEN = {
    "STRAATNAAM",
    "POSTCODE",
    "PLAATSNAAM",
    "VESTIGINGSNAAM",
}
BAG_ADRES_VERPLICHTE_KOLOMMEN = {
    "pand_id",
    "openbare_ruimte_naam",
    "postcode",
    "huisnummer",
    "woonplaats_naam",
}
BAG_PAND_VERPLICHTE_KOLOMMEN = {
    "pand_id",
    "geometry",
}
EXACT_MATCH_TYPE = "adres_exact"
MATCH_BETROUWBAARHEID_HOOG = "hoog"
MATCH_CONTROLE_NODIG = "controle_nodig"


# %% Stap 2: normalisatiehelpers
def normaliseer_tekst(waarde: object) -> str:
    """Normaliseer vrije tekst naar lowercase ASCII-achtige vergelijktekst."""
    if pd.isna(waarde):
        return ""

    waarde = str(waarde).strip().lower()
    waarde = unicodedata.normalize("NFKD", waarde)
    waarde = "".join(teken for teken in waarde if not unicodedata.combining(teken))
    waarde = re.sub(r"[-.'’]", " ", waarde)
    return re.sub(r"\s+", " ", waarde)


def vervang_straatnaam_suffix(token: str) -> str:
    """Vervang bekende vastgeplakte straatnaamsuffixen."""
    for suffix, vervanging in sorted(
        STRAATNAAM_SUFFIXEN.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if len(token) > len(suffix) + 1 and token.endswith(suffix):
            return token[: -len(suffix)] + vervanging
    return token


def normaliseer_straatnaam(waarde: object) -> str:
    """Normaliseer straatnamen voor vergelijking tussen DUO en BAG."""
    tekst = normaliseer_tekst(waarde)
    nieuwe_tokens = []

    for token in tekst.split():
        token = STRAATNAAM_AFKORTINGEN.get(token, token)
        token = STRAATNAAM_VARIANTEN.get(token, token)
        token = vervang_straatnaam_suffix(token)
        token = STRAATNAAM_INITIALEN.get(token, token)
        token = STRAATNAAM_WOORD_CORRECTIES.get(token, token)
        nieuwe_tokens.append(token)

    tekst = " ".join(nieuwe_tokens)
    tekst = tekst.replace("ij", "y")
    return tekst


def normaliseer_postcode(waarde: object) -> str:
    """Normaliseer postcodes naar compact hoofdletterformaat."""
    if pd.isna(waarde):
        return ""

    return re.sub(r"\s+", "", str(waarde).upper())


def normaliseer_pand_id(series: pd.Series) -> pd.Series:
    """Normaliseer BAG-pand-id's naar 16 tekens zonder Excel-decimaal."""
    return (
        series.astype("string")
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(16)
    )


def splits_huisnummer(waarde: object) -> tuple[str, str, str]:
    """Splits huisnummer in nummer, huisletter en toevoeging."""
    if pd.isna(waarde):
        return "", "", ""

    tekst = str(waarde).strip()
    match = re.match(r"^(\d+)\s*[-/]?\s*([A-Za-z]?)\s*[-/]?\s*(.*)$", tekst)

    if not match:
        return normaliseer_tekst(waarde), "", ""

    huisnummer = match.group(1)
    huisletter = match.group(2).upper()
    toevoeging = normaliseer_tekst(match.group(3))

    return huisnummer, huisletter, toevoeging


def kies_huisnummerkolom(df: pd.DataFrame) -> pd.Series:
    """Combineer beschikbare huisnummerkolommen tot een adresdeel."""
    huisnummer = pd.Series("", index=df.index)

    if "HUISNUMMER" in df.columns:
        huisnummer = df["HUISNUMMER"].fillna("").astype(str).str.strip()

        huisletter_kolom = None
        if "HUISLETTER" in df.columns:
            huisletter_kolom = "HUISLETTER"
        elif "huisletter" in df.columns:
            huisletter_kolom = "huisletter"

        if huisletter_kolom is not None:
            huisletter = df[huisletter_kolom].fillna("").astype(str).str.strip()
            huisnummer = (huisnummer + " " + huisletter).str.strip()

        if "HUISNUMMERTOEVOEGING" in df.columns:
            toevoeging = df["HUISNUMMERTOEVOEGING"].fillna("").astype(str).str.strip()
            huisnummer = (huisnummer + " " + toevoeging).str.strip()

    if "HUISNUMMER-TOEVOEGING" in df.columns:
        fallback = df["HUISNUMMER-TOEVOEGING"].fillna("").astype(str).str.strip()
        huisnummer = huisnummer.where(huisnummer.ne(""), fallback)

    return huisnummer.str.replace(r"\s+", " ", regex=True)


def voeg_adressleutels_toe(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Voeg genormaliseerde adreskeys toe voor BAG-koppeling."""
    df = df.copy()

    huisnummerdelen = kies_huisnummerkolom(df).apply(splits_huisnummer)
    df[f"{prefix}_straat_key"] = df["STRAATNAAM"].apply(normaliseer_straatnaam)
    df[f"{prefix}_huisnummer_key"] = huisnummerdelen.apply(lambda delen: delen[0])
    df[f"{prefix}_huisletter_key"] = huisnummerdelen.apply(lambda delen: delen[1])
    df[f"{prefix}_toevoeging_key"] = huisnummerdelen.apply(lambda delen: delen[2])
    df[f"{prefix}_postcode_key"] = df["POSTCODE"].apply(normaliseer_postcode)
    if "PLAATSNAAM" in df.columns:
        plaats = df["PLAATSNAAM"]
    elif "woonplaats_naam" in df.columns:
        plaats = df["woonplaats_naam"]
    else:
        plaats = pd.Series("", index=df.index)
    df[f"{prefix}_plaats_key"] = plaats.apply(normaliseer_tekst)

    df[f"{prefix}_exact_adres_key"] = (
        df[f"{prefix}_postcode_key"]
        + "|"
        + df[f"{prefix}_huisnummer_key"]
        + "|"
        + df[f"{prefix}_huisletter_key"]
        + "|"
        + df[f"{prefix}_toevoeging_key"]
        + "|"
        + df[f"{prefix}_straat_key"]
    )
    df[f"{prefix}_basis_adres_key"] = (
        df[f"{prefix}_postcode_key"]
        + "|"
        + df[f"{prefix}_huisnummer_key"]
    )
    df[f"{prefix}_plaats_adres_key"] = (
        df[f"{prefix}_plaats_key"]
        + "|"
        + df[f"{prefix}_huisnummer_key"]
        + "|"
        + df[f"{prefix}_straat_key"]
    )

    return df


def pas_adrescorrecties_toe(onderwijs):
    correcties_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "onderwijs"
        / "adres_correcties.csv"
    )

    onderwijs = onderwijs.copy()
    onderwijs["adres_correctie_toegepast"] = False
    onderwijs["adres_correctie_bron"] = pd.NA

    if not correcties_pad.exists():
        return onderwijs

    print(f"Lees adrescorrecties: {correcties_pad}")
    correcties = pd.read_csv(correcties_pad, dtype="string", encoding="utf-8-sig")
    verplichte_kolommen = {
        "vestigingsnaam",
        "plaatsnaam",
        "straatnaam",
        "huisnummer_toevoeging",
        "postcode",
    }
    ontbrekende_kolommen = verplichte_kolommen - set(correcties.columns)
    if ontbrekende_kolommen:
        raise KeyError(
            "Adrescorrecties missen kolommen: "
            + ", ".join(sorted(ontbrekende_kolommen))
        )

    onderwijs["_correctie_vestiging_key"] = onderwijs["VESTIGINGSNAAM"].apply(
        normaliseer_tekst
    )
    onderwijs["_correctie_plaats_key"] = onderwijs["PLAATSNAAM"].apply(normaliseer_tekst)

    for _, correctie in correcties.iterrows():
        masker = (
            onderwijs["_correctie_vestiging_key"].eq(
                normaliseer_tekst(correctie["vestigingsnaam"])
            )
            & onderwijs["_correctie_plaats_key"].eq(
                normaliseer_tekst(correctie["plaatsnaam"])
            )
        )
        if not masker.any():
            print(
                "Waarschuwing: adrescorrectie niet toegepast voor "
                f"{correctie['vestigingsnaam']} ({correctie['plaatsnaam']})"
            )
            continue

        for kolom in ["STRAATNAAM", "HUISNUMMER-TOEVOEGING", "POSTCODE", "PLAATSNAAM"]:
            origineel_kolom = f"origineel_{kolom.lower().replace('-', '_')}"
            if origineel_kolom not in onderwijs.columns:
                onderwijs[origineel_kolom] = pd.NA
            onderwijs.loc[masker, origineel_kolom] = onderwijs.loc[masker, kolom]

        onderwijs.loc[masker, "STRAATNAAM"] = correctie["straatnaam"]
        onderwijs.loc[masker, "HUISNUMMER-TOEVOEGING"] = correctie[
            "huisnummer_toevoeging"
        ]
        onderwijs.loc[masker, "POSTCODE"] = correctie["postcode"]
        onderwijs.loc[masker, "PLAATSNAAM"] = correctie["plaatsnaam"]
        onderwijs.loc[masker, "adres_correctie_toegepast"] = True
        onderwijs.loc[masker, "adres_correctie_bron"] = correctie.get("bron", pd.NA)

    onderwijs = onderwijs.drop(
        columns=["_correctie_vestiging_key", "_correctie_plaats_key"]
    )

    return onderwijs


# %% Stap 3: onderwijs, BAG-adressen en BAG-panden lezen
def lees_onderwijs():
    input_pad = (
        BASE_DIR
        / "3_voorzieningen"
        / "processed"
        / "onderwijs"
        / "onderwijs_voor_bag.csv"
    )

    if not input_pad.exists():
        raise FileNotFoundError(
            f"Onderwijsbestand niet gevonden: {input_pad}. "
            "Run eerst 3_voorzieningen/onderwijs/fetch.py."
        )

    print(f"Lees onderwijs: {input_pad}")
    onderwijs = pd.read_csv(input_pad, dtype="string", encoding="utf-8-sig")
    valideer_kolommen(onderwijs, ONDERWIJS_VERPLICHTE_KOLOMMEN, "Onderwijsbestand")
    onderwijs["onderwijs_id"] = range(1, len(onderwijs) + 1)

    onderwijs = pas_adrescorrecties_toe(onderwijs)
    onderwijs = voeg_adressleutels_toe(onderwijs, "onderwijs")

    return onderwijs


def lees_bag_adressen():
    input_pad = (
        BASE_DIR
        / "2_bag"
        / "bag_frl_xml"
        / "vbo_pand_koppeling.csv"
    )

    if not input_pad.exists():
        raise FileNotFoundError(f"BAG-adresbestand niet gevonden: {input_pad}")

    print(f"Lees BAG-adressen: {input_pad}")
    adressen = pd.read_csv(input_pad, dtype="string")
    valideer_kolommen(adressen, BAG_ADRES_VERPLICHTE_KOLOMMEN, "BAG-adresbestand")
    adressen["pand_id"] = normaliseer_pand_id(adressen["pand_id"])

    if "vbo_eind_geldigheid" in adressen.columns:
        eind_geldigheid = pd.to_datetime(
            adressen["vbo_eind_geldigheid"],
            errors="coerce",
            format="mixed",
        )
        adressen = adressen[eind_geldigheid.isna() | (eind_geldigheid >= PEILDATUM)].copy()

    adressen = adressen.rename(
        columns={
            "openbare_ruimte_naam": "STRAATNAAM",
            "postcode": "POSTCODE",
            "huisnummer": "HUISNUMMER",
            "huisnummertoevoeging": "HUISNUMMERTOEVOEGING",
        }
    )
    adressen = voeg_adressleutels_toe(adressen, "bag")

    adressen = adressen[adressen["bag_huisnummer_key"].ne("")].copy()

    return adressen


def lees_panden(jaar):
    input_pad = (
        BASE_DIR
        / "2_bag"
        / "bag_frl_xml"
        / "per_jaar"
        / f"pnd_fryslan_{jaar}.geojson"
    )

    if not input_pad.exists():
        raise FileNotFoundError(f"BAG-pandbestand niet gevonden: {input_pad}")

    print(f"Lees BAG-panden: {input_pad}")
    panden = gpd.read_file(input_pad)
    valideer_kolommen(panden, BAG_PAND_VERPLICHTE_KOLOMMEN, "BAG-pandbestand")

    if panden.crs is None:
        panden = panden.set_crs(CRS_WGS84)

    panden = panden.to_crs(CRS_WGS84)
    panden["pand_id"] = normaliseer_pand_id(panden["pand_id"])
    panden = panden[panden.geometry.notna()].copy()
    panden = panden[~panden.geometry.is_empty].copy()

    if "pand_status" in panden.columns:
        panden = panden[panden["pand_status"].isin(GELDIGE_PAND_STATUSSEN)].copy()

    kolommen = [
        "pand_id",
        "bouwjaar",
        "pand_status",
        "pand_begin_geldigheid",
        "geometry",
    ]
    kolommen = [kolom for kolom in kolommen if kolom in panden.columns]

    panden = panden[kolommen].copy()

    gebruik_pad = BASE_DIR / "2_bag" / "processed" / f"bag_pand_gebruik_{jaar}.csv"
    if gebruik_pad.exists():
        print(f"Lees BAG-gebruiksdoelen: {gebruik_pad}")
        gebruik = pd.read_csv(
            gebruik_pad,
            dtype={"pand_id": "string", "gebruiksdoelen": "string"},
            usecols=lambda kolom: kolom in {"pand_id", "gebruiksdoelen"},
        )
        gebruik["pand_id"] = normaliseer_pand_id(gebruik["pand_id"])
        gebruik["bag_heeft_onderwijsfunctie"] = (
            gebruik["gebruiksdoelen"]
            .fillna("")
            .str.contains("onderwijsfunctie", case=False, regex=False)
        )
        gebruik = gebruik.rename(columns={"gebruiksdoelen": "bag_gebruiksdoelen"})
        panden = panden.merge(
            gebruik[["pand_id", "bag_gebruiksdoelen", "bag_heeft_onderwijsfunctie"]],
            on="pand_id",
            how="left",
        )
    else:
        panden["bag_gebruiksdoelen"] = pd.NA
        panden["bag_heeft_onderwijsfunctie"] = False

    panden["bag_heeft_onderwijsfunctie"] = (
        panden["bag_heeft_onderwijsfunctie"].fillna(False).astype(bool)
    )

    return panden.copy()


# %% Stap 4: onderwijs aan BAG-adressen koppelen
def aggregeer_bag_adressen(adressen, sleutelkolom, prefix):
    return (
        adressen
        .drop_duplicates([sleutelkolom, "pand_id"])
        .groupby(sleutelkolom, as_index=False)
        .agg(
            **{
                f"{prefix}_pand_ids": (
                    "pand_id",
                    lambda waarden: ";".join(sorted(set(waarden.dropna()))),
                ),
                f"{prefix}_pand_aantal": ("pand_id", "nunique"),
                f"{prefix}_straatnaam": ("STRAATNAAM", "first"),
                f"{prefix}_huisnummer": ("HUISNUMMER", "first"),
                f"{prefix}_huisletter": ("huisletter", "first"),
                f"{prefix}_huisnummertoevoeging": ("HUISNUMMERTOEVOEGING", "first"),
                f"{prefix}_postcode": ("POSTCODE", "first"),
                f"{prefix}_woonplaats_naam": ("woonplaats_naam", "first"),
            }
        )
    )


def voeg_bag_adresvelden_toe(gekoppeld, bag_adressen):
    gekozen_adressen = (
        bag_adressen.sort_values(
            [
                "pand_id",
                "bag_postcode_key",
                "bag_straat_key",
                "bag_huisnummer_key",
                "bag_huisletter_key",
                "bag_toevoeging_key",
            ]
        )
        .drop_duplicates("pand_id")
        [
            [
                "pand_id",
                "STRAATNAAM",
                "HUISNUMMER",
                "huisletter",
                "HUISNUMMERTOEVOEGING",
                "POSTCODE",
                "woonplaats_naam",
            ]
        ]
        .rename(
            columns={
                "STRAATNAAM": "bag_gekozen_straatnaam",
                "HUISNUMMER": "bag_gekozen_huisnummer",
                "huisletter": "bag_gekozen_huisletter",
                "HUISNUMMERTOEVOEGING": "bag_gekozen_huisnummertoevoeging",
                "POSTCODE": "bag_gekozen_postcode",
                "woonplaats_naam": "bag_gekozen_woonplaats",
            }
        )
    )
    return gekoppeld.merge(gekozen_adressen, on="pand_id", how="left")


def pand_score(pand_id, pand_lookup):
    info = pand_lookup.get(str(pand_id), {})
    return (
        0 if info.get("bag_heeft_onderwijsfunctie", False) else 1,
        str(pand_id),
    )


def kies_pand_uit_ids(pand_ids, pand_lookup):
    ids = [
        str(pand_id).strip()
        for pand_id in str(pand_ids).split(";")
        if str(pand_id).strip()
    ]
    if not ids:
        return pd.NA
    return sorted(ids, key=lambda pand_id: pand_score(pand_id, pand_lookup))[0]


def nummer_als_int(waarde):
    if pd.isna(waarde):
        return pd.NA
    match = re.search(r"\d+", str(waarde))
    if not match:
        return pd.NA
    return int(match.group(0))


def kies_dichtstbijzijnd_adrespand(rij, bag_adressen, pand_lookup):
    doel_nummer = nummer_als_int(rij.get("onderwijs_huisnummer_key"))
    if pd.isna(doel_nummer):
        return None, None

    kandidaten_sets = [
        (
            "adres_postcode_straat_huisnummer_nearest",
            bag_adressen[
                bag_adressen["bag_postcode_key"].eq(rij.get("onderwijs_postcode_key"))
                & bag_adressen["bag_straat_key"].eq(rij.get("onderwijs_straat_key"))
            ],
        ),
        (
            "adres_postcode_huisnummer_nearest",
            bag_adressen[
                bag_adressen["bag_postcode_key"].eq(rij.get("onderwijs_postcode_key"))
            ],
        ),
        (
            "adres_woonplaats_huisnummer_nearest",
            bag_adressen[
                bag_adressen["woonplaats_naam"]
                .fillna("")
                .apply(normaliseer_tekst)
                .eq(normaliseer_tekst(rij.get("PLAATSNAAM")))
            ],
        ),
    ]

    for match_type, kandidaten in kandidaten_sets:
        kandidaten = kandidaten.copy()
        if kandidaten.empty:
            continue
        kandidaten["huisnummer_num"] = kandidaten["HUISNUMMER"].apply(nummer_als_int)
        kandidaten = kandidaten[kandidaten["huisnummer_num"].notna()].copy()
        if kandidaten.empty:
            continue
        kandidaten["heeft_onderwijsfunctie"] = kandidaten["pand_id"].map(
            lambda pand_id: pand_lookup.get(str(pand_id), {}).get(
                "bag_heeft_onderwijsfunctie",
                False,
            )
        )
        kandidaten["nummer_afstand"] = (
            kandidaten["huisnummer_num"].astype(int) - int(doel_nummer)
        ).abs()
        kandidaten = kandidaten.sort_values(
            [
                "nummer_afstand",
                "heeft_onderwijsfunctie",
                "bag_postcode_key",
                "bag_straat_key",
                "HUISNUMMER",
            ],
            ascending=[True, False, True, True, True],
        )
        return kandidaten.iloc[0]["pand_id"], match_type

    return None, None


def betrouwbaarheid_voor_match(match_type: object) -> str:
    """Markeer exacte adresmatches als hoog; andere BAG-matches vragen controle."""
    if str(match_type) == EXACT_MATCH_TYPE:
        return MATCH_BETROUWBAARHEID_HOOG
    return MATCH_CONTROLE_NODIG


def is_bag_gevalideerd(match_type: object) -> bool:
    """Bepaal of een record aan een BAG-pand gekoppeld is."""
    return str(match_type) != "geen_match"


def maak_pand_lookup(panden: pd.DataFrame) -> dict:
    """Maak snelle lookup met BAG-pandmetadata voor matchkeuzes."""
    return (
        panden.set_index("pand_id")[
            ["bag_gebruiksdoelen", "bag_heeft_onderwijsfunctie"]
        ]
        .to_dict("index")
    )


def filter_bag_adressen_op_geldige_panden(
    bag_adressen: pd.DataFrame,
    panden: pd.DataFrame,
) -> pd.DataFrame:
    """Beperk BAG-adressen tot panden die in de pandenlaag geldig zijn."""
    geldige_pand_ids = set(panden["pand_id"].dropna().astype(str))
    return bag_adressen[
        bag_adressen["pand_id"].astype(str).isin(geldige_pand_ids)
    ].copy()


def maak_bag_adres_aggregaties(bag_adressen: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Maak aggregaties voor elke adresmatchstrategie."""
    exact = aggregeer_bag_adressen(
        bag_adressen,
        "bag_exact_adres_key",
        "bag_exact",
    )
    basis = aggregeer_bag_adressen(
        bag_adressen,
        "bag_basis_adres_key",
        "bag_basis",
    )
    plaats_adres = aggregeer_bag_adressen(
        bag_adressen,
        "bag_plaats_adres_key",
        "bag_plaats_adres",
    )
    return {
        "exact": exact,
        "basis": basis,
        "plaats_adres": plaats_adres,
    }


def voeg_adres_aggregaties_toe(
    onderwijs: pd.DataFrame,
    aggregaties: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Voeg BAG-adresaggregaties toe aan onderwijsrecords."""
    gekoppeld = onderwijs.merge(
        aggregaties["exact"],
        left_on="onderwijs_exact_adres_key",
        right_on="bag_exact_adres_key",
        how="left",
    )
    gekoppeld = gekoppeld.merge(
        aggregaties["basis"],
        left_on="onderwijs_basis_adres_key",
        right_on="bag_basis_adres_key",
        how="left",
    )
    gekoppeld = gekoppeld.merge(
        aggregaties["plaats_adres"],
        left_on="onderwijs_plaats_adres_key",
        right_on="bag_plaats_adres_key",
        how="left",
    )

    gekoppeld["pand_id"] = pd.NA
    gekoppeld["bag_match_type"] = "geen_match"
    gekoppeld["bag_adres_pand_aantal"] = pd.NA
    return gekoppeld


def zet_match(
    gekoppeld: pd.DataFrame,
    masker: pd.Series,
    pand_ids_kolom: str,
    pand_aantal_kolom: str,
    match_type: str,
    pand_lookup: dict,
) -> None:
    """Vul BAG-matchvelden voor rijen die bij een strategie horen."""
    if not masker.any():
        return

    gekoppeld.loc[masker, "pand_id"] = (
        gekoppeld.loc[masker, pand_ids_kolom].apply(
            lambda ids: kies_pand_uit_ids(ids, pand_lookup)
        )
    )
    gekoppeld.loc[masker, "bag_match_type"] = match_type
    gekoppeld.loc[masker, "bag_adres_pand_aantal"] = gekoppeld.loc[
        masker,
        pand_aantal_kolom,
    ]


def pas_adresmatch_strategieen_toe(
    gekoppeld: pd.DataFrame,
    pand_lookup: dict,
) -> pd.DataFrame:
    """Pas adresmatchstrategieen toe van meest naar minst betrouwbaar."""
    gekoppeld = gekoppeld.copy()

    exacte_match = gekoppeld["bag_exact_pand_aantal"].fillna(0).astype(int).gt(0)
    zet_match(
        gekoppeld,
        exacte_match,
        "bag_exact_pand_ids",
        "bag_exact_pand_aantal",
        EXACT_MATCH_TYPE,
        pand_lookup,
    )

    plaats_adres_match = (
        gekoppeld["pand_id"].isna()
        & gekoppeld["bag_plaats_adres_pand_aantal"].fillna(0).astype(int).gt(0)
    )
    zet_match(
        gekoppeld,
        plaats_adres_match,
        "bag_plaats_adres_pand_ids",
        "bag_plaats_adres_pand_aantal",
        "adres_plaats_straat_huisnummer",
        pand_lookup,
    )

    basis_uniek = (
        gekoppeld["pand_id"].isna()
        & gekoppeld["bag_basis_pand_aantal"].fillna(0).astype(int).eq(1)
    )
    zet_match(
        gekoppeld,
        basis_uniek,
        "bag_basis_pand_ids",
        "bag_basis_pand_aantal",
        "adres_postcode_huisnummer_straat_overgenomen",
        pand_lookup,
    )

    basis_meerdere = (
        gekoppeld["pand_id"].isna()
        & gekoppeld["bag_basis_pand_aantal"].fillna(0).astype(int).gt(1)
    )
    zet_match(
        gekoppeld,
        basis_meerdere,
        "bag_basis_pand_ids",
        "bag_basis_pand_aantal",
        "adres_postcode_huisnummer_meerdere_panden_gekozen",
        pand_lookup,
    )
    return gekoppeld


def pas_nearest_huisnummer_fallback_toe(
    gekoppeld: pd.DataFrame,
    bag_adressen: pd.DataFrame,
    pand_lookup: dict,
) -> pd.DataFrame:
    """Gebruik nearest huisnummer alleen als herkenbare fallbackmatch."""
    gekoppeld = gekoppeld.copy()
    nog_geen_match = gekoppeld["pand_id"].isna()
    for idx, rij in gekoppeld.loc[nog_geen_match].iterrows():
        pand_id, match_type = kies_dichtstbijzijnd_adrespand(
            rij,
            bag_adressen,
            pand_lookup,
        )
        if pand_id is None:
            continue
        gekoppeld.at[idx, "pand_id"] = pand_id
        gekoppeld.at[idx, "bag_match_type"] = match_type
        gekoppeld.at[idx, "bag_adres_pand_aantal"] = 1

    return gekoppeld


def werk_match_betrouwbaarheid_bij(gekoppeld: pd.DataFrame) -> pd.DataFrame:
    """Werk betrouwbaarheid en harde validatie afgeleid van matchtype bij."""
    gekoppeld = gekoppeld.copy()
    gekoppeld["bag_match_betrouwbaarheid"] = gekoppeld["bag_match_type"].apply(
        betrouwbaarheid_voor_match
    )
    gekoppeld["bag_gevalideerd"] = gekoppeld["bag_match_type"].apply(is_bag_gevalideerd)
    return gekoppeld


def koppel_bag_adressen(onderwijs, bag_adressen, panden):
    # Matchvolgorde: exact adres, plaats-straat-huisnummer,
    # postcode-huisnummer, nearest huisnummer en daarna coordinaatfallback.
    pand_lookup = maak_pand_lookup(panden)
    bag_adressen = filter_bag_adressen_op_geldige_panden(bag_adressen, panden)
    aggregaties = maak_bag_adres_aggregaties(bag_adressen)
    gekoppeld = voeg_adres_aggregaties_toe(onderwijs, aggregaties)
    gekoppeld = pas_adresmatch_strategieen_toe(gekoppeld, pand_lookup)
    gekoppeld = pas_nearest_huisnummer_fallback_toe(
        gekoppeld,
        bag_adressen,
        pand_lookup,
    )
    gekoppeld = werk_match_betrouwbaarheid_bij(gekoppeld)
    gekoppeld = voeg_bag_adresvelden_toe(gekoppeld, bag_adressen)

    return gekoppeld


def voeg_coordinaatfallback_toe(onderwijs, panden):
    ontbreekt = onderwijs["pand_id"].isna()
    if not ontbreekt.any() or not {"latitude", "longitude"} <= set(onderwijs.columns):
        return onderwijs

    latitude = pd.to_numeric(onderwijs.loc[ontbreekt, "latitude"], errors="coerce")
    longitude = pd.to_numeric(onderwijs.loc[ontbreekt, "longitude"], errors="coerce")
    met_coordinaat = ontbreekt.copy()
    met_coordinaat.loc[ontbreekt] = latitude.notna() & longitude.notna()
    if not met_coordinaat.any():
        return onderwijs

    punten = gpd.GeoDataFrame(
        onderwijs.loc[met_coordinaat].copy(),
        geometry=gpd.points_from_xy(
            pd.to_numeric(onderwijs.loc[met_coordinaat, "longitude"], errors="coerce"),
            pd.to_numeric(onderwijs.loc[met_coordinaat, "latitude"], errors="coerce"),
        ),
        crs=CRS_WGS84,
    ).to_crs(CRS_RD)

    panden_rd = panden[["pand_id", "geometry"]].copy().to_crs(CRS_RD)
    nearest = gpd.sjoin_nearest(
        punten,
        panden_rd,
        how="left",
        distance_col="bag_coordinaat_afstand_meter",
    )
    nearest = nearest[
        nearest["bag_coordinaat_afstand_meter"].le(MAX_COORDINAAT_AFSTAND_METER)
    ].copy()
    if nearest.empty:
        return onderwijs

    nearest = nearest.sort_values("bag_coordinaat_afstand_meter").drop_duplicates(
        subset="onderwijs_id",
        keep="first",
    )
    nearest = nearest.set_index("onderwijs_id")
    onderwijs = onderwijs.copy()
    id_index = onderwijs.set_index("onderwijs_id").index
    match_ids = id_index.intersection(nearest.index)
    if match_ids.empty:
        return onderwijs

    for onderwijs_id in match_ids:
        rij_masker = onderwijs["onderwijs_id"].eq(onderwijs_id)
        onderwijs.loc[rij_masker, "pand_id"] = nearest.at[onderwijs_id, "pand_id_right"]
        onderwijs.loc[rij_masker, "bag_match_type"] = "coordinaat_nearest"
        onderwijs.loc[rij_masker, "bag_adres_pand_aantal"] = 1
        onderwijs.loc[rij_masker, "bag_coordinaat_afstand_meter"] = round(
            float(nearest.at[onderwijs_id, "bag_coordinaat_afstand_meter"]),
            2,
        )

    onderwijs = werk_match_betrouwbaarheid_bij(onderwijs)
    return onderwijs


def voeg_pandgeometrie_toe(onderwijs, panden):
    onderwijs = voeg_coordinaatfallback_toe(onderwijs, panden)
    onderwijs = werk_match_betrouwbaarheid_bij(onderwijs)
    onderwijs = onderwijs.merge(
        panden,
        on="pand_id",
        how="left",
    )

    return gpd.GeoDataFrame(onderwijs, geometry="geometry", crs=CRS_WGS84)


def voeg_onderwijsniveau_toe(onderwijs):
    onderwijs = onderwijs.copy()
    bron = onderwijs["bron"].fillna("").astype(str).str.strip().str.lower()
    structuur = (
        onderwijs["ONDERWIJSSTRUCTUUR"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    onderwijs["onderwijs_niveau"] = pd.NA
    onderwijs.loc[bron.eq("basisonderwijs"), "onderwijs_niveau"] = "basisonderwijs"
    onderwijs.loc[bron.eq("vo"), "onderwijs_niveau"] = "vo"
    onderwijs.loc[bron.eq("mbo"), "onderwijs_niveau"] = "mbo"
    onderwijs.loc[
        bron.eq("hbo_wo") & structuur.eq("hbo"),
        "onderwijs_niveau",
    ] = "hbo"
    onderwijs.loc[
        bron.eq("hbo_wo") & structuur.eq("wo"),
        "onderwijs_niveau",
    ] = "wo"

    onderwijs["onderwijs_niveau_naam"] = onderwijs["onderwijs_niveau"].map(
        ONDERWIJS_NIVEAU
    )
    onderwijs["vo_subniveaus"] = onderwijs.apply(bepaal_vo_subniveaus, axis=1)

    return onderwijs


def bepaal_vo_subniveaus(rij):
    if str(rij.get("bron", "")).strip().lower() != "vo":
        return ""

    structuur = normaliseer_tekst(rij.get("ONDERWIJSSTRUCTUUR", ""))
    gevonden = []
    for subniveau, termen in VO_SUBNIVEAU.items():
        if any(re.search(rf"\b{re.escape(term)}\b", structuur) for term in termen):
            gevonden.append(subniveau)
    return ";".join(gevonden)


# %% Stap 5: output schrijven
def schrijf_tabel(
    data: gpd.GeoDataFrame,
    gpkg_pad: Path,
    csv_pad: Path,
    layer_naam: str,
) -> None:
    tijdelijk_gpkg_pad = gpkg_pad.with_name(f"{gpkg_pad.stem}.tmp.gpkg")
    tijdelijk_csv_pad = csv_pad.with_suffix(".tmp.csv")
    tijdelijk_gpkg_pad.unlink(missing_ok=True)

    data.to_file(
        tijdelijk_gpkg_pad,
        layer=layer_naam,
        driver="GPKG",
    )
    data.drop(columns="geometry").to_csv(tijdelijk_csv_pad, index=False)
    tijdelijk_gpkg_pad.replace(gpkg_pad)
    tijdelijk_csv_pad.replace(csv_pad)


def schrijf_controlebestanden(
    onderwijs: gpd.GeoDataFrame,
    output_layers: Path,
    output_csv: Path,
) -> None:
    controle_layers = output_layers / "controle"
    controle_csv = output_csv / "controle"
    controle_layers.mkdir(parents=True, exist_ok=True)
    controle_csv.mkdir(parents=True, exist_ok=True)

    controles = {
        "onderwijs_niet_adres_exact": onderwijs[
            onderwijs["bag_match_type"].ne(EXACT_MATCH_TYPE)
        ].copy(),
        "onderwijs_geen_bag_onderwijsfunctie": onderwijs[
            ~onderwijs["bag_heeft_onderwijsfunctie"].fillna(False).astype(bool)
        ].copy(),
    }

    for naam, data in controles.items():
        if data.empty:
            continue
        gpkg_pad = controle_layers / f"{naam}.gpkg"
        csv_pad = controle_csv / f"{naam}.csv"
        schrijf_tabel(data, gpkg_pad, csv_pad, naam)
        print(f"Opgeslagen: {gpkg_pad}")
        print(f"Opgeslagen: {csv_pad}")


def schrijf_output(onderwijs: gpd.GeoDataFrame) -> None:
    output_layers = (
        BASE_DIR
        / "0_layers"
        / "processed"
        / "3_voorzieningen"
        / "onderwijs"
    )
    output_csv = BASE_DIR / "3_voorzieningen" / "processed" / "onderwijs"
    output_layers.mkdir(parents=True, exist_ok=True)
    output_csv.mkdir(parents=True, exist_ok=True)

    csv_pad = output_csv / "onderwijs.csv"
    tijdelijk_csv_pad = output_csv / "onderwijs.tmp.csv"

    onderwijs.drop(columns="geometry").to_csv(tijdelijk_csv_pad, index=False)
    tijdelijk_csv_pad.replace(csv_pad)
    print(f"Opgeslagen: {csv_pad}")
    schrijf_controlebestanden(onderwijs, output_layers, output_csv)

    for niveau, onderwijs_niveau in onderwijs.groupby("onderwijs_niveau", dropna=True):
        niveau_layers = output_layers / niveau
        niveau_csv = output_csv / niveau
        niveau_layers.mkdir(parents=True, exist_ok=True)
        niveau_csv.mkdir(parents=True, exist_ok=True)

        gpkg_pad = niveau_layers / f"onderwijs_{niveau}.gpkg"
        csv_niveau_pad = niveau_csv / f"onderwijs_{niveau}.csv"
        layer_naam = f"onderwijs_{niveau}"

        schrijf_tabel(onderwijs_niveau, gpkg_pad, csv_niveau_pad, layer_naam)

        print(f"Opgeslagen: {gpkg_pad}")
        print(f"Opgeslagen: {csv_niveau_pad}")

    vo = onderwijs[
        onderwijs["onderwijs_niveau"].eq("vo")
        & onderwijs["vo_subniveaus"].fillna("").astype(str).ne("")
    ].copy()
    if vo.empty:
        return

    vo_subniveaus = vo.assign(
        onderwijs_niveau=vo["vo_subniveaus"].str.split(";")
    ).explode("onderwijs_niveau")
    vo_subniveaus["onderwijs_niveau_naam"] = vo_subniveaus["onderwijs_niveau"].map(
        ONDERWIJS_NIVEAU
    )

    for niveau, onderwijs_niveau in vo_subniveaus.groupby("onderwijs_niveau", dropna=True):
        niveau_layers = output_layers / niveau
        niveau_csv = output_csv / niveau
        niveau_layers.mkdir(parents=True, exist_ok=True)
        niveau_csv.mkdir(parents=True, exist_ok=True)

        gpkg_pad = niveau_layers / f"onderwijs_{niveau}.gpkg"
        csv_niveau_pad = niveau_csv / f"onderwijs_{niveau}.csv"
        layer_naam = f"onderwijs_{niveau}"

        schrijf_tabel(onderwijs_niveau, gpkg_pad, csv_niveau_pad, layer_naam)

        print(f"Opgeslagen: {gpkg_pad}")
        print(f"Opgeslagen: {csv_niveau_pad}")


# %% Stap 6: workflow uitvoeren
def main():
    onderwijs = lees_onderwijs()
    bag_adressen = lees_bag_adressen()
    panden = lees_panden(JAAR)

    gekoppeld = koppel_bag_adressen(onderwijs, bag_adressen, panden)
    gekoppeld = voeg_pandgeometrie_toe(gekoppeld, panden)
    gekoppeld = voeg_onderwijsniveau_toe(gekoppeld)

    print(f"Onderwijs totaal: {len(gekoppeld)}")
    print(f"BAG-gevalideerd: {int(gekoppeld['bag_gevalideerd'].sum())}")
    print(f"Geen BAG-match: {int((~gekoppeld['bag_gevalideerd']).sum())}")
    print(gekoppeld["bag_match_type"].value_counts(dropna=False).to_string())
    print(gekoppeld["onderwijs_niveau"].value_counts(dropna=False).to_string())

    schrijf_output(gekoppeld)


if __name__ == "__main__":
    main()
