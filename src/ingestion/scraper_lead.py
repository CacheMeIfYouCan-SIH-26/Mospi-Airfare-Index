=import argparse
import asyncio
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import quote

from playwright.async_api import Response, async_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.engineering.fare_unbundler import unbundle_fare
from src.ingestion.matrix_generator import generate_query_matrix
from src.ingestion.stealth_browser import create_stealth_context

OUTPUT_STAGING_FILE = "seed_data/staging_raw_payloads.jsonl"
MAX_BODY_BYTES = 512 * 1024

OFFER_URL_MARKERS = ("flight_search", "batch_execute", "/flights", "grpc", "loadparameters")
OFFER_BODY_KEYWORDS = (b"fare", b"price", b"offering", b"totalprice", b"perperson", b"amount")

DETAIL_URL_MARKERS = ("detail", "itinerary", "shoppingresults", "fare", "baggage", "pricebreak")
DETAIL_BODY_KEYWORDS = (b"baggage", b"seat", b"cabin", b"farebreakdown", b"totalprice", b"carrier")

_SEAT_VOCAB = (
    "ultra", "basic", "saver", "standard", "comfort", "flex", "value",
    "premium economy", "economy", "business", "first",
)
_PRICE_PAT = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_BAGGAGE_PAT = re.compile(r"(\d{1,2})\s*(?:kg|kilo|kgs)", re.IGNORECASE)
_TIME_PAT = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_FLIGHT_NUM_RE = re.compile(r"([A-Z0-9]{1,3})\s*[-]?\s*(\d{2,4})\b", re.IGNORECASE)

_AIRPORT_NAMES = {
    "DEL": "New Delhi", "BOM": "Mumbai", "BLR": "Bengaluru",
    "HYD": "Hyderabad", "CCU": "Kolkata", "MAA": "Chennai",
}

_SEAT_ALT = "|".join(re.escape(v) for v in _SEAT_VOCAB)
_ROW_TOKEN_RE = re.compile(
    rf"({_SEAT_ALT})|(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)",
    re.IGNORECASE,
)

_CARRIER_NAMES = {
    "6E": "IndiGo", "AI": "Air India", "IX": "Air India Express", "SG": "SpiceJet",
    "QP": "Akasa Air", "UK": "Vistara", "9W": "Jet Airways", "I5": "Air India Regional",
}


@dataclass
class FlightTarget:
    flight_number: str
    flight_id: Optional[str] = None
    carrier_code: Optional[str] = None


def build_search_url(task: dict) -> str:
    query = (
        f"Flights to {task['destination']} "
        f"from {task['origin']} on {task['departure_date']}"
    )
    encoded = quote(query)
    return f"https://www.google.com/travel/flights?q={encoded}"


def normalize_flight_number(raw: str) -> str:
    match = _FLIGHT_NUM_RE.match(raw.strip())
    if not match:
        return raw.strip().upper()
    return f"{match.group(1).upper()} {match.group(2)}"


def _flight_text_variants(flight_number: str) -> set:
    match = _FLIGHT_NUM_RE.fullmatch(flight_number)
    if not match:
        return {flight_number}
    carrier, number = match.group(1), match.group(2)
    return {
        f"{carrier} {number}", f"{carrier}{number}", f"{carrier}-{number}",
        f"{carrier} \u2022 {number}", f"{carrier}\u00a0{number}",
    }


def _parse_flight_details(flight_number: str) -> tuple:
    match = _FLIGHT_NUM_RE.match(flight_number)
    if match:
        return match.group(1).upper(), match.group(2)
    return flight_number, ""


def _is_offer_response(url: str, content_type: str, body: bytes) -> bool:
    lowered_url = url.lower()
    header_hit = "json" in content_type or "grpc" in content_type or "protobuf" in content_type
    url_hit = any(marker in lowered_url for marker in OFFER_URL_MARKERS)
    body_hit = any(keyword in body.lower()[:65536] for keyword in OFFER_BODY_KEYWORDS)
    return (url_hit and (header_hit or body_hit)) or (header_hit and body_hit)


def _extract_flight_number_from_text(text: str) -> str:
    for match in _FLIGHT_NUM_RE.finditer(text or ""):
        return f"{match.group(1).upper()} {match.group(2)}"
    return ""


def _carrier_search_terms(target: "FlightTarget") -> list:
    code = target.carrier_code or _parse_flight_details(target.flight_number)[0]
    terms = [_CARRIER_NAMES[code]] if code in _CARRIER_NAMES else []
    if code:
        terms.append(code)
    return terms


def _is_detail_response(url: str, content_type: str, body: bytes) -> bool:
    lowered_url = url.lower()
    url_hit = any(marker in lowered_url for marker in DETAIL_URL_MARKERS)
    body_hit = any(keyword in body.lower()[:65536] for keyword in DETAIL_BODY_KEYWORDS)
    header_hit = "json" in content_type or "grpc" in content_type or "protobuf" in content_type
    xhr_hit = "/data/" in lowered_url or "frontendui" in lowered_url or "batch_execute" in lowered_url
    return (url_hit and (header_hit or xhr_hit)) or body_hit


def _decode_payload(body: bytes, content_type: str) -> dict:
    try:
        return {
            "api_response_type": "json",
            "content_type": content_type,
            "body_length": len(body),
            "api_response": json.loads(body.decode("utf-8")),
        }
    except Exception:
        try:
            parsed = json.loads(body.decode("utf-8", errors="ignore"))
            return {"api_response_type": "json", "content_type": content_type,
                    "body_length": len(body), "api_response": parsed}
        except Exception:
            return {
                "api_response_type": "binary",
                "content_type": content_type,
                "body_length": len(body),
                "api_response": body.decode("utf-8", errors="replace")[:4096],
            }


def _extract_departure_time_from_text(text: str) -> str:
    match = _TIME_PAT.search(text or "")
    return f"{match.group(1)}:{match.group(2)}" if match else ""


def _parse_fare_breakdown(text: str) -> tuple:
    breakdown: List[Dict[str, Any]] = []
    lowest = None
    current_seat: Optional[str] = None
    for match in _ROW_TOKEN_RE.finditer(text or ""):
        if match.group(1):
            current_seat = match.group(1).title()
            continue
        if current_seat is None:
            continue
        price = float(match.group(2).replace(",", ""))
        wstart = max(0, match.start() - 120)
        window = (text or "")[wstart:match.start() + 160]
        price_in_window = match.start() - wstart
        best_kg = ""
        best_dist = 10 ** 9
        for bm in _BAGGAGE_PAT.finditer(window):
            dist = abs(bm.start() - price_in_window)
            if dist < best_dist:
                best_dist, best_kg = dist, f"{bm.group(1)}kg"
        unf = unbundle_fare(window, total_quote=price)
        breakdown.append({
            "seat_class": current_seat,
            "base_fare": unf.base_fare,
            "tax_udf": unf.tax_udf,
            "convenience_fee": unf.convenience_fee,
            "total_quote": unf.total_quote,
            "fare_details_html": window,
            "baggage_rule": best_kg,
        })
        lowest = price if lowest is None else min(lowest, price)
        current_seat = None
    if lowest is None:
        prices = _PRICE_PAT.findall(text or "")
        if prices:
            lowest = min(float(p.replace(",", "")) for p in prices)
    return breakdown, lowest


def _append_staging_record(record: dict) -> None:
    os.makedirs(os.path.dirname(OUTPUT_STAGING_FILE), exist_ok=True)
    if os.name == "nt" and os.path.exists(OUTPUT_STAGING_FILE):
        try:
            os.chmod(OUTPUT_STAGING_FILE, stat.S_IWRITE)
        except Exception:
            pass
    with open(OUTPUT_STAGING_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


async def handle_network_interception(response: Response, query_task: dict) -> None:
    try:
        body = await response.body()
    except Exception:
        return
    body = body[:MAX_BODY_BYTES]
    content_type = response.headers.get("content-type", "")
    if not _is_offer_response(response.url, content_type, body):
        return

    staging_record = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "route_code": query_task["route_code"],
        "origin": query_task["origin"],
        "destination": query_task["destination"],
        "advance_window": query_task["advance_window"],
        "departure_date": query_task["departure_date"],
        "intercepted_url": response.url,
        "scrape_type": "bulk_flight_summary",
        "raw_payload": _decode_payload(body, content_type),
    }
    _append_staging_record(staging_record)
    url_brief = response.url[:100]
    print(f"[OK] Captured {url_brief} ({query_task['advance_window']} | {query_task['departure_date']})")


async def _run_bulk_scrape(page, task: dict, index: int, total: int) -> None:
    url = build_search_url(task)

    def make_handler(task_ref=task):
        def handler(response: Response) -> None:
            asyncio.create_task(handle_network_interception(response, task_ref))

        return handler

    handler = make_handler()
    page.on("response", handler)
    print(f"[INFO] [{index}/{total}] Navigate {task['route_code']} "
          f"{task['advance_window']} | {task['departure_date']} -> {url}")
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception as err:
        print(f"[ERR] {task['advance_window']} | {task['departure_date']}: {err}")
    finally:
        page.remove_listener("response", handler)


async def _submit_search_form(page, task: dict) -> None:
    """Drives Google Flights' search form to force the results view."""
    origin_name = _AIRPORT_NAMES.get(task["origin"], task["origin"])
    dest_name = _AIRPORT_NAMES.get(task["destination"], task["destination"])

    for label, city in (("Where from?", origin_name), ("Where to?", dest_name)):
        try:
            field = page.get_by_label(label, exact=False).first
            await field.click(timeout=4000)
            await field.fill(city, timeout=4000)
            await field.press("ArrowDown")
            await field.press("Enter")
        except Exception as err:
            print(f"[INFO] airport select '{city}' skipped: {repr(err)[:100]}")

    try:
        departure = page.get_by_label("Departure", exact=True).first
        await departure.click(timeout=4000)
        await departure.fill(task["departure_date"], timeout=4000)
        await departure.press("Enter")
    except Exception as err:
        print(f"[INFO] departure date entry skipped: {repr(err)[:100]}")

    try:
        done = page.get_by_role("button", name=re.compile(r"^\s*done\s*$", re.IGNORECASE)).first
        await done.click(timeout=3000)
    except Exception:
        pass
    await page.keyboard.press("Enter")


async def _capture_flight_detail(response: Response, holder: dict) -> None:
    try:
        body = await response.body()
    except Exception:
        return
    body = body[:MAX_BODY_BYTES]
    content_type = response.headers.get("content-type", "")
    if not _is_detail_response(response.url, content_type, body):
        return
    holder["url"] = response.url
    holder["body"] = body
    print(f"[OK] Detail response captured: {response.url[:100]}")


async def _locate_and_click_flight(page, target: FlightTarget) -> bool:
    locators = []
    for variant in _flight_text_variants(target.flight_number):
        locators.append(page.get_by_text(variant, exact=False).first)
    for term in _carrier_search_terms(target):
        locators.append(page.get_by_text(term, exact=False).first)
    if target.flight_id:
        locators.append(page.locator(f"text={target.flight_id}").first)

    for loc in locators:
        try:
            await loc.wait_for(state="attached", timeout=3000)
            await loc.scroll_into_view_if_needed(timeout=3000)
            await loc.click(timeout=5000)
            return True
        except Exception:
            continue
    return False


async def _persist_single_flight_record(
    page, task: dict, target: FlightTarget, holder: dict
) -> None:
    try:
        body_text = await page.locator("body").inner_text(timeout=8000)
    except Exception:
        body_text = ""

    breakdown, lowest = _parse_fare_breakdown(body_text)
    departure_time = _extract_departure_time_from_text(body_text)
    actual_number = _extract_flight_number_from_text(body_text)
    flight_number = actual_number or target.flight_number
    carrier_code = target.carrier_code or _parse_flight_details(flight_number)[0]
    carrier_label = _CARRIER_NAMES.get(carrier_code, carrier_code)

    if holder["body"] is not None:
        raw_api = _decode_payload(holder["body"], "application/grpc")
    else:
        raw_api = {"api_response_type": "dom", "content_type": "dom",
                   "api_response": None, "body_length": 0}

    raw_payload = dict(raw_api)
    raw_payload.update({
        "scrape_type": "single_flight_detail",
        "flight_number": flight_number,
        "carrier": carrier_label,
        "departure_time": departure_time,
        "fare_breakdown": breakdown,
        "total_quote": lowest,
    })

    record = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "route_code": task["route_code"],
        "origin": task["origin"],
        "destination": task["destination"],
        "advance_window": task["advance_window"],
        "departure_date": task["departure_date"],
        "intercepted_url": holder["url"] or task.get("search_url", build_search_url(task)),
        "scrape_type": "single_flight_detail",
        "flight_number": flight_number,
        "carrier": carrier_label,
        "departure_time": departure_time,
        "raw_payload": raw_payload,
    }
    _append_staging_record(record)
    print(f"[OK] Appended single-flight detail record for {flight_number} "
          f"({task['advance_window']} | {task['departure_date']}) | quote={lowest}")


async def _run_targeted_scrape(page, task: dict, target: FlightTarget) -> None:
    holder = {"url": None, "body": None}

    def on_response(response: Response) -> None:
        asyncio.create_task(_capture_flight_detail(response, holder))

    page.on("response", on_response)
    search_url = task.get("search_url", build_search_url(task))
    try:
        await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
        await _submit_search_form(page, task)
        try:
            await page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass
        clicked = await _locate_and_click_flight(page, target)
        if not clicked:
            print(f"[ERR] Flight {target.flight_number} not found on {task['departure_date']}")
            return
        print(f"[INFO] Clicked {target.flight_number} flight card on {task['departure_date']}")
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        await asyncio.sleep(2.0)
        await _persist_single_flight_record(page, task, target, holder)
    except Exception as err:
        print(f"[ERR] {task['advance_window']} | {task['departure_date']}: {repr(err)[:200]}")
    finally:
        page.remove_listener("response", on_response)


async def run_data_ingestion_pipeline(target: Optional[FlightTarget] = None) -> None:
    query_matrix = generate_query_matrix()
    mode = f"TARGETED single-flight detail for {target.flight_number}" if target else "BULK summary"
    print(f"[INFO] Starting live flight interception ({mode}) across {len(query_matrix)} tasks.")

    async with async_playwright() as p:
        browser, context = await create_stealth_context(p, headless=True)
        page = await context.new_page()

        for index, task in enumerate(query_matrix, start=1):
            if target:
                await _run_targeted_scrape(page, task, target)
            else:
                await _run_bulk_scrape(page, task, index, len(query_matrix))

        await browser.close()
    print(f"[OK] Ingestion pass complete. Records appended to '{OUTPUT_STAGING_FILE}'")


def _parse_args(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scraper_lead",
        description="MOSPI Airfare Index scraper: bulk summary capture (default) or "
                    "targeted single-flight detail capture via flight card click.",
    )
    parser.add_argument(
        "--flight-number", dest="flight_number", default=None,
        help="Target flight (e.g. '6E 201') to locate, click, and capture its fare detail.",
    )
    parser.add_argument(
        "--flight-id", dest="flight_id", default=None,
        help="Optional Google Flights flight id used as a fallback locator.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    target = None
    if args.flight_number:
        carrier_code, _ = _parse_flight_details(args.flight_number)
        target = FlightTarget(
            flight_number=normalize_flight_number(args.flight_number),
            flight_id=args.flight_id,
            carrier_code=carrier_code or None,
        )
    asyncio.run(run_data_ingestion_pipeline(target=target))
