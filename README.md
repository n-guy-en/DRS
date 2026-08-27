# DUS project

Deze projectmap verwerkt ruimtelijke data voor analyses in Fryslân.

De map is ingedeeld per onderwerp. Scripts staan bij het onderwerp waar ze bij
horen. Inputdata staat meestal in `raw/`, gemaakte bestanden in `processed/`.

---
## Installatie

Gebruik bij voorkeur een lokale Python-omgeving in de projectmap. Maak eerst een
`.venv` aan en installeer daarna de benodigde packages uit `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Daarna kunnen scripts vanuit de projectmap worden uitgevoerd met de Python uit
de virtuele omgeving, bijvoorbeeld:

```bash
.venv/bin/python 5_bereikbaarheid/bop.py
```

Op Windows is het activeren van de omgeving anders:

```powershell
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---
## Ruwe bronnen

Ruwe bestanden staan bij de projectstap die ze verwerkt. Daardoor blijft duidelijk
welk script verantwoordelijk is voor welke bron.

Voorbeelden:

```text
1_buurten/raw/Buurten_2026.gpkg
1_buurten/raw/archief/Buurten_2024.gpkg
3_voorzieningen/raw/supermarkt/supermarkt.geojson
3_voorzieningen/raw/ziekenhuis/ziekenhuis.geojson
```

Voor buurtlagen geldt:

* zet de actieve jaargang direct in `1_buurten/raw/`;
* zet oudere jaargangen in `1_buurten/raw/archief/`;
* het script `1_buurten/buurtlaag.py` gebruikt standaard de nieuwste beschikbare jaargang.


# Mappen

| Map | Inhoud |
|---|---|
| `0_layers/` | Centrale GIS-lagen die door meerdere analyses worden gebruikt |
| `1_buurten/` | Buurtdata opschonen en buurtlagen maken |
| `2_bag/` | BAG-panden, pandcentroids, gebruiksdoelen en woonpandselectie |
| `3_voorzieningen/` | Voorzieningen zoals supermarkten, recreatief groen, sport, zorg, onderwijs en ziekenhuizen ophalen en BAG-valideren |
| `4_netwerk/` | OSM-netwerken en verkeerstypen-netwerken |
| `5_bereikbaarheid/` | Bereikbaarheidsberekeningen per voorziening |
| `6_interpretatie/` | Afgeleide interpretatielagen: knelpuntenkaarten en isochronen |
| `7_analyses/` | Losse aanvullende analyses buiten de hoofdworkflow, zoals FSN-knooppuntbereikbaarheid en netwerkkwaliteit |
| `8_rapport/` | Rapporttabellen en legenda's |

---

# Basisprincipe

Elke onderwerpmap volgt zoveel mogelijk deze structuur:

```text
onderwerp/
  README.md          uitleg en workflow
  script.py          scripts voor dit onderwerp
  raw/               originele brondata
  processed/         gemaakte tussen- en eindbestanden
```

`0_layers/` is de centrale plek voor GIS-bestanden die door meerdere onderwerpen
worden gebruikt, bijvoorbeeld buurtlagen, BAG-lagen en bereikbaarheidslagen.

---

# Aanbevolen volgorde

Voor de bereikbaarheids- en interpretatielagen is dit de logische volgorde:

| Stap | Map | Script |
|---|---|---|
| 1 | `1_buurten/` | `buurtlaag.py` |
| 2 | `2_bag/` | `bag.py` |
| 3 | `2_bag/` | `pand_centroids.py` |
| 4 | `2_bag/` | `pand_gebruik.py` |
| 5 | `3_voorzieningen/` | `apotheek/apotheek.py`, `huisarts/huisarts.py`, `onderwijs/onderwijs.py`, `ov/fetch.py`, `recreatief_groen/recreatief_groen.py`, `sport/sport.py`, `supermarkt/supermarkt.py`, `ziekenhuis/ziekenhuis.py` |
| 6 | `3_voorzieningen/` | `filter.py` per voorziening waar aanwezig |
| 7 | `4_netwerk/` | `osm_netwerk.py` |
| 8 | `4_netwerk/` | `NWB_netwerk.py` |
| 9 | `4_netwerk/` | `gtfs_ov_netwerk.py` |
| 10 | `5_bereikbaarheid/` | `config.py`, daarna `bop.py` |
| 11 | `6_interpretatie/` | `config.py`, daarna `interpretatie.py` |
| 12 | `8_rapport/` | `rapport.py` |
| 13 | `8_rapport/` | `legenda.py` |

Losse aanvullende analyses staan buiten deze hoofdvolgorde. Gebruik
`7_analyses/` voor verkennende of presentatiegerichte analyses die de
hoofdpipeline niet mogen verzwaren.

Het analysejaar staat in `2_bag/config.py` als `ANALYSEJAAR`. Dat jaar wordt
ook gebruikt door voorzieningen en netwerk. Instellingen zoals modaliteiten,
tijdvakken, voorzieningen en outputkeuzes staan voor bereikbaarheid in
`5_bereikbaarheid/config.py` en voor interpretatie in `6_interpretatie/config.py`.

De inhoudelijke uitleg over knelpunten, isochronen en multimodale lagen
staat bij de betreffende stap in `6_interpretatie/README.md`.

Rapporttabellen en legenda's worden gemaakt in `8_rapport/`. Deze stap gebruikt
de output uit de eerdere projectstappen en schrijft de gemaakte bestanden naar
`8_rapport/processed/`.

Losse analyse-output uit `7_analyses/` blijft in
`7_analyses/processed/`.
