from __future__ import annotations

import pandas as pd
import streamlit as st


def data_table(frame: pd.DataFrame, columns: list[str] | None = None, height: int = 320) -> None:
    working = frame.copy()
    if columns is not None:
        available = [column for column in columns if column in working.columns]
        working = working[available]
    st.dataframe(working, use_container_width=True, hide_index=True, height=height)
