import pandas as pd
import plotly.graph_objects as go

# Soft, muted palette inspired by modern analytics dashboards
WINDOW_PALETTE = {
    "T+1": "#6366F1",  # Indigo
    "T+2": "#8B5CF6",  # Violet
    "T+3": "#3B82F6",  # Blue
    "T+4": "#06B6D4",  # Cyan
    "T+5": "#10B981",  # Emerald
    "T+7": "#F59E0B",  # Amber
    "T+15": "#EC4899",  # Pink
    "T+30": "#EF4444",  # Red
    "T+45": "#94A3B8",  # Slate
}

WINDOW_FILL = {
    "T+1": "rgba(99, 102, 241, 0.08)",
    "T+2": "rgba(139, 92, 246, 0.08)",
    "T+3": "rgba(59, 130, 246, 0.08)",
    "T+4": "rgba(6, 182, 212, 0.08)",
    "T+5": "rgba(16, 185, 129, 0.08)",
    "T+7": "rgba(245, 158, 11, 0.08)",
    "T+15": "rgba(236, 72, 153, 0.08)",
    "T+30": "rgba(239, 68, 68, 0.08)",
    "T+45": "rgba(148, 163, 184, 0.08)",
}

CALENDAR_LABELS = {
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

_LAYOUT_FONT = "Inter, -apple-system, BlinkMacSystemFont, sans-serif"


def _window_sort(window: str) -> int:
    try:
        return int(window[2:])
    except Exception:
        return 999


def build_trend_figure(
    df: pd.DataFrame,
    baseline_mean: float | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    """Clean area-line trend chart with gradient fills per advance window."""
    df = df.copy()

    fig = go.Figure()

    windows = sorted(df["advance_window"].unique(), key=_window_sort)

    for window in windows:
        sub = df[df["advance_window"] == window].sort_values("departure_date")
        color = WINDOW_PALETTE.get(window, "#94A3B8")
        fill_color = WINDOW_FILL.get(window, "rgba(148, 163, 184, 0.08)")
        label = CALENDAR_LABELS.get(window, window)

        # Area fill trace (gradient effect)
        fig.add_trace(
            go.Scatter(
                x=sub["departure_date"],
                y=sub["total_quote"],
                mode="lines",
                name=label,
                line=dict(width=2.5, color=color, shape="spline", smoothing=1.3),
                fill="tozeroy",
                fillcolor=fill_color,
                customdata=sub[["base_fare", "tax_udf", "advance_window"]].to_numpy(),
                hovertemplate=(
                    "<b>%{x|%b %d}</b><br>"
                    "Total: <b>₹%{y:,.0f}</b><br>"
                    "Base: <b>₹%{customdata[0]:,.0f}</b><br>"
                    "Tax: <b>₹%{customdata[1]:,.0f}</b>"
                    "<extra>" + label + "</extra>"
                ),
            )
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
            tickformat="%b %d",
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
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=12,
            font_family=_LAYOUT_FONT,
            font_color="#0F172A",
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
            itemsizing="constant",
        ),
        margin=dict(l=10, r=10, t=30, b=10),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig