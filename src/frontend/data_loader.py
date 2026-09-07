import json
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_PATH = PROJECT_ROOT / "seed_data" / "clean_airfare_index.parquet"
STAGING_JSONL_PATH = PROJECT_ROOT / "seed_data" / "staging_raw_payloads.jsonl"
QUARANTINE_JSONL_PATH = PROJECT_ROOT / "seed_data" / "quarantine_raw_payloads.jsonl"

MOCK_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5", "T+7", "T+15", "T+30", "T+45"]
MOCK_ROUTES = {
    "DEL-BOM": ("DEL", "BOM", 4200.0),
    "DEL-BLR": ("DEL", "BLR", 6100.0),
    "BOM-BLR": ("BOM", "BLR", 4900.0),
    "DEL-CCU": ("DEL", "CCU", 3800.0),
    "BLR-HYD": ("BLR", "HYD", 2600.0),
}


def _build_mock_records() -> list[dict]:
    rows: list[dict] = []
    step_seconds = 0
    for route_code, (origin, destination, price) in MOCK_ROUTES.items():
        for window in MOCK_WINDOWS:
            for _ in range(2):
                base_fare = price - (int(window[2:]) % 7) * 140.0
                tax_udf = round(base_fare * 0.18, 2)
                rows.append(
                    {
                        "route_code": route_code,
                        "origin": origin,
                        "destination": destination,
                        "advance_window": window,
                        "departure_date": (pd.Timestamp.now().normalize()
                                           + pd.Timedelta(days=int(window[2:]))).isoformat()[:10],
                        "captured_at": (pd.Timestamp.now() - pd.Timedelta(hours=72)
                                        + pd.Timedelta(minutes=step_seconds)).isoformat(),
                        "base_fare": float(base_fare),
                        "tax_udf": tax_udf,
                        "convenience_fee": 300.0,
                        "total_quote": float(base_fare) + tax_udf + 300.0,
                        "is_outlier": False,
                        "outlier_reason": "",
                    }
                )
                step_seconds += 15
    return rows


@st.cache_data(show_spinner=False)
def load_clean_parquet(path: str | Path = PARQUET_PATH) -> pd.DataFrame:
    p = Path(path)
    df = pd.DataFrame(_build_mock_records())
    df.attrs["source"] = "mock"
    if not p.exists():
        return df
    try:
        real = pd.read_parquet(p, engine="pyarrow")
        real.attrs["source"] = "parquet"
        return real
    except Exception:
        return df


@st.cache_data(show_spinner=False)
def load_raw_staging_jsonl(path: str | Path = STAGING_JSONL_PATH) -> list[dict]:
    records: list[dict] = []
    p = Path(path)
    if not p.exists():
        return records
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
    return records


@st.cache_data(show_spinner=False)
def count_quarantine_payloads(path: str | Path = QUARANTINE_JSONL_PATH) -> int:
    return len(load_raw_staging_jsonl(path))



 