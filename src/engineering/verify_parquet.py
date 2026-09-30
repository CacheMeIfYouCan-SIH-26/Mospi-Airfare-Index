from pathlib import Path

import pandas as pd

PARQUET_FILE = Path("seed_data/clean_airfare_index.parquet")

CRITICAL_COLUMNS = ("total_quote", "base_fare", "route_code")


def verify_parquet(parquet_file: Path = PARQUET_FILE) -> pd.DataFrame:
    """Audits the cleaned Parquet file: schema, dtypes, row count, size, nulls."""
    if not parquet_file.exists():
        raise FileNotFoundError(f"Parquet file not found: {parquet_file}")

    df = pd.read_parquet(parquet_file)
    file_size_bytes = parquet_file.stat().st_size

    print("=" * 70)
    print(f"Parquet Audit : {parquet_file}")
    print("=" * 70)
    print(f"File size on disk : {file_size_bytes:,} bytes ({file_size_bytes / 1024:.2f} KB)")
    print(f"Row count         : {len(df):,}")
    print(f"Columns           : {len(df.columns)}")
    print()

    print("-- DataFrame Schema (data types) --")
    for column, dtype in df.dtypes.items():
        print(f"  {column:<18} {str(dtype):<12} nulls={int(df[column].isna().sum()):,}")
    print()

    print("-- Null check on critical columns --")
    null_counts = df[list(CRITICAL_COLUMNS)].isna().sum()
    for column in CRITICAL_COLUMNS:
        count = int(null_counts[column])
        status = "OK   (no nulls)" if count == 0 else f"FAIL ({count:,} nulls)"
        print(f"  {column:<16} : {status}")
        if count != 0:
            raise AssertionError(f"Critical column '{column}' contains {count} null values")

    print()
    print("-- First 5 records --")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(df.head(5).to_string(index=False))
    print("=" * 70)

    return df


if __name__ == "__main__":
    verify_parquet()