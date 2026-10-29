"""Geographic utility functions."""
from __future__ import annotations

import math
from typing import Tuple

EARTH_RADIUS_METERS = 6_371_008.8  # WGS-84 mean radius


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 coordinates.

    This is a straight-line distance over the Earth's surface — NOT a pedestrian
    route distance. Do not present this value as a walking path length.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def estimated_walk_seconds(distance_meters: float, walk_speed_mps: float = 1.2) -> int:
    """Estimate walking time in seconds from straight-line distance.

    Uses a configurable walking speed (default 1.2 m/s ≈ 4.3 km/h).
    This is an approximation; actual pedestrian paths will be longer.
    """
    return int(math.ceil(distance_meters / walk_speed_mps))


def bbox_for_radius(lat: float, lon: float, radius_meters: float) -> Tuple[float, float, float, float]:
    """Return a bounding box (min_lat, min_lon, max_lat, max_lon) that encloses
    a circle of *radius_meters* centred at (lat, lon).

    Useful for fast pre-filtering before precise Haversine calculation.
    """
    lat_rad = math.radians(lat)
    delta_lat = math.degrees(radius_meters / EARTH_RADIUS_METERS)
    delta_lon = math.degrees(radius_meters / (EARTH_RADIUS_METERS * math.cos(lat_rad)))
    return (lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def is_valid_delhi_ncr_coord(lat: float, lon: float) -> bool:
    """Rough bounding box check for Delhi/NCR region.

    Used during GTFS validation to flag stops that fall outside the expected area.
    Does not guarantee a stop is reachable — only that its coordinates are plausible.
    """
    return (27.8 <= lat <= 29.0) and (76.5 <= lon <= 77.9)

