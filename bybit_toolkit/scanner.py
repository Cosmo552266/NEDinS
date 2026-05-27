"""Bybit funding rate scanner.

Ranks USDT perpetuals by current funding rate, filtered for liquidity and
spread so the numbers are actually tradable.

Usage:
    python -m bybit_toolkit.scanner
    python -m bybit_toolkit.scanner --top 20 --min-volume 5000000
    python -m bybit_toolkit.scanner --history       # adds 30-period average
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from .bybit_api import Ticker, avg_funding_apr, get_linear_tickers
from .fixtures import demo_funding_history, demo_tickers


def fmt_pct(x: float, decimals: int = 4) -> str:
    return f"{x * 100:.{decimals}f}%"


def fmt_usd(x: float) -> str:
    if x >= 1_000_000_000:
        return f"${x / 1e9:.2f}B"
    if x >= 1_000_000:
        return f"${x / 1e6:.1f}M"
    if x >= 1_000:
        return f"${x / 1e3:.1f}K"
    return f"${x:.0f}"


def filter_tickers(
    tickers: list[Ticker],
    min_volume: float,
    max_spread_bps: float,
    only_usdt: bool,
) -> list[Ticker]:
    out = []
    for t in tickers:
        if only_usdt and not t.symbol.endswith("USDT"):
            continue
        if t.volume_24h_usd < min_volume:
            continue
        if t.spread_bps > max_spread_bps:
            continue
        if t.funding_rate == 0:
            continue
        out.append(t)
    return out


def print_table(
    tickers: list[Ticker],
    top: int,
    show_history: bool,
    history_lookback: int,
) -> None:
    headers = [
        ("Symbol", 14),
        ("Funding 8h", 11),
        ("APR (now)", 10),
        ("Next in", 9),
        ("Mark", 12),
        ("Spread bps", 11),
        ("Vol 24h", 10),
    ]
    if show_history:
        headers.insert(3, (f"APR avg{history_lookback}", 11))

    line = " ".join(f"{name:<{w}}" for name, w in headers)
    print(line)
    print("-" * len(line))

    for t in tickers[:top]:
        cols = [
            f"{t.symbol:<14}",
            f"{fmt_pct(t.funding_rate):<11}",
            f"{fmt_pct(t.funding_apr, 1):<10}",
            f"{t.hours_to_funding:>5.2f}h  ",
            f"{t.mark_price:<12.6g}",
            f"{t.spread_bps:>8.2f}   ",
            f"{fmt_usd(t.volume_24h_usd):<10}",
        ]
        if show_history:
            try:
                avg_apr = avg_funding_apr(t.symbol, history_lookback)
            except Exception:
                history = demo_funding_history(t.symbol, history_lookback)
                avg = sum(r for _, r in history) / len(history) if history else 0
                avg_apr = avg * 3 * 365
            cols.insert(3, f"{fmt_pct(avg_apr, 1):<11}")
        print(" ".join(cols))


def estimate_pnl(symbol: str, funding_rate: float, position_usd: float) -> None:
    """Print expected funding payout if you held a delta-neutral position."""
    per_8h = position_usd * funding_rate
    print()
    print(f"  Delta-neutral PnL estimate on {symbol} @ ${position_usd:.0f} notional:")
    print(f"    Per funding (8h): ${per_8h:+.4f}")
    print(f"    Per day:          ${per_8h * 3:+.4f}")
    print(f"    Per month (30d):  ${per_8h * 3 * 30:+.4f}")
    print(f"    Per year:         ${per_8h * 3 * 365:+.2f}")
    print(f"    APR equivalent:   {fmt_pct(funding_rate * 3 * 365, 2)}")
    print()
    print("  Note: this is gross. Subtract maker/taker fees (~0.04% round trip),")
    print("  spread, and any slippage. Also subtract any negative funding periods.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=15, help="rows to show")
    parser.add_argument(
        "--min-volume",
        type=float,
        default=10_000_000,
        help="min 24h turnover in USD (default 10M)",
    )
    parser.add_argument(
        "--max-spread",
        type=float,
        default=20.0,
        help="max bid/ask spread in basis points (default 20)",
    )
    parser.add_argument(
        "--all", action="store_true", help="include non-USDT pairs"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="also fetch 30-period average funding (slower, one request per symbol)",
    )
    parser.add_argument(
        "--lookback", type=int, default=30, help="periods for --history average"
    )
    parser.add_argument(
        "--estimate",
        type=float,
        default=0,
        help="if >0, show PnL estimate for top symbol at this USD notional",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="use bundled sample data instead of calling Bybit (offline-safe)",
    )
    args = parser.parse_args()

    print(
        f"Bybit Funding Rate Scanner  |  "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    print(
        f"Filter: vol >= {fmt_usd(args.min_volume)}, "
        f"spread <= {args.max_spread}bps, "
        f"{'all' if args.all else 'USDT-quoted only'}"
    )
    print()

    if args.demo:
        print("(demo mode — using bundled sample data, not live market)")
        tickers = demo_tickers()
    else:
        try:
            tickers = get_linear_tickers()
        except Exception as e:
            print(f"ERROR: could not fetch tickers: {e}", file=sys.stderr)
            print("Tip: pass --demo to run with bundled sample data.", file=sys.stderr)
            return 1

    print(f"Fetched {len(tickers)} perpetuals from Bybit.")
    filtered = filter_tickers(
        tickers,
        min_volume=args.min_volume,
        max_spread_bps=args.max_spread,
        only_usdt=not args.all,
    )
    filtered.sort(key=lambda t: t.funding_rate, reverse=True)
    print(f"{len(filtered)} pass filters. Top by funding rate:")
    print()

    print_table(filtered, args.top, args.history, args.lookback)

    print()
    print("Bottom 5 (most negative funding — short side pays you to be long):")
    print_table(filtered[-5:][::-1], 5, False, args.lookback)

    if args.estimate > 0 and filtered:
        estimate_pnl(filtered[0].symbol, filtered[0].funding_rate, args.estimate)

    return 0


if __name__ == "__main__":
    sys.exit(main())
