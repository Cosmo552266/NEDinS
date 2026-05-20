"""
End-to-end simulation: $26 BTC/USDT perpetual, OCI strategy.

Run:
    python -m strategy.run_simulation              # synthetic data
    python -m strategy.run_simulation --live       # try Binance, fall back to synthetic
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

import numpy as np
import pandas as pd

from strategy import backtest, data_loader, indicator


def fmt(x: float, digits: int = 4) -> str:
    if isinstance(x, float) and (np.isinf(x) or np.isnan(x)):
        return "n/a"
    return f"{x:.{digits}f}"


def summarise(res: backtest.Result, df: pd.DataFrame, cfg: backtest.Config) -> dict:
    stats = res.stats()
    days = (df.index[-1] - df.index[0]).total_seconds() / 86_400
    # Days-to-double (approx, on log-linear)
    eq = res.equity_curve.values
    log_eq = np.log(eq / eq[0] + 1e-12)
    if log_eq[-1] > 0:
        slope = log_eq[-1] / max(days, 1.0)
        d2x = np.log(2.0) / slope if slope > 0 else float("inf")
    else:
        d2x = float("inf")
    stats["days_simulated"] = days
    stats["days_to_double"] = d2x
    if res.trades:
        reasons = Counter(t.exit_reason for t in res.trades)
        stats["exit_reasons"] = dict(reasons)
        stats["avg_leverage"] = float(np.mean([t.leverage for t in res.trades]))
        stats["avg_bars_held"] = float(np.mean([t.bars_held for t in res.trades]))
        longs = [t for t in res.trades if t.side == "long"]
        shorts = [t for t in res.trades if t.side == "short"]
        stats["long_trades"] = len(longs)
        stats["short_trades"] = len(shorts)
    return stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true", help="try fetching real BTCUSDT 15m klines")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--bars", type=int, default=17_280, help="number of synthetic 15m bars (default ~180d)")
    p.add_argument("--out", type=str, default="strategy/results.json")
    args = p.parse_args()

    if args.live:
        df = data_loader.load(use_live=True)
    else:
        df = data_loader.synthetic_btc(n_bars=args.bars, seed=args.seed)

    df = indicator.compute(df)
    cfg = backtest.Config()
    res = backtest.backtest(df, cfg)
    stats = summarise(res, df, cfg)

    print("=" * 60)
    print(f"BTC/USDT 15m simulation — start ${cfg.starting_equity:.2f}")
    print(f"Bars: {len(df)}  Days: {stats['days_simulated']:.1f}")
    print("-" * 60)
    print(f"Trades              : {stats.get('trades', 0)}  "
          f"(L:{stats.get('long_trades', 0)} / S:{stats.get('short_trades', 0)})")
    print(f"Final equity        : ${stats.get('final_equity', 0):.2f}")
    print(f"Total return        : {stats.get('total_return_x', 0):.2f}x")
    print(f"Win rate            : {fmt(stats.get('win_rate', 0)*100, 2)}%")
    print(f"Avg R per trade     : {fmt(stats.get('avg_R', 0))}")
    print(f"Profit factor       : {fmt(stats.get('profit_factor', 0))}")
    print(f"Max drawdown        : {fmt(stats.get('max_drawdown', 0)*100, 2)}%")
    print(f"Days to double (est): {fmt(stats.get('days_to_double', 0), 2)}")
    print(f"Avg leverage used   : {fmt(stats.get('avg_leverage', 0), 2)}x")
    print(f"Avg bars held       : {fmt(stats.get('avg_bars_held', 0), 1)} ({fmt(stats.get('avg_bars_held', 0)*15/60, 1)}h)")
    print(f"Exit reasons        : {stats.get('exit_reasons', {})}")
    print("=" * 60)

    out = {
        "config": cfg.__dict__,
        "stats": stats,
        "first_5_trades": [
            {
                "side": t.side, "entry": t.entry_price, "exit": t.exit_price,
                "reason": t.exit_reason, "R": t.r_multiple, "pnl": t.pnl,
                "leverage": t.leverage, "bars": t.bars_held,
            }
            for t in res.trades[:5]
        ],
        "equity_curve_sample": {
            str(ts): float(v) for ts, v in
            res.equity_curve.iloc[::max(len(res.equity_curve) // 50, 1)].items()
        },
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
