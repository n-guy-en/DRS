# %% Stap 1: imports en instellingen
from pathlib import Path
import shutil
import sys
import time


NETWERK_TYPES = ("walk", "bike", "drive")

# %% CONFIGURATIE
GEBIED = "Friesland, Netherlands"
TYPES = list(NETWERK_TYPES)
OUTPUT = None
VEREENVOUDIGEN = True
OVERSCHRIJVEN = False
DOWNLOAD_POGINGEN = 4
WACHTTIJDEN_SECONDEN = (60, 180, 300)
OVERPASS_URLS = (
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
)
STOP_BIJ_DOWNLOADFOUT = True


class DownloadFout(RuntimeError):
    pass


# %% Stap 2: projectpaden en OSMnx instellen
def project_dir():
    return Path(__file__).resolve().parents[1]


def laad_osmnx():
    try:
        import osmnx as ox
    except ImportError:
        print(
            "Package ontbreekt: osmnx\n"
            "Installeer met: python3 -m pip install osmnx",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return ox


def stel_osmnx_in(ox, overpass_url=None):
    ox.settings.use_cache = True
    ox.settings.log_console = True
    ox.settings.timeout = 180
    ox.settings.requests_timeout = 180

    if overpass_url and hasattr(ox.settings, "overpass_url"):
        ox.settings.overpass_url = overpass_url

    cache_map = project_dir() / "4_netwerk" / "processed" / "OSM" / "cache"
    cache_map.mkdir(parents=True, exist_ok=True)

    if hasattr(ox.settings, "cache_folder"):
        ox.settings.cache_folder = str(cache_map)


def maak_output_map(output):
    if output:
        output_map = Path(output)
    else:
        output_map = project_dir() / "4_netwerk" / "processed" / "OSM"

    output_map.mkdir(parents=True, exist_ok=True)
    return output_map


# %% Stap 3: netwerk downloaden en reistijden toevoegen
def maak_netwerk(ox, gebied, netwerk_type, vereenvoudigen):
    print(f"Download OSM-netwerk: {netwerk_type}")
    return ox.graph_from_place(
        gebied,
        network_type=netwerk_type,
        simplify=vereenvoudigen,
        retain_all=False,
        truncate_by_edge=True,
    )


def download_netwerk_met_retries(ox, gebied, netwerk_type, vereenvoudigen):
    laatste_fout = None

    for poging in range(1, DOWNLOAD_POGINGEN + 1):
        overpass_url = OVERPASS_URLS[(poging - 1) % len(OVERPASS_URLS)]
        stel_osmnx_in(ox, overpass_url=overpass_url)
        print(
            f"Downloadpoging {poging}/{DOWNLOAD_POGINGEN} "
            f"voor {netwerk_type} via {overpass_url}"
        )

        try:
            return maak_netwerk(ox, gebied, netwerk_type, vereenvoudigen)
        except Exception as fout:
            laatste_fout = fout
            if poging == DOWNLOAD_POGINGEN:
                break

            wachttijd = WACHTTIJDEN_SECONDEN[
                min(poging - 1, len(WACHTTIJDEN_SECONDEN) - 1)
            ]
            print(
                f"Download mislukt voor {netwerk_type}: {fout}\n"
                f"Nieuwe poging over {wachttijd} seconden."
            )
            time.sleep(wachttijd)

    raise DownloadFout(
        f"OSM-netwerk kon niet worden opgehaald: {netwerk_type}"
    ) from laatste_fout


def voeg_reistijd_toe(graph, netwerk_type):
    snelheid_kmh = {
        "walk": 4.8,
        "bike": 15.0,
    }.get(netwerk_type)

    if snelheid_kmh is not None:
        snelheid_m_per_min = snelheid_kmh * 1000 / 60

        for _, _, _, data in graph.edges(keys=True, data=True):
            lengte_meter = data.get("length")
            if lengte_meter is None:
                continue

            data["speed_kph"] = snelheid_kmh
            data["travel_time_min"] = float(lengte_meter) / snelheid_m_per_min

        return graph

    try:
        import osmnx as ox

        graph = ox.add_edge_speeds(graph)
        graph = ox.add_edge_travel_times(graph)

        for _, _, _, data in graph.edges(keys=True, data=True):
            reistijd_sec = data.get("travel_time")
            if reistijd_sec is not None:
                data["travel_time_min"] = float(reistijd_sec) / 60
    except Exception as fout:
        print(
            "Waarschuwing: autosnelheden/reistijden konden niet volledig "
            f"worden toegevoegd: {fout}"
        )

    return graph


# %% Stap 4: output schrijven
def sla_netwerk_op(ox, graph, output_map, netwerk_type):
    nodes, edges = ox.graph_to_gdfs(graph)
    nodes = nodes.reset_index()
    edges = edges.reset_index()
    nodes_pad = output_map / f"{netwerk_type}_nodes.gpkg"
    edges_pad = output_map / f"{netwerk_type}_edges.gpkg"
    tijdelijk_map = output_map / "_tijdelijk" / netwerk_type
    tijdelijk_nodes_pad = tijdelijk_map / nodes_pad.name
    tijdelijk_edges_pad = tijdelijk_map / edges_pad.name

    if tijdelijk_map.exists():
        shutil.rmtree(tijdelijk_map)
    tijdelijk_map.mkdir(parents=True, exist_ok=True)

    nodes.to_file(
        tijdelijk_nodes_pad,
        layer=f"{netwerk_type}_nodes",
        driver="GPKG",
        index=True,
    )
    edges.to_file(
        tijdelijk_edges_pad,
        layer=f"{netwerk_type}_edges",
        driver="GPKG",
        index=True,
    )

    tijdelijk_nodes_pad.replace(nodes_pad)
    tijdelijk_edges_pad.replace(edges_pad)
    shutil.rmtree(tijdelijk_map)

    print(f"Opgeslagen: {nodes_pad}")
    print(f"Opgeslagen: {edges_pad}")


def bestanden_compleet(nodes_pad, edges_pad):
    return (
        nodes_pad.exists()
        and edges_pad.exists()
        and nodes_pad.stat().st_size > 0
        and edges_pad.stat().st_size > 0
    )


# %% Stap 5: workflow uitvoeren
def main():
    ox = laad_osmnx()
    stel_osmnx_in(ox)

    output_map = maak_output_map(OUTPUT)
    print(f"Gebied: {GEBIED}")
    print(f"Outputmap: {output_map}")

    for netwerk_type in TYPES:
        nodes_pad = output_map / f"{netwerk_type}_nodes.gpkg"
        edges_pad = output_map / f"{netwerk_type}_edges.gpkg"

        if bestanden_compleet(nodes_pad, edges_pad) and not OVERSCHRIJVEN:
            print(f"Overgeslagen, bestaat al: {nodes_pad}")
            print(f"Overgeslagen, bestaat al: {edges_pad}")
            continue

        try:
            graph = download_netwerk_met_retries(
                ox,
                GEBIED,
                netwerk_type,
                vereenvoudigen=VEREENVOUDIGEN,
            )
        except DownloadFout as fout:
            print(fout, file=sys.stderr)
            print(
                "Overpass is tijdelijk niet bereikbaar of overbelast. "
                "Bestaande output is niet vervangen.",
                file=sys.stderr,
            )
            if STOP_BIJ_DOWNLOADFOUT:
                raise SystemExit(1) from None
            continue

        graph = voeg_reistijd_toe(graph, netwerk_type)
        sla_netwerk_op(
            ox,
            graph,
            output_map,
            netwerk_type,
        )


if __name__ == "__main__":
    main()
