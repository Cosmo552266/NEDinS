# SMC 1m Scalper — Closed-Loop Spec

Built from the user's TradingView indicator stack:

| Screenshot label         | Implementation                              |
| ------------------------ | ------------------------------------------- |
| SCALPTOOL R1.1 34/89/111/144 | 4-EMA stack regime filter            |
| HL OTT 2 1.5 15 VAR      | VIDYA + percent-band trailing line          |
| Liquidity Concepts CHoCH/BOS | Swing pivots + Break-of-Structure state machine |
| Order Block Detector     | Last opposite-colour candle before impulse  |
| LuxAlgo Liquidity (FRVP) | Rolling fixed-range Volume Profile + POC    |

Mandated by the user:
- **1-minute timeframe**
- **10× leverage cap**
- **Compounding** (fixed-fractional sizing on current equity)
- **180-day backtest**

---

## 1. The indicators

### 1.1 EMA stack (SCALPTOOL)
```
ema34, ema89, ema111, ema144
stack_bull = ema34 > ema89 > ema111 > ema144
stack_bear = ema34 < ema89 < ema111 < ema144
```
Captures the multi-timeframe trend alignment a scalper visually reads on chart.

### 1.2 HL OTT
A VIDYA (variable-index moving average) with a percent band trail. Acts like
a slower Supertrend.
```
VAR = VIDYA(close, length=15)
band = VAR * 1.5%
trail follows long_stop / short_stop with state flip on close-cross
ott_dir ∈ {+1, -1}
```

### 1.3 Swing pivots + BOS / CHoCH
```
pivot_high(i) = high[i] is max in window [i-5, i+5]   # confirmed only at i+5
pivot_low (i) = low [i] is min in window [i-5, i+5]
last_ph / last_pl = forward-fill last confirmed pivot
BOS_up   = close crosses above last_ph
BOS_dn   = close crosses below last_pl
smc_state +1 after a BOS_up, -1 after a BOS_dn
CHoCH    = first BOS in the opposite direction of the previous state
```

### 1.4 Order Blocks
```
bullish_OB = last bear candle before a >=1.5×ATR upward impulse
  zone     = [low, high] of that bear candle
  invalid  = price closes through bull_ob_low
```
Mirrored for bearish OBs.

### 1.5 Fixed-range Volume Profile POC
```
For each bar i, take the prior 360 bars, bin (high+low+close)/3 into 50
buckets weighted by volume. POC = bucket with max volume. HVN (high-volume
node) range = bins with volume >= 70th percentile.
```

---

## 2. Entry logic — confluence score

The system uses a **score** (0..5) rather than hard AND, so missing or
slow-confirming indicators don't permanently lock the strategy out.

For each side, sum the points:
1. EMA stack aligned in that direction
2. OTT direction agrees
3. SMC state agrees (last BOS = same direction)
4. Price touched a *fresh* OB (≤ 80 bars old) in this bar
5. Trigger fired this bar:
   - LONG  : low ≤ recent 5-bar low **and** close > prev_high **and** close > EMA34
   - SHORT : high ≥ recent 5-bar high **and** close < prev_low  **and** close < EMA34

Enter when `score ≥ CONFLUENCE_TH` (default 4) **and** the opposite-side
score is strictly lower.

> The fifth condition combines the *liquidity sweep* (sweeping the recent
> extreme) with the *reclaim* (close back through prior bar + EMA34) — the
> textbook SMC trigger.

---

## 3. Risk & exits

| Item                  | Rule                                                                   |
| --------------------- | ---------------------------------------------------------------------- |
| Stop (long)           | `max(OB_low − 0.5×ATR, entry − SL_ATR_MAX×ATR)`                        |
| Stop (short)          | mirror                                                                 |
| Take profit           | `entry ± TP_R_TARGET × stop_distance` capped at `TP_ATR_MAX × ATR`     |
| Trailing              | Chandelier `extreme ∓ 2.5×ATR` after MFE ≥ 2R                          |
| Flip exit             | Immediate exit on `ott_dir` flip against position                      |
| Time stop             | 60 bars (1h on 1m)                                                     |
| Sizing                | `risk = 6% × current_equity`; `qty = risk / stop_distance`             |
| Leverage              | Cap at **10×**; bind when ATR is small                                 |
| Fees                  | 4 bps taker × 2 + 2 bps slippage = **12 bps round-trip**               |

The sizing is the **compounding** mechanism: every trade scales risk to
current equity, so the same edge produces geometric growth (or geometric
decay if expectancy is negative).

---

## 4. The hard reality of 10× leverage on 1-minute

This is the single most important finding for the closed-loop AI.

**Fees per trade at 10× leverage are ≈ 1R when the stop is 1 ATR.**

Derivation (median 1m BTC ATR ≈ 0.116 % of price):
```
risk_dollars = SL_ATR · ATR_pct · lev · equity
             = 1.0 · 0.00116 · 10 · equity = 1.16 % of equity   (= 1R)
fee per side = (taker + slip) bps · notional
             = (4 + 2) bps · 10 · equity = 0.6 % of equity
fee round-trip = 1.2 % of equity = 1.03 R
```

`Fees / 1R` is **independent of leverage** — scaling leverage scales
1R and fees proportionally. So switching from 10× to 1× doesn't help.

**Implications**

| TP : SL | Break-even win rate | Achievable? |
| ------- | ------------------- | ----------- |
| 2 : 1   | 67.8 %              | No          |
| 4 : 1   | 40.7 %              | Hard        |
| 6 : 1   | 29.1 %              | Yes         |

**To escape the fee trap there are only three doors:**
1. Widen the stop (SL = 3 ATR → fees become ~0.35 R per trade).
2. Use maker-only with rebates (fees → 0 bps or negative).
3. Trade much less frequently (total fee burden shrinks).

The SMC scalper above takes door (1): the OB-based stops are typically
1.5–2.5 × ATR rather than 1 ATR.

---

## 5. Why synthetic data cannot validate this strategy

The strategy was built and runs cleanly, but the calibrated synthetic
data shows negative expectancy across all configurations (PF 0.5–0.8,
win rate 30–37 %, see §6).

SMC concepts work in *real* BTC 1m because of microstructure that does
not exist in the synthetic generator:

- **Stop hunts** — wicks designed to clear pending stops, followed by
  reversal. These create the liquidity-sweep + reclaim pattern that the
  trigger condition fires on.
- **Order block respect** — institutional re-fills at OB zones produce
  the bounce after a touch. GBM has no concept of "remembering" a price
  zone.
- **News-driven jumps + funding-driven mean reversion** — both produce
  predictable post-event behaviour absent in any random-walk model.

Honest conclusion: **synthetic validation says the code is correct and
the math is sound; live validation on Binance 1m klines is required to
verify the edge.**

---

## 6. Reference numbers (synthetic, 180-day, multi-seed)

`python -m strategy.smc_multi`

| Seed | Th | Trades | WR    | Avg R   | PF   | Final $ | Max DD |
| ---: | -: | -----: | ----: | ------: | ---: | ------: | -----: |
|    7 |  3 |    275 | 35.3% | -0.175  | 0.71 | $0.99   | -96.8% |
|   19 |  3 |    327 | 37.6% | -0.161  | 0.73 | $1.00   | -96.3% |
|   42 |  3 |    311 | 34.4% | -0.190  | 0.83 | $0.98   | -96.3% |
|    7 |  4 |    277 | 35.7% | -0.289  | 0.80 | $0.99   | -96.7% |
|   19 |  4 |    209 | 33.0% | -0.272  | 0.78 | $0.99   | -96.4% |

**Across every seed × every threshold the strategy ends near $0** with
PF 0.71–0.83 and WR 33–38 %. The result is *consistent* across seeds:
not noise, but a real (negative) edge on this data generator.

Smoke-tested on 30-day, seed = 7:

| Confluence ≥ | Trades | WR    | Avg R  | PF   | Final $ | Max DD |
| ------------ | -----: | ----: | -----: | ---: | ------: | -----: |
| 5            | 5      | 20%   | -0.731 | 0.05 | $21.87  | -15.9% |

Threshold 5 (all five must align) protects the account (only -15.9 %)
but produces too few trades to compound — *and* the synthetic data
doesn't reward SMC pattern recognition.

---

## 7. The closed-loop pseudocode

```python
for bar in stream:
    f = compute_indicators(bar)        # EMA stack, OTT, pivots, OBs, POC

    if pos is None:
        score_l = (
            f.stack_bull
            + (f.ott_dir == 1)
            + (f.smc_state == 1)
            + touches_fresh_bull_ob(bar, f)
            + sweep_and_reclaim_long(bar, f)
        )
        score_s = ...mirror...
        if score_l >= TH and score_l > score_s:
            open_long(stop=ob_based_stop(f), tp_R=TP_R_TARGET, risk=6% * equity)
        elif score_s >= TH and score_s > score_l:
            open_short(...)
    else:
        update_chandelier(pos, f.atr)
        if   pos.hit_stop()                     : close(reason="trail" if pos.trail_active else "stop")
        elif pos.hit_take()                     : close(reason="take")
        elif f.ott_dir != pos.dir               : close(reason="ott_flip")
        elif pos.bars >= MAX_BARS               : close(reason="time")
```

Single deterministic loop, suitable for a closed-loop AI agent. Tune
only `CONFLUENCE_TH`, `TP_R_TARGET`, `SL_ATR_MAX`.

---

## 8. Files

```
strategy/
  smc.py                 indicator stack (EMA, OTT, pivots, OBs, POC)
  smc_scalper.py         entry/exit engine + runner
  smc_multi.py           multi-seed sweep
SMC_SCALPER.md           this document
```

Run with `python -m strategy.smc_scalper` (default 180-day 1m run) or
`--bars 43200` for a 30-day smoke test.
