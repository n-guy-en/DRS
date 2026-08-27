"""
Download sportvoorzieningen uit OpenStreetMap (Overpass) en merge met Gemeente Súdwest-Fryslân WFS.

Output:
- 3_voorzieningen/raw/sport/sport.geojson
"""

# %% Stap 1: imports en instellingen
from pathlib import Path
import json
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
from socket import timeout as SocketTimeout
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PAD = (
    BASE_DIR
    / "3_voorzieningen"
    / "raw"
    / "sport"
    / "sport.geojson"
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
  nwr["leisure"="sports_centre"](area.searchArea);
  nwr["leisure"="pitch"](area.searchArea);
  nwr["leisure"="sports_hall"](area.searchArea);
  nwr["leisure"="stadium"](area.searchArea);
  nwr["leisure"="track"](area.searchArea);
  nwr["leisure"="swimming_pool"](area.searchArea);
  nwr["leisure"="horse_riding"](area.searchArea);
);
out center meta;
""".strip()

SWF_WFS_URL = "https://geo.sudwestfryslan.nl/geoserver/swf/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=swf:geo_sportlocaties&outputFormat=application/json"


# %% Stap 2: Overpass-data ophalen
def lees_json_response(response, ophalen_url):
    tekst = response.read().decode("utf-8", errors="replace").strip()
    if not tekst:
        raise RuntimeError(f"Lege response van Overpass: {ophalen_url}")
    try:
        return json.loads(tekst)
    except json.JSONDecodeError as fout:
        preview = tekst[:500].replace("\n", " ")
        raise RuntimeError(
            f"Gaf geen geldige JSON terug. Endpoint: {ophalen_url}. Preview: {preview}"
        ) from fout


def haal_overpass_data(overpass_urls=OVERPASS_URLS):
    data = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode("utf-8")
    fouten = []
    for ophalen_url in overpass_urls:
        request = urllib.request.Request(
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
            with urllib.request.urlopen(request, timeout=240) as response:
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

    raise RuntimeError("Overpass-download mislukt:\n- " + "\n- ".join(fouten))


# %% Stap 3: Súdwest-Fryslân WFS ophalen
def haal_swf_wfs():
    print(f"Vraag Súdwest-Fryslân WFS op: {SWF_WFS_URL}")
    request = urllib.request.Request(
        SWF_WFS_URL,
        headers={"User-Agent": "DUS-voorzieningen/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Waarschuwing: Laden van Súdwest-Fryslân WFS mislukt: {e}")
        return None


# %% Stap 4: OSM elementen omzetten naar GeoJSON features
def bepaal_match_type(tags):
    leisure = tags.get("leisure", "").lower()
    if leisure:
        return f"leisure_{leisure}"
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
        "osm_id": str(element["id"]),
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
    return features


# %% Stap 5: Mergen van OSM en SWF WFS data
def maak_tekst(waarde, *, lower=False):
    if pd.isna(waarde):
        return None

    if isinstance(waarde, float) and waarde.is_integer():
        waarde = int(waarde)

    tekst = str(waarde).strip()
    if not tekst:
        return None

    return tekst.lower() if lower else tekst


def maak_adres_huisnummer(row):
    huisnummer = maak_tekst(row.get("huisnummer")) or ""
    huisletter = maak_tekst(row.get("huisletter")) or ""
    return maak_tekst(f"{huisnummer}{huisletter}")


def merge_datasets(osm_features, swf_wfs_data):
    if not swf_wfs_data or not swf_wfs_data.get("features"):
        print("Geen SWF WFS data om te mergen. Gebruik alleen OSM data.")
        return osm_features

    print("Verwerk en vergelijk OSM en Súdwest-Fryslân WFS...")
    
    # Maak GeoDataFrames voor ruimtelijke vergelijking
    # OSM
    osm_rows = []
    for f in osm_features:
        props = f["properties"].copy()
        coords = f["geometry"]["coordinates"]
        props["geometry"] = Point(coords[0], coords[1])
        osm_rows.append(props)
    
    osm_gdf = gpd.GeoDataFrame(osm_rows, geometry="geometry", crs="EPSG:4326")
    osm_gdf_rd = osm_gdf.to_crs("EPSG:28992")

    # SWF WFS (WFS coordinaten zijn in RD EPSG:28992)
    swf_rows = []
    for f in swf_wfs_data["features"]:
        props = f["properties"].copy()
        geom = f["geometry"]
        if geom and geom["type"] == "Point":
            coords = geom["coordinates"]
            props["geometry"] = Point(coords[0], coords[1])
        else:
            props["geometry"] = None
        swf_rows.append(props)
        
    swf_gdf_rd = gpd.GeoDataFrame(swf_rows, geometry="geometry", crs="EPSG:28992")
    swf_gdf_rd = swf_gdf_rd[swf_gdf_rd.geometry.notna()].copy()

    # Koppel WFS aan dichtstbijzijnde OSM binnen 100 meter
    matched = gpd.sjoin_nearest(
        swf_gdf_rd,
        osm_gdf_rd,
        how="left",
        max_distance=100.0,
        distance_col="match_distance"
    )

    # Identificeer niet-gekoppelde WFS records
    unmatched_swf_ids = swf_gdf_rd["id"].isin(matched[matched["osm_id"].isna()]["id"])
    unmatched_swf = swf_gdf_rd[unmatched_swf_ids].copy()
    print(f"Súdwest-Fryslân WFS: {len(swf_gdf_rd)} locaties, waarvan {len(unmatched_swf)} niet in OSM gevonden (binnen 100m).")

    # Convert unmatched WFS features to WGS84 and add to list of features
    unmatched_swf_wgs = unmatched_swf.to_crs("EPSG:4326")
    
    merged_features = list(osm_features)
    for idx, row in unmatched_swf_wgs.iterrows():
        geom = row["geometry"]
        
        # Map properties naar OSM-achtige tags
        tags = {
            "osm_type": "municipal_wfs",
            "osm_id": f"swf_{row['id']}",
            "match_type": "municipal_wfs",
            "name": maak_tekst(row.get("naam_accommodatie")),
            "sport": maak_tekst(row.get("type"), lower=True) or "unknown",
            "brand": maak_tekst(row.get("naam_vereniging")),
            "website": maak_tekst(row.get("website__url_")),
            "addr:city": maak_tekst(row.get("woonplaats")),
            "addr:street": maak_tekst(row.get("straatnaam")),
            "addr:housenumber": maak_adres_huisnummer(row),
            "addr:postcode": maak_tekst(row.get("postcode")),
            "leisure": "sports_centre" if row.get("soort_accomodatie") == "Binnensportaccommodaties" else "pitch",
            "source": "gemeente_swf"
        }
        
        feature = {
            "type": "Feature",
            "properties": tags,
            "geometry": {
                "type": "Point",
                "coordinates": [geom.x, geom.y]
            }
        }
        merged_features.append(feature)

    print(f"Merged resultaat bevat {len(merged_features)} sportvoorzieningen.")
    return merged_features


# %% Stap 6: main
def main():
    # 1. Download OSM
    overpass_data = haal_overpass_data()
    osm_features = maak_geojson(overpass_data)
    print(f"OSM sportvoorzieningen gedownload: {len(osm_features)}")

    # 2. Download SWF WFS
    swf_wfs_data = haal_swf_wfs()

    # 3. Merge
    merged_features = merge_datasets(osm_features, swf_wfs_data)

    # 4. Schrijf output
    OUTPUT_PAD.parent.mkdir(parents=True, exist_ok=True)
    geojson = {
        "type": "FeatureCollection",
        "name": "sport",
        "features": merged_features
    }
    
    with OUTPUT_PAD.open("w", encoding="utf-8") as bestand:
        json.dump(geojson, bestand, ensure_ascii=False, indent=2)

    print(f"Opgeslagen: {OUTPUT_PAD}")


if __name__ == "__main__":
    main()
