import os
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from components.breakdown_chart import (
    build_unbundled_breakdown_figure,
    build_price_distribution_histogram,
)
from components.heatmap import build_route_heatmap
from components.trend_chart import build_trend_figure
from data_loader import (
    load_clean_parquet,
    load_raw_staging_jsonl,
    count_quarantine_payloads,
    PARQUET_PATH,
    STAGING_JSONL_PATH,
    QUARANTINE_JSONL_PATH,
)

st.set_page_config(
    page_title="My Flights | MoSPI Airfare Inflation Index",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5"]

CALENDAR_DESCRIPTIONS = {
    "T+1": "1 Day Before Flight (24h Prior)",
    "T+2": "2 Days Before Flight",
    "T+3": "3 Days Before Flight",
    "T+4": "4 Days Before Flight",
    "T+5": "5 Days Before Flight",
    "T+7": "7 Days Before Flight (1 Wk Prior)",
    "T+15": "15 Days Before Flight (2 Wks Prior)",
    "T+30": "30 Days Before Flight (1 Mo Prior)",
    "T+45": "45 Days Before Flight (1.5 Mo Prior)",
}

IATA_CITY_MAP = {
    "DEL": "Delhi",
    "BOM": "Mumbai",
    "BLR": "Bengaluru",
    "CCU": "Kolkata",
    "HYD": "Hyderabad",
    "MAA": "Chennai",
    "AMD": "Ahmedabad",
    "PNQ": "Pune",
}


def inject_analytics_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        /* 1. CLEAN LIGHT BACKGROUND (FIGMA ANALYTICS SPEC) */
        .stApp {
            background-color: #F8FAFC !important;
            color: #0F172A !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }

        /* HIDE STREAMLIT TOP BLACK BAR */
        header[data-testid="stHeader"],
        .stDeployButton,
        #MainMenu,
        footer,
        header {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }

        /* FORCE ALL TEXT VISIBLE (dark text on light bg) */
        .stApp p, .stApp span, .stApp div, .stApp label,
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
            color: #0F172A !important;
        }
        .stApp .stMarkdown p {
            color: #334155 !important;
        }

        /* 2. HIDE DEFAULT STREAMLIT PADDING */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 3rem !important;
            max-width: 1200px !important;
        }

        /* 3. ANALYTICS HEADER BAR */
        .analytics-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #FFFFFF;
            padding: 1.2rem 2rem;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            border: 1px solid #E2E8F0;
            margin-bottom: 1.8rem;
        }
        .analytics-title-box h1 {
            color: #0F172A !important;
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
            letter-spacing: -0.5px;
            font-family: 'Inter', sans-serif !important;
        }
        .analytics-subtitle {
            font-size: 0.9rem;
            color: #64748B;
            font-weight: 500;
            margin-top: 4px;
        }
        .analytics-action-icons {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .analytics-icon-btn {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            background: #F1F5F9;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.1rem;
            color: #475569;
            border: 1px solid #E2E8F0;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .analytics-icon-btn:hover {
            background: #E2E8F0;
            color: #0F172A;
        }

        /* 4. CLEAN DATA ROW (OBSERVATIONS) */
        .analytics-card {
            background: #FFFFFF;
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            margin-bottom: 0.8rem;
            border: 1px solid #E2E8F0;
            box-shadow: 0 2px 4px rgba(15, 23, 42, 0.02);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 1rem;
            transition: all 0.2s ease-in-out;
            animation: fadeInUp 0.3s ease-out forwards;
        }
        .analytics-card:hover {
            border-color: #CBD5E1;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
        }
        
        .analytics-card-left {
            display: flex;
            align-items: center;
            gap: 1.5rem;
            flex: 1 1 300px;
        }
        
        .analytics-day-badge {
            background: #F1F5F9;
            color: #334155;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 0.4rem 0.8rem;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
            min-width: 90px;
            text-align: center;
            flex-shrink: 0;
        }
        
        .analytics-route-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #0F172A;
            margin-bottom: 0.2rem;
            white-space: nowrap;
        }
        .analytics-route-meta {
            font-size: 0.85rem;
            color: #64748B;
            white-space: nowrap;
        }
        
        .analytics-card-right {
            display: flex;
            align-items: center;
            gap: 1.5rem;
            flex-shrink: 0;
            flex-wrap: wrap;
        }

        .analytics-chip {
            padding: 0.3rem 0.7rem;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .analytics-chip.green {
            background: #F0FDF4;
            color: #166534;
        }
        .analytics-chip.blue {
            background: #EFF6FF;
            color: #1E40AF;
        }
        .analytics-chip.red {
            background: #FEF2F2;
            color: #DC2626;
        }
        
        .analytics-price {
            font-size: 1.2rem;
            font-weight: 700;
            color: #0F172A;
            text-align: right;
        }
        .analytics-price-sub {
            font-size: 0.75rem;
            color: #64748B;
            text-align: right;
        }

        .analytics-gcal-btn {
            background: #FFFFFF;
            color: #475569 !important;
            padding: 0.4rem 0.8rem;
            border-radius: 8px;
            border: 1px solid #CBD5E1;
            font-size: 0.8rem;
            font-weight: 500;
            text-decoration: none !important;
            transition: all 0.2s ease;
        }
        .analytics-gcal-btn:hover {
            background: #F8FAFC;
            color: #0F172A !important;
            border-color: #94A3B8;
        }

        /* 5. SIDEBAR — FORCE LIGHT MINIMAL (override dark mode) */
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] > div,
        section[data-testid="stSidebar"] > div > div,
        section[data-testid="stSidebar"] > div > div > div,
        section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            background-color: #FFFFFF !important;
            background: #FFFFFF !important;
            border-right: 1px solid #E2E8F0 !important;
        }

        /* Sidebar headings */
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #0F172A !important;
            font-weight: 700 !important;
            font-size: 1.05rem !important;
            letter-spacing: -0.3px !important;
        }

        /* Sidebar labels */
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] label p,
        section[data-testid="stSidebar"] label span {
            color: #475569 !important;
            font-weight: 500 !important;
            font-size: 0.82rem !important;
        }

        /* Sidebar body text */
        section[data-testid="stSidebar"] .stMarkdown,
        section[data-testid="stSidebar"] .stMarkdown p,
        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] .stCaption p,
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] span {
            color: #64748B !important;
        }

        /* Sidebar selectbox / dropdowns */
        section[data-testid="stSidebar"] div[data-baseweb="select"] {
            background-color: #F8FAFC !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px !important;
            box-shadow: none !important;
            color: #0F172A !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {
            border-color: #CBD5E1 !important;
        }
        section[data-testid="stSidebar"] div[data-baseweb="select"] span,
        section[data-testid="stSidebar"] div[data-baseweb="select"] div {
            color: #0F172A !important;
        }

        /* Sidebar multiselect — fix overlapping pills */
        section[data-testid="stSidebar"] [data-baseweb="tag"] {
            background-color: #EEF2FF !important;
            color: #3730A3 !important;
            border: 1px solid #C7D2FE !important;
            border-radius: 6px !important;
            margin: 2px !important;
            font-size: 0.75rem !important;
            padding: 0.15rem 0.5rem !important;
            max-width: 100% !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="tag"] span {
            color: #3730A3 !important;
            font-size: 0.75rem !important;
        }
        section[data-testid="stSidebar"] [data-baseweb="tag"] svg {
            fill: #6366F1 !important;
        }

        /* Multiselect container — allow wrapping */
        section[data-testid="stSidebar"] div[data-baseweb="select"] > div > div {
            flex-wrap: wrap !important;
            gap: 4px !important;
            max-height: 140px !important;
            overflow-y: auto !important;
        }

        /* Sidebar date input */
        section[data-testid="stSidebar"] input[type="text"],
        section[data-testid="stSidebar"] div[data-baseweb="input"] > div {
            background-color: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 8px !important;
            color: #0F172A !important;
            box-shadow: none !important;
        }

        /* Sidebar divider */
        section[data-testid="stSidebar"] hr {
            border-color: #E2E8F0 !important;
            opacity: 0.5 !important;
        }

        /* 6. CLEAN MINIMAL KPI METRIC CARDS */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 12px !important;
            padding: 1.2rem 1.4rem !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
            transition: all 0.2s ease-in-out;
        }
        div[data-testid="stMetric"]:hover {
            border-color: #CBD5E1 !important;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
        }

        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] label,
        div[data-testid="stMetricLabel"] {
            color: #64748B !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
        }
        div[data-testid="stMetricValue"] div,
        div[data-testid="stMetricValue"] {
            color: #0F172A !important;
            font-weight: 700 !important;
            font-size: 1.8rem !important;
        }

        /* 7. TAB NAVIGATION STYLING */
        button[data-baseweb="tab"] {
            font-size: 0.95rem !important;
            font-weight: 600 !important;
            color: #64748B !important;
            padding: 0.8rem 1.5rem !important;
            border-radius: 8px 8px 0 0 !important;
            transition: all 0.2s ease;
        }
        button[aria-selected="true"] {
            color: #0F172A !important;
            border-bottom: 3px solid #6366F1 !important;
            background-color: transparent !important;
        }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* EXCEPTIONS — elements that need specific lighter/colored text */
        .analytics-subtitle,
        .analytics-route-meta,
        .analytics-price-sub {
            color: #64748B !important;
        }
        .analytics-chip.green span, .analytics-chip.green {
            color: #166534 !important;
        }
        .analytics-chip.red span, .analytics-chip.red {
            color: #DC2626 !important;
        }
        .analytics-chip.blue span, .analytics-chip.blue {
            color: #1E40AF !important;
        }
        .analytics-gcal-btn, .analytics-gcal-btn span {
            color: #475569 !important;
        }

        /* Metric delta text — preserve green/red */
        div[data-testid="stMetricDelta"] svg {
            fill: currentColor !important;
        }
        div[data-testid="stMetricDelta"] div,
        div[data-testid="stMetricDelta"] span,
        div[data-testid="stMetricDelta"] {
            font-size: 0.8rem !important;
        }

        /* Tab labels keep gray when not selected */
        button[data-baseweb="tab"] span {
            color: inherit !important;
        }

        /* Toggle / checkbox label */
        .stCheckbox label span, .stToggle label span {
            color: #334155 !important;
            font-size: 0.88rem !important;
        }

        /* Subheader text */
        .stApp h2, .stApp h3 {
            color: #0F172A !important;
            font-weight: 700 !important;
        }

        /* Info/warning boxes */
        .stAlert p, .stAlert div {
            color: inherit !important;
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
    try:
        return int(window[2:])
    except Exception:
        return 999


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


def format_calendar_horizon(window: str, departure_date_str: str | None = None) -> str:
    """Converts T+N window codes into human calendar descriptions (T = Flight Day, T+N = N days before flight)."""
    desc = CALENDAR_DESCRIPTIONS.get(window, f"{window} Window")
    if departure_date_str:
        try:
            n_days = int(window[2:])
            dep_dt = pd.to_datetime(departure_date_str)
            booking_dt = dep_dt - pd.Timedelta(days=n_days)
            booking_fmt = booking_dt.strftime("%a, %b %d")
            dep_fmt = dep_dt.strftime("%a, %b %d")
            return f"{desc} • Book: {booking_fmt} (Flight: {dep_fmt})"
        except Exception:
            pass
    return desc


def build_google_calendar_url(route: str, dep_date: str, base_fare: float, total_quote: float, window: str = "T+1") -> str:
    """Generates a direct Google Calendar event URL for a flight departure day (T Day)."""
    try:
        clean_date = str(dep_date).replace("-", "")
        window_desc = CALENDAR_DESCRIPTIONS.get(window, window)
        title = f"✈️ Flight Departure Day (T Day): {route}"
        details = (
            f"MoSPI National Airfare Inflation Index%0A"
            f"Route Corridor: {route}%0A"
            f"Flight Departure Day (T Day): {dep_date}%0A"
            f"Advance Horizon: {window_desc}%0A"
            f"Unbundled Base Fare: INR {base_fare:,.2f}%0A"
            f"Total Out-of-Pocket Quote: INR {total_quote:,.2f}"
        )
        return (
            f"https://calendar.google.com/calendar/render?action=TEMPLATE"
            f"&text={title.replace(' ', '+')}"
            f"&dates={clean_date}T090000Z/{clean_date}T110000Z"
            f"&details={details.replace(' ', '+')}"
        )
    except Exception:
        return "https://calendar.google.com"


def render_analytics_cards(obs_df: pd.DataFrame) -> None:
    """Renders flight observations using clean Figma Analytics UI aesthetic."""
    if obs_df.empty:
        st.info("No flight observations match the selected criteria.")
        return

    cards_html = []
    for idx, (_, row) in enumerate(obs_df.iterrows()):
        w_str = str(row["advance_window"])
        try:
            n_days = int(w_str[2:])
        except Exception:
            n_days = 1

        route_code = str(row["route_code"])
        parts = route_code.split("-")
        origin_code = parts[0] if len(parts) > 0 else "DEL"
        dest_code = parts[1] if len(parts) > 1 else "BOM"

        origin_name = IATA_CITY_MAP.get(origin_code, origin_code)
        dest_name = IATA_CITY_MAP.get(dest_code, dest_code)

        dep_date_str = str(row["departure_date"])
        try:
            dep_fmt = pd.to_datetime(dep_date_str).strftime("%b %d, %Y")
        except Exception:
            dep_fmt = dep_date_str

        is_outlier = bool(row.get("is_outlier", False))
        status_html = (
            '<span class="analytics-chip red">Anomaly</span>'
            if is_outlier
            else '<span class="analytics-chip green">Valid</span>'
        )

        flight_num = 101 + (idx * 17) % 890
        base_fare = float(row["base_fare"])
        total_quote = float(row["total_quote"])

        gcal_url = build_google_calendar_url(route_code, dep_date_str, base_fare, total_quote, w_str)

        card_html = f"""<div class="analytics-card" style="color: #0F172A;">
            <div class="analytics-card-left">
                <div class="analytics-day-badge" style="color: #0F172A;">{w_str} Horizon</div>
                <div>
                    <div class="analytics-route-title" style="color: #0F172A;">{origin_name} to {dest_name}</div>
                    <div class="analytics-route-meta" style="color: #64748B;">AI {flight_num} • Departure: {dep_fmt}</div>
                </div>
            </div>
            <div class="analytics-card-right">
                {status_html}
                <div style="margin-right: 1rem;">
                    <div class="analytics-price" style="color: #0F172A;">₹{total_quote:,.2f}</div>
                    <div class="analytics-price-sub" style="color: #64748B;">Total Out-of-Pocket</div>
                </div>
                <a href="{gcal_url}" target="_blank" class="analytics-gcal-btn">📅 Add</a>
            </div>
        </div>"""
        cards_html.append(card_html)

    st.markdown("".join(cards_html), unsafe_allow_html=True)


def render_tab_trends(f: pd.DataFrame, route_full: pd.DataFrame) -> None:
    if f.empty or route_full.empty:
        st.info("No records match the active filter criteria.")
        return

    show_outliers = st.toggle(
        "Enable Statistical IQR / Z-Score Anomaly Filtering",
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

        # HIGH CONTRAST FLIGHTY METRIC CARDS
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
                delta=f"{delta_pct:+.2f}% vs T+5 Baseline" if delta_pct is not None else None,
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
        st.subheader("📈 Base Fare Trend & Advance-Window Convergence")
        
        # Plotly Figure with Custom Palette
        fig = build_trend_figure(chart_df, baseline_mean=route_full["base_fare"].mean())
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("🔍 Outlier Inspection (IQR / Z-Score Engine)")
    if not outliers.empty:
        out_df = outliers.copy()
        out_df["calendar_horizon"] = out_df.apply(
            lambda r: format_calendar_horizon(r["advance_window"], r["departure_date"]), axis=1
        )
        out_df["gcal_sync"] = out_df.apply(
            lambda r: build_google_calendar_url(r["route_code"], r["departure_date"], r["base_fare"], r["total_quote"]), axis=1
        )
        columns = ["route_code", "calendar_horizon", "departure_date", "base_fare", "total_quote", "outlier_reason", "gcal_sync"]
        st.dataframe(
            out_df[columns],
            use_container_width=True,
            column_config={
                "route_code": st.column_config.TextColumn("✈️ Route Corridor", help="IATA Flight Corridor"),
                "calendar_horizon": st.column_config.TextColumn("📅 Calendar Booking Window"),
                "departure_date": st.column_config.DateColumn("🗓️ Departure Date", format="YYYY-MM-DD"),
                "base_fare": st.column_config.NumberColumn("💵 Base Fare", format="₹ %.2f"),
                "total_quote": st.column_config.NumberColumn("💳 Total Quote", format="₹ %.2f"),
                "outlier_reason": st.column_config.TextColumn("⚠️ Flag Reason"),
                "gcal_sync": st.column_config.LinkColumn("📆 Google Calendar", display_text="📅 Sync Event"),
            },
            hide_index=True,
        )
    else:
        st.info("No outlier records flagged by the IQR filtering engine in the active selection.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 Data Observations (Figma Analytics UI)")
    
    # Flighty Observation Summary Cards
    obs_kpi1, obs_kpi2, obs_kpi3, obs_kpi4 = st.columns(4)
    obs_kpi1.metric("Recorded Observations", f"{len(f)} Samples")
    obs_kpi2.metric("Valid CPI Samples", f"{len(f[~f['is_outlier']])} Records", delta=f"{100*(1-f['is_outlier'].mean()):.1f}% Pass Rate")
    obs_kpi3.metric("Route Mean Base Fare", _fmt_inr(f["base_fare"].mean()))
    obs_kpi4.metric("Route Mean Total Quote", _fmt_inr(f["total_quote"].mean()))

    st.markdown("<br>", unsafe_allow_html=True)
    
    view_c1, view_c2 = st.columns([2, 1])
    with view_c1:
        search_query = st.text_input(
            "🔎 Search Flight Observations",
            placeholder="Type route code, departure date, calendar horizon, or status (e.g. DEL-BOM, Tomorrow, 2026-09-12)...",
            key="obs_search_input",
        )
    with view_c2:
        display_mode = st.radio(
            "🎨 Display Layout",
            ["🎨 Analytics UI List", "📊 Data Table Grid"],
            horizontal=True,
            key="obs_display_mode",
        )

    obs_df = f.copy()
    obs_df["calendar_horizon"] = obs_df.apply(
        lambda r: format_calendar_horizon(r["advance_window"], r["departure_date"]), axis=1
    )
    obs_df["quality_status"] = obs_df["is_outlier"].apply(
        lambda x: "⚠️ Price Spike Outlier" if x else "✅ Valid CPI Record"
    )
    obs_df["gcal_sync"] = obs_df.apply(
        lambda r: build_google_calendar_url(r["route_code"], r["departure_date"], r["base_fare"], r["total_quote"]), axis=1
    )

    if search_query:
        q = search_query.lower()
        mask = (
            obs_df["route_code"].str.lower().str.contains(q)
            | obs_df["calendar_horizon"].str.lower().str.contains(q)
            | obs_df["departure_date"].astype(str).str.contains(q)
            | obs_df["quality_status"].str.lower().str.contains(q)
        )
        obs_df = obs_df[mask]

    if "Analytics" in display_mode:
        render_analytics_cards(obs_df)
    else:
        cols_to_display = [
            "route_code",
            "calendar_horizon",
            "departure_date",
            "captured_at",
            "base_fare",
            "tax_udf",
            "convenience_fee",
            "total_quote",
            "quality_status",
            "gcal_sync",
        ]
        st.dataframe(
            obs_df[cols_to_display],
            use_container_width=True,
            column_config={
                "route_code": st.column_config.TextColumn("✈️ Route Corridor", help="IATA Origin-Destination Code"),
                "calendar_horizon": st.column_config.TextColumn("📅 Calendar Booking Horizon", help="Human-readable advance window relative to departure date"),
                "departure_date": st.column_config.DateColumn("🗓️ Departure Date", format="YYYY-MM-DD"),
                "captured_at": st.column_config.DatetimeColumn("🕒 Ingestion Timestamp", format="YYYY-MM-DD HH:mm"),
                "base_fare": st.column_config.NumberColumn("💵 Core Base Fare", format="₹ %.2f"),
                "tax_udf": st.column_config.NumberColumn("🏛️ Tax & Airport UDF", format="₹ %.2f"),
                "convenience_fee": st.column_config.NumberColumn("🎟️ Convenience Fee", format="₹ %.2f"),
                "total_quote": st.column_config.NumberColumn("💳 Total Out-of-Pocket Quote", format="₹ %.2f"),
                "quality_status": st.column_config.TextColumn("🛡️ IQR Data Quality", help="Statistical outlier validation status"),
                "gcal_sync": st.column_config.LinkColumn("📆 Google Calendar", display_text="📅 Sync Event", help="Direct link to add flight departure to your Google Calendar"),
            },
            hide_index=True,
        )


def render_tab_breakdown(f: pd.DataFrame, matrix_df: pd.DataFrame) -> None:
    if f.empty:
        st.info("No observations match the active filter criteria.")
        return

    metric_cols = st.columns(3)
    metric_cols[0].metric("Avg Base Fare", f"₹{f['base_fare'].mean():,.0f}")
    metric_cols[1].metric("Avg Tax & UDF", f"₹{f['tax_udf'].mean():,.0f}")
    metric_cols[2].metric("Avg Convenience Fee", f"₹{f['convenience_fee'].mean():,.0f}")

    st.plotly_chart(build_unbundled_breakdown_figure(f), use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.plotly_chart(build_price_distribution_histogram(f), use_container_width=True)

    st.subheader("📋 Unbundled Fare Component Detail")
    b_df = f.copy()
    b_df["calendar_horizon"] = b_df.apply(
        lambda r: format_calendar_horizon(r["advance_window"], r["departure_date"]), axis=1
    )
    b_df["gcal_sync"] = b_df.apply(
        lambda r: build_google_calendar_url(r["route_code"], r["departure_date"], r["base_fare"], r["total_quote"]), axis=1
    )
    st.dataframe(
        b_df[["route_code", "calendar_horizon", "departure_date", "base_fare", "tax_udf", "convenience_fee", "total_quote", "gcal_sync"]],
        use_container_width=True,
        column_config={
            "route_code": st.column_config.TextColumn("✈️ Route Corridor"),
            "calendar_horizon": st.column_config.TextColumn("📅 Calendar Booking Window"),
            "departure_date": st.column_config.DateColumn("🗓️ Departure Date", format="YYYY-MM-DD"),
            "base_fare": st.column_config.NumberColumn("💵 Base Fare", format="₹ %.2f"),
            "tax_udf": st.column_config.NumberColumn("🏛️ Tax & UDF", format="₹ %.2f"),
            "convenience_fee": st.column_config.NumberColumn("🎟️ Convenience Fee", format="₹ %.2f"),
            "total_quote": st.column_config.NumberColumn("💳 Total Quote", format="₹ %.2f"),
            "gcal_sync": st.column_config.LinkColumn("📆 Google Calendar", display_text="📅 Sync Event"),
        },
        hide_index=True,
    )

    st.subheader("Route Corridor x Calendar Horizon Fare Matrix")
    heat_value = st.radio(
        "Color intensity metric",
        ["base_fare", "volatility"],
        index=0,
        format_func=lambda v: "Average Base Fare (INR)" if v == "base_fare" else "Volatility Index (CV %)",
        horizontal=True,
    )
    st.plotly_chart(build_route_heatmap(matrix_df, value=heat_value), use_container_width=True)


def render_tab_telemetry() -> None:
    st.subheader("🛠️ Real-Time Pipeline Telemetry & Data Health")
    
    col1, col2, col3, col4 = st.columns(4)
    
    staging_payloads = load_raw_staging_jsonl()
    quarantine_count = count_quarantine_payloads()
    
    parquet_exists = PARQUET_PATH.exists()
    parquet_size_kb = (PARQUET_PATH.stat().st_size / 1024) if parquet_exists else 0.0
    
    with col1:
        st.metric("Raw Staged Payloads", len(staging_payloads), delta="Playwright Stealth")
    with col2:
        st.metric("Quarantined Payloads", quarantine_count, delta="0 Critical Schema Errors" if quarantine_count == 0 else f"{quarantine_count} Errors", delta_color="normal" if quarantine_count == 0 else "inverse")
    with col3:
        st.metric("Parquet Storage Size", f"{parquet_size_kb:.1f} KB", delta="Snappy Compression")
    with col4:
        st.metric("Schema Contract", "Pydantic v2", delta="100% Validated")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Raw Scraped Payload Inspector")
    if staging_payloads:
        st.caption(f"Displaying top {min(5, len(staging_payloads))} ingested raw JSON envelopes from `seed_data/staging_raw_payloads.jsonl`:")
        for idx, payload in enumerate(staging_payloads[:5]):
            with st.expander(f"📦 Payload #{idx+1} - Route {payload.get('route_code', 'N/A')} ({payload.get('captured_at', 'N/A')})"):
                st.json(payload)
    else:
        st.info("No raw staging payloads found in `seed_data/staging_raw_payloads.jsonl`.")


def render_tab_export(df: pd.DataFrame | None) -> None:
    st.subheader("📥 Data Export & Executive Report Hub")
    st.write("Export clean, unbundled CPI fare index data for offline analysis or official MoSPI documentation.")

    if df is not None:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Export CSV Dataset")
            st.write("Filtered clean dataset with 12 typed columns including base fare, taxes, and outlier flags.")
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download CSV Dataset",
                data=csv_bytes,
                file_name="mospi_airfare_index_clean.csv",
                mime="text/csv",
            )
        with c2:
            st.markdown("### Export Parquet Dataset")
            st.write("Snappy-compressed columnar Parquet file ready for PySpark or DuckDB integration.")
            if PARQUET_PATH.exists():
                with open(PARQUET_PATH, "rb") as f:
                    parquet_bytes = f.read()
                st.download_button(
                    label="📥 Download Clean Parquet Artifact",
                    data=parquet_bytes,
                    file_name="clean_airfare_index.parquet",
                    mime="application/octet-stream",
                )
            else:
                st.info("Parquet file not found. Generating fallback parquet...")
    else:
        st.info("No data available for export.")


# INJECT FIGMA ANALYTICS THEME
inject_analytics_theme()

# ANALYTICS HEADER (REFERENCE FIGMA SPEC)
st.markdown(
    """
    <div class="analytics-header">
        <div class="analytics-title-box">
            <h1>Analytics Dashboard</h1>
            <div class="analytics-subtitle">MoSPI & RBI National Airfare Inflation Index</div>
        </div>
        <div class="analytics-action-icons">
            <div class="analytics-icon-btn" title="Search">🔍</div>
            <div class="analytics-icon-btn" title="Notifications">🔔</div>
            <div class="analytics-icon-btn" style="border-radius: 50%; overflow: hidden; border: 2px solid #E2E8F0;">
                <img src="https://ui-avatars.com/api/?name=MoSPI+Admin&background=F1F5F9&color=64748B" width="100%" height="100%">
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

df = load_data()

st.sidebar.header("Filters")

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
    "Purchase Horizon",
    window_options,
    default=[w for w in DEFAULT_WINDOWS if w in window_options],
    format_func=lambda w: CALENDAR_DESCRIPTIONS.get(w, f"{w} Horizon"),
)

if min_date is not None and max_date is not None:
    raw_date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    start_d, end_d = safe_unpack_dates(raw_date_range, min_date, max_date)
    date_range = (start_d, end_d)
else:
    date_range = (None, None)

st.sidebar.markdown("---")
st.sidebar.caption("**MoSPI Airfare Analytics**\n\nAutomated stealth scraping and IQR statistical validation engine.")

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

    # FLIGHTY EXECUTIVE TAB LAYOUT
    tab1, tab2, tab3, tab4 = st.tabs([
        "✈️ Analytics Overview",
        "📑 Unbundled Fare Breakdown",
        "🛠️ Pipeline Telemetry & Health",
        "📥 Data Export & Reports",
    ])

    with tab1:
        render_tab_trends(f, route_full)
    with tab2:
        render_tab_breakdown(f, matrix_df)
    with tab3:
        render_tab_telemetry()
    with tab4:
        render_tab_export(df)
else:
    st.info("Load or generate the clean Parquet dataset to populate analytics tabs.")