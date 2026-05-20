"""Show why 10x leverage on 1m timeframe is unforgiving on fees."""

from __future__ import annotations


def breakeven_wr(tp_atr: float, sl_atr: float, atr_pct: float,
                 lev: float, fee_bps_round: float) -> float:
    """Win-rate needed to break even on average.

    win_equity_pct = tp_atr * atr_pct * lev - fee_bps_round/100 * lev
    loss_equity_pct = sl_atr * atr_pct * lev + fee_bps_round/100 * lev
    Need: wr * win - (1 - wr) * loss = 0
    """
    win_pct = tp_atr * atr_pct * lev - (fee_bps_round / 10_000.0) * lev
    loss_pct = sl_atr * atr_pct * lev + (fee_bps_round / 10_000.0) * lev
    if win_pct <= 0:
        return 1.0
    return loss_pct / (win_pct + loss_pct)


def main() -> None:
    atr_pct = 0.116      # median 1m BTC ATR/price, from synthetic
    fee_bps = 12.0       # 6 bps taker+slip per side x 2
    print("Break-even win-rate matrix (1m BTC, ATR≈0.116% of price)")
    print(f"Fee round-trip: {fee_bps:.0f} bps")
    print()
    print(f"{'lev':>4}  {'SL/TP':<10}  {'win%req':>8}  {'win$@$26':>9}  {'loss$@$26':>9}")
    print("-" * 60)
    for lev in (1, 3, 5, 10, 20):
        for sl, tp in [(1.0, 2.0), (1.0, 4.0), (1.0, 6.0), (1.5, 6.0), (2.0, 8.0)]:
            wr = breakeven_wr(tp, sl, atr_pct / 100.0, lev, fee_bps) * 100
            win_dollars = (tp * atr_pct / 100.0 * lev - fee_bps / 10_000.0 * lev) * 26
            loss_dollars = (sl * atr_pct / 100.0 * lev + fee_bps / 10_000.0 * lev) * 26
            print(f"{lev:4d}  {sl:.1f}/{tp:.1f}   {wr:7.1f}%  "
                  f"${win_dollars:8.3f}  ${loss_dollars:8.3f}")
        print()


if __name__ == "__main__":
    main()
