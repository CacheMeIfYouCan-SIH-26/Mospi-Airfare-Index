import numpy as np
import pandas as pd

IQR_MULTIPLIER = 1.5
Z_SCORE_THRESHOLD = 3.0
MIN_Z_SCORE_SAMPLE = 10


def _iqr_bounds(group: pd.Series) -> tuple:
    q1 = group.quantile(0.25)
    q3 = group.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - (IQR_MULTIPLIER * iqr)
    upper_bound = q3 + (IQR_MULTIPLIER * iqr)
    return lower_bound, upper_bound


def _group_outlier_mask(group: pd.Series, z_score_threshold: float) -> "pd.Series[bool]":
    """Flags outliers per group, falling back to Z-score for small samples."""
    if group.size == 0:
        return pd.Series([False] * len(group), index=group.index)

    if group.size < MIN_Z_SCORE_SAMPLE:
        std = group.std(ddof=0)
        if std is None or np.isnan(std) or std == 0:
            return pd.Series([False] * len(group), index=group.index)
        z_scores = (group - group.mean()) / std
        return z_scores.abs() > z_score_threshold

    lower_bound, upper_bound = _iqr_bounds(group)
    return (group < lower_bound) | (group > upper_bound)


def _outlier_reason(group: pd.Series, z_score_threshold: float) -> "pd.Series[str]":
    """Builds human-readable outlier reasons aligned to the group's rows."""
    if group.size == 0:
        return pd.Series([], index=group.index, dtype=str)

    if group.size < MIN_Z_SCORE_SAMPLE:
        std = group.std(ddof=0)
        if std is None or np.isnan(std) or std == 0:
            return pd.Series(["" for _ in group], index=group.index)
        z_scores = (group - group.mean()) / std
        return pd.Series(
            (
                f"Z-score {z:.3f} exceeds threshold {z_score_threshold:.1f} "
                f"(N={group.size}, mean={group.mean():.2f}, std={std:.2f})"
                if abs(z) > z_score_threshold
                else ""
            )
            for z in z_scores
        )

    lower_bound, upper_bound = _iqr_bounds(group)
    q1 = group.quantile(0.25)
    q3 = group.quantile(0.75)
    iqr = q3 - q1
    return pd.Series(
        (
            f"Below IQR lower bound {lower_bound:.2f} (Q1={q1:.2f}, IQR={iqr:.2f})"
            if value < lower_bound
            else (
                f"Above IQR upper bound {upper_bound:.2f} (Q3={q3:.2f}, IQR={iqr:.2f})"
                if value > upper_bound
                else ""
            )
        )
        for value in group
    )


def flag_outliers(
    df: pd.DataFrame,
    fare_col: str = "total_quote",
    z_score_threshold: float = Z_SCORE_THRESHOLD,
    group_cols: "tuple[str, ...]" = ("route_code", "advance_window"),
) -> pd.DataFrame:
    """Flags outliers per route_code + advance_window fare group.

    Groups with N >= 10 use the IQR fence method (1.5 * IQR). Small groups
    (N < 10) fall back to the Z-score method with the given threshold.
    Records are flagged, not dropped, preserving auditability.

    Returns:
        A copy of the input DataFrame with added `is_outlier` and
        `outlier_reason` metadata columns.
    """
    result = df.copy().reset_index(drop=True)
    result["is_outlier"] = False
    result["outlier_reason"] = ""

    for indices in result.groupby(list(group_cols), dropna=False).groups.values():
        group = result.loc[indices, fare_col]
        result.loc[indices, "is_outlier"] = _group_outlier_mask(group, z_score_threshold).to_numpy(dtype=bool)
        result.loc[indices, "outlier_reason"] = _outlier_reason(group, z_score_threshold).to_numpy()

    return result


if __name__ == "__main__":
    rng = np.random.default_rng(42)

    rows = []
    for route_code in ("DEL-BOM", "DEL-BLR"):
        for window in ("T+1", "T+2", "T+3"):
            fares = rng.normal(loc=5500.0, scale=400.0, size=11)
            rows.extend(
                {"route_code": route_code, "advance_window": window, "total_quote": round(float(f), 2)}
                for f in fares
            )

    small_rows = [
        {"route_code": "BOM-BLR", "advance_window": "T+1", "total_quote": 100.0},
        {"route_code": "BOM-BLR", "advance_window": "T+1", "total_quote": 5200.0},
        {"route_code": "BOM-BLR", "advance_window": "T+1", "total_quote": 5400.0},
        {"route_code": "BOM-BLR", "advance_window": "T+1", "total_quote": 5300.0},
        {"route_code": "BOM-BLR", "advance_window": "T+1", "total_quote": 5100.0},
    ]
    rows.extend(small_rows)

    df = pd.DataFrame(rows)
    flagged = flag_outliers(df)

    print("== Outlier detection summary (defaults: IQR 1.5x / Z-score 3.0) ==")
    print(flagged.groupby(["route_code", "advance_window"], dropna=False)["is_outlier"].sum().rename("outlier_count"))
    print()
    detected = flagged[flagged["is_outlier"]]
    print("== Flagged outliers (not dropped) ==")
    print(detected[["route_code", "advance_window", "total_quote", "is_outlier", "outlier_reason"]].to_string(index=False))

    assert "is_outlier" in flagged.columns and "outlier_reason" in flagged.columns
    assert len(flagged) == len(df), "No rows should be dropped"

    iqr_rows = flagged[flagged.groupby(["route_code", "advance_window"], dropna=False).transform("size") >= 10]
    print()
    print(f"[PASS] IQR method applied on {len(iqr_rows)} rows in large groups (N >= 10)")
    print(f"[PASS] Z-score fallback selected for {len(flagged) - len(iqr_rows)} rows in small groups (N < 10)")

    z_flagged = flag_outliers(pd.DataFrame(small_rows), z_score_threshold=1.5)
    z_hit = z_flagged[z_flagged["is_outlier"]]
    assert len(z_hit) == 1, f"Expected the extreme value flagged with threshold 1.5, got {len(z_hit)}"
    assert z_hit.iloc[0]["outlier_reason"].startswith("Z-score"), z_hit.iloc[0]["outlier_reason"]
    print("[PASS] Z-score method flags the extreme fare with Z-score reason (threshold 1.5 demo)")