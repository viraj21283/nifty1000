# Nifty 1000 Technicals

A multi-page Streamlit dashboard for the Nifty 1000 universe, built on **free
Yahoo Finance data only**.

> **Not investment advice.** Read [DISCLAIMER.md](DISCLAIMER.md) before use.

## Pages
| Page | What it shows | Filters |
|---|---|---|
| **Technical Ratings** | Strong Buy → Strong Sell for 1H, 2H, 4H, Daily, Weekly, Monthly | One-click *Strong Buy / Buy / Sell / Strong Sell on all timeframes* (with counts), per-timeframe rating filters (AND/OR), search, industry |
| **RSI** | RSI(14) for all six timeframes | One-click Buy (RSI ≥ 60) / Sell (RSI ≤ 40) with counts, timeframe picker (all / any), custom RSI range |
| **Minervini Trend Template** | All 8 criteria as ✔/✘ per stock, score out of 8, SMAs 50/150/200, 200-SMA slope, 52-week high/low, % above low / below high, RS rating | One-click All 8 / 7+ / 6+, adjustable thresholds (RS, % above low, % from high, 200-SMA lookback), search, industry |
| **Returns & Sharpe** | % change 1H, 2H, 1D, 1W, 1M and 12-month Sharpe ratio | One-click Sharpe ≥ 1 / ≥ 2, up/down on every period, min Sharpe / 1M % |

Each page is a separate script (`views/`) and reads only the columns it needs
from the snapshot, so only the page you open is loaded.

## Refreshing data
- **Hourly, automatically:** a GitHub Actions job (`.github/workflows/refresh.yml`)
  recomputes everything every hour on market days (~09:20–16:20 IST) and commits
  `data/snapshot.csv`. The app picks it up and any open page reloads itself.
- **If the job isn't running:** the app refreshes itself when someone opens it and
  the data is over 60 minutes old during market hours.
- **Manually:** *Refresh data now* in the sidebar recomputes everything (about 1–3
  minutes, with a progress bar). It is skipped if data is under 10 minutes old, and
  only one refresh runs at a time.

## Definitions
- **Rating:** votes from moving averages (SMA/EMA 10, 20, 30, 50, 100, 200) and
  oscillators (RSI, Stochastic, CCI, ADX, Awesome Oscillator, Momentum, MACD,
  Williams %R) are averaged into a score in [-1, 1] → ≥0.5 Strong Buy, ≥0.1 Buy,
  within ±0.1 Neutral, ≤-0.1 Sell, ≤-0.5 Strong Sell. Similar to, but not identical
  to, TradingView's.
- **One-click filters:** Strong Buy / Strong Sell = all six timeframes have that exact
  rating. Buy = all six are Buy or Strong Buy; Sell = all six are Sell or Strong Sell.
- **RSI:** 14-period, Wilder smoothing, on the bars of each timeframe. ≥60 green (Buy zone), ≤40 red (Sell zone).
- **Sharpe (12M):** (mean daily return − 6.5%/252) ÷ std of daily returns × √252 over
  the last 252 trading days (needs ≥200 days). Change `RISK_FREE` in `tech_engine.py`.
- **% change:** 1H / 2H vs. the close 1 / 2 hourly bars ago; 1D vs. previous close;
  1W / 1M vs. the last close on or before 7 days / 1 month ago.
- 2h and 4h bars are built from hourly data anchored to the 09:15 IST open.

- **Minervini Trend Template:** price above 150- and 200-day SMA; 150 above 200; 200-day rising
  (1 or 4 months); 50 above 150 and 200; price above 50; ≥30% above 52-week low; within 25% of
  52-week high; RS rating ≥ 70. **RS rating** = percentile (1–99) within the Nifty 1000 of
  0.4×3M + 0.2×6M + 0.2×9M + 0.2×12M price change (similar to, not the same as, IBD's).

## Project layout
```
streamlit_app.py     Entry point + navigation
common.py            Data loading, refresh logic, styling
tech_engine.py      Yahoo Finance download + indicators/ratings
refresh.py           CLI used by the scheduled job
views/               One script per page (ratings, rsi, returns, minervini)
data/ind_nifty1000_list.csv   Stock universe
data/snapshot.csv    Latest computed data (auto-generated)
.github/workflows/refresh.yml Hourly refresh job
```

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```
The first run builds the snapshot automatically (1–3 minutes). Or run `python refresh.py`.

## Deploy (Streamlit Community Cloud)
1. Push the whole folder (including `views/` and `data/`) to GitHub.
2. Create an app pointing at `streamlit_app.py`.
3. In the repo go to Settings → Actions → General → Workflow permissions →
   *Read and write*, then run *Refresh technicals (hourly)* once from the Actions tab.

## Limitations
- Yahoo Finance is unofficial: data can be delayed, missing or rate-limited, and
  `yfinance` may break when Yahoo changes things. Shared cloud IPs are sometimes
  throttled; the scheduled job helps because the app then rarely fetches itself.
- Hourly history is limited (~2 years); newly listed stocks have fewer monthly bars,
  so long moving averages and Sharpe may be missing.
- Some tickers may not resolve on Yahoo and are omitted.
- The stock list is static and may not reflect the latest index changes.

## License
MIT — see [LICENSE](LICENSE). © 2026 Srikrishna Solutions.
