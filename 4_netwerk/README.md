# Netwerken

Deze map maakt de netwerk- en parkeerlagen die worden gebruikt in de
bereikbaarheidsanalyses.

Er zijn vier hoofdonderdelen:

1. `gtfs_ov_netwerk.py`: OV-netwerk uit GTFS/NDOV.
2. `osm_netwerk.py`: OSM-netwerken voor lopen, fietsen en auto.
3. `NWB_netwerk.py`: verkeerstypen-netwerken uit NWB-bronnen, aangevuld met OSM.
4. `parkeergarage.py`: parkeergaragepanden uit RDW Open Data, gevalideerd met BAG.

## Structuur

Ruwe en verwerkte data staan onder `4_netwerk/`:

```text
4_netwerk/
├── raw/
│   ├── GTFS/
│   └── NWB/
├── processed/
│   ├── GTFS/
│   ├── OSM/
│   ├── NWB/
│   └── RDW/
├── ov/
│   └── helpers/
└── nwb/
    └── helpers/
```

Verwerkte lagen voor vervolgstappen staan onder:

```text
0_layers/processed/4_netwerk/
```

## 1. OV-Netwerk Uit GTFS/NDOV

Script:

```bash
.venv/bin/python 4_netwerk/gtfs_ov_netwerk.py
```

### Doel

Dit script maakt een routeerbaar OV-netwerk uit GTFS. Het netwerk bevat bus,
trein en ferry/boot in één samenhangend netwerk.

De reistijden komen uit `stop_times.txt`. De haltevolgorde komt uit de GTFS-
ritten; shapes worden alleen gebruikt voor kaartlijnen en controle.

### Bronnen

Hoofdbron:

```text
4_netwerk/raw/GTFS/gtfs-openov-nl/
```

Bron URL: https://gtfs.openov.nl

Deze mapnaam is bewust vastgezet. Het script stopt als `gtfs-openov-nl`
ontbreekt of geen `stop_times.txt` bevat, zodat niet per ongeluk een andere
GTFS-map wordt gebruikt.

Verplichte GTFS-bestanden:

```text
agency.txt
routes.txt
trips.txt
stops.txt
stop_times.txt
calendar_dates.txt
```

Optionele GTFS-bestanden:

```text
calendar.txt
shapes.txt
```

Extra NDOV-bronnen voor controle en verrijking:

```text
4_netwerk/raw/GTFS/OV_LIJNEN_FRL_ACTUEEL.json
4_netwerk/raw/GTFS/OV_HALTES_FRL_ACTUEEL.json
```

Deze bestanden zijn Friese exports uit landelijke OV-lagen uit het Nationaal
Georegister (NGR). De dataset-eigenaar is Provincie Zuid-Holland. De service
wordt ontsloten via:

```text
https://geodata.zuid-holland.nl/geoserver/verkeer/wms?service=WMS&version=1.3.0&request=GetCapabilities
```

Gebruikte lagen:

```text
OV_LIJNEN_NL_ACTUEEL
OV_HALTES_NL_ACTUEEL
```

Filter:

```text
OV_HALTES_NL_ACTUEEL: Provincie = 'Fryslân'
OV_LIJNEN_NL_ACTUEEL: Provincie LIKE '%Fryslân%'
```

### Belangrijke instellingen

De vaste instellingen staan in `4_netwerk/ov/helpers/instellingen.py`.

Helperstructuur:

```text
4_netwerk/ov/
  helpers/
    instellingen.py
    invoer.py
    validatie.py
    verwerking.py
    edges.py
    samenvatting.py
    kaartlagen.py
    tijd.py
    tekst.py
    geometrie.py
    haltes.py
    lijnen.py
```

Belangrijk:

```text
ROUTE_TYPE_NAAR_MODE = {
    "2": "train",
    "3": "bus",
    "4": "ferry",
}
TOEGESTANE_ROUTE_TYPES = [int(route_type) for route_type in ROUTE_TYPE_NAAR_MODE]
```

Alleen deze operators worden meegenomen:

```text
Arriva
NS
Qbuzz
Wagenborg Passagiersdiensten
Rederij Doeksen
```

Afstanden voor koppeling en controle:

```text
MAX_AFSTAND_GTFS_TOT_HALTE_M = 250
MAX_AFSTAND_HALTE_TOT_OV_LIJN_M = 250
```

Bussegmenten met een originele GTFS-reistijd van 0 minuten worden gecorrigeerd.
Dit kan voorkomen bij korte bussegmenten tussen opeenvolgende haltes, waarbij
de geregistreerde of afgeronde reistijd korter is dan één minuut. Om te
voorkomen dat deze segmenten zonder reistijd in het netwerk terechtkomen,
worden ze gecorrigeerd naar:

```text
BUS_NUL_REISTIJD_SECONDEN = 30
```

De originele waarde blijft beschikbaar in de validatie- en tussenbestanden.

### Verwerking

De workflow volgt de stappen in `gtfs_ov_netwerk.py`:

1. instellingen en outputmappen maken;
2. GTFS-bestanden inlezen;
3. verplichte kolommen controleren;
4. routes verwerken;
5. trips verwerken;
6. stops verwerken en koppelen aan Friese haltegegevens;
7. stop_times verwerken;
8. netwerkedges maken uit opeenvolgende haltes;
9. reistijden per lijnsegment en volledige rit samenvatten;
10. kaartlagen en validatiebestanden schrijven.

### Output

Hoofdoutput:

```text
4_netwerk/processed/GTFS/gtfs_ov_netwerk/line_total_summary.csv
4_netwerk/processed/GTFS/gtfs_ov_netwerk/trip_total_summary.csv
0_layers/processed/4_netwerk/ov/line_total_travel_times.geojson
0_layers/processed/4_netwerk/ov/line_total_stop_points.geojson
```

Validatie en tussenbestanden:

```text
4_netwerk/processed/GTFS/gtfs_ov_netwerk/validatie/
4_netwerk/processed/GTFS/gtfs_ov_netwerk/validatie/tussenbestanden/
4_netwerk/processed/GTFS/gtfs_ov_netwerk/validatie/kaartcontrole/
```

Belangrijke bestanden:

* `line_total_travel_times.geojson`: lijnsegmenten met reistijden.
* `line_total_stop_points.geojson`: haltepunten voor OV-bereikbaarheid.
* `validatie/tussenbestanden/line_total_travel_times.csv`: tijdafhankelijke
  OV-routering in de bereikbaarheidsanalyse.
* `validatie/validatie_edges_gtfs_zero_times.csv`: segmenten waarvan de
  originele GTFS-reistijd 0 minuten was.
* `validatie/kaartcontrole/`: kaartlagen voor visuele controle.

### Gebruik in bereikbaarheidsanalyses

De bereikbaarheidsanalyse gebruikt individuele GTFS-ritsegmenten. Daardoor kan
rekening worden gehouden met:

* vertrektijd;
* aankomsttijd;
* wachttijd;
* overstappen;
* minimale overstaptijd;
* `calendar_dates.txt` en, als aanwezig, `calendar.txt`.

De OV-route wordt opgebouwd als:

```text
pand -> accessnetwerk naar halte -> OV-netwerk -> halte -> loopnetwerk naar voorziening
```

Voor `ov_lopen` is het accessnetwerk lopen. Voor `ov_fiets` is het
accessnetwerk fiets. Het natransport vanaf de uitstaphalte naar de voorziening
is lopen.

De GTFS-ferry's zijn onderdeel van het OV-netwerk via `route_type = 4`. Routes
tussen de Waddeneilanden en de vaste wal, zoals Ameland naar Friesland, tellen
daardoor mee wanneer ze in de GTFS-feed staan. Er is daarom geen aparte
bootroute-laag nodig voor OV-bereikbaarheid.

## 2. OSM-Netwerken

Script:

```bash
.venv/bin/python 4_netwerk/osm_netwerk.py
```

### Doel

Dit script downloadt OpenStreetMap-netwerken met `osmnx` en schrijft deze als
nodes en edges weg. De netwerken worden gebruikt voor lopen, fietsen en auto.

### Installatie

Als `osmnx` ontbreekt:

```bash
python3 -m pip install osmnx
```

### Belangrijke instellingen

De instellingen staan bovenin `osm_netwerk.py`:

```python
GEBIED = "Friesland, Netherlands"
TYPES = ["walk", "bike", "drive"]
OUTPUT = None
VEREENVOUDIGEN = True
OVERSCHRIJVEN = False
DOWNLOAD_POGINGEN = 4
WACHTTIJDEN_SECONDEN = (60, 180, 300)
OVERPASS_URLS = (
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
)
STOP_BIJ_DOWNLOADFOUT = True
```

Betekenis:

* `GEBIED`: gebied dat `osmnx` downloadt.
* `TYPES`: netwerktypen die worden gemaakt.
* `OUTPUT`: aangepaste outputmap; `None` gebruikt de standaardmap.
* `VEREENVOUDIGEN`: OSMnx vereenvoudigt het netwerk.
* `OVERSCHRIJVEN`: bestaande output wordt standaard niet opnieuw gemaakt.
* `DOWNLOAD_POGINGEN`: aantal pogingen per netwerktype bij Overpass-storingen.
* `WACHTTIJDEN_SECONDEN`: wachttijd tussen mislukte downloadpogingen.
* `OVERPASS_URLS`: Overpass-endpoints die na elkaar worden geprobeerd.
* `STOP_BIJ_DOWNLOADFOUT`: stop zonder traceback als Overpass blijft falen.

Overpass kan tijdelijk `504 Gateway Timeout` of `Connection refused` geven.
Dat betekent meestal dat de server op dat moment te zwaar belast is. Het script
probeert dan opnieuw en schrijft pas naar de definitieve GeoPackage-paden als
zowel nodes als edges volledig zijn gemaakt. Bestaande output wordt met
`OVERSCHRIJVEN = False` overgeslagen. Als Overpass na alle pogingen blijft
falen, stopt het script met een korte melding en zonder Python-traceback.

```

### Verwerking

Per netwerk:

1. OSM-netwerk downloaden met `ox.graph_from_place`;
2. reistijd toevoegen;
3. nodes en edges als GeoPackage schrijven.

Voor lopen en fietsen gebruikt het script vaste snelheden:

```text
walk: 4.8 km/u
bike: 15.0 km/u
```

Voor auto gebruikt het script OSMnx-snelheden en reistijden wanneer die
beschikbaar zijn.

### Output

```text
4_netwerk/processed/OSM/walk_nodes.gpkg
4_netwerk/processed/OSM/walk_edges.gpkg
4_netwerk/processed/OSM/bike_nodes.gpkg
4_netwerk/processed/OSM/bike_edges.gpkg
4_netwerk/processed/OSM/drive_nodes.gpkg
4_netwerk/processed/OSM/drive_edges.gpkg
```

De OSMnx-cache staat in:

```text
4_netwerk/processed/OSM/cache/
```

GraphML wordt niet opgeslagen; GeoPackage is de projectoutput.

## 3. NWB-Verkeerstypen

Script:

```bash
.venv/bin/python 4_netwerk/NWB_netwerk.py
```

### Doel

Dit script maakt per verkeerstype een routeerbare netwerklaag. De
NWB-verkeerstypenbron bepaalt welke modaliteiten toegang hebben tot een wegvak.
De geometrische basis komt uit de NWB-snelhedenlaag.

Voor lopen en fietsen worden extra OSM-routes toegevoegd, omdat de
NWB-verkeerstypenbron in de praktijk relevante paden kan missen.

### Bronnen

Ruwe NWB-bronnen:

```text
4_netwerk/raw/NWB/verkeerstypen/verkeerstypen_frl.json
4_netwerk/raw/NWB/wegcategorie/wegcategorie_frl.json
4_netwerk/raw/NWB/snelheden/snelheden_frl.json
4_netwerk/raw/NWB/rijstroken/rijstroken_frl.json
4_netwerk/raw/NWB/parkeren/parkeerpunten_frl.json
4_netwerk/raw/NWB/parkeren/parkeervlakken_frl.json
```

De landelijke WKD-Geopackagebronnen staan bij RWS per peildatum in mappen met
formaat `01-01-<jaar>`. Het bronjaar volgt automatisch `ANALYSEJAAR` uit
`2_bag/config.py` via `JAAR` in
`4_netwerk/nwb/helpers/instellingen.py`:

```python
JAAR = lees_bag_analysejaar()
```

Download voor een complete lokale set deze bestanden voor dat jaar:

```text
wegcategorie:
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Wegcategorisering/01-01-2026/WKD_WEG_CATV2.gpkg

snelheden:
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Maximum%20Snelheden/01-01-2026/Snelheden.gpkg

verkeerstypen:
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Verkeerstypen/01-01-2026/WKD_VRKRSTPNV2.gpkg

rijstroken:
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Rijstroken/01-01-2026/WKD_RIJ_DG_STR.gpkg

parkeren:
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Parkeerpunten/01-01-2026/WKD_Parkpunten.gpkg
https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Parkeervlakken/01-01-2026/WKD_Parkvlak.gpkg
```

De landelijke WKD-lagen bevatten geen provincieveld. Download de GPKG's eerst
lokaal en zet ze naast de Friese raw-exports in de bestaande `raw/NWB`
bronmappen:

```text
4_netwerk/raw/NWB/wegcategorie/WKD_WEG_CATV2.gpkg
4_netwerk/raw/NWB/snelheden/Snelheden.gpkg
4_netwerk/raw/NWB/verkeerstypen/WKD_VRKRSTPNV2.gpkg
4_netwerk/raw/NWB/rijstroken/WKD_RIJ_DG_STR.gpkg
4_netwerk/raw/NWB/parkeren/WKD_Parkpunten.gpkg
4_netwerk/raw/NWB/parkeren/WKD_Parkvlak.gpkg
```

`4_netwerk/NWB_netwerk.py` filtert alle landelijke WKD-bronnen direct naar de
lokale Friese lagen. Als lokaal geen complete WKD-set staat, stopt het
script met een melding welke lokale map wordt verwacht. De Friese selectie
wordt ruimtelijk gefilterd met de buitenste Fryslân grens uit
`0_layers/processed/1_buurten/buurten_basis.gpkg`.

Run de bestaande workflow:

```bash
.venv/bin/python 4_netwerk/NWB_netwerk.py
```

OSM-aanvullingen:

```text
4_netwerk/processed/OSM/walk_edges.gpkg
4_netwerk/processed/OSM/bike_edges.gpkg
```

Interne bron voor watermaskering:

```text
0_layers/processed/1_buurten/buurten_basis.gpkg
```

Buurten met `water = JA` worden alleen gebruikt om landgebonden
NWB-verkeerstypen over water uit te sluiten. Dit filter raakt de GTFS-ferry's
niet: bootverbindingen blijven meetellen in het OV-netwerk via `route_type = 4`.

### Belangrijke Instellingen

De paden staan bovenin `NWB_netwerk.py`:

```python
BRON
WEGCATEGORIE
SNELHEDEN
RIJSTROKEN
PARKEERPUNTEN
PARKEERVLAKKEN
OUTPUT
OSM_WALK_EDGES
OSM_BIKE_EDGES
WATER_BUURTEN
```

Samenvoegingen:

```python
LOOPROUTE_SAMENVOEGING = True
FIETSROUTE_SAMENVOEGING = True
```

De configuratie voor verkeerstypen, standaardsnelheden en OSM-selectie staat in
`4_netwerk/nwb/helpers/instellingen.py`.

Helperstructuur:

```text
4_netwerk/nwb/
  helpers/
    instellingen.py
    normalisatie.py
    invoer.py
    netwerk.py
    export.py
    osm.py
```

### Verwerking

De workflow volgt `NWB_netwerk.py`:

1. verkeerstypenbron inlezen;
2. `snelheden_frl.json` als netwerkbasis inlezen;
3. verkeerstypen koppelen via `wvk_id`;
4. wegcategorieën koppelen via `wvk_id`;
5. rijstroken, parkeerpunten en parkeervlakken koppelen;
6. waterlijnen maskeren;
7. per verkeerstype exporteren;
8. OSM-looproutes en OSM-fietsroutes toevoegen;
9. onderzoekslagen publiceren naar `0_layers`.

### Verkeerstypen

Deze NWB-verkeerstypen worden geëxporteerd:

```text
voetganger
fiets
snorfiets
bromfiets
motorfiets
personenauto
motorvoertuigen_met_aanhanger
vrachtauto
autobus
landbouwvoertuigen
```

Daarnaast worden gecombineerde lagen gemaakt:

```text
voetganger_osm
fiets_osm
```

### Richtingstoegang

In de bron staat `_h` voor heen en `_t` voor terug.

Een wegvak wordt meegenomen wanneer minimaal één richting is toegestaan:

```text
_h = J OR _t = J
```

In de export worden deze velden gebruikt:

```text
heen_toegestaan
terug_toegestaan
beide_richtingen_toegestaan
```

De oorspronkelijke `_h`- en `_t`-kolommen blijven in de brondata, maar worden
niet als losse kolommen in elke exportlaag bewaard.

### Wegcategorie

`wegcategorie_frl.json` wordt gekoppeld aan de snelhedenbasis via `wvk_id`.
De wegcategorie is vooral bedoeld voor analyse, kwaliteitscontrole en
netwerkvalidatie.

Voorbeelden van categorieën:

```text
fietspad
verplicht fietspad
voetpad
lokale weg
straat
autosnelweg
autoweg
erf
onbekend
```

### Snelheden en reistijd

`snelheden_frl.json` levert:

* geometrie;
* straatnaam;
* baansoort;
* bronrichting;
* lengte;
* maximumsnelheid.

De gebruikte standaardsnelheden zijn:

```text
voetganger: 4.8 km/u
fiets: 15 km/u
snorfiets: 25 km/u
bromfiets: 45 km/u
landbouwvoertuigen: 25 km/u
gemotoriseerd fallback: 50 km/u
```

Voor gemotoriseerd verkeer wordt `max_snelheid_kmh` gebruikt wanneer deze
beschikbaar is. Anders wordt de gemotoriseerde fallback gebruikt.

### OSM aanvulling voor Lopen

`voetganger_osm.json` bestaat uit:

1. alle lijnen uit `voetganger.json`;
2. OSM-aanvullingen uit `walk_edges.gpkg`.

De OSM-selectie:

```sql
highway IN ('footway', 'path', 'pedestrian', 'steps', 'track')
```

Er wordt geen ontdubbeling toegepast. Ontbrekende looproutes hebben meer
invloed op bereikbaarheidsuitkomsten dan dubbele parallelle lijnen.

### OSM anvulling voor fietsen

`fiets_osm.json` bestaat uit:

1. alle lijnen uit `fiets.json`;
2. OSM-aanvullingen uit `bike_edges.gpkg`.

De geselecteerde OSM-highwaywaarden staan in `OSM_FIETS_HIGHWAYS` in
`4_netwerk/nwb/helpers/instellingen.py`.

Voor OSM-aanvullingen voor lopen en fietsen wordt zonder expliciete
eenrichtingstag uitgegaan van twee richtingen. Als `oneway` of
`oneway:bicycle` expliciet eenrichting aangeeft, blijft alleen de heenrichting
toegestaan. Deze keuze voorkomt dat ontbrekende OSM-richtingstags de
fietsbereikbaarheid systematisch onderschatten.

### Output

Werkoutput:

```text
4_netwerk/processed/NWB/parkeren.json
4_netwerk/processed/NWB/voetganger.json
4_netwerk/processed/NWB/fiets.json
4_netwerk/processed/NWB/snorfiets.json
4_netwerk/processed/NWB/bromfiets.json
4_netwerk/processed/NWB/motorfiets.json
4_netwerk/processed/NWB/personenauto.json
4_netwerk/processed/NWB/motorvoertuigen_met_aanhanger.json
4_netwerk/processed/NWB/vrachtauto.json
4_netwerk/processed/NWB/autobus.json
4_netwerk/processed/NWB/landbouwvoertuigen.json
4_netwerk/processed/NWB/voetganger_osm.json
4_netwerk/processed/NWB/fiets_osm.json
```

Verwerkte lagen:

```text
0_layers/processed/4_netwerk/verkeerstypen/voetganger_osm.json
0_layers/processed/4_netwerk/verkeerstypen/fiets_osm.json
0_layers/processed/4_netwerk/verkeerstypen/personenauto.json
0_layers/processed/4_netwerk/verkeerstypen/parkeren.json
```

De overige verkeerstypen blijven beschikbaar als werkoutput, maar worden niet
standaard gebruikt in de bereikbaarheidsanalyse.

## 4. Parkeergarages uit RDW

Script:

```bash
.venv/bin/python 4_netwerk/parkeergarage.py
```

### Doel

Dit script maakt een parkeergaragelaag uit RDW Open Data. De RDW-records worden
gekoppeld aan BAG, zodat de output de BAG-pandgeometrie van de parkeergarage
bevat.

### Bronnen

RDW Open Data:

```text
https://opendata.rdw.nl/resource/adw6-9hsg.json
https://opendata.rdw.nl/resource/c653-u9z2.json
https://opendata.rdw.nl/resource/k3dr-ge3w.json
https://opendata.rdw.nl/resource/ygq4-hh5q.json
```

Betekenis:

* `adw6-9hsg`: gebieden;
* `c653-u9z2`: in- en uitgangen;
* `k3dr-ge3w`: GPS-coördinaten;
* `ygq4-hh5q`: parkeeradressen.

BAG-bronnen:

```text
0_layers/processed/2_bag/bag_panden.gpkg
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_2026.geojson
2_bag/bag_frl_xml/vbo_pand_koppeling.csv
```

### Belangrijke instellingen

Bovenin `parkeergarage.py`:

```python
PEILDATUM = pd.Timestamp("2026-12-31")
LIMIT = 50000
CRS_WGS84 = "EPSG:4326"
```

De BAG-laag is de basis voor de pandgeometrie. Daarom gebruikt
`parkeergarage.py` dezelfde eindjaarspeildatum als de BAG-pandselectie.

Output:

```text
0_layers/processed/4_netwerk/verkeerstypen/parkeergarage.geojson
```

### Verwerking

De workflow:

1. RDW-datasets ophalen;
2. verlopen records filteren met de einddatumkolommen;
3. gebieden selecteren met `garage`, `parkeergarage` of `parking` in
   `areadesc`;
4. in-/uitgangen koppelen aan GPS-locaties en adressen;
5. RDW-adreskey maken;
6. BAG-pandpunten, BAG-pandpolygonen en BAG-adressen lezen;
7. RDW-adres aan BAG-adres koppelen;
8. RDW-punt met `within` aan BAG-pand koppelen;
9. beste match kiezen;
10. BAG-pandgeometrie wegschrijven.

### BAG matchtypes

```text
punt_binnen_pand
adres_fallback_punt_niet_in_pand
adres_fallback_geen_punt
geen_match
```

Een record is BAG-gevalideerd wanneer `match_pand_id` gevuld is.

### Output

```text
0_layers/processed/4_netwerk/verkeerstypen/parkeergarage.geojson
```

## Bronnen

Externe bronnen:

* NDOV/OpenOV GTFS-feed in `4_netwerk/raw/GTFS/gtfs-openov-nl/`.
  Herkomst: `https://gtfs.openov.nl`.
* NDOV actuele OV-lijnen en haltes:
  `4_netwerk/raw/GTFS/OV_LIJNEN_FRL_ACTUEEL.json` en
  `4_netwerk/raw/GTFS/OV_HALTES_FRL_ACTUEEL.json`.
  Herkomst: Nationaal Georegister (NGR), dataset-eigenaar Provincie Zuid-Holland,
  WMS/WFS-service
  `https://geodata.zuid-holland.nl/geoserver/verkeer/wms?service=WMS&version=1.3.0&request=GetCapabilities`,
  lagen `OV_LIJNEN_NL_ACTUEEL` en `OV_HALTES_NL_ACTUEEL`. De lokale bestanden
  zijn gefilterd op Fryslân.
* OpenStreetMap via `osmnx`.
* NWB/verkeerstypen:
  `4_netwerk/raw/NWB/verkeerstypen/verkeerstypen_frl.json`.
  Herkomst:
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Verkeerstypen/01-01-2026/WKD_VRKRSTPNV2.gpkg`.
* NWB/wegcategorie:
  `4_netwerk/raw/NWB/wegcategorie/wegcategorie_frl.json`.
  Herkomst:
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Wegcategorisering/01-01-2026/WKD_WEG_CATV2.gpkg`.
* NWB/snelheden:
  `4_netwerk/raw/NWB/snelheden/snelheden_frl.json`.
  Herkomst:
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Maximum%20Snelheden/01-01-2026/Snelheden.gpkg`.
* NWB/rijstroken:
  `4_netwerk/raw/NWB/rijstroken/rijstroken_frl.json`.
  Herkomst:
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Rijstroken/01-01-2026/WKD_RIJ_DG_STR.gpkg`.
* NWB/parkeren:
  `4_netwerk/raw/NWB/parkeren/parkeerpunten_frl.json` en
  `4_netwerk/raw/NWB/parkeren/parkeervlakken_frl.json`.
  Herkomst:
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Parkeerpunten/01-01-2026/WKD_Parkpunten.gpkg` en
  `https://downloads.rijkswaterstaatdata.nl/wkd/geogegevens/Geopackage/Parkeervlakken/01-01-2026/WKD_Parkvlak.gpkg`.
* RDW Open Data:
  `https://opendata.rdw.nl/resource/adw6-9hsg.json`,
  `https://opendata.rdw.nl/resource/c653-u9z2.json`,
  `https://opendata.rdw.nl/resource/k3dr-ge3w.json` en
  `https://opendata.rdw.nl/resource/ygq4-hh5q.json`.

Interne projectbronnen:

* `0_layers/processed/1_buurten/buurten_basis.gpkg` voor watermaskering.
* `0_layers/processed/2_bag/bag_panden.gpkg` voor parkeergarages.
* `2_bag/bag_frl_xml/per_jaar/pnd_fryslan_2026.geojson` voor parkeergarages.
* `2_bag/bag_frl_xml/vbo_pand_koppeling.csv` voor parkeergarages.
