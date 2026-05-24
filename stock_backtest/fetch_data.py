"""Fetcher for xStocks priced off their underlying US equities.

Hierarchy: Yahoo chart REST -> Stooq daily CSV -> on-disk cache ->
equity-calibrated GBM synthetic. Returns OHLCV in the same shape as
``btc_backtest.fetch_data.FetchResult`` so downstream modules don't care.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from io import StringIO
from typing import Dict, Optional

import numpy as np
import pandas as pd
import requests

from .calendar import BARS_PER_YEAR_RTH, INTERVAL_MINUTES, TZ, rth_index, rth_mask


# Snapshot of Bybit-listed xStocks (Backed Finance issuance) as of 2025-Q2.
# Verify against https://www.bybit.com/en/trade/spot for staleness before live use.
BYBIT_XSTOCKS_LISTED: tuple[str, ...] = (
    "AAPLx", "TSLAx", "NVDAx", "MSFTx", "GOOGLx",
    "METAx", "AMZNx", "SPYx", "QQQx",
    "COINx", "MSTRx", "CRCLx",
)

XSTOCK_TO_UNDERLYING: Dict[str, str] = {
    "AAPLx": "AAPL", "TSLAx": "TSLA", "NVDAx": "NVDA", "MSFTx": "MSFT",
    "GOOGLx": "GOOGL", "METAx": "META", "AMZNx": "AMZN",
    "SPYx": "SPY", "QQQx": "QQQ",
    "COINx": "COIN", "MSTRx": "MSTR", "CRCLx": "CRCL",
}

# Approximate spot starting prices and annualised vols used when no live data
# is available. ETFs (SPY/QQQ) get tighter vol than single names.
SYNTHETIC_SEED: Dict[str, tuple[float, float]] = {
    "AAPLx": (205.0, 0.28),
    "TSLAx": (260.0, 0.55),
    "NVDAx": (135.0, 0.50),
    "MSFTx": (420.0, 0.26),
    "GOOGLx": (175.0, 0.30),
    "METAx": (560.0, 0.36),
    "AMZNx": (200.0, 0.32),
    "SPYx": (560.0, 0.16),
    "QQQx": (490.0, 0.20),
    "COINx": (240.0, 0.70),
    "MSTRx": (320.0, 0.85),
    "CRCLx": (35.0, 0.55),
}

YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
YAHOO_RANGE_CAP = {"1m": "7d", "5m": "60d", "15m": "60d", "1h": "730d", "1d": "5y"}
USER_AGENT = "Mozilla/5.0 (compatible; xStocks-Backtester/1.0)"


@dataclass
class FetchResult:
    df: pd.DataFrame
    source: str   # "yahoo" | "stooq" | "cache" | "synthetic"
    symbol: str   # xStock symbol e.g. "AAPLx"
    underlying: str
    interval: str


def to_underlying(symbol: str) -> str:
    if symbol not in XSTOCK_TO_UNDERLYING:
        raise KeyError(f"{symbol} is not in the Bybit xStock map; "
                       f"known: {sorted(XSTOCK_TO_UNDERLYING)}")
    return XSTOCK_TO_UNDERLYING[symbol]


def _yahoo_chart(underlying: str, interval: str, rng: str) -> Optional[pd.DataFrame]:
    for host in YAHOO_HOSTS:
        url = f"https://{host}/v8/finance/chart/{underlying}"
        params = {"interval": interval, "range": rng, "includePrePost": "false"}
        try:
            r = requests.get(url, params=params, timeout=8,
                             headers={"User-Agent": USER_AGENT})
            if r.status_code != 200:
                continue
            payload = r.json()
            res = payload.get("chart", {}).get("result")
            if not res:
                continue
            block = res[0]
            ts = block.get("timestamp")
            ind = block.get("indicators", {}).get("quote", [{}])[0]
            if not ts or not ind.get("close"):
                continue
            df = pd.DataFrame({
                "open": ind["open"], "high": ind["high"], "low": ind["low"],
                "close": ind["close"], "volume": ind["volume"],
            }, index=pd.to_datetime(ts, unit="s", utc=True))
            df.index.name = "timestamp"
            return df.dropna(subset=["open", "high", "low", "close"])
        except requests.RequestException:
            continue
    return None


def _stooq_daily(underlying: str) -> Optional[pd.DataFrame]:
    url = f"https://stooq.com/q/d/l/?s={underlying.lower()}.us&i=d"
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200 or not r.text.strip().startswith("Date"):
            return None
        df = pd.read_csv(StringIO(r.text))
        df["timestamp"] = pd.to_datetime(df["Date"], utc=True)
        df = df.rename(columns={"Open": "open", "High": "high", "Low": "low",
                                "Close": "close", "Volume": "volume"})
        return df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    except requests.RequestException:
        return None


def _synthetic_ohlcv(symbol: str, interval: str, n_bars: int) -> pd.DataFrame:
    """Equity-calibrated GBM with RTH-aware index + overnight gaps."""
    start_price, annual_vol = SYNTHETIC_SEED.get(symbol, (100.0, 0.30))
    seed = hash(symbol) & 0xFFFF
    rng = np.random.default_rng(seed)

    bpy = BARS_PER_YEAR_RTH[interval]
    mu = 0.07 / bpy
    sigma = annual_vol / np.sqrt(bpy)

    idx = rth_index(interval, n_bars)
    et = idx.tz_convert(TZ)
    day = et.normalize()
    new_session = np.concatenate([[True], day[1:] != day[:-1]])

    returns = rng.normal(mu, sigma, size=n_bars)
    # Overnight gap injection at every session boundary (except the first bar).
    gap = rng.normal(0.0, 0.005, size=n_bars)
    returns = np.where(new_session, returns + gap, returns)
    # Occasional intraday surprises.
    jumps = rng.choice([0.0, 1.0], size=n_bars, p=[0.998, 0.002]) * rng.normal(0, 4 * sigma, size=n_bars)
    returns = returns + jumps

    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.empty_like(close)
    open_[0] = start_price
    open_[1:] = close[:-1]
    wick = np.abs(rng.normal(0, sigma * 0.6, size=n_bars)) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    base_vol = rng.lognormal(mean=11.0, sigma=0.5, size=n_bars)
    volume = base_vol * (1 + 30 * np.abs(returns))

    return pd.DataFrame({
        "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    }, index=idx)


def _from_cache(cache_path: str, bars: int) -> Optional[pd.DataFrame]:
    if not os.path.exists(cache_path):
        return None
    df = pd.read_csv(cache_path, index_col="timestamp", parse_dates=True)
    if len(df) < bars // 2:
        return None
    return df.tail(bars)


def load_ohlcv(symbol: str, interval: str = "5m", bars: int = 2000,
               cache_dir: str = "data", force_synthetic: bool = False,
               rth_only: bool = True) -> FetchResult:
    if symbol not in XSTOCK_TO_UNDERLYING:
        raise KeyError(f"{symbol} not in xStock map")
    underlying = XSTOCK_TO_UNDERLYING[symbol]

    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol}_{interval}.csv")

    if not force_synthetic:
        rng_str = YAHOO_RANGE_CAP.get(interval, "60d")
        df = _yahoo_chart(underlying, interval, rng_str)
        if df is not None and len(df) > 50:
            if rth_only:
                df = df[rth_mask(df.index)]
            df.to_csv(cache_path)
            time.sleep(0.4)  # be polite between symbols
            return FetchResult(df=df.tail(bars), source="yahoo",
                               symbol=symbol, underlying=underlying, interval=interval)

        if interval in ("1h", "1d"):
            df = _stooq_daily(underlying)
            if df is not None and len(df) > 50:
                df.to_csv(cache_path)
                return FetchResult(df=df.tail(bars), source="stooq",
                                   symbol=symbol, underlying=underlying, interval=interval)

        cached = _from_cache(cache_path, bars)
        if cached is not None:
            return FetchResult(df=cached, source="cache",
                               symbol=symbol, underlying=underlying, interval=interval)

    df = _synthetic_ohlcv(symbol, interval, bars)
    df.to_csv(cache_path)
    return FetchResult(df=df, source="synthetic",
                       symbol=symbol, underlying=underlying, interval=interval)


if __name__ == "__main__":
    for s in ("AAPLx", "TSLAx", "SPYx"):
        res = load_ohlcv(s, interval="5m", bars=500, force_synthetic=True)
        print(f"{res.symbol} ({res.underlying}) {res.interval}: "
              f"{len(res.df)} bars  source={res.source}")
        print(res.df.tail(2))
