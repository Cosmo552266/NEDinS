"""Validate winning configuration across multiple seeds and risk levels."""

from __future__ import annotations

import numpy as np

from strategy import backtest, data_loader, indicator


def main() -> None:
    seeds = (7, 19, 42, 99, 113)
    dfs = []
    for s in seeds:
        d = data_loader.synthetic_btc(n_bars=17_280, seed=s)
        d = indicator.compute(d)
        dfs.append((s, d))

    print(f"{'risk%':>5} {'lev':>4} {'thr':>4}  "
          f"{'mean_x':>7} {'min_x':>7} {'max_x':>7}  {'avgWin%':>7} {'avgDD%':>7} {'avgPF':>5}")
    print("-" * 80)
    for risk in (0.04, 0.06, 0.08, 0.10):
        for lev in (3.0, 5.0):
            for thr in (40.0, 45.0, 55.0):
                cfg = backtest.Config(
                    entry_mode="breakout",
                    long_threshold=thr, short_threshold=thr,
                    sl_atr=1.0, tp_atr=4.0, trail_atr=3.5, trail_activate_R=1.5,
                    risk_pct=risk, max_leverage=lev,
                )
                rets, wins, dds, pfs, trades = [], [], [], [], []
                for _, df in dfs:
                    res = backtest.backtest(df, cfg)
                    s = res.stats()
                    rets.append(s.get("total_return_x", 0.0))
                    wins.append(s.get("win_rate", 0.0))
                    dds.append(s.get("max_drawdown", -1.0))
                    pfs.append(s.get("profit_factor", 0.0))
                    trades.append(s.get("trades", 0))
                rets = np.array(rets); dds = np.array(dds); pfs = np.array(pfs)
                print(f"{risk*100:5.1f} {lev:4.1f} {thr:4.0f}  "
                      f"{rets.mean():7.2f} {rets.min():7.2f} {rets.max():7.2f}  "
                      f"{np.mean(wins)*100:6.1f}% {dds.mean()*100:6.1f}% "
                      f"{np.mean([p for p in pfs if not np.isinf(p)]):5.2f}")


if __name__ == "__main__":
    main()
