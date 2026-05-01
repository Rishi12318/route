"""
Fuel station data loader and route-corridor filter.
"""
import os
import csv
import logging
import math
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

CLEANED_CSV_FILENAME = "cleaned_fuel_prices.csv"
DEFAULT_CORRIDOR_KM = 40.0  # stations within this distance of any waypoint


def _find_cleaned_csv() -> str:
    """Search common relative locations for the cleaned fuel CSV."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", CLEANED_CSV_FILENAME),
        os.path.join(os.path.dirname(__file__), "..", "auxiliary_system",
                     "data_preprocessing", CLEANED_CSV_FILENAME),
        os.path.join(os.path.dirname(__file__), "..", CLEANED_CSV_FILENAME),
        CLEANED_CSV_FILENAME,
    ]
    for path in candidates:
        resolved = os.path.normpath(path)
        if os.path.isfile(resolved):
            logger.info("Found cleaned CSV at: %s", resolved)
            return resolved
    raise FileNotFoundError(
        f"Cannot find '{CLEANED_CSV_FILENAME}'. Run the preprocessor first."
    )


def load_fuel_data(csv_path: str = None) -> List[Dict[str, float]]:
    """
    Load lat/lng/price records from the cleaned fuel prices CSV.
    Raises FileNotFoundError if the CSV cannot be located.
    """
    path = csv_path or _find_cleaned_csv()
    stations: List[Dict[str, float]] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                station = {
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "price": float(row["price"]),
                }
                # Add optional metadata fields if they exist
                for key in ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID"]:
                    if key in row:
                        station[key] = row[key]
                stations.append(station)
            except (KeyError, ValueError):
                continue
    logger.info("Loaded %d stations from %s", len(stations), path)
    return stations


def _point_to_segment_distance_km(
    px: float, py: float,
    ax: float, ay: float,
    bx: float, by: float,
) -> float:
    """Euclidean distance (degrees) from point P to segment AB, scaled to km."""
    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        dist_deg = math.hypot(px - ax, py - ay)
    else:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
        dist_deg = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
    return dist_deg * 111.0   # 1° ≈ 111 km (approximate)


def filter_stations(
    waypoints: List[Tuple[float, float]],
    stations: List[Dict[str, float]],
    corridor_km: float = DEFAULT_CORRIDOR_KM,
) -> List[Dict[str, float]]:
    """
    Return stations within corridor_km of any route segment.
    """
    if len(waypoints) < 2:
        return stations

    result: List[Dict[str, float]] = []
    for station in stations:
        slat, slng = station["lat"], station["lng"]
        in_corridor = False
        for i in range(len(waypoints) - 1):
            a_lat, a_lng = waypoints[i]
            b_lat, b_lng = waypoints[i + 1]
            dist_km = _point_to_segment_distance_km(
                slng, slat, a_lng, a_lat, b_lng, b_lat
            )
            if dist_km <= corridor_km:
                in_corridor = True
                break
        if in_corridor:
            result.append(station)

    logger.info("Filtered to %d corridor stations (%.0f km width)", len(result), corridor_km)
    return result