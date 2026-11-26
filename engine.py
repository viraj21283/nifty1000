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

CSV_PATH = Path(__file__).parent / "data" / "ind_nifty1000_list.csv"
SNAPSHOT_PATH = Path(__file__).parent / "data" / "snapshot.csv"

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


def technical_score(df: pd.DataFrame) -> float:
    """Return a score in [-1, 1]: mean of MA-vote average and oscillator-vote average."""
    df = df.dropna(subset=["Close"])
    if len(df) < 35:
        return np.nan
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
    return float(np.mean(parts)) if parts else np.nan


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
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    return df[["Company Name", "Symbol", "Industry"]]


def compute_all(progress: Optional[Callable[[float, str], None]] = None) -> pd.DataFrame:
    uni = load_universe()
    yf_map = {s: f"{s}.NS" for s in uni["Symbol"]}
    rows = []
    chunks = [list(yf_map.values())[i : i + CHUNK] for i in range(0, len(yf_map), CHUNK)]

    for ci, tk in enumerate(chunks):
        if progress:
            progress(ci / len(chunks), f"Fetching batch {ci + 1}/{len(chunks)}…")
        hourly = _download(tk, "6mo", "1h")
        daily = _download(tk, "2y", "1d")
        weekly = _download(tk, "10y", "1wk")
        monthly = _download(tk, "max", "1mo")
        for t in tk:
            if t not in daily:
                continue
            row = {"Symbol": t[:-3]}
            dd = daily[t]
            row["Price"] = float(dd["Close"].iloc[-1])
            row["Chg %"] = float((dd["Close"].iloc[-1] / dd["Close"].iloc[-2] - 1) * 100) if len(dd) > 1 else np.nan
            h1 = hourly.get(t)
            row["1 Hour"] = technical_score(h1) if h1 is not None else np.nan
            row["2 Hours"] = technical_score(_resample(h1, "2h")) if h1 is not None else np.nan
            row["4 Hours"] = technical_score(_resample(h1, "4h")) if h1 is not None else np.nan
            row["Daily"] = technical_score(dd)
            row["Weekly"] = technical_score(weekly[t]) if t in weekly else np.nan
            row["Monthly"] = technical_score(monthly[t]) if t in monthly else np.nan
            rows.append(row)

    scores = pd.DataFrame(rows)
    if scores.empty:
        raise RuntimeError("No data returned from Yahoo Finance")
    for tf in TIMEFRAMES:
        scores[tf] = scores[tf].map(score_to_rating)
    out = uni.merge(scores, on="Symbol", how="inner")
    if progress:
        progress(1.0, "Done")
    return out


def save_snapshot(df: pd.DataFrame) -> None:
    df = df.copy()
    df["updated_at"] = pd.Timestamp.now(tz="Asia/Kolkata").isoformat()
    df.to_csv(SNAPSHOT_PATH, index=False)


def load_snapshot() -> tuple[Optional[pd.DataFrame], Optional[pd.Timestamp]]:
    if not SNAPSHOT_PATH.exists():
        return None, None
    df = pd.read_csv(SNAPSHOT_PATH)
    ts = pd.Timestamp(df["updated_at"].iloc[0]) if "updated_at" in df and len(df) else None
    return df.drop(columns=["updated_at"], errors="ignore"), ts
