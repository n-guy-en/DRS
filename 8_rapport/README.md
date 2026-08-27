# Rapport

Deze map bevat rapporttabellen en legenda's voor de bereikbaarheidsanalyse.

De rapportstap rekent geen nieuwe bereikbaarheid uit. De tabellen worden
samengesteld uit de bestaande output van `5_bereikbaarheid`. De legenda's worden
gemaakt op basis van de kleur- en norminstellingen uit `5_bereikbaarheid` en
`6_interpretatie`.

---

# Structuur

```text
8_rapport/
  README.md
  LEGENDA.md
  rapport.py
  legenda.py
  helpers/
  legenda/
  processed/
    rapport/
```

| Map of bestand | Wat staat erin? |
|---|---|
| `rapport.py` | Maakt de rapporttabellen en schrijft de output weg |
| `legenda.py` | Maakt SVG-legenda's voor kaartlagen uit `5_bereikbaarheid` en `6_interpretatie` |
| `helpers/` | Helpers voor instellingen, invoer, tabellen en Excel |
| `LEGENDA.md` | Toelichting op legenda's, kleuren en labels |
| `legenda/` | Gegenereerde SVG-legenda's |
| `processed/rapport/` | Gegenereerde rapporttabellen en controles |

`processed/` bevat reproduceerbare uitvoer en wordt niet in git opgeslagen.

De rapporthelpers zijn als volgt verdeeld:

| Helper | Verantwoordelijkheid |
|---|---|
| `instellingen.py` | Vaste paden, modaliteiten, labels en voorzieningrun-definitie |
| `invoer.py` | Beschikbare voorzieningen detecteren en pand-, buurt- en gemeentetabellen inlezen |
| `tabellen.py` | Rapporttabellen berekenen |
| `excel.py` | Excelbestand schrijven |

---

# Workflow

Voer eerst de benodigde bereikbaarheidsstap uit:

```bash
python3 5_bereikbaarheid/bop.py
```

Maak daarna de rapporttabellen:

```bash
python3 8_rapport/rapport.py
```

Maak daarna de legenda's:

```bash
python3 8_rapport/legenda.py
```

`rapport.py` neemt een voorziening alleen mee wanneer alle vijf modaliteiten
beschikbaar zijn:

```text
lopen
fiets
auto
ov_lopen
ov_fiets
```

Onderwijsniveaus worden als afzonderlijke voorzieningen behandeld wanneer de
output per niveau beschikbaar is.

---

# Output

De rapporttabellen worden opgeslagen in:

```text
8_rapport/processed/rapport/
```

Belangrijke output:

```text
8_rapport/processed/rapport/controle/overzicht_rapport.csv
8_rapport/processed/rapport/controle/controles_eindoutput.csv
8_rapport/processed/rapport/provinciaal/rapport_daily_urban_systems.xlsx
8_rapport/processed/rapport/voorzieningen/<voorziening>/
8_rapport/processed/rapport/provinciaal/01_modaliteitenranglijst_per_voorziening.csv
8_rapport/processed/rapport/provinciaal/02_aantal_onvoldoende_modaliteiten.csv
8_rapport/processed/rapport/provinciaal/03_bereikbaarheidsprofielen.csv
8_rapport/processed/rapport/provinciaal/04_kerncijfers_per_voorziening.csv
8_rapport/processed/rapport/provinciaal/05_gemeenteranglijst_per_voorziening_modaliteit.csv
8_rapport/processed/rapport/provinciaal/06_beste_en_slechtste_gemeenten.csv
8_rapport/processed/rapport/provinciaal/07_buurtranglijst_per_voorziening_modaliteit.csv
8_rapport/processed/rapport/provinciaal/08_beste_en_slechtste_buurten.csv
8_rapport/processed/rapport/provinciaal/09_samenvatting_zwakste_modaliteit_en_aandachtsvoorziening.csv
```

De Excel bevat dezelfde provinciale rapporttabellen als de losse CSV-bestanden.
De CSV-bestanden blijven handig voor controle, hergebruik en import in andere
programma's.

De map `provinciaal/` bevat negen provinciale CSV-tabellen en één Excelbestand.
De map `voorzieningen/` bevat dezelfde typen tabellen uitgesplitst per
voorziening.

Niet complete voorzieningenruns worden overgeslagen. Er worden geen fictieve
uitkomsten gemaakt.

---

# Bronnen

De rapporttabellen gebruiken deze primaire bronbestanden:

```text
0_layers/processed/5_bereikbaarheid/.../<voorziening>_<code>.gpkg
5_bereikbaarheid/processed/.../buurten_<code>.csv
5_bereikbaarheid/processed/.../gemeenten_<code>.csv
```

De unieke woonpandsleutel is `pand_id` uit de BAG-woonpandlagen. Modaliteiten
worden alleen op deze sleutel gecombineerd.

---

# Uitgangspunten

* modaliteiten blijven afzonderlijk;
* er wordt geen gemiddelde over modaliteiten gemaakt;
* multimodale indicatoren worden alleen op unieke `pand_id` afgeleid;
* onderwijsniveaus worden als aparte voorzieningen gerapporteerd;
* kaartlagen blijven leidend in `0_layers/processed`;
* rapportoutput staat in `8_rapport/processed`.

---

# Legenda

De projectbrede uitleg van legenda's, labels, drempels en kleuren staat in:

```text
8_rapport/LEGENDA.md
```

De SVG-legenda's worden opgeslagen in:

```text
8_rapport/legenda/
```

`legenda.py` haalt de kleuren, normen en klasses uit de scripts van
`5_bereikbaarheid` en `6_interpretatie`. Als de kaartstijl daar wijzigt, worden de
legenda's opnieuw volgens dezelfde instellingen gemaakt.

---
