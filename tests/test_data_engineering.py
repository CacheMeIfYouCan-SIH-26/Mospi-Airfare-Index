import json

import numpy as np
import pandas as pd
import pytest

from src.engineering.fare_unbundler import unbundle_fare
from src.engineering.outlier_filter import flag_outliers
from src.engineering.schema_validator import validate_staging_payloads

# ---------------------------------------------------------------------------
# schema_validator tests
# ---------------------------------------------------------------------------

VALID_RECORD = {
    "scraped_at": "2026-08-27T15:24:37.357891Z",
    "route_code": "DEL-BOM",
    "origin": "DEL",
    "destination": "BOM",
    "advance_window": "T+1",
    "departure_date": "2026-08-28",
    "intercepted_url": "https://httpbin.org/get?origin=DEL&dest=BOM&date=2026-08-28",
    "raw_payload": {"carrier": "IndiGo", "total_quote": 5420.0},
}


def write_jsonl(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line if isinstance(line, str) else json.dumps(line))
            f.write("\n")


class TestSchemaValidator:
    def test_valid_records_pass(self, tmp_path):
        staging = tmp_path / "staging.jsonl"
        quarantine = tmp_path / "quarantine.jsonl"
        write_jsonl(staging, [VALID_RECORD, dict(VALID_RECORD, route_code="DEL-BLR")])

        valid, quarantined = validate_staging_payloads(staging, quarantine)

        assert len(valid) == 2
        assert len(quarantined) == 0
        assert valid[0].route_code == "DEL-BOM"
        assert valid[0].origin == "DEL"

    def test_optional_fields_default_to_none(self, tmp_path):
        staging = tmp_path / "staging.jsonl"
        quarantine = tmp_path / "quarantine.jsonl"
        minimal = {k: v for k, v in VALID_RECORD.items() if k not in ("advance_window", "intercepted_url")}
        write_jsonl(staging, [minimal])

        valid, quarantined = validate_staging_payloads(staging, quarantine)

        assert len(valid) == 1
        assert valid[0].advance_window is None
        assert valid[0].intercepted_url is None

    def test_corrupted_json_is_quarantined(self, tmp_path):
        staging = tmp_path / "staging.jsonl"
        quarantine = tmp_path / "quarantine.jsonl"
        write_jsonl(staging, [VALID_RECORD, "{this is not valid json"])

        valid, quarantined = validate_staging_payloads(staging, quarantine)

        assert len(valid) == 1
        assert len(quarantined) == 1
        assert quarantined[0]["line_number"] == 2
        assert "Invalid JSON" in quarantined[0]["error_reason"]

    def test_schema_violations_are_quarantined(self, tmp_path):
        staging = tmp_path / "staging.jsonl"
        quarantine = tmp_path / "quarantine.jsonl"
        bad_iata = dict(VALID_RECORD, origin="del")
        bad_date = dict(VALID_RECORD, departure_date="28-08-2026")
        bad_route = dict(VALID_RECORD, route_code="DELBOM")
        write_jsonl(staging, [bad_iata, bad_date, bad_route])

        valid, quarantined = validate_staging_payloads(staging, quarantine)

        assert len(valid) == 0
        assert len(quarantined) == 3
        for q in quarantined:
            assert "Schema validation failed" in q["error_reason"]

    def test_missing_staging_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_staging_payloads(tmp_path / "does_not_exist.jsonl", tmp_path / "q.jsonl")


# ---------------------------------------------------------------------------
# fare_unbundler tests
# ---------------------------------------------------------------------------

class TestFareUnbundler:
    @pytest.mark.parametrize(
        "fare_text,base,tax,convenience",
        [
            ("Base: 5186, Tax: 933.48, Convenience: 300", 5186.0, 933.48, 300.0),
            ("Base:5186, Tax:933.48, Convenience:300", 5186.0, 933.48, 300.0),
            (
                "Base Fare: 5186, Tax & Airport User Development Fee: 933.48, "
                "Convenience / Management Fee: 300",
                5186.0,
                933.48,
                300.0,
            ),
            ("Base: Rs.5186, Tax: INR 933.48, Convenience: ₹ 300", 5186.0, 933.48, 300.0),
            (
                "<div class='fare'><span>Base: 5186, Tax: 933.48, Convenience: 300</span></div>",
                5186.0,
                933.48,
                300.0,
            ),
            ("Base: 5,186.00, Tax: 933.48, Convenience: 300", 5186.0, 933.48, 300.0),
        ],
    )
    def test_extraction_formats(self, fare_text, base, tax, convenience):
        fare = unbundle_fare(fare_text)

        assert fare.base_fare == pytest.approx(base)
        assert fare.tax_udf == pytest.approx(tax)
        assert fare.convenience_fee == pytest.approx(convenience)

    @pytest.mark.parametrize("total", [7492.1, 6011.33, 4520.0])
    def test_fallback_math_when_tax_missing(self, total):
        fare = unbundle_fare("Base: 5000, Convenience: 300", total_quote=total)

        assert fare.base_fare == pytest.approx(round(total * 0.82, 2))
        assert fare.tax_udf == pytest.approx(round(total * 0.18, 2))
        assert fare.total_quote == total

    def test_total_inferred_from_components(self):
        fare = unbundle_fare("Base Fare 5186 | Tax 933.48 | Convenience 300")

        assert fare.total_quote == pytest.approx(5186 + 933.48 + 300)

    def test_no_negative_values(self):
        fare = unbundle_fare("Base: 5186, Tax: 933.48, Convenience: 300")
        assert fare.base_fare >= 0
        assert fare.tax_udf >= 0
        assert fare.convenience_fee >= 0
        assert fare.total_quote >= 0


# ---------------------------------------------------------------------------
# outlier_filter tests
# ---------------------------------------------------------------------------

class TestOutlierFilter:
    @staticmethod
    def iqr_group(with_spike=True):
        fares = [5200.0, 5300.0, 5400.0, 5500.0, 5600.0, 5700.0, 5800.0, 5900.0, 6000.0, 6100.0, 6200.0]
        if with_spike:
            fares.append(99999.0)
        return pd.DataFrame(
            {"route_code": "DEL-BOM", "advance_window": "T+1", "total_quote": fares}
        )

    def test_extreme_high_spike_flagged(self):
        flagged = flag_outliers(self.iqr_group(with_spike=True))

        assert flagged.loc[flagged["total_quote"] == 99999.0, "is_outlier"].item() is True
        assert flagged.loc[flagged["total_quote"] == 99999.0, "outlier_reason"].item().startswith("Above IQR")

    def test_extreme_low_spike_flagged(self):
        df = pd.DataFrame(
            {
                "route_code": "DEL-BOM",
                "advance_window": "T+1",
                "total_quote": [1.0, 5200.0, 5300.0, 5400.0, 5500.0, 5600.0,
                                5700.0, 5800.0, 5900.0, 6000.0, 6100.0, 6200.0],
            }
        )
        flagged = flag_outliers(df)

        assert flagged.loc[flagged["total_quote"] == 1.0, "is_outlier"].item() is True
        assert flagged.loc[flagged["total_quote"] == 1.0, "outlier_reason"].item().startswith("Below IQR")

    def test_stable_fares_not_flagged(self):
        flagged = flag_outliers(self.iqr_group(with_spike=False))

        assert not flagged["is_outlier"].any()
        assert (flagged["outlier_reason"] == "").all()

    def test_rows_preserved_for_auditability(self):
        raw = self.iqr_group(with_spike=True)
        flagged = flag_outliers(raw)

        assert len(flagged) == len(raw)
        assert list(flagged.columns).count("is_outlier") == 1

    def test_small_sample_uses_z_score(self):
        df = pd.DataFrame(
            {
                "route_code": "BOM-BLR",
                "advance_window": "T+1",
                "total_quote": [100.0, 5200.0, 5400.0, 5300.0, 5100.0],
            }
        )
        flagged = flag_outliers(df, z_score_threshold=1.5)

        hit = flagged[flagged["is_outlier"]]
        assert len(hit) == 1
        assert hit.iloc[0]["outlier_reason"].startswith("Z-score")

    def test_group_partitioning_by_route_and_window(self):
        rows = []
        for route in ("DEL-BOM", "DEL-BLR"):
            row = self.iqr_group(with_spike=True)
            row["route_code"] = route
            rows.append(row)
        df = pd.concat(rows, ignore_index=True)

        flagged = flag_outliers(df)

        assert flagged.groupby(["route_code", "advance_window"])["is_outlier"].sum().to_dict() == {
            ("DEL-BLR", "T+1"): 1,
            ("DEL-BOM", "T+1"): 1,
        }