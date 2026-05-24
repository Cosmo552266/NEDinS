"""End-to-end driver for xStocks: fetch -> analyse -> 3-strategy backtest -> report."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from btc_backtest.indicators import add_indicators
from btc_backtest.backtest import run_backtest
from btc_backtest.report import compute_metrics, save_report, metrics_table, Metrics

from stock_backtest.analysis import analyze_universe
from stock_backtest.calendar import bars_per_year, session_id
from stock_backtest.fetch_data import BYBIT_XSTOCKS_LISTED, load_ohlcv
from stock_backtest.strategies import REGISTRY


DEFAULT_UNIVERSE = ("AAPLx", "TSLAx", "NVDAx", "MSFTx", "SPYx")


def _parse_symbols(arg: str) -> tuple[str, ...]:
    if arg.lower() == "all":
        return BYBIT_XSTOCKS_LISTED
    return tuple(s.strip() for s in arg.split(",") if s.strip())


def run(symbols: tuple[str, ...], interval: str, bars: int,
        fee_bps: float, slippage_bps: float, force_synthetic: bool,
        out_dir: str) -> dict:
    enriched: Dict[str, pd.DataFrame] = {}
    sources: Dict[str, str] = {}

    for sym in symbols:
        fetched = load_ohlcv(sym, interval=interval, bars=bars,
                             force_synthetic=force_synthetic)
        df = fetched.df
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        sk = session_id(df.index)
        df = add_indicators(df, session_key=sk)
        if len(df) < 60:
            print(f"[skip] {sym}: only {len(df)} bars after warmup")
            continue
        enriched[sym] = df
        sources[sym] = fetched.source
        print(f"[fetch] {sym} ({fetched.underlying}) {interval}: "
              f"{len(df)} bars after indicators  source={fetched.source}")

    if not enriched:
        raise RuntimeError("no symbols produced usable data")

    print("\n[analysis] screening universe…")
    analysis = analyze_universe(enriched, interval=interval, out_dir=out_dir,
                                sources=sources)
    print("[analysis] dashboard ->", analysis.dashboard_md)
    for sym, row in analysis.snapshot.iterrows():
        print(f"  {sym:7s}  regime={row['regime']:<8s}  "
              f"rec={row['recommended_strategy']}")

    bpy = bars_per_year(interval)
    aggregate_rows: List[pd.DataFrame] = []
    artefacts: Dict[str, dict] = {}
    best_equity: Dict[str, pd.Series] = {}

    for sym, df in enriched.items():
        results = []
        metrics: List[Metrics] = []
        for spec in REGISTRY.values():
            sig = spec.fn(df)
            res = run_backtest(df, sig, name=spec.name,
                               fee_bps=fee_bps, slippage_bps=slippage_bps)
            m = compute_metrics(res, bpy)
            results.append(res)
            metrics.append(m)
            print(f"[bt] {sym:7s} {spec.name:20s}  trades={m.trades:4d}  "
                  f"win={m.win_rate*100:5.2f}%  pf={m.profit_factor:5.2f}  "
                  f"dd={m.max_drawdown_pct*100:6.2f}%  ret={m.total_return_pct*100:7.2f}%")

        sym_out = save_report(results, metrics, interval=interval,
                              source=sources[sym], out_dir=out_dir,
                              asset_label=f"{sym} (Bybit xStock)", tag=sym)
        artefacts[sym] = sym_out

        row = metrics_table(metrics).reset_index()
        row.insert(0, "symbol", sym)
        aggregate_rows.append(row)

        best = max(metrics, key=lambda m: m.total_return_pct)
        best_result = next(r for r in results if r.name == best.name)
        best_equity[f"{sym}:{best.name}"] = best_result.equity

    aggregate = pd.concat(aggregate_rows, ignore_index=True)
    agg_csv = f"{out_dir}/aggregate_{interval}.csv"
    aggregate.to_csv(agg_csv, index=False)
    print(f"\n[aggregate] {agg_csv}")
    print(aggregate.to_string(index=False))

    agg_md = _write_aggregate_md(aggregate, best_equity, analysis.dashboard_md,
                                 interval, out_dir, sources)
    print(f"[aggregate] markdown -> {agg_md}")

    return {
        "analysis": analysis.dashboard_md,
        "aggregate_csv": agg_csv,
        "aggregate_md": agg_md,
        "per_symbol": artefacts,
    }


def _write_aggregate_md(aggregate: pd.DataFrame, best_equity: Dict[str, pd.Series],
                        dashboard_path: str, interval: str, out_dir: str,
                        sources: Dict[str, str]) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 5))
    for label, eq in best_equity.items():
        ax.plot(eq.index, eq.values, label=label, linewidth=1.1)
    ax.axhline(1.0, color="grey", linestyle="--", linewidth=0.8)
    ax.set_title(f"xStocks best-strategy equity per symbol ({interval})")
    ax.set_ylabel("Equity (start = 1.0)")
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    plot_path = f"{out_dir}/aggregate_{interval}.png"
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)

    lines = [
        f"# xStocks aggregate backtest report ({interval})",
        "",
        f"See [analysis dashboard]({Path(dashboard_path).name}) for the pre-trade screen.",
        "",
        f"![best equity per symbol]({Path(plot_path).name})",
        "",
        "## Sources",
        "",
        ", ".join(f"`{s}`={src}" for s, src in sources.items()),
        "",
        "## Full results",
        "",
        aggregate.to_markdown(index=False),
        "",
    ]
    # Best per symbol by total_return_pct (parse the percent string back)
    def _pct(s):
        try:
            return float(str(s).rstrip("%"))
        except ValueError:
            return float("-inf")
    by_sym = (aggregate.assign(_ret=aggregate["total_return_pct"].map(_pct))
                       .sort_values("_ret", ascending=False)
                       .drop(columns="_ret"))
    lines.append("## Best strategy per symbol (by total return)")
    lines.append("")
    lines.append(by_sym.groupby("symbol").head(1).to_markdown(index=False))
    lines.append("")

    path = f"{out_dir}/aggregate_{interval}.md"
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="xStocks (Bybit) backtest pipeline")
    ap.add_argument("--symbols", default=",".join(DEFAULT_UNIVERSE),
                    help="Comma-separated xStock tickers, or 'all' for the full Bybit list. "
                         f"Known: {','.join(BYBIT_XSTOCKS_LISTED)}")
    ap.add_argument("--interval", choices=["1m", "5m", "15m", "1h", "1d"], default="5m",
                    help="Yahoo intraday caps: 1m=7d, 5m=60d, 15m=60d, 1h=730d.")
    ap.add_argument("--bars", type=int, default=3000)
    ap.add_argument("--fee-bps", type=float, default=5.0)
    ap.add_argument("--slippage-bps", type=float, default=2.0)
    ap.add_argument("--synthetic", action="store_true",
                    help="Force the GBM synthetic generator (sandbox-safe).")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    run(symbols=_parse_symbols(args.symbols),
        interval=args.interval, bars=args.bars,
        fee_bps=args.fee_bps, slippage_bps=args.slippage_bps,
        force_synthetic=args.synthetic, out_dir=args.out)


if __name__ == "__main__":
    main()
