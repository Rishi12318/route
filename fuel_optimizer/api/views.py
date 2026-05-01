"""
API views for the Intelligent Fuel Route Optimization API.
Endpoint: POST /api/plan-route/
"""
import logging
from typing import Any, Dict

from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .services.routing import get_route, extract_route_data, haversine_distance
from .services.data import load_fuel_data, filter_stations
from .services.fuel_optimizer import assign_distances, optimize_fuel
from .auxiliary_system.data_preprocessing.us_cities_geocode import lookup as city_lookup

logger = logging.getLogger(__name__)
KM_PER_MILE = 1.60934


def _validate_coord(data: Dict[str, Any], key: str, lo: float, hi: float) -> float:
    if key not in data:
        raise ValueError(f"Missing required field: '{key}'")
    try:
        value = float(data[key])
    except (TypeError, ValueError):
        raise ValueError(f"Field '{key}' must be numeric, got: {data[key]!r}")
    if not (lo <= value <= hi):
        raise ValueError(f"Field '{key}' = {value} out of range [{lo}, {hi}]")
    return value


def index(request):
    """Serve the integrated map UI."""
    return render(request, "api/index.html")


@api_view(["POST"])
def plan_route(request: Request) -> Response:
    """
    POST /api/plan-route/

    Body: { start_lat, start_lng, end_lat, end_lng }

    Response:
        distance_km      – total driving distance
        duration_minutes – estimated travel time
        fuel_cost_usd    – total optimised fuel spend
        refuel_stops     – [{lat, lng, price}, ...]
        route_geometry   – GeoJSON LineString of the actual road route
    """
    data = request.data
    # Check for text-based location inputs first
    if "start_location" in data and "end_location" in data:
        try:
            start_parts = [p.strip() for p in data["start_location"].split(",")]
            end_parts = [p.strip() for p in data["end_location"].split(",")]
            
            start_coords = city_lookup(start_parts[0], start_parts[1] if len(start_parts) > 1 else "")
            end_coords = city_lookup(end_parts[0], end_parts[1] if len(end_parts) > 1 else "")
            
            if not start_coords: raise ValueError(f"Could not find start city: {data['start_location']}")
            if not end_coords: raise ValueError(f"Could not find end city: {data['end_location']}")
            
            start_lat, start_lng = start_coords
            end_lat, end_lng = end_coords
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    else:
        # Fall back to explicit coordinates
        try:
            start_lat = _validate_coord(data, "start_lat", -90.0,  90.0)
            start_lng = _validate_coord(data, "start_lng", -180.0, 180.0)
            end_lat   = _validate_coord(data, "end_lat",   -90.0,  90.0)
            end_lng   = _validate_coord(data, "end_lng",   -180.0, 180.0)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    # ── 1. Get route from OSRM (single API call) ─────────────────────────
    try:
        route_json = get_route(
            {"lat": start_lat, "lng": start_lng},
            {"lat": end_lat,   "lng": end_lng},
        )
        waypoints, distance_m, duration_s = extract_route_data(route_json)
    except Exception as exc:
        logger.exception("Route computation failed")
        return Response(
            {"error": f"Route computation error: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    distance_km    = distance_m / 1000.0
    distance_miles = distance_km / KM_PER_MILE
    duration_min   = round(duration_s / 60.0, 1)

    # ── 2. Load & filter fuel stations ───────────────────────────────────
    try:
        all_stations = load_fuel_data()
    except FileNotFoundError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as exc:
        logger.exception("Failed to load fuel data")
        return Response(
            {"error": f"Data loading error: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    corridor_stations = filter_stations(waypoints, all_stations)
    sorted_stations   = assign_distances(corridor_stations, start_lat, start_lng)

    # ── 3. Optimise fuel purchases ────────────────────────────────────────
    fuel_cost_usd, refuel_stops = optimize_fuel(sorted_stations, distance_miles)

    return Response({
        "distance_km":      round(distance_km, 2),
        "duration_minutes": duration_min,
        "fuel_cost_usd":    fuel_cost_usd,
        "refuel_stops":     refuel_stops,
        "route_geometry":   route_json.get("geometry"),
        "resolved_start":   {"lat": start_lat, "lng": start_lng},
        "resolved_end":     {"lat": end_lat, "lng": end_lng},
    }, status=status.HTTP_200_OK)