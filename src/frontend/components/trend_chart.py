import pandas as pd
import plotly.graph_objects as go

WINDOW_PALETTE = {
    "T+1": "#e4572e",
    "T+2": "#f2a541",
    "T+3": "#5aa9e6",
    "T+4": "#7f96ff",
    "T+5": "#7bc950",
}


def _window_sort(window: str) -> int:
    return int(window[2:])


def build_trend_figure(
    df: pd.DataFrame,
    baseline_mean: float | None = None,
    template: str = "plotly_white",
) -> go.Figure:
    df = df.copy()
    base = baseline_mean or df["total_quote"].mean()
    df["index_score"] = (100.0 * df["total_quote"] / base) if base else 100.0

    fig = go.Figure()

    for window in sorted(df["advance_window"].unique(), key=_window_sort):
        sub = df[df["advance_window"] == window].sort_values("departure_date")
        fig.add_trace(
            go.Scatter(
                x=sub["departure_date"],
                y=sub["total_quote"],
                mode="lines+markers",
                name=window,
                line=dict(width=2.2, color=WINDOW_PALETTE.get(window, "#9aa5b1")),
                customdata=sub[["base_fare", "tax_udf", "advance_window", "index_score"]].to_numpy(),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Advance Window: %{customdata[2]}<br>"
                    "Total Quote: Rs. %{y:,.2f}<br>"
                    "Base Fare: Rs. %{customdata[0]:,.2f}<br>"
                    "Tax & UDF: Rs. %{customdata[1]:,.2f}<br>"
                    "<extra></extra>"
                ),
            )
        )

    idx = df.groupby("departure_date")["index_score"].mean().reset_index()
    fig.add_trace(
        go.Scatter(
            x=idx["departure_date"],
            y=idx["index_score"],
            mode="lines+markers",
            name="Composite Index (Base 100)",
            yaxis="y2",
            line=dict(dash="dash", width=2.4, color="#1f4e79"),
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Index Score: %{y:.2f}<br>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=template,
        title=dict(
            text="Total Quote by Departure Date & Advance Window",
            x=0.0,
            font=dict(size=15, color="#0f1c2e"),
        ),
        xaxis_title="Departure Date",
        yaxis_title="Total Quote (INR)",
        yaxis2=dict(
            title="Composite Index (Base 100)",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        hovermode="x unified",
        legend_title="Advance Window",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig