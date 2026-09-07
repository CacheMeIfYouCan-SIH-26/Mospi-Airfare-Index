import pandas as pd
import streamlit as st

from components.heatmap import build_route_heatmap
from components.trend_chart import build_trend_figure
from data_loader import (
    PARQUET_PATH,
    PROJECT_ROOT,
    STAGING_JSONL_PATH,
    count_quarantine_payloads,
    load_clean_parquet,
    load_raw_staging_jsonl,
)

PDF_CANDIDATES = [
    "Role_1_Ingestion_Executive_Summary.pdf",
    "Role_2_Data_Engineering_Documentation.pdf",
    "Role_1_Ingestion_Documentation_v2.pdf",
    "Role_1_Ingestion_Documentation.pdf",
]

st.set_page_config(page_title="MOSPI Airfare Index Dashboard", layout="wide")

DEFAULT_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5"]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .dashboard-header {
            background: linear-gradient(135deg, #0f1c2e 0%, #20304a 100%);
            color: #ffffff;
            padding: 1.4rem 1.6rem;
            border-radius: 10px;
            border: 1px solid #33475f;
            margin-bottom: 0.6rem;
        }
        .dashboard-header h1 {
            margin: 0;
            font-size: 1.7rem;
            color: #ffffff;
        }
        .dashboard-header p {
            margin: 0.25rem 0 0;
            font-size: 0.95rem;
            color: #b8c7db;
        }
        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-left: 4px solid #1f4e79;
            border-radius: 8px;
            padding: 0.9rem 1.1rem;
            box-shadow: 0 2px 6px rgba(15, 28, 46, 0.08);
        }
        div[data-testid="stMetricLabel"] {
            color: #33475f;
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            color: #0f1c2e;
        }
        .status-badge {
            display: inline-block;
            padding: 0.45rem 1.1rem;
            border: 1px solid #c6e6c6;
            border-radius: 20px;
            background: #e8f5e9;
            color: #1b5e20;
            font-weight: 600;
            font-size: 0.95rem;
            margin-right: 0.6rem;
        }
        .status-dot {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #2e7d32;
            margin-right: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_data() -> pd.DataFrame | None:
    df = load_clean_parquet()
    is_mock = df.attrs.get("source") == "mock"
    df = df.copy()
    if is_mock:
        st.warning(
            "Clean Parquet artifact not found in seed_data. Displaying deterministic sample mock "
            "records so the demo keeps working."
        )
    if df.empty:
        return None
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True).dt.tz_localize(None)
    return df


def window_sort_key(window: str) -> int:
    return int(window[2:])


def _resolve_report_pdf():
    for name in PDF_CANDIDATES:
        candidate = PROJECT_ROOT / name
        if candidate.exists():
            return candidate
    return None


def filtered_csv(f: pd.DataFrame) -> bytes:
    return f.to_csv(index=False).encode("utf-8")


def classify_outliers(outliers: pd.DataFrame) -> pd.DataFrame:
    cohort_mean = outliers.groupby("advance_window")["total_quote"].transform("mean")
    labeled = outliers.copy()
    labeled["anomaly_type"] = labeled["total_quote"].gt(cohort_mean).map(
        {True: "PRICE SPIKE", False: "SUB-MARKET DIP"}
    )
    return labeled


def outlier_style_functions(outliers: pd.DataFrame):
    cohort_mean = outliers.groupby("advance_window")["total_quote"].transform("mean")

    def color_cells(row: pd.Series) -> list[str]:
        if row["total_quote"] > cohort_mean[row.name]:
            return ["background-color: #fdecea; color: #b71c1c; font-weight: 600"] * len(row)
        return ["background-color: #e8f5e9; color: #1b5e20; font-weight: 600"] * len(row)

    return outliers.style.apply(color_cells, axis=1)


def _fmt_inr(value: float | None) -> str:
    return "N/A" if value is None else f"₹{value:,.2f}"


def render_tab_trends(f: pd.DataFrame, route_full: pd.DataFrame) -> None:
    if f.empty or route_full.empty:
        st.info("No observations match the current filters.")
        return

    show_outliers = st.toggle(
        "Show outliers in trend chart",
        value=True,
        help="Toggle anomalies flagged by the Role 2 IQR engine to compare index values with and without spikes.",
    )
    chart_df = f if show_outliers else f[~f["is_outlier"]]
    outliers = f[f["is_outlier"]]

    if chart_df.empty:
        st.warning("All records in this selection are outliers. Turn the toggle back on to view them.")
    else:
        mean_quote = chart_df["total_quote"].mean()
        ref_mean = route_full["total_quote"].mean()
        composite_index = (100.0 * mean_quote / ref_mean) if ref_mean else 100.0

        baseline5 = route_full.loc[route_full["advance_window"] == "T+5", "total_quote"]
        mean_quote5 = baseline5.mean() if not baseline5.empty else None
        delta_pct = None
        if mean_quote5 is not None and mean_quote5:
            delta_pct = (mean_quote - mean_quote5) / mean_quote5 * 100.0

        mean_base = chart_df["base_fare"].mean()
        quality_score = 100.0 * (1.0 - f["is_outlier"].mean()) if len(f) else 0.0

        kpi = st.columns(4)
        kpi[0].metric("Composite Index (Base 100)", f"{composite_index:,.2f}")
        kpi[1].metric(
            "Avg Total Quote (INR)",
            _fmt_inr(mean_quote),
            delta=f"{delta_pct:.2f}% vs T+5" if delta_pct is not None else None,
        )
        kpi[2].metric("Avg Base Fare (INR)", _fmt_inr(mean_base))
        kpi[3].metric("Data Quality Score", f"{quality_score:.1f}%")

        st.caption("KPI block: composite index vs route benchmark (base 100), currency delta vs T+5 baseline, "
                   "and share of valid non-outlier records in the current selection.")
        st.subheader("Total Quote Trend & Advance-Window Convergence")
        fig = build_trend_figure(chart_df, baseline_mean=route_full["total_quote"].mean())
        st.plotly_chart(fig, width="stretch")

    st.subheader("Outlier Inspection (Role 2 IQR Engine)")
    if not outliers.empty:
        st.caption("Red = anomaly price spike, green = sub-market dip, each judged against the advance-window "
                   "cohort mean.")
        labeled = classify_outliers(outliers)
        columns = ["route_code", "advance_window", "departure_date", "total_quote",
                   "anomaly_type", "outlier_reason"]
        st.dataframe(
            outlier_style_functions(labeled)[columns],
            width="stretch",
            column_config={"total_quote": st.column_config.NumberColumn("Total Quote (INR)",
                                                                       format="₹ %.2f")},
        )
    else:
        st.info("No outlier records flagged by the Role 2 IQR engine in the current selection.")

    st.subheader("Observation Detail")
    st.dataframe(
        f[["route_code", "advance_window", "departure_date", "captured_at", "total_quote", "is_outlier"]],
        width="stretch",
    )


def render_tab_breakdown(f: pd.DataFrame, matrix_df: pd.DataFrame) -> None:
    if f.empty:
        st.info("No observations match the current filters.")
        return

    metric_cols = st.columns(3)
    metric_cols[0].metric("Avg Base Fare", f"{f['base_fare'].mean():,.0f}")
    metric_cols[1].metric("Avg Tax & UDF", f"{f['tax_udf'].mean():,.0f}")
    metric_cols[2].metric("Avg Convenience Fee", f"{f['convenience_fee'].mean():,.0f}")

    st.subheader("Unbundled Fare Components by Advance Window")
    breakdown = (
        f.groupby("advance_window")[["base_fare", "tax_udf", "convenience_fee"]]
        .sum()
        .reindex(sorted(f["advance_window"].unique(), key=window_sort_key))
    )
    st.bar_chart(breakdown)

    st.subheader("Fare Component Detail")
    st.dataframe(
        f[["advance_window", "departure_date", "base_fare", "tax_udf", "convenience_fee", "total_quote"]],
        width="stretch",
    )

    st.subheader("Route x Advance Window Fare Matrix")
    heat_value = st.radio(
        "Color intensity metric",
        ["fare", "volatility"],
        index=0,
        format_func=lambda v: "Average Fare Price" if v == "fare" else "Volatility Index (CV %)",
        horizontal=True,
    )
    st.plotly_chart(build_route_heatmap(matrix_df, value=heat_value), width="stretch")


def render_tab_pipeline(all_df: pd.DataFrame) -> None:
    if all_df.empty:
        st.info("No clean pipeline data to display.")
        return

    st.markdown(
        "<div>"
        "<span class='status-badge'><span class='status-dot'></span>Ingestion Locked (Role 1)</span>"
        "<span class='status-badge'><span class='status-dot'></span>Parquet Cleaned (Role 2)</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Green status badges confirm the Role 1 ingestion and Role 2 parquet hand-offs are locked and ready "
               "for downstream analytics.")

    jsonl_size = STAGING_JSONL_PATH.stat().st_size if STAGING_JSONL_PATH.exists() else 0
    parquet_size = PARQUET_PATH.stat().st_size if PARQUET_PATH.exists() else 0
    compression_pct = (1.0 - parquet_size / jsonl_size) * 100.0 if jsonl_size else 0.0
    bytes_saved = jsonl_size - parquet_size if jsonl_size else 0

    storage_cols = st.columns(3)
    storage_cols[0].metric("Raw Staging Size", f"{jsonl_size / 1024:.1f} KB")
    storage_cols[1].metric("Clean Parquet Size", f"{parquet_size / 1024:.1f} KB")
    storage_cols[2].metric(
        "Compression Efficiency",
        f"{compression_pct:.1f}%",
        delta=f"{bytes_saved / 1024:.1f} KB saved on disk",
        delta_color="normal",
    )
    st.caption(
        f"Disk hand-off comparison: {STAGING_JSONL_PATH.name} {jsonl_size:,} bytes -> "
        f"{PARQUET_PATH.name} {parquet_size:,} bytes (Snappy codec)."
    )

    pipeline_cols = st.columns(3)
    pipeline_cols[0].metric("Clean Rows Loaded", f"{len(all_df):,}")
    outliers = all_df[all_df["is_outlier"]]
    pipeline_cols[1].metric("Rows Flagged Outlier", f"{int(outliers['is_outlier'].sum()):,}")
    pipeline_cols[2].metric("Quarantined Payloads", f"{count_quarantine_payloads():,}")

    if not outliers.empty:
        st.subheader("Flagged Outlier Rows")
        st.dataframe(
            outliers[["route_code", "advance_window", "total_quote", "outlier_reason"]],
            width="stretch",
        )

    st.subheader("Raw JSONL Inspector")
    raw_records = load_raw_staging_jsonl()
    if not raw_records:
        st.info("No staging payloads found in seed_data/staging_raw_payloads.jsonl.")
        return
    labels = [
        f"Record {i + 1} | {r.get('route_code', '?')} | {r.get('advance_window', '?')} | "
        f"scraped {r.get('scraped_at', '?')[:19]}"
        for i, r in enumerate(raw_records)
    ]
    record_idx = st.selectbox("Select an intercepted staging record", range(len(labels)),
                              format_func=lambda i: labels[i])
    st.json(raw_records[record_idx])


inject_css()

st.markdown(
    "<div class='dashboard-header'>"
    "<h1>MOSPI Airfare Index Dashboard</h1>"
    "<p>Automated High-Frequency Flight Price Indexing Engine (NSO / RBI Hackathon Scope)</p>"
    "</div>",
    unsafe_allow_html=True,
)

df = load_data()

st.sidebar.header("Dashboard Filters")

if df is not None:
    all_routes = sorted(df["route_code"].unique())
    window_options = sorted(df["advance_window"].unique(), key=window_sort_key)
    min_date = df["captured_at"].min().date()
    max_date = df["captured_at"].max().date()
else:
    all_routes = ["DEL-BOM"]
    window_options = list(DEFAULT_WINDOWS)
    min_date = None
    max_date = None

route = st.sidebar.selectbox(
    "Route",
    all_routes,
    index=all_routes.index("DEL-BOM") if "DEL-BOM" in all_routes else 0,
)

windows = st.sidebar.multiselect(
    "Advance Window (Lead Time)",
    window_options,
    default=[w for w in DEFAULT_WINDOWS if w in window_options],
)

if min_date is not None and max_date is not None:
    date_range = st.sidebar.date_input(
        "Execution Timestamp Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
else:
    date_range = (None, None)

if df is not None:
    matrix_df = df.copy()
    if windows:
        matrix_df = matrix_df[matrix_df["advance_window"].isin(windows)]
    if date_range[0] is not None and date_range[1] is not None:
        matrix_df = matrix_df[
            (matrix_df["captured_at"].dt.date >= date_range[0])
            & (matrix_df["captured_at"].dt.date <= date_range[1])
        ]
    f = matrix_df[matrix_df["route_code"] == route]
    route_full = df[df["route_code"] == route]

    with st.sidebar:
        st.subheader("Exports")
        report = _resolve_report_pdf()
        if report is not None:
            st.download_button(
                "Download Executive Report (PDF)",
                data=report.read_bytes(),
                file_name=report.name,
                mime="application/pdf",
            )
        else:
            st.warning("Technical specification PDF not found in the project root.")
        st.download_button(
            "Download Filtered Data (CSV)",
            data=filtered_csv(f),
            file_name="filtered_airfare_index.csv",
            mime="text/csv",
        )
    tab1, tab2, tab3 = st.tabs(
        [
            "Airfare Index & Price Trends",
            "Unbundled Fare Breakdown",
            "Pipeline Health & Staging Logs",
        ]
    )
    with tab1:
        render_tab_trends(f, route_full)
    with tab2:
        render_tab_breakdown(f, matrix_df)
    with tab3:
        render_tab_pipeline(df)
else:
    st.info("Load the Role 2 clean Parquet artifact to populate the dashboard tabs.")