import streamlit as st

import common
import tech_engine as engine

CHG = ["1H %", "2H %", "1D %", "1W %", "1M %"]

st.title("Returns & Sharpe — Nifty 1000")

df = common.load(["Price", *CHG, "Sharpe 12M"])

preset = st.segmented_control(
    "One-click filter",
    ["All", "Sharpe ≥ 1", "Sharpe ≥ 2", "Up on every period", "Down on every period"],
    default="All", key="ret_preset",
) or "All"

f = common.apply_common_filters(df, "ret")
min_sh = st.sidebar.number_input("Min Sharpe (12M)", value=-10.0, step=0.5)
min_1m = st.sidebar.number_input("Min 1M %", value=-100.0, step=1.0)
f = f[(f["Sharpe 12M"].fillna(-99) >= min_sh) & (f["1M %"].fillna(-999) >= min_1m)]

if preset == "Sharpe ≥ 1":
    f = f[f["Sharpe 12M"] >= 1]
elif preset == "Sharpe ≥ 2":
    f = f[f["Sharpe 12M"] >= 2]
elif preset == "Up on every period":
    f = f[(f[CHG] > 0).all(axis=1)]
elif preset == "Down on every period":
    f = f[(f[CHG] < 0).all(axis=1)]

c1, c2 = st.columns(2)
c1.metric("Matching stocks", len(f))
c2.metric("Median Sharpe", f"{f['Sharpe 12M'].median():.2f}" if len(f) else "–")

show = f[["Symbol", "Company Name", "Industry", "Price", *CHG, "Sharpe 12M"]].sort_values(
    "Sharpe 12M", ascending=False).reset_index(drop=True)
sty = (show.style.map(common.signed_css, subset=CHG + ["Sharpe 12M"])
       .format({"Price": "{:,.2f}", "Sharpe 12M": "{:.2f}", **{c: "{:+.2f}%" for c in CHG}}))
st.dataframe(sty, **common.STRETCH, height=680, hide_index=True,
             column_config={"Symbol": st.column_config.TextColumn(pinned=True)})
st.caption(
    f"Sharpe = (mean daily return − {engine.RISK_FREE:.1%}/252) ÷ std of daily returns × √252, over the last 252 trading days "
    "(needs ≥200 days of history). 1H / 2H = change vs. the close 1 / 2 hourly bars ago; 1D = vs. previous close; "
    "1W / 1M = vs. the last close on or before 7 days / 1 month ago."
)
st.download_button("⬇ Download CSV", show.to_csv(index=False).encode("utf-8-sig"), "returns_sharpe.csv", "text/csv")
common.footer()
