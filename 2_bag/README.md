# BAG

Deze map bevat scripts voor het verwerken van BAG-data voor Fryslân.

De BAG-laag wordt binnen dit project gebruikt voor:

* pandpolygonen;
* pandcentroids als vertrekpunten voor bereikbaarheidsanalyses;
* koppeling van panden aan buurten;
* validatie van voorzieningen;
* gebruiksdoelen uit verblijfsobjecten;
* selectie van woonpanden.

## Scripts

| Script               | Functie                                                       |
| -------------------- | ------------------------------------------------------------- |
| `bag.py`             | Maakt BAG-pandbestanden en de VBO-PND-koppeltabel             |
| `pand_centroids.py`  | Maakt pandcentroids en koppelt panden strikt aan buurten     |
| `pand_gebruik.py`    | Verrijkt pandcentroids met geldige VBO-gebruiksdoelen en woonpandindicatoren |

De instellingen die je normaal aanpast staan in:

```text
2_bag/config.py
```

`ANALYSEJAAR` is het jaar dat je analyseert. `BAG_EXPORT_JAREN` bepaalt welke
BAG-jaargangen worden meegenomen of geexporteerd.

Technische hulpfuncties staan in:

```text
2_bag/helpers/
```

Deze helpers horen bij de BAG-verwerking en worden niet als losse analysestap
gedraaid.

## Input
Download het BAG-extractbestand uit: [Kadaster BAG extract downloaden](https://www.kadaster.nl/-/gratis-download-bag-extract)
Plaats dit bestand in:

```text
2_bag/lvbag-extract-nl/
```

Belangrijke BAG-bronnen binnen het extract:

* `PND`: panden, pandgeometrie, bouwjaar en pandstatus;
* `VBO`: verblijfsobjecten, gebruiksdoelen, oppervlaktes en `PandRef`;
* `NUM`: nummeraanduidingen;
* `OPR`: openbare ruimtes;
* `WPL`: woonplaatsen;
* `GEM-WPL-RELATIE`: koppeling tussen gemeenten en woonplaatsen.

Voor de centroidstap is ook de buurtlaag nodig:

```text
0_layers/processed/1_buurten/buurten_basis.gpkg
```

## Workflow

### 1. BAG-extract verwerken

Run:

```bash
python3 2_bag/bag.py
```

Output:

```text
2_bag/bag_frl_xml/vbo_pand_koppeling.csv
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.csv
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.xml
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
```

De koppeltabel bevat de relatie:

```text
pand_id -> verblijfsobject_id -> nummeraanduiding -> openbare ruimte -> woonplaats
```

De GeoJSON-bestanden bevatten de gebouwen uit de Basisregistratie Adressen en Gebouwen (BAG) voor elk analysejaar. Voor ieder jaar wordt de BAG-situatie bepaald op **31 december**. Hierdoor bevat de jaarlaag alle gebouwen die aan het einde van dat jaar bestonden en de bijbehorende status hadden.

Voor het jaar 2026 betekent dit dat de laag de situatie aan het einde van 2026 weergeeft, en niet de situatie op 1 januari 2026. Gebouwen die gedurende het jaar zijn opgeleverd, worden daardoor wel opgenomen. Dit voorkomt dat bijvoorbeeld voorzieningen niet aan het juiste gebouw kunnen worden gekoppeld, omdat dat gebouw eerder in hetzelfde jaar nog als pand in aanbouw geregistreerd stond.

### 2. Pandcentroids maken

Run:

```bash
python3 2_bag/pand_centroids.py
```

Het script gebruikt de waarde van `ANALYSEJAAR` uit `2_bag/config.py`.

Input:

```text
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
0_layers/processed/1_buurten/buurten_basis.gpkg
```

Het script filtert de panden eerst op:

```text
pand_status = Pand in gebruik
```

Daarna worden de pandpolygonen omgezet naar centroids en gekoppeld aan de
buurtlaag met een strikte `within`-koppeling. Als een centroid niet binnen een
buurt valt, stopt de stap met een fout. Dat is bewust: de buurtkoppeling moet
geometrisch kloppen en wordt niet met een afstandsfallback gerepareerd.

Deze filter geldt voor de algemene pandcentroidlaag `bag_panden.gpkg`.
Voorzieningenvalidatie in `3_voorzieningen/` leest de BAG-pandpolygonen opnieuw
en kan per voorziening ruimere pandstatussen gebruiken, zoals `Verbouwing pand`
bij supermarkten.

Output:

```text
0_layers/processed/2_bag/bag_panden.gpkg
```

Belangrijke kolommen in `bag_panden.gpkg`:

* `pand_id`
* `jaar`
* `bouwjaar`
* `pand_status`
* `pand_oppervlakte_m2`
* `pand_x`
* `pand_y`
* `pand_lon`
* `pand_lat`
* `buurtcode`
* `buurtnaam`

`pand_oppervlakte_m2` komt niet als BAG-attribuut mee. Deze wordt berekend uit
de BAG-pandpolygon in RD New (`EPSG:28992`).

### 3. Gebruiksdoelen toevoegen

Run:

```bash
python3 2_bag/pand_gebruik.py
```

Het script gebruikt de waarde van `ANALYSEJAAR` uit `2_bag/config.py`. Dit jaartal
wordt gebruikt voor de CSV-outputnaam.

Input:

```text
2_bag/bag_frl_xml/vbo_pand_koppeling.csv
0_layers/processed/2_bag/bag_panden.gpkg
```

Output:

```text
2_bag/processed/bag_pand_gebruik_2026.csv
0_layers/processed/2_bag/bag_panden.gpkg
```

Het script voegt onder andere deze kolommen toe. De belangrijkste kolommen voor
vervolganalyses zijn `gebruiksdoelen` en `is_woonpand`.

* `vbo_aantal`
* `vbo_in_gebruik_aantal`
* `vbo_woonfunctie_aantal`
* `gebruiksdoelen`
* `is_woonpand`

## Inhoud van de output

De VBO-samenvatting gebruikt alleen VBO-voorkomens die geldig zijn op
31 december van `ANALYSEJAAR`. Dubbele pand-VBO-relaties buiten de peildatum worden
verwijderd, zodat de gebruiksdoelen en aantallen aansluiten op de BAG-situatie
van het analysejaar.

### `gebruiksdoelen`

Komt uit BAG `Verblijfsobject/gebruiksdoel`.

Per pand worden de unieke gebruiksdoelen samengevoegd, bijvoorbeeld:

```text
woonfunctie
logiesfunctie;woonfunctie
winkelfunctie
onderwijsfunctie
```

### `is_woonpand`

Wordt afgeleid uit de gebruiksdoelen.

```text
is_woonpand = True als minstens een gekoppeld VBO gebruiksdoel woonfunctie heeft
```

### VBO-oppervlaktes

VBO-oppervlaktes worden niet als losse VBO-regels aan `bag_panden.gpkg`
toegevoegd. In plaats daarvan worden alleen de VBO-voorkomens meegenomen die
geldig zijn op 31 december van `ANALYSEJAAR`, en daarna geaggregeerd per pand. Zo
blijven oppervlaktes en gebruiksdoelen in dezelfde peildatumselectie.

De belangrijkste oppervlaktevelden zijn:

* `vbo_oppervlakte_totaal`
* `vbo_woonoppervlakte_totaal`

Deze velden zijn vooral bedoeld voor controle en aanvullende interpretatie.
Voor de kern van de pipeline blijven `gebruiksdoelen` en `is_woonpand`
het belangrijkst.

## Gebruik in vervolgprocessen

De BAG-output wordt gebruikt door:

* voorzieningenvalidatie;
* bereikbaarheidsanalyses;
* buurtanalyses op basis van pandcentroids.

Voor bereikbaarheid worden woonpanden geselecteerd met:

```text
is_woonpand = True
```

De volledige pandcentroidlaag blijft beschikbaar voor controles en validatie:

```text
0_layers/processed/2_bag/bag_panden.gpkg
```

## Structuur

```text
2_bag/
├── config.py
├── bag.py
├── pand_centroids.py
├── pand_gebruik.py
├── helpers/
│   ├── bag_geojson.py
│   ├── bag_selectie.py
│   └── bag_xml.py
├── lvbag-extract-nl/
├── bag_frl_xml/
│   ├── per_jaar/
│   └── xml/
└── processed/
```

## Let op

De VBO-koppeltabel bevat alleen VBO-voorkomens die geldig zijn op de
eindejaarspeildatum. De koppeltabel bevat daarnaast nog steeds de relevante
historievelden, zoals:

* `vbo_voorkomen_id`
* `vbo_begin_geldigheid`
* `vbo_eind_geldigheid`
* `vbo_tijdstip_registratie`
* `vbo_eind_registratie`

Gebruik deze kolommen als controle- en herleidbaarheidsvelden. Voor exacte
oppervlakte- of bezettingsanalyses blijft het belangrijk om expliciet te
documenteren dat de telling op pandniveau plaatsvindt en niet op VBO-oppervlak.

## Bronnen

* [Kadaster BAG extract downloaden](https://www.kadaster.nl/-/gratis-download-bag-extract)
