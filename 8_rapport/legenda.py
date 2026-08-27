"""Maak SVG-legenda's voor rapportage en presentatie."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
LEGENDA_DIR = BASE_DIR / "legenda"

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

bereik_config = import_module("5_bereikbaarheid.helpers.instellingen")
bereik_output = import_module("5_bereikbaarheid.helpers.output")
pandstromen = import_module("5_bereikbaarheid.helpers.pandstromen")
interpretatie_knelpunten = import_module("6_interpretatie.helpers.knelpunten")
dus_isochroon = import_module("6_interpretatie.helpers.isochroon")

MODI = tuple(bereik_config.MODUS_CODES)


def drempels_voor_norm(norm_min: float) -> tuple[float, ...]:
    if norm_min <= 15 and norm_min % 5 == 0:
        return tuple(float(waarde) for waarde in range(5, int(norm_min) + 1, 5))
    if norm_min <= 30 and norm_min % 10 == 0:
        return tuple(float(waarde) for waarde in range(10, int(norm_min) + 1, 10))
    return (
        round(norm_min / 3, 1),
        round(norm_min * 2 / 3, 1),
        float(norm_min),
    )


def fmt_min(waarde: float) -> str:
    return f"{waarde:g}"


def flow_label_voor_legenda(label: str) -> str:
    return label.replace("pandroutes", "routes").replace("pandroute", "route")


def svg_legenda(titel: str, items: list[dict], breedte: int = 500) -> str:
    rijhoogte = 44
    hoogte = 70 + rijhoogte * len(items) + 24
    rows = []
    y = 76
    for item in items:
        if item.get("type") == "line":
            rows.append(
                f'<line x1="30" y1="{y + 12}" x2="88" y2="{y + 12}" '
                f'stroke="{item["kleur"]}" stroke-width="{item["width"]}" '
                f'stroke-opacity="{item.get("opacity", 1)}" stroke-linecap="round"/>'
            )
        else:
            rows.append(
                f'<rect x="30" y="{y}" width="58" height="26" '
                f'fill="{item["kleur"]}" fill-opacity="{item.get("opacity", 1)}" '
                f'stroke="{item.get("stroke", "#ffffff")}" stroke-width="1.2"/>'
            )
        rows.append(f'<text x="112" y="{y + 20}" class="label">{item["label"]}</text>')
        y += rijhoogte

    rows_str = "\n  ".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{breedte}" height="{hoogte}" viewBox="0 0 {breedte} {hoogte}">
  <style>
    .title {{ font: 700 30px Arial, sans-serif; fill: #111827; }}
    .label {{ font: 400 26px Arial, sans-serif; fill: #111827; }}
  </style>
  <rect x="0" y="0" width="{breedte}" height="{hoogte}" fill="#ffffff"/>
  <text x="{breedte / 2:g}" y="42" text-anchor="middle" class="title">{titel}</text>
  {rows_str}
</svg>
"""


def schrijf_svg(relatief_pad: str, inhoud: str) -> None:
    pad = LEGENDA_DIR / relatief_pad
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(inhoud, encoding="utf-8")


def maak_basislegendas() -> None:
    schrijf_svg(
        "5_bereikbaarheid/buurtkaart.svg",
        svg_legenda(
            "Legenda",
            [
                {
                    "label": kleurklasse[2],
                    "kleur": kleurklasse[3],
                    "stroke": "#555555",
                }
                for kleurklasse in bereik_config.KLEUREN
            ] + [
                {"label": "Geen woningen", "kleur": "#bdbdbd", "stroke": "#555555"},
            ],
        ),
    )
    schrijf_svg(
        "5_bereikbaarheid/pandstatus.svg",
        svg_legenda(
            "Legenda",
            [
                {
                    "label": "Binnen de gewenste reistijd",
                    "kleur": bereik_output.PANDSTATUS_STIJL["binnen_norm"],
                },
                {
                    "label": "Buiten de gewenste reistijd",
                    "kleur": bereik_output.PANDSTATUS_STIJL["buiten_norm"],
                },
                {
                    "label": "Geen betrouwbare route",
                    "kleur": bereik_output.PANDSTATUS_STIJL[
                        "geen_betrouwbare_route"
                    ],
                },
            ],
        ),
    )
    schrijf_svg(
        "6_interpretatie/knelpunten.svg",
        svg_legenda(
            "Legenda",
            [
                {
                    "label": interpretatie_knelpunten.aantal_modaliteiten_label(aantal),
                    "kleur": interpretatie_knelpunten.KNELPUNT_STIJL[
                        interpretatie_knelpunten.aantal_modaliteiten_categorie(aantal)
                    ][0],
                    "stroke": interpretatie_knelpunten.KNELPUNT_STIJL[
                        interpretatie_knelpunten.aantal_modaliteiten_categorie(aantal)
                    ][1],
                }
                for aantal in range(0, 6)
            ] + [
                {
                    "label": "Geen woningen",
                    "kleur": interpretatie_knelpunten.KNELPUNT_STIJL[
                        "datacontrole_uitvoeren"
                    ][0],
                    "stroke": interpretatie_knelpunten.KNELPUNT_STIJL[
                        "datacontrole_uitvoeren"
                    ][1],
                },
            ],
            breedte=620,
        ),
    )
    schrijf_svg(
        "5_bereikbaarheid/stromenkaart.svg",
        svg_legenda(
            "Legenda",
            [
                {
                    "type": "line",
                    "label": flow_label_voor_legenda(label),
                    "kleur": kleur,
                    "width": max(1, lijndikte * 1.5),
                    "opacity": opacity,
                }
                for label, lijndikte, kleur, opacity in pandstromen.FLOW_KLASSEN
            ],
            breedte=560,
        ),
    )


def normen_per_voorziening() -> dict[str, dict[str, float]]:
    normen = {
        voorziening: dict(modus_normen)
        for voorziening, modus_normen
        in bereik_config.NORMEN_PER_VOORZIENING.items()
    }
    normen["ziekenhuis_joure"] = dict(normen["ziekenhuis"])
    return normen


def maak_isochroonlegendas() -> None:
    for voorziening, normen in normen_per_voorziening().items():
        for modus, norm_min in normen.items():
            vorige = 0.0
            items = []
            for index, drempel in enumerate(drempels_voor_norm(norm_min)):
                fill, stroke, opacity = dus_isochroon.BAND_KLEUREN[
                    min(index, len(dus_isochroon.BAND_KLEUREN) - 1)
                ]
                items.append(
                    {
                        "label": f"{fmt_min(vorige)}-{fmt_min(drempel)} min",
                        "kleur": fill,
                        "stroke": stroke,
                        "opacity": opacity,
                    }
                )
                vorige = drempel
            schrijf_svg(
                f"6_interpretatie/isochronen/{voorziening}/isochronen_{modus}.svg",
                svg_legenda(
                    "Legenda",
                    items,
                    breedte=420,
                ),
            )


def main() -> None:
    maak_basislegendas()
    maak_isochroonlegendas()


if __name__ == "__main__":
    main()
