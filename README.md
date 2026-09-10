# 🇮🇳 BHARAT AIR-CPI: Automated Airfare Inflation Index

## 1. Project Information
* **Project Title**: BHARAT AIR-CPI – Automated Real-Time Airfare Indexing & Analytics Engine
* **PS ID**: 26056
* **PS Title**: Automated Real-Time Airfare Inflation Tracking & Base Fare Decomposition Engine
* **Category**: Software
* **Theme**: Smart Governance / Macroeconomic Analytics (MoSPI & RBI Scope)

---

## 2. Problem Statement
The Ministry of Statistics and Programme Implementation (MoSPI) and the Reserve Bank of India (RBI) require accurate, real-time tracking of airfare inflation for Consumer Price Index (CPI) calculations. Existing manual or naive web scraping methods face major challenges:
* Failure to isolate pure airline revenue (**Base Fare**) from statutory airport taxes, User Development Fees (UDF), and booking convenience charges.
* Price volatility across advance purchase lead times ($T+1$ to $T+5$ days prior to departure).
* Anti-scraping measures, malformed API payloads, and statistical price anomalies skewing macro inflation trends.

---

## 3. Proposed Solution
**BHARAT AIR-CPI** is an end-to-end, multi-role data engineering and analytics pipeline:
1. **Stealth Ingestion**: A Playwright-driven stealth crawler intercepts network JSON fare envelopes across 5 high-density domestic flight corridors.
2. **Automated Cleaning & Unbundling**: A Pydantic v2 validation pipeline quarantines invalid payloads, unbundles ticket costs into pure base fare vs. taxes/fees using regex rules, and flags price anomalies using IQR (Interquartile Range) and Z-score filtering.
3. **Columnar Materialization**: Clean records are written to compressed Snappy Parquet files (`clean_airfare_index.parquet`).
4. **Sovereign Dashboard**: A high-performance Streamlit application styled with an Indian National Government aesthetic presents real-time CPI trends, convergence charts, and fare heatmaps for policy analysts.

---

## 4. Key Features
* **Automated Stealth Ingestion**: Intercepts flight search API payloads across 5 major routes (`DEL-BOM`, `BLR-DEL`, `BOM-MAA`, `DEL-CCU`, `HYD-BOM`) and 5 lead-time horizons ($T+1$ to $T+5$).
* **Fare Decomposition & Unbundling**: Deconstructs raw total quotes into Base Fare (~78%), Taxes & UDF (~17%), and Convenience Fees (~5%) with deterministic fallback logic.
* **Schema Validation & Quarantine**: Pydantic v2 models validate data formats and quarantine malformed records to `quarantine_raw_payloads.jsonl`.
* **Statistical Outlier Detection**: Cohort-based IQR and Z-score anomaly engine flags price spikes/dips without dropping valid historical data.
* **Indian Sovereign Dashboard**: A Streamlit frontend styled with Saffron, Ashoka Navy, and Emerald Green, displaying composite price indices, advance-window convergence, and fare breakdown heatmaps.

---

## 5. Technology Stack
* **Frontend & Presentation**: Streamlit, Plotly Express
* **Data Engineering & Cleaning**: Python 3.11+, Pandas, NumPy, SciPy, PyArrow, Pydantic v2
* **Ingestion & Scraping**: Asyncio, Playwright (Chromium Stealth)
* **Containerization & Deployment**: Docker, Render / Streamlit Cloud

---

## 6. Architecture

```text
User / Policy Analyst
          │
          ▼
┌────────────────────────────────────────────────────────┐
│               Streamlit Web Command Center             │ (Role 4: Frontend)
└───────────────────────────┬────────────────────────────┘
                            │ Reads clean artifacts
                            ▼
┌────────────────────────────────────────────────────────┐
│           Compressed Columnar Parquet File             │ (seed_data/clean_airfare_index.parquet)
└───────────────────────────▲────────────────────────────┘
                            │ Materializes clean records
┌───────────────────────────┴────────────────────────────┐
│         Data Engineering & Cleaning Pipeline           │ (Role 2: ETL Engine)
│  - Pydantic v2 Schema Validation                       │
│  - Regex Fare Unbundling (Base / Tax / Fees)           │
│  - Statistical Outlier Engine (IQR / Z-score)          │
└───────────────────────────▲────────────────────────────┘
                            │ Ingests raw JSONL
┌───────────────────────────┴────────────────────────────┐
│            Playwright Stealth Web Scraper              │ (Role 1: Ingestion)
│  - Intercepts raw network JSON/gRPC flight envelopes   │
└────────────────────────────────────────────────────────┘
```
## 7.Repository Structure
```Mospi-Airfare-Index/
├── README.md
├── SUBMISSION_GUIDE.md
├── submission/
│   ├── PRESENTATION.md
│   └── DEMO.md
├── src/
│   ├── ingestion/             # Role 1: Playwright stealth scraper & matrix generator
│   ├── engineering/           # Role 2: Validation, unbundling, and IQR filtering
│   └── frontend/              # Role 4: Streamlit UI (app.py, data_loader.py, components/)
├── seed_data/                 # Shared data handoff folder
│   ├── staging_raw_payloads.jsonl
│   ├── quarantine_raw_payloads.jsonl
│   └── clean_airfare_index.parquet
├── docs/
│   └── architecture.md
├── assets/
│   └── screenshots/
│       └── README.md
├── tests/                     # Pytest suite for data pipeline modules
├── run_pipeline.py            # Master pipeline orchestrator CLI
├── Dockerfile                 # Container environment setup
├── requirements.txt           # Python dependency manifest
```
## 8. Final Presentation
* Details regarding the final submission slides and structural deck are documented in `submission/PRESENTATION.md`.
* Access the accessible viewer link or presentation document directly inside `submission/PRESENTATION.md`.

## 9. Demo Video
A walkthrough video demonstrating the data ingestion, unbundling pipeline, and Streamlit command center is linked in `submission/DEMO.md`.

## 11. Installation

1. **Clone the repository**:
```bash
git clone [https://github.com/CacheMeIfYouCan-SIH-26/Mospi-Airfare-Index.git](https://github.com/CacheMeIfYouCan-SIH-26/Mospi-Airfare-Index.git)
cd Mospi-Airfare-Index
```
2. **Install dependencies**:
```bash
pip install -r requirements.txt
```
3.Install Playwright Browsers
```bash
playwright install chromium
```
## 12. Run
Step 1: Run the Data Pipeline (Role 2 Cleaning)
Process raw staging payloads from seed_data/ into a clean Parquet dataset:
```bash
python -m src.engineering.clean_staging_lead
```
##12. Run
Step 1: Run the Data Pipeline
Process raw staging payloads from seed_data/ into a clean Parquet dataset:
```bash
python -m src.engineering.clean_staging_lead
```
