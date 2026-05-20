"""
SMC-scalper indicator stack — implements the TradingView setup from the user's screenshot:
  SCALPTOOL R1.1     -> EMA stack (34, 89, 111, 144) trend regime
  HL OTT 2 1.5 15    -> Optimized Trend Tracker (VAR / band trail)
  Liquidity Concepts -> Swing pivots, BOS, CHoCH
  Order Block        -> Last opposite-colour bar before an impulse
  LuxAlgo Liquidity  -> Fixed-range Volume Profile POC (Point of Control)

All indicators are computed in a strictly look-ahead-safe way (rolling
windows reference only past bars).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategy.indicator import ema, atr


# ---------------- 1. SCALPTOOL: 4-EMA stack ----------------

def ema_stack(df: pd.DataFrame, lengths=(34, 89, 111, 144)) -> pd.DataFrame:
    out = df.copy()
    for L in lengths:
        out[f"ema{L}"] = ema(out["close"], L)
    e = [out[f"ema{L}"] for L in lengths]
    out["stack_bull"] = (e[0] > e[1]) & (e[1] > e[2]) & (e[2] > e[3])
    out["stack_bear"] = (e[0] < e[1]) & (e[1] < e[2]) & (e[2] < e[3])
    # Slope of fastest EMA over 5 bars (normalised by ATR for scale invariance)
    a = atr(out, 14)
    out["stack_slope"] = (e[0] - e[0].shift(5)) / (a + 1e-9)
    return out


# ---------------- 2. HL OTT ----------------

def vidya(close: pd.Series, length: int) -> pd.Series:
    """VIDYA: variable-index dynamic moving average (Chande)."""
    up = close.diff().clip(lower=0).rolling(length).sum()
    dn = (-close.diff().clip(upper=0)).rolling(length).sum()
    cmo = ((up - dn) / (up + dn).replace(0, np.nan)).fillna(0).abs()
    alpha = 2.0 / (length + 1)
    k = alpha * cmo
    out = close.copy().astype(float)
    for i in range(1, len(close)):
        prev = out.iloc[i - 1]
        out.iloc[i] = k.iloc[i] * close.iloc[i] + (1 - k.iloc[i]) * prev
    return out


def ott(df: pd.DataFrame, length: int = 15, pct: float = 1.5) -> pd.Series:
    """Optimized Trend Tracker — VIDYA with percent-band trailing.

    OTT acts like a slower Supertrend. Returns the trail line; direction is
    sign(close - ott).
    """
    var_ma = vidya(df["close"], length)
    band = var_ma * pct / 100.0
    long_stop = var_ma - band
    short_stop = var_ma + band
    trail = np.full(len(df), np.nan)
    direction = np.zeros(len(df), dtype=int)
    trail[0] = float(var_ma.iloc[0])
    direction[0] = 1
    for i in range(1, len(df)):
        if direction[i - 1] == 1:
            new_trail = max(trail[i - 1], float(long_stop.iloc[i]))
            if df["close"].iloc[i] < new_trail:
                direction[i] = -1
                trail[i] = float(short_stop.iloc[i])
            else:
                direction[i] = 1
                trail[i] = new_trail
        else:
            new_trail = min(trail[i - 1], float(short_stop.iloc[i]))
            if df["close"].iloc[i] > new_trail:
                direction[i] = 1
                trail[i] = float(long_stop.iloc[i])
            else:
                direction[i] = -1
                trail[i] = new_trail
    out = df.copy()
    out["ott"] = trail
    out["ott_dir"] = direction         # +1 long regime, -1 short regime
    return out


# ---------------- 3. Swing pivots + BOS / CHoCH ----------------

def swing_pivots(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.DataFrame:
    """Detect confirmed swing highs / lows.

    A pivot at bar i requires `right` bars to its right, so the pivot is
    only *known* at bar i+right (no look-ahead).
    """
    high = df["high"].values
    low = df["low"].values
    n = len(df)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(left, n - right):
        window_h = high[i - left:i + right + 1]
        window_l = low[i - left:i + right + 1]
        if high[i] == window_h.max() and high[i] > 0:
            ph[i] = high[i]
        if low[i] == window_l.min() and low[i] > 0:
            pl[i] = low[i]
    out = df.copy()
    # Shift right so the pivot value only appears at the bar it's confirmed
    out["pivot_high"] = pd.Series(ph, index=df.index).shift(right)
    out["pivot_low"] = pd.Series(pl, index=df.index).shift(right)
    out["last_ph"] = out["pivot_high"].ffill()
    out["last_pl"] = out["pivot_low"].ffill()
    return out


def bos_choch(df: pd.DataFrame) -> pd.DataFrame:
    """Break of structure + Change of character flags.

    Requires `last_ph`, `last_pl` (from `swing_pivots`).
    """
    out = df.copy()
    out["bos_up"] = (out["close"] > out["last_ph"]) & (out["close"].shift(1) <= out["last_ph"].shift(1))
    out["bos_dn"] = (out["close"] < out["last_pl"]) & (out["close"].shift(1) >= out["last_pl"].shift(1))
    # Market-state machine: +1 bull regime, -1 bear regime
    state = np.zeros(len(out), dtype=int)
    s = 0
    choch = np.zeros(len(out), dtype=int)
    bos_up = out["bos_up"].values
    bos_dn = out["bos_dn"].values
    for i in range(len(out)):
        if bos_up[i] and s <= 0:
            choch[i] = 1     # change of character to bull
            s = 1
        elif bos_dn[i] and s >= 0:
            choch[i] = -1
            s = -1
        state[i] = s
    out["smc_state"] = state
    out["choch"] = choch
    return out


# ---------------- 4. Order Blocks ----------------

def order_blocks(df: pd.DataFrame, impulse_atr: float = 1.5,
                 lookback: int = 50) -> pd.DataFrame:
    """Last opposite-colour bar before an impulse of >= impulse_atr * ATR.

    Emits bullish_ob_high / bullish_ob_low and bearish_ob_high / bearish_ob_low
    forward-filled until invalidated (price closes through the OB body).
    """
    out = df.copy()
    a = atr(out, 14).values
    op = out["open"].values
    cl = out["close"].values
    hi = out["high"].values
    lo = out["low"].values

    bull_h = np.full(len(out), np.nan)
    bull_l = np.full(len(out), np.nan)
    bear_h = np.full(len(out), np.nan)
    bear_l = np.full(len(out), np.nan)

    last_bull = None
    last_bear = None

    for i in range(2, len(out)):
        body = cl[i] - cl[i - 1]
        thresh = impulse_atr * a[i]
        # Bullish impulse → previous bar(s) bear candle = bullish OB
        if body > thresh and a[i] > 0:
            # Find last bear candle in last lookback bars
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if cl[j] < op[j]:
                    last_bull = (hi[j], lo[j])
                    break
        if body < -thresh and a[i] > 0:
            for j in range(i - 1, max(0, i - lookback) - 1, -1):
                if cl[j] > op[j]:
                    last_bear = (hi[j], lo[j])
                    break
        # Invalidate if price closes through
        if last_bull is not None and cl[i] < last_bull[1]:
            last_bull = None
        if last_bear is not None and cl[i] > last_bear[0]:
            last_bear = None
        if last_bull is not None:
            bull_h[i], bull_l[i] = last_bull
        if last_bear is not None:
            bear_h[i], bear_l[i] = last_bear

    out["bull_ob_high"] = bull_h
    out["bull_ob_low"] = bull_l
    out["bear_ob_high"] = bear_h
    out["bear_ob_low"] = bear_l
    # Freshness: bars since the OB last refreshed
    bull_age = np.full(len(out), 999, dtype=int)
    bear_age = np.full(len(out), 999, dtype=int)
    age = 999
    prev_bull = None
    for i in range(len(out)):
        cur = (bull_h[i], bull_l[i])
        if not np.isnan(cur[0]):
            if prev_bull != cur:
                age = 0
                prev_bull = cur
            else:
                age += 1
        else:
            age = 999
            prev_bull = None
        bull_age[i] = age
    age = 999
    prev_bear = None
    for i in range(len(out)):
        cur = (bear_h[i], bear_l[i])
        if not np.isnan(cur[0]):
            if prev_bear != cur:
                age = 0
                prev_bear = cur
            else:
                age += 1
        else:
            age = 999
            prev_bear = None
        bear_age[i] = age
    out["bull_ob_age"] = bull_age
    out["bear_ob_age"] = bear_age
    return out


# ---------------- 5. Fixed-Range Volume Profile POC ----------------

def volume_profile_poc(df: pd.DataFrame, window: int = 360, bins: int = 50) -> pd.DataFrame:
    """Rolling fixed-range volume profile.

    For each bar i, compute POC over the prior `window` bars and the
    high-volume node range (top 30% of volume).
    """
    out = df.copy()
    poc = np.full(len(out), np.nan)
    hvn_high = np.full(len(out), np.nan)
    hvn_low = np.full(len(out), np.nan)
    close = out["close"].values
    vol = out["volume"].values
    high = out["high"].values
    low = out["low"].values
    # Pre-compute typical price for binning
    tp = (high + low + close) / 3.0
    for i in range(window, len(out)):
        lo_i = i - window
        prices = tp[lo_i:i]
        vols = vol[lo_i:i]
        if prices.max() == prices.min():
            continue
        edges = np.linspace(prices.min(), prices.max(), bins + 1)
        idx = np.digitize(prices, edges) - 1
        idx = np.clip(idx, 0, bins - 1)
        hist = np.zeros(bins)
        for k in range(len(prices)):
            hist[idx[k]] += vols[k]
        if hist.sum() == 0:
            continue
        peak = int(hist.argmax())
        poc[i] = 0.5 * (edges[peak] + edges[peak + 1])
        # HVN range: bins with >= 70th-percentile volume
        thresh = np.quantile(hist[hist > 0], 0.70)
        mask = hist >= thresh
        if mask.any():
            hi_idx = np.where(mask)[0].max()
            lo_idx = np.where(mask)[0].min()
            hvn_high[i] = edges[hi_idx + 1]
            hvn_low[i] = edges[lo_idx]
    out["poc"] = poc
    out["hvn_high"] = hvn_high
    out["hvn_low"] = hvn_low
    return out


# ---------------- Pipeline ----------------

def compute_smc(df: pd.DataFrame, vp_window: int = 360, pivot_k: int = 5) -> pd.DataFrame:
    """Run the full SMC indicator stack on OHLCV input."""
    df = ema_stack(df)
    df = ott(df, length=15, pct=1.5)
    df = swing_pivots(df, left=pivot_k, right=pivot_k)
    df = bos_choch(df)
    df = order_blocks(df, impulse_atr=1.5, lookback=50)
    df = volume_profile_poc(df, window=vp_window, bins=50)
    df["atr"] = atr(df, 14)
    return df
