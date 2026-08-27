"""
Download recreatief groen uit OpenStreetMap via Overpass.

Output:
- 3_voorzieningen/raw/recreatief_groen/recreatief_groen.geojson
"""

# %% Stap 1: imports en instellingen
from pathlib import Path
import json
from json import JSONDecodeError
from socket import timeout as SocketTimeout
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PAD = (
    BASE_DIR
    / "3_voorzieningen"
    / "raw"
    / "recreatief_groen"
    / "recreatief_groen.geojson"
)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
]

OVERPASS_QUERY = """
[out:json][timeout:300];

area["ISO3166-2"="NL-FR"]->.searchArea;

(
  nwr["leisure"="park"](area.searchArea);
  nwr["landuse"="recreation_ground"](area.searchArea);
  nwr["leisure"="garden"](area.searchArea);
  nwr["leisure"="playground"](area.searchArea);
  nwr["boundary"="national_park"](area.searchArea);
  nwr["leisure"="nature_reserve"](area.searchArea);
);

out center meta;
""".strip()


# %% Stap 2: Overpass-data ophalen
def lees_json_response(response, ophalen_url):
    tekst = response.read().decode("utf-8", errors="replace").strip()

    if not tekst:
        raise RuntimeError(f"Lege response van Overpass: {ophalen_url}")

    try:
        return json.loads(tekst)
    except JSONDecodeError as fout:
        preview = tekst[:500].replace("\n", " ")
        raise RuntimeError(
            "Overpass gaf geen geldige JSON terug. "
            f"Endpoint: {ophalen_url}. Eerste response-tekst: {preview}"
        ) from fout


def haal_overpass_data(overpass_urls=OVERPASS_URLS):
    data = urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    fouten = []

    for ophalen_url in overpass_urls:
        request = Request(
            ophalen_url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "DUS-voorzieningen/1.0",
            },
            method="POST",
        )

        print(f"Vraag Overpass op: {ophalen_url}")

        try:
            with urlopen(request, timeout=240) as response:
                return lees_json_response(response, ophalen_url)
        except HTTPError as fout:
            fouten.append(f"{ophalen_url}: HTTP {fout.code}")
        except URLError as fout:
            fouten.append(f"{ophalen_url}: {fout}")
        except TimeoutError:
            fouten.append(f"{ophalen_url}: timeout")
        except SocketTimeout:
            fouten.append(f"{ophalen_url}: socket timeout")
        except RuntimeError as fout:
            fouten.append(str(fout))

    raise RuntimeError(
        "Overpass-download mislukt:\n- " + "\n- ".join(fouten)
    )


# %% Stap 3: Overpass-elementen omzetten naar GeoJSON
def bepaal_match_type(tags):
    leisure = tags.get("leisure", "").lower()
    landuse = tags.get("landuse", "").lower()
    boundary = tags.get("boundary", "").lower()

    if leisure:
        return f"leisure_{leisure}"
    if landuse:
        return f"landuse_{landuse}"
    if boundary:
        return f"boundary_{boundary}"

    return "unknown"


def element_naar_feature(element):
    if element["type"] == "node":
        lon = element.get("lon")
        lat = element.get("lat")
    else:
        center = element.get("center") or {}
        lon = center.get("lon")
        lat = center.get("lat")

    if lon is None or lat is None:
        return None

    tags = element.get("tags", {})

    properties = {
        "osm_type": element["type"],
        "osm_id": element["id"],
        "match_type": bepaal_match_type(tags),
        "osm_timestamp": element.get("timestamp", ""),
        **tags,
    }

    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
    }


def maak_geojson(overpass_data):
    features = []
    geziene_elementen = set()

    for element in overpass_data.get("elements", []):
        sleutel = (element.get("type"), element.get("id"))

        if sleutel in geziene_elementen:
            continue

        geziene_elementen.add(sleutel)

        feature = element_naar_feature(element)
        if feature is not None:
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "name": "recreatief_groen",
        "features": features,
    }


# %% Stap 4: output schrijven
def schrijf_geojson(geojson, output_pad):
    output_pad.parent.mkdir(parents=True, exist_ok=True)

    with output_pad.open("w", encoding="utf-8") as bestand:
        json.dump(geojson, bestand, ensure_ascii=False, indent=2)

    print(f"Recreatief groen gedownload: {len(geojson['features'])}")
    print(f"Opgeslagen: {output_pad}")


# %% Stap 5: workflow uitvoeren
def main():
    overpass_data = haal_overpass_data()
    geojson = maak_geojson(overpass_data)
    schrijf_geojson(geojson, OUTPUT_PAD)


if __name__ == "__main__":
    main()
