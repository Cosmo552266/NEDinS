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

## Framework：vectorbt

Default backtest engine：**vectorbt**（vectorized、numba JIT、適合 Phase 5 嘅 grid search + walk-forward）。

Codegen 由 `templates/vectorbt_strategy.py.tmpl` 開始，replace 5 個 placeholder：

| Placeholder | 內容 |
|---|---|
| `{{SLUG}}` | spec.name (kebab) |
| `{{CLASS_NAME}}` | PascalCase 版 |
| `{{HYPOTHESIS}}` | spec.hypothesis 一句版 |
| `{{INDICATOR_BODY}}` | spec.formula → vectorized pandas/numpy |
| `{{SIGNAL_BODY}}` | spec.entry_logic / exit_logic → boolean masks |
| `{{DEFAULT_PARAMS}}` | spec.parameters dataclass fields |

Template 已 bake 入：
- `IN_SAMPLE_END = 2022-12-31` hard guard
- 5 bps fee + 5 bps slippage default
- Optional perp `funding_rate` cost
- `metrics()` 出 workflow.md 要求嘅所有指標
- `param_sensitivity()` + `walk_forward()` helper（Phase 5）

### Indicator codegen rule

所有 rolling/expanding stat **必須 `.shift(1)`**：

```python
# ✅ 啱
df["close"].rolling(20).mean().shift(1)

# ❌ 錯（用咗當前 bar 嘅 close 計 MA）
df["close"].rolling(20).mean()
```

### 依賴

```bash
pip install vectorbt ccxt pandas numpy pyarrow loguru pytest jsonschema pyyaml
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
