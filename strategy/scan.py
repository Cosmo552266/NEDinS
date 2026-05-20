"""Grid-search parameter scan to find OCI configs that compound $26 fast."""

from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from strategy import backtest, data_loader, indicator


def trial(df: pd.DataFrame, **kw) -> dict:
    cfg = backtest.Config(**kw)
    res = backtest.backtest(df, cfg)
    s = res.stats()
    s["params"] = {k: kw[k] for k in kw}
    return s


def main() -> None:
    # Build dataframe once over multiple seeds for robustness
    print("Generating data across 2 seeds...", flush=True)
    dfs = []
    for seed in (7, 19):
        d = data_loader.synthetic_btc(n_bars=8_640, seed=seed)   # ~90 days each
        d = indicator.compute(d)
        dfs.append(d)

    grid = {
        "long_threshold": [30.0, 40.0],
        "short_threshold": [25.0, 35.0],
        "adx_min": [18.0, 25.0],
        "sl_atr": [1.2, 1.8],
        "tp_atr": [3.0, 4.5],
        "trail_atr": [1.5, 2.5],
        "risk_pct": [0.05, 0.07],
        "max_leverage": [10.0],
        "flip_exit_threshold": [25.0],
    }
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    # Require TP > SL to avoid pointless combos
    combos = [c for c in combos if c[keys.index("tp_atr")] > c[keys.index("sl_atr")]]
    print(f"Combinations: {len(combos)}")

    results = []
    for i, combo in enumerate(combos):
        kw = dict(zip(keys, combo))
        # Average over seeds
        sub = [trial(df, **kw) for df in dfs]
        finals = np.array([s.get("final_equity", 0.0) for s in sub])
        rets = np.array([s.get("total_return_x", 0.0) for s in sub])
        wins = np.array([s.get("win_rate", 0.0) for s in sub])
        dds = np.array([s.get("max_drawdown", -1.0) for s in sub])
        trades = np.array([s.get("trades", 0) for s in sub])
        # Score: prefer high geometric mean of return × min(0.7, win_rate) × (1+max_dd)
        # Penalise blow-ups (any seed dd < -80%)
        blowup = (dds < -0.80).any() or (finals < 5.0).any()
        score = float(np.exp(np.log(np.maximum(rets, 1e-3)).mean())) * (1.0 + dds.mean())
        if blowup:
            score *= 0.1
        results.append({
            "params": kw,
            "mean_return_x": float(rets.mean()),
            "geo_return_x": float(np.exp(np.log(np.maximum(rets, 1e-3)).mean())),
            "min_return_x": float(rets.min()),
            "mean_win_rate": float(wins.mean()),
            "mean_dd": float(dds.mean()),
            "mean_trades": float(trades.mean()),
            "score": score,
            "blowup": blowup,
        })
        if (i + 1) % 20 == 0:
            print(f"  ...{i+1}/{len(combos)}", flush=True)

    results.sort(key=lambda r: r["score"], reverse=True)
    print("\nTop 10 configs:")
    for r in results[:10]:
        p = r["params"]
        print(f" score={r['score']:.3f}  geo={r['geo_return_x']:.2f}x  min={r['min_return_x']:.2f}x  "
              f"wr={r['mean_win_rate']*100:.1f}%  dd={r['mean_dd']*100:.1f}%  trades={r['mean_trades']:.0f}  "
              f"L>{p['long_threshold']:.0f} S>{p['short_threshold']:.0f} adx>{p['adx_min']:.0f} "
              f"sl={p['sl_atr']:.1f} tp={p['tp_atr']:.1f} trail={p['trail_atr']:.1f} risk={p['risk_pct']:.2f}")

    with open("strategy/scan_results.json", "w") as f:
        json.dump(results[:30], f, indent=2)
    print("\nWrote strategy/scan_results.json")


if __name__ == "__main__":
    main()
