"""Step 2 — Indicators: VWAP, EMA, ATR, RSI, Volume.

Each function takes a price/volume DataFrame and returns a Series. The
``add_indicators`` helper attaches a full bundle to a copy of the frame so
strategies can index columns by name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def session_vwap(df: pd.DataFrame, session: str = "1D",
                 session_key: pd.Series | None = None) -> pd.Series:
    """Volume-weighted average price, reset every ``session`` (default daily).

    When ``session_key`` is supplied, group by it instead of flooring the index
    (used by equity sessions that reset at 09:30 ET, not at UTC midnight).
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    tpv = typical * df["volume"]
    grouper = session_key if session_key is not None else df.index.floor(session)
    cum_tpv = tpv.groupby(grouper).cumsum()
    cum_vol = df["volume"].groupby(grouper).cumsum()
    return (cum_tpv / cum_vol.replace(0, np.nan)).rename("vwap")


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean().rename(f"ema_{period}")


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean().rename(f"atr_{period}")


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0).rename(f"rsi_{period}")


def volume_zscore(volume: pd.Series, period: int = 30) -> pd.Series:
    mean = volume.rolling(period, min_periods=period // 2).mean()
    std = volume.rolling(period, min_periods=period // 2).std()
    return ((volume - mean) / std.replace(0, np.nan)).fillna(0.0).rename(f"vol_z_{period}")


def add_indicators(df: pd.DataFrame, session_key: pd.Series | None = None) -> pd.DataFrame:
    out = df.copy()
    out["vwap"] = session_vwap(out, session_key=session_key)
    out["ema_9"] = ema(out["close"], 9)
    out["ema_21"] = ema(out["close"], 21)
    out["ema_50"] = ema(out["close"], 50)
    out["ema_200"] = ema(out["close"], 200)
    out["atr_14"] = atr(out, 14)
    out["rsi_14"] = rsi(out["close"], 14)
    out["vol_z_30"] = volume_zscore(out["volume"], 30)
    return out.dropna()


if __name__ == "__main__":
    from fetch_data import load_ohlcv
    res = load_ohlcv(interval="1m", bars=500)
    enriched = add_indicators(res.df)
    print(enriched.tail(3))
