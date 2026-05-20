"""1-minute scalping system: OCI + Donchian + HTF (15m) trend filter, 10x lev."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter

import numpy as np

from strategy import backtest, data_loader, indicator


SCALP_DEFAULTS = dict(
    starting_equity=26.0,
    entry_mode="compression",   # compressed-range breakout (the scalp pattern)
    long_threshold=25.0,
    short_threshold=25.0,
    adx_min=18.0,
    sl_atr=1.0,
    tp_atr=5.0,                 # need 33% WR to beat fees at 10x lev
    trail_atr=1.5,
    trail_activate_R=2.5,
    flip_exit_threshold=25.0,
    max_bars_in_trade=45,
    risk_pct=0.06,
    max_leverage=10.0,
    use_htf_filter=True,
    taker_fee_bps=4.0,
    slippage_bps=2.0,
    cb_max_range_pct=0.004,     # <=0.4% range over 10 bars
    cb_min_oci=25.0,
)


def run(seed: int = 7, **overrides) -> dict:
    t0 = time.time()
    df = data_loader.synthetic_btc(n_bars=259_200, bar_minutes=1, seed=seed)
    df = indicator.compute(df)
    df = indicator.add_htf_filter(df, working_tf_minutes=1, htf_minutes=15, ema_len=200)
    setup_time = time.time() - t0

    cfg_kwargs = {**SCALP_DEFAULTS, **overrides}
    cfg = backtest.Config(**cfg_kwargs)
    t0 = time.time()
    res = backtest.backtest(df, cfg)
    bt_time = time.time() - t0

    s = res.stats()
    if res.trades:
        s["exit_reasons"] = dict(Counter(t.exit_reason for t in res.trades))
        s["avg_leverage"] = float(np.mean([t.leverage for t in res.trades]))
        s["avg_bars_held"] = float(np.mean([t.bars_held for t in res.trades]))
        s["long_trades"] = sum(1 for t in res.trades if t.side == "long")
        s["short_trades"] = sum(1 for t in res.trades if t.side == "short")
    s["setup_s"] = setup_time
    s["backtest_s"] = bt_time
    s["bars"] = len(df)
    s["htf_long_bias_pct"] = float((df["htf_trend"] == 1).mean() * 100)
    s["htf_short_bias_pct"] = float((df["htf_trend"] == -1).mean() * 100)
    s["htf_neutral_pct"] = float((df["htf_trend"] == 0).mean() * 100)
    s["signal_freq_pct"] = float((df["oci"].abs() > cfg.long_threshold).mean() * 100)
    return s, cfg, res


def print_stats(s: dict, cfg: backtest.Config) -> None:
    print("=" * 70)
    print(f"1-minute scalper — start ${cfg.starting_equity:.2f}, lev cap {cfg.max_leverage:.0f}x")
    print(f"Bars: {s['bars']} (180 days of 1m)  setup {s['setup_s']:.1f}s  bt {s['backtest_s']:.1f}s")
    print(f"HTF regime: long={s['htf_long_bias_pct']:.1f}%  short={s['htf_short_bias_pct']:.1f}%  "
          f"neutral={s['htf_neutral_pct']:.1f}%")
    print(f"Raw OCI signal freq |OCI|>{cfg.long_threshold:.0f}: {s['signal_freq_pct']:.2f}%")
    print("-" * 70)
    n = s.get("trades", 0)
    if n == 0:
        print("NO TRADES — filter is too strict.")
        return
    print(f"Trades              : {n}  (L:{s.get('long_trades',0)} / S:{s.get('short_trades',0)})")
    print(f"Final equity        : ${s.get('final_equity', 0):.2f}")
    print(f"Total return        : {s.get('total_return_x', 0):.2f}x   "
          f"({(s.get('total_return_x', 1)-1)*100:+.1f}%)")
    print(f"Win rate            : {s.get('win_rate', 0)*100:.2f}%")
    print(f"Avg R per trade     : {s.get('avg_R', 0):+.3f}")
    pf = s.get('profit_factor', 0)
    print(f"Profit factor       : {pf if not np.isinf(pf) else 'inf'}")
    print(f"Max drawdown        : {s.get('max_drawdown', 0)*100:.2f}%")
    print(f"Avg leverage used   : {s.get('avg_leverage', 0):.2f}x")
    print(f"Avg bars held       : {s.get('avg_bars_held', 0):.1f} ({s.get('avg_bars_held', 0):.1f} min)")
    print(f"Exit reasons        : {s.get('exit_reasons', {})}")
    print("=" * 70)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--no-htf", action="store_true")
    args = p.parse_args()
    s, cfg, res = run(seed=args.seed, use_htf_filter=not args.no_htf)
    print_stats(s, cfg)
    with open("strategy/scalper_results.json", "w") as f:
        json.dump({"config": cfg.__dict__, "stats": s}, f, indent=2, default=str)


if __name__ == "__main__":
    main()
