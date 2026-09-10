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


if __name__ == "__main__":
    matrix = generate_query_matrix()
    print(f"[OK] Generated {len(matrix)} tasks across {len(ROUTES)} routes.")