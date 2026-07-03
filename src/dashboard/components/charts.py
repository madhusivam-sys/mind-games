from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def price_chart(frame: pd.DataFrame, title: str = "Auction Context") -> None:
    working = frame.copy()
    if working.empty:
        st.info("No chart data available.")
        return
    working["timestamp"] = pd.to_datetime(working["timestamp"])

    figure = go.Figure()
    if {"open", "high", "low", "close"}.issubset(working.columns):
        figure.add_trace(
            go.Candlestick(
                x=working["timestamp"],
                open=working["open"],
                high=working["high"],
                low=working["low"],
                close=working["close"],
                name="Price",
                increasing_line_color="#0f9d7a",
                decreasing_line_color="#c2410c",
            )
        )
    for column, color in [("vwap", "#c58b2a"), ("developing_poc", "#182535"), ("vah", "#2563eb"), ("val", "#dc2626")]:
        if column in working.columns:
            figure.add_trace(
                go.Scatter(x=working["timestamp"], y=working[column], mode="lines", line={"width": 2, "color": color}, name=column.upper())
            )

    figure.update_layout(
        title=title,
        template="plotly_white",
        height=430,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend={"orientation": "h", "y": 1.06},
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.35)",
    )
    st.plotly_chart(figure, use_container_width=True)


def score_distribution(scores: list[dict[str, object]], title: str) -> None:
    if not scores:
        st.info("No scores available.")
        return
    frame = pd.DataFrame(scores)
    figure = go.Figure(
        go.Bar(
            x=frame["setup_name"],
            y=frame["score"],
            marker_color=["#c58b2a" if label == "watch" else "#182535" for label in frame["label"]],
            text=frame["label"],
            textposition="outside",
        )
    )
    figure.update_layout(title=title, template="plotly_white", height=340, margin={"l": 10, "r": 10, "t": 55, "b": 10})
    st.plotly_chart(figure, use_container_width=True)
