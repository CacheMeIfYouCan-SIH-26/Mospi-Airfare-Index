import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

ROUTES = [
    {"route_code": "DEL-BOM", "origin": "DEL", "destination": "BOM", "base_price": 5200.0},
    {"route_code": "BLR-DEL", "origin": "BLR", "destination": "DEL", "base_price": 4900.0},
    {"route_code": "BOM-MAA", "origin": "BOM", "destination": "MAA", "base_price": 3800.0},
    {"route_code": "DEL-CCU", "origin": "DEL", "destination": "CCU", "base_price": 4200.0},
    {"route_code": "HYD-BOM", "origin": "HYD", "destination": "BOM", "base_price": 3600.0},
]

ADVANCE_WINDOWS = [
    {"label": "T+1", "days": 1},
    {"label": "T+2", "days": 2},
    {"label": "T+3", "days": 3},
    {"label": "T+4", "days": 4},
    {"label": "T+5", "days": 5},
]


def generate_query_matrix() -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    query_matrix: List[Dict[str, Any]] = []

    for route in ROUTES:
        for window in ADVANCE_WINDOWS:
            dep_date = (today + timedelta(days=window["days"])).strftime("%Y-%m-%d")
            query_matrix.append({
                "route_code": route["route_code"],
                "origin": route["origin"],
                "destination": route["destination"],
                "advance_window": window["label"],
                "departure_date": dep_date,
                "base_price": route["base_price"],
            })

    return query_matrix


def generate_custom_date_matrix(
    origin: str,
    destination: str,
    start_date_str: str,
    end_date_str: str,
    base_price: float = 5000.0,
) -> List[Dict[str, Any]]:
    """Generates query tasks for every day in a targeted departure date range for a specific route corridor."""
    route_code = f"{origin.upper()}-{destination.upper()}"
    
    # Preserve original route baseline price if available
    for route in ROUTES:
        if route["route_code"] == route_code or (
            route["origin"] == origin.upper() and route["destination"] == destination.upper()
        ):
            base_price = route["base_price"]
            break

    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()

    custom_matrix: List[Dict[str, Any]] = []
    curr = start_dt

    while curr <= end_dt:
        if curr >= today:  # Only target present and future departure dates
            advance_days = (curr - today).days
            window_label = f"T+{advance_days}" if advance_days > 0 else "T+0"
            custom_matrix.append({
                "route_code": route_code,
                "origin": origin.upper(),
                "destination": destination.upper(),
                "advance_window": window_label,
                "departure_date": curr.strftime("%Y-%m-%d"),
                "base_price": base_price,
            })
        curr += timedelta(days=1)

    return custom_matrix


if __name__ == "__main__":
    matrix = generate_query_matrix()
    print(f"[OK] Generated {len(matrix)} tasks across {len(ROUTES)} routes.")