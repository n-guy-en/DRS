"""Kaartlagen voor het GTFS OV-netwerk."""

import json
import math

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from .geometrie import maak_shape_segment
from .instellingen import CRS_RD, CRS_WGS84, KAARTCONTROLE_DIR, LAGEN_DIR
from .lijnen import maak_ov_lijn_segment
from .samenvatting import maak_ov_publicatie_output
from .tekst import unieke_tekst


def maak_json_schoon(waarde):
    """Maak waarden geldig voor strikte GeoJSON/Mapshaper."""
    if isinstance(waarde, dict):
        return {key: maak_json_schoon(item) for key, item in waarde.items()}
    if isinstance(waarde, list):
        return [maak_json_schoon(item) for item in waarde]
    if pd.isna(waarde):
        return None
    if isinstance(waarde, float) and not math.isfinite(waarde):
        return None
    return waarde


def schrijf_geojson(pad, features):
    """Schrijf een GeoJSON FeatureCollection."""
    geojson = {"type": "FeatureCollection", "features": features}
    with open(pad, "w", encoding="utf-8") as bestand:
        json.dump(
            maak_json_schoon(geojson),
            bestand,
            ensure_ascii=False,
            allow_nan=False,
        )
    return geojson


def maak_shape_lijnen(shapes, line_total_summary, trip_total_summary):
    """Maak GTFS-shapes als WGS84 LineStrings."""
    shape_lijnen = {}
    if shapes.empty or "shape_id" not in shapes.columns:
        return shape_lijnen

    shape_ids = set(line_total_summary["shape_id"].dropna().astype(str).unique())
    shape_ids.update(trip_total_summary["shape_id"].dropna().astype(str).unique())
    shapes_selectie = shapes[shapes["shape_id"].astype(str).isin(shape_ids)].copy()

    for kolom in ["shape_pt_sequence", "shape_pt_lat", "shape_pt_lon"]:
        shapes_selectie[kolom] = pd.to_numeric(shapes_selectie[kolom], errors="coerce")

    for shape_id, shape_group in shapes_selectie.groupby("shape_id"):
        shape_group = shape_group.sort_values("shape_pt_sequence")
        coordinates = [
            (row["shape_pt_lon"], row["shape_pt_lat"])
            for _, row in shape_group.iterrows()
            if pd.notna(row["shape_pt_lon"]) and pd.notna(row["shape_pt_lat"])
        ]
        if len(coordinates) >= 2:
            shape_lijnen[str(shape_id)] = LineString(coordinates)

    return shape_lijnen


def lijnverbinding_geometrie(line, shape_lijnen, lijnen_frl):
    """Bepaal de beste geometrie voor een lijnverbinding."""
    shape_segment = maak_shape_segment(
        shape_lijnen.get(str(line["shape_id"])),
        line["from_stop_lon"],
        line["from_stop_lat"],
        line["to_stop_lon"],
        line["to_stop_lat"],
    )
    if shape_segment is not None:
        return list(shape_segment.coords), "gtfs_shape_segment", {}

    ov_lijn_segment = maak_ov_lijn_segment(line, lijnen_frl)
    if ov_lijn_segment is not None:
        segment_wgs84 = gpd.GeoSeries(
            [ov_lijn_segment["segment"]],
            crs=CRS_RD,
        ).to_crs(CRS_WGS84).iloc[0]
        extra = {
            "segment_projection_distance_from_m": ov_lijn_segment["from_afstand_m"],
            "segment_projection_distance_to_m": ov_lijn_segment["to_afstand_m"],
            "afstand_langs_lijn_m": ov_lijn_segment["afstand_langs_lijn_m"],
        }
        return list(segment_wgs84.coords), "ov_lijn_segment", extra

    if all(
        pd.notna(line[kolom])
        for kolom in ["from_halte_x", "from_halte_y", "to_halte_x", "to_halte_y"]
    ):
        punten = gpd.GeoSeries(
            [
                Point(float(line["from_halte_x"]), float(line["from_halte_y"])),
                Point(float(line["to_halte_x"]), float(line["to_halte_y"])),
            ],
            crs=CRS_RD,
        ).to_crs(CRS_WGS84)
        return [
            (punten.iloc[0].x, punten.iloc[0].y),
            (punten.iloc[1].x, punten.iloc[1].y),
        ], "haltes_frl", {}

    if all(
        pd.notna(line[kolom])
        for kolom in ["from_stop_lon", "from_stop_lat", "to_stop_lon", "to_stop_lat"]
    ):
        return [
            (float(line["from_stop_lon"]), float(line["from_stop_lat"])),
            (float(line["to_stop_lon"]), float(line["to_stop_lat"])),
        ], "gtfs_stop_coords", {}

    return None, None, {}


def maak_lijnverbinding_features(line_total_summary, shape_lijnen, lijnen_frl):
    """Maak kaartfeatures voor exacte lijnverbindingen."""
    features = []
    for _, line in line_total_summary.iterrows():
        coords, geometry_source, extra = lijnverbinding_geometrie(
            line,
            shape_lijnen,
            lijnen_frl,
        )
        if coords is None:
            continue

        properties = maak_ov_publicatie_output(
            line.drop(labels=["geometry"], errors="ignore").to_frame().T
        ).iloc[0].to_dict()
        properties.update(extra)
        properties["geometry_source"] = geometry_source
        properties["tooltip"] = (
            f"Lijn {line['line_id']}"
            f"<br>Richting: {line['trip_headsign']}"
            f"<br>Van: {line['from_stop_name']}"
            f"<br>Naar: {line['to_stop_name']}"
            f"<br>Reistijd verbinding: {line['total_travel_time_min']} min"
            f"<br>Totale rit: {line['trip_from_stop_name']} "
            f"-> {line['trip_to_stop_name']} "
            f"({line['trip_total_travel_time_min']} min)"
            f"<br>Aantal ritten: {line['aantal_trips']}"
        )
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[coord[0], coord[1]] for coord in coords],
                },
                "properties": properties,
            }
        )
    return features


def maak_ritroute_features(trip_total_summary, shape_lijnen):
    """Maak kaartfeatures voor totale GTFS-ritten."""
    features = []
    for _, trip_route in trip_total_summary.iterrows():
        shape_lijn = shape_lijnen.get(str(trip_route["shape_id"]))
        if shape_lijn is not None:
            coords = list(shape_lijn.coords)
            geometry_source = "gtfs_shape"
        elif all(
            pd.notna(trip_route[kolom])
            for kolom in [
                "trip_from_stop_lon",
                "trip_from_stop_lat",
                "trip_to_stop_lon",
                "trip_to_stop_lat",
            ]
        ):
            coords = [
                (
                    float(trip_route["trip_from_stop_lon"]),
                    float(trip_route["trip_from_stop_lat"]),
                ),
                (
                    float(trip_route["trip_to_stop_lon"]),
                    float(trip_route["trip_to_stop_lat"]),
                ),
            ]
            geometry_source = "gtfs_stop_coords"
        else:
            continue

        properties = maak_ov_publicatie_output(
            trip_route.drop(labels=["geometry"], errors="ignore").to_frame().T
        ).iloc[0].to_dict()
        properties["geometry_source"] = geometry_source
        properties["tooltip"] = (
            f"Lijn {trip_route['line_id']}"
            f"<br>Richting: {trip_route['trip_headsign']}"
            f"<br>Van: {trip_route['trip_from_stop_name']}"
            f"<br>Naar: {trip_route['trip_to_stop_name']}"
            f"<br>Totale reistijd: "
            f"{trip_route['trip_total_travel_time_min']} min"
            f"<br>Aantal stops: {trip_route['aantal_stops']}"
            f"<br>Aantal ritten: {trip_route['aantal_trips']}"
        )
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[coord[0], coord[1]] for coord in coords],
                },
                "properties": properties,
            }
        )
    return features


def maak_haltepunt_records(line_total_summary):
    """Maak losse records voor haltepunten uit lijnverbindingen."""
    records = []
    for _, verbinding in line_total_summary.iterrows():
        for kant in ["from", "to"]:
            halte_id = verbinding[f"{kant}_halte_id"]
            halte_x = verbinding[f"{kant}_halte_x"]
            halte_y = verbinding[f"{kant}_halte_y"]
            stop_lon = verbinding[f"{kant}_stop_lon"]
            stop_lat = verbinding[f"{kant}_stop_lat"]
            heeft_halte = (
                pd.notna(halte_id)
                and str(halte_id).strip() != ""
                and str(halte_id).lower() != "nan"
            )

            if heeft_halte and pd.notna(halte_x) and pd.notna(halte_y):
                punt = gpd.GeoSeries(
                    [Point(float(halte_x), float(halte_y))],
                    crs=CRS_RD,
                ).to_crs(CRS_WGS84).iloc[0]
                node_id = "ov_halte_" + str(halte_id)
                geometry_source = "ov_halte"
            elif pd.notna(stop_lon) and pd.notna(stop_lat):
                punt = Point(float(stop_lon), float(stop_lat))
                node_id = "gtfs_stop_" + str(verbinding[f"{kant}_stop_id"])
                geometry_source = "gtfs_stop_coords"
            else:
                continue

            records.append(
                {
                    "node_id": node_id,
                    "stop_id": verbinding[f"{kant}_stop_id"],
                    "stop_name": verbinding[f"{kant}_stop_name"],
                    "halte_id": halte_id,
                    "halte_naam": verbinding[f"{kant}_halte_naam"],
                    "mode": verbinding["mode"],
                    "operator": verbinding["operator"],
                    "line_id": verbinding["line_id"],
                    "route_id": verbinding["route_id"],
                    "geometry_source": geometry_source,
                    "lon": punt.x,
                    "lat": punt.y,
                }
            )
    return records


def maak_haltepunt_features(line_total_summary):
    """Maak kaartfeatures voor unieke haltepunten."""
    stop_points = pd.DataFrame(maak_haltepunt_records(line_total_summary))
    if stop_points.empty:
        return []

    summary = (
        stop_points.groupby("node_id", dropna=False)
        .agg(
            stop_ids=("stop_id", unieke_tekst),
            stop_names=("stop_name", unieke_tekst),
            halte_id=("halte_id", "first"),
            halte_naam=("halte_naam", "first"),
            modes=("mode", unieke_tekst),
            operators=("operator", unieke_tekst),
            line_ids=("line_id", unieke_tekst),
            aantal_lijnen=("line_id", "nunique"),
            aantal_routes=("route_id", "nunique"),
            aantal_verbindingen=("route_id", "count"),
            geometry_source=("geometry_source", "first"),
            lon=("lon", "first"),
            lat=("lat", "first"),
        )
        .reset_index()
    )

    features = []
    for _, halte in summary.iterrows():
        tooltip = (
            str(halte["halte_naam"])
            if pd.notna(halte["halte_naam"])
            and str(halte["halte_naam"]).strip() != ""
            else str(halte["stop_names"])
        )
        tooltip += f"<br>Lijnen: {halte['line_ids']}<br>Modes: {halte['modes']}"

        properties = halte.drop(labels=["lon", "lat"], errors="ignore").to_dict()
        properties["tooltip"] = tooltip
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(halte["lon"]), float(halte["lat"])],
                },
                "properties": properties,
            }
        )
    return features


def maak_shape_features(shape_lijnen, trips_processed):
    """Maak controlekaart met volledige GTFS-shapes."""
    if not shape_lijnen:
        print("Waarschuwing: geen bruikbare GTFS-shapes; leeg GeoJSON gemaakt.")
        return []

    shape_to_route = (
        trips_processed[
            [
                "shape_id",
                "route_id",
                "line_id",
                "route_long_name",
                "mode",
                "operator",
                "direction_id",
                "trip_headsign",
            ]
        ]
        .drop_duplicates("shape_id")
        .set_index("shape_id")
        .to_dict(orient="index")
    )

    features = []
    for shape_id, shape_lijn in shape_lijnen.items():
        coords = list(shape_lijn.coords)
        if len(coords) < 2:
            continue
        route_info = shape_to_route.get(str(shape_id), {})
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[coord[0], coord[1]] for coord in coords],
                },
                "properties": {
                    "shape_id": shape_id,
                    "route_id": route_info.get("route_id", ""),
                    "line_id": route_info.get("line_id", ""),
                    "route_long_name": route_info.get("route_long_name", ""),
                    "mode": route_info.get("mode", ""),
                    "operator": route_info.get("operator", ""),
                    "direction_id": route_info.get("direction_id", ""),
                    "trip_headsign": route_info.get("trip_headsign", ""),
                },
            }
        )
    return features


def maak_stops_index(stops_processed):
    """Maak een index op GTFS stop_id."""
    return stops_processed.assign(
        stop_id_norm=stops_processed["stop_id"].astype(str)
    ).set_index("stop_id_norm")


def eerste_stop(stops_index, stop_id):
    """Geef de eerste stoprij terug voor een stop_id."""
    stop = stops_index.loc[str(stop_id)]
    if isinstance(stop, pd.DataFrame):
        return stop.iloc[0]
    return stop


def maak_segment_tooltip_features(route_segment_summary, stops_processed):
    """Maak eenvoudige controlelaag met segment-tooltips."""
    features = []
    stops_index = maak_stops_index(stops_processed)

    for _, edge in route_segment_summary.iterrows():
        if (
            str(edge["from_stop_id"]) not in stops_index.index
            or str(edge["to_stop_id"]) not in stops_index.index
        ):
            continue

        from_stop = eerste_stop(stops_index, edge["from_stop_id"])
        to_stop = eerste_stop(stops_index, edge["to_stop_id"])
        if any(
            pd.isna(waarde)
            for waarde in [
                from_stop["stop_lon"],
                from_stop["stop_lat"],
                to_stop["stop_lon"],
                to_stop["stop_lat"],
            ]
        ):
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [float(from_stop["stop_lon"]), float(from_stop["stop_lat"])],
                        [float(to_stop["stop_lon"]), float(to_stop["stop_lat"])],
                    ],
                },
                "properties": {
                    "route_id": edge["route_id"],
                    "line_id": edge["line_id"],
                    "route_long_name": edge["route_long_name"],
                    "mode": edge["mode"],
                    "operator": edge["operator"],
                    "direction_id": edge["direction_id"],
                    "trip_headsign": edge["trip_headsign"],
                    "from_stop_id": edge["from_stop_id"],
                    "from_stop_name": edge["from_stop_name"],
                    "to_stop_id": edge["to_stop_id"],
                    "to_stop_name": edge["to_stop_name"],
                    "travel_time_min": edge["travel_time_min"],
                    "min_travel_time_min": edge["min_travel_time_min"],
                    "max_travel_time_min": edge["max_travel_time_min"],
                    "travel_time_original_min": edge["travel_time_original_min"],
                    "travel_time_correction_delta_min": (
                        edge["travel_time_correction_delta_min"]
                    ),
                    "travel_time_source": edge["travel_time_source"],
                    "travel_time_correction_note": (
                        edge["travel_time_correction_note"]
                    ),
                    "aantal_trips": edge["aantal_trips"],
                    "tooltip": (
                        f"Lijn {edge['line_id']}"
                        f"<br>Richting: {edge['trip_headsign']}"
                        f"<br>Van: {edge['from_stop_name']}"
                        f"<br>Naar: {edge['to_stop_name']}"
                        f"<br>Reistijd: {edge['travel_time_min']} min"
                        f"<br>Aantal ritten: {edge['aantal_trips']}"
                    ),
                },
            }
        )
    return features


def halte_edge_geometrie(segment, stops_index):
    """Bepaal RD-geometrie voor een halte-edge."""
    if all(
        pd.notna(segment.get(kolom))
        for kolom in ["from_halte_x", "from_halte_y", "to_halte_x", "to_halte_y"]
    ):
        return LineString(
            [
                (float(segment["from_halte_x"]), float(segment["from_halte_y"])),
                (float(segment["to_halte_x"]), float(segment["to_halte_y"])),
            ]
        ), "haltes_frl"

    if (
        str(segment["from_stop_id"]) not in stops_index.index
        or str(segment["to_stop_id"]) not in stops_index.index
    ):
        return None, None

    from_stop = eerste_stop(stops_index, segment["from_stop_id"])
    to_stop = eerste_stop(stops_index, segment["to_stop_id"])
    if any(
        pd.isna(waarde)
        for waarde in [
            from_stop["stop_lon"],
            from_stop["stop_lat"],
            to_stop["stop_lon"],
            to_stop["stop_lat"],
        ]
    ):
        return None, None

    punten = gpd.GeoSeries(
        [
            Point(float(from_stop["stop_lon"]), float(from_stop["stop_lat"])),
            Point(float(to_stop["stop_lon"]), float(to_stop["stop_lat"])),
        ],
        crs=CRS_WGS84,
    ).to_crs(CRS_RD)
    return LineString(
        [(punten.iloc[0].x, punten.iloc[0].y), (punten.iloc[1].x, punten.iloc[1].y)]
    ), "gtfs_stop_coords"


def maak_halte_edge_records(route_segment_summary, stops_processed):
    """Maak halte-edge records met RD-geometrie."""
    records = []
    stops_index = maak_stops_index(stops_processed)

    for _, segment in route_segment_summary.iterrows():
        geometry, geometry_source = halte_edge_geometrie(segment, stops_index)
        if geometry is None:
            continue

        records.append(
            {
                "edge_id": (
                    f"{segment['mode']}_{segment['line_id']}_"
                    f"{segment['direction_id']}_{segment['from_stop_id']}_"
                    f"{segment['to_stop_id']}"
                ),
                "mode": segment["mode"],
                "operator": segment["operator"],
                "route_id": segment["route_id"],
                "line_id": segment["line_id"],
                "direction_id": segment["direction_id"],
                "trip_headsign": segment["trip_headsign"],
                "from_stop_id": segment["from_stop_id"],
                "from_stop_name": segment["from_stop_name"],
                "from_halte_id": segment["from_halte_id"],
                "from_halte_naam": segment["from_halte_naam"],
                "from_halte_gemeente": segment["from_halte_gemeente"],
                "to_stop_id": segment["to_stop_id"],
                "to_stop_name": segment["to_stop_name"],
                "to_halte_id": segment["to_halte_id"],
                "to_halte_naam": segment["to_halte_naam"],
                "to_halte_gemeente": segment["to_halte_gemeente"],
                "aantal_trips": segment["aantal_trips"],
                "eerste_vertrek": segment["eerste_vertrek"],
                "laatste_vertrek": segment["laatste_vertrek"],
                "min_travel_time_min": segment["min_travel_time_min"],
                "travel_time_min": segment["travel_time_min"],
                "max_travel_time_min": segment["max_travel_time_min"],
                "travel_time_original_min": segment["travel_time_original_min"],
                "travel_time_correction_delta_min": (
                    segment["travel_time_correction_delta_min"]
                ),
                "travel_time_source": segment["travel_time_source"],
                "travel_time_correction_note": (
                    segment["travel_time_correction_note"]
                ),
                "geometry_source": geometry_source,
                "tooltip": (
                    f"Lijn {segment['line_id']}"
                    f"<br>{segment['from_stop_name']} -> {segment['to_stop_name']}"
                    f"<br>Reistijd mediaan: {segment['travel_time_min']} min"
                    f"<br>Aantal ritten: {segment['aantal_trips']}"
                ),
                "geometry": geometry,
            }
        )
    return records


def schrijf_halte_edges(route_segment_summary, stops_processed):
    """Schrijf halte-edge controlelagen."""
    records = maak_halte_edge_records(route_segment_summary, stops_processed)
    edges = gpd.GeoDataFrame(records, geometry="geometry", crs=CRS_RD)

    if edges.empty:
        schrijf_geojson(KAARTCONTROLE_DIR / "friesland_stop_edges.geojson", [])
        return edges

    edges.to_crs(CRS_WGS84).to_file(
        KAARTCONTROLE_DIR / "friesland_stop_edges.geojson",
        driver="GeoJSON",
    )
    edges.to_file(
        KAARTCONTROLE_DIR / "friesland_stop_edges.gpkg",
        layer="friesland_stop_edges",
        driver="GPKG",
    )
    return edges


def schrijf_kaartlagen(
    line_total_summary,
    trip_total_summary,
    route_segment_summary,
    stops_processed,
    trips_processed,
    shapes,
    lijnen_frl,
):
    """Schrijf GeoJSON/GPKG-kaartlagen en geef aantallen terug."""
    shape_lijnen = maak_shape_lijnen(shapes, line_total_summary, trip_total_summary)

    line_total_features = maak_lijnverbinding_features(
        line_total_summary,
        shape_lijnen,
        lijnen_frl,
    )
    schrijf_geojson(LAGEN_DIR / "line_total_travel_times.geojson", line_total_features)
    print("Stap 12 klaar: exacte lijnverbinding GeoJSON gemaakt")
    print("Line connection GeoJSON features:", len(line_total_features))

    trip_total_route_features = maak_ritroute_features(
        trip_total_summary,
        shape_lijnen,
    )
    schrijf_geojson(
        KAARTCONTROLE_DIR / "trip_total_routes.geojson",
        trip_total_route_features,
    )
    print("Stap 13 klaar: totale GTFS-ritten GeoJSON gemaakt")
    print("Trip total route GeoJSON features:", len(trip_total_route_features))

    stop_point_features = maak_haltepunt_features(line_total_summary)
    stop_points_geojson = schrijf_geojson(
        LAGEN_DIR / "line_total_stop_points.geojson",
        stop_point_features,
    )
    print("Stap 14 klaar: haltepunten GeoJSON gemaakt")
    print("Haltepunten GeoJSON features:", len(stop_point_features))

    shape_features = maak_shape_features(shape_lijnen, trips_processed)
    schrijf_geojson(KAARTCONTROLE_DIR / "shapes_routes.geojson", shape_features)
    print("Stap 15 klaar: shapes verwerkt")
    print("Shape features:", len(shape_features))

    tooltip_features = maak_segment_tooltip_features(
        route_segment_summary,
        stops_processed,
    )
    schrijf_geojson(KAARTCONTROLE_DIR / "segment_tooltip.geojson", tooltip_features)
    print("Stap 16 klaar: segment-tooltip GeoJSON gemaakt")
    print("Tooltip segmenten:", len(tooltip_features))

    friesland_stop_edges = schrijf_halte_edges(
        route_segment_summary,
        stops_processed,
    )
    print("Stap 17 klaar: halte-edge GeoJSON/GPKG gemaakt")
    print("Friese halte-edges:", len(friesland_stop_edges))

    return {
        "line_total_features": line_total_features,
        "trip_total_route_features": trip_total_route_features,
        "stop_points_geojson": stop_points_geojson,
        "shape_features": shape_features,
        "tooltip_features": tooltip_features,
        "friesland_stop_edges": friesland_stop_edges,
    }
