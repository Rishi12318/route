"""
Look-ahead greedy fuel optimization algorithm.

Given a sorted list of fuel stations along a route (each with a cumulative
`distance_miles` key), decide at each station how much fuel to purchase so
that the total spend is minimised subject to:
  - Vehicle range: 500 miles per full tank
  - Fuel efficiency: 10 mpg (constant)
"""
import logging
import math
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

MAX_RANGE_MILES = 500.0
MPG = 10.0
TANK_CAPACITY_GAL = MAX_RANGE_MILES / MPG   # 50 gallons


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in miles."""
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def assign_distances(
    stations: List[Dict[str, float]],
    start_lat: float,
    start_lng: float,
) -> List[Dict[str, float]]:
    """
    Compute cumulative route distance (miles) from start to each station
    using Haversine, then sort by that distance.
    """
    for s in stations:
        s["distance_miles"] = _haversine_miles(start_lat, start_lng, s["lat"], s["lng"])
    return sorted(stations, key=lambda x: x["distance_miles"])


def optimize_fuel(
    stations: List[Dict[str, float]],
    total_distance_miles: float,
) -> Tuple[float, List[Dict[str, float]]]:
    """
    Look-ahead greedy algorithm.

    Strategy: at each station, check if there is a cheaper station reachable
    within MAX_RANGE_MILES. If yes, buy only enough fuel to reach that cheaper
    station. Otherwise, fill the tank completely.

    Returns:
        total_cost: total USD spent on fuel
        refuel_stops: list of stations where fuel was purchased
    """
    if not stations:
        gallons_needed = total_distance_miles / MPG
        logger.warning("No corridor stations — estimating average price $3.50/gal")
        return round(gallons_needed * 3.50, 2), []

    # Include a synthetic "destination" node so the algorithm always terminates
    dest_node = {
        "lat": stations[-1]["lat"],
        "lng": stations[-1]["lng"],
        "price": 0.0,
        "distance_miles": total_distance_miles,
        "synthetic": True,
    }
    all_nodes = stations + [dest_node]

    fuel_in_tank = 0.0   # start empty — fill at first station
    total_cost = 0.0
    refuel_stops: List[Dict[str, float]] = []
    current_pos_miles = 0.0

    for i, station in enumerate(all_nodes[:-1]):
        dist_to_station = station["distance_miles"] - current_pos_miles
        if dist_to_station < 0:
            continue

        # Burn fuel to reach this station
        fuel_in_tank -= dist_to_station / MPG
        fuel_in_tank = max(0.0, fuel_in_tank)
        current_pos_miles = station["distance_miles"]

        if station.get("synthetic"):
            break

        # Look ahead: find cheapest reachable station within MAX_RANGE_MILES
        reachable = [
            s for s in all_nodes[i + 1:]
            if s["distance_miles"] - current_pos_miles <= MAX_RANGE_MILES
        ]

        # Find first cheaper station ahead
        cheaper_ahead = next(
            (s for s in reachable if s["price"] < station["price"]), None
        )

        if cheaper_ahead:
            # Buy just enough to reach the cheaper station
            miles_to_cheaper = cheaper_ahead["distance_miles"] - current_pos_miles
            fuel_to_buy = max(0.0, miles_to_cheaper / MPG - fuel_in_tank)
            target_label = "cheaper station ahead"
        else:
            # No cheaper option — fill tank completely
            fuel_to_buy = max(0.0, TANK_CAPACITY_GAL - fuel_in_tank)
            target_label = "fill tank"

        if fuel_to_buy > 0:
            cost = fuel_to_buy * station["price"]
            total_cost += cost
            fuel_in_tank += fuel_to_buy
            logger.debug(
                "Buy %.2f gal @ $%.3f at (%.4f, %.4f) [%s] — cumulative $%.2f",
                fuel_to_buy, station["price"], station["lat"], station["lng"],
                target_label, total_cost,
            )
            stop_info = {
                "lat": round(station["lat"], 6),
                "lng": round(station["lng"], 6),
                "price": round(station["price"], 2),
            }
            for key in ["OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Rack ID"]:
                if key in station:
                    stop_info[key] = station[key]
            refuel_stops.append(stop_info)

    return round(total_cost, 2), refuel_stops