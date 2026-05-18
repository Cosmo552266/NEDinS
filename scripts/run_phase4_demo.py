"""Phase 4 demo runner — produces the artifact layout expected by
backtest-runner skill, using SYNTHETIC data because this sandbox blocks
egress to Binance/CryptoDataDownload.

For real runs:
  1. pip install ccxt vectorbt
  2. Fetch BTC/USDT:USDT 1h OHLCV + funding from Binance (≥ 2 years)
  3. Save to data/ohlcv/binance/BTC_USDT_USDT/1h.parquet
  4. Replace the `load_data()` call here with parquet read
"""
from __future__ import annotations
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# repo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strategies.funding_rate_extreme_mr import Params, simulate, IN_SAMPLE_END


SLUG = "funding-rate-extreme-mr"


def load_data() -> pd.DataFrame:
    """SYNTHETIC stand-in. Replace with parquet read for real backtest."""
    n = 24 * 365 * 5   # 5 years of hourly bars
    rng = np.random.default_rng(2026)
    idx = pd.date_range("2018-01-01", periods=n, freq="1h", tz="UTC")
    # AR(1) returns with occasional vol shocks
    rets = rng.normal(0, 0.005, n)
    rets += 0.02 * np.sin(np.arange(n) / 4000)
    close = 10_000 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.0005, n)),
        "high": close * (1 + np.abs(rng.normal(0, 0.002, n))),
        "low":  close * (1 - np.abs(rng.normal(0, 0.002, n))),
        "close": close,
        "volume": rng.uniform(100, 500, n),
        # funding mean-reverting OU(theta=0, kappa=ln2/8, sigma=0.0003)
        "funding_rate": _ou_path(n, half_life=8, sigma=0.0003, seed=2026),
    }, index=idx)
    return df.loc[df.index <= IN_SAMPLE_END]


def _ou_path(n: int, half_life: float, sigma: float, seed: int) -> np.ndarray:
    kappa = np.log(2) / half_life
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = x[i-1] * (1 - kappa) + sigma * rng.normal()
    return x


def metrics_from_simulate(result: dict, df: pd.DataFrame) -> dict:
    trades = result["trades"]
    if not trades:
        return {"trade_count": 0, "note": "no trades fired"}
    pnls = np.array([t["pnl"] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    final_eq = result["final_equity"]
    init = 100_000.0
    days = (df.index.max() - df.index.min()).days
    cagr = (final_eq / init) ** (365 / max(days, 1)) - 1
    return {
        "total_return": result["total_return"],
        "cagr": float(cagr),
        "trade_count": len(trades),
        "win_rate": float(len(wins) / len(trades)),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if losses.sum() < 0 else float("inf"),
        "best_trade": float(pnls.max()),
        "worst_trade": float(pnls.min()),
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / "backtests" / SLUG / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[phase4] loading data (SYNTHETIC — sandbox blocks live API)")
    df = load_data()
    print(f"[phase4] data: {df.index.min()} → {df.index.max()}, {len(df):,} bars")

    p = Params()
    print(f"[phase4] running simulate with {p}")
    result = simulate(df, p, in_sample_only=True)
    m = metrics_from_simulate(result, df)
    print(f"[phase4] metrics: {json.dumps(m, indent=2)}")

    # save artifacts
    (out_dir / "metrics.json").write_text(json.dumps(m, indent=2))
    trades_df = pd.DataFrame(result["trades"])
    if not trades_df.empty:
        trades_df.to_parquet(out_dir / "trades.parquet")

    meta = {
        "run_id": run_id,
        "slug": SLUG,
        "spec_file": "specs/funding-rate-extreme-mr.yaml",
        "spec_version": "0.1.0",
        "git_commit": git_commit(),
        "random_seed": 2026,
        "data_source": "SYNTHETIC (sandbox: no network egress)",
        "in_sample_period": [str(df.index.min()), str(df.index.max())],
        "param_trial_count_N": 1,
        "phase5_complete": False,
        "phase6_unlocked": False,
        "notes": "Real backtest blocked by sandbox network restrictions. "
                 "All Phase 3 infrastructure verified working with synthetic OU funding path.",
    }
    (out_dir / "meta.yaml").write_text(
        "\n".join(f"{k}: {json.dumps(v)}" for k, v in meta.items())
    )

    print(f"[phase4] artifacts saved to {out_dir.relative_to(ROOT)}/")
    print(f"[phase4] DONE")


if __name__ == "__main__":
    main()
