# Losse analyses

Deze map bevat aanvullende analyses die buiten de hoofdworkflow vallen. Ze zijn
bedoeld voor verkenning en versie 2 overdracht. De scripts lezen
bestaande output uit `0_layers`, `4_netwerk`, `5_bereikbaarheid` en `6_interpretatie`,
maar schrijven alleen naar `7_analyses/processed/`.

## Ziekenhuis Joure Casus

Maakt een aparte ziekenhuiscasus waarin Sneek en Heerenveen vervallen en
Ziekenhuis Joure wordt toegevoegd. De standaard ziekenhuislaag uit
`3_voorzieningen` blijft ongewijzigd.

```bash
.venv/bin/python 7_analyses/ziekenhuis_joure.py
```

Het script maakt eerst deze voorzieningenlaag:

```text
7_analyses/processed/ziekenhuis_joure/voorzieningen/ziekenhuizen_joure.gpkg
```

Daarna draait het de bestaande workflows voor de aparte voorziening
`ziekenhuis_joure`. De output komt terecht onder:

```text
5_bereikbaarheid/processed/ziekenhuis_joure/
0_layers/processed/5_bereikbaarheid/ziekenhuis_joure/
6_interpretatie/processed/ziekenhuis_joure/
0_layers/processed/6_interpretatie/ziekenhuis_joure/
```

## FSN Bereikbaarheid

Bereken per woonpand in de vier FSN-gemeenten of een centraal FSN-knooppunt
binnen de norm bereikbaar is. De analyse draait per modaliteit, zodat je elke
modus los kunt testen.

```bash
.venv/bin/python 7_analyses/fsn_bereikbaarheid.py --modus fiets
```

Voor OV:

```bash
.venv/bin/python 7_analyses/fsn_bereikbaarheid.py --modus ov_fiets
```

Het OV-tijdvenster, de OV-datum en de stapgrootte worden overgenomen uit
`RUN` in `5_bereikbaarheid/config.py`.

Deze analyse gebruikt de bestaande `5_bereikbaarheid`-rekenlogica, maar draait
als losse casus. De bestemming is per run een expliciet gekozen knooppunt, zoals
`Leeuwarden Station/Busstation` of `Drachten Van Knobelsdorffplein`. Daardoor
wordt zichtbaar welke panden binnen bijvoorbeeld gemeente Leeuwarden goed of
slecht zijn aangesloten op de andere FSN-knooppunten.

De output wordt na elke bestemmingsrun gekopieerd naar:

```text
7_analyses/processed/fsn_knooppuntbereikbaarheid/<modus>/<bestemming>/
```

## Netwerkkwaliteit

Maak losse kwaliteitslagen voor fiets- en voetgangersnetwerk:

```bash
.venv/bin/python 7_analyses/netwerkkwaliteit.py
```

Dit script vergelijkt de NWB-fietslaag en NWB-voetgangerslaag met de NWB-autolaag.
Een segment wordt `gedeeld_met_autonetwerk` wanneer het geometrisch overlapt met
de autolaag of hetzelfde `wvk_id` heeft. Segmenten zonder overlap met de autolaag
worden `vrijliggend_van_autonetwerk`.

De OSM-aanvullingen worden hier niet gebruikt. Voor bereikbaarheid zijn
`fiets_osm` en `voetganger_osm` nuttig, omdat zij ontbrekende routes aanvullen.
Voor netwerkkwaliteit zijn zij minder geschikt als publicatielaag: OSM-lijnen
kunnen dicht langs of op dezelfde plek als autowegen liggen, terwijl uit de
geometrie niet altijd betrouwbaar blijkt of het fysiek een vrijliggend pad is.
Daarom gebruikt deze analyse alleen de NWB-lagen, waar `wvk_id`, wegcategorie en
modaliteitstoegang consistenter met elkaar samenhangen.

Output:

```text
7_analyses/processed/netwerkkwaliteit/fiets/fiets_netwerkkwaliteit.gpkg
7_analyses/processed/netwerkkwaliteit/lopen/lopen_netwerkkwaliteit.gpkg
7_analyses/processed/netwerkkwaliteit/netwerkkwaliteit_samenvatting.csv
```
