import pandas as pd
import streamlit as st

import common

MET = ["Price", "SMA 50", "SMA 150", "SMA 200", "SMA200 1M %", "SMA200 4M %", "52W High", "52W Low", "RS Rating"]

st.title("Minervini Trend Template — Nifty 1000")

df = common.load(MET)

# ---- adjustable thresholds (Minervini's defaults)
st.sidebar.subheader("Template thresholds")
min_rs = st.sidebar.slider("Min RS rating", 1, 99, 70)
min_above_low = st.sidebar.slider("Min % above 52-week low", 0, 200, 30)
max_below_high = st.sidebar.slider("Max % below 52-week high", 0, 60, 25)
trend = st.sidebar.radio("200-day SMA must be rising for", ["1 month", "4 months"], horizontal=True)
slope_col = "SMA200 1M %" if trend == "1 month" else "SMA200 4M %"

# ---- evaluate the 8 criteria for every stock (missing data = fail)
d = df.copy()
d["% above 52W Low"] = (d["Price"] / d["52W Low"] - 1) * 100
d["% below 52W High"] = (1 - d["Price"] / d["52W High"]) * 100

names = {
    "c1": "1 · P > 150 & 200 SMA",
    "c2": "2 · 150 > 200 SMA",
    "c3": "3 · 200 SMA rising",
    "c4": "4 · 50 > 150 & 200 SMA",
    "c5": "5 · P > 50 SMA",
    "c6": f"6 · ≥{min_above_low}% above low",
    "c7": f"7 · ≤{max_below_high}% from high",
    "c8": f"8 · RS ≥ {min_rs}",
}
c = pd.DataFrame(index=d.index)
c["c1"] = (d["Price"] > d["SMA 150"]) & (d["Price"] > d["SMA 200"])
c["c2"] = d["SMA 150"] > d["SMA 200"]
c["c3"] = d[slope_col] > 0
c["c4"] = (d["SMA 50"] > d["SMA 150"]) & (d["SMA 50"] > d["SMA 200"])
c["c5"] = d["Price"] > d["SMA 50"]
c["c6"] = d["% above 52W Low"] >= min_above_low
c["c7"] = d["% below 52W High"] <= max_below_high
c["c8"] = d["RS Rating"] >= min_rs
d["Score"] = c.sum(axis=1).astype(int)
CRIT = list(names.values())
d[CRIT] = c.rename(columns=names).map(lambda x: "✔" if x else "✘")

# ---- one-click filters
opts = {
    "All": d["Score"] >= 0,
    "All 8 criteria": d["Score"] == 8,
    "7+ criteria": d["Score"] >= 7,
    "6+ criteria": d["Score"] >= 6,
}
counts = {k: int(v.sum()) for k, v in opts.items()}
quick = st.segmented_control(
    "One-click filter", list(opts), default="All",
    format_func=lambda k: f"{k} ({counts[k]})", key="mv_quick",
) or "All"

f = common.apply_common_filters(d[opts[quick]], "mv")

c1, c2, c3 = st.columns(3)
c1.metric("Matching stocks", len(f))
c2.metric("Pass all 8 (whole universe)", counts["All 8 criteria"])
c3.metric("With enough history", int(d["SMA 200"].notna().sum()))

cols = ["Symbol", "Company Name", "Industry", "Price", "Score", *CRIT,
        "SMA 50", "SMA 150", "SMA 200", "SMA200 1M %", "SMA200 4M %",
        "52W High", "52W Low", "% above 52W Low", "% below 52W High", "RS Rating"]
show = f[cols].sort_values(["Score", "RS Rating"], ascending=False).reset_index(drop=True)

num = ["Price", "SMA 50", "SMA 150", "SMA 200", "52W High", "52W Low"]
sty = (show.style
       .map(lambda v: "color:#2fbf5b;font-weight:700" if v == "✔" else ("color:#e5484d" if v == "✘" else ""), subset=CRIT)
       .map(common.signed_css, subset=["SMA200 1M %", "SMA200 4M %"])
       .format({**{k: "{:,.2f}" for k in num},
                "SMA200 1M %": "{:+.2f}%", "SMA200 4M %": "{:+.2f}%",
                "% above 52W Low": "{:.1f}%", "% below 52W High": "{:.1f}%",
                "RS Rating": "{:.0f}"}, na_rep="–"))
st.dataframe(sty, **common.STRETCH, height=680, hide_index=True,
             column_config={"Symbol": st.column_config.TextColumn(pinned=True)})

st.caption(
    "Mark Minervini's Trend Template: (1) price above the 150- and 200-day SMA, (2) 150-day above 200-day, "
    "(3) 200-day rising for at least 1 month (ideally 4–5), (4) 50-day above both, (5) price above the 50-day, "
    "(6) price at least 30% above its 52-week low, (7) within 25% of its 52-week high, (8) RS rating of 70 or more "
    "(80+ is better). Thresholds are adjustable in the sidebar. **RS rating here** is a 1–99 percentile rank within "
    "the Nifty 1000 of 0.4×3M + 0.2×6M + 0.2×9M + 0.2×12M price change, similar to, but not the same as, IBD's. "
    "52-week high/low use daily highs/lows. Stocks with under ~1 year of history fail the criteria they can't be tested on."
)
export = show.copy()
export[CRIT] = export[CRIT].replace({"✔": "Yes", "✘": "No"})  # plain text filters cleanly in Excel
st.download_button("⬇ Download CSV", export.to_csv(index=False).encode("utf-8-sig"),
                   "minervini_trend_template.csv", "text/csv")
common.footer()
