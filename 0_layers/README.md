# Layers

Deze map is de centrale publicatielaag voor GIS-bestanden die door meerdere
onderdelen van het project worden gebruikt.

`0_layers` bevat geen scripts. Scripts blijven staan in de inhoudelijke
onderwerpmappen, zoals `1_buurten`, `2_bag`, `3_voorzieningen`,
`4_netwerk`, `5_bereikbaarheid`, `6_interpretatie`,
`7_analyses` en `8_rapport`.

## 1. Doel

`0_layers/processed/` is bedoeld als centrale opslaglocatie voor gedeelde kaartlagen. 
Hier worden de uiteindelijke GIS-lagen opgeslagen, zodat ze door andere projectstappen opnieuw gebruikt kunnen worden.

Voorbeelden:

```text
0_layers/processed/1_buurten/buurten_basis.gpkg
0_layers/processed/2_bag/bag_panden.gpkg
0_layers/processed/3_voorzieningen/supermarkt/supermarkten_groot.gpkg
0_layers/processed/3_voorzieningen/onderwijs/basisonderwijs/onderwijs_basisonderwijs.gpkg
0_layers/processed/3_voorzieningen/ziekenhuis/ziekenhuizen.gpkg
0_layers/processed/4_netwerk/ov/line_total_travel_times.geojson
0_layers/processed/5_bereikbaarheid/supermarkt/lopen/supermarkt_buurten_lop_kleur.gpkg
0_layers/processed/5_bereikbaarheid/onderwijs/vo/fiets/vo_buurten_fie_kleur.gpkg
0_layers/processed/6_interpretatie/supermarkt/knelpunten/supermarkt_modaliteiten_onvoldoende.gpkg
0_layers/processed/6_interpretatie/supermarkt/isochroon/isochroon_supermarkt_multimodaal.geojson
```

## 2. Wat hoort hier?

### Wel

* bewerkte GeoPackages (`.gpkg`)
* bewerkte GeoJSON-bestanden (`.geojson` of `.json`)

### Niet

* Python-scripts
* ruwe bronbestanden
* CSV-bestanden
* rapporttabellen en legenda-output uit `8_rapport/processed/`

## 3. Waar staan de scripts?

Scripts horen altijd in de onderwerpmap waar ze functioneel bij horen:

* `1_buurten/`
* `2_bag/`
* `3_voorzieningen/`
* `4_netwerk/`
* `5_bereikbaarheid/`
* `6_interpretatie/`
* `7_analyses/`
* `8_rapport/`

## 4. Structuur

```text
0_layers/
└── processed/
    ├── 1_buurten/
    │   └── buurten_basis.gpkg
    ├── 2_bag/
    │   └── bag_panden.gpkg
    ├── 3_voorzieningen/
    │   ├── supermarkt/
    │   ├── onderwijs/
    │   ├── ziekenhuis/
    │   └── ov/
    ├── 4_netwerk/
    │   ├── ov/
    │   └── verkeerstypen/
    ├── 5_bereikbaarheid/
    │   ├── supermarkt/
    │   ├── onderwijs/
    │   ├── ziekenhuis/
    │   └── ov/
    ├── 6_interpretatie/
    │   ├── supermarkt/
    │   ├── onderwijs/
    │   ├── ziekenhuis/
    │   └── ov/
    └── voorbeelden/
```

Bestanden in `processed/` kunnen afkomstig zijn uit meerdere onderwerpmappen.
De map volgt zoveel mogelijk dezelfde stapnummers als de rest van het project.
Bij onderwijs staat meestal nog een extra onderwijsniveaulaag tussen de
voorziening en de modaliteit, bijvoorbeeld `onderwijs/vmbo/fiets/`.

## 5. Workflow

Gebruik `0_layers` niet direct. Draai eerst een inhoudelijke projectstap:

```bash
python3 1_buurten/buurtlaag.py
python3 2_bag/bag.py
python3 2_bag/pand_centroids.py
python3 2_bag/pand_gebruik.py
python3 3_voorzieningen/supermarkt/supermarkt.py
python3 3_voorzieningen/supermarkt/filter.py
python3 3_voorzieningen/recreatief_groen/recreatief_groen.py
python3 3_voorzieningen/recreatief_groen/filter.py
python3 3_voorzieningen/sport/sport.py
python3 3_voorzieningen/sport/filter.py
python3 3_voorzieningen/apotheek/apotheek.py
python3 3_voorzieningen/apotheek/filter.py
python3 3_voorzieningen/huisarts/huisarts.py
python3 3_voorzieningen/huisarts/filter.py
python3 3_voorzieningen/onderwijs/onderwijs.py
python3 3_voorzieningen/ziekenhuis/ziekenhuis.py
python3 3_voorzieningen/ov/fetch.py
python3 4_netwerk/osm_netwerk.py
python3 4_netwerk/NWB_netwerk.py
python3 4_netwerk/gtfs_ov_netwerk.py
python3 5_bereikbaarheid/bop.py
python3 6_interpretatie/interpretatie.py
```

Die scripts schrijven zelf hun kaartlagen naar `0_layers/processed/`.
Instellingen zoals voorzieningen, modaliteiten en runtimekeuzes staan in
`5_bereikbaarheid/config.py` en `6_interpretatie/config.py`. Het analysejaar komt uit
`2_bag/config.py`. De OV-datum voor bereikbaarheidsanalyses staat centraal in
`5_bereikbaarheid/helpers/instellingen.py`.

### Overzicht van kaartlagen

| Laaggroep | Script | Belangrijkste vereiste vooraf | Voorbeeldoutput |
|---|---|---|---|
| `1_buurten` | `1_buurten/buurtlaag.py` | CBS-buurtlaag in `1_buurten/raw/` | `0_layers/processed/1_buurten/buurten_basis.gpkg` |
| `2_bag` | `2_bag/pand_centroids.py`, daarna `2_bag/pand_gebruik.py` | BAG-extract verwerkt met `2_bag/bag.py` en buurtlaag uit stap 1 | `0_layers/processed/2_bag/bag_panden.gpkg` |
| `3_voorzieningen/supermarkt` | `3_voorzieningen/supermarkt/supermarkt.py`, daarna `3_voorzieningen/supermarkt/filter.py` | OSM-supermarkten en BAG-panden | `0_layers/processed/3_voorzieningen/supermarkt/supermarkten_groot.gpkg` |
| `3_voorzieningen/recreatief_groen` | `3_voorzieningen/recreatief_groen/recreatief_groen.py`, daarna `3_voorzieningen/recreatief_groen/filter.py` | OSM-groen en BAG-panden | `0_layers/processed/3_voorzieningen/recreatief_groen/recreatief_groen_groot.gpkg` |
| `3_voorzieningen/sport` | `3_voorzieningen/sport/sport.py`, daarna `3_voorzieningen/sport/filter.py` | OSM-sportlocaties en BAG-panden | `0_layers/processed/3_voorzieningen/sport/sport_groot.gpkg` |
| `3_voorzieningen/apotheek` | `3_voorzieningen/apotheek/apotheek.py`, daarna `3_voorzieningen/apotheek/filter.py` | OSM-apotheken en BAG-panden | `0_layers/processed/3_voorzieningen/apotheek/apotheek_groot.gpkg` |
| `3_voorzieningen/huisarts` | `3_voorzieningen/huisarts/huisarts.py`, daarna `3_voorzieningen/huisarts/filter.py` | OSM-huisartsen en BAG-panden | `0_layers/processed/3_voorzieningen/huisarts/huisarts_groot.gpkg` |
| `3_voorzieningen/onderwijs` | `3_voorzieningen/onderwijs/onderwijs.py` | Onderwijsadressen en BAG-panden | `0_layers/processed/3_voorzieningen/onderwijs/vmbo/onderwijs_vmbo.gpkg` |
| `3_voorzieningen/ziekenhuis` | `3_voorzieningen/ziekenhuis/ziekenhuis.py` | OSM-ziekenhuizen en BAG-panden | `0_layers/processed/3_voorzieningen/ziekenhuis/ziekenhuizen.gpkg` |
| `3_voorzieningen/ov` | `3_voorzieningen/ov/fetch.py` | OV-netwerk uit `4_netwerk` | `0_layers/processed/3_voorzieningen/ov/ov_haltes.gpkg` |
| `4_netwerk/ov` | `4_netwerk/gtfs_ov_netwerk.py` | GTFS/NDOV-bronnen | `0_layers/processed/4_netwerk/ov/line_total_travel_times.geojson` |
| `4_netwerk/verkeerstypen` | `4_netwerk/osm_netwerk.py`, `4_netwerk/NWB_netwerk.py`, `4_netwerk/parkeergarage.py` | OSM-, NWB- en RDW-bronnen | `0_layers/processed/4_netwerk/verkeerstypen/personenauto.json` |
| `5_bereikbaarheid` | `5_bereikbaarheid/bop.py` | BAG-panden, voorzieningen en netwerken | `0_layers/processed/5_bereikbaarheid/supermarkt/lopen/supermarkt_buurten_lop_kleur.gpkg` |
| `6_interpretatie` | `6_interpretatie/interpretatie.py` | Bereikbaarheidsoutput uit stap 5 | `0_layers/processed/6_interpretatie/supermarkt/knelpunten/supermarkt_modaliteiten_onvoldoende.gpkg`; `0_layers/processed/6_interpretatie/supermarkt/isochroon/isochroon_supermarkt_multimodaal.geojson` |
| `voorbeelden` | `5_bereikbaarheid/bop.py` | Bereikbaarheidsrun met voorbeeldroute-output | `0_layers/processed/voorbeelden/voorbeeldroute_supermarkt_lop.gpkg` |

## 6. Gebruik in vervolgstappen

Andere scripts lezen kaartlagen uit `0_layers/processed/` weer in.
Daardoor is de workflow reproduceerbaar: elke stap slaat zijn uiteindelijke
gedeelde kaartlagen centraal op, terwijl ruwe data en tabellen bij de eigen
projectstap blijven. Losse analyse-output blijft bij `7_analyses/processed/`,
behalve wanneer een los script tijdelijk bestaande workflow-output onder
`0_layers/processed/` hergebruikt.
