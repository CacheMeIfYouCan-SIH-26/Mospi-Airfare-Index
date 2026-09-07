import json
import os
import stat
from pathlib import Path
from typing import List, Dict, Any, Tuple

from pydantic import ValidationError

from src.engineering.schemas import RawStagingPayload

STAGING_FILE = Path("seed_data/staging_raw_payloads.jsonl")
QUARANTINE_FILE = Path("seed_data/quarantine_raw_payloads.jsonl")


def _make_writable(path: Path) -> None:
    """Clears the read-only attribute on Windows sync-backed files before writing."""
    if os.name == "nt" and path.exists():
        path.chmod(stat.S_IWRITE)


def _read_lines(file_path: Path) -> List[str]:
    if not file_path.exists():
        raise FileNotFoundError(f"Staging file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return [line for line in f if line.strip()]


def _save_quarantine(records: List[Dict[str, Any]], quarantine_file: Path) -> None:
    quarantine_file.parent.mkdir(parents=True, exist_ok=True)
    _make_writable(quarantine_file)
    with open(quarantine_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def validate_staging_payloads(
    staging_file: Path = STAGING_FILE,
    quarantine_file: Path = QUARANTINE_FILE,
) -> Tuple[List[RawStagingPayload], List[Dict[str, Any]]]:
    """Ingests and validates the staging JSONL, separating valid from quarantined records.

    Returns:
        Tuple of (valid_records, quarantine_records) where valid_records are
        validated `RawStagingPayload` objects and quarantine_records preserve the
        original payload along with the reasons it failed validation.
    """
    lines = _read_lines(staging_file)
    total = len(lines)
    valid_records: List[RawStagingPayload] = []
    quarantine_records: List[Dict[str, Any]] = []

    for line_number, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, TypeError) as err:
            quarantine_records.append(
                {
                    "line_number": line_number,
                    "record": None,
                    "error_reason": f"Invalid JSON: {err}",
                }
            )
            continue

        try:
            valid_records.append(RawStagingPayload.model_validate(payload))
        except ValidationError as err:
            quarantine_records.append(
                {
                    "line_number": line_number,
                    "record": payload,
                    "error_reason": f"Schema validation failed: {err.errors()}",
                }
            )

    _save_quarantine(quarantine_records, quarantine_file)

    passed = len(valid_records)
    quarantined = len(quarantine_records)
    print(f"[OK] Ingestion complete: {total} total | {passed} passed | {quarantined} quarantined")
    print(f"[OK] Quarantined records written to '{quarantine_file}'")

    return valid_records, quarantine_records


if __name__ == "__main__":
    valid, quarantine = validate_staging_payloads()