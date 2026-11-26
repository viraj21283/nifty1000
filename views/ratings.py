import pandas as pd
import streamlit as st

import common
from common import TF_LIST

RATINGS = ["Strong Buy", "Buy", "Neutral", "Sell", "Strong Sell"]
BULL, BEAR = {"Strong Buy", "Buy"}, {"Sell", "Strong Sell"}

st.title("Technical Ratings — Nifty 1000")

df = common.load(["Price", "1D %", *TF_LIST])

# ---- one-click filters across ALL timeframes
all_masks = {
    "All": pd.Series(True, index=df.index),
    "Strong Buy": (df[TF_LIST] == "Strong Buy").all(axis=1),
    "Buy": df[TF_LIST].isin(BULL).all(axis=1),
    "Sell": df[TF_LIST].isin(BEAR).all(axis=1),
    "Strong Sell": (df[TF_LIST] == "Strong Sell").all(axis=1),
}
counts = {k: int(v.sum()) for k, v in all_masks.items()}
quick = st.segmented_control(
    "One-click filter: rating on ALL 6 timeframes",
    list(all_masks),
    default="All",
    format_func=lambda k: k if k == "All" else f"{k} ({counts[k]})",
    key="quick",
) or "All"
st.caption(
    "Strong Buy / Strong Sell = every timeframe has that exact rating. "
    "Buy = every timeframe is Buy or Strong Buy; Sell = every timeframe is Sell or Strong Sell."
)
f = df[all_masks[quick]]

# ---- sidebar filters
f = common.apply_common_filters(f, "rt")
st.sidebar.subheader("Rating by timeframe")
st.sidebar.caption("Leave a timeframe empty to ignore it.")
active = {tf: st.sidebar.multiselect(tf, RATINGS, key=f"rt_{tf}") for tf in TF_LIST}
active = {k: v for k, v in active.items() if v}
if active:
    use_and = st.sidebar.radio("Combine with", ["AND", "OR"], horizontal=True) == "AND"
    masks = [f[tf].isin(r) for tf, r in active.items()]
    m = masks[0]
    for x in masks[1:]:
        m = (m & x) if use_and else (m | x)
    f = f[m]

# ---- table
c1, c2, c3 = st.columns(3)
c1.metric("Matching stocks", len(f))
c2.metric("Bullish on Daily", int(f["Daily"].isin(BULL).sum()))
c3.metric("Bearish on Daily", int(f["Daily"].isin(BEAR).sum()))

show = f[["Symbol", "Company Name", "Industry", "Price", "1D %", *TF_LIST]].reset_index(drop=True)
sty = (show.style.map(common.rating_css, subset=TF_LIST)
       .map(common.signed_css, subset=["1D %"])
       .format({"Price": "{:,.2f}", "1D %": "{:+.2f}%"}))
st.dataframe(sty, **common.STRETCH, height=680, hide_index=True,
             column_config={"Symbol": st.column_config.TextColumn(pinned=True)})
st.download_button("⬇ Download CSV", show.to_csv(index=False).encode(), "technical_ratings.csv", "text/csv")
common.footer()
