"""Equity-tier strategy defaults.

Re-uses the three signal functions from ``btc_backtest.strategies`` verbatim
and only rebinds default parameters via ``functools.partial``. Equity intraday
data is less noisy than 24/7 crypto, so the entry/exit thresholds are tighter
and the volatility filters higher.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable, Dict

import pandas as pd

from btc_backtest.strategies import (
    vwap_pullback as _vwap_pullback,
    ema_breakout as _ema_breakout,
    rsi_mean_reversion as _rsi_mean_reversion,
)


vwap_pullback = partial(_vwap_pullback,
                        rsi_long=48.0, rsi_short=52.0, vol_z_min=0.5)
ema_breakout = partial(_ema_breakout,
                       lookback=20, atr_floor_pct=0.0015)
rsi_mean_reversion = partial(_rsi_mean_reversion,
                             rsi_buy=30.0, rsi_sell=70.0,
                             atr_ceiling_pct=0.0030, vwap_band_pct=0.004)


@dataclass
class StrategySpec:
    name: str
    fn: Callable[[pd.DataFrame], pd.Series]
    description: str


REGISTRY: Dict[str, StrategySpec] = {
    "vwap_pullback": StrategySpec(
        name="vwap_pullback",
        fn=vwap_pullback,
        description="Trend-aligned VWAP reclaim, equity-tier RSI/volume gates.",
    ),
    "ema_breakout": StrategySpec(
        name="ema_breakout",
        fn=ema_breakout,
        description="20-bar Donchian breakout with ATR floor 0.15%.",
    ),
    "rsi_mean_reversion": StrategySpec(
        name="rsi_mean_reversion",
        fn=rsi_mean_reversion,
        description="Range RSI fade near VWAP, ATR ceiling 0.30%.",
    ),
}
