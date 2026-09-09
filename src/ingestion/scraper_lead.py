import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import quote

from playwright.async_api import Response, async_playwright

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.ingestion.matrix_generator import generate_query_matrix
from src.ingestion.stealth_browser import create_stealth_context

OUTPUT_STAGING_FILE = "seed_data/staging_raw_payloads.jsonl"
MAX_BODY_BYTES = 512 * 1024

OFFER_URL_MARKERS = ("flight_search", "batch_execute", "/flights", "grpc", "loadparameters")
OFFER_BODY_KEYWORDS = (b"fare", b"price", b"offering", b"totalprice", b"perperson", b"amount")


def build_search_url(task: dict) -> str:
    query = (
        f"Flights to {task['destination']} "
        f"from {task['origin']} on {task['departure_date']}"
    )
    encoded = quote(query)
    return f"https://www.google.com/travel/flights?q={encoded}"


def _is_offer_response(url: str, content_type: str, body: bytes) -> bool:
    lowered_url = url.lower()
    header_hit = "json" in content_type or "grpc" in content_type or "protobuf" in content_type
    url_hit = any(marker in lowered_url for marker in OFFER_URL_MARKERS)
    body_hit = any(keyword in body.lower()[:65536] for keyword in OFFER_BODY_KEYWORDS)
    return (url_hit and (header_hit or body_hit)) or (header_hit and body_hit)


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
        "raw_payload": _decode_payload(body, content_type),
    }

    os.makedirs(os.path.dirname(OUTPUT_STAGING_FILE), exist_ok=True)
    with open(OUTPUT_STAGING_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(staging_record) + "\n")
    print(f"[OK] Captured {response.url} ({query_task['advance_window']} | {query_task['departure_date']})")


async def run_data_ingestion_pipeline() -> None:
    query_matrix = generate_query_matrix()
    print(f"[INFO] Starting live flight interception for {len(query_matrix)} matrix tasks (WAIT_FOR 'networkidle').")

    async with async_playwright() as p:
        browser, context = await create_stealth_context(p, headless=True)
        page = await context.new_page()

        for index, task in enumerate(query_matrix, start=1):
            url = build_search_url(task)

            def make_handler(task_ref=task):
                def handler(response: Response) -> None:
                    asyncio.create_task(handle_network_interception(response, task_ref))

                return handler

            handler = make_handler()
            page.on("response", handler)
            print(f"[INFO] [{index}/{len(query_matrix)}] Navigate {task['route_code']} "
                  f"{task['advance_window']} | {task['departure_date']} -> {url}")
            try:
                await page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception as err:
                print(f"[ERR] {task['advance_window']} | {task['departure_date']}: {err}")
            finally:
                page.remove_listener("response", handler)

        await browser.close()
    print(f"[OK] Ingestion pass complete. Records appended to '{OUTPUT_STAGING_FILE}'")


if __name__ == "__main__":
    asyncio.run(run_data_ingestion_pipeline())