# Pipeline shakedown — 2026-05-18

> 唔係正式 strategy report，係 end-to-end pipeline 嘅 dry run 紀錄。
> 用嚟驗證 5 個 skill + 文件鏈條 work，**唔係**對 funding-rate-extreme-mr 嘅 verdict。

## 跑過嘅 phase

| Phase | Skill | Output | 狀態 |
|---|---|---|---|
| 1 Discovery | `crypto-research` | `research/2026-05-18-discovery.md` | ✅ Done — 4 candidate（2 promote, 1 hold, 1 reject） |
| 2 Spec | `indicator-spec` | `specs/funding-rate-extreme-mr.yaml` v0.1.0 | ✅ Done — schema validation PASS |
| 3 Implementation | `backtest-runner` (codegen) | `strategies/funding_rate_extreme_mr.py` + `tests/...` | ✅ Done — 5/5 unit tests pass，lookahead lint clean |
| 4 In-sample backtest | `backtest-runner` | `backtests/funding-rate-extreme-mr/<run>/` | 🟡 **Synthetic only** — sandbox 封鎖 Binance / cryptodatadownload egress |
| 5 Robustness | `backtest-runner` | (n/a) | ⏸ blocked，要真實 data |
| 6 Statistical validation | `statistical-validator` | (n/a) | ⏸ blocked |
| 7 Final report | `strategy-report` | (n/a) | ⏸ blocked |

## 對 candidate 嘅 verdict

**未有**。Synthetic backtest 嘅 metrics（CAGR 283%、Sharpe 未算）係 noise，唔可以用嚟做 verdict。需要：

1. 真實 BTC/USDT:USDT 1h OHLCV + funding rate, 2018-01-01 → 今日
2. 用真實 data 重跑 Phase 4，先得 in-sample metrics
3. 再行 Phase 5 robustness（grid search、walk-forward、multi-asset）
4. 最後解鎖 OOS，行 Phase 6

## Pipeline 學到嘅嘢

1. **Spec schema 設計太嚴** — `retrieved` 用 ISO date type 但 YAML auto-parses；要 quote 做 string。將會更新 schema 接受 date object。
2. **arxiv / Glassnode / Medium-style 站普遍 403 WebFetch** — `crypto-research` skill 要靠 WebSearch 嘅 synthesis 多過 individual page fetch。考慮加 RSS / Atom feed 為主要 source。
3. **vectorbt 重 dependency** — 第一輪 codegen 用 pure pandas/numpy 跑 unit test 更快（< 0.5s），vectorbt 留俾 production run。已 reflect 喺 strategy module 嘅 docstring。

## 下一步

當有真實 data infrastructure（live env 接駁到 Binance）：

```bash
# 1. Fetch data
python scripts/fetch_binance.py --symbol BTC/USDT:USDT --tf 1h --start 2018-01-01

# 2. 替換 scripts/run_phase4_demo.py 嘅 load_data() 用 parquet read

# 3. 加 Phase 5 runner
python scripts/run_phase5.py --slug funding-rate-extreme-mr
```

呢個 sandbox session 無法做。
