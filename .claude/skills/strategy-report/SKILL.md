---
name: strategy-report
description: Aggregate backtest and validation outputs into a final markdown report with verdict (GREEN / YELLOW / RED). Use when the user asks to "write report", "verdict", "summarize results", or completes Phase 6. Also appends a row to decisions.md.
---

# strategy-report

Phase 7 嘅 skill。整合 Phase 4–6 嘅 output，出 markdown report，決定 verdict。

## 何時用

- statistical-validator 完成 + summary.md 已 generate
- 用戶話 "出 report / verdict / summarize / 寫 final"

## 流程

1. **Collect inputs**
   - In-sample metrics：`backtests/<slug>/<run_id>/metrics.json`
   - Phase 5 outputs：同個 run 嘅 walk_forward、multi_asset、regime_breakdown
   - Validation outputs：`validations/<slug>/<run_id>/*`
   - Spec：`specs/<slug>.yaml`

2. **生成 metric table**

   | Metric | In-sample | OOS | Δ |
   |---|---|---|---|
   | CAGR | ... | ... | ... |
   | Sharpe | ... | ... | ... |
   | Sortino | ... | ... | ... |
   | Calmar | ... | ... | ... |
   | Max DD | ... | ... | ... |
   | Win rate | ... | ... | ... |
   | Profit factor | ... | ... | ... |

3. **Pass condition checklist**（每條打 ✅/❌）

   Phase 5:
   - [ ] Param sensitivity：default ±30% Sharpe drop < 20%
   - [ ] Walk-forward：median WF Sharpe ≥ 0.7 × IS Sharpe
   - [ ] Multi-asset：≥ 4/7 asset Sharpe > 1.0
   - [ ] Regime：Sharpe 唔係集中喺單一 regime

   Phase 6:
   - [ ] OOS Sharpe ≥ 0.5 × IS Sharpe
   - [ ] OOS Sharpe > 0.5 absolute
   - [ ] MC DD percentile 落 25–75th
   - [ ] Bootstrap Sharpe 95% CI lower > 0
   - [ ] Random entry p < 0.05
   - [ ] DSR > 0 且 p < 0.05
   - [ ] t-test vs. BAH p < 0.05

4. **Verdict 決定**（嚴格按 rule，唔自由發揮）

   | Verdict | 條件 |
   |---|---|
   | 🟢 GREEN | Phase 5 + Phase 6 全部 ✅ |
   | 🟡 YELLOW | ≥ 80% ✅ 但有 1–2 條 ❌ 喺非 critical 項 |
   | 🔴 RED | OOS Sharpe fail，或 DSR ≤ 0，或 CI 包含 0，或 < 80% ✅ |

   ⚠️ **Critical 項**（呢啲 fail 直接 RED，唔可以 YELLOW）：
   - OOS Sharpe < 0
   - DSR ≤ 0
   - Bootstrap CI 下界 ≤ 0
   - Random entry p ≥ 0.05

5. **寫 report**（7 個 section，順序固定）

   ```markdown
   # <strategy slug> — Strategy Report
   
   **Date**: YYYY-MM-DD  
   **Spec version**: 0.X.0  
   **In-sample run**: <run_id>  
   **Validation run**: <run_id>  
   **Verdict**: 🟢/🟡/🔴 <name>
   
   ## 1. Hypothesis
   <一段話講 economic mechanism>
   
   ## 2. Method
   - Data: ...
   - Period: ...
   - Cost: ...
   - Position sizing: ...
   
   ## 3. Results Summary
   <metric table>
   
   ## 4. Robustness (Phase 5)
   <4 個 check 嘅結果 + 一段 prose>
   
   ## 5. Statistical Validation (Phase 6)
   <7 個 check 嘅結果 + 一段 prose>
   
   ## 6. Caveats
   <至少 1 個 limitation>
   
   ## 7. Verdict & Next Steps
   <verdict 重申 + 下一步建議：paper trade / iterate / archive>
   ```

6. **Append 到 `decisions.md`**

   ```markdown
   | YYYY-MM-DD | <slug> | <verdict> | OOS Sharpe | DSR | <note> |
   ```

7. **Output**：`reports/<YYYY-MM-DD>-<slug>.md`

## 必要工具
- `Read`
- `Write`
- `Edit`（append decisions.md）

## 唔做嘅嘢

- ❌ 唔自己改 verdict 規則
- ❌ 唔幫 YELLOW 自動 retry（用戶決定下一步）
- ❌ 唔再跑 backtest（只整合）
- ❌ 唔篩走唔好嘅 metric（要 transparent）

## 驗收 checklist

- [ ] 7 個 section 齊
- [ ] 所有 metric 同上游 JSON 對得上（無 cherry-pick）
- [ ] Verdict 同 pass condition checklist 一致
- [ ] 至少 1 個 caveat（live trading risk、regime dependence 等）
- [ ] decisions.md 新 row 同 report verdict 一致
- [ ] 已 push 到 git

## 範例 prompt

```
用 strategy-report 整合 hawkes-vol-clustering 嘅所有結果，
in-sample run_id = 2026-05-18T14:30:00Z，
validation run_id = 2026-05-21T09:00:00Z。
出 report 同 update decisions.md。
```
