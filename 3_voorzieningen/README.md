# Voorzieningen

Deze map verwerkt voorzieningen voor bereikbaarheidsanalyses. De workflow is per
voorziening grotendeels hetzelfde:

1. brondata ophalen of voorbereiden;
2. BAG-validatie of BAG-koppeling uitvoeren;
3. een selectie maken voor de analyse;
4. de uitkomst wegschrijven naar `processed/` en `0_layers/`.

## Structuur

```text
3_voorzieningen/
  helpers/
  apotheek/
  huisarts/
  onderwijs/
  ov/
  recreatief_groen/
  sport/
  supermarkt/
  ziekenhuis/
  raw/
    <voorziening>/
  processed/
    <voorziening>/
```

Vuistregel:

* brondata staat in `3_voorzieningen/raw/<voorziening>/`;
* tussen- en eindbestanden staan in `3_voorzieningen/processed/<voorziening>/`;
* centrale GIS-lagen staan in `0_layers/processed/3_voorzieningen/<voorziening>/`.

## Invoer

De belangrijkste bronbestanden staan in `3_voorzieningen/raw/<voorziening>/`.
Voorbeelden:

```text
3_voorzieningen/raw/apotheek/apotheek.geojson
3_voorzieningen/raw/huisarts/huisarts.geojson
3_voorzieningen/raw/onderwijs/<bron>.csv
3_voorzieningen/raw/recreatief_groen/recreatief_groen.geojson
3_voorzieningen/raw/sport/sport.geojson
3_voorzieningen/raw/supermarkt/supermarkt.geojson
3_voorzieningen/raw/ziekenhuis/ziekenhuis.geojson
3_voorzieningen/raw/ov/ov_haltes.geojson
```

Voor BAG-validatie is ook de BAG-pandlaag per jaar nodig:

```text
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
```

De vaste gedeelde instellingen staan in:

```text
3_voorzieningen/helpers/instellingen.py
```

Daar staan onder andere `JAAR`, `BAG_PEILDATUM`, `CRS_RD`, `CRS_WGS84`,
`MAX_AFSTAND_METER` en de toegestane pandstatussen. `JAAR` wordt overgenomen uit
`ANALYSEJAAR` in `2_bag/config.py`.

## Bronnen

| Voorziening | Bron |
|---|---|
| `apotheek` | [OpenStreetMap](https://www.openstreetmap.org) (`amenity=pharmacy`, `healthcare=pharmacy`) |
| `huisarts` | [OpenStreetMap](https://www.openstreetmap.org) (`amenity=doctors`, `healthcare=doctor`) |
| `onderwijs` | [DUO Open Onderwijsdata](https://duo.nl/open_onderwijsdata/) |
| `ov` | `4_netwerk/processed/GTFS/gtfs_ov_netwerk/` |
| `recreatief_groen` | [OpenStreetMap](https://www.openstreetmap.org) (`leisure=*`, `landuse=recreation_ground`, `boundary=national_park`) |
| `sport` | [OpenStreetMap](https://www.openstreetmap.org) en Gemeente Súdwest-Fryslân WFS (`leisure=sports_centre`, `leisure=pitch`, `leisure=sports_hall`, `leisure=stadium`, `leisure=track`, `leisure=swimming_pool`, `leisure=horse_riding`) |
| `supermarkt` | [OpenStreetMap](https://www.openstreetmap.org) (`shop=supermarket`, `shop=convenience`, `shop=grocery`, plus ketens op `brand`/`name`) |
| `ziekenhuis` | [OpenStreetMap](https://www.openstreetmap.org) (`amenity=hospital`, `healthcare=hospital`) |

## Verwerking in hoofdlijnen

De puntvoorzieningen volgen meestal dezelfde route:

1. brondata ophalen;
2. geometrie in RD zetten;
3. BAG-validatie uitvoeren;
4. selectie maken;
5. CSV en GPKG wegschrijven.

`onderwijs` wijkt af:

1. DUO-bronnen ophalen en opschonen;
2. adresvelden normaliseren;
3. BAG-adressen en BAG-panden koppelen;
4. controlebestanden en niveau-output schrijven.

## Gedeelde helpers

| Bestand | Functie |
|---|---|
| `helpers/instellingen.py` | Vaste paden, CRS, BAG-analysejaar en afstandsinstellingen |
| `helpers/punt_bag.py` | BAG-koppeling voor puntvoorzieningen |
| `helpers/validatie.py` | Basisvalidaties op kolommen |

## Voorzieningen

| Voorziening | Bron | Validatie | Selectie |
|---|---|---|---|
| `apotheek` | OSM | BAG-pandkoppeling | apotheken |
| `huisarts` | OSM | BAG-pandkoppeling | huisartsenpraktijken |
| `onderwijs` | DUO | BAG-adres en BAG-pand | onderwijsinstellingen |
| `ov` | `4_netwerk` | geen extra BAG-validatie | haltes en stations |
| `recreatief_groen` | OSM | BAG-pandkoppeling | openbaar groen |
| `sport` | OSM + WFS | BAG-pandkoppeling | openbare sportvoorzieningen |
| `supermarkt` | OSM | BAG-pandkoppeling | grote supermarkten |
| `ziekenhuis` | OSM | BAG-pandkoppeling | ziekenhuizen |

## Per voorziening

### Apotheek

OSM-bron via [OpenStreetMap](https://www.openstreetmap.org) met apotheken via
`amenity=pharmacy` en `healthcare=pharmacy`.
Na BAG-koppeling volgen selectie en export naar `processed/apotheek/`.
De selectiestap houdt apotheken met apotheek-tags, apotheeknamen of bekende
apotheekketens vast en sluit afhaal- of veterinaire uitzonderingen uit.

### Huisarts

OSM-bron via [OpenStreetMap](https://www.openstreetmap.org) met
huisartspraktijken via `amenity=doctors` en `healthcare=doctor`. Na
BAG-koppeling volgen selectie en export naar `processed/huisarts/`.
De selectiestap sluit duidelijke niet-huisartsen uit, zoals tandartsen,
dierenartsen, fysiotherapie, GGZ/GGD, ziekenhuizen, ambulanceposten en andere
specialistische praktijken.

### Onderwijs

DUO-bronnen uit [Open Onderwijsdata](https://duo.nl/open_onderwijsdata/)
worden samengevoegd, opgeschoond en via BAG-adressen en BAG-panden gekoppeld.
De controle-output staat apart in `processed/onderwijs/controle/`.

### OV

Haltes en stations komen uit de NDOV/GTFS-werkstroom in `4_netwerk`.
Het rawbestand `3_voorzieningen/raw/ov/ov_haltes.geojson` wordt bewust in git
meegenomen, zodat de OV-voorziening ook beschikbaar is zonder de zware
netwerkstap opnieuw te draaien. Deze stap schrijft daarnaast naar
`processed/ov/` en `0_layers/`.

### Recreatief groen

OSM-bron via [OpenStreetMap](https://www.openstreetmap.org) voor openbaar
groen en recreatiegebieden. Na validatie volgt export naar
`processed/recreatief_groen/`. De selectiestap sluit privegroen,
niet-toegankelijk groen en lege, losse tuinen zonder naam uit.

### Sport

OSM en gemeentelijke WFS-bron via [OpenStreetMap](https://www.openstreetmap.org)
voor sportlocaties. Na validatie volgt export naar `processed/sport/`.
De selectiestap sluit prive- of leden-only locaties uit en houdt alleen
bruikbare sportvoorzieningen zoals sportcentra, velden, sporthallen, stadions,
banen, zwembaden en paardrijvoorzieningen vast. Gemeentelijke WFS-records uit
Súdwest-Fryslân worden als geldig meegenomen.

### Supermarkt

OSM-bron via [OpenStreetMap](https://www.openstreetmap.org) voor supermarkten
en aanverwante winkels, inclusief ketenlogica. Na validatie volgt export naar
`processed/supermarkt/`.

### Ziekenhuis

OSM-bron via [OpenStreetMap](https://www.openstreetmap.org) voor ziekenhuizen
via `amenity=hospital` en `healthcare=hospital`. Na BAG-koppeling volgt export
naar `processed/ziekenhuis/`.

## BAG-basis

Voor alle BAG-validatie wordt dezelfde pandlaag gebruikt:

```text
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
```

De BAG-peildatum is 31 december van `JAAR` uit
`3_voorzieningen/helpers/instellingen.py`; die waarde volgt `ANALYSEJAAR` uit
`2_bag/config.py`. Panden met status `Pand in gebruik` en
`Verbouwing pand` worden meegenomen, tenzij een voorziening expliciet anders
werkt.

## Workflow per voorziening

### Apotheek

```bash
python3 3_voorzieningen/apotheek/fetch.py
python3 3_voorzieningen/apotheek/apotheek.py
python3 3_voorzieningen/apotheek/filter.py
```

Output:

```text
3_voorzieningen/raw/apotheek/apotheek.geojson
3_voorzieningen/processed/apotheek/apotheek.csv
3_voorzieningen/processed/apotheek/apotheek_groot.csv
0_layers/processed/3_voorzieningen/apotheek/apotheek.gpkg
0_layers/processed/3_voorzieningen/apotheek/apotheek_groot.gpkg
```

### Huisarts

```bash
python3 3_voorzieningen/huisarts/fetch.py
python3 3_voorzieningen/huisarts/huisarts.py
python3 3_voorzieningen/huisarts/filter.py
```

Output:

```text
3_voorzieningen/raw/huisarts/huisarts.geojson
3_voorzieningen/processed/huisarts/huisarts.csv
3_voorzieningen/processed/huisarts/huisarts_groot.csv
0_layers/processed/3_voorzieningen/huisarts/huisarts.gpkg
0_layers/processed/3_voorzieningen/huisarts/huisarts_groot.gpkg
```

### Onderwijs

```bash
python3 3_voorzieningen/onderwijs/fetch.py
python3 3_voorzieningen/onderwijs/onderwijs.py
```

Output:

```text
3_voorzieningen/raw/onderwijs/<bron>.csv
3_voorzieningen/processed/onderwijs/<bron>_voor_bag.csv
3_voorzieningen/processed/onderwijs/onderwijs_voor_bag.csv
0_layers/processed/3_voorzieningen/onderwijs/<niveau>/onderwijs_<niveau>.gpkg
```

Onderwijs werkt anders dan de puntvoorzieningen:

* eerst worden DUO-bronnen opgeschoond en samengevoegd;
* daarna wordt via BAG-adressen en BAG-panden gekoppeld;
* de validatie is gericht op adresherkenning en plausibele pandkoppeling.

### OV

```bash
python3 3_voorzieningen/ov/fetch.py
```

Output:

```text
3_voorzieningen/raw/ov/ov_haltes.geojson
3_voorzieningen/processed/ov/ov_haltes.gpkg
0_layers/processed/3_voorzieningen/ov/ov_haltes.gpkg
```

### Recreatief groen

```bash
python3 3_voorzieningen/recreatief_groen/fetch.py
python3 3_voorzieningen/recreatief_groen/recreatief_groen.py
python3 3_voorzieningen/recreatief_groen/filter.py
```

Output:

```text
3_voorzieningen/raw/recreatief_groen/recreatief_groen.geojson
3_voorzieningen/processed/recreatief_groen/recreatief_groen.csv
3_voorzieningen/processed/recreatief_groen/recreatief_groen_groot.csv
0_layers/processed/3_voorzieningen/recreatief_groen/recreatief_groen.gpkg
0_layers/processed/3_voorzieningen/recreatief_groen/recreatief_groen_groot.gpkg
```

### Sport

```bash
python3 3_voorzieningen/sport/fetch.py
python3 3_voorzieningen/sport/sport.py
python3 3_voorzieningen/sport/filter.py
```

Output:

```text
3_voorzieningen/raw/sport/sport.geojson
3_voorzieningen/processed/sport/sport.csv
3_voorzieningen/processed/sport/sport_groot.csv
0_layers/processed/3_voorzieningen/sport/sport.gpkg
0_layers/processed/3_voorzieningen/sport/sport_groot.gpkg
```

### Supermarkt

```bash
python3 3_voorzieningen/supermarkt/fetch.py
python3 3_voorzieningen/supermarkt/supermarkt.py
python3 3_voorzieningen/supermarkt/filter.py
```

Output:

```text
3_voorzieningen/raw/supermarkt/supermarkt.geojson
3_voorzieningen/processed/supermarkt/supermarkten.csv
3_voorzieningen/processed/supermarkt/supermarkten_groot.csv
0_layers/processed/3_voorzieningen/supermarkt/supermarkten.gpkg
0_layers/processed/3_voorzieningen/supermarkt/supermarkten_groot.gpkg
```

### Ziekenhuis

```bash
python3 3_voorzieningen/ziekenhuis/fetch.py
python3 3_voorzieningen/ziekenhuis/ziekenhuis.py
```

Output:

```text
3_voorzieningen/raw/ziekenhuis/ziekenhuis.geojson
3_voorzieningen/processed/ziekenhuis/ziekenhuizen.csv
0_layers/processed/3_voorzieningen/ziekenhuis/ziekenhuizen.gpkg
```

## Output per voorziening

De centrale lagen staan in `0_layers/processed/3_voorzieningen/<voorziening>/`.
De tabellen staan in `3_voorzieningen/processed/<voorziening>/`.

## Extra info

### Puntvoorzieningen

* `apotheek`, `huisarts`, `recreatief_groen`, `sport`, `supermarkt` en
  `ziekenhuis` zijn
  puntvoorzieningen of worden als punt behandeld.
* Deze voorzieningen worden geometrisch aan BAG-panden gekoppeld met eerst
  `within` en daarna een beperkte `nearest`-fallback.
* De BAG-validatie is bedoeld om het voorzieningpunt aan het juiste pand te
  hangen, niet om een inhoudelijke broncontrole volledig te vervangen.

### Recreatief groen

* Recreatief groen wordt op basis van OSM-tags gefilterd op openbaar bruikbaar
  groen.
* De BAG-koppeling is hier vooral een controle op ligging en bronkwaliteit.
* Uitgesloten worden onder andere `access=private`, `access=no`,
  `access=members_only`, `private=yes`, `garden:type=private`,
  `garden:type=residential` en namen met `privé`, `private`, `achtertuin` of
  `volkstuinvereniging`.
* `leisure_garden` zonder naam wordt niet meegenomen, omdat dit vaak losse of
  private tuinen zijn.
* Geldige typen zijn `leisure_park`, `landuse_recreation_ground`,
  `leisure_garden`, `leisure_playground`, `boundary_national_park` en
  `leisure_nature_reserve`.
* Een record moet ook betrouwbaar gekoppeld zijn: bronregister aanwezig of
  BAG/betrouwbaarheid akkoord, plus `bag_match_type=within` of
  `bag_match_type=nearest` met maximaal 50 meter afstand.
* Controle huidige output: 1098 van 2218 records behouden, 1120 uitgesloten.

### Apotheek, huisarts en sportfilter

* Apotheek: uitgesloten worden namen met `dierenapotheek`, `afhaalkluis` of
  `medicijnkluis`. Een record moet daarnaast BAG-gevalideerd zijn. Controle
  huidige output: 48 van 48 records behouden.
* Huisarts: uitgesloten worden duidelijke specialisten of niet-huisartsen,
  waaronder `tandarts`, `dierenarts`, `fysiotherapie`, `fysio`,
  `huidtherapie`, `orthodontie`, `logopedie`, `psycholoog`, `acupunctuur`,
  `podotherapie`, `oogarts`, `verloskundigen`, `ehbo`, `ggd`, `ggz`,
  `ziekenhuis` en `ambulance`. Een record moet daarnaast BAG-gevalideerd zijn.
  Controle huidige output: 89 van 94 records behouden, 5 uitgesloten.
* Sport: uitgesloten worden `access=private`, `access=no`,
  `access=members_only`, `access=membership`, `private=yes` en namen met
  `privé`, `private`, `prive` of `achtertuin`. Geldige leisure-typen zijn
  `sports_centre`, `pitch`, `sports_hall`, `stadium`, `track`,
  `swimming_pool` en `horse_riding`. Gemeentelijke WFS-records
  (`osm_type=municipal_wfs` of `source=gemeente_swf`) worden altijd inhoudelijk
  geldig geacht. Een record moet ook betrouwbaar gekoppeld zijn: bronregister
  aanwezig of BAG/betrouwbaarheid akkoord, plus `bag_match_type=within` of
  `bag_match_type=nearest` met maximaal 50 meter afstand. Controle huidige
  output: 1605 van 2482 records behouden, 877 uitgesloten.

### Onderwijs

* Onderwijs wordt primair op adres aan BAG-verblijfsobjecten en panden
  gekoppeld.
* Houd rekening met handmatige HBO/WO-adressen in `onderwijs/fetch.py`.
* Controlebestanden voor twijfelgevallen staan in
  `3_voorzieningen/processed/onderwijs/controle/` en
  `0_layers/processed/3_voorzieningen/onderwijs/controle/`.
