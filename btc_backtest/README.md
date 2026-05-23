# BTC/USDT strategy backtest

End-to-end pipeline that covers the six steps:

1. **Import OHLCV** — `fetch_data.load_ohlcv()` pulls BTC/USDT 1m or 5m bars
   from Binance public REST endpoints. When the host has no outbound access
   to the exchange (sandboxed runs, etc.), it falls back to a cached CSV in
   `data/`, or to a realistic geometric-Brownian-motion synthetic series so
   the pipeline can still be exercised.
2. **Indicators** — `indicators.add_indicators()` attaches session VWAP,
   EMA(9/21/50/200), ATR(14), RSI(14) and a 30-bar volume z-score.
3. **Three strategies** (`strategies.py`):
   - `vwap_pullback` — trend-aligned VWAP reclaim with RSI + volume confirmation.
   - `ema_breakout` — Donchian breakout gated by EMA-21 slope and an ATR floor.
   - `rsi_mean_reversion` — counter-trend RSI fades inside a low-ATR range near VWAP.
4. **Backtest** — `backtest.run_backtest()` is a vectorised engine with a
   one-bar execution lag, per-side fees and slippage in basis points, and
   trade-by-trade reconstruction.
5. **P&L report** — `report.save_report()` writes per-strategy trade
   blotters, a combined equity curve PNG, a summary CSV and a Markdown
   report into `reports/`.
6. **Headline metrics** — every run prints and saves win rate, max
   drawdown and profit factor (plus expectancy, Sharpe and total return).

## Run it

```bash
pip install -r requirements.txt
python -m btc_backtest.main --interval 1m --bars 3000
python -m btc_backtest.main --interval 5m --bars 3000
# Force the offline path:
python -m btc_backtest.main --interval 5m --bars 3000 --synthetic
```

Flags:

| flag | default | meaning |
| --- | --- | --- |
| `--interval` | `1m` | `1m` / `5m` / `15m` / `1h` |
| `--bars` | `2000` | how many bars to pull |
| `--fee-bps` | `5` | per-side commission (bps) |
| `--slippage-bps` | `2` | per-side slippage (bps) |
| `--synthetic` | off | skip network and use the GBM generator |
| `--out` | `reports` | output directory |

## Outputs

For each run on interval `X` the pipeline writes:

- `reports/summary_X.csv` — headline metrics for all three strategies.
- `reports/equity_X.csv` and `reports/equity_X.png` — equity curves.
- `reports/trades_X_<strategy>.csv` — full trade blotter per strategy.
- `reports/report_X.md` — Markdown summary embedding the equity plot.

## Notes on the synthetic fallback

The synthetic generator uses ~80% annualised volatility and small Poisson
jumps to mimic BTC's tape; results from it should be read as a sanity check
of the pipeline, not as an estimate of real-market edge. Re-run with live
data (any host that can reach `api.binance.com`) to evaluate the strategies
against real conditions.
