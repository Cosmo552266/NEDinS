---
name: statistical-validator
description: Run Phase 6 statistical validation — out-of-sample replay, Monte Carlo simulations (trade shuffle + bootstrap), random-entry p-value, Deflated Sharpe Ratio, and paired t-test vs. buy-and-hold. Use only AFTER backtest-runner has completed Phase 5 robustness. Use when the user mentions "OOS", "Monte Carlo", "p-value", "DSR", "validate", "Phase 6".
---

# statistical-validator

Phase 6 嘅 skill。解鎖 OOS data，跑嚴謹統計檢驗。

## 神聖規則

**OOS data 只可以由呢個 skill 接觸。**

之前 backtest-runner 嘅 code 內有 `assert df.index.max() <= IN_SAMPLE_END`。
呢度 explicit 解鎖：

```python
import os
os.environ["PHASE_6_UNLOCKED"] = "1"
# 之後 load 完整 history
```

**全套 validation 對同一個 strategy 只跑一次**。如果 fail，唔可以調 param 再跑——咁樣等於 OOS pollution，要重新攞更近期 OOS window。

## 何時用

- backtest-runner 完成 + Phase 5 全部 pass
- 用戶話 "validate / OOS / Monte Carlo / DSR / 統計檢驗"

## 前置檢查

1. Confirm Phase 5 passed：讀 `backtests/<slug>/<run_id>/walk_forward.json`、`multi_asset.json` 等
2. Confirm spec param **locked**：spec YAML 嘅 commit hash 同 strategy file 嘅 commit hash 對得上
3. Confirm 之前無偷睇 OOS：grep strategy code 揾有冇 hard-coded 2023+ 日期或者 if/else 偷雞

## 流程

1. **OOS replay**（2023-01-01 → 今日）
   - 攞 in-sample 鎖定嘅 default param
   - 用同樣 cost model
   - 跑出完整 metrics dashboard
   - Output: `oos_metrics.json`

2. **Monte Carlo A — trade-order shuffle**
   - 攞 in-sample + OOS 嘅 trade PnL list
   - 隨機重排 10,000 次（fixed seed）
   - 每次計 Max DD
   - Output: `mc_drawdown.json`（含分佈、真實 DD percentile）

3. **Monte Carlo B — bootstrap returns**
   - 攞 daily returns
   - Sample with replacement 10,000 次
   - 每次計 annualized Sharpe
   - Output: `mc_sharpe_ci.json`（含 95% CI lower / upper）

4. **Random-entry p-value**
   - 用同 strategy 同 holding period，但 entry 隨機
   - 跑 1,000 次
   - 計策略 Sharpe 喺 random 分佈嘅 percentile → p-value
   - Output: `random_entry_pvalue.json`

5. **Deflated Sharpe Ratio**
   - 公式：Bailey & López de Prado (2014)
   - Inputs：observed SR、trial count N（由 backtest meta 攞）、skew、kurtosis、sample length T
   - Output: `dsr.json`（DSR value、對應 p-value）

6. **Paired t-test vs. buy-and-hold**
   - daily strategy return − daily BTC buy-and-hold return
   - 跑 t-test，one-sided（H1：strategy > BAH）
   - Output: `t_test_vs_bah.json`

7. **Summary**：寫 `summary.md`，每條 pass condition 打 ✅/❌：

   | Check | Threshold | Actual | Pass? |
   |---|---|---|---|
   | OOS Sharpe | ≥ 0.5 × IS Sharpe | X.XX | ✅/❌ |
   | OOS Sharpe absolute | > 0.5 | X.XX | ✅/❌ |
   | MC DD percentile | 25–75th | X.X% | ✅/❌ |
   | Bootstrap Sharpe CI lower | > 0 | X.XX | ✅/❌ |
   | Random entry p-value | < 0.05 | X.XXX | ✅/❌ |
   | DSR | > 0 with p < 0.05 | X.XX | ✅/❌ |
   | t-test vs. BAH | p < 0.05 | X.XXX | ✅/❌ |

## Output 目錄

`validations/<slug>/<run_id>/`：
- `oos_metrics.json`
- `mc_drawdown.json`
- `mc_sharpe_ci.json`
- `random_entry_pvalue.json`
- `dsr.json`
- `t_test_vs_bah.json`
- `summary.md`
- `meta.yaml`（含 upstream backtest run_id、commit hash、seed）

## 必要工具
- `Read`
- `Bash`
- `Write`

## 唔做嘅嘢

- ❌ 唔重新 tune param（OOS fail 就 fail）
- ❌ 唔出 verdict → `strategy-report`
- ❌ 唔自己加 metric（standardize 7 個 check）

## 驗收 checklist

- [ ] Phase 5 證實 pass 先開始
- [ ] Strategy code git diff 顯示 in-sample 後無改動
- [ ] 7 個 check 全部跑完
- [ ] 所有 random number 用 fixed seed
- [ ] `summary.md` 列齊 pass/fail per check
- [ ] N（trial count）從 backtest meta 攞，無 hard-code

## 範例 prompt

```
hawkes-vol-clustering 通過咗 Phase 5。
用 statistical-validator 跑全套 Phase 6，
backtest run_id 係 2026-05-18T14:30:00Z。
```
