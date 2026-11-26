"""Shared helpers for all pages: data loading, refresh logic, styling."""
from __future__ import annotations

import threading

import pandas as pd
import streamlit as st

import tech_engine as engine

TF_LIST = engine.TIMEFRAMES
_V = tuple(int(x) for x in st.__version__.split(".")[:2])
STRETCH = {"width": "stretch"} if _V >= (1, 49) else {"use_container_width": True}
ID_COLS = ["Symbol", "Company Name", "Industry"]
AUTO_REFRESH_MIN = 60   # auto-refresh if data is older than this during market hours
MIN_GAP_MIN = 10        # ignore manual refreshes if data is fresher than this


# ------------------------------------------------------------------ time
def now_ist() -> pd.Timestamp:
    return pd.Timestamp.now(tz="Asia/Kolkata")


def in_market_window(ts: pd.Timestamp) -> bool:
    """Mon-Fri 09:15-16:30 IST (includes the post-close update)."""
    m = ts.hour * 60 + ts.minute
    return ts.weekday() < 5 and 9 * 60 + 15 <= m <= 16 * 60 + 30


def age_minutes(ts):
    return None if ts is None else (now_ist() - ts).total_seconds() / 60


# ------------------------------------------------------------------ data
@st.cache_data(show_spinner=False)
def _load(cols: tuple, stamp: str) -> pd.DataFrame:
    return pd.read_csv(engine.SNAPSHOT_PATH, usecols=list(cols))


def load(cols: list[str]) -> pd.DataFrame:
    """Load only the columns a page needs (keeps each page light)."""
    ts, _ = engine.snapshot_meta()
    return _load(tuple(dict.fromkeys(ID_COLS + cols)), str(ts))


@st.cache_resource
def _lock() -> threading.Lock:
    return threading.Lock()


def run_refresh(manual: bool) -> str:
    """Recompute everything from Yahoo Finance. Returns 'ok' or a message."""
    ts, _ = engine.snapshot_meta()
    age = age_minutes(ts)
    if manual and age is not None and age < MIN_GAP_MIN and engine.snapshot_is_current_schema():
        return f"Data was refreshed {age:.0f} min ago, so it's already up to date."
    lk = _lock()
    if not lk.acquire(blocking=False):
        return "A refresh is already running. Reload in a minute or two."
    try:
        bar = st.progress(0.0, text="Fetching prices from Yahoo Finance (1–3 min)…")
        df = engine.compute_all(lambda p, m: bar.progress(min(p, 1.0), text=m))
        engine.save_snapshot(df, "Yahoo Finance")
        bar.empty()
        _load.clear()
        return "ok"
    except Exception as e:
        return f"Refresh failed: {e}"
    finally:
        lk.release()


@st.fragment(run_every="5m")
def _watch(loaded_stamp: str):
    """If another session (or the scheduled job) updated the data, reload this page."""
    ts, _ = engine.snapshot_meta()
    if str(ts) != loaded_stamp:
        st.rerun()


def chrome():
    """Sidebar status + refresh button + auto refresh. Call once from the entry file."""
    ts, source = engine.snapshot_meta()
    ok_schema = engine.snapshot_is_current_schema()

    with st.sidebar:
        clicked = st.button("↻ Refresh data now", **STRETCH)
        if ts is not None:
            age = age_minutes(ts)
            st.caption(f"Updated {ts:%d %b, %H:%M} IST ({age:.0f} min ago) · {source}")
        st.caption("Auto-refreshes hourly on market days.")

    stale = ts is None or not ok_schema or (
        age_minutes(ts) > AUTO_REFRESH_MIN and in_market_window(now_ist())
    )
    if clicked or stale:
        msg = run_refresh(manual=clicked)
        if msg == "ok":
            st.rerun()
        elif clicked or ts is None or not ok_schema:
            st.warning(msg)

    ts, _ = engine.snapshot_meta()
    if ts is None or not engine.snapshot_is_current_schema():
        st.error("No data available yet. Try 'Refresh data now' in the sidebar.")
        st.stop()
    _watch(str(ts))


# --------------------------------------------------------------- styling
RATING_CSS = {
    "Strong Buy": "color:#1f9d43;font-weight:700",
    "Buy": "color:#2fbf5b;font-weight:700",
    "Neutral": "color:#8b8f98;font-weight:500",
    "Sell": "color:#e5484d;font-weight:700",
    "Strong Sell": "color:#d11a2a;font-weight:700",
}


def rating_css(v):
    return RATING_CSS.get(v, "")


def signed_css(v):
    if pd.isna(v):
        return ""
    return "color:#2fbf5b" if v > 0 else ("color:#e5484d" if v < 0 else "")


def rsi_css(v):
    if pd.isna(v):
        return ""
    if v >= 60:
        return "color:#2fbf5b;font-weight:700"   # buy zone
    if v <= 40:
        return "color:#e5484d;font-weight:700"   # sell zone
    return ""


def apply_common_filters(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Search + industry filters in the sidebar."""
    q = st.sidebar.text_input("Search symbol / company", key=f"{key}_q")
    ind = st.sidebar.multiselect("Industry", sorted(df["Industry"].dropna().unique()), key=f"{key}_ind")
    if q:
        m = df["Symbol"].str.contains(q, case=False, na=False) | df["Company Name"].str.contains(q, case=False, na=False)
        df = df[m]
    if ind:
        df = df[df["Industry"].isin(ind)]
    return df


def footer():
    st.caption(
        "⚠️ For information and education only; not investment advice. Calculated from Yahoo Finance prices "
        "(may be delayed or inaccurate); ratings are similar to, but not identical to, TradingView's. "
        "Trading involves risk of loss. See DISCLAIMER.md."
    )
