"""US equity RTH calendar helpers.

xStocks themselves trade 24/7 on Bybit, but the underlying US equities (which
this backtest uses as a price proxy) only trade 09:30-16:00 America/New_York
on regular session days. ``rth_index`` produces a contiguous sequence of RTH
timestamps skipping nights and weekends so synthetic series and annualisation
match the real session structure.
"""
from __future__ import annotations

from datetime import time
from typing import Dict

import numpy as np
import pandas as pd


TZ = "America/New_York"
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)

# Bars per regular trading year (252 sessions * 6.5h). For 1d we use 252.
BARS_PER_YEAR_RTH: Dict[str, float] = {
    "1m": 252 * 390,        # 98_280
    "5m": 252 * 78,         # 19_656
    "15m": 252 * 26,        # 6_552
    "1h": 252 * 6.5,        # 1_638
    "1d": 252,
}

INTERVAL_MINUTES: Dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 60 * 390}


def bars_per_year(interval: str) -> float:
    if interval not in BARS_PER_YEAR_RTH:
        raise ValueError(f"unsupported interval: {interval}")
    return BARS_PER_YEAR_RTH[interval]


def rth_mask(idx: pd.DatetimeIndex) -> np.ndarray:
    """True for timestamps inside 09:30-16:00 ET on Mon-Fri."""
    et = idx.tz_convert(TZ) if idx.tz is not None else idx.tz_localize("UTC").tz_convert(TZ)
    weekday = et.weekday < 5
    t = et.time
    in_session = np.array([RTH_OPEN <= x < RTH_CLOSE for x in t])
    return weekday & in_session


def session_id(idx: pd.DatetimeIndex) -> pd.Series:
    """ET trading-day label used to reset session-VWAP."""
    et = idx.tz_convert(TZ) if idx.tz is not None else idx.tz_localize("UTC").tz_convert(TZ)
    return pd.Series(et.normalize().tz_localize(None), index=idx, name="session_id")


def rth_index(interval: str, n_bars: int, end: pd.Timestamp | None = None) -> pd.DatetimeIndex:
    """Build a contiguous RTH DatetimeIndex of ``n_bars`` bars ending at ``end``."""
    if interval == "1d":
        end = end or pd.Timestamp.now(tz="UTC").normalize()
        days = pd.bdate_range(end=end.tz_convert(TZ).normalize(), periods=n_bars, tz=TZ)
        return days.tz_convert("UTC")

    step = pd.Timedelta(minutes=INTERVAL_MINUTES[interval])
    end = end or pd.Timestamp.now(tz="UTC")
    end_et = end.tz_convert(TZ) if end.tzinfo else end.tz_localize("UTC").tz_convert(TZ)
    bars_per_day = int(BARS_PER_YEAR_RTH[interval] / 252)

    days_needed = (n_bars + bars_per_day - 1) // bars_per_day + 2
    session_days = pd.bdate_range(end=end_et.normalize(), periods=days_needed, tz=TZ)

    out: list[pd.Timestamp] = []
    for day in session_days:
        open_ts = day + pd.Timedelta(hours=9, minutes=30)
        for k in range(bars_per_day):
            out.append(open_ts + k * step)
    full = pd.DatetimeIndex(out, tz=TZ).sort_values()
    full = full[full <= end_et]
    return full[-n_bars:].tz_convert("UTC")
