from datetime import datetime, timedelta
from typing import List, Dict, Any
from urllib.parse import quote
ROUTES = [
    {"route_code": "DEL-BOM", "origin": "DEL", "destination": "BOM"},
    {"route_code": "BLR-DEL", "origin": "BLR", "destination": "DEL"},
    {"route_code": "BOM-MAA", "origin": "BOM", "destination": "MAA"},
    {"route_code": "DEL-CCU", "origin": "DEL", "destination": "CCU"},
    {"route_code": "HYD-BOM", "origin": "HYD", "destination": "BOM"},
]

# Set lead time window from 1 day ahead up to 10 days ahead (T+1 to T+10)
ADVANCE_WINDOWS = list(range(1, 11))

def build_flight_search_url(origin: str, destination: str, departure_date: str) -> str:
    query = f"Flights to {destination} from {origin} on {departure_date}"
    return f"https://www.google.com/travel/flights?q={quote(query)}"

def generate_query_matrix() -> List[Dict[str, Any]]:
    matrix = []
    today = datetime.now()

    for route in ROUTES:
        for window in ADVANCE_WINDOWS:
            # Target date represents flight departure date (up to 10 days in the future)
            target_date = (today + timedelta(days=window)).strftime("%Y-%m-%d")

            task = {
                "route_code": f"{route['origin']}-{route['destination']}",
                "origin": route["origin"],
                "destination": route["destination"],
                "advance_window": f"T+{window}",
                "days_ahead": window,
                "departure_date": target_date,
                "search_url": build_flight_search_url(route["origin"], route["destination"], target_date)
            }
            matrix.append(task)

    return matrix

if __name__ == "__main__":
    queries = generate_query_matrix()
    print(f"[OK] Generated {len(queries)} matrix tasks for DEL-BOM (T+1 to T+10).")