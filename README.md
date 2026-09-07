# Mospi-Airfare-Index

Automated airfare index pipeline for the MOSPI Airfare Index platform (SIH-26 hackathon).
The repository is split by engineering roles. Each role owns a self-contained slice of
the pipeline and hands off artifacts through well-defined file contracts under `seed_data/`.

## Repository Layout

```
.
|- src/
|  |- ingestion/          Role 1: Data Ingestion (Playwright stealth scraper)
|  |- engineering/        Role 2: Data Engineering & Cleaning Pipeline
|  |- frontend/           Role 4: Streamlit dashboard (app.py, data_loader.py, components/)
|- seed_data/             Staging, quarantine and clean artifacts (JSONL / Parquet)
|- tests/                 Pytest suite for data engineering modules
|- run_pipeline.py        End-to-end CLI orchestrator
|- Makefile               Automation targets (ingest / clean-data / test / docs / dashboard)
|- Dockerfile             Frontend dashboard container (Python 3.13, port 8501)
|- generate_pdf.py        Role 1 PDF documentation
`- Role_1_Ingestion_Executive_Summary.pdf
```

---

## Role 1: Data Ingestion (summary)

Role 1 drives a stealth Chromium browser via Playwright, intercepts network JSON fare
responses, and persists each envelope as a JSON Line in `seed_data/staging_raw_payloads.jsonl`.
See the dedicated Role 1 documentation for details.

---

## Role 2: Data Engineering & Cleaning Pipeline

Role 2 transforms the raw interception envelopes produced by Role 1 into a validated,
columnar, analytics-ready dataset. The pipeline runs four sequential stages:

1. **Ingest & Validate** - `schema_validator.py` reads the staging JSONL and validates every
   envelope against the Pydantic v2 `RawStagingPayload` contract (dates in `YYYY-MM-DD`,
   IATA codes as 3 uppercase letters). Malformed JSON and schema violations are quarantined
   to `seed_data/quarantine_raw_payloads.jsonl` with the source line number and error reason.
2. **Unbundle Fares** - `fare_unbundler.py` parses raw fare strings / HTML snippets and
   decomposes them into `base_fare`, `tax_udf` and `convenience_fee` via regular expressions.
   If explicit tax extraction fails, a proportional 82/18 fallback is applied using the
   total quote.
3. **IQR Outlier Filter** - `outlier_filter.py` flags outliers per `route_code` +
   `advance_window` cohort. Cohorts with N >= 10 use the IQR fence rule
   (Q1 - 1.5*IQR, Q3 + 1.5*IQR); sparse cohorts fall back to a Z-score rule (threshold 3.0).
   Rows are flagged (`is_outlier`, `outlier_reason`), never dropped.
4. **Output Hand-off** - `clean_staging_lead.py` orchestrates all stages and materialises
   the clean dataset in two formats (see below).

### Input / Output Files

| Stage | File | Direction |
| ----- | ---- | --------- |
| Input (Role 1 hand-off) | `seed_data/staging_raw_payloads.jsonl` | ingests |
| Quarantine (failures) | `seed_data/quarantine_raw_payloads.jsonl` | writes |
| Clean artifact (primary) | `seed_data/clean_airfare_index.parquet` | writes (Snappy) |
| Clean artifact (inspect) | `seed_data/clean_airfare_index.jsonl` | writes |
| Verification audit | `seed_data/clean_airfare_index.parquet` | reads |

The clean Parquet exposes 12 typed columns:
`route_code`, `origin`, `destination`, `advance_window`, `departure_date`, `captured_at`,
`base_fare`, `tax_udf`, `convenience_fee`, `total_quote`, `is_outlier`, `outlier_reason`.
Critical columns (`total_quote`, `base_fare`, `route_code`) are guaranteed null-free.

### Terminal Execution Commands

Run the full Role 2 pipeline:

```bash
python src/engineering/clean_staging_lead.py
# or module form
python -m src.engineering.clean_staging_lead
```

Audit the resulting Parquet file:

```bash
python -m src.engineering.verify_parquet
```

Run the Role 2 unit tests:

```bash
python -m pytest tests/test_data_engineering.py -v
```

Generate the Role 2 PDF documentation:

```bash
python -m src.engineering.generate_role2_pdf
```

Orchestrate everything (roles or full pipeline):

```bash
python run_pipeline.py --role 2      # Role 2 only
python run_pipeline.py --all         # Role 1 + Role 2
make clean-data                      # if GNU make is available (WSL / Linux)
```

### Dependencies

```bash
pip install pydantic pandas numpy pyarrow pytest fpdf2 streamlit plotly
```

---

## Frontend Dashboard & Deployment (Role 4)

The interactive dashboard is a Streamlit app at `src/frontend/app.py` backed by the
clean Parquet artifact and staged raw payloads.

### Launch the local web app

From the repository root:

```bash
python -m streamlit run src/frontend/app.py
```

Or with GNU make (WSL / Linux):

```bash
make dashboard
```

Streamlit starts on `http://localhost:8501`. The dashboard provides:

- Tab 1 - Airfare Index & Price Trends (composite index KPIs, advance-window
  convergence chart, outlier inspection table with spike/dip highlighting).
- Tab 2 - Unbundled Fare Breakdown (component bar chart and route x window fare matrix).
- Tab 3 - Pipeline Health & Staging Logs (status badges, disk/compression stats,
  raw JSONL inspector).
- Sidebar exports - Executive report PDF download and filtered CSV export.
- A deterministic mock-data fallback keeps the UI alive during demos even if the
  Parquet artifact is missing.

### Containerized deployment (Docker)

A `Dockerfile` (Python 3.13 slim, port 8501) is included at the repository root.

```bash
docker build -t mospi-airfare-dashboard .
docker run -p 8501:8501 mospi-airfare-dashboard
```

Then open `http://localhost:8501`.

---

## Git Workflow for Collaborators

To receive the latest Role 2 updates (or any role's changes) on an existing local clone:

1. **Check your current state** (commit or stash local work first so nothing is lost):

   ```bash
   git status
   ```

2. **Fetch and merge the latest upstream main**:

   ```bash
   git pull origin main
   ```

3. **Resolve conflicts if prompted** - edit the conflicted files, then stage and complete:

   ```bash
   git add <file>
   git commit -m "resolve merge conflict"
   ```

4. **Verify dependencies and run the test suite** before continuing development:

   ```bash
   pip install -r requirements.txt
   python -m pytest tests/ -v -p no:cacheprovider
   ```

5. **Smoke-test the Role 2 pipeline end to end** (requires the staged JSONL present):

   ```bash
   python -m src.engineering.clean_staging_lead
   python -m src.engineering.verify_parquet
   ```

### For first-time contributors (new clone)

```bash
git clone https://github.com/CacheMeIfYouCan-SIH-26/Mospi-Airfare-Index.git
cd Mospi-Airfare-Index
git checkout main
pip install -r requirements.txt
```

> **Note on Windows / synced folders:** files under the repo may briefly become
> read-only while the sync client touches them. If a write fails, clear the attribute:
> `Set-ItemProperty -Path <file> -Name IsReadOnly -Value $false`.