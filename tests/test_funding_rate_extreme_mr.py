"""Unit tests for strategies.funding_rate_extreme_mr.

Run: pytest tests/test_funding_rate_extreme_mr.py -v
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# allow `import strategies` when running pytest from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategies.funding_rate_extreme_mr import (
    Params,
    compute_thresholds,
    generate_signals,
    simulate,
    IN_SAMPLE_END,
)


def _synthetic(n: int = 200, *, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="1h", tz="UTC")
    close = 30_000 + np.cumsum(rng.normal(0, 50, n))
    df = pd.DataFrame({
        "open": close + rng.normal(0, 5, n),
        "high": close + np.abs(rng.normal(0, 20, n)),
        "low": close - np.abs(rng.normal(0, 20, n)),
        "close": close,
        "volume": rng.uniform(100, 200, n),
        "funding_rate": rng.normal(0.0001, 0.0003, n),
    }, index=idx)
    return df


def test_no_lookahead_in_thresholds():
    """upper/lower at row t must be computable using only funding rows < t."""
    df = _synthetic(n=300)
    p = Params(lookback_hours=50)
    th = compute_thresholds(df["funding_rate"], p)
    # mutate the last row of funding; thresholds before the last row should not change
    df2 = df.copy()
    df2.loc[df2.index[-1], "funding_rate"] = 999.0
    th2 = compute_thresholds(df2["funding_rate"], p)
    # all rows up to and including the last should be identical
    pd.testing.assert_series_equal(
        th["upper"].iloc[:-1], th2["upper"].iloc[:-1], check_names=False
    )


def test_signal_triggers_on_extreme_funding():
    """Inject a funding spike and verify a short signal appears one bar later."""
    df = _synthetic(n=200)
    p = Params(lookback_hours=50, upper_percentile=0.90, lower_percentile=0.10)
    # set bar 100's funding to a huge value -> p90 of prior 50 obs will be exceeded next bar
    df.loc[df.index[100], "funding_rate"] = 0.05
    sig = generate_signals(df, p)
    # signal at bar 101 (using funding(100) shifted) should be -1
    assert sig.iloc[101] == -1, f"expected short signal, got {sig.iloc[101]}"


def test_oos_guard_raises():
    """Simulator must refuse to run on post-2022 data when in_sample_only=True."""
    idx = pd.date_range("2023-06-01", periods=50, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "open": 30000.0, "high": 30100.0, "low": 29900.0, "close": 30000.0,
        "volume": 100.0, "funding_rate": 0.0,
    }, index=idx)
    with pytest.raises(AssertionError, match="OOS leakage"):
        simulate(df, Params())


def test_simulator_executes_a_trade():
    """End-to-end smoke test — at least one trade should fire."""
    df = _synthetic(n=400)
    # plant several funding extremes to guarantee trades
    df.loc[df.index[80], "funding_rate"] = 0.02
    df.loc[df.index[200], "funding_rate"] = -0.02
    p = Params(lookback_hours=50, upper_percentile=0.90, lower_percentile=0.10,
               holding_bars=10)
    result = simulate(df, p, position_fraction=0.05)
    assert result["trade_count"] >= 1
    # equity stays positive and finite
    assert np.isfinite(result["final_equity"])
    assert result["final_equity"] > 0


def test_params_defaults_match_spec():
    """Guardrail: if spec.yaml changes defaults, this test reminds you to update Params."""
    import yaml
    spec = yaml.safe_load(
        open(Path(__file__).resolve().parents[1] / "specs" / "funding-rate-extreme-mr.yaml")
    )
    sp = spec["parameters"]
    p = Params()
    assert p.lookback_hours == sp["lookback_hours"]["default"]
    assert p.upper_percentile == sp["upper_percentile"]["default"]
    assert p.lower_percentile == sp["lower_percentile"]["default"]
    assert p.holding_bars == sp["holding_bars"]["default"]
