"""Sweep leverage to find where 1m scalper crosses break-even."""

from __future__ import annotations

from strategy import backtest, data_loader, indicator


def main() -> None:
    df = data_loader.synthetic_btc(n_bars=259_200, bar_minutes=1, seed=7)
    df = indicator.compute(df)
    df = indicator.add_htf_filter(df, working_tf_minutes=1, htf_minutes=15, ema_len=200)

    print(f"{'sl/tp':>7}  {'lev':>4}  {'trades':>6}  {'WR':>6}  {'avgR':>6}  {'PF':>5}  "
          f"{'final$':>7}  {'DD%':>6}")
    print("-" * 70)
    for sl, tp in [(3.0, 9.0), (3.0, 12.0), (4.0, 12.0), (4.0, 16.0), (5.0, 15.0)]:
     for lev in (3, 5, 10):
        cfg = backtest.Config(
            entry_mode="compression",
            long_threshold=25.0, short_threshold=25.0,
            adx_min=18.0, sl_atr=sl, tp_atr=tp,
            trail_atr=max(1.0, sl-0.5), trail_activate_R=2.0,
            max_bars_in_trade=45,
            risk_pct=0.06, max_leverage=float(lev),
            use_htf_filter=True,
            cb_max_range_pct=0.004, cb_min_oci=25.0,
        )
        res = backtest.backtest(df, cfg)
        s = res.stats()
        if s.get("trades", 0) == 0:
            print(f"{sl:.0f}/{tp:.0f}    {lev:4d}  (no trades)")
            continue
        pf = s.get("profit_factor", 0)
        pf_s = f"{pf:5.2f}" if pf != float("inf") else "  inf"
        print(f"{sl:3.1f}/{tp:3.1f}  {lev:4d}  {s['trades']:6d}  {s['win_rate']*100:5.1f}%  "
              f"{s['avg_R']:+5.2f}  {pf_s}  {s['final_equity']:7.2f}  "
              f"{s['max_drawdown']*100:5.1f}%")


if __name__ == "__main__":
    main()
