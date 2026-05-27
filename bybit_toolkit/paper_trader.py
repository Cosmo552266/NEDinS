"""Paper-trading bot for delta-neutral funding rate arbitrage.

Simulates: buy spot + short equal-size perp.
Earns: funding payments every 8h (positive funding -> short side receives).
Costs: maker/taker fees on entry and exit.
Storage: JSON file under bybit_toolkit/data/

Subcommands:
    open    SYMBOL --notional USD [--fee-bps 4]
    close   POSITION_ID [--fee-bps 4]
    tick                              # apply funding for every open position
    status                            # show open positions + closed PnL
    reset                             # delete all paper state

Usage:
    python -m bybit_toolkit.paper_trader open BTCUSDT --notional 200
    python -m bybit_toolkit.paper_trader tick
    python -m bybit_toolkit.paper_trader status
    python -m bybit_toolkit.paper_trader close 1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .bybit_api import get_ticker
from .fixtures import demo_tickers

DATA_DIR = Path(__file__).parent / "data"
STATE_FILE = DATA_DIR / "paper_state.json"


@dataclass
class Position:
    id: int
    symbol: str
    qty: float                 # base units of the underlying
    entry_price: float
    notional_usd: float        # qty * entry_price
    opened_at_ms: int
    fee_paid_usd: float        # entry fee on both legs
    funding_received_usd: float = 0.0
    funding_ticks: int = 0
    last_tick_ms: int = 0
    closed: bool = False
    close_price: float = 0.0
    closed_at_ms: int = 0
    exit_fee_usd: float = 0.0

    @property
    def total_fees(self) -> float:
        return self.fee_paid_usd + self.exit_fee_usd

    @property
    def net_pnl(self) -> float:
        return self.funding_received_usd - self.total_fees

    def realized_apr(self) -> float:
        if self.closed_at_ms == 0:
            return 0.0
        days = max((self.closed_at_ms - self.opened_at_ms) / 86_400_000, 1 / 24)
        return self.net_pnl / self.notional_usd / days * 365


@dataclass
class State:
    next_id: int = 1
    positions: list[Position] = field(default_factory=list)
    demo: bool = False

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if not p.closed]

    def closed_positions(self) -> list[Position]:
        return [p for p in self.positions if p.closed]


def load_state() -> State:
    if not STATE_FILE.exists():
        return State()
    raw = json.loads(STATE_FILE.read_text())
    positions = [Position(**p) for p in raw.get("positions", [])]
    return State(
        next_id=raw.get("next_id", 1),
        positions=positions,
        demo=raw.get("demo", False),
    )


def save_state(state: State) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "next_id": state.next_id,
        "demo": state.demo,
        "positions": [asdict(p) for p in state.positions],
    }
    STATE_FILE.write_text(json.dumps(payload, indent=2))


def fetch_ticker(symbol: str, demo: bool):
    if demo:
        for t in demo_tickers():
            if t.symbol == symbol:
                return t
        return None
    return get_ticker(symbol)


def cmd_open(args: argparse.Namespace) -> int:
    state = load_state()
    if args.demo:
        state.demo = True
    ticker = fetch_ticker(args.symbol, state.demo)
    if ticker is None:
        print(f"Symbol {args.symbol} not found.", file=sys.stderr)
        return 1

    notional = args.notional
    mid = (ticker.bid1 + ticker.ask1) / 2 if ticker.bid1 > 0 and ticker.ask1 > 0 else ticker.mark_price
    qty = notional / mid
    # entry fee: spot (taker 0.1%) + perp (taker 0.055%) by default, configurable
    fee = notional * (args.fee_bps / 10_000) * 2  # two legs

    pos = Position(
        id=state.next_id,
        symbol=args.symbol,
        qty=qty,
        entry_price=mid,
        notional_usd=notional,
        opened_at_ms=int(time.time() * 1000),
        fee_paid_usd=fee,
        last_tick_ms=int(time.time() * 1000),
    )
    state.next_id += 1
    state.positions.append(pos)
    save_state(state)

    print(f"[OPENED #{pos.id}] {args.symbol} delta-neutral")
    print(f"  Notional:   ${notional:.2f}")
    print(f"  Qty:        {qty:.8g} (spot long + perp short)")
    print(f"  Entry mid:  {mid:.6g}")
    print(f"  Entry fees: ${fee:.4f} (two legs @ {args.fee_bps}bps each)")
    print(f"  Funding 8h: {ticker.funding_rate * 100:.4f}%  ->  next payment in {ticker.hours_to_funding:.2f}h")
    print(f"  Expected daily PnL (if funding holds): ${notional * ticker.funding_rate * 3:+.4f}")
    return 0


def cmd_close(args: argparse.Namespace) -> int:
    state = load_state()
    pos = next((p for p in state.positions if p.id == args.position_id and not p.closed), None)
    if pos is None:
        print(f"No open position #{args.position_id}.", file=sys.stderr)
        return 1
    ticker = fetch_ticker(pos.symbol, state.demo)
    if ticker is None:
        print(f"Could not fetch price for {pos.symbol}.", file=sys.stderr)
        return 1

    mid = (ticker.bid1 + ticker.ask1) / 2 if ticker.bid1 > 0 and ticker.ask1 > 0 else ticker.mark_price
    pos.close_price = mid
    pos.closed = True
    pos.closed_at_ms = int(time.time() * 1000)
    pos.exit_fee_usd = pos.notional_usd * (args.fee_bps / 10_000) * 2
    save_state(state)

    held_days = (pos.closed_at_ms - pos.opened_at_ms) / 86_400_000
    print(f"[CLOSED #{pos.id}] {pos.symbol}")
    print(f"  Held:            {held_days:.3f} days ({pos.funding_ticks} funding ticks)")
    print(f"  Funding earned:  ${pos.funding_received_usd:+.4f}")
    print(f"  Total fees:      ${pos.total_fees:.4f}")
    print(f"  Net PnL:         ${pos.net_pnl:+.4f}")
    print(f"  Realized APR:    {pos.realized_apr() * 100:+.2f}%")
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    """Credit funding to every open position for any funding boundary crossed."""
    state = load_state()
    if not state.open_positions():
        print("No open positions.")
        return 0

    now_ms = int(time.time() * 1000)
    eight_h_ms = 8 * 3600 * 1000

    for pos in state.open_positions():
        ticker = fetch_ticker(pos.symbol, state.demo)
        if ticker is None:
            print(f"  #{pos.id} {pos.symbol}: could not fetch, skipping")
            continue

        last = pos.last_tick_ms or pos.opened_at_ms
        # Bybit fundings at 00/08/16 UTC. We approximate: ticks = elapsed / 8h.
        if args.simulate_hours > 0:
            ticks = int(args.simulate_hours / 8)
            credit_per_tick = pos.notional_usd * ticker.funding_rate
            credit = credit_per_tick * ticks
        else:
            elapsed_ms = now_ms - last
            ticks = int(elapsed_ms // eight_h_ms)
            credit_per_tick = pos.notional_usd * ticker.funding_rate
            credit = credit_per_tick * ticks

        if ticks == 0:
            print(f"  #{pos.id} {pos.symbol}: no funding boundary crossed yet")
            continue

        pos.funding_received_usd += credit
        pos.funding_ticks += ticks
        pos.last_tick_ms = now_ms
        print(
            f"  #{pos.id} {pos.symbol}: +{ticks} tick(s) "
            f"({ticker.funding_rate * 100:+.4f}%/8h) "
            f"credited ${credit:+.4f}, total ${pos.funding_received_usd:+.4f}"
        )

    save_state(state)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state()
    opens = state.open_positions()
    closes = state.closed_positions()

    print(f"Paper trading state (demo={state.demo})")
    print("=" * 70)
    print(f"Open positions: {len(opens)}")
    if opens:
        print(f"{'ID':<4}{'Symbol':<12}{'Notional':<12}{'Funding $':<14}{'Fees $':<10}{'Net $':<10}")
        for p in opens:
            print(
                f"{p.id:<4}{p.symbol:<12}"
                f"${p.notional_usd:<10.2f}"
                f"{p.funding_received_usd:<+13.4f} "
                f"{p.fee_paid_usd:<9.4f} "
                f"{p.net_pnl:<+9.4f}"
            )
    print()
    print(f"Closed positions: {len(closes)}")
    if closes:
        total_pnl = sum(p.net_pnl for p in closes)
        total_fees = sum(p.total_fees for p in closes)
        total_funding = sum(p.funding_received_usd for p in closes)
        win_rate = sum(1 for p in closes if p.net_pnl > 0) / len(closes)
        print(f"  Total funding earned: ${total_funding:+.4f}")
        print(f"  Total fees paid:      ${total_fees:.4f}")
        print(f"  Total net PnL:        ${total_pnl:+.4f}")
        print(f"  Win rate:             {win_rate * 100:.1f}%")
        print()
        print(f"{'ID':<4}{'Symbol':<12}{'Days':<8}{'Net $':<10}{'APR':<10}")
        for p in closes[-10:]:
            days = (p.closed_at_ms - p.opened_at_ms) / 86_400_000
            print(f"{p.id:<4}{p.symbol:<12}{days:<8.3f}{p.net_pnl:<+9.4f} {p.realized_apr() * 100:<+9.2f}%")
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    print("Paper state reset.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="open a delta-neutral position")
    p_open.add_argument("symbol")
    p_open.add_argument("--notional", type=float, required=True, help="USD notional per leg")
    p_open.add_argument("--fee-bps", type=float, default=4.0, help="per-leg fee in basis points")
    p_open.add_argument("--demo", action="store_true")
    p_open.set_defaults(func=cmd_open)

    p_close = sub.add_parser("close", help="close a position")
    p_close.add_argument("position_id", type=int)
    p_close.add_argument("--fee-bps", type=float, default=4.0)
    p_close.set_defaults(func=cmd_close)

    p_tick = sub.add_parser("tick", help="credit funding for elapsed 8h ticks")
    p_tick.add_argument(
        "--simulate-hours",
        type=float,
        default=0.0,
        help="instead of using wall-clock, credit this many simulated hours",
    )
    p_tick.set_defaults(func=cmd_tick)

    p_status = sub.add_parser("status", help="show open + closed positions")
    p_status.set_defaults(func=cmd_status)

    p_reset = sub.add_parser("reset", help="wipe all paper state")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
