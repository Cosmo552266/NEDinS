"""Multi-seed validation of SMC scalper on full 180-day windows."""

from __future__ import annotations

import numpy as np

from strategy import smc_scalper


def main() -> None:
    print(f"{'seed':>4}  {'th':>3}  {'trades':>6}  {'WR':>6}  {'avgR':>7}  "
          f"{'PF':>5}  {'final$':>7}  {'DD%':>6}")
    print("-" * 70)
    for th in (3, 4, 5):
        for seed in (7, 19, 42):
            s, cfg, _ = smc_scalper.run(
                seed=seed, n_bars=259_200, verbose=False, confluence_threshold=th,
            )
            if s.get("trades", 0) == 0:
                print(f"{seed:4d}  {th:3d}  (no trades)")
                continue
            pf = s["profit_factor"]
            pfs = "  inf" if pf == float("inf") else f"{pf:5.2f}"
            print(f"{seed:4d}  {th:3d}  {s['trades']:6d}  "
                  f"{s['win_rate']*100:5.1f}%  {s['avg_R']:+6.3f}  {pfs}  "
                  f"{s['final_equity']:7.2f}  {s['max_drawdown']*100:5.1f}%")


if __name__ == "__main__":
    main()
