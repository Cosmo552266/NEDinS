"""End-to-end driver: fetch -> indicators -> 3 strategies -> backtest -> report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python btc_backtest/main.py` as well as `python -m btc_backtest.main`
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from btc_backtest.fetch_data import load_ohlcv
from btc_backtest.indicators import add_indicators
from btc_backtest.strategies import REGISTRY
from btc_backtest.backtest import run_backtest
from btc_backtest.report import compute_metrics, save_report, metrics_table


BARS_PER_YEAR = {"1m": 60 * 24 * 365, "5m": 12 * 24 * 365,
                 "15m": 4 * 24 * 365, "1h": 24 * 365}


def run(interval: str = "1m", bars: int = 2000, fee_bps: float = 5.0,
        slippage_bps: float = 2.0, force_synthetic: bool = False,
        out_dir: str = "reports") -> dict:
    fetched = load_ohlcv(interval=interval, bars=bars, force_synthetic=force_synthetic)
    print(f"[fetch] {fetched.symbol} {fetched.interval}: {len(fetched.df)} bars, source={fetched.source}")

    enriched = add_indicators(fetched.df)
    print(f"[indicators] columns: {list(enriched.columns)}  rows after warmup: {len(enriched)}")

    results = []
    metrics = []
    for spec in REGISTRY.values():
        sig = spec.fn(enriched)
        res = run_backtest(enriched, sig, name=spec.name,
                           fee_bps=fee_bps, slippage_bps=slippage_bps)
        m = compute_metrics(res, BARS_PER_YEAR.get(interval, 365 * 24))
        results.append(res)
        metrics.append(m)
        print(f"[backtest] {spec.name:20s}  trades={m.trades:4d}  "
              f"win={m.win_rate*100:5.2f}%  pf={m.profit_factor:5.2f}  "
              f"dd={m.max_drawdown_pct*100:6.2f}%  ret={m.total_return_pct*100:7.2f}%")

    out = save_report(results, metrics, interval=interval,
                      source=fetched.source, out_dir=out_dir)
    print("\n[report] saved:")
    for k, v in out.items():
        print(f"  - {k}: {v}")

    print("\n[summary]\n" + metrics_table(metrics).to_string())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="BTC/USDT 1m/5m strategy backtest")
    ap.add_argument("--interval", choices=["1m", "5m", "15m", "1h"], default="1m")
    ap.add_argument("--bars", type=int, default=2000)
    ap.add_argument("--fee-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--synthetic", action="store_true",
                    help="Force synthetic OHLCV instead of attempting live fetch.")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    run(interval=args.interval, bars=args.bars, fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps, force_synthetic=args.synthetic,
        out_dir=args.out)


if __name__ == "__main__":
    main()
