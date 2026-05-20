"""
SMC-scalper: closed-loop 1-minute scalping system using the indicator stack
from the user's screenshot.

ENTRY LOGIC (must satisfy ALL):
  LONG:
    A. EMA stack bull       : ema34 > ema89 > ema111 > ema144
    B. OTT direction = +1   : close > OTT trail line
    C. SMC state = +1       : last BOS was up (bullish market structure)
    D. Pullback into bull OB OR HVN (price within OB zone or touched POC)
    E. Trigger: close > prior bar's high AND close > ema34
       (resumption of trend after pullback)
  SHORT: mirror

EXIT:
  - Hard stop: max(0.5 ATR below OB low, entry - SL_ATR_MAX * ATR)
  - Take profit: next opposite pivot (recent swing high/low) capped at TP_ATR_MAX
  - Chandelier trail at 2.5 ATR after MFE >= 2R
  - OTT direction flip against position -> immediate exit
  - Time stop: max_bars

POSITION SIZING (compounding):
  risk_dollars = RISK_PCT * current_equity
  qty = risk_dollars / stop_distance
  leverage capped at MAX_LEV (10x as requested)
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategy import data_loader, smc


@dataclass
class Config:
    starting_equity: float = 26.0
    risk_pct: float = 0.06
    max_leverage: float = 10.0
    sl_atr_max: float = 2.5         # cap stop distance to N x ATR
    tp_atr_max: float = 10.0        # cap take-profit to N x ATR
    ob_buffer_atr: float = 0.5      # stop is buffer below OB low (long)
    pullback_zone_atr: float = 1.0  # consider pullback if close near OB / POC
    tp_R_target: float = 4.0        # take-profit at this many R
    ob_max_age: int = 80
    require_liq_sweep: bool = False
    use_confluence_score: bool = True
    confluence_threshold: int = 4   # need >= 4 of 5 indicators in agreement
    sweep_lookback: int = 5
    require_ob: bool = True
    require_poc_touch: bool = False # alternate confluence
    trail_atr: float = 2.5
    trail_activate_R: float = 2.0
    max_bars_in_trade: int = 60     # 60 min on 1m
    fee_bps_per_side: float = 4.0
    slippage_bps: float = 2.0
    warmup_bars: int = 400


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
    risk_dollars: float
    initial_stop: float
    exit_time: pd.Timestamp = None
    exit_price: float = None
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


def _fee(notional: float, cfg: Config) -> float:
    return notional * (cfg.fee_bps_per_side + cfg.slippage_bps) / 10_000.0


def _atr_floor(x: float) -> float:
    return max(x, 1e-9)


def backtest(df: pd.DataFrame, cfg: Config | None = None) -> Result:
    cfg = cfg or Config()
    df = df.dropna(subset=["close", "atr"]).reset_index().rename(columns={"index": "ts"})
    n = len(df)
    eq_curve = np.empty(n)
    equity = cfg.starting_equity
    pos: Trade | None = None
    trades: list[Trade] = []

    # Vectorised feature extraction for speed
    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    atr_v = df["atr"].values
    ema34 = df["ema34"].values
    stack_bull = df["stack_bull"].values
    stack_bear = df["stack_bear"].values
    ott_dir = df["ott_dir"].values
    smc_state = df["smc_state"].values
    bull_oh = df["bull_ob_high"].values
    bull_ol = df["bull_ob_low"].values
    bear_oh = df["bear_ob_high"].values
    bear_ol = df["bear_ob_low"].values
    bull_age = df["bull_ob_age"].values
    bear_age = df["bear_ob_age"].values
    last_ph = df["last_ph"].values
    last_pl = df["last_pl"].values
    poc = df["poc"].values

    for i in range(n):
        price = close[i]
        a = atr_v[i] if not np.isnan(atr_v[i]) else 0.0
        a = _atr_floor(a)

        # ---------- Manage open position ----------
        if pos is not None:
            pos.bars_held += 1
            one_r = abs(pos.entry_price - pos.initial_stop)
            activate_at = cfg.trail_activate_R * one_r

            if pos.side == "long":
                pos.peak_favourable = max(pos.peak_favourable, high[i] - pos.entry_price)
                if pos.peak_favourable >= activate_at:
                    pos.trail_active = True
                    new_stop = (pos.entry_price + pos.peak_favourable) - cfg.trail_atr * a
                    pos.stop = max(pos.stop, new_stop)
            else:
                pos.peak_favourable = max(pos.peak_favourable, pos.entry_price - low[i])
                if pos.peak_favourable >= activate_at:
                    pos.trail_active = True
                    new_stop = (pos.entry_price - pos.peak_favourable) + cfg.trail_atr * a
                    pos.stop = min(pos.stop, new_stop)

            exit_price = None
            exit_reason = ""

            if pos.side == "long":
                if low[i] <= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif high[i] >= pos.take:
                    exit_price, exit_reason = pos.take, "take"
                elif ott_dir[i] == -1:
                    exit_price, exit_reason = price, "ott_flip"
                elif pos.bars_held >= cfg.max_bars_in_trade:
                    exit_price, exit_reason = price, "time"
            else:
                if high[i] >= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif low[i] <= pos.take:
                    exit_price, exit_reason = pos.take, "take"
                elif ott_dir[i] == +1:
                    exit_price, exit_reason = price, "ott_flip"
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
                pos.exit_time = df["ts"].iloc[i]
                pos.exit_reason = exit_reason
                pos.r_multiple = pos.pnl / pos.risk_dollars if pos.risk_dollars > 0 else 0.0
                equity += pos.pnl
                trades.append(pos)
                pos = None

        # ---------- New entry ----------
        if pos is None and i >= cfg.warmup_bars and equity > 1.0:
            if cfg.use_confluence_score:
                # Per-side confluence score: each of 5 conditions = 1 point
                lo_n = max(0, i - cfg.sweep_lookback)
                recent_low = np.min(low[lo_n:i]) if i > 0 else low[i]
                recent_high = np.max(high[lo_n:i]) if i > 0 else high[i]
                prev_high = high[i - 1] if i > 0 else high[i]
                prev_low = low[i - 1] if i > 0 else low[i]

                long_score = (
                    int(stack_bull[i])
                    + int(ott_dir[i] == 1)
                    + int(smc_state[i] == 1)
                    + int(
                        not np.isnan(bull_oh[i])
                        and low[i] <= bull_oh[i]
                        and low[i] >= bull_ol[i] - cfg.ob_buffer_atr * a
                        and bull_age[i] <= cfg.ob_max_age
                    )
                    + int(low[i] <= recent_low and close[i] > prev_high and close[i] > ema34[i])
                )
                short_score = (
                    int(stack_bear[i])
                    + int(ott_dir[i] == -1)
                    + int(smc_state[i] == -1)
                    + int(
                        not np.isnan(bear_ol[i])
                        and high[i] >= bear_ol[i]
                        and high[i] <= bear_oh[i] + cfg.ob_buffer_atr * a
                        and bear_age[i] <= cfg.ob_max_age
                    )
                    + int(high[i] >= recent_high and close[i] < prev_low and close[i] < ema34[i])
                )
                long_cond = long_score >= cfg.confluence_threshold and long_score > short_score
                short_cond = short_score >= cfg.confluence_threshold and short_score > long_score
            else:
                # Hard-AND version (kept for comparison)
                long_cond = (
                    stack_bull[i] and ott_dir[i] == 1 and smc_state[i] == 1
                )
                short_cond = (
                    stack_bear[i] and ott_dir[i] == -1 and smc_state[i] == -1
                )
                if long_cond and cfg.require_ob:
                    long_cond = long_cond and (
                        not np.isnan(bull_oh[i])
                        and low[i] <= bull_oh[i]
                        and low[i] >= bull_ol[i] - cfg.ob_buffer_atr * a
                        and bull_age[i] <= cfg.ob_max_age
                    )
                if short_cond and cfg.require_ob:
                    short_cond = short_cond and (
                        not np.isnan(bear_ol[i])
                        and high[i] >= bear_ol[i]
                        and high[i] <= bear_oh[i] + cfg.ob_buffer_atr * a
                        and bear_age[i] <= cfg.ob_max_age
                    )
                if i > 0:
                    if long_cond:
                        long_cond = close[i] > high[i - 1] and close[i] > ema34[i]
                    if short_cond:
                        short_cond = close[i] < low[i - 1] and close[i] < ema34[i]

            if long_cond or short_cond:
                side = "long" if long_cond else "short"
                # Stop: OB-based, capped at sl_atr_max
                if side == "long":
                    ob_low = bull_ol[i] if not np.isnan(bull_ol[i]) else price - cfg.sl_atr_max * a
                    stop = max(ob_low - cfg.ob_buffer_atr * a, price - cfg.sl_atr_max * a)
                    stop_dist = price - stop
                else:
                    ob_high = bear_oh[i] if not np.isnan(bear_oh[i]) else price + cfg.sl_atr_max * a
                    stop = min(ob_high + cfg.ob_buffer_atr * a, price + cfg.sl_atr_max * a)
                    stop_dist = stop - price

                if stop_dist <= 0.5 * a:
                    eq_curve[i] = equity
                    continue
                # Take profit: fixed multiple of stop distance, capped by ATR
                # (pivot-based TP was too narrow — average winners < 2R)
                tp_dist = min(cfg.tp_R_target * stop_dist, cfg.tp_atr_max * a)
                if side == "long":
                    take = price + tp_dist
                else:
                    take = price - tp_dist

                intended_risk = cfg.risk_pct * equity
                qty = intended_risk / stop_dist
                notional = qty * price
                lev = notional / equity
                if lev > cfg.max_leverage:
                    lev = cfg.max_leverage
                    notional = lev * equity
                    qty = notional / price
                actual_risk = qty * stop_dist
                fee_in = _fee(notional, cfg)
                equity -= fee_in
                pos = Trade(
                    side=side, entry_time=df["ts"].iloc[i], entry_price=price,
                    stop=stop, take=take, qty=qty, notional=notional, leverage=lev,
                    risk_dollars=actual_risk, initial_stop=stop,
                )

        eq_curve[i] = equity

    # Close any remaining open position at end-of-data
    if pos is not None:
        exit_price = float(close[-1])
        if pos.side == "long":
            raw_pnl = (exit_price - pos.entry_price) * pos.qty
        else:
            raw_pnl = (pos.entry_price - exit_price) * pos.qty
        fee_out = _fee(exit_price * pos.qty, cfg)
        pos.pnl = raw_pnl - fee_out
        pos.exit_price = exit_price
        pos.exit_time = df["ts"].iloc[-1]
        pos.exit_reason = "eod"
        equity += pos.pnl
        trades.append(pos)
        eq_curve[-1] = equity

    return Result(equity_curve=pd.Series(eq_curve, index=df["ts"], name="equity"), trades=trades)


def stats_summary(res: Result, cfg: Config, n_bars: int) -> dict:
    if not res.trades:
        return {"trades": 0, "final_equity": cfg.starting_equity}
    pnls = np.array([t.pnl for t in res.trades])
    rs = np.array([t.r_multiple for t in res.trades])
    wins = pnls > 0
    eq = res.equity_curve.values
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    pf_num = pnls[wins].sum()
    pf_den = -pnls[~wins].sum()
    return {
        "trades": len(res.trades),
        "long_trades": sum(1 for t in res.trades if t.side == "long"),
        "short_trades": sum(1 for t in res.trades if t.side == "short"),
        "final_equity": float(eq[-1]),
        "total_return_x": float(eq[-1] / cfg.starting_equity),
        "win_rate": float(wins.mean()),
        "avg_R": float(rs.mean()),
        "max_R": float(rs.max()),
        "min_R": float(rs.min()),
        "profit_factor": float(pf_num / pf_den) if pf_den > 0 else float("inf"),
        "max_drawdown": float(dd.min()),
        "avg_leverage": float(np.mean([t.leverage for t in res.trades])),
        "avg_bars_held": float(np.mean([t.bars_held for t in res.trades])),
        "exit_reasons": dict(Counter(t.exit_reason for t in res.trades)),
        "bars": n_bars,
    }


def run(seed: int = 7, n_bars: int = 259_200, bar_minutes: int = 1,
        verbose: bool = True, **overrides) -> tuple[dict, Config, Result]:
    t0 = time.time()
    df = data_loader.synthetic_btc(n_bars=n_bars, bar_minutes=bar_minutes, seed=seed)
    data_t = time.time() - t0
    t0 = time.time()
    df = smc.compute_smc(df, vp_window=360, pivot_k=5)
    smc_t = time.time() - t0
    if verbose:
        print(f"[smc] data {data_t:.1f}s  indicators {smc_t:.1f}s  bars={len(df)}")
        print(f"[smc] OTT bullish freq: {(df['ott_dir'] == 1).mean()*100:.1f}%  "
              f"SMC bullish state: {(df['smc_state'] == 1).mean()*100:.1f}%  "
              f"EMA stack bull: {df['stack_bull'].mean()*100:.1f}%")
        bo = df['bull_ob_high'].notna()
        be = df['bear_ob_high'].notna()
        print(f"[smc] OB coverage: bull {bo.mean()*100:.1f}%  bear {be.mean()*100:.1f}%")
    cfg = Config(**overrides)
    t0 = time.time()
    res = backtest(df, cfg)
    bt_t = time.time() - t0
    if verbose:
        print(f"[smc] backtest {bt_t:.1f}s")
    return stats_summary(res, cfg, len(df)), cfg, res


def print_stats(s: dict, cfg: Config) -> None:
    print("=" * 70)
    print(f"SMC 1m Scalper  —  start ${cfg.starting_equity:.2f}, lev cap {cfg.max_leverage:.0f}x, "
          f"risk {cfg.risk_pct*100:.0f}% (compounding)")
    print(f"Bars: {s['bars']} (~{s['bars']/1440:.0f} days of 1m)")
    print("-" * 70)
    n = s.get("trades", 0)
    if n == 0:
        print("NO TRADES — filters never aligned.")
        return
    print(f"Trades              : {n}  (L:{s['long_trades']} / S:{s['short_trades']})")
    print(f"Final equity        : ${s['final_equity']:.2f}")
    print(f"Total return        : {s['total_return_x']:.2f}x  "
          f"({(s['total_return_x']-1)*100:+.1f}%)")
    print(f"Win rate            : {s['win_rate']*100:.2f}%")
    print(f"Avg R per trade     : {s['avg_R']:+.3f}")
    pf = s['profit_factor']
    print(f"Profit factor       : {'inf' if pf == float('inf') else f'{pf:.2f}'}")
    print(f"Best / worst trade  : {s['max_R']:+.2f}R  /  {s['min_R']:+.2f}R")
    print(f"Max drawdown        : {s['max_drawdown']*100:.2f}%")
    print(f"Avg leverage used   : {s['avg_leverage']:.2f}x")
    print(f"Avg bars held       : {s['avg_bars_held']:.1f} min")
    print(f"Exit reasons        : {s['exit_reasons']}")
    print("=" * 70)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--bars", type=int, default=259_200, help="default = 180d × 1440 min")
    p.add_argument("--bar-minutes", type=int, default=1)
    args = p.parse_args()
    s, cfg, res = run(seed=args.seed, n_bars=args.bars, bar_minutes=args.bar_minutes)
    print_stats(s, cfg)
    with open("strategy/smc_scalper_results.json", "w") as f:
        json.dump({"config": cfg.__dict__, "stats": s}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
