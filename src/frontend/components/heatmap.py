import numpy as np
import pandas as pd
import plotly.graph_objects as go

SCOPE_WINDOWS = ["T+1", "T+2", "T+3", "T+4", "T+5"]


def _window_sort(window: str) -> int:
    return int(window[2:])


def _cost(value: float) -> str:
    return f"₹{value:,.2f}"


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

    colorscale = [[0.0, "#eef4fb"], [0.5, "#9ecae1"], [1.0, "#3182bd"]]

    colorbar_title = "Avg Fare (INR)" if value == "fare" else "Volatility (CV %)"
    title_text = (
        "Average Fare Price by Route & Advance Window"
        if value == "fare"
        else "Fare Volatility (CV %) by Route & Advance Window"
    )

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=fare_pivot.columns.tolist(),
            y=fare_pivot.index.tolist(),
            text=text_matrix,
            texttemplate="%{text}",
            textfont=dict(size=11, color="#0f1c2e"),
            colorscale=colorscale,
            colorbar=dict(title=colorbar_title),
            hoverongaps=False,
            hovertemplate=(
                "Route: %{y}<br>"
                "Advance Window: %{x}<br>"
                "Avg Fare: %{text}<br>"
                "Value: %{z:.2f}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=template,
        title=dict(text=title_text, x=0.0, font=dict(size=15, color="#0f1c2e")),
        xaxis_title="Advance Window",
        yaxis_title="Route",
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig