from datetime import datetime, timedelta
from typing import List, Dict, Any

# Target Route Configuration
ROUTES = [
    {"origin": "DEL", "destination": "BOM"}
]

# 10-Day Booking Horizon (T+1 to T+10)
ADVANCE_WINDOWS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def generate_query_matrix() -> List[Dict[str, Any]]:
    """Generates parameterized query targets for flight searches."""
    matrix = []
    today = datetime.now()
    
    for route in ROUTES:
        for window in ADVANCE_WINDOWS:
            target_date = (today + timedelta(days=window)).strftime("%Y-%m-%d")
            
            task = {
                "route_code": f"{route['origin']}-{route['destination']}",
                "origin": route["origin"],
                "destination": route["destination"],
                "advance_window": f"T+{window}",
                "days_ahead": window,
                "departure_date": target_date,
                # Dynamic target URL endpoint template
                "search_url": f"https://httpbin.org/get?origin={route['origin']}&dest={route['destination']}&date={target_date}"
            }
            matrix.append(task)
            
    return matrix

if __name__ == "__main__":
    queries = generate_query_matrix()
    print(f"[✔] Generated {len(queries)} matrix tasks for DEL-BOM (T+1 to T+5).")