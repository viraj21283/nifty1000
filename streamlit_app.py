"""Nifty 1000 Technicals – entry point. Each page is a separate script in views/,
and Streamlit only runs the page that is currently selected."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
st.set_page_config(page_title="Nifty 1000 Technicals", page_icon="📈", layout="wide")

try:
    import common
except ModuleNotFoundError as e:
    st.error(
        f"Missing module: `{e.name}`. Make sure engine.py, common.py and the views/ folder are in the "
        "repo next to this file, and requirements.txt (streamlit, pandas, numpy, yfinance) is in the repo root."
    )
    st.stop()

pages = [
    st.Page("views/ratings.py", title="Technical Ratings", icon="📊", default=True),
    st.Page("views/rsi.py", title="RSI", icon="📉"),
    st.Page("views/returns.py", title="Returns & Sharpe", icon="📈"),
]
nav = st.navigation(pages)
common.chrome()
nav.run()
