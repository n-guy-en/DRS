# Legenda's

Dit bestand beschrijft de actuele legenda's voor de kaartlagen uit
`5_bereikbaarheid` en `6_interpretatie`. De losse legenda-afbeeldingen staan in:

```text
legenda/
```

Beschikbare SVG's:

| Bestand | Gebruik |
| --- | --- |
| `5_bereikbaarheid/buurtkaart.svg` | Buurtkaarten uit `5_bereikbaarheid` |
| `5_bereikbaarheid/pandstatus.svg` | Woning-/pandkaarten met normstatus |
| `5_bereikbaarheid/stromenkaart.svg` | Stromenkaarten |
| `6_interpretatie/knelpunten.svg` | Knelpuntenkaart met aantal onvoldoende modaliteiten |
| `6_interpretatie/isochronen/<voorziening>/isochronen_<modus>.svg` | Isochronen |

## Modaliteiten

| Code | Label | Betekenis |
| --- | --- | --- |
| `lopen` / `lop` | Lopen | Route over het voetgangersnetwerk. |
| `fiets` / `fie` | Fiets | Route over het fietsnetwerk. |
| `auto` / `aut` | Auto | Autoroute naar een parkeerplek plus lopen naar de voorziening. |
| `ov_lopen` / `ovl` | OV + lopen | Lopen naar de opstaphalte, OV-rit en lopen vanaf de uitstaphalte. |
| `ov_fiets` / `ovf` | OV + fiets | Fietsen naar de opstaphalte, OV-rit en lopen vanaf de uitstaphalte. |

## Buurtkaarten

De buurtkaarten tonen per buurt het aandeel panden binnen de
bereikbaarheidsnorm.

| Klasse | Kleur |
| --- | --- |
| `0-20%` | `#d73027` |
| `20-40%` | `#fc8d59` |
| `40-60%` | `#fee08b` |
| `60-80%` | `#d9ef8b` |
| `80-100%` | `#1a9850` |
| `Geen woningen` | `#bdbdbd` |

## Pandstatus

De pandkaarten tonen per pand of de voorziening binnen de norm bereikbaar is.

| Status | Kleur |
| --- | --- |
| `binnen_norm` | `#2ca25f` |
| `buiten_norm` | `#de2d26` |
| `geen_betrouwbare_route` | `#9e9e9e` |

## Isochronen

De isochronen tonen bereikbare netwerkruimte in opeenvolgende reistijdbanden.
De exacte minutenbanden hangen af van de norm voor de
voorziening en modaliteit. Daarom staan deze legenda's per voorziening in
aparte mappen:

```text
legenda/6_interpretatie/isochronen/<voorziening>/
```

| Band | Fill | Stroke | Opacity |
| --- | --- | --- | ---: |
| Kortste reistijdband | `#2b8cbe` | `#045a8d` | 0.75 |
| Middelste reistijdband | `#7bccc4` | `#2b8cbe` | 0.60 |
| Buitenste reistijdband | `#edf8b1` | `#7bccc4` | 0.50 |

## Knelpuntenkaart

De knelpuntenkaart telt hoeveel modaliteiten per buurt onder de
signaleringsgrens scoren.

| Categorie | Kleur |
| --- | --- |
| `0_modaliteiten_onvoldoende` | `#2ca25f` |
| `1_modaliteit_onvoldoende` | `#ffd84d` |
| `2_modaliteiten_onvoldoende` | `#fdae61` |
| `3_modaliteiten_onvoldoende` | `#f46d43` |
| `4_modaliteiten_onvoldoende` | `#d73027` |
| `5_modaliteiten_onvoldoende` | `#7f0000` |
| `datacontrole_uitvoeren` | `#79706e` - Geen woningen |

## Stromenkaarten

Stromenkaarten tellen per netwerksegment hoeveel berekende routes over dat
segment lopen. Dit is geen gemeten verkeersintensiteit.

| Legenda-label | Kleur | Lijndikte |
| --- | --- | ---: |
| `1 route` | `#9e9e9e` | 0.35 |
| `2-40 routes` | `#00c853` | 1.1 |
| `41-100 routes` | `#8eea32` | 2.2 |
| `101-250 routes` | `#ffd400` | 3.6 |
| `251-500 routes` | `#ff7a1a` | 5.0 |
| `>500 routes` | `#ff1a1a` | 6.5 |
