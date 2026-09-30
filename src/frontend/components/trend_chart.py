import pandas as pd
import plotly.graph_objects as go

_LAYOUT_FONT = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"


def build_trend_figure(
    df: pd.DataFrame,
    baseline_mean: float | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    """
    Builds a 100% Dynamic Chronological Base Fare Trend Graph.
    - Plots pure unbundled Base Fare (INR) aligned with MoSPI CPI index rules.
    - Uses smooth Y-axis auto-scaling to prevent minor price variations from looking like exaggerated spikes.
    - Works for any user-selected date window (past, future, mixed).
    """
    df = df.copy()
    fig = go.Figure()

    if df.empty:
        fig.update_layout(
            template=template,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=380,
        )
        return fig

    # Date column normalization
    if "departure_dt" in df.columns:
        df["dep_date"] = pd.to_datetime(df["departure_dt"])
    else:
        df["dep_date"] = pd.to_datetime(df["departure_date"])

    # Dynamic grouping across whatever departure dates exist in the user-selected window
    agg = (
        df.groupby("dep_date", as_index=False)
        .agg(
            avg_base=("base_fare", "mean"),
            avg_total=("total_quote", "mean"),
            avg_tax=("tax_udf", "mean"),
            advance_window=("advance_window", "first"),
            sample_count=("base_fare", "count"),
        )
        .sort_values("dep_date")
    )

    agg["formatted_date"] = agg["dep_date"].dt.strftime("%b %d")
    agg["full_date_str"] = agg["dep_date"].dt.strftime("%Y-%m-%d")

    # Main Base Fare Trend Line (Pure carrier fare matching booking apps)
    fig.add_trace(
        go.Scatter(
            x=agg["formatted_date"],
            y=agg["avg_base"],
            mode="lines+markers+text",
            name="Base Fare Trend",
            text=[f"₹{val:,.0f}" for val in agg["avg_base"]],
            textposition="top center",
            textfont=dict(size=11, color="#0F172A", family=_LAYOUT_FONT),
            line=dict(width=3.5, color="#6366F1", shape="spline", smoothing=1.1),
            marker=dict(size=8, color="#4338CA", symbol="circle", line=dict(width=2, color="#FFFFFF")),
            fill="tozeroy",
            fillcolor="rgba(99, 102, 241, 0.05)",
            customdata=agg[["avg_total", "avg_tax", "advance_window", "full_date_str", "sample_count"]].to_numpy(),
            hovertemplate=(
                "<b>Date: %{customdata[3]} (%{x})</b><br>"
                "Unbundled Base Fare: <b>₹%{y:,.0f}</b><br>"
                "Total Out-of-Pocket: <b>₹%{customdata[0]:,.0f}</b><br>"
                "Avg Tax & UDF: <b>₹%{customdata[1]:,.0f}</b><br>"
                "Horizon Tag: <b>%{customdata[2]}</b><br>"
                "Scraped Flights: <b>%{customdata[4]}</b>"
                "<extra>MoSPI Core Index</extra>"
            ),
        )
    )

    # Baseline Reference Line if available
    if baseline_mean is not None and baseline_mean > 0:
        fig.add_hline(
            y=baseline_mean,
            line_dash="dash",
            line_color="#94A3B8",
            line_width=1.5,
            annotation_text=f"Historical Base Benchmark (₹{baseline_mean:,.0f})",
            annotation_position="bottom left",
            annotation_font=dict(size=10, color="#64748B", family=_LAYOUT_FONT),
        )

    # Smooth Auto-scaling for Y-axis with realistic padding (prevents exaggerated mountain waves)
    min_val = agg["avg_base"].min()
    max_val = agg["avg_base"].max()
    padding = max((max_val - min_val) * 0.35, 1200)
    y_min = max(0, min_val - padding)
    y_max = max_val + padding

    fig.update_layout(
        template=template,
        title=dict(
            text="📈 Pure Base Fare Trend (Unbundled Carrier Price)",
            font=dict(size=14, color="#0F172A", family=_LAYOUT_FONT),
            x=0,
            y=0.98,
        ),
        xaxis=dict(
            title=dict(text="Flight Departure Dates (Chronological Order)", font=dict(size=11, color="#64748B", family=_LAYOUT_FONT)),
            showgrid=True,
            gridcolor="#F1F5F9",
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#475569", family=_LAYOUT_FONT),
        ),
        yaxis=dict(
            title=dict(text="Unbundled Base Fare (INR)", font=dict(size=11, color="#64748B", family=_LAYOUT_FONT)),
            showgrid=True,
            gridcolor="#E2E8F0",
            gridwidth=1,
            griddash="dot",
            zeroline=False,
            showline=False,
            range=[y_min, y_max],
            tickfont=dict(size=11, color="#64748B", family=_LAYOUT_FONT),
            tickprefix="₹",
            tickformat=",",
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=12,
            font_family=_LAYOUT_FONT,
            font_color="#0F172A",
            bordercolor="#CBD5E1",
        ),
        margin=dict(l=10, r=10, t=40, b=10),
        height=400,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )

    return fig