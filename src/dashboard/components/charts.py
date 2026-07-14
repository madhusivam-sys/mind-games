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
                increasing_line_color="#3C7B53",
                decreasing_line_color="#B84A3A",
            )
        )
    for column, color in [("vwap", "#D5A63D"), ("developing_poc", "#333333"), ("vah", "#20959A"), ("val", "#B84A3A")]:
        if column in working.columns:
            figure.add_trace(
                go.Scatter(x=working["timestamp"], y=working[column], mode="lines", line={"width": 2, "color": color}, name=column.upper())
            )

    figure.update_layout(
        template="plotly_white",
        font={"family": "Lato", "color": "#333333", "size": 12},
        title={"text": title, "font": {"family": "Montserrat", "size": 17, "color": "#333333"}, "x": 0.02},
        height=430,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        legend={"orientation": "h", "y": 1.06},
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,254,250,0.35)",
        xaxis={"gridcolor": "rgba(56,56,97,.08)", "linecolor": "rgba(56,56,97,.12)"},
        yaxis={"gridcolor": "rgba(56,56,97,.08)", "linecolor": "rgba(56,56,97,.12)"},
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
            marker_color=["#D5A63D" if label == "watch" else "#383861" for label in frame["label"]],
            text=frame["label"],
            textposition="outside",
        )
    )
    figure.update_layout(
        title={"text": title, "font": {"family": "Montserrat", "size": 16, "color": "#333333"}, "x": 0.02},
        template="plotly_white", height=340, margin={"l": 10, "r": 10, "t": 55, "b": 10},
        font={"family": "Lato", "color": "#333333"}, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,254,250,.35)", yaxis={"gridcolor": "rgba(56,56,97,.08)"},
    )
    st.plotly_chart(figure, use_container_width=True)
