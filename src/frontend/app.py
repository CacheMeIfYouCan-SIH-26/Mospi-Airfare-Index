import pandas as pd
import plotly.express as px
import streamlit as st

from components.heatmap import build_route_heatmap
from components.trend_chart import build_trend_figure
from data_loader import load_clean_parquet

st.set_page_config(
    page_title="National Airfare Inflation Index | MoSPI & RBI Portal",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5"]


def inject_vibrant_indian_theme() -> None:
    st.markdown(
        """
        <style>
        /* 1. TRICOLOR TOP ACCENT BAR */
        .stApp::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 6px;
            background: linear-gradient(90deg, #FF9933 0%, #FF9933 33%, #FFFFFF 33%, #FFFFFF 66%, #138808 66%, #138808 100%);
            z-index: 999999;
        }

        /* 2. MAIN APP CANVAS - Crisp Govt Portal Theme */
        .stApp {
            background-color: #F8FAFC;
            color: #0F172A;
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        /* 3. NATIONAL GOVERNMENT PORTAL BANNER */
        .gov-banner {
            background: linear-gradient(135deg, #0A192F 0%, #1E3A8A 60%, #064E3B 100%);
            border-radius: 12px;
            padding: 1.6rem 2.2rem;
            margin-top: 0.6rem;
            margin-bottom: 1.8rem;
            box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.25);
            border-left: 8px solid #FF9933;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .gov-title-box h1 {
            color: #FFFFFF !important;
            font-size: 2.1rem !important;
            font-weight: 800 !important;
            margin: 0 !important;
            letter-spacing: -0.5px;
        }
        .gov-title-box p {
            color: #E2E8F0 !important;
            font-size: 1.0rem !important;
            margin-top: 0.4rem !important;
            font-weight: 500 !important;
        }
        .sih-badge {
            background: linear-gradient(135deg, #FF9933 0%, #D97706 100%);
            color: #FFFFFF;
            padding: 0.55rem 1.2rem;
            border-radius: 30px;
            font-size: 0.85rem;
            font-weight: 800;
            letter-spacing: 0.8px;
            box-shadow: 0 4px 12px rgba(217, 119, 6, 0.35);
            text-align: center;
            border: 1px solid #FDE68A;
        }

        /* 4. SIDEBAR STYLING */
        section[data-testid="stSidebar"] {
            background-color: #0F172A !important;
            border-right: 2px solid #E2E8F0 !important;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label {
            color: #F8FAFC !important;
            font-weight: 700 !important;
        }

        /* 5. VIBRANT HIGH-CONTRAST METRIC CARDS */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 12px !important;
            padding: 1.2rem 1.4rem !important;
            box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12) !important;
        }

        /* INDIVIDUAL CARD BORDER COLORWAYS */
        div[data-testid="stMetric"]:nth-child(1) { border-top: 6px solid #FF9933 !important; }
        div[data-testid="stMetric"]:nth-child(2) { border-top: 6px solid #1D4ED8 !important; }
        div[data-testid="stMetric"]:nth-child(3) { border-top: 6px solid #059669 !important; }
        div[data-testid="stMetric"]:nth-child(4) { border-top: 6px solid #7C3AED !important; }

        /* METRIC TYPOGRAPHY FIXES */
        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] label,
        div[data-testid="stMetricLabel"] {
            color: #1E293B !important;
            font-weight: 800 !important;
            font-size: 1.0rem !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        div[data-testid="stMetricValue"] div,
        div[data-testid="stMetricValue"] {
            color: #0F172A !important;
            font-weight: 900 !important;
            font-size: 2.0rem !important;
        }

        /* 6. TAB STYLING */
        button[data-baseweb="tab"] {
            font-size: 1.1rem !important;
            font-weight: 800 !important;
            color: #64748B !important;
            padding: 0.85rem 1.8rem !important;
            border-radius: 8px 8px 0 0 !important;
        }
        button[aria-selected="true"] {
            color: #1E3A8A !important;
            border-bottom: 4px solid #FF9933 !important;
            background-color: #FFFFFF !important;
            box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05);
        }

        /* 7. DATAFRAMES & CARDS */
        div[data-testid="stDataFrame"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_data() -> pd.DataFrame | None:
    df = load_clean_parquet()
    if df.empty:
        return None
    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True).dt.tz_localize(None)
    return df


def window_sort_key(window: str) -> int:
    return int(window[2:])


def _fmt_inr(value: float | None) -> str:
    return "N/A" if value is None else f"₹{value:,.2f}"


def safe_unpack_dates(raw_range, fallback_min, fallback_max):
    """Safely unpacks st.date_input tuples/lists to prevent IndexError."""
    if isinstance(raw_range, (list, tuple)):
        if len(raw_range) == 2:
            return raw_range[0], raw_range[1]
        elif len(raw_range) == 1:
            return raw_range[0], raw_range[0]
    elif raw_range is not None:
        return raw_range, raw_range
    return fallback_min, fallback_max


def render_tab_trends(f: pd.DataFrame, route_full: pd.DataFrame) -> None:
    if f.empty or route_full.empty:
        st.info("No records match the active filter criteria.")
        return

    show_outliers = st.toggle(
        "Show statistical price anomalies (IQR / Z-Score Engine)",
        value=True,
        help="Toggle price spikes flagged by the automated outlier engine to evaluate pure index stability.",
    )
    chart_df = f if show_outliers else f[~f["is_outlier"]]
    outliers = f[f["is_outlier"]]

    if chart_df.empty:
        st.warning("All records in this selection are flagged as outliers. Enable the toggle to inspect.")
    else:
        mean_base = chart_df["base_fare"].mean()
        ref_base_mean = route_full["base_fare"].mean()
        composite_index = (100.0 * mean_base / ref_base_mean) if ref_base_mean else 100.0

        baseline5_base = route_full.loc[route_full["advance_window"] == "T+5", "base_fare"]
        mean_base5 = baseline5_base.mean() if not baseline5_base.empty else None
        delta_pct = None
        if mean_base5 is not None and mean_base5:
            delta_pct = (mean_base - mean_base5) / mean_base5 * 100.0

        mean_total = chart_df["total_quote"].mean()
        quality_score = 100.0 * (1.0 - f["is_outlier"].mean()) if len(f) else 0.0

        # HIGH CONTRAST GOVERNMENT METRIC CARDS
        kpi = st.columns(4)

        with kpi[0]:
            st.metric(
                label="Base Fare Index",
                value=f"{composite_index:,.2f}",
                delta=f"{composite_index - 100.0:+.2f} pts vs Base 100",
                help="Laspeyres-style macro price index computed relative to historical route benchmark baseline (Base 100)."
            )

        with kpi[1]:
            st.metric(
                label="Avg Base Fare",
                value=_fmt_inr(mean_base),
                delta=f"{delta_pct:+.2f}% vs T+5 Horizon" if delta_pct is not None else None,
                help="Pure unbundled core airline fare set by carriers (excluding taxes and convenience fees)."
            )

        with kpi[2]:
            st.metric(
                label="Avg Total Quote",
                value=_fmt_inr(mean_total),
                delta=f"₹{mean_total - mean_base:,.2f} Taxes & Surcharges" if mean_total and mean_base else None,
                delta_color="off",
                help="Final out-of-pocket price paid by consumer (Base Fare + Statutory Taxes + Airport UDF)."
            )

        with kpi[3]:
            st.metric(
                label="Data Quality Score",
                value=f"{quality_score:.1f}%",
                delta="0 Quarantined" if quality_score == 100.0 else f"{100.0 - quality_score:.1f}% Outliers",
                help="Percentage of scraped records passing validation and statistical IQR outlier filtering."
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("Base Fare Trend & Advance-Window Convergence")
        
        # Plotly Figure with Custom Indian Flag Color Palette
        fig = build_trend_figure(chart_df, baseline_mean=route_full["base_fare"].mean())
        fig.update_layout(
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#F8FAFC",
            font=dict(color="#0F172A", family="Segoe UI"),
            margin=dict(l=30, r=30, t=50, b=30),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1.0,
                font=dict(color="#0F172A", size=11),
            ),
            colorway=["#FF9933", "#1E3A8A", "#138808", "#D97706", "#2563EB", "#059669"]
        )
        st.plotly_chart(fig, width="stretch")

    st.subheader("Outlier Inspection (IQR / Z-Score Engine)")
    if not outliers.empty:
        columns = ["route_code", "advance_window", "departure_date", "base_fare", "total_quote", "outlier_reason"]
        st.dataframe(
            outliers[columns],
            width="stretch",
            column_config={
                "base_fare": st.column_config.NumberColumn("Base Fare (INR)", format="₹ %.2f"),
                "total_quote": st.column_config.NumberColumn("Total Quote (INR)", format="₹ %.2f"),
            },
        )
    else:
        st.info("No outlier records flagged by the IQR filtering engine in the active selection.")

    st.subheader("Observation Detail")
    st.dataframe(
        f[["route_code", "advance_window", "departure_date", "captured_at", "base_fare", "total_quote", "is_outlier"]],
        width="stretch",
    )


def render_tab_breakdown(f: pd.DataFrame, matrix_df: pd.DataFrame) -> None:
    if f.empty:
        st.info("No observations match the active filter criteria.")
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
        ["base_fare", "volatility"],
        index=0,
        format_func=lambda v: "Average Base Fare" if v == "base_fare" else "Volatility Index (CV %)",
        horizontal=True,
    )
    st.plotly_chart(build_route_heatmap(matrix_df, value=heat_value), width="stretch")


# INJECT VIBRANT THEME
inject_vibrant_indian_theme()

# NATIONAL PORTAL HEADER
st.markdown(
    """
    <div class="gov-banner">
        <div class="gov-title-box">
            <h1>🇮🇳 Automated Real-Time Airfare Index</h1>
            <p>National CPI Inflation Tracking & Base Fare Analytics Engine | MoSPI & RBI Scope</p>
        </div>
        <div class="sih-badge">SIH PS ID: 26056</div>
    </div>
    """,
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
    "Route Corridor",
    all_routes,
    index=all_routes.index("DEL-BOM") if "DEL-BOM" in all_routes else 0,
)

windows = st.sidebar.multiselect(
    "Advance Purchase Window",
    window_options,
    default=[w for w in DEFAULT_WINDOWS if w in window_options],
)

if min_date is not None and max_date is not None:
    raw_date_range = st.sidebar.date_input(
        "Execution Timestamp Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    start_d, end_d = safe_unpack_dates(raw_date_range, min_date, max_date)
    date_range = (start_d, end_d)
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

    # CLEAN 2-TAB EXECUTIVE LAYOUT
    tab1, tab2 = st.tabs([
        "📊 Airfare Index & Price Trends",
        "📑 Unbundled Fare Breakdown",
    ])

    with tab1:
        render_tab_trends(f, route_full)
    with tab2:
        render_tab_breakdown(f, matrix_df)
else:
    st.info("Load or generate the clean Parquet dataset to populate analytics tabs.")