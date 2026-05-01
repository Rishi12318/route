"""
Routing via OSRM (Open Source Routing Machine).

Uses the free public OSRM API — completely free, no API key required,
backed by OpenStreetMap data.  Makes exactly ONE HTTP call per request.

Public endpoint: http://router.project-osrm.org
"""
import math
import logging
import requests
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
REQUEST_TIMEOUT = 10          # seconds
AVG_SPEED_KMH   = 100.0       # fallback when OSRM duration unavailable
EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres (used as fallback)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def get_route(start: Dict[str, float], end: Dict[str, float]) -> Dict:
    """
    Call OSRM once to retrieve driving route between two coordinate pairs.

    Returns a normalised dict with keys:
        distance_m   – total route distance in metres
        duration_s   – estimated driving time in seconds
        geometry     – GeoJSON LineString (coordinates as [lng, lat] pairs)
        waypoints    – list of (lat, lng) tuples spaced along the route
    """
    lat1, lng1 = float(start["lat"]), float(start["lng"])
    lat2, lng2 = float(end["lat"]), float(end["lng"])

    url = f"{OSRM_BASE}/{lng1},{lat1};{lng2},{lat2}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError(f"OSRM returned code={data.get('code')}")

        route      = data["routes"][0]
        distance_m = route["distance"]          # metres
        duration_s = route["duration"]          # seconds
        geometry   = route["geometry"]          # GeoJSON LineString

        # Build (lat, lng) waypoints from GeoJSON coordinates
        coords = geometry.get("coordinates", [])
        waypoints: List[Tuple[float, float]] = [(c[1], c[0]) for c in coords]

        logger.info(
            "OSRM route: %.1f km, %.0f min, %d waypoints",
            distance_m / 1000, duration_s / 60, len(waypoints),
        )
        return {
            "distance_m": distance_m,
            "duration_s": duration_s,
            "geometry":   geometry,
            "waypoints":  waypoints,
        }

    except requests.exceptions.Timeout:
        logger.warning("OSRM timeout — falling back to Haversine straight line")
    except Exception as exc:
        logger.warning("OSRM error (%s) — falling back to Haversine straight line", exc)

    # ── Haversine fallback (straight-line) ──────────────────────────────
    dist_km = haversine_distance(lat1, lng1, lat2, lng2)
    n = max(2, int(dist_km / 16))
    waypoints = [
        (lat1 + i / n * (lat2 - lat1), lng1 + i / n * (lng2 - lng1))
        for i in range(n + 1)
    ]
    fallback_geometry = {
        "type": "LineString",
        "coordinates": [[lng, lat] for lat, lng in waypoints],
    }
    return {
        "distance_m": dist_km * 1000,
        "duration_s": dist_km / AVG_SPEED_KMH * 3600,
        "geometry":   fallback_geometry,
        "waypoints":  waypoints,
    }


def extract_route_data(
    route_json: Dict,
) -> Tuple[List[Tuple[float, float]], float, float]:
    """Unpack route dict → (waypoints, distance_m, duration_s)."""
    return (
        route_json["waypoints"],
        route_json["distance_m"],
        route_json["duration_s"],
    )