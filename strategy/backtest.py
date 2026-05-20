"""
Event-driven backtest engine for the OCI strategy on BTC/USDT perpetual.

Rules (matches STRATEGY.md):
  Entry  LONG  : oci > +LONG_TH  AND adx > ADX_MIN AND rsi < 78
  Entry  SHORT : oci < -SHORT_TH AND adx > ADX_MIN AND rsi > 22
  Sizing       : risk = RISK_PCT * equity; qty = risk / (stop_distance)
                 leverage capped at MAX_LEV
  Stop         : 1.5 * ATR from entry
  Take profit  : 3.0 * ATR (R:R = 2.0)
  Trailing     : after price moves 1R in favour, trail by 1.0 * ATR
  Time stop    : exit after MAX_BARS bars in trade
  Flip exit    : exit if OCI sign flips strongly against position
  Fees         : taker fee per side, slippage in bps
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Config:
    """Defaults are the all-seed-positive configuration from strategy/diagnose.py."""
    starting_equity: float = 26.0
    risk_pct: float = 0.06              # 6% of equity per trade (fixed-fractional)
    max_leverage: float = 3.0           # higher lev gets killed by fees
    long_threshold: float = 55.0        # only the strongest OCI signals
    short_threshold: float = 55.0
    adx_min: float = 18.0
    sl_atr: float = 1.0                 # tight initial stop
    tp_atr: float = 4.0                 # asymmetric R:R = 4
    trail_atr: float = 3.5              # chandelier exit (loose)
    trail_activate_R: float = 1.5       # only trail after 1.5R MFE
    max_bars_in_trade: int = 192        # 48h on 15m
    flip_exit_threshold: float = 25.0
    taker_fee_bps: float = 4.0          # 0.04% per side
    slippage_bps: float = 2.0
    entry_mode: str = "breakout"        # "oci_only", "breakout", "mean_reversion"
    mr_rsi_long: float = 30.0
    mr_rsi_short: float = 70.0
    mr_pctb_long: float = 0.10
    mr_pctb_short: float = 0.90
    mr_trend_filter: bool = True


@dataclass
class Trade:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    stop: float
    take: float
    qty: float
    notional: float
    leverage: float
    risk_dollars: float        # 1R = this many $ (set at entry)
    initial_stop: float        # for trail-vs-stop discrimination
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str = ""
    pnl: float = 0.0
    r_multiple: float = 0.0
    bars_held: int = 0
    peak_favourable: float = 0.0
    trail_active: bool = False


@dataclass
class Result:
    equity_curve: pd.Series
    trades: list[Trade] = field(default_factory=list)

    def stats(self) -> dict:
        if not self.trades:
            return {"trades": 0}
        pnls = np.array([t.pnl for t in self.trades])
        rs = np.array([t.r_multiple for t in self.trades])
        wins = pnls > 0
        eq = self.equity_curve.values
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak
        return {
            "trades": len(self.trades),
            "final_equity": float(eq[-1]),
            "total_return_x": float(eq[-1] / eq[0]),
            "win_rate": float(wins.mean()),
            "avg_R": float(rs.mean()),
            "expectancy_R": float(rs.mean()),
            "profit_factor": float(pnls[wins].sum() / -pnls[~wins].sum()) if (~wins).any() and pnls[~wins].sum() < 0 else float("inf"),
            "max_drawdown": float(dd.min()),
            "sharpe_per_bar": float(np.mean(np.diff(eq) / eq[:-1]) / (np.std(np.diff(eq) / eq[:-1]) + 1e-12)),
        }


def _fee(notional: float, cfg: Config) -> float:
    return notional * (cfg.taker_fee_bps + cfg.slippage_bps) / 10_000.0


def backtest(df: pd.DataFrame, cfg: Config | None = None) -> Result:
    cfg = cfg or Config()
    df = df.dropna().reset_index().rename(columns={"index": "ts"})
    equity = cfg.starting_equity
    eq_curve = np.empty(len(df))
    pos: Trade | None = None
    trades: list[Trade] = []

    for i in range(len(df)):
        row = df.iloc[i]
        price = float(row["close"])
        high = float(row["high"])
        low = float(row["low"])
        atr_val = float(row["atr"])
        oci = float(row["oci"])
        adx_val = float(row["adx"])
        rsi_val = float(row["rsi"])

        # --- Manage open position ---
        if pos is not None:
            pos.bars_held += 1
            one_r_price = abs(pos.entry_price - pos.initial_stop)
            activate_at = cfg.trail_activate_R * one_r_price

            if pos.side == "long":
                pos.peak_favourable = max(pos.peak_favourable, high - pos.entry_price)
                if pos.peak_favourable >= activate_at:
                    pos.trail_active = True
                    new_stop = (pos.entry_price + pos.peak_favourable) - cfg.trail_atr * atr_val
                    pos.stop = max(pos.stop, new_stop)
            else:
                pos.peak_favourable = max(pos.peak_favourable, pos.entry_price - low)
                if pos.peak_favourable >= activate_at:
                    pos.trail_active = True
                    new_stop = (pos.entry_price - pos.peak_favourable) + cfg.trail_atr * atr_val
                    pos.stop = min(pos.stop, new_stop)

            exit_price = None
            exit_reason = ""

            if pos.side == "long":
                if low <= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif high >= pos.take:
                    exit_price, exit_reason = pos.take, "take"
                elif oci < -cfg.flip_exit_threshold:
                    exit_price, exit_reason = price, "flip"
                elif pos.bars_held >= cfg.max_bars_in_trade:
                    exit_price, exit_reason = price, "time"
            else:
                if high >= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif low <= pos.take:
                    exit_price, exit_reason = pos.take, "take"
                elif oci > cfg.flip_exit_threshold:
                    exit_price, exit_reason = price, "flip"
                elif pos.bars_held >= cfg.max_bars_in_trade:
                    exit_price, exit_reason = price, "time"

            if exit_price is not None:
                if pos.side == "long":
                    raw_pnl = (exit_price - pos.entry_price) * pos.qty
                else:
                    raw_pnl = (pos.entry_price - exit_price) * pos.qty
                fee_out = _fee(exit_price * pos.qty, cfg)
                pos.pnl = raw_pnl - fee_out
                pos.exit_price = exit_price
                pos.exit_time = row["ts"]
                pos.exit_reason = exit_reason
                pos.r_multiple = pos.pnl / pos.risk_dollars if pos.risk_dollars > 0 else 0.0
                equity += pos.pnl
                trades.append(pos)
                pos = None

        # --- New entry ---
        if pos is None and i >= 200:  # warm-up
            if cfg.entry_mode == "oci_only":
                long_ok = oci > cfg.long_threshold and adx_val > cfg.adx_min and rsi_val < 78
                short_ok = oci < -cfg.short_threshold and adx_val > cfg.adx_min and rsi_val > 22
            elif cfg.entry_mode == "breakout":
                don_h = float(row.get("don_high", np.inf))
                don_l = float(row.get("don_low", -np.inf))
                oci_long_ok = oci > cfg.long_threshold and adx_val > cfg.adx_min
                oci_short_ok = oci < -cfg.short_threshold and adx_val > cfg.adx_min
                long_ok = oci_long_ok and high >= don_h
                short_ok = oci_short_ok and low <= don_l
            else:  # mean_reversion
                pctb = float(row.get("pctb", 0.5))
                ema200_val = float(row.get("ema200", price))
                trend_up = price > ema200_val
                trend_dn = price < ema200_val
                # Buy oversold dip in established uptrend; require OCI not screaming down
                long_ok = (
                    rsi_val <= cfg.mr_rsi_long
                    and pctb <= cfg.mr_pctb_long
                    and (not cfg.mr_trend_filter or trend_up)
                    and oci > -cfg.long_threshold  # OCI not collapsing
                )
                short_ok = (
                    rsi_val >= cfg.mr_rsi_short
                    and pctb >= cfg.mr_pctb_short
                    and (not cfg.mr_trend_filter or trend_dn)
                    and oci < cfg.short_threshold
                )
            if long_ok or short_ok:
                side = "long" if long_ok else "short"
                stop_dist = cfg.sl_atr * atr_val
                if stop_dist <= 0 or equity <= 1.0:
                    eq_curve[i] = equity
                    continue
                risk_dollars = cfg.risk_pct * equity
                qty = risk_dollars / stop_dist
                notional = qty * price
                lev = notional / equity
                if lev > cfg.max_leverage:
                    lev = cfg.max_leverage
                    notional = lev * equity
                    qty = notional / price
                fee_in = _fee(notional, cfg)
                equity -= fee_in
                if side == "long":
                    entry, stop, take = price, price - stop_dist, price + cfg.tp_atr * atr_val
                else:
                    entry, stop, take = price, price + stop_dist, price - cfg.tp_atr * atr_val
                pos = Trade(side=side, entry_time=row["ts"], entry_price=entry,
                            stop=stop, take=take, qty=qty, notional=notional, leverage=lev,
                            risk_dollars=risk_dollars, initial_stop=stop)

        eq_curve[i] = equity

    # Close open position at end
    if pos is not None:
        last = df.iloc[-1]
        exit_price = float(last["close"])
        if pos.side == "long":
            raw_pnl = (exit_price - pos.entry_price) * pos.qty
        else:
            raw_pnl = (pos.entry_price - exit_price) * pos.qty
        fee_out = _fee(exit_price * pos.qty, cfg)
        pos.pnl = raw_pnl - fee_out
        pos.exit_price = exit_price
        pos.exit_time = last["ts"]
        pos.exit_reason = "eod"
        equity += pos.pnl
        trades.append(pos)
        eq_curve[-1] = equity

    return Result(
        equity_curve=pd.Series(eq_curve, index=df["ts"], name="equity"),
        trades=trades,
    )
