"""Steps 5 & 6 — P&L report with win rate / max drawdown / profit factor."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Iterable, List

import numpy as np
import pandas as pd

from .backtest import BacktestResult


@dataclass
class Metrics:
    name: str
    bars: int
    trades: int
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy_pct: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe: float
    avg_bars_held: float

    def as_row(self) -> dict:
        d = asdict(self)
        d["win_rate"] = f"{self.win_rate*100:.2f}%"
        d["avg_win_pct"] = f"{self.avg_win_pct*100:.3f}%"
        d["avg_loss_pct"] = f"{self.avg_loss_pct*100:.3f}%"
        d["profit_factor"] = f"{self.profit_factor:.2f}"
        d["expectancy_pct"] = f"{self.expectancy_pct*100:.3f}%"
        d["total_return_pct"] = f"{self.total_return_pct*100:.2f}%"
        d["max_drawdown_pct"] = f"{self.max_drawdown_pct*100:.2f}%"
        d["sharpe"] = f"{self.sharpe:.2f}"
        d["avg_bars_held"] = f"{self.avg_bars_held:.1f}"
        return d


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def _annualised_sharpe(returns: pd.Series, bars_per_year: float) -> float:
    if returns.std(ddof=0) == 0 or returns.empty:
        return 0.0
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(bars_per_year))


def compute_metrics(result: BacktestResult, bars_per_year: float) -> Metrics:
    pnls = np.array([t.net_pnl_pct for t in result.trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_win = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(-losses.sum()) if losses.size else 0.0

    win_rate = float(wins.size / pnls.size) if pnls.size else 0.0
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(losses.mean()) if losses.size else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    expectancy = float(pnls.mean()) if pnls.size else 0.0
    total_ret = float(result.equity.iloc[-1] - 1.0) if not result.equity.empty else 0.0
    max_dd = _max_drawdown(result.equity)
    sharpe = _annualised_sharpe(result.returns, bars_per_year)
    avg_held = float(np.mean([t.bars_held for t in result.trades])) if result.trades else 0.0

    return Metrics(
        name=result.name,
        bars=int(len(result.returns)),
        trades=int(pnls.size),
        win_rate=win_rate,
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        profit_factor=pf,
        expectancy_pct=expectancy,
        total_return_pct=total_ret,
        max_drawdown_pct=max_dd,
        sharpe=sharpe,
        avg_bars_held=avg_held,
    )


def metrics_table(metrics: Iterable[Metrics]) -> pd.DataFrame:
    return pd.DataFrame([m.as_row() for m in metrics]).set_index("name")


def trades_to_frame(result: BacktestResult) -> pd.DataFrame:
    if not result.trades:
        return pd.DataFrame(columns=[
            "entry_time", "exit_time", "side", "entry_price", "exit_price",
            "bars_held", "gross_pnl_pct", "net_pnl_pct",
        ])
    rows = []
    for t in result.trades:
        rows.append({
            "entry_time": t.entry_time, "exit_time": t.exit_time,
            "side": "LONG" if t.side == 1 else "SHORT",
            "entry_price": round(t.entry_price, 2),
            "exit_price": round(t.exit_price, 2),
            "bars_held": t.bars_held,
            "gross_pnl_pct": round(t.gross_pnl_pct * 100, 4),
            "net_pnl_pct": round(t.net_pnl_pct * 100, 4),
        })
    return pd.DataFrame(rows)


def save_report(results: List[BacktestResult], metrics: List[Metrics],
                interval: str, source: str, out_dir: str = "reports") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    summary = metrics_table(metrics)
    summary_path = os.path.join(out_dir, f"summary_{interval}.csv")
    summary.to_csv(summary_path)

    trade_paths = {}
    for r in results:
        tf = trades_to_frame(r)
        p = os.path.join(out_dir, f"trades_{interval}_{r.name}.csv")
        tf.to_csv(p, index=False)
        trade_paths[r.name] = p

    equity_df = pd.concat({r.name: r.equity for r in results}, axis=1)
    equity_path = os.path.join(out_dir, f"equity_{interval}.csv")
    equity_df.to_csv(equity_path)

    plot_path = _plot_equity(equity_df, interval, source, out_dir)
    md_path = _write_markdown(summary, results, metrics, interval, source, out_dir, plot_path)

    return {
        "summary_csv": summary_path,
        "equity_csv": equity_path,
        "plot_png": plot_path,
        "markdown": md_path,
        "trades": trade_paths,
    }


def _plot_equity(equity_df: pd.DataFrame, interval: str, source: str, out_dir: str) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    for col in equity_df.columns:
        ax.plot(equity_df.index, equity_df[col], label=col, linewidth=1.3)
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.8)
    ax.set_title(f"BTC/USDT {interval} — strategy equity curves  (data: {source})")
    ax.set_ylabel("Equity (start = 1.0)")
    ax.set_xlabel("Time")
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    path = os.path.join(out_dir, f"equity_{interval}.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def _write_markdown(summary: pd.DataFrame, results: List[BacktestResult],
                    metrics: List[Metrics], interval: str, source: str,
                    out_dir: str, plot_path: str) -> str:
    lines: List[str] = []
    lines.append(f"# BTC/USDT {interval} backtest report")
    lines.append("")
    lines.append(f"- Data source: **{source}**")
    lines.append(f"- Bars analysed: **{results[0].equity.shape[0] if results else 0}**")
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(summary.to_markdown())
    lines.append("")
    lines.append(f"![equity curves]({os.path.basename(plot_path)})")
    lines.append("")
    for r, m in zip(results, metrics):
        lines.append(f"## {r.name}")
        lines.append("")
        lines.append(f"- Trades: **{m.trades}**  |  Win rate: **{m.win_rate*100:.2f}%**  |  "
                     f"Profit factor: **{m.profit_factor:.2f}**  |  "
                     f"Max DD: **{m.max_drawdown_pct*100:.2f}%**")
        lines.append(f"- Total return: **{m.total_return_pct*100:.2f}%**  |  "
                     f"Expectancy/trade: **{m.expectancy_pct*100:.3f}%**  |  "
                     f"Sharpe (annualised): **{m.sharpe:.2f}**")
        lines.append("")
    path = os.path.join(out_dir, f"report_{interval}.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path
