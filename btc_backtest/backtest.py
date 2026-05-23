"""Step 4 — vectorised backtester for {-1, 0, +1} positions.

Trades are taken on the next bar's open after a signal change to avoid
look-ahead. Commission and slippage are charged on every position change in
units of the new exposure (one-way) — i.e. a flip from +1 to -1 pays
``cost * |delta|`` = ``cost * 2``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int            # +1 long, -1 short
    entry_price: float
    exit_price: float
    bars_held: int
    gross_pnl_pct: float
    net_pnl_pct: float


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series                  # cumulative equity index, starts at 1.0
    returns: pd.Series                 # per-bar net returns
    position: pd.Series                # executed position per bar
    trades: List[Trade] = field(default_factory=list)


def run_backtest(df: pd.DataFrame,
                 signal: pd.Series,
                 name: str,
                 fee_bps: float = 5.0,
                 slippage_bps: float = 2.0) -> BacktestResult:
    """fee_bps / slippage_bps are per-side, applied on each unit of position change."""
    cost = (fee_bps + slippage_bps) / 10_000.0

    # Execute on next bar's open: position effective from t+1 using signal at t
    pos = signal.shift(1).fillna(0).astype(int)
    open_price = df["open"]
    # Bar return: from this bar's open to next bar's open, holding ``pos`` over it
    bar_ret = open_price.shift(-1) / open_price - 1.0
    gross = pos * bar_ret

    # Costs charged when position changes (on this bar's open)
    pos_delta = pos.diff().abs().fillna(pos.abs())
    fees = pos_delta * cost
    net = (gross - fees).fillna(0.0)

    equity = (1.0 + net).cumprod()

    # Reconstruct discrete trades
    trades: List[Trade] = []
    current_side = 0
    entry_idx = None
    entry_price = None
    for i in range(len(pos)):
        side = int(pos.iat[i])
        if side != current_side:
            if current_side != 0 and entry_idx is not None:
                exit_price = float(open_price.iat[i])
                bars_held = i - entry_idx
                gross_pnl = current_side * (exit_price / entry_price - 1.0)
                net_pnl = gross_pnl - 2 * cost  # entry + exit cost
                trades.append(Trade(
                    entry_time=df.index[entry_idx],
                    exit_time=df.index[i],
                    side=current_side,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    bars_held=bars_held,
                    gross_pnl_pct=gross_pnl,
                    net_pnl_pct=net_pnl,
                ))
            if side != 0:
                entry_idx = i
                entry_price = float(open_price.iat[i])
            else:
                entry_idx = None
                entry_price = None
            current_side = side
    # Close any open trade at last bar
    if current_side != 0 and entry_idx is not None:
        last = len(df) - 1
        exit_price = float(open_price.iat[last])
        bars_held = last - entry_idx
        gross_pnl = current_side * (exit_price / entry_price - 1.0)
        net_pnl = gross_pnl - 2 * cost
        trades.append(Trade(
            entry_time=df.index[entry_idx],
            exit_time=df.index[last],
            side=current_side,
            entry_price=entry_price,
            exit_price=exit_price,
            bars_held=bars_held,
            gross_pnl_pct=gross_pnl,
            net_pnl_pct=net_pnl,
        ))

    return BacktestResult(name=name, equity=equity, returns=net, position=pos, trades=trades)
