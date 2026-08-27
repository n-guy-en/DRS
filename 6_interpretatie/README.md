# Interpretatie

Deze map bevat de interpretatielaag bovenop de bereikbaarheidsberekeningen uit
`5_bereikbaarheid`. De bereikbaarheidsstap rekent per pand uit of een
voorziening binnen de norm ligt. Deze stap vertaalt dat naar isochronen en
knelpuntenkaarten voor rapportage en kaartgebruik.
De legenda's voor de kaartlagen staan in `../8_rapport/LEGENDA.md`.

Er is een centrale workflow voor supermarkten, recreatief groen,
sportvoorzieningen, apotheken, huisartsen, ziekenhuizen, onderwijs en
OV-haltes. Onderwijs wordt per onderwijsniveau verwerkt, aansluitend op de
niveaumappen uit `5_bereikbaarheid/processed/onderwijs`.

Multimodale interpretatielagen worden alleen vernieuwd wanneer alle modaliteiten in de
run aanwezig zijn. Een losse run met bijvoorbeeld alleen fiets overschrijft dus
geen bestaande multimodale output.

## Workflow

Voer eerst de benodigde bereikbaarheidsstap uit:

```bash
python3 5_bereikbaarheid/bop.py
```

De instellingen voor voorzieningen, jaar, pandselectie en modaliteiten staan in
`5_bereikbaarheid/config.py`. De OV-datum staat centraal in
`5_bereikbaarheid/helpers/instellingen.py` en geldt voor bereikbaarheid en interpretatie.

Maak daarna de interpretatie-output:

Gebruik voor normale runs de centrale configuratie:

```text
6_interpretatie/config.py
```

Kies daar `VOORZIENINGEN` en `INTERPRETATIE_MODI`. Start daarna de gekozen voorzieningen:

```bash
python3 6_interpretatie/interpretatie.py
```

`interpretatie.py` gebruikt de algemene helpermap `6_interpretatie/helpers`.
Per gekozen voorziening wordt dezelfde stapvolgorde uitgevoerd: tekorten,
modaliteiten onvoldoende en isochronen.

Voor onderwijs stel je in `6_interpretatie/config.py` de gewenste niveaus in:

```python
VOORZIENINGEN = ["onderwijs"]
ONDERWIJS_NIVEAUS = ["vmbo", "havo"]
```

Gebruik alle onderwijsniveaus met:

```python
ONDERWIJS_NIVEAUS = "all"
```

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

## Output

Analyse- en tabeloutput:

```text
6_interpretatie/processed/supermarkt/knelpunten/supermarkt_modaliteiten_onvoldoende.csv
6_interpretatie/processed/supermarkt/isochroon/isochroon_supermarkt.csv
6_interpretatie/processed/ziekenhuis/...
6_interpretatie/processed/onderwijs/<niveau>/...
6_interpretatie/processed/ov/...
```

Kaartlagen worden alleen centraal opgeslagen in `0_layers`:

```text
0_layers/processed/6_interpretatie/supermarkt/knelpunten/supermarkt_modaliteiten_onvoldoende.gpkg
0_layers/processed/6_interpretatie/supermarkt/isochroon/isochroon_supermarkt_multimodaal.geojson
0_layers/processed/6_interpretatie/ziekenhuis/...
0_layers/processed/6_interpretatie/onderwijs/<niveau>/...
0_layers/processed/6_interpretatie/ov/...
```

Deze gepubliceerde kaartlagen staan in `EPSG:4326`, zodat ze aansluiten op de
kaartlagen uit `5_bereikbaarheid` en webkaarttools. De berekeningen zelf worden
intern in RD (`EPSG:28992`) uitgevoerd.

`<voorziening>_modaliteiten_onvoldoende.gpkg` is de knelpuntenkaart. Bij
onderwijs gebruikt de bestandsnaam het onderwijsniveau, bijvoorbeeld
`vmbo_modaliteiten_onvoldoende.gpkg`. Dit is een compacte
kaartlaag met de belangrijkste bereikbaarheidspercentages, ernstklasse en het
aantal onvoldoende modaliteiten. De kleur volgt
`aantal_modaliteiten_onvoldoende`, met `fill`, `stroke`,
`fill-opacity` en `stroke-width` als stijlvelden. De kleur is
een gradiënt op basis van `aantal_modaliteiten_onvoldoende`: groen betekent dat
alle modaliteiten voldoen, geel betekent één onvoldoende modaliteit, en daarna
loopt de kleur via oranje naar rood wanneer meer modaliteiten onder de
signaleringsgrens zitten.
buurt-specifieke interpretatie komt uit de percentages `pct_lopen`,
`pct_fiets`, `pct_auto`, `pct_ov_lopen`, `pct_ov_fiets`, `beste_pct` en
`slechtste_pct`.
De uitgebreide tabelvariant staat in `<voorziening>_modaliteiten_onvoldoende.csv`. Een
aparte `buurten_tekortdiagnose.csv` wordt niet meer opgeslagen, omdat dezelfde
diagnosevelden al in deze tabel zitten.
CSV- en GPKG-output uit de hoofdworkflow wordt eerst naar een tijdelijk bestand
geschreven en daarna pas vervangen. Daardoor blijft een eerdere geldige output
staan als een write halverwege faalt.

Betekenis van `aantal_modaliteiten_onvoldoende`:

| Categorie | Betekenis voor de buurt |
| --- | --- |
| `0_modaliteiten_onvoldoende` | Alle modaliteiten voldoen. |
| `1_modaliteit_onvoldoende` | Eén modaliteit zit onder de signaleringsgrens. |
| `2_modaliteiten_onvoldoende` | Twee modaliteiten zitten onder de signaleringsgrens. |
| `3_modaliteiten_onvoldoende` | Drie modaliteiten zitten onder de signaleringsgrens. |
| `4_modaliteiten_onvoldoende` | Vier modaliteiten zitten onder de signaleringsgrens. |
| `5_modaliteiten_onvoldoende` | Geen modaliteit voldoet. |
| `datacontrole_uitvoeren` | Geen woningen. |

## Isochronen

De isochroonlaag wordt standaard na de knelpuntenkaart gemaakt. De laag vertaalt de
voorzieningbereikbaarheid naar netwerkisochroonbanden per modaliteit. De
tijdsnorm komt exact uit de voorziening- en modaliteitsnormen in
`5_bereikbaarheid/helpers/instellingen.py`.

Definitie voor kaartuitleg:

> Een isochroon toont het gebied rond netwerkdelen die binnen de gekozen
> reistijdnorm bereikbaar zijn vanaf of naar de actieve voorziening. De kaart is
> een visualisatie van bereikbare netwerkruimte. Voor exacte uitspraken over
> welke panden binnen of buiten de norm vallen, blijft de pandoutput uit
> `5_bereikbaarheid` leidend.

De isochroon is dus niet hetzelfde als een exacte pandselectie. Door het
bufferen en generaliseren van netwerksegmenten kan een pand visueel binnen het
vlak liggen terwijl de exacte pandberekening net buiten de norm valt, of
andersom bij randen van de polygonen. Gebruik de isochroon voor de herkenbare
bereikvlek en gebruik de pand- en buurtlagen voor aantallen, percentages en
knelpunten.

Voor lopen, fiets en auto worden bereikbare netwerksegmenten naar de actieve
voorzieningen gebruikt. Voor `ov_lopen` en `ov_fiets` wordt voor
voorzieningenbereikbaarheid het accessnetwerk naar haltes gecombineerd met het
tijdafhankelijke GTFS-profiel naar de voorziening. De OV-instellingen worden
overgenomen uit `RUN` in `5_bereikbaarheid/config.py`.

De losse modaliteitslagen beantwoorden de vraag: hoe ziet de ster eruit voor
lopen, fiets, auto, OV met lopen of OV met fiets afzonderlijk? Deze lagen zijn
het meest geschikt om knelpunten per modaliteit te bespreken.

Output per voorziening:

```text
0_layers/processed/6_interpretatie/<voorziening>/isochroon/isochroon_<voorziening>_<modus>.geojson
0_layers/processed/6_interpretatie/<voorziening>/isochroon/isochroon_<voorziening>_multimodaal.geojson
6_interpretatie/processed/<voorziening>/isochroon/isochroon_<voorziening>_<modus>.csv
6_interpretatie/processed/<voorziening>/isochroon/isochroon_<voorziening>_multimodaal.csv
```

Belangrijke velden voor kaartopmaak zijn `band_van_min`, `band_tot_min`,
`kleur_klasse`, `fill`, `stroke`, `fill-opacity` en `stroke-width`.
`isochrone_buffer_meter` is de bufferafstand waarmee bereikbare panden of
netwerksegmenten tot een vlak worden gemaakt. `generalisatie_meter` is de
afstand waarmee dat vlak cartografisch wordt afgerond en samengevoegd.

De multimodale isochroon is een unie van de geselecteerde modaliteiten per
tijdsband. Deze laag betekent: bereikbaar binnen de tijd via minstens een van de
meegenomen modaliteiten. Het is dus een best-beschikbare-modaliteit-kaart, geen
gemiddelde reistijd en geen uitspraak over doelgroepen zonder toegang tot een
bepaalde modaliteit.

Gebruik de multimodale laag voor de vraag: hoe groot is de maximale bereikvlek als
bewoners de snelste beschikbare modaliteit kunnen kiezen? Gebruik daarnaast
altijd de losse modaliteitslagen, omdat auto, fiets en OV niet voor iedere
bewoner even beschikbaar zijn.

## Routes

Route- en stromenkaarten worden gemaakt in `5_bereikbaarheid`. Deze
interpretatiestap gebruikt die routes niet opnieuw en schrijft zelf geen
route-output weg.

## Configuratie

De actieve helperimports staan centraal in `6_interpretatie/helpers`.
De voorzieningen worden gekozen in `6_interpretatie/config.py`;
`6_interpretatie/interpretatie.py` zet per voorziening de actieve
helperconfiguratie.
Configuratie, inlezen, tekortdiagnose, knelpunten, isochronen en knelpuntenkaarten
gebruiken dezelfde gedeelde helpercode. De normen worden overgenomen uit
`5_bereikbaarheid/helpers/instellingen.py`. De signaleringsgrens voor
onvoldoende bereikbaarheid is 80%; de grens voor een ernstig tekort is 60%.
