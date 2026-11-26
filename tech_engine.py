"""Fetches OHLC data from Yahoo Finance and computes a TradingView-style
technical rating (moving averages + oscillators) for 6 timeframes.

No API key and no TradingView access needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd
import yfinance as yf

BASE = Path(__file__).resolve().parent
SNAPSHOT_PATH = BASE / "data" / "snapshot.csv"
CSV_NAME = "ind_nifty1000_list.csv"


def _find_csv() -> Path:
    """Look for the stock list in data/, next to this file, or anywhere in the repo."""
    for p in (BASE / "data" / CSV_NAME, BASE / CSV_NAME):
        if p.exists():
            return p
    hits = sorted(BASE.rglob("*nifty1000*.csv")) or sorted(BASE.rglob("*nifty*1000*.csv"))
    if hits:
        return hits[0]
    raise FileNotFoundError(
        f"Stock list '{CSV_NAME}' not found. Upload it to the repo at data/{CSV_NAME}."
    )

TIMEFRAMES = ["1 Hour", "2 Hours", "4 Hours", "Daily", "Weekly", "Monthly"]
CHUNK = 100


# ------------------------------------------------------------ rating logic
def score_to_rating(x) -> Optional[str]:
    if x is None or pd.isna(x):
        return None
    if x >= 0.5:
        return "Strong Buy"
    if x >= 0.1:
        return "Buy"
    if x > -0.1:
        return "Neutral"
    if x > -0.5:
        return "Sell"
    return "Strong Sell"


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1 / n, adjust=False).mean()


def analyze(df: pd.DataFrame) -> tuple[float, float]:
    """Return (score in [-1, 1], RSI-14). Score = mean of MA-vote and oscillator-vote averages."""
    df = df.dropna(subset=["Close"])
    if len(df) < 35:
        return np.nan, np.nan
    o, h, l, c = (df[k].astype(float) for k in ("Open", "High", "Low", "Close"))
    last = c.iloc[-1]

    # ---- moving averages (price vs SMA/EMA 10..200)
    ma_votes = []
    for n in (10, 20, 30, 50, 100, 200):
        if len(c) >= n:
            for ma in (c.rolling(n).mean().iloc[-1], c.ewm(span=n, adjust=False).mean().iloc[-1]):
                ma_votes.append(np.sign(last - ma))

    # ---- oscillators
    osc = []

    # RSI 14
    d = c.diff()
    rsi = 100 - 100 / (1 + _wilder(d.clip(lower=0), 14) / _wilder((-d).clip(lower=0), 14).replace(0, np.nan))
    r, rp = rsi.iloc[-1], rsi.iloc[-2]
    if not np.isnan(r):
        osc.append(1 if (r < 30 and r > rp) else -1 if (r > 70 and r < rp) else 0)

    # Stochastic %K(14,3,3)
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    k = (100 * (c - ll) / (hh - ll).replace(0, np.nan)).rolling(3).mean()
    dd = k.rolling(3).mean()
    if not np.isnan(dd.iloc[-1]):
        kk, dv = k.iloc[-1], dd.iloc[-1]
        osc.append(1 if (kk < 20 and dv < 20 and kk > dv) else -1 if (kk > 80 and dv > 80 and kk < dv) else 0)

    # CCI 20
    tp = ((h + l + c) / 3).to_numpy()
    def cci_at(i):
        w = tp[i - 19 : i + 1]
        m = w.mean()
        mad = np.abs(w - m).mean()
        return (tp[i] - m) / (0.015 * mad) if mad else 0.0
    if len(tp) >= 22:
        cn, cp = cci_at(len(tp) - 1), cci_at(len(tp) - 2)
        osc.append(1 if (cn < -100 and cn > cp) else -1 if (cn > 100 and cn < cp) else 0)

    # ADX 14 with DI
    up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = _wilder(tr, 14)
    pdi = 100 * _wilder(pd.Series(pdm, index=c.index), 14) / atr
    ndi = 100 * _wilder(pd.Series(ndm, index=c.index), 14) / atr
    adx = _wilder(100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan), 14)
    if not np.isnan(adx.iloc[-1]):
        osc.append(0 if adx.iloc[-1] <= 20 else (1 if pdi.iloc[-1] > ndi.iloc[-1] else -1))

    # Awesome Oscillator
    med = (h + l) / 2
    ao = med.rolling(5).mean() - med.rolling(34).mean()
    if not np.isnan(ao.iloc[-2]):
        osc.append(1 if (ao.iloc[-1] > 0 and ao.iloc[-1] > ao.iloc[-2]) else -1 if (ao.iloc[-1] < 0 and ao.iloc[-1] < ao.iloc[-2]) else 0)

    # Momentum 10
    mom = c - c.shift(10)
    if not np.isnan(mom.iloc[-2]):
        osc.append(1 if mom.iloc[-1] > mom.iloc[-2] else -1 if mom.iloc[-1] < mom.iloc[-2] else 0)

    # MACD 12/26/9
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    osc.append(1 if macd.iloc[-1] > sig.iloc[-1] else -1 if macd.iloc[-1] < sig.iloc[-1] else 0)

    # Williams %R 14
    wr = -100 * (hh - c) / (hh - ll).replace(0, np.nan)
    if not np.isnan(wr.iloc[-2]):
        osc.append(1 if (wr.iloc[-1] < -80 and wr.iloc[-1] > wr.iloc[-2]) else -1 if (wr.iloc[-1] > -20 and wr.iloc[-1] < wr.iloc[-2]) else 0)

    parts = [np.mean(v) for v in (ma_votes, osc) if len(v)]
    return (float(np.mean(parts)) if parts else np.nan), float(r)


def technical_score(df: pd.DataFrame) -> float:
    return analyze(df)[0]


# ------------------------------------------------------------- data fetch
def _download(tickers: list[str], period: str, interval: str) -> dict[str, pd.DataFrame]:
    raw = yf.download(
        tickers, period=period, interval=interval, group_by="ticker",
        auto_adjust=True, threads=True, progress=False,
    )
    out = {}
    if raw is None or raw.empty:
        return out
    top = set(raw.columns.get_level_values(0))
    for t in tickers:
        if t in top:
            d = raw[t].dropna(how="all")
            if len(d):
                out[t] = d
    return out


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    # NSE session opens 09:15, so anchor bins there
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    return df.resample(rule, origin="start_day", offset="9h15min").agg(agg).dropna(subset=["Close"])


def load_universe() -> pd.DataFrame:
    df = pd.read_csv(_find_csv())
    df.columns = [c.strip() for c in df.columns]
    return df[["Company Name", "Symbol", "Industry"]]


RISK_FREE = 0.065  # annual risk-free rate used for the Sharpe ratio (India ~6.5%)
ROW_TFS = ["1 Hour", "2 Hours", "4 Hours", "Daily", "Weekly", "Monthly"]


def _naive(s: pd.Series) -> pd.Series:
    s = s.dropna().copy()
    idx = pd.DatetimeIndex(s.index)
    s.index = idx.tz_localize(None) if idx.tz is not None else idx
    return s


def _pct(a: float, b: float) -> float:
    return float((a / b - 1) * 100) if b else np.nan


def _since(c: pd.Series, offset) -> float:
    """% change from the last close on/before (latest date - offset) to the latest close."""
    target = c.index[-1] - offset
    prior = c[c.index <= target]
    return _pct(c.iloc[-1], prior.iloc[-1]) if len(prior) else np.nan


def sharpe_12m(c: pd.Series) -> float:
    r = c.pct_change().dropna().tail(252)
    if len(r) < 200 or r.std() == 0:
        return np.nan
    return float((r.mean() - RISK_FREE / 252) / r.std() * np.sqrt(252))


def build_row(daily: pd.DataFrame, hourly, weekly, monthly) -> dict:
    row = {}
    frames = {
        "1 Hour": hourly,
        "2 Hours": _resample(hourly, "2h") if hourly is not None and len(hourly) else None,
        "4 Hours": _resample(hourly, "4h") if hourly is not None and len(hourly) else None,
        "Daily": daily, "Weekly": weekly, "Monthly": monthly,
    }
    for tf, frame in frames.items():
        sc, rsi = analyze(frame) if frame is not None else (np.nan, np.nan)
        row[tf], row[f"RSI {tf}"] = sc, rsi

    dc = _naive(daily["Close"])
    row["Price"] = float(dc.iloc[-1])

    # --- Minervini trend-template inputs
    n = len(dc)
    for w in (50, 150, 200):
        row[f"SMA {w}"] = float(dc.rolling(w).mean().iloc[-1]) if n >= w else np.nan
    sma200 = dc.rolling(200).mean()
    row["SMA200 1M %"] = _pct(sma200.iloc[-1], sma200.iloc[-22]) if n >= 222 else np.nan
    row["SMA200 4M %"] = _pct(sma200.iloc[-1], sma200.iloc[-85]) if n >= 285 else np.nan
    hi = _naive(daily["High"]).tail(252)
    lo = _naive(daily["Low"]).tail(252)
    row["52W High"] = float(hi.max()) if len(hi) else np.nan
    row["52W Low"] = float(lo.min()) if len(lo) else np.nan
    if n >= 253:
        p = lambda k: dc.iloc[-1] / dc.iloc[-1 - k] - 1
        row["RS Raw"] = float(0.4 * p(63) + 0.2 * p(126) + 0.2 * p(189) + 0.2 * p(252))
    else:
        row["RS Raw"] = np.nan
    row["1D %"] = _pct(dc.iloc[-1], dc.iloc[-2]) if len(dc) > 1 else np.nan
    row["1W %"] = _since(dc, pd.Timedelta(days=7))
    row["1M %"] = _since(dc, pd.DateOffset(months=1))
    row["Sharpe 12M"] = sharpe_12m(dc)
    hc = hourly["Close"].dropna() if hourly is not None else pd.Series(dtype=float)
    row["1H %"] = _pct(hc.iloc[-1], hc.iloc[-2]) if len(hc) > 2 else np.nan
    row["2H %"] = _pct(hc.iloc[-1], hc.iloc[-3]) if len(hc) > 3 else np.nan
    return row


def compute_all(progress: Optional[Callable[[float, str], None]] = None) -> pd.DataFrame:
    uni = load_universe()
    tickers = [f"{s}.NS" for s in uni["Symbol"]]
    rows = []
    chunks = [tickers[i : i + CHUNK] for i in range(0, len(tickers), CHUNK)]

    for ci, tk in enumerate(chunks):
        if progress:
            progress(ci / len(chunks), f"Fetching batch {ci + 1}/{len(chunks)}…")
        hourly = _download(tk, "6mo", "1h")
        daily = _download(tk, "2y", "1d")
        weekly = _download(tk, "10y", "1wk")
        monthly = _download(tk, "max", "1mo")
        for t in tk:
            if t not in daily or len(daily[t].dropna(subset=["Close"])) < 2:
                continue
            try:
                row = build_row(daily[t], hourly.get(t), weekly.get(t), monthly.get(t))
            except Exception:
                continue
            rows.append({"Symbol": t[:-3], **row})

    scores = pd.DataFrame(rows)
    if scores.empty:
        raise RuntimeError("No data returned from Yahoo Finance")
    for tf in ROW_TFS:
        scores[tf] = scores[tf].map(score_to_rating)
    # Relative-strength rating (1-99): percentile rank of weighted 12-month performance
    scores["RS Rating"] = (scores["RS Raw"].rank(pct=True) * 99).round().clip(1, 99)
    scores = scores.drop(columns=["RS Raw"])
    out = uni.merge(scores, on="Symbol", how="inner")
    if progress:
        progress(1.0, "Done")
    return out


def save_snapshot(df: pd.DataFrame, source: str = "Yahoo Finance") -> None:
    df = df.copy()
    df["updated_at"] = pd.Timestamp.now(tz="Asia/Kolkata").isoformat()
    df["source"] = source
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOT_PATH, index=False)


def parse_snapshot(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[pd.Timestamp], str]:
    ts = pd.Timestamp(df["updated_at"].iloc[0]) if "updated_at" in df and len(df) else None
    source = str(df["source"].iloc[0]) if "source" in df and len(df) else "unknown"
    return df.drop(columns=["updated_at", "source"], errors="ignore"), ts, source


def load_snapshot() -> tuple[Optional[pd.DataFrame], Optional[pd.Timestamp], str]:
    if not SNAPSHOT_PATH.exists():
        return None, None, ""
    return parse_snapshot(pd.read_csv(SNAPSHOT_PATH))


REQUIRED_COLUMNS = ["Symbol", "Sharpe 12M", "RSI Daily", "1H %", "1M %", "RS Rating", "SMA 200", "52W High"]


def snapshot_meta() -> tuple[Optional[pd.Timestamp], str]:
    """Cheap read of (updated_at, source) without loading the whole table."""
    try:
        m = pd.read_csv(SNAPSHOT_PATH, usecols=["updated_at", "source"], nrows=1)
        return pd.Timestamp(m["updated_at"].iloc[0]), str(m["source"].iloc[0])
    except Exception:
        return None, ""


def snapshot_is_current_schema() -> bool:
    try:
        cols = set(pd.read_csv(SNAPSHOT_PATH, nrows=0).columns)
        return all(c in cols for c in REQUIRED_COLUMNS)
    except Exception:
        return False
