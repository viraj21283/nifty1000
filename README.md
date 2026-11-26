# Nifty 1000 Technicals

A Streamlit dashboard that shows technical ratings (Strong Buy → Strong Sell)
for the Nifty 1000 universe across six timeframes — 1 Hour, 2 Hours, 4 Hours,
Daily, Weekly and Monthly — with filters to slice the list.

> **Not investment advice.** Read [DISCLAIMER.md](DISCLAIMER.md) before use.

## Features
- Colour-coded ratings table for ~1000 NSE stocks
- Per-timeframe rating filters, combinable with AND / OR
- Search, industry and price-range filters
- Presets: bullish / bearish on all timeframes, or on at least 4
- "Bullish TFs" / "Bearish TFs" counts (sortable)
- Download the filtered view as CSV
- Automatic data refresh (on load when stale, plus an optional scheduled job)

## How it works
1. `engine.py` downloads OHLC prices from Yahoo Finance (`SYMBOL.NS`) with
   `yfinance`. 2h and 4h bars are built from hourly data, anchored to the
   09:15 IST open.
2. For each timeframe it takes votes from moving averages (SMA/EMA 10, 20, 30,
   50, 100, 200) and oscillators (RSI, Stochastic, CCI, ADX, Awesome
   Oscillator, Momentum, MACD, Williams %R), averages them into a score in
   [-1, 1] and maps it to a rating (≥0.5 Strong Buy, ≥0.1 Buy, within ±0.1
   Neutral, ≤-0.1 Sell, ≤-0.5 Strong Sell).
3. `app.py` loads `data/snapshot.csv` if it is under 30 minutes old; otherwise
   it fetches live data (about 1–2 minutes), saves a new snapshot and caches
   it for 15 minutes. If a live fetch fails it falls back to the last snapshot.
4. `.github/workflows/refresh.yml` (optional) refreshes the snapshot every
   30 minutes during market hours so visitors get instant loads.

Ratings approximate TradingView's methodology but are **not identical** to it.

## Project layout
```
app.py                       Streamlit UI and filters
engine.py                    Data fetching + indicator/rating logic
refresh.py                   CLI entry point for scheduled refreshes
data/ind_nifty1000_list.csv  Stock universe (company, industry, symbol)
data/snapshot.csv            Latest computed ratings (auto-generated)
.github/workflows/refresh.yml  Scheduled refresh (optional)
.streamlit/config.toml       Dark theme
```

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
To pre-build the snapshot without opening the app: `python refresh.py`.

## Deploy
**Streamlit Community Cloud**
1. Push this folder to a GitHub repo.
2. Create a new app pointing at `app.py`.
3. In the repo's **Actions** tab, run *Refresh technicals* once (and make sure
   Settings → Actions → General → Workflow permissions allows read/write) so a
   snapshot exists and stays current.

Any other host that can run Streamlit and reach Yahoo Finance also works.

## Updating the stock list
Replace `data/ind_nifty1000_list.csv` with a newer file using the same columns
(`Company Name, Industry, Symbol, Series, ISIN Code`). Symbols must be NSE
tickers as used by Yahoo Finance (`<SYMBOL>.NS`).

## Limitations
- Yahoo Finance is an unofficial source: data can be delayed, missing or
  rate-limited, and the library may break when Yahoo changes its API.
- Hourly history is limited (~2 years), so long moving averages may be absent
  on short intraday series; newly listed stocks have fewer monthly bars.
- Some tickers may not resolve on Yahoo and are omitted from the table.
- The stock list is static and may not reflect the latest index changes.

## License
MIT — see [LICENSE](LICENSE). Replace `<YOUR NAME>` in the license with your
name before publishing.
