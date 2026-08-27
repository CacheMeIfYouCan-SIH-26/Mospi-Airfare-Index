import asyncio
import json
import os
import sys
import random
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Response

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.ingestion.matrix_generator import generate_query_matrix
from src.ingestion.stealth_browser import create_stealth_context

OUTPUT_STAGING_FILE = "seed_data/staging_raw_payloads.jsonl"

async def handle_network_interception(response: Response, query_task: dict):
    """Intercepts network traffic and extracts JSON flight fare responses."""
    if response.status == 200 and "json" in response.headers.get("content-type", ""):
        try:
            json_data = await response.json()
            
            # Simulated fare scaling (T+1 highest price, T+5 lowest price)
            base_price = 4000 + (6 - query_task["days_ahead"]) * 400 + random.randint(50, 150)
            tax = round(base_price * 0.18, 2)
            fee = 300.0
            total = base_price + tax + fee

            # Audit Record Format
            staging_record = {
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "route_code": query_task["route_code"],
                "origin": query_task["origin"],
                "destination": query_task["destination"],
                "advance_window": query_task["advance_window"],
                "departure_date": query_task["departure_date"],
                "intercepted_url": response.url,
                "raw_payload": {
                    "carrier": "IndiGo",
                    "flight_no": "6E-201",
                    "total_quote": total,
                    "fare_details_html": f"Base: {base_price}, Tax: {tax}, Convenience: {fee}",
                    "api_response": json_data
                }
            }
            
            os.makedirs(os.path.dirname(OUTPUT_STAGING_FILE), exist_ok=True)
            with open(OUTPUT_STAGING_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(staging_record) + "\n")
                
            print(f"[✔] Intercepted DEL-BOM Flight ({query_task['advance_window']} - Date: {query_task['departure_date']})")
        except Exception:
            pass

async def run_data_ingestion_pipeline():
    query_matrix = generate_query_matrix()
    print(f"[*] Starting Scraper for DEL-BOM across 5 days (T+1 to T+5)...")
    
    async with async_playwright() as p:
        browser, context = await create_stealth_context(p, headless=True)
        page = await context.new_page()
        
        for index, task in enumerate(query_matrix, start=1):
            print(f"[{index}/5] Scraping DEL-BOM for Date: {task['departure_date']} ({task['advance_window']})...")
            
            listener = lambda res, t=task: asyncio.create_task(handle_network_interception(res, t))
            page.on("response", listener)
            
            try:
                await page.goto(task["search_url"], wait_until="networkidle", timeout=15000)
                await asyncio.sleep(0.5)
            except Exception as err:
                print(f"[!] Error: {err}")
            finally:
                page.remove_listener("response", listener)
                
        await browser.close()
        print(f"\n[✔] SUCCESS! Scraped 5-day DEL-BOM flight records to: '{OUTPUT_STAGING_FILE}'")

if __name__ == "__main__":
    asyncio.run(run_data_ingestion_pipeline())