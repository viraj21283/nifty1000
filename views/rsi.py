import pandas as pd
import streamlit as st

import common
from common import TF_LIST

RSI_COLS = [f"RSI {tf}" for tf in TF_LIST]
BUY_AT, SELL_AT = 60, 40

st.title("RSI (14) — all timeframes")

df = common.load(["Price", *RSI_COLS])

tfs = st.multiselect("Timeframes to apply the filter on", TF_LIST, default=["Daily"], key="rsi_tfs")
how_all = st.radio("Match", ["All selected timeframes", "Any selected timeframe"], horizontal=True).startswith("All")


def zone_mask(frame: pd.DataFrame, zone: str) -> pd.Series:
    cols = [f"RSI {t}" for t in tfs]
    if zone == "All" or not cols:
        return pd.Series(True, index=frame.index)
    conds = [frame[c] >= BUY_AT if zone == "Buy" else frame[c] <= SELL_AT for c in cols]
    m = conds[0]
    for x in conds[1:]:
        m = (m & x) if how_all else (m | x)
    return m


counts = {z: int(zone_mask(df, z).sum()) for z in ("All", "Buy", "Sell")}
labels = {"All": f"All ({counts['All']})", "Buy": f"Buy · RSI ≥ {BUY_AT} ({counts['Buy']})",
          "Sell": f"Sell · RSI ≤ {SELL_AT} ({counts['Sell']})"}
zone = st.segmented_control("One-click filter", list(labels), default="All",
                            format_func=labels.get, key="zone") or "All"

lo, hi = st.slider("Or a custom RSI range (applied to the selected timeframes)", 0, 100, (0, 100))

f = common.apply_common_filters(df, "rsi")
f = f[zone_mask(f, zone)]
if (lo, hi) != (0, 100) and tfs:
    conds = [f[f"RSI {t}"].between(lo, hi) for t in tfs]
    m = conds[0]
    for x in conds[1:]:
        m = (m & x) if how_all else (m | x)
    f = f[m]

st.metric("Matching stocks", len(f))
show = f[["Symbol", "Company Name", "Industry", "Price", *RSI_COLS]].reset_index(drop=True)
sty = show.style.map(common.rsi_css, subset=RSI_COLS).format({"Price": "{:,.2f}", **{c: "{:.1f}" for c in RSI_COLS}})
st.dataframe(sty, **common.STRETCH, height=680, hide_index=True,
             column_config={"Symbol": st.column_config.TextColumn(pinned=True)})
st.caption(f"Green = Buy zone (RSI ≥ {BUY_AT}), red = Sell zone (RSI ≤ {SELL_AT}). "
           "RSI uses Wilder smoothing over 14 bars of each timeframe.")
st.download_button("⬇ Download CSV", show.to_csv(index=False).encode(), "rsi.csv", "text/csv")
common.footer()
