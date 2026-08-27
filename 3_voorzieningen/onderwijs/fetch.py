"""
Haal onderwijsinstellingen op uit DUO Open Onderwijsdata.

Output:
- 3_voorzieningen/raw/onderwijs/<bron>.csv
- 3_voorzieningen/processed/onderwijs/<bron>_voor_bag.csv
- 3_voorzieningen/processed/onderwijs/onderwijs_voor_bag.csv
"""

# %% Stap 1: imports en instellingen
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "3_voorzieningen" / "raw" / "onderwijs"
PROCESSED_DIR = BASE_DIR / "3_voorzieningen" / "processed" / "onderwijs"

PROVINCIE_FILTER_WAARDEN = ["Friesland", "Fryslân"]

BRONNEN = {
    "basisonderwijs": {
        "url": "https://duo.nl/open_onderwijsdata/images/02.-alle-schoolvestigingen-basisonderwijs.csv",
        "filter_kolom": "PROVINCIE",
        "filter_waarden": PROVINCIE_FILTER_WAARDEN,
    },
    "vo": {
        "url": "https://duo.nl/open_onderwijsdata/images/02.-alle-vestigingen-vo.csv",
        "filter_kolom": "PROVINCIE",
        "filter_waarden": PROVINCIE_FILTER_WAARDEN,
    },
    "mbo": {
        "url": "https://duo.nl/open_onderwijsdata/images/02.-onderwijslocaties-mbo-met-inschrijvingen-en-geografische-gegevens-per-1-oktober-2025.csv",
        "filter_kolom": "ARBEIDSMARKTREGIO",
        "filter_waarden": PROVINCIE_FILTER_WAARDEN,
    },
}

HBO_WO_ADRESSEN = [
    {
        "INSTELLINGSNAAM": "NHL Stenden Hogeschool",
        "ONDERWIJSSTRUCTUUR": "hbo",
        "STRAATNAAM": "Rengerslaan",
        "HUISNUMMER": "10",
        "POSTCODE": "8917 DD",
        "PLAATSNAAM": "Leeuwarden",
        "GEMEENTENAAM": "Leeuwarden",
        "PROVINCIE": "Friesland",
    },
    {
        "INSTELLINGSNAAM": "Van Hall Larenstein",
        "ONDERWIJSSTRUCTUUR": "hbo",
        "STRAATNAAM": "Agora",
        "HUISNUMMER": "1",
        "POSTCODE": "8934 CJ",
        "PLAATSNAAM": "Leeuwarden",
        "GEMEENTENAAM": "Leeuwarden",
        "PROVINCIE": "Friesland",
    },
    {
        "INSTELLINGSNAAM": "Rijksuniversiteit Groningen Campus Fryslân",
        "ONDERWIJSSTRUCTUUR": "wo",
        "STRAATNAAM": "Wirdumerdijk",
        "HUISNUMMER": "34",
        "POSTCODE": "8911 CE",
        "PLAATSNAAM": "Leeuwarden",
        "GEMEENTENAAM": "Leeuwarden",
        "PROVINCIE": "Friesland",
    },
]

BAG_KOLOM_ALIASES = {
    "Naam_instelling": "INSTELLINGSNAAM",
    "Straatnaam_onderwijslocatie": "STRAATNAAM",
    "Huisnummer_onderwijslocatie": "HUISNUMMER",
    "Huisnummertoevoeging_onderwijslocatie": "HUISNUMMERTOEVOEGING",
    "Postcode_onderwijslocatie": "POSTCODE",
    "Plaats_onderwijslocatie": "PLAATSNAAM",
    "Arbeidsmarktregio": "ARBEIDSMARKTREGIO",
    "Gps_latitude_onderwijslocatie": "latitude",
    "Gps_longitude_onderwijslocatie": "longitude",
}

BAG_KOLOMMEN = [
    "bron",
    "PROVINCIE",
    "VESTIGINGSNAAM",
    "INSTELLINGSNAAM",
    "NAAM INSTELLING",
    "STRAATNAAM",
    "HUISNUMMER-TOEVOEGING",
    "HUISNUMMER",
    "HUISNUMMERTOEVOEGING",
    "POSTCODE",
    "PLAATSNAAM",
    "GEMEENTENAAM",
    "ONDERWIJSSTRUCTUUR",
    "ARBEIDSMARKTREGIO",
    "latitude",
    "longitude",
    "adres_bag",
]


# %% Stap 2: DUO-data ophalen en opslaan
def haal_duo_csv(url):
    request = Request(
        url,
        headers={
            "Accept": "text/csv,*/*",
            "User-Agent": "DUS-onderwijs-fetch/1.0",
        },
    )

    try:
        with urlopen(request, timeout=120) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as fout:
        raise RuntimeError(f"DUO-data ophalen mislukt: {url}") from fout


def lees_duo_csv(url):
    inhoud = haal_duo_csv(url)
    fouten = []

    for encoding in ["utf-8-sig", "cp1252", "latin1"]:
        try:
            return pd.read_csv(
                BytesIO(inhoud),
                sep=";",
                dtype=str,
                encoding=encoding,
            )
        except UnicodeDecodeError as fout:
            fouten.append(f"{encoding}: {fout}")

    raise RuntimeError(
        "DUO CSV kon niet worden gelezen met utf-8-sig, cp1252 of latin1. "
        + " | ".join(fouten)
    )


def schoon_kolommen(df):
    df = df.copy()
    df.columns = df.columns.str.strip()
    return df


def standaardiseer_bag_kolommen(df):
    kolom_aliases = {
        kolom: BAG_KOLOM_ALIASES[kolom]
        for kolom in df.columns
        if kolom in BAG_KOLOM_ALIASES
    }
    return df.rename(columns=kolom_aliases).copy()


def schrijf_raw_csv(df, naam):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_pad = RAW_DIR / f"{naam}.csv"
    df.to_csv(output_pad, index=False, encoding="utf-8-sig")
    print(f"Ruwe DUO-data opgeslagen: {output_pad}")


# %% Stap 3: filteren en adres voor BAG maken
def filter_fryslan(df, kolom, waarden):
    if kolom not in df.columns:
        beschikbare_kolommen = ", ".join(df.columns)
        raise KeyError(
            f"Filterkolom '{kolom}' ontbreekt. Beschikbare kolommen: "
            f"{beschikbare_kolommen}"
        )

    toegestane_waarden = {
        waarde.lower()
        for waarde in waarden
    }
    bron_waarden = df[kolom].astype(str).str.strip().str.lower()

    return df[bron_waarden.isin(toegestane_waarden)].copy()


def combineer_huisnummer(df):
    onderdelen = []

    for kolom in ["HUISNUMMER-TOEVOEGING", "HUISNUMMER", "HUISNUMMERTOEVOEGING"]:
        if kolom in df.columns:
            onderdelen.append(df[kolom].fillna("").astype(str).str.strip())

    if not onderdelen:
        return pd.Series("", index=df.index)

    huisnummer = onderdelen[0]
    for onderdeel in onderdelen[1:]:
        huisnummer = (huisnummer + " " + onderdeel).str.strip()

    return huisnummer.str.replace(r"\s+", " ", regex=True)


def maak_adres_bag(df):
    if "STRAATNAAM" not in df.columns:
        df["adres_bag"] = pd.NA
        return df

    straat = df["STRAATNAAM"].fillna("").astype(str).str.strip()
    huisnummer = combineer_huisnummer(df)

    if "GEMEENTENAAM" in df.columns:
        plaats = df["GEMEENTENAAM"].fillna("").astype(str).str.strip()
    elif "PLAATSNAAM" in df.columns:
        plaats = df["PLAATSNAAM"].fillna("").astype(str).str.strip()
    else:
        plaats = pd.Series("", index=df.index)

    df["adres_bag"] = (
        straat + " " + huisnummer + ", " + plaats
    ).str.replace(r"\s+", " ", regex=True).str.strip(" ,")

    return df


def kies_bag_kolommen(df):
    aanwezige_kolommen = [kolom for kolom in BAG_KOLOMMEN if kolom in df.columns]
    return df[aanwezige_kolommen].copy()


# %% Stap 4: output schrijven
def schrijf_voor_bag_csv(df, naam):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_pad = PROCESSED_DIR / f"{naam}_voor_bag.csv"
    df.to_csv(output_pad, index=False, encoding="utf-8-sig")
    print(f"{naam}: {len(df)} regels opgeslagen: {output_pad}")


def schrijf_gecombineerde_csv(datasets):
    if not datasets:
        return

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    gecombineerd = pd.concat(datasets, ignore_index=True, sort=False)
    output_pad = PROCESSED_DIR / "onderwijs_voor_bag.csv"
    gecombineerd.to_csv(output_pad, index=False, encoding="utf-8-sig")
    print(f"Onderwijs totaal: {len(gecombineerd)} regels opgeslagen: {output_pad}")


# %% Stap 5: workflow uitvoeren
def verwerk_bron(naam, info):
    print(f"Haal DUO-bron op: {naam}")

    df = lees_duo_csv(info["url"])
    df = schoon_kolommen(df)
    schrijf_raw_csv(df, naam)

    df = standaardiseer_bag_kolommen(df)
    df = filter_fryslan(df, info["filter_kolom"], info["filter_waarden"])
    df.insert(0, "bron", naam)
    df = maak_adres_bag(df)
    df = kies_bag_kolommen(df)
    schrijf_voor_bag_csv(df, naam)

    return df


def verwerk_hbo_wo():
    naam = "hbo_wo"
    print("Gebruik handmatige HBO/WO-adressen")

    df = pd.DataFrame(HBO_WO_ADRESSEN)
    schrijf_raw_csv(df, naam)

    df.insert(0, "bron", naam)
    df = maak_adres_bag(df)
    df = kies_bag_kolommen(df)
    schrijf_voor_bag_csv(df, naam)

    return df


def main():
    datasets = []

    for naam, info in BRONNEN.items():
        datasets.append(verwerk_bron(naam, info))

    datasets.append(verwerk_hbo_wo())
    schrijf_gecombineerde_csv(datasets)


if __name__ == "__main__":
    main()
