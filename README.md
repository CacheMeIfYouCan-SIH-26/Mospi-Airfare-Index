# 🇮🇳 BHARAT AIR-CPI: Automated Airfare Inflation Index

An automated data pipeline and dashboard built for the Ministry of Statistics and Programme Implementation (MoSPI) and Reserve Bank of India (RBI) scope (SIH-26 Hackathon, PS ID: 26056). 

It tracks real-time domestic airfares, separates pure base fares from taxes/fees, filters out abnormal price spikes, and presents national inflation trends on an interactive dashboard.

---

## How the Project Works

Tracking airfare inflation requires clean, unbundled price data collected regularly across key flight corridors. Think of this repository as a factory assembly line:

$$\text{Collect Data} \longrightarrow \text{Check Data} \longrightarrow \text{Clean \& Unbundle} \longrightarrow \text{Detect Price Spikes} \longrightarrow \text{Save Output} \longrightarrow \text{Display Dashboard}$$

1. **Collect**: An automated browser silently scrapes live flight quotes across 5 key Indian routes (`DEL-BOM`, `BLR-DEL`, `BOM-MAA`, `DEL-CCU`, `HYD-BOM`) for 5 advance booking windows (`T+1` to `T+5` days out).
2. **Check & Clean**: Raw data is checked for errors, bad records are set aside, and total prices are unbundled into pure **Base Fare** (~78%), **Taxes/UDF** (~17%), and **Convenience Fees** (~5%).
3. **Detect Outliers**: Statistical rules flag abnormal price spikes and dips without throwing away valid historical data.
4. **Display**: A user-friendly government dashboard presents real-time price trends, inflation index scores, and route comparisons.

---

## Simple Data Flow

```text
┌───────────────────────┐
│ Playwright Web Scraper│  (Role 1: Collects raw flight quotes)
└───────────┬───────────┘
            │ Generates raw files (.jsonl)
            ▼
┌───────────────────────┐
│ Data Cleaning Engine  │  (Role 2: Validates, unbundles fares, flags outliers)
└───────────┬───────────┘
            │ Saves clean, compressed output (.parquet)
            ▼
┌───────────────────────┐
│  Streamlit Dashboard  │  (Role 4: Displays inflation KPIs & charts)
└───────────────────────┘


.
├── src/
│   ├── ingestion/     # Role 1: Web scraping scripts
│   ├── engineering/   # Role 2: Cleaning, unbundling, and outlier filtering
│   └── frontend/      # Role 4: Streamlit web dashboard (app.py)
├── seed_data/         # Shared folder where data artifacts are stored
│   ├── staging_raw_payloads.jsonl      <-- Raw scraped input
│   ├── quarantine_raw_payloads.jsonl   <-- Bad/corrupted data set aside
│   └── clean_airfare_index.parquet     <-- Final clean dataset for dashboard
├── tests/             # Automated test suite
├── run_pipeline.py    # Master pipeline orchestrator script
├── Dockerfile         # Container setup file for deployment
└── requirements.txt   # Python library requirements