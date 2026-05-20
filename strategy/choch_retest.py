"""
User's logic (decoded from screenshot):

  1. Detect CHoCH (Change of Character) events from the swing-pivot state machine.
     A CHoCH = the FIRST break of structure against the previous trend.
  2. The OB associated with the CHoCH = the last opposite-coloured candle
     immediately before the impulsive break.
  3. ARM the trade after CHoCH. Wait for price to PULL BACK into the OB zone.
  4. TRIGGER the entry on the next bar that closes back through the OB
     in the new trend direction (long if CHoCH-up, short if CHoCH-down).
  5. STOP just beyond the OB extreme.
  6. TARGET the most recent opposite swing pivot.
  7. Position sized by fixed-fractional 6% risk on current equity, cap 10x.

The system is intentionally LOW-FREQUENCY — a real CHoCH-and-retest is rare.
Typical output on real charts: 0.5–2 setups per day at 15m, 2–6 per day at 1m.
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
    sl_buffer_atr: float = 0.5      # stop = OB extreme ± this many ATR
    sl_atr_cap: float = 3.0         # cap stop distance to N x ATR
    tp_atr_max: float = 12.0        # cap take-profit
    tp_R_min: float = 2.0           # never accept TP closer than this many R
    retest_max_age: int = 40        # how many bars after CHoCH to wait for retest
    confirm_bars: int = 1           # how many bars after retest to confirm trigger
    trail_atr: float = 2.0
    trail_activate_R: float = 1.5
    max_bars_in_trade: int = 100
    fee_bps_per_side: float = 4.0
    slippage_bps: float = 2.0
    warmup_bars: int = 250
    require_ott_agreement: bool = True   # OTT direction must match trade dir
    require_ema_stack: bool = False      # EMA stack alignment optional


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
    setup_choch_bar: int          # bookkeeping: bar of the originating CHoCH
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


def backtest(df: pd.DataFrame, cfg: Config | None = None) -> Result:
    cfg = cfg or Config()
    df = df.dropna(subset=["close", "atr"]).reset_index().rename(columns={"index": "ts"})
    n = len(df)
    eq_curve = np.empty(n)
    equity = cfg.starting_equity
    pos: Trade | None = None
    trades: list[Trade] = []

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values
    atr_v = df["atr"].values
    choch = df["choch"].values
    smc_state = df["smc_state"].values
    ott_dir = df["ott_dir"].values
    stack_bull = df["stack_bull"].values
    stack_bear = df["stack_bear"].values
    bull_oh = df["bull_ob_high"].values
    bull_ol = df["bull_ob_low"].values
    bear_oh = df["bear_ob_high"].values
    bear_ol = df["bear_ob_low"].values
    last_ph = df["last_ph"].values
    last_pl = df["last_pl"].values
    ts = df["ts"].values

    # ARMED setups waiting for retest+confirmation
    # Each: (side, choch_bar_idx, ob_high, ob_low, retested?)
    armed: list[dict] = []

    for i in range(n):
        price = close[i]
        a = max(float(atr_v[i]) if not np.isnan(atr_v[i]) else 0.0, 1e-9)

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

            exit_price = exit_reason = None

            if pos.side == "long":
                if low[i] <= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif high[i] >= pos.take:
                    exit_price, exit_reason = pos.take, "take"
                elif pos.bars_held >= cfg.max_bars_in_trade:
                    exit_price, exit_reason = price, "time"
            else:
                if high[i] >= pos.stop:
                    exit_price = pos.stop
                    exit_reason = "trail" if pos.trail_active else "stop"
                elif low[i] <= pos.take:
                    exit_price, exit_reason = pos.take, "take"
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
                pos.exit_time = ts[i]
                pos.exit_reason = exit_reason
                pos.r_multiple = pos.pnl / pos.risk_dollars if pos.risk_dollars > 0 else 0.0
                equity += pos.pnl
                trades.append(pos)
                pos = None

        # ---------- Arm new setup on CHoCH ----------
        if choch[i] == 1 and not np.isnan(bull_oh[i]):
            armed.append({
                "side": "long",
                "choch_bar": i,
                "ob_h": bull_oh[i],
                "ob_l": bull_ol[i],
                "retested": False,
                "retest_bar": -1,
            })
        elif choch[i] == -1 and not np.isnan(bear_ol[i]):
            armed.append({
                "side": "short",
                "choch_bar": i,
                "ob_h": bear_oh[i],
                "ob_l": bear_ol[i],
                "retested": False,
                "retest_bar": -1,
            })

        # Expire stale setups
        armed = [a for a in armed if (i - a["choch_bar"]) <= cfg.retest_max_age]

        # ---------- Try to trigger ----------
        if pos is None and i >= cfg.warmup_bars and equity > 1.0:
            for setup in armed:
                if setup["side"] == "long":
                    # Phase 1: price touched OB body
                    if not setup["retested"]:
                        if low[i] <= setup["ob_h"] and low[i] >= setup["ob_l"] - cfg.sl_buffer_atr * a:
                            setup["retested"] = True
                            setup["retest_bar"] = i
                        continue
                    # Phase 2: confirmation — close > prior bar high, in the OB direction
                    bars_since_retest = i - setup["retest_bar"]
                    if 1 <= bars_since_retest <= cfg.confirm_bars + 1:
                        if i > 0 and close[i] > high[i - 1] and smc_state[i] == 1:
                            # Optional filters
                            if cfg.require_ott_agreement and ott_dir[i] != 1:
                                continue
                            if cfg.require_ema_stack and not stack_bull[i]:
                                continue
                            # Build the trade
                            stop = setup["ob_l"] - cfg.sl_buffer_atr * a
                            stop = max(stop, price - cfg.sl_atr_cap * a)
                            stop_dist = price - stop
                            if stop_dist <= 0.3 * a:
                                continue
                            target = last_ph[i] if not np.isnan(last_ph[i]) else price + cfg.tp_atr_max * a
                            tp_dist = target - price
                            if tp_dist < cfg.tp_R_min * stop_dist:
                                tp_dist = cfg.tp_R_min * stop_dist
                            tp_dist = min(tp_dist, cfg.tp_atr_max * a)
                            take = price + tp_dist
                            pos = _open(price, stop, take, "long", stop_dist, equity, cfg, ts[i], setup["choch_bar"])
                            equity -= _fee(pos.notional, cfg)
                            armed = [a for a in armed if a is not setup]
                            break
                else:
                    if not setup["retested"]:
                        if high[i] >= setup["ob_l"] and high[i] <= setup["ob_h"] + cfg.sl_buffer_atr * a:
                            setup["retested"] = True
                            setup["retest_bar"] = i
                        continue
                    bars_since_retest = i - setup["retest_bar"]
                    if 1 <= bars_since_retest <= cfg.confirm_bars + 1:
                        if i > 0 and close[i] < low[i - 1] and smc_state[i] == -1:
                            if cfg.require_ott_agreement and ott_dir[i] != -1:
                                continue
                            if cfg.require_ema_stack and not stack_bear[i]:
                                continue
                            stop = setup["ob_h"] + cfg.sl_buffer_atr * a
                            stop = min(stop, price + cfg.sl_atr_cap * a)
                            stop_dist = stop - price
                            if stop_dist <= 0.3 * a:
                                continue
                            target = last_pl[i] if not np.isnan(last_pl[i]) else price - cfg.tp_atr_max * a
                            tp_dist = price - target
                            if tp_dist < cfg.tp_R_min * stop_dist:
                                tp_dist = cfg.tp_R_min * stop_dist
                            tp_dist = min(tp_dist, cfg.tp_atr_max * a)
                            take = price - tp_dist
                            pos = _open(price, stop, take, "short", stop_dist, equity, cfg, ts[i], setup["choch_bar"])
                            equity -= _fee(pos.notional, cfg)
                            armed = [a for a in armed if a is not setup]
                            break

        eq_curve[i] = equity

    # End-of-data close
    if pos is not None:
        exit_price = float(close[-1])
        raw_pnl = (exit_price - pos.entry_price) * pos.qty if pos.side == "long" \
            else (pos.entry_price - exit_price) * pos.qty
        pos.pnl = raw_pnl - _fee(exit_price * pos.qty, cfg)
        pos.exit_price = exit_price
        pos.exit_time = ts[-1]
        pos.exit_reason = "eod"
        equity += pos.pnl
        trades.append(pos)
        eq_curve[-1] = equity

    return Result(equity_curve=pd.Series(eq_curve, index=df["ts"], name="equity"), trades=trades)


def _open(price, stop, take, side, stop_dist, equity, cfg, ts, choch_bar) -> Trade:
    intended_risk = cfg.risk_pct * equity
    qty = intended_risk / stop_dist
    notional = qty * price
    lev = notional / equity
    if lev > cfg.max_leverage:
        lev = cfg.max_leverage
        notional = lev * equity
        qty = notional / price
    actual_risk = qty * stop_dist
    return Trade(
        side=side, entry_time=ts, entry_price=price,
        stop=stop, take=take, qty=qty, notional=notional, leverage=lev,
        risk_dollars=actual_risk, initial_stop=stop, setup_choch_bar=int(choch_bar),
    )


def stats_summary(res: Result, cfg: Config, n_bars: int) -> dict:
    if not res.trades:
        return {"trades": 0, "final_equity": cfg.starting_equity, "bars": n_bars}
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


def run(seed: int = 7, n_bars: int = 17_280, bar_minutes: int = 15,
        skip_vp: bool = True, verbose: bool = True, **overrides):
    t0 = time.time()
    df = data_loader.synthetic_btc(n_bars=n_bars, bar_minutes=bar_minutes, seed=seed)
    data_t = time.time() - t0
    t0 = time.time()
    df = smc.ema_stack(df)
    df = smc.ott(df, length=15, pct=1.5)
    df = smc.swing_pivots(df, left=5, right=5)
    df = smc.bos_choch(df)
    df = smc.order_blocks(df, impulse_atr=1.5, lookback=50)
    df["atr"] = smc.atr(df, 14)
    if not skip_vp:
        df = smc.volume_profile_poc(df, window=360, bins=50)
    smc_t = time.time() - t0
    if verbose:
        choch_up = int((df["choch"] == 1).sum())
        choch_dn = int((df["choch"] == -1).sum())
        print(f"[choch] data {data_t:.1f}s  indicators {smc_t:.1f}s  bars={len(df)}")
        print(f"[choch] CHoCH events: up={choch_up}  down={choch_dn}  "
              f"(~{(choch_up+choch_dn)*1440/n_bars/bar_minutes:.2f}/day)")
    cfg = Config(**overrides)
    t0 = time.time()
    res = backtest(df, cfg)
    bt_t = time.time() - t0
    if verbose:
        print(f"[choch] backtest {bt_t:.1f}s")
    return stats_summary(res, cfg, len(df)), cfg, res


def print_stats(s: dict, cfg: Config, label: str = "") -> None:
    bm = "1m" if s.get("bars", 0) > 100_000 else "15m"
    days = s.get("bars", 0) / (1440 if bm == "1m" else 96)
    print("=" * 72)
    print(f"CHoCH-Retest Scalper {label}  —  start ${cfg.starting_equity:.2f}, "
          f"lev cap {cfg.max_leverage:.0f}x, risk {cfg.risk_pct*100:.0f}% (compounding)")
    print(f"Timeframe: {bm}   Bars: {s.get('bars', 0)} ({days:.0f} days)")
    print("-" * 72)
    n = s.get("trades", 0)
    if n == 0:
        print("NO TRADES — CHoCH-retest pattern did not fire.")
        return
    print(f"Trades              : {n}  (L:{s['long_trades']} / S:{s['short_trades']})")
    print(f"Final equity        : ${s['final_equity']:.2f}")
    print(f"Total return        : {s['total_return_x']:.2f}x  ({(s['total_return_x']-1)*100:+.1f}%)")
    print(f"Win rate            : {s['win_rate']*100:.2f}%")
    print(f"Avg R per trade     : {s['avg_R']:+.3f}")
    pf = s['profit_factor']
    print(f"Profit factor       : {'inf' if pf == float('inf') else f'{pf:.2f}'}")
    print(f"Best / worst        : {s['max_R']:+.2f}R / {s['min_R']:+.2f}R")
    print(f"Max drawdown        : {s['max_drawdown']*100:.2f}%")
    print(f"Avg leverage used   : {s['avg_leverage']:.2f}x")
    print(f"Avg bars held       : {s['avg_bars_held']:.1f}")
    print(f"Exit reasons        : {s['exit_reasons']}")
    print("=" * 72)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--bars", type=int, default=17_280, help="default = 180d × 96 (15m)")
    p.add_argument("--bar-minutes", type=int, default=15)
    p.add_argument("--no-ott-filter", action="store_true")
    args = p.parse_args()
    s, cfg, res = run(seed=args.seed, n_bars=args.bars, bar_minutes=args.bar_minutes,
                      require_ott_agreement=not args.no_ott_filter)
    print_stats(s, cfg, label=f"({args.bar_minutes}m)")
    with open("strategy/choch_retest_results.json", "w") as f:
        json.dump({"config": cfg.__dict__, "stats": s}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
