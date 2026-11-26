"""Nifty 1000 – Technicals dashboard (Streamlit).

Ratings are TradingView's aggregate technical rating (oscillators + moving
averages) per timeframe, pulled from the public TradingView scanner endpoint.
"""
import pandas as pd
import streamlit as st

import engine
from engine import TIMEFRAMES as TF_LIST

st.set_page_config(page_title="Nifty 1000 Technicals", page_icon="📈", layout="wide")

TIMEFRAMES = {tf: tf for tf in TF_LIST}
RATINGS = ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
BULLISH = {"Strong Buy", "Buy"}
BEARISH = {"Sell", "Strong Sell"}
MAX_AGE_MIN = 30  # recompute if the snapshot is older than this


def _age_min(ts):
    return (pd.Timestamp.now(tz="Asia/Kolkata") - ts).total_seconds() / 60 if ts is not None else 1e9


@st.cache_data(ttl=900, show_spinner=False)
def get_data():
    """Use a fresh snapshot if available, otherwise fetch live; fall back to a stale snapshot."""
    snap, ts = engine.load_snapshot()
    if snap is not None and _age_min(ts) < MAX_AGE_MIN:
        return snap, ts, "snapshot"
    try:
        bar = st.progress(0.0, text="Fetching prices from Yahoo Finance…")
        df = engine.compute_all(lambda p, m: bar.progress(min(p, 1.0), text=m))
        bar.empty()
        try:
            engine.save_snapshot(df)
        except OSError:
            pass
        return df, pd.Timestamp.now(tz="Asia/Kolkata"), "live"
    except Exception as e:
        if snap is not None:
            return snap, ts, f"stale ({e})"
        raise


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Bullish TFs"] = df[TF_LIST].isin(BULLISH).sum(axis=1)
    df["Bearish TFs"] = df[TF_LIST].isin(BEARISH).sum(axis=1)
    keep = ["Symbol", "Company Name", "Industry", "Price", "Chg %", *TF_LIST, "Bullish TFs", "Bearish TFs"]
    return df[keep].sort_values("Symbol").reset_index(drop=True)


# --------------------------------------------------------------------- UI
st.title("Technicals — Nifty 1000")

col_a, col_b = st.columns([6, 1])
with col_b:
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    raw, fetched_at, source = get_data()
    data = finalize(raw)
except Exception as e:
    st.error(f"Could not fetch data: {e}")
    st.stop()

with col_a:
    st.caption(
        f"{len(data)} stocks · technical rating from Yahoo Finance prices · "
        f"updated {fetched_at:%d %b %Y, %H:%M} IST · source: {source.split(' (')[0]}"
    )
    if source.startswith("stale"):
        st.warning(f"Live fetch failed, showing the last saved snapshot. ({source})")

# ---- sidebar filters
with st.sidebar:
    st.header("Filters")
    q = st.text_input("Search symbol / company")
    industries = st.multiselect("Industry", sorted(data["Industry"].dropna().unique()))

    st.subheader("Rating by timeframe")
    st.caption("Leave a timeframe empty to ignore it.")
    tf_filters = {tf: st.multiselect(tf, RATINGS, key=f"f_{tf}") for tf in TIMEFRAMES}
    match_all = st.radio(
        "Combine timeframe filters with", ["AND (all must match)", "OR (any can match)"]
    ).startswith("AND")

    st.subheader("Quick presets")
    preset = st.selectbox(
        "Alignment",
        ["None", "Bullish on all timeframes", "Bearish on all timeframes",
         "Bullish on ≥ 4 timeframes", "Bearish on ≥ 4 timeframes"],
    )
    c1, c2 = st.columns(2)
    min_p = c1.number_input("Min price", min_value=0.0, value=0.0, step=10.0)
    max_p = c2.number_input("Max price", min_value=0.0, value=0.0, step=10.0, help="0 = no limit")

# ---- apply filters
f = data
if q:
    m = f["Symbol"].str.contains(q, case=False, na=False) | f["Company Name"].str.contains(q, case=False, na=False)
    f = f[m]
if industries:
    f = f[f["Industry"].isin(industries)]
if min_p:
    f = f[f["Price"] >= min_p]
if max_p:
    f = f[f["Price"] <= max_p]

active = [(tf, r) for tf, r in tf_filters.items() if r]
if active:
    masks = [f[tf].isin(r) for tf, r in active]
    combined = masks[0]
    for m in masks[1:]:
        combined = combined & m if match_all else combined | m
    f = f[combined]

if preset == "Bullish on all timeframes":
    f = f[f["Bullish TFs"] == len(TIMEFRAMES)]
elif preset == "Bearish on all timeframes":
    f = f[f["Bearish TFs"] == len(TIMEFRAMES)]
elif preset == "Bullish on ≥ 4 timeframes":
    f = f[f["Bullish TFs"] >= 4]
elif preset == "Bearish on ≥ 4 timeframes":
    f = f[f["Bearish TFs"] >= 4]

# ---- summary
m1, m2, m3, m4 = st.columns(4)
m1.metric("Matching stocks", len(f))
m2.metric("Bullish on Daily", int(f["Daily"].isin(BULLISH).sum()))
m3.metric("Bearish on Daily", int(f["Daily"].isin(BEARISH).sum()))
m4.metric("Bullish on all 6 TFs", int((f["Bullish TFs"] == len(TIMEFRAMES)).sum()))

# ---- styled table
COLORS = {
    "Strong Buy": "color:#1f9d43;font-weight:700",
    "Buy": "color:#2fbf5b;font-weight:700",
    "Neutral": "color:#8b8f98;font-weight:500",
    "Sell": "color:#e5484d;font-weight:700",
    "Strong Sell": "color:#d11a2a;font-weight:700",
}
style_fn = lambda v: COLORS.get(v, "")
chg_fn = lambda v: "color:#2fbf5b" if v > 0 else ("color:#e5484d" if v < 0 else "")

styler = f.style
styler = (styler.map if hasattr(styler, "map") else styler.applymap)(style_fn, subset=list(TIMEFRAMES))
styler = (styler.map if hasattr(styler, "map") else styler.applymap)(chg_fn, subset=["Chg %"])
styler = styler.format({"Price": "{:,.2f}", "Chg %": "{:+.2f}%"})

st.dataframe(
    styler,
    use_container_width=True,
    height=700,
    hide_index=True,
    column_config={
        "Symbol": st.column_config.TextColumn(pinned=True),
        "Bullish TFs": st.column_config.NumberColumn(help="Timeframes rated Buy / Strong Buy"),
        "Bearish TFs": st.column_config.NumberColumn(help="Timeframes rated Sell / Strong Sell"),
    },
)

st.download_button(
    "⬇ Download filtered CSV",
    f.to_csv(index=False).encode(),
    file_name="nifty1000_technicals.csv",
    mime="text/csv",
)
st.caption(
    "⚠️ For information and education only; not investment advice. Ratings are computed from "
    "Yahoo Finance prices (similar to, but not identical to, TradingView), may be delayed or inaccurate, "
    "and are not a recommendation to buy or sell. Trading involves risk of loss. See DISCLAIMER.md."
)
