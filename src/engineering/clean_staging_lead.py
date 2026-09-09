import os
import stat
import sys
from pathlib import Path
from typing import Tuple

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.engineering.fare_unbundler import unbundle_fare
from src.engineering.outlier_filter import flag_outliers
from src.engineering.schemas import CleanAirfareRecord, RawStagingPayload
from src.engineering.schema_validator import validate_staging_payloads

STAGING_FILE = Path("seed_data/staging_raw_payloads.jsonl")
QUARANTINE_FILE = Path("seed_data/quarantine_raw_payloads.jsonl")
CLEAN_PARQUET = Path("seed_data/clean_airfare_index.parquet")
CLEAN_JSONL = Path("seed_data/clean_airfare_index.jsonl")


def _make_writable(path: Path) -> None:
    """Clears the read-only attribute on Windows sync-backed files before writing."""
    if os.name == "nt" and path.exists():
        path.chmod(stat.S_IWRITE)


def _unbundle_records(records: "list[RawStagingPayload]") -> "list[CleanAirfareRecord]":
    clean_records = []
    for record in records:
        raw_payload = record.raw_payload if record.raw_payload else {}
        total_quote = raw_payload.get("total_quote")
        fare_string = raw_payload.get("fare_details_html", "")

        if total_quote is not None:
            total_quote = float(total_quote)
        unbundled = unbundle_fare(fare_string, total_quote=total_quote)

        clean_records.append(
            CleanAirfareRecord(
                route_code=record.route_code,
                origin=record.origin,
                destination=record.destination,
                departure_date=record.departure_date,
                advance_window=record.advance_window,
                captured_at=record.scraped_at,
                unbundled=unbundled,
            )
        )
    return clean_records


def _records_to_dataframe(records: "list[CleanAirfareRecord]") -> pd.DataFrame:
    rows = [
        {
            "route_code": r.route_code,
            "origin": r.origin,
            "destination": r.destination,
            "departure_date": r.departure_date,
            "advance_window": r.advance_window,
            "captured_at": r.captured_at.isoformat() if r.captured_at else None,
            "base_fare": r.unbundled.base_fare,
            "tax_udf": r.unbundled.tax_udf,
            "convenience_fee": r.unbundled.convenience_fee,
            "total_quote": r.unbundled.total_quote,
        }
        for r in records
    ]
    return pd.DataFrame(rows)


def _print_summary(
    total_ingested: int,
    validated: "list[RawStagingPayload]",
    quarantined: int,
    clean: pd.DataFrame,
) -> None:
    print("\n" + "=" * 56)
    print("MOSPI Airfare Index - Role 2 Cleanup Summary")
    print("=" * 56)
    print(f"[1] Ingest & Validate : {total_ingested} ingested | {len(validated)} passed | {quarantined} quarantined")
    print(f"[2] Unbundle Fares    : {len(clean)} fares decomposed")
    print(f"[3] Outlier Filter    : {int(clean['is_outlier'].sum())} flagged out of {len(clean)} records")
    print(f"[4] Outputs           : {CLEAN_PARQUET} (snappy) | {CLEAN_JSONL}")
    print("-" * 56)
    
    # Aggregating strictly on pure base_fare for MOSPI standards
    price_summary = clean.groupby("route_code", dropna=False)["base_fare"].agg(
        ["count", "mean", "min", "max"]
    )
    print(price_summary.round(2).to_string())
    print("=" * 56)


def run_role_2_pipeline(
    staging_file: Path = STAGING_FILE,
    quarantine_file: Path = QUARANTINE_FILE,
    parquet_out: Path = CLEAN_PARQUET,
    jsonl_out: Path = CLEAN_JSONL,
) -> Tuple[pd.DataFrame, "list[CleanAirfareRecord]"]:
    """Master orchestrator: Ingest & Validate -> Unbundle -> Outlier Filter -> Output."""
    print("[STEP 1/4] Ingesting & validating staging JSONL...")
    validated, quarantined_records = validate_staging_payloads(staging_file, quarantine_file)
    quarantined = len(quarantined_records)
    total_ingested = len(validated) + quarantined

    print("\n[STEP 2/4] Unbundling fares into granular components...")
    clean_records = _unbundle_records(validated)
    df = _records_to_dataframe(clean_records)

    print("\n[STEP 3/4] Applying outlier detection (IQR / Z-score fallback)...")
    df = flag_outliers(df)

    print("\n[STEP 4/4] Writing cleaned dataset...")
    parquet_out.parent.mkdir(parents=True, exist_ok=True)
    order = [
        "route_code",
        "origin",
        "destination",
        "advance_window",
        "departure_date",
        "captured_at",
        "base_fare",
        "tax_udf",
        "convenience_fee",
        "total_quote",
        "is_outlier",
        "outlier_reason",
    ]
    df = df[order]
    _make_writable(parquet_out)
    _make_writable(jsonl_out)
    df.to_parquet(parquet_out, engine="pyarrow", compression="snappy", index=False)
    df.to_json(jsonl_out, orient="records", lines=True, force_ascii=False)
    print(f"[OK] Parquet saved  -> {parquet_out}")
    print(f"[OK] JSONL saved    -> {jsonl_out}")

    # Print clean summary focused on Base Fare
    _print_summary(total_ingested, validated, quarantined, df)
    
    return df, clean_records


if __name__ == "__main__":
    clean_df, clean_objects = run_role_2_pipeline()