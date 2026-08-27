# Rapportage reistijdberekening voorzieningenbereikbaarheid

Deze rapportage beschrijft hoe de voorzieningenbereikbaarheid per BAG-pand
wordt berekend voor lopen, fiets, auto en OV. De analyse gebruikt
pandcentroids als herkomstpunten en voorzieningen als bestemmingen. De
berekeningswijze is algemeen opgezet voor meerdere voorzieningen.

## Scope en normen

De analyse wordt uitgevoerd voor woonpanden in Fryslân. Per pand wordt de
kortste reistijd naar een voorziening berekend. Daarna wordt bepaald of het pand
binnen de modaliteitsnorm valt.

| Modaliteit | Norm | Netwerkbasis |
|---|---:|---|
| Lopen | voorziening- of niveauspecifiek | `voetganger_osm.json` |
| Fiets | voorziening- of niveauspecifiek | `fiets_osm.json` |
| Auto | voorziening- of niveauspecifiek | `personenauto.json` plus parkeren en loopnatransport |
| OV met lopen | voorziening- of niveauspecifiek | loopnetwerk naar halte, tijdafhankelijke GTFS-ritten, loopnetwerk naar voorziening |
| OV met fiets | voorziening- of niveauspecifiek | fietsnetwerk naar halte, tijdafhankelijke GTFS-ritten, loopnetwerk naar voorziening |

## Bronnen

De belangrijkste invoerbestanden zijn:

```text
0_layers/processed/2_bag/bag_panden.gpkg
0_layers/processed/3_voorzieningen/<voorziening>/...
0_layers/processed/4_netwerk/verkeerstypen/voetganger_osm.json
0_layers/processed/4_netwerk/verkeerstypen/fiets_osm.json
0_layers/processed/4_netwerk/verkeerstypen/personenauto.json
0_layers/processed/4_netwerk/verkeerstypen/parkeren.json
0_layers/processed/4_netwerk/ov/line_total_stop_points.geojson
4_netwerk/processed/GTFS/gtfs_ov_netwerk/validatie/tussenbestanden/line_total_travel_times.csv
4_netwerk/raw/GTFS/gtfs-openov-nl/calendar_dates.txt
```

Voor OV kan daarnaast `calendar.txt` worden gebruikt als de feed dat bestand
bevat. De huidige openOV/9292-feed bevat de rijdagen vooral in
`calendar_dates.txt`.

De verkeersnetwerken zijn gerichte netwerken. Per lijnsegment staat vast of
reizen in de heenrichting, terugrichting of beide richtingen is toegestaan.
Voor auto bevat het netwerk ook maximumsnelheden, baansoort en bronrichting uit
de NWB-snelhedenlaag.

## Algemene netwerkberekening

Alle modaliteiten gebruiken hetzelfde basisprincipe:

1. De netwerklaag wordt ingelezen als `DiGraph`.
2. Elk lijnsegment wordt gesplitst in een startnode `u` en eindnode `v`.
3. Als `heen_toegestaan = true`, wordt een edge `u -> v` toegevoegd.
4. Als `terug_toegestaan = true`, wordt een edge `v -> u` toegevoegd.
5. De edge-kosten zijn reistijden in minuten.
6. Panden en doelen worden naar het dichtstbijzijnde netwerksegment gesnapt.
7. Vanaf alle doelen wordt met Dijkstra de kortste reistijd naar alle bereikbare
   netwerkknopen berekend.
8. Per pand wordt de beste route via de toegestane richting van het gesnapte
   segment gekozen.

De totale reistijd is:

```text
totale_reistijd =
  snapkosten_van_pand_naar_netwerk
  + reistijd_over_netwerk
  + eventuele modaliteitsspecifieke natransportkosten
```

Snapkosten worden berekend met dezelfde verplaatsingssnelheid als de betreffende
accessmodaliteit.

## Routebewuste snapping

Voor alle netwerkmodaliteiten wordt eerst elk pand naar de dichtstbijzijnde
edge gesnapt. Als die edge door richting of netwerkconnectiviteit geen route
naar een voorziening, parkeerdoel of OV-halte oplevert, zoekt het script binnen
de maximale snapafstand naar een alternatieve edge die wel verbonden is met een
doel.

Daarbij wordt niet alleen afstand gebruikt, maar de laagste totale reistijd:

```text
snapafstand / autosnelheid
+ toegestane edgekosten naar u of v
+ kortste netwerktijd naar parkeerdoel/voorziening
```

Deze fallback is ook belangrijk voor lopen en fietsen. Een pand kan namelijk
het dichtst bij een kleine, losse of topologisch niet verbonden netwerkedge
liggen, terwijl er binnen dezelfde snapafstand wel een bruikbare loop- of
fietsroute ligt.

Voorbeeld: pand `0080100000359457` in Leeuwarden snapte eerst naar een
dichtstbijzijnde eenrichtingssegment op Europaplein. De bereikbare node lag aan
de verkeerde kant van het segment, waardoor de route als onbetrouwbaar werd
gemarkeerd. Met routebewuste snapping wordt een bruikbare auto-edge binnen de
snapafstand gekozen. Het pand krijgt nu een reistijd van 1,05 minuut en valt
binnen de autonorm.

## Lopen

Voor lopen wordt het netwerk `voetganger_osm.json` gebruikt. Dit is een
gecombineerde voetgangerslaag met netwerkbroninformatie en OSM-aanvullingen voor
looproutes.

De berekening is direct:

```text
pand -> loopnetwerk -> voorziening
```

De loopsnelheid is 80 meter per minuut. Voorzieningen worden op het loopnetwerk
gesnapt en vormen de doelpunten voor Dijkstra. Elk pand krijgt de kortste
netwerktijd naar een voorziening plus de snapkosten van pand naar loopnetwerk.

## Fiets

Voor fiets wordt `fiets_osm.json` gebruikt. Dit netwerk bevat de toegestane
fietsrichtingen uit de verkeersnetwerkbron plus een OSM-bike aanvulling voor
fietsdoorsteken en fietspaden die in de netwerkbron kunnen ontbreken. De
berekening is direct:

```text
pand -> fietsnetwerk -> voorziening
```

De fietssnelheid is 250 meter per minuut. Voorzieningen worden op het fietsnetwerk
gesnapt. Per pand wordt de kortste route naar een voorziening berekend, rekening
houdend met toegestane rijrichtingen.

## Auto

Autobereikbaarheid bestaat uit rijden naar een parkeerlocatie en daarna lopen
naar de voorziening:

```text
pand -> autonetwerk -> parkeerlocatie -> loopnetwerk/luchtlijn -> voorziening
```

De auto rijdt over `personenauto.json`. De routekosten gebruiken waar mogelijk de
maximumsnelheid uit het netwerksegment. Als geen maximumsnelheid beschikbaar is,
wordt een standaardsnelheid gebruikt.

Parkeerlocaties worden eerst gekoppeld aan voorzieningen. Hiervoor worden zowel
`parkeren.json` uit het NWB als `parkeergarage.geojson` uit RDW gebruikt. De
parkeervakken langs de weg zijn lijnen; de parkeergarages zijn BAG-pandpolygonen.
Beide lagen worden voor de routeberekening omgezet naar puntrepresentaties.

1. Voorzieningen worden gesnapt op het loopnetwerk.
2. Parkeerpunten, parkeervlakken en parkeergarages worden gesnapt op het
   loopnetwerk.
3. De looptijd van parkeerlocatie naar voorziening wordt berekend.
4. Als het loopnetwerk voor dit korte natransport geen verbinding vindt, maar de
   parkeerlocatie hemelsbreed wel binnen de ingestelde loopgrens ligt, wordt de
   rechte afstand gedeeld door de loopsnelheid. Dit is een noodschatting voor
   ontbrekende kleine paden, ingangen of parkeerterreinverbindingen in het
   loopnetwerk.
5. Parkeerlocaties met meer dan 10 minuten lopen naar een voorziening vallen af.

Daarna worden de overblijvende parkeerlocaties als autodoelen gebruikt. De
autorit eindigt dus niet direct bij de voorziening, maar bij een parkeerlocatie
die binnen acceptabele loopafstand van een voorziening ligt.

De gekozen parkeerlocatie is niet noodzakelijk de hemelsbreed dichtstbijzijnde
parkeerplek bij de voorziening. Voor elk pand wordt de totale deur-tot-deur
reistijd geminimaliseerd:

```text
rijtijd pand -> parkeerlocatie
+ looptijd parkeerlocatie -> voorziening
```

Een iets verder gelegen parkeerlocatie kan dus gekozen worden wanneer die via
het autonetwerk sneller bereikbaar is. De voorbeeldroute gebruikt dezelfde
weging, inclusief de loopkosten vanaf parkeerlocatie naar voorziening.

## OV met lopen

OV met lopen bestaat uit:

```text
pand -> loopnetwerk -> opstaphalte
  -> wachten op eerstvolgende rit
  -> GTFS-rit of ritten
  -> eventuele overstap met minimale overstaptijd en wachttijd
  -> uitstaphalte -> loopnetwerk -> voorziening
```

Eerst wordt per OV-halte een tijdvensterprofiel bepaald. De OV-ritten komen uit
`line_total_travel_times.csv`, dus uit individuele GTFS-verbindingen met
werkelijke vertrek- en aankomsttijden. Haltes komen uit
`line_total_stop_points.geojson`.

De OV-run gebruikt de instellingen uit `5_bereikbaarheid/config.py`:
`ov_datum`, `ov_starttijd`, `ov_eindtijd`, `ov_stap_minuten` en
`min_overstap_min`. De datum valt standaard terug op `OV_DATUM` uit
`5_bereikbaarheid/helpers/instellingen.py`. Daardoor gebruikt de servicefilter
`calendar_dates.txt` en, als aanwezig, `calendar.txt` voor een dagspecifieke
dienstregeling.

Per vertrekmoment wordt de deur-tot-deur reistijd berekend:

```text
looptijd pand -> opstaphalte
+ wachttijd eerste rit
+ OV-rijtijd
+ overstaplooptijd en minimale overstaptijd
+ wachttijd bij overstap
+ looptijd uitstaphalte -> voorziening
```

Daarna wordt per halte een profiel gemaakt met onder andere minimum, mediaan en
p90. Voor de hoofdindicator `reistijd_<voorziening>_ov_lopen_min` wordt de mediaan
gebruikt, zodat een willekeurig vertrek binnen het tijdvenster wordt benaderd.
Daarna wordt deze OV-route vergeleken met de directe looproute naar een
voorziening. Als direct lopen sneller is dan OV en binnen de actieve loopnorm
valt, wordt de directe route gebruikt. Als direct lopen langer duurt, blijft OV
de voorkeursbron wanneer er een bruikbare OV-route is.
De panduitvoer bevat daarnaast:

```text
reistijd_<voorziening>_ov_lopen_bron
reistijd_<voorziening>_ov_lopen_min_min
reistijd_<voorziening>_ov_lopen_mediaan_min
reistijd_<voorziening>_ov_lopen_p90_min
```

## OV met fiets

OV met fiets gebruikt dezelfde tijdafhankelijke OV-kern als OV met lopen, maar
de toegang vanaf pand naar halte gaat via het fietsnetwerk:

```text
pand -> fietsnetwerk -> halte -> OV-netwerk -> halte -> loopnetwerk -> voorziening
```

Het natransport vanaf de uitstaphalte naar de voorziening blijft lopen. De
fietscomponent gebruikt dezelfde fietssnelheid en richtingstoegang als de
directe fietsberekening. De hoofdindicator
`reistijd_<voorziening>_ov_fiets_min` is ook hier de mediaan over de
vertrekmomenten in het OV-tijdvenster. Daarna wordt ook hier vergeleken met de
directe fietsroute naar de voorziening. Direct fietsen wordt alleen gebruikt als
de route sneller is dan OV en binnen de actieve fietsnorm valt; anders blijft
fiets-plus-OV-plus-lopen de voorkeursbron wanneer die beschikbaar is.

## Buurtsamenvatting

Na de pandberekening worden de resultaten per buurt samengevat. Per buurt worden
onder andere berekend:

```text
panden_aantal
panden_met_reistijd
panden_binnen_norm
percentage_met_reistijd
percentage_binnen_norm
reistijd_mediaan_min
reistijd_p90_min
```

De buurtpolygonen komen uit:

```text
0_layers/processed/1_buurten/buurten_basis.gpkg
```

Waterbuurten worden niet gepubliceerd in de voorzieningen-buurtkaartlagen. De
kaartlagen bevatten daardoor alleen Friese niet-waterbuurten.

## Gemeentesamenvatting

Per modaliteit wordt ook een CSV per gemeente geschreven:

```text
5_bereikbaarheid/processed/<voorziening>/<modaliteit>/gemeenten_<code>.csv
```

Deze tabel bevat onder andere:

```text
panden_aantal
panden_bereikbaar
panden_niet_bereikbaar
percentage_bereikbaar
percentage_niet_bereikbaar
panden_binnen_norm
panden_niet_binnen_norm
percentage_binnen_norm
percentage_niet_binnen_norm
reistijd_mediaan_min
reistijd_p90_min
```

## Publicatiekaartlagen

Per voorziening en modaliteit worden de pandlagen als GeoPackage gepubliceerd in:

```text
0_layers/processed/5_bereikbaarheid/<voorziening>/<modaliteit>/<voorziening>_<code>.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/<modaliteit>/<voorziening>_<code>_norm_status.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/<modaliteit>/<voorziening>_<code>_binnen_norm.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/<modaliteit>/<voorziening>_<code>_buiten_norm.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/<modaliteit>/<voorziening>_buurten_<code>_kleur.gpkg
```

Voor onderwijs wordt de subcategorie als bestandsnaam gebruikt:

```text
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_<code>_norm_status.gpkg
```

De laag `<voorziening>_<code>.gpkg` bevat de doorgerekende pandpunten. De lagen
`_norm_status`, `_binnen_norm` en `_buiten_norm` gebruiken BAG-pandpolygonen voor
kaartweergave. Publicatiekolommen met gekozen voorzieningen worden zonder
`gekozen_`-prefix geschreven, bijvoorbeeld `supermarkt_id` en `supermarkt_naam`.
Stijlvelden worden geschreven als `fill`, `stroke`, `fill-opacity` en
`stroke-width`.

Als alle vijf modaliteiten beschikbaar zijn, wordt ook multimodale output
vernieuwd:

```text
0_layers/processed/5_bereikbaarheid/<voorziening>/multimodaal/<voorziening>_mul_norm_status.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/multimodaal/<voorziening>_mul_binnen_norm.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/multimodaal/<voorziening>_mul_buiten_norm.gpkg
```

Deze multimodale laag wordt niet gemiddeld: een pand valt binnen de multimodale
norm wanneer minimaal één beschikbare modaliteit binnen de eigen norm valt.

## Stromenkaarten

Als `PAND_FLOWMAPS = True` staat in `5_bereikbaarheid/config.py`, wordt na elke
gekozen modaliteit een routes-flowmap gemaakt op basis van dezelfde pandkeuzes
die net in de bereikbaarheidsrun zijn berekend. De output staat in:

```text
0_layers/processed/5_bereikbaarheid/<voorziening>/pandstromen/pand_<voorziening>_flowmap_<code>.gpkg
```

De lijnbreedte geeft het aantal berekende routes over een netwerksegment weer.
Dit is geen gemeten verkeersintensiteit.

## Voorbeeldroutes

Als `VOORBEELDROUTES = True` staat in `config.py`, wordt bij elke modaliteit een
willekeurige voorbeeldroute opgeslagen in:

```text
0_layers/processed/voorbeelden/voorbeeldroute_<voorziening>_<code>.gpkg
```

Elk GeoPackage-bestand bevat:

* `route_segmenten`: de lijnsegmenten van de voorbeeldroute, met
  `segment_lengte_meter` per segment en `route_lengte_meter` voor de totale
  voorbeeldroute.
* `route_punten`: de gekozen punten bij de route.

Voor lopen en fietsen bevat de route de netwerksegmenten vanaf het gekozen pand
naar een voorziening. De puntenlaag bevat het pand en de voorziening. Voor auto
bevat de route de autoroute naar een parkeerdoel plus de looproute van
parkeerplek naar voorziening. De puntenlaag bevat dan het pand, de parkeerplek en
de voorziening. Voor OV bevat de route de accessroute naar de gekozen opstaphalte.
Als er routegeometrie beschikbaar is, worden daarna ook de OV-ritsegmenten, een
eventuele overstap en de egressroute naar de voorziening toegevoegd. De puntenlaag
bevat dan het pand, de opstaphalte, de uitstaphalte en de voorziening. De
OV-voorbeeldroute kiest bij voorkeur een pand waarvoor `bron = ov`, zodat het
voorbeeld laat zien wanneer OV echt wordt gebruikt. Alleen als er geen bruikbaar
OV-voorbeeld kan worden opgebouwd, valt de voorbeeldroute terug op directe
loop- of fietsaccess.

## Interpretatie van geen betrouwbare route

Een pand krijgt `geen_betrouwbare_route` wanneer geen volledige route kan worden
berekend. Mogelijke oorzaken zijn:

* het pand ligt verder dan de maximale snapafstand van het netwerk;
* het dichtstbijzijnde netwerksegment heeft een rijrichting die geen route naar
  een doel mogelijk maakt;
* het netwerkcomponent waarin het pand ligt is niet verbonden met een voorziening,
  parkeerdoel of OV-halte;
* bij auto is er geen bruikbare parkeerlocatie binnen de ingestelde loopgrens;
* bij OV is er geen combinatie van access, actieve dienstregeling, OV-rit,
  overstap en natransport beschikbaar binnen het gekozen tijdvenster.

Panden zonder route na de eerste snap worden opnieuw beoordeeld met
routebewuste snapping. Alleen als ook binnen de snapafstand geen bruikbare edge
wordt gevonden, blijft de status `geen_betrouwbare_route`.
