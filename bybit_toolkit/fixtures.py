"""Offline sample data so the tools can be demoed without network access."""
from __future__ import annotations

import time

from .bybit_api import Ticker


def _now_plus(hours: float) -> int:
    return int((time.time() + hours * 3600) * 1000)


def demo_tickers() -> list[Ticker]:
    """Plausible Bybit linear-perp snapshot for tutorials and tests."""
    return [
        Ticker("BTCUSDT", 102345.5, 102340.1, 102338.0, 0.00012, _now_plus(3.5), 4_800_000_000, 102345.0, 102346.0),
        Ticker("ETHUSDT", 3845.2, 3844.9, 3845.0, 0.00018, _now_plus(3.5), 2_100_000_000, 3845.1, 3845.3),
        Ticker("SOLUSDT", 178.45, 178.43, 178.44, 0.00031, _now_plus(3.5), 580_000_000, 178.44, 178.46),
        Ticker("DOGEUSDT", 0.2145, 0.2144, 0.2145, 0.00045, _now_plus(3.5), 320_000_000, 0.21449, 0.21451),
        Ticker("AVAXUSDT", 28.55, 28.54, 28.55, 0.00028, _now_plus(3.5), 95_000_000, 28.54, 28.56),
        Ticker("PEPEUSDT", 0.0000142, 0.0000142, 0.0000142, 0.00089, _now_plus(3.5), 180_000_000, 0.00001419, 0.00001421),
        Ticker("LINKUSDT", 21.34, 21.33, 21.34, 0.00021, _now_plus(3.5), 110_000_000, 21.33, 21.35),
        Ticker("ARBUSDT", 0.875, 0.874, 0.875, 0.00065, _now_plus(3.5), 60_000_000, 0.8749, 0.8751),
        Ticker("WIFUSDT", 1.23, 1.229, 1.23, 0.00125, _now_plus(3.5), 75_000_000, 1.229, 1.231),
        Ticker("ORDIUSDT", 18.4, 18.39, 18.4, -0.00015, _now_plus(3.5), 40_000_000, 18.39, 18.41),
        Ticker("MATICUSDT", 0.48, 0.479, 0.48, -0.00028, _now_plus(3.5), 85_000_000, 0.4799, 0.4801),
        Ticker("OPUSDT", 1.85, 1.849, 1.85, -0.00055, _now_plus(3.5), 55_000_000, 1.849, 1.851),
        Ticker("APEUSDT", 0.82, 0.819, 0.82, 0.00008, _now_plus(3.5), 28_000_000, 0.8199, 0.8201),
        Ticker("NEARUSDT", 4.85, 4.849, 4.85, 0.00022, _now_plus(3.5), 70_000_000, 4.849, 4.851),
        Ticker("SUIUSDT", 3.42, 3.419, 3.42, 0.00038, _now_plus(3.5), 130_000_000, 3.419, 3.421),
        Ticker("INJUSDT", 22.5, 22.49, 22.5, 0.00033, _now_plus(3.5), 45_000_000, 22.49, 22.51),
        Ticker("TIAUSDT", 5.65, 5.649, 5.65, 0.00041, _now_plus(3.5), 50_000_000, 5.649, 5.651),
        Ticker("SEIUSDT", 0.42, 0.4199, 0.42, 0.00078, _now_plus(3.5), 65_000_000, 0.4199, 0.4201),
        Ticker("FETUSDT", 1.15, 1.149, 1.15, 0.00098, _now_plus(3.5), 80_000_000, 1.1499, 1.1501),
        Ticker("RNDRUSDT", 7.85, 7.849, 7.85, 0.00052, _now_plus(3.5), 55_000_000, 7.849, 7.851),
    ]


def demo_funding_history(symbol: str, limit: int = 30) -> list[tuple[int, float]]:
    """Pseudo-random but stable per-symbol funding history."""
    base = sum(ord(c) for c in symbol) % 50 / 100_000  # 0 .. 0.0005
    sign = 1 if "USDT" in symbol and len(symbol) <= 8 else 1
    out: list[tuple[int, float]] = []
    now = int(time.time() * 1000)
    for i in range(limit):
        ts = now - i * 8 * 3600 * 1000
        rate = sign * (base + (i % 5 - 2) * 0.00002)
        out.append((ts, rate))
    return out
