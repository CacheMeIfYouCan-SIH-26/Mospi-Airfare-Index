import numpy as np
import pandas as pd
import plotly.graph_objects as go

CALENDAR_MAP = {
    "T+1": "1 Day",
    "T+2": "2 Days",
    "T+3": "3 Days",
    "T+4": "4 Days",
    "T+5": "5 Days",
    "T+7": "1 Week",
    "T+15": "2 Weeks",
    "T+30": "1 Month",
    "T+45": "45 Days",
}

WINDOW_SORT = {"T+1": 1, "T+2": 2, "T+3": 3, "T+4": 4, "T+5": 5, "T+7": 7, "T+15": 15, "T+30": 30, "T+45": 45}

_LAYOUT_FONT = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"

# Soft color palette
_BAR_COLORS = ["#6366F1", "#3B82F6", "#10B981"]
_BAR_BORDERS = ["#4F46E5", "#2563EB", "#059669"]


def build_unbundled_breakdown_figure(f: pd.DataFrame, template: str = "plotly_white") -> go.Figure:
    """Clean minimal grouped bar chart for fare components."""
    df = f.copy()

    grouped = (
        df.groupby("advance_window")[["base_fare", "tax_udf", "convenience_fee"]]
        .mean()
        .reset_index()
    )
    grouped["sort_key"] = grouped["advance_window"].map(lambda w: WINDOW_SORT.get(w, 99))
    grouped = grouped.sort_values("sort_key")
    grouped["x_label"] = grouped["advance_window"].map(lambda w: CALENDAR_MAP.get(w, w))

    fig = go.Figure()

    components = [
        ("base_fare", "Base Fare", _BAR_COLORS[0], _BAR_BORDERS[0]),
        ("tax_udf", "Tax & UDF", _BAR_COLORS[1], _BAR_BORDERS[1]),
        ("convenience_fee", "Conv. Fee", _BAR_COLORS[2], _BAR_BORDERS[2]),
    ]

    for col, name, color, border in components:
        fig.add_trace(
            go.Bar(
                x=grouped["x_label"],
                y=grouped[col],
                name=name,
                marker=dict(
                    color=color,
                    line=dict(width=0),
                    cornerradius=6,
                    opacity=0.85,
                ),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + name + ": <b>₹%{y:,.0f}</b>"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        template=template,
        barmode="group",
        bargap=0.3,
        bargroupgap=0.08,
        title=None,
        xaxis=dict(
            title=None,
            showgrid=False,
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#94A3B8", family=_LAYOUT_FONT),
        ),
        yaxis=dict(
            title=None,
            showgrid=True,
            gridcolor="rgba(226, 232, 240, 0.5)",
            gridwidth=1,
            griddash="dot",
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#94A3B8", family=_LAYOUT_FONT),
            tickprefix="₹",
            tickformat=",",
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=12,
            font_color="#0F172A",
            font_family=_LAYOUT_FONT,
            bordercolor="#E2E8F0",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12, color="#475569", family=_LAYOUT_FONT),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        margin=dict(l=10, r=10, t=30, b=10),
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def build_price_distribution_histogram(df: pd.DataFrame, template: str = "plotly_white") -> go.Figure:
    """Clean minimal price distribution histogram with density overlay."""
    if df.empty:
        return go.Figure()

    prices = df["total_quote"].dropna().values
    mean_val = np.mean(prices)
    median_val = np.median(prices)

    fig = go.Figure()

    # Histogram bars
    fig.add_trace(
        go.Histogram(
            x=prices,
            name="Price Distribution",
            nbinsx=20,
            marker=dict(
                color="rgba(99, 102, 241, 0.6)",
                line=dict(width=1, color="rgba(99, 102, 241, 0.9)"),
                cornerradius=4,
            ),
            hovertemplate="Range: <b>₹%{x:,.0f}</b><br>Count: <b>%{y}</b><extra></extra>",
        )
    )

    # KDE overlay
    if len(prices) >= 5:
        try:
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(prices)
            x_vals = np.linspace(min(prices) * 0.9, max(prices) * 1.1, 200)
            kde_vals = kde(x_vals) * len(prices) * (max(prices) - min(prices)) / 20
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=kde_vals,
                    mode="lines",
                    name="Density",
                    line=dict(color="#EC4899", width=2.5, shape="spline"),
                    hoverinfo="skip",
                )
            )
        except Exception:
            pass

    # Mean line
    fig.add_vline(
        x=mean_val,
        line_width=2,
        line_dash="dash",
        line_color="#EF4444",
        annotation_text=f"Mean ₹{mean_val:,.0f}",
        annotation_position="top right",
        annotation_font=dict(size=10, color="#EF4444", family=_LAYOUT_FONT),
    )

    # Median line
    fig.add_vline(
        x=median_val,
        line_width=2,
        line_dash="dot",
        line_color="#10B981",
        annotation_text=f"Median ₹{median_val:,.0f}",
        annotation_position="top left",
        annotation_font=dict(size=10, color="#10B981", family=_LAYOUT_FONT),
    )

    fig.update_layout(
        template=template,
        title=None,
        xaxis=dict(
            title=None,
            showgrid=False,
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#94A3B8", family=_LAYOUT_FONT),
            tickprefix="₹",
            tickformat=",",
        ),
        yaxis=dict(
            title=None,
            showgrid=True,
            gridcolor="rgba(226, 232, 240, 0.5)",
            gridwidth=1,
            griddash="dot",
            zeroline=False,
            showline=False,
            tickfont=dict(size=11, color="#94A3B8", family=_LAYOUT_FONT),
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=12,
            font_color="#0F172A",
            font_family=_LAYOUT_FONT,
            bordercolor="#E2E8F0",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12, color="#475569", family=_LAYOUT_FONT),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
        ),
        margin=dict(l=10, r=10, t=30, b=10),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
