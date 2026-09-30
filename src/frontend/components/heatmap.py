import numpy as np
import pandas as pd
import plotly.graph_objects as go

SCOPE_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5"]


def _window_sort(window: str) -> int:
    try:
        return int(window[2:])
    except Exception:
        return 999


def _cost(value: float) -> str:
    return f"₹{value:,.0f}"


CALENDAR_LABELS_SHORT = {
    "T+1": "1 Day Before",
    "T+2": "2 Days Before",
    "T+3": "3 Days Before",
    "T+4": "4 Days Before",
    "T+5": "5 Days Before",
    "T+7": "7 Days Before (1 Wk)",
    "T+15": "15 Days Before (2 Wks)",
    "T+30": "30 Days Before (1 Mo)",
    "T+45": "45 Days Before (1.5 Mo)",
}


def build_route_heatmap(
    df: pd.DataFrame,
    value: str = "fare",
    template: str = "plotly_white",
    price_col: str = "total_quote",
) -> go.Figure:
    df = df.copy()
    present_windows = sorted(
        {w for w in df["advance_window"].unique()} | set(SCOPE_WINDOWS),
        key=_window_sort,
    )

    fare_pivot = df.pivot_table(
        index="route_code",
        columns="advance_window",
        values=price_col,
        aggfunc="mean",
    )
    fare_pivot = fare_pivot.reindex(columns=present_windows, fill_value=None)
    fare_pivot = fare_pivot.sort_index()

    if value == "volatility":
        std_pivot = df.pivot_table(
            index="route_code",
            columns="advance_window",
            values=price_col,
            aggfunc="std",
        ).reindex(index=fare_pivot.index, columns=fare_pivot.columns)
        z_raw = (std_pivot / fare_pivot * 100.0).to_numpy()
    else:
        z_raw = fare_pivot.to_numpy()

    z = np.nan_to_num(z_raw, nan=0.0)

    text_matrix = fare_pivot.map(lambda v: "" if pd.isna(v) else _cost(v)).to_numpy()

    if value == "volatility":
        colorscale = [
            [0.0, "#ECFDF5"],  # Light Mint Green
            [0.5, "#FBBF24"],  # Amber
            [1.0, "#EF4444"],  # High Volatility Red
        ]
        colorbar_title = "CV (%)"
        title_text = "🔥 Fare Volatility Index (CV %) by Route Corridor & Calendar Horizon"
    else:
        colorscale = [
            [0.0, "#EFF6FF"],  # Soft Sky Blue
            [0.5, "#3B82F6"],  # Cobalt Blue
            [1.0, "#1E3A8A"],  # Deep Navy Blue
        ]
        colorbar_title = "Avg Fare (₹)"
        title_text = "🗺️ Route Corridor x Calendar Advance Horizon Fare Matrix"

    x_labels = [CALENDAR_LABELS_SHORT.get(col, col) for col in fare_pivot.columns.tolist()]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=x_labels,
            y=fare_pivot.index.tolist(),
            text=text_matrix,
            texttemplate="<b>%{text}</b>",
            textfont=dict(size=12, color="#0F172A", family="Segoe UI, Inter, sans-serif"),
            colorscale=colorscale,
            colorbar=dict(
                title=dict(text=colorbar_title, font=dict(size=11, color="#334155", weight=700)),
                thickness=16,
                len=0.85,
            ),
            hoverongaps=False,
            hovertemplate=(
                "Route: <b>%{y}</b><br>"
                "Calendar Horizon: <b>%{x}</b><br>"
                "Avg Fare: <b>%{text}</b><br>"
                "Metric Value: <b>%{z:.2f}</b><extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=template,
        title=dict(
            text=title_text,
            x=0.01,
            y=0.96,
            font=dict(size=15, color="#0F172A", family="Segoe UI, Inter, sans-serif"),
        ),
        xaxis=dict(
            title=dict(text="Advance Purchase Window", font=dict(size=12, color="#475569", weight=700)),
            tickfont=dict(size=11, color="#1E293B", weight=600),
        ),
        yaxis=dict(
            title=dict(text="Route Corridor", font=dict(size=12, color="#475569", weight=700)),
            tickfont=dict(size=11, color="#1E293B", weight=600),
        ),
        margin=dict(l=20, r=20, t=65, b=20),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(248, 250, 252, 0.5)",
    )
    return fig