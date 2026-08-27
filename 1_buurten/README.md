# Buurten

Deze map bevat scripts voor het verwerken van buurtdata.

De buurtlaag vormt de administratieve basis voor analyses binnen dit project. 
Deze laag dient als gemeenschappelijke referentie voor het koppelen en aggregeren van gegevens op buurtniveau, waaronder:

* BAG-panden per buurt
* voorzieningen per buurt
* bereikbaarheidsanalyse
* netwerkanalyses

## Scripts

| Script         | Functie                                    |
| -------------- | ------------------------------------------ |
| `buurtlaag.py` | Maakt de basiskaartlaag met buurtpolygonen |

## Workflow

### 1. Buurtlaag maken

Run:

```bash
python3 1_buurten/buurtlaag.py
```

### Input

De actieve buurtkaart staat in:

```text
1_buurten/raw/Buurten_<jaar>.gpkg
```

Voorbeeld:

```text
1_buurten/raw/Buurten_2026.gpkg
```

Standaard gebruikt het script automatisch de nieuwste beschikbare jaargang.

Wil je een specifieke jaargang gebruiken, pas bovenin `buurtlaag.py` de
configuratie aan. Het script zoekt dan naar `Buurten_<jaar>.gpkg` in
`1_buurten/raw/`:

```python
JAAR = 2026
```

Oudere jaargangen kunnen worden opgeslagen in:

```text
1_buurten/raw/archief/
```

### Output

```text
0_layers/processed/1_buurten/buurten_basis.gpkg
```

## Inhoud van de output

De basislaag bevat buurtpolygonen en aanvullende kenmerken die door andere analyses worden gebruikt.

Belangrijk:

* de laag bevat een kolom `water`;
* hierdoor kunnen watervlakken binnen buurten eenvoudig worden herkend en uit de analyse worden gefilterd.

Het script controleert of deze verplichte kolommen aanwezig zijn:

```text
buurtcode
buurtnaam
gemeentecode
gemeentenaam
water
jaar
geometry
```

Deze kolommen worden meegenomen als ze in de CBS-bron aanwezig zijn, maar zijn
niet verplicht:

```text
aantal_inwoners
aantal_huishoudens
bevolkingsdichtheid_inwoners_per_km2
oppervlakte_land_in_ha
oppervlakte_water_in_ha
omgevingsadressendichtheid
```

Als optionele kolommen ontbreken, meldt het script dat tijdens het draaien. De
laag blijft dan bruikbaar als administratieve basislaag.

## Gebruik in vervolgprocessen

De output wordt gebruikt in:

* `2_bag/` voor het koppelen van BAG-panden aan buurten;
* `4_netwerk/` voor netwerkverwerking waarbij buurt- en waterpolygonen nodig zijn;
* `5_bereikbaarheid/` voor bereikbaarheidskaarten en aggregaties per buurt;
* `6_interpretatie/` voor isochronen en knelpuntenkaarten.

## Structuur

```text
1_buurten/
├── buurtlaag.py
└── raw/
    ├── Buurten_2026.gpkg
    └── archief/
```

## Bronnen

Buurtkaarten van het CBS:

* [CBS Wijk- en Buurtkaart 2026](https://www.cbs.nl/nl-nl/dossier/nederland-regionaal/geografische-data/wijk-en-buurtkaart-2026)
