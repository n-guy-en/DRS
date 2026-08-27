# Bereikbaarheid

Deze map bevat bereikbaarheidsanalyses voor voorzieningen.
De legenda's voor de kaartlagen staan in `../8_rapport/LEGENDA.md`.

De analyses berekenen bereikbaarheid van BAG-pandcentroids naar voorzieningen
voor lopen, fiets, auto en OV. De huidige voorzieningen zijn supermarkt,
recreatief groen, sportvoorzieningen, apotheek, huisarts, ziekenhuis,
onderwijs en OV-haltes/stations.

# Structuur

```text
5_bereikbaarheid/
  README.md
  BEREKENINGEN.md
  config.py
  bop.py
  helpers/
  processed/
    supermarkt/
    recreatief_groen/
    sport/
    apotheek/
    huisarts/
    onderwijs/
    ziekenhuis/
    ov/
```

| Map of bestand | Wat staat erin? |
|---|---|
| `config.py` | Runconfiguratie: voorzieningen, jaar, pandselectie, modaliteiten en runtime-instellingen |
| `bop.py` | Centrale runner voor alle gekozen voorzieningen |
| `helpers/` | Universele helpers voor instellingen, inlezen, netwerk, auto, OV, output, pandstromen en workflow |
| `processed/<voorziening>/` | CSV-tabellen per modaliteit |
| `BEREKENINGEN.md` | Algemene toelichting op de reistijdberekening |

De gedeelde map heet gewoon `helpers`. De actieve voorzieningen worden gekozen
in `config.py`; `bop.py` start daarna `helpers/workflow.py` per gekozen
voorziening.

De universele helpers zijn bewust praktisch gehouden:

| Helper | Verantwoordelijkheid |
|---|---|
| `instellingen.py` | Voorzieninginstellingen, vaste paden, CRS, modaliteiten en normen |
| `invoer.py` | BAG-panden, voorzieningen en pandpolygonen inlezen |
| `geometrie.py` | Kleine geometriehulpen |
| `netwerk.py` | Netwerk opbouwen, punten snappen en routekosten berekenen |
| `auto.py` | Autobereikbaarheid via parkeren |
| `ov.py` | OV-bereikbaarheid met voor- en natransport |
| `output.py` | Buurtsamenvattingen en kaartlagen wegschrijven |
| `pandstromen.py` | Optionele stromenkaarten op basis van de gekozen voorziening per pand |
| `routes.py` | Routegeometrie voor voorbeeldroutes en stromenkaarten |
| `workflow.py` | Gedeelde workflow voor alle voorzieningen |

---

# Workflow

Gebruik voor normale runs de centrale configuratie:

```text
5_bereikbaarheid/config.py
```

Kies daar `VOORZIENINGEN`, `PAND_SELECTIE` en `MODI`. Start daarna de
gekozen voorzieningen:

```bash
python3 5_bereikbaarheid/bop.py
```

Het analysejaar staat centraal in:

```text
2_bag/config.py
```

`5_bereikbaarheid` leest `ANALYSEJAAR` automatisch uit die BAG-config. De run
controleert dit jaar tegen de kolom `jaar` in
`0_layers/processed/2_bag/bag_panden.gpkg`, zodat de analyse niet ongemerkt met
pandpunten uit een ander jaar draait. `PAND_SELECTIE` mag alleen `woonpanden`
of `alle_panden` zijn.

Voor een enkele modaliteit gebruik je bijvoorbeeld `MODI = "lopen"`.
De multimodale bereikbaarheidsoutput wordt alleen vernieuwd wanneer alle
modaliteiten in dezelfde run aanwezig zijn. Een losse fietsrun overschrijft dus
geen bestaande multimodale output.

Stromenkaarten zijn zwaar. Zet ze in `5_bereikbaarheid/config.py` alleen aan
wanneer je deze kaartlagen nodig hebt:

```python
PAND_FLOWMAPS = True
```

De stromenkaarten gebruiken automatisch dezelfde modaliteiten als `RUN.modi`.
Als `RUN.modi = "fiets"` is, wordt dus alleen de fiets-stromenkaart gemaakt. De
stromenkaart wordt direct na de output van die modaliteit gemaakt en gebruikt
de pandkeuzes uit dezelfde bereikbaarheidsrun. Er wordt geen nieuwe keuze naar alle
voorzieningen uitgerekend.

Output:

```text
5_bereikbaarheid/processed/<voorziening>/pandstromen/pand_<voorziening>_flowmap_<modus>.gpkg
0_layers/processed/5_bereikbaarheid/<voorziening>/pandstromen/pand_<voorziening>_flowmap_<modus>.gpkg
```

Onderwijs kan per niveau los worden gedraaid door in `config.py` onderwijs op
te nemen in `VOORZIENINGEN` en `ONDERWIJS_NIVEAUS` te vullen:

```python
VOORZIENINGEN = ["onderwijs"]
ONDERWIJS_NIVEAUS = "vmbo,havo"
```

Gelieve `ONDERWIJS_NIVEAUS = "all"` niet te gebruiken voor normale runs.
Hiermee worden alle onderwijsniveaus doorgerekend, waardoor de run erg lang
duurt.

Beschikbare onderwijsniveaus:

```text
basisonderwijs
vo
vmbo
mavo
havo
vwo
pro
brugjaar
mbo
hbo
wo
```

Voor OV gebruikt het script standaard een tijdvenster van 00:00:00 tot
23:59:59, met vertrekmomenten per 15 minuten en een minimale overstaptijd van
3 minuten. `OV_DATUM` moet voor een accurate analyse een concrete datum in
`YYYYMMDD` zijn. Deze datum staat centraal in
`5_bereikbaarheid/helpers/instellingen.py` en geldt voor alle voorzieningen. De
huidige standaard is `OV_DATUM = "20260616"`, een dinsdag.

OV-parameters:

```text
5_bereikbaarheid/helpers/instellingen.py:
OV_DATUM = "20260616"

5_bereikbaarheid/config.py:
RUN = RuntimeConfig(...)
```

Beschikbare modi:

```text
lopen
fiets
auto
ov_lopen
ov_fiets
all
```

Minimumnormen per voorziening staan centraal in `helpers/instellingen.py`.

| Voorziening | Auto | Fiets | OV met fiets | OV met lopen | Lopen |
|---|---:|---:|---:|---:|---:|
| OV-halte | 15 min | 15 min | 15 min | 15 min | 15 min |
| Supermarkt | 10 min | 10 min | 15 min | 15 min | 15 min |
| Recreatief groen | 15 min | 15 min | 15 min | 15 min | 15 min |
| Sportvoorziening | 30 min | 30 min | 30 min | 30 min | 30 min |
| Apotheek | 10 min | 10 min | 20 min | 20 min | 15 min |
| Huisarts | 10 min | 10 min | 20 min | 20 min | 15 min |
| Ziekenhuis | 20 min | 25 min | 30 min | 30 min | 20 min |
| Basisschool | 10 min | 10 min | 10 min | 10 min | 10 min |
| Middelbare school | 15 min | 25 min | 30 min | 30 min | 25 min |
| MBO | 25 min | 25 min | 40 min | 40 min | 25 min |
| HBO | 35 min | 25 min | 45 min | 45 min | 15 min |
| WO | 35 min | 25 min | 45 min | 45 min | 15 min |

Bij auto bestaat de reistijd uit rijden naar een geschikte parkeerlocatie en
daarna lopen naar de voorziening. Parkeerdoelen komen uit `parkeren.json`
voor parkeren langs de weg en uit `parkeergarage.geojson` voor RDW-
parkeergarages op BAG-pandniveau. Normaal wordt dat laatste stuk via het
loopnetwerk berekend. Alleen als het loopnetwerk daar geen verbinding vindt,
maar de parkeerplek hemelsbreed wel binnen de toegestane loopafstand ligt,
gebruikt het script de rechte afstand als noodschatting voor dat korte
natransport. Dit voorkomt dat bruikbare parkeerplekken afvallen door ontbrekende
kleine paden of parkeerterreinverbindingen in het loopnetwerk.

---

# Input

Het script verwacht dat deze stappen al klaar zijn:

```text
0_layers/processed/2_bag/bag_panden.gpkg
0_layers/processed/3_voorzieningen/supermarkt/supermarkten_groot.gpkg
0_layers/processed/3_voorzieningen/recreatief_groen/recreatief_groen_groot.gpkg
0_layers/processed/3_voorzieningen/sport/sport_groot.gpkg
0_layers/processed/3_voorzieningen/apotheek/apotheek_groot.gpkg
0_layers/processed/3_voorzieningen/huisarts/huisarts_groot.gpkg
0_layers/processed/3_voorzieningen/onderwijs/<niveau>/onderwijs_<niveau>.gpkg
0_layers/processed/3_voorzieningen/ziekenhuis/ziekenhuizen.gpkg
0_layers/processed/3_voorzieningen/ov/ov_haltes.gpkg
0_layers/processed/4_netwerk/verkeerstypen/voetganger_osm.json
0_layers/processed/4_netwerk/verkeerstypen/fiets_osm.json
0_layers/processed/4_netwerk/verkeerstypen/personenauto.json
0_layers/processed/4_netwerk/verkeerstypen/parkeren.json
0_layers/processed/4_netwerk/verkeerstypen/parkeergarage.geojson
0_layers/processed/4_netwerk/ov/line_total_stop_points.geojson
4_netwerk/processed/GTFS/gtfs_ov_netwerk/validatie/tussenbestanden/line_total_travel_times.csv
4_netwerk/raw/GTFS/gtfs-openov-nl/calendar_dates.txt
```

Als de GTFS-feed ook `calendar.txt` bevat, gebruikt het script die naast
`calendar_dates.txt`. In de huidige 9292/openOV-feed zitten de actieve rijdagen
vooral in `calendar_dates.txt`.

Voor pandpolygonen gebruikt het script daarnaast:

```text
2_bag/bag_frl_xml/per_jaar/pnd_fryslan_<jaar>.geojson
```

De pandpunten en pandpolygonen moeten dus allebei bij hetzelfde `ANALYSEJAAR`
horen.

---

# Output

Kaartlagen worden centraal opgeslagen in `0_layers`, zodat andere analyses ze
makkelijk kunnen gebruiken:

```text
0_layers/processed/5_bereikbaarheid/supermarkt/<modaliteit>/<voorziening>_<code>.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/<modaliteit>/<voorziening>_<code>_norm_status.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/<modaliteit>/<voorziening>_<code>_binnen_norm.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/<modaliteit>/<voorziening>_<code>_buiten_norm.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/<modaliteit>/<voorziening>_buurten_<code>_kleur.gpkg
```

Voor de andere voorzieningen wordt dezelfde structuur gebruikt, met de
voorzieningnaam in plaats van `supermarkt`.

Na elke run wordt ook een multimodale output gemaakt voor de modaliteiten die in
`MODI` zijn meegedraaid:

```text
0_layers/processed/5_bereikbaarheid/supermarkt/multimodaal/<voorziening>_mul.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/multimodaal/<voorziening>_mul_norm_status.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/multimodaal/<voorziening>_mul_binnen_norm.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/multimodaal/<voorziening>_mul_buiten_norm.gpkg
0_layers/processed/5_bereikbaarheid/supermarkt/multimodaal/<voorziening>_buurten_mul_kleur.gpkg
```

Voor onderwijs wordt daar nog een niveaulaag tussen gezet:

```text
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_<code>.gpkg
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_<code>_norm_status.gpkg
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_<code>_binnen_norm.gpkg
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_<code>_buiten_norm.gpkg
0_layers/processed/5_bereikbaarheid/onderwijs/<niveau>/<modaliteit>/<niveau>_buurten_<code>_kleur.gpkg
```

Bij onderwijs gebruikt de bestandsnaam dus de subcategorie, bijvoorbeeld
`vmbo_fie_norm_status.gpkg`, niet `onderwijs_fie_norm_status.gpkg`.

Beschikbare onderwijsniveaus:

```text
basisonderwijs
vo
vmbo
mavo
havo
vwo
pro
brugjaar
mbo
hbo
wo
```

Er wordt geen aparte GeoJSON-kleurvariant gemaakt. Wel wordt naast de gewone
buurtlaag een GeoPackage-kleurlaag geschreven met `fill`, `stroke` en
klasse-attributen voor directe symbolisatie in GIS of een kaartviewer.

`<voorziening>_<code>.gpkg` bevat de doorgerekende pandpunten. De polygonlagen
`<voorziening>_<code>_norm_status.gpkg`,
`<voorziening>_<code>_binnen_norm.gpkg` en
`<voorziening>_<code>_buiten_norm.gpkg` worden uit exact dezelfde pandselectie
opgebouwd. Het verschil is alleen de geometrie: de polygonlagen gebruiken de
BAG-pandpolygonen, zodat je de panden op de kaart als gebouwvlakken kunt tonen.

Gebruik `<voorziening>_<code>_norm_status.gpkg` wanneer je in één laag panden
binnen en buiten de gewenste reistijd wilt tonen. Belangrijke stijlvelden zijn
`fill`, `stroke`, `fill-opacity` en `stroke-width`. Groen betekent binnen de
gewenste reistijd, rood betekent buiten de gewenste reistijd en grijs betekent
geen betrouwbare route. De splitlagen `<voorziening>_<code>_binnen_norm.gpkg`
en `<voorziening>_<code>_buiten_norm.gpkg` bevatten dezelfde panden, maar dan
alvast gescheiden in twee bestanden.

De multimodale laag gebruikt dezelfde kaartlogica, maar combineert de
meegedraaide modaliteiten. Een pand is in `<voorziening>_mul_norm_status.gpkg` groen
wanneer minstens één van de geselecteerde modaliteiten binnen de eigen norm valt.
Er wordt dus niet gemiddeld over modaliteiten. Het veld
`gekozen_multimodale_modus` laat zien welke modaliteit voor dat pand bepalend
is: eerst de snelste modaliteit die binnen de norm valt, en als geen modaliteit
binnen de norm valt de snelste modaliteit waarvoor wel een route is gevonden.
Het veld `aantal_modaliteiten_binnen_norm` laat zien hoeveel modaliteiten voor
dat pand voldoen.

Als `MODI = "all"` staat, telt auto mee in de multimodale kaart. Dat is geschikt
voor de vraag welke plek bereikbaar is als bewoners de snelste beschikbare
route kunnen kiezen. Voor een analyse zonder auto draai je alleen de relevante
modaliteiten mee, bijvoorbeeld `MODI = "lopen,fiets,ov_lopen,ov_fiets"`. De
multimodale output wordt dan alleen uit die modaliteiten opgebouwd.

CSV-tabellen blijven bij de bereikbaarheidsstap:

```text
5_bereikbaarheid/processed/supermarkt/<modaliteit>/buurten_<code>.csv
5_bereikbaarheid/processed/supermarkt/<modaliteit>/gemeenten_<code>.csv
5_bereikbaarheid/processed/supermarkt/multimodaal/buurten_mul.csv
5_bereikbaarheid/processed/supermarkt/multimodaal/gemeenten_mul.csv
```

Voor de andere voorzieningen wordt dezelfde processed-structuur gebruikt. Bij
onderwijs staan de CSV-tabellen ook per niveau:

```text
5_bereikbaarheid/processed/onderwijs/<niveau>/<modaliteit>/buurten_<code>.csv
5_bereikbaarheid/processed/onderwijs/<niveau>/<modaliteit>/gemeenten_<code>.csv
```

`gemeenten_<code>.csv` bevat per gemeente onder andere het aantal panden dat
wel of niet bereikbaar is, het aantal panden binnen of buiten de norm en de
bijbehorende percentages.

Als `VOORBEELDROUTES = True` staat in `config.py`, wordt per modaliteit ook een
willekeurige voorbeeldroute weggeschreven:

```text
0_layers/processed/voorbeelden/voorbeeldroute_<voorziening>_<code>.gpkg
```

Elk voorbeeldbestand bevat twee lagen:

* `route_segmenten`: de lijnsegmenten van de voorbeeldroute, met
  `segment_lengte_meter` per segment en `route_lengte_meter` voor de totale
  voorbeeldroute.
* `route_punten`: de gekozen punten bij de route, zoals `pand`,
  `voorziening`, `parkeerplek` of `opstaphalte`.

Voor lopen en fietsen is dit de netwerkroute vanaf het gekozen pand naar een
voorziening. Voor auto is dit de autoroute vanaf het pand naar een parkeerdoel,
plus de looproute van parkeerplek naar voorziening. De puntenlaag bevat dan het
pand, de parkeerplek en de voorziening. Voor OV is dit de accessroute naar de
opstaphalte wanneer een echte OV-route is gekozen. De OV-voorbeeldroute kiest
bij voorkeur een pand met `bron = ov`, zodat het voorbeeld een situatie toont
waarin OV echt wordt gebruikt. Alleen als zo'n voorbeeld niet kan worden
opgebouwd, valt de voorbeeldroute terug op directe loop- of fietsaccess.

Voor OV bevat `reistijd_<voorziening>_<modus>_min` de mediaan van de
deur-tot-deur reistijden over de gesamplede vertrekmomenten in het tijdvenster.
Als een voorziening direct lopend of fietsend sneller bereikbaar is dan via OV en
binnen de gewone norm valt, wordt die directe route gebruikt zodat panden naast
een voorziening niet onbereikbaar worden door een verplichte OV-rit. De directe
norm komt uit dezelfde voorziening- of onderwijsniveauconfiguratie als de gewone
fiets- of loopnorm. De bron staat in
`reistijd_<voorziening>_<modus>_bron` met waarden zoals `ov` of `direct_access`.
Daarnaast worden op pandniveau ook OV-profielvelden weggeschreven, zoals
`reistijd_<voorziening>_ov_lopen_min_min`,
`reistijd_<voorziening>_ov_lopen_mediaan_min` en
`reistijd_<voorziening>_ov_lopen_p90_min`.

Voor directe routeberekeningen bevat de pandoutput ook de gekozen voorziening uit
de routering, met onder andere `<voorziening>_id`, `<voorziening>_naam`,
`<voorziening>_plaats`, `<voorziening>_lon` en `<voorziening>_lat`.
