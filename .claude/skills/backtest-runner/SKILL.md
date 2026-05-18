---
name: backtest-runner
description: Generate strategy code from a YAML spec, run unit tests, then execute in-sample backtest plus Phase 5 robustness checks (parameter sensitivity, walk-forward, multi-asset, regime breakdown). Use when the user asks to "backtest", "run strategy", "implement spec", or "robustness check". Must NOT touch out-of-sample data.
---

# backtest-runner

Phase 3–5 嘅 skill。Spec → Python implementation → in-sample backtest → robustness checks。

## 關鍵原則：唔可以掂 OOS

呢個 skill 嘅 backtest period 由 spec 或 default 決定，最遲到 **2022-12-31**。
代碼必須有 hard guard：

```python
IN_SAMPLE_END = pd.Timestamp("2022-12-31")
assert df.index.max() <= IN_SAMPLE_END, "in-sample violation"
```

如果用戶話「跑全期」、「包括 2024」，要**stop and ask**——OOS 屬於 Phase 6。

## 何時用

- Spec 已就緒，要跑 backtest
- 想 re-run 一個已 implement 嘅 strategy（用唔同 cost 或 asset）
- 想跑 Phase 5 robustness check

## 流程

1. **讀 spec** `specs/<slug>.yaml`
2. **Codegen** `strategies/<slug>.py`，包含：
   - `compute_indicator(df: pd.DataFrame, params: dict) -> pd.Series`
   - `generate_signals(df, params) -> pd.DataFrame[signal, size]`
   - 全部 vectorized，禁 for-loop bar-by-bar
   - 每個 rolling stat 都加 `.shift(1)` 防 lookahead
3. **生成 unit tests** `tests/test_<slug>.py`
   - ≥ 3 個 known-input/known-output case
   - 用 fixed seed
4. **Lookahead lint**：grep code 揾任何冇 `.shift` 嘅 rolling 操作，flag 出嚟
5. **跑 pytest**——必須全 pass 至下一步
6. **In-sample backtest**（default 2018-01-01 → 2022-12-31, BTC/USDT）
   - Cost：taker 0.05%、slippage 5 bps、perp funding（若 spec 用 perp）
   - 起始資金 $100k
   - 用 spec 嘅 default param
7. **Phase 5 robustness**：
   - **5.1 Param sensitivity**：grid search default ±30% 範圍，畫 Sharpe heatmap
   - **5.2 Walk-forward**：5y train / 6m test，roll 8 次
   - **5.3 Multi-asset**：BTC, ETH, SOL, BNB, XRP, ADA, AVAX
   - **5.4 Regime**：bull/bear/chop（用 BTC 200-day MA）切
8. **Save outputs** 落 `backtests/<slug>/<run_id>/`：
   - `equity_curve.parquet`
   - `trades.parquet`
   - `metrics.json`（CAGR / Sharpe / Sortino / Calmar / MaxDD / WinRate / PF / Skew / Kurt）
   - `param_heatmap.png`
   - `walk_forward.json`
   - `multi_asset.json`
   - `regime_breakdown.json`
   - `meta.yaml`（**必須包括 trial count N**，下游 DSR 要用）

## Codegen template skeleton

```python
import pandas as pd
import numpy as np

IN_SAMPLE_END = pd.Timestamp("2022-12-31")

def compute_indicator(df: pd.DataFrame, params: dict) -> pd.Series:
    # 所有 rolling 都用 shift(1)
    ...

def generate_signals(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    assert df.index.max() <= IN_SAMPLE_END
    indicator = compute_indicator(df, params)
    signal = pd.Series(0, index=df.index)
    # entry / exit logic
    ...
    return pd.DataFrame({"signal": signal, "size": ...})
```

## 必要工具
- `Read`
- `Write`
- `Edit`
- `Bash`（pytest、backtest script）

## 唔做嘅嘢

- ❌ 唔掂 OOS（hard assert in code）
- ❌ 唔做 statistical test → `statistical-validator`
- ❌ 唔出 verdict → `strategy-report`
- ❌ 唔自己改 spec（如果發現 spec 有問題，stop and ask）

## 驗收 checklist

- [ ] pytest 全 pass
- [ ] Lookahead lint 0 warning
- [ ] `metrics.json` 有齊所有 metric
- [ ] `meta.yaml` 有 N（grid cell 數）、commit hash、seed、data snapshot date
- [ ] In-sample 結束日期 ≤ 2022-12-31
- [ ] Phase 5 嘅 4 個 sub-output 全部 generate 到

## 範例 prompt

```
用 backtest-runner 跑 specs/hawkes-vol-clustering.yaml。
跟 default config 跑 in-sample + Phase 5 全套 robustness check。
結果落 backtests/hawkes-vol-clustering/<auto-timestamp>/。
```
