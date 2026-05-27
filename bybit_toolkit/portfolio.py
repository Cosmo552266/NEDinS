"""Portfolio tracker.

Reads a portfolio definition (JSON) and a daily equity history (CSV) and
reports:
  - current allocation vs target
  - realized P&L, daily returns, Sharpe, max drawdown
  - rebalancing suggestions

Portfolio file format (bybit_toolkit/data/portfolio.json):
{
  "base_currency": "USDT",
  "sleeves": [
    {"name": "funding_arb",  "target_pct": 60, "current_usd": 600},
    {"name": "earn_flexi",   "target_pct": 25, "current_usd": 280},
    {"name": "btc_hold",     "target_pct": 10, "current_usd": 90},
    {"name": "cash_buffer",  "target_pct":  5, "current_usd": 30}
  ]
}

Equity history CSV (bybit_toolkit/data/equity.csv):
  date,equity_usd
  2025-12-01,1000.00
  2025-12-02,1003.50
  ...

Subcommands:
  init      - write a starter portfolio.json + sample equity.csv
  show      - allocation table vs target, rebalance suggestion
  metrics   - Sharpe, max drawdown, CAGR on equity.csv
  log       - append today's equity (auto-sums sleeves)
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
EQUITY_FILE = DATA_DIR / "equity.csv"


def load_portfolio() -> dict:
    if not PORTFOLIO_FILE.exists():
        raise FileNotFoundError(f"{PORTFOLIO_FILE} not found. Run `portfolio init` first.")
    return json.loads(PORTFOLIO_FILE.read_text())


def save_portfolio(p: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_FILE.write_text(json.dumps(p, indent=2))


def load_equity() -> list[tuple[date, float]]:
    if not EQUITY_FILE.exists():
        return []
    out: list[tuple[date, float]] = []
    with EQUITY_FILE.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                e = float(row["equity_usd"])
                out.append((d, e))
            except (KeyError, ValueError):
                continue
    out.sort(key=lambda x: x[0])
    return out


def append_equity(d: date, equity: float) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existed = EQUITY_FILE.exists()
    with EQUITY_FILE.open("a", newline="") as f:
        writer = csv.writer(f)
        if not existed:
            writer.writerow(["date", "equity_usd"])
        writer.writerow([d.isoformat(), f"{equity:.2f}"])


def cmd_init(args: argparse.Namespace) -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if PORTFOLIO_FILE.exists() and not args.force:
        print(f"{PORTFOLIO_FILE} already exists. Use --force to overwrite.")
        return 1
    starter = {
        "base_currency": "USDT",
        "note": "Bybit-only conservative split. Edit sleeves to match reality.",
        "sleeves": [
            {"name": "funding_arb",  "target_pct": 60, "current_usd": 0.0,
             "desc": "Delta-neutral spot + perp short on Bybit"},
            {"name": "earn_flexi",   "target_pct": 25, "current_usd": 0.0,
             "desc": "Bybit Earn flexible savings (USDT)"},
            {"name": "btc_hold",     "target_pct": 10, "current_usd": 0.0,
             "desc": "BTC/ETH long-term DCA"},
            {"name": "cash_buffer",  "target_pct":  5, "current_usd": 0.0,
             "desc": "Free USDT for emergencies / margin top-up"},
        ],
    }
    save_portfolio(starter)
    print(f"Wrote {PORTFOLIO_FILE}.")
    if not EQUITY_FILE.exists():
        EQUITY_FILE.write_text("date,equity_usd\n")
        print(f"Wrote {EQUITY_FILE}.")
    print("Next: edit current_usd values, then run `portfolio show`.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    p = load_portfolio()
    sleeves = p["sleeves"]
    total = sum(s["current_usd"] for s in sleeves)
    if total <= 0:
        print("Total equity is 0. Edit sleeves[].current_usd in portfolio.json.")
        return 1

    print(f"Portfolio ({p.get('base_currency', 'USDT')})  total = ${total:,.2f}")
    print("=" * 78)
    print(f"{'Sleeve':<16}{'Target':>8}{'Current':>9}{'USD':>14}{'Drift':>10}{'Rebalance':>15}")
    print("-" * 78)
    for s in sleeves:
        cur_pct = s["current_usd"] / total * 100
        target_pct = s["target_pct"]
        drift = cur_pct - target_pct
        target_usd = target_pct / 100 * total
        rebal = target_usd - s["current_usd"]
        arrow = " " if abs(rebal) < 0.5 else ("BUY " if rebal > 0 else "SELL")
        print(
            f"{s['name']:<16}"
            f"{target_pct:>7.1f}%"
            f"{cur_pct:>8.1f}%"
            f"${s['current_usd']:>12.2f}"
            f"{drift:>+9.1f}%"
            f"   {arrow}${abs(rebal):>7.2f}"
        )
    print("-" * 78)

    drift_total = sum(abs(s["current_usd"] / total * 100 - s["target_pct"]) for s in sleeves)
    print(f"Total drift: {drift_total:.1f} percentage points")
    if drift_total > 10:
        print("  -> consider rebalancing")
    else:
        print("  -> within tolerance")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    if args.equity is not None:
        equity = args.equity
    else:
        try:
            p = load_portfolio()
            equity = sum(s["current_usd"] for s in p["sleeves"])
        except FileNotFoundError:
            print("Provide --equity or run `portfolio init` first.", file=sys.stderr)
            return 1
    d = date.today() if args.date is None else datetime.strptime(args.date, "%Y-%m-%d").date()
    append_equity(d, equity)
    print(f"Logged {d.isoformat()}: ${equity:,.2f}")
    return 0


def daily_returns(equity: list[tuple[date, float]]) -> list[float]:
    returns: list[float] = []
    for (_, e1), (_, e2) in zip(equity, equity[1:]):
        if e1 > 0:
            returns.append(e2 / e1 - 1)
    return returns


def sharpe_ratio(returns: list[float], risk_free_apr: float = 0.04) -> float:
    if len(returns) < 2:
        return 0.0
    rf_daily = risk_free_apr / 365
    excess = [r - rf_daily for r in returns]
    mean = statistics.mean(excess)
    sd = statistics.pstdev(excess)
    if sd == 0:
        return 0.0
    return mean / sd * math.sqrt(365)


def max_drawdown(equity: list[tuple[date, float]]) -> tuple[float, date | None, date | None]:
    if not equity:
        return 0.0, None, None
    peak = equity[0][1]
    peak_date = equity[0][0]
    max_dd = 0.0
    dd_start: date | None = None
    dd_end: date | None = None
    for d, e in equity:
        if e > peak:
            peak = e
            peak_date = d
        dd = (e - peak) / peak if peak > 0 else 0
        if dd < max_dd:
            max_dd = dd
            dd_start = peak_date
            dd_end = d
    return max_dd, dd_start, dd_end


def cmd_metrics(args: argparse.Namespace) -> int:
    equity = load_equity()
    if len(equity) < 2:
        print("Need at least 2 equity points. Run `portfolio log` daily.")
        return 1

    start_d, start_e = equity[0]
    end_d, end_e = equity[-1]
    days = (end_d - start_d).days or 1
    total_return = end_e / start_e - 1
    cagr = (end_e / start_e) ** (365 / days) - 1 if start_e > 0 else 0.0

    returns = daily_returns(equity)
    sharpe = sharpe_ratio(returns)
    dd, dd_start, dd_end = max_drawdown(equity)
    vol = statistics.pstdev(returns) * math.sqrt(365) if len(returns) >= 2 else 0.0

    print(f"Equity metrics  {start_d.isoformat()} -> {end_d.isoformat()}  ({days} days)")
    print("=" * 60)
    print(f"  Start equity:      ${start_e:,.2f}")
    print(f"  End equity:        ${end_e:,.2f}")
    print(f"  Total return:      {total_return * 100:+.2f}%")
    print(f"  CAGR (annualized): {cagr * 100:+.2f}%")
    print(f"  Volatility (ann.): {vol * 100:.2f}%")
    print(f"  Sharpe ratio:      {sharpe:.2f}  (rf 4% assumed)")
    print(f"  Max drawdown:      {dd * 100:.2f}%")
    if dd_start and dd_end:
        print(f"    from {dd_start} to {dd_end}")
    print()
    print(f"  Daily return stats over {len(returns)} days:")
    if returns:
        print(f"    mean:   {statistics.mean(returns) * 100:+.4f}%")
        print(f"    median: {statistics.median(returns) * 100:+.4f}%")
        print(f"    best:   {max(returns) * 100:+.4f}%")
        print(f"    worst:  {min(returns) * 100:+.4f}%")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="write starter portfolio.json")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_show = sub.add_parser("show", help="allocation vs target")
    p_show.set_defaults(func=cmd_show)

    p_log = sub.add_parser("log", help="append today's equity to equity.csv")
    p_log.add_argument("--equity", type=float, help="override total equity")
    p_log.add_argument("--date", type=str, help="YYYY-MM-DD (default today)")
    p_log.set_defaults(func=cmd_log)

    p_m = sub.add_parser("metrics", help="Sharpe / CAGR / drawdown")
    p_m.set_defaults(func=cmd_metrics)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
