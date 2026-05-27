"""Bybit public API helpers. No API key required for market data."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests

BYBIT_BASE = "https://api.bybit.com"
TIMEOUT = 10


@dataclass
class Ticker:
    symbol: str
    last_price: float
    mark_price: float
    index_price: float
    funding_rate: float
    next_funding_time_ms: int
    volume_24h_usd: float
    bid1: float
    ask1: float

    @property
    def spread_bps(self) -> float:
        if self.bid1 <= 0 or self.ask1 <= 0:
            return float("inf")
        mid = (self.bid1 + self.ask1) / 2
        return (self.ask1 - self.bid1) / mid * 10_000

    @property
    def funding_apr(self) -> float:
        # Bybit funding rate is per 8h. 3 fundings per day, 365 days.
        return self.funding_rate * 3 * 365

    @property
    def hours_to_funding(self) -> float:
        return max(0.0, (self.next_funding_time_ms - time.time() * 1000) / 3_600_000)


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{BYBIT_BASE}{path}"
    r = requests.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit error {data.get('retCode')}: {data.get('retMsg')}")
    return data["result"]


def get_linear_tickers() -> list[Ticker]:
    """Fetch all USDT-perpetual tickers."""
    result = _get("/v5/market/tickers", {"category": "linear"})
    out: list[Ticker] = []
    for row in result.get("list", []):
        try:
            out.append(
                Ticker(
                    symbol=row["symbol"],
                    last_price=float(row.get("lastPrice") or 0),
                    mark_price=float(row.get("markPrice") or 0),
                    index_price=float(row.get("indexPrice") or 0),
                    funding_rate=float(row.get("fundingRate") or 0),
                    next_funding_time_ms=int(row.get("nextFundingTime") or 0),
                    volume_24h_usd=float(row.get("turnover24h") or 0),
                    bid1=float(row.get("bid1Price") or 0),
                    ask1=float(row.get("ask1Price") or 0),
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def get_ticker(symbol: str) -> Ticker | None:
    result = _get("/v5/market/tickers", {"category": "linear", "symbol": symbol})
    rows = result.get("list", [])
    if not rows:
        return None
    row = rows[0]
    return Ticker(
        symbol=row["symbol"],
        last_price=float(row.get("lastPrice") or 0),
        mark_price=float(row.get("markPrice") or 0),
        index_price=float(row.get("indexPrice") or 0),
        funding_rate=float(row.get("fundingRate") or 0),
        next_funding_time_ms=int(row.get("nextFundingTime") or 0),
        volume_24h_usd=float(row.get("turnover24h") or 0),
        bid1=float(row.get("bid1Price") or 0),
        ask1=float(row.get("ask1Price") or 0),
    )


def get_funding_history(symbol: str, limit: int = 30) -> list[tuple[int, float]]:
    """Return [(timestamp_ms, funding_rate), ...] newest first."""
    result = _get(
        "/v5/market/funding/history",
        {"category": "linear", "symbol": symbol, "limit": limit},
    )
    out: list[tuple[int, float]] = []
    for row in result.get("list", []):
        try:
            out.append((int(row["fundingRateTimestamp"]), float(row["fundingRate"])))
        except (KeyError, ValueError):
            continue
    return out


def avg_funding_apr(symbol: str, lookback: int = 30) -> float:
    """Average funding rate over last N periods, annualized."""
    history = get_funding_history(symbol, lookback)
    if not history:
        return 0.0
    avg = sum(r for _, r in history) / len(history)
    return avg * 3 * 365
