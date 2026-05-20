"""
Omni Composite Indicator (OCI) for BTC/USDT.

Combines five signal families into one bounded score in [-100, +100]:
  Trend (30%) + Momentum (25%) + Mean Reversion (15%)
  + Volatility Regime (15%) + Volume Confirmation (15%)

The score is designed to be model-friendly: a closed-loop AI can treat OCI as
a single feature and tune only the entry/exit thresholds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / length, adjust=False).mean()
    roll_down = down.ewm(alpha=1.0 / length, adjust=False).mean()
    rs = roll_up / roll_down.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    return out.fillna(50.0)


def macd_hist(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
    macd_line = ema(series, fast) - ema(series, slow)
    sig = ema(macd_line, signal)
    return macd_line - sig


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / length, adjust=False).mean()


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = atr(df, length) * length
    plus_di = 100.0 * pd.Series(plus_dm, index=df.index).ewm(alpha=1.0 / length, adjust=False).mean() / tr.replace(0, np.nan)
    minus_di = 100.0 * pd.Series(minus_dm, index=df.index).ewm(alpha=1.0 / length, adjust=False).mean() / tr.replace(0, np.nan)
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100.0
    return dx.ewm(alpha=1.0 / length, adjust=False).mean().fillna(0.0)


def bollinger_pctb(series: pd.Series, length: int = 20, mult: float = 2.0) -> pd.Series:
    mid = series.rolling(length).mean()
    std = series.rolling(length).std(ddof=0)
    upper = mid + mult * std
    lower = mid - mult * std
    width = (upper - lower).replace(0, np.nan)
    return ((series - lower) / width).fillna(0.5)


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0.0))
    return (direction * df["volume"]).cumsum()


def zscore(series: pd.Series, length: int) -> pd.Series:
    mean = series.rolling(length).mean()
    std = series.rolling(length).std(ddof=0).replace(0, np.nan)
    return ((series - mean) / std).fillna(0.0).clip(-3, 3)


def percent_rank(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).apply(
        lambda w: (w[-1] > w[:-1]).mean() if len(w) > 1 else 0.5, raw=True
    ).fillna(0.5)


# ---------- Composite score ----------

WEIGHTS = {"trend": 0.30, "momentum": 0.25, "mean_rev": 0.15, "vol_regime": 0.15, "volume": 0.15}


def compute(df: pd.DataFrame) -> pd.DataFrame:
    """Add OCI columns to df. df must have columns: open, high, low, close, volume."""
    out = df.copy()

    # 1) Trend: EMA20 vs EMA50 + price vs EMA200
    e20, e50, e200 = ema(out["close"], 20), ema(out["close"], 50), ema(out["close"], 200)
    trend_short = np.tanh((e20 - e50) / (atr(out, 14) + 1e-9))           # [-1, 1]
    trend_long = np.tanh((out["close"] - e200) / (atr(out, 14) * 5 + 1e-9))
    trend_score = 0.6 * trend_short + 0.4 * trend_long                    # [-1, 1]

    # 2) Momentum: RSI deviation + MACD histogram z-score
    r = rsi(out["close"], 14)
    rsi_score = ((r - 50.0) / 25.0).clip(-1.5, 1.5) / 1.5                  # [-1, 1]
    macd_z = zscore(macd_hist(out["close"]), 100) / 2.5                    # ~[-1, 1]
    momentum_score = (0.5 * rsi_score + 0.5 * macd_z).clip(-1, 1)

    # 3) Mean reversion: Bollinger %B centred at 0.5, inverted (overbought = negative)
    pctb = bollinger_pctb(out["close"], 20, 2.0)
    mean_rev_score = (-(pctb - 0.5) * 2.0).clip(-1, 1)

    # 4) Volatility regime: prefer mid-range vol (penalty for extreme high or dead-low)
    atr_pct = atr(out, 14) / out["close"]
    atr_rank = percent_rank(atr_pct, 200)                                  # [0, 1]
    # Bell-shape preference: peak around 0.55, low at 0 and 1
    vol_score = (1.0 - 4.0 * (atr_rank - 0.55) ** 2).clip(-1, 1)

    # 5) Volume confirmation: OBV slope + volume z-score aligned with price direction
    obv_slope = obv(out).diff(10)
    obv_score = np.tanh(zscore(obv_slope, 100) / 1.5)
    vol_z = zscore(out["volume"], 50) / 2.5
    price_dir = np.sign(out["close"].diff(5).fillna(0.0))
    volume_score = (0.7 * obv_score + 0.3 * vol_z * price_dir).clip(-1, 1)

    out["oci_trend"] = trend_score
    out["oci_momentum"] = momentum_score
    out["oci_mean_rev"] = mean_rev_score
    out["oci_vol_regime"] = vol_score
    out["oci_volume"] = volume_score
    out["adx"] = adx(out, 14)
    out["atr"] = atr(out, 14)
    out["rsi"] = r
    # Donchian channels for breakout entries
    don_len = 20
    out["don_high"] = out["high"].rolling(don_len).max().shift(1)
    out["don_low"] = out["low"].rolling(don_len).min().shift(1)
    out["pctb"] = bollinger_pctb(out["close"], 20, 2.0)
    out["ema200"] = ema(out["close"], 200)
    out["ema50"] = ema(out["close"], 50)
    out["ema20"] = ema(out["close"], 20)
    # Compression range (10-bar) for scalp breakout trigger
    out["range_high_10"] = out["high"].rolling(10).max().shift(1)
    out["range_low_10"] = out["low"].rolling(10).min().shift(1)
    out["range_width_pct"] = (out["range_high_10"] - out["range_low_10"]) / out["close"]

    composite = (
        WEIGHTS["trend"] * trend_score
        + WEIGHTS["momentum"] * momentum_score
        + WEIGHTS["mean_rev"] * mean_rev_score
        + WEIGHTS["vol_regime"] * vol_score
        + WEIGHTS["volume"] * volume_score
    )
    out["oci"] = (composite * 100.0).clip(-100, 100)
    return out


def add_htf_filter(df: pd.DataFrame, working_tf_minutes: int = 1,
                   htf_minutes: int = 15, ema_len: int = 200) -> pd.DataFrame:
    """Add a higher-timeframe trend column `htf_trend` ∈ {-1, 0, +1}.

    The added entry condition for the scalper:
      LONG  only if htf_trend = +1
      SHORT only if htf_trend = -1
      No trade when htf_trend = 0

    Built from HTF EMA slope. EMA computed on resampled close to HTF then
    forward-filled back to the working timeframe (no look-ahead: each
    HTF candle is closed before its value propagates).
    """
    factor = htf_minutes // working_tf_minutes
    if factor < 1:
        raise ValueError("htf_minutes must be >= working_tf_minutes")
    htf_close = df["close"].iloc[::factor].copy()        # one sample per HTF bar
    htf_ema = ema(htf_close, ema_len)
    htf_slope = htf_ema.diff(3)                          # 3-bar slope on HTF
    # Trend: +1 if price > EMA AND slope up; -1 if price < EMA AND slope down
    htf_trend = pd.Series(0, index=htf_close.index, dtype=int)
    htf_trend[(htf_close > htf_ema) & (htf_slope > 0)] = 1
    htf_trend[(htf_close < htf_ema) & (htf_slope < 0)] = -1
    # Forward-fill to every working-TF bar; shift by 1 HTF bar to avoid
    # look-ahead (you only know an HTF bar's state after it closes).
    full = htf_trend.reindex(df.index, method="ffill").shift(factor).fillna(0).astype(int)
    out = df.copy()
    out["htf_trend"] = full
    out["htf_ema"] = htf_ema.reindex(df.index, method="ffill")
    return out
