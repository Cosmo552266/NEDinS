"""
Data loader for BTC/USDT.

- `fetch_binance`: live klines from Binance public REST (requires network)
- `synthetic_btc`: regime-switching GBM calibrated to BTC stats, used when
  the sandbox blocks exchange APIs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fetch_binance(symbol: str = "BTCUSDT", interval: str = "15m", limit: int = 1000) -> pd.DataFrame:
    import requests
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore",
    ])
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = df[c].astype(float)
    df.index = pd.to_datetime(df["open_time"], unit="ms")
    return df[["open", "high", "low", "close", "volume"]]


def synthetic_btc(n_bars: int = 17_280, seed: int = 7, start_price: float = 60_000.0,
                  bar_minutes: int = 15) -> pd.DataFrame:
    """Generate realistic-looking BTC/USDT OHLCV with vol clustering and regime switches.

    Defaults n_bars=17,280 @ 15m ≈ 180 days. For 1m scalping use
    n_bars=259_200, bar_minutes=1. Calibrated to BTC annual vol ~65%.
    """
    rng = np.random.default_rng(seed)
    bars_per_year = (365 * 24 * 60) // bar_minutes
    target_annual_vol = 0.65
    base_sigma = target_annual_vol / np.sqrt(bars_per_year)

    # Regime drifts/durations were calibrated on 15m bars. Scale to current TF
    # so 1m and 15m runs produce comparable price paths.
    drift_scale = bar_minutes / 15.0
    dur_scale = 15.0 / bar_minutes      # 1m → 15× more bars per regime

    # Regime states: 0=bull-trend, 1=bear-trend, 2=range, 3=high-vol-chop
    regimes = np.array([
        (+0.000035 * drift_scale, 0.9, 1500 * dur_scale),
        (-0.000040 * drift_scale, 1.1, 1000 * dur_scale),
        (+0.000000 * drift_scale, 0.6,  800 * dur_scale),
        (+0.000005 * drift_scale, 2.2,  400 * dur_scale),
    ], dtype=[("drift", "f8"), ("volmul", "f8"), ("dur", "f8")])

    # GARCH-like vol process
    vol = np.empty(n_bars)
    vol[0] = base_sigma
    eps = rng.standard_normal(n_bars)

    state = 0
    state_remaining = int(regimes[state]["dur"])
    states = np.empty(n_bars, dtype=int)

    # AR(1) on log returns. phi ≈ 0.08 for 15m, ≈ 0.12 for 1m (active hours).
    # Higher TF → less serial correlation as noise averages out.
    phi = 0.12 if bar_minutes <= 5 else 0.08
    returns = np.empty(n_bars)
    prev_ret = 0.0
    for t in range(n_bars):
        if state_remaining <= 0:
            state = int(rng.integers(0, 4))
            state_remaining = int(rng.exponential(regimes[state]["dur"]))
        states[t] = state
        state_remaining -= 1

        if t > 0:
            sigma2 = 0.05 * base_sigma**2 + 0.08 * (returns[t-1])**2 + 0.87 * vol[t-1]**2
            vol[t] = float(np.clip(np.sqrt(sigma2), 0.2 * base_sigma, 6.0 * base_sigma))
        drift = regimes[state]["drift"]
        sigma = vol[t] * regimes[state]["volmul"]
        innovation = sigma * eps[t]
        ret = drift + phi * prev_ret + innovation
        ret = float(np.clip(ret, -0.15, 0.15))
        returns[t] = ret
        prev_ret = ret

    # Build closes
    close = start_price * np.exp(np.cumsum(returns))

    # Intra-bar OHLC: each bar's high/low derived from sub-bar BM
    n_sub = 8
    sub_eps = rng.standard_normal((n_bars, n_sub))
    sub_sigma = (vol * np.array([regimes[s]["volmul"] for s in states])) / np.sqrt(n_sub)
    sub_returns = sub_eps * sub_sigma[:, None]
    sub_prices = np.exp(np.cumsum(sub_returns, axis=1))
    prev_close = np.concatenate([[start_price], close[:-1]])
    bar_open = prev_close
    bar_path = bar_open[:, None] * sub_prices
    # Rescale so the last sub-price hits the realized close exactly
    bar_path = bar_path * (close / bar_path[:, -1])[:, None]
    bar_high = bar_path.max(axis=1)
    bar_low = bar_path.min(axis=1)
    # Ensure open/close within [low, high]
    bar_high = np.maximum(bar_high, np.maximum(bar_open, close))
    bar_low = np.minimum(bar_low, np.minimum(bar_open, close))

    # Volume: log-normal, higher in high-vol regimes
    base_vol = rng.lognormal(mean=4.0, sigma=0.5, size=n_bars)
    vol_state_mul = np.array([1.0, 1.2, 0.7, 1.8])[states]
    bar_volume = base_vol * vol_state_mul * (1 + np.abs(returns) * 30)

    idx = pd.date_range("2025-11-01", periods=n_bars, freq=f"{bar_minutes}min")
    df = pd.DataFrame({
        "open": bar_open,
        "high": bar_high,
        "low": bar_low,
        "close": close,
        "volume": bar_volume,
    }, index=idx)
    return df


def load(use_live: bool = False) -> pd.DataFrame:
    if use_live:
        try:
            return fetch_binance()
        except Exception as exc:  # noqa: BLE001
            print(f"[data_loader] live fetch failed ({exc}); falling back to synthetic")
    return synthetic_btc()
