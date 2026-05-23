"""Step 3 — three AI-proposed strategies.

Each strategy is a pure function ``signal(df) -> Series`` returning a target
position in {-1, 0, +1}. The backtester translates a change in target into a
trade. Signals are computed on closed-bar information only — the engine
applies a one-bar execution lag to avoid look-ahead bias.

Strategies
----------
1. ``vwap_pullback``
   Trend filter via EMA-50 vs EMA-200; entries on pullbacks to VWAP that
   reclaim with RSI confirmation and elevated volume.

2. ``ema_breakout``
   Donchian-style breakout of recent N-bar high/low gated by EMA-21 slope
   and an ATR-based volatility filter to skip dead tape.

3. ``rsi_mean_reversion``
   Counter-trend fades when RSI plunges/spikes inside a range regime
   (price near VWAP, low ATR), with quick exits back to the mean.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Strategy 1 — VWAP pullback in the direction of the EMA trend
# ---------------------------------------------------------------------------
def vwap_pullback(df: pd.DataFrame,
                  rsi_long: float = 45.0,
                  rsi_short: float = 55.0,
                  vol_z_min: float = 0.3) -> pd.Series:
    trend_up = df["ema_50"] > df["ema_200"]
    trend_dn = df["ema_50"] < df["ema_200"]

    above_vwap = df["close"] > df["vwap"]
    below_vwap = df["close"] < df["vwap"]
    prev_below = above_vwap.shift(1).fillna(False) == False  # was at/below
    prev_above = below_vwap.shift(1).fillna(False) == False

    long_entry = trend_up & above_vwap & prev_below & (df["rsi_14"] > rsi_long) & (df["vol_z_30"] > vol_z_min)
    short_entry = trend_dn & below_vwap & prev_above & (df["rsi_14"] < rsi_short) & (df["vol_z_30"] > vol_z_min)

    # Exit when price closes back through VWAP against the position
    pos = pd.Series(0, index=df.index, dtype=int)
    current = 0
    for i in range(len(df)):
        if current == 1 and df["close"].iat[i] < df["vwap"].iat[i]:
            current = 0
        elif current == -1 and df["close"].iat[i] > df["vwap"].iat[i]:
            current = 0
        if current == 0:
            if long_entry.iat[i]:
                current = 1
            elif short_entry.iat[i]:
                current = -1
        pos.iat[i] = current
    return pos.rename("vwap_pullback")


# ---------------------------------------------------------------------------
# Strategy 2 — Donchian breakout with EMA slope + ATR filter
# ---------------------------------------------------------------------------
def ema_breakout(df: pd.DataFrame,
                 lookback: int = 30,
                 atr_floor_pct: float = 0.0008) -> pd.Series:
    hh = df["high"].rolling(lookback).max().shift(1)
    ll = df["low"].rolling(lookback).min().shift(1)
    slope_up = df["ema_21"].diff(5) > 0
    slope_dn = df["ema_21"].diff(5) < 0
    vol_ok = (df["atr_14"] / df["close"]) > atr_floor_pct

    long_entry = (df["close"] > hh) & slope_up & vol_ok
    short_entry = (df["close"] < ll) & slope_dn & vol_ok

    # Trail exit: close back inside the channel mid (EMA-21)
    pos = pd.Series(0, index=df.index, dtype=int)
    current = 0
    for i in range(len(df)):
        if current == 1 and df["close"].iat[i] < df["ema_21"].iat[i]:
            current = 0
        elif current == -1 and df["close"].iat[i] > df["ema_21"].iat[i]:
            current = 0
        if current == 0:
            if long_entry.iat[i]:
                current = 1
            elif short_entry.iat[i]:
                current = -1
        pos.iat[i] = current
    return pos.rename("ema_breakout")


# ---------------------------------------------------------------------------
# Strategy 3 — RSI mean reversion inside low-vol / range regimes
# ---------------------------------------------------------------------------
def rsi_mean_reversion(df: pd.DataFrame,
                       rsi_buy: float = 25.0,
                       rsi_sell: float = 75.0,
                       atr_ceiling_pct: float = 0.0020,
                       vwap_band_pct: float = 0.003) -> pd.Series:
    quiet = (df["atr_14"] / df["close"]) < atr_ceiling_pct
    near_vwap = (df["close"] - df["vwap"]).abs() / df["close"] < vwap_band_pct
    regime = quiet & near_vwap

    long_entry = regime & (df["rsi_14"] < rsi_buy)
    short_entry = regime & (df["rsi_14"] > rsi_sell)

    pos = pd.Series(0, index=df.index, dtype=int)
    current = 0
    for i in range(len(df)):
        # Exit when RSI mean-reverts through 50, or regime breaks
        if current == 1 and (df["rsi_14"].iat[i] >= 50.0 or not quiet.iat[i]):
            current = 0
        elif current == -1 and (df["rsi_14"].iat[i] <= 50.0 or not quiet.iat[i]):
            current = 0
        if current == 0:
            if long_entry.iat[i]:
                current = 1
            elif short_entry.iat[i]:
                current = -1
        pos.iat[i] = current
    return pos.rename("rsi_mean_reversion")


@dataclass
class StrategySpec:
    name: str
    fn: Callable[[pd.DataFrame], pd.Series]
    description: str


REGISTRY: Dict[str, StrategySpec] = {
    "vwap_pullback": StrategySpec(
        name="vwap_pullback",
        fn=vwap_pullback,
        description="Trend-aligned VWAP reclaim with RSI + volume confirmation.",
    ),
    "ema_breakout": StrategySpec(
        name="ema_breakout",
        fn=ema_breakout,
        description="Donchian breakout filtered by EMA-21 slope and ATR floor.",
    ),
    "rsi_mean_reversion": StrategySpec(
        name="rsi_mean_reversion",
        fn=rsi_mean_reversion,
        description="Counter-trend RSI fades inside a low-ATR range near VWAP.",
    ),
}
