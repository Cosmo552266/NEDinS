# Skill 需求規格（Skill Requirements）

> 呢份描述 `.claude/skills/` 入面 5 個 skill 各自要做咩、輸入輸出、依賴、驗收條件。
> 對應實作喺 `.claude/skills/<name>/SKILL.md`。

---

## 概覽

| Skill | Phase | Trigger 關鍵字 |
|---|---|---|
| `crypto-research` | 1 | "搵 candidate"、"discover indicator"、"weekly scan" |
| `indicator-spec` | 2 | "spec 化"、"轉成 YAML"、"formalize indicator" |
| `backtest-runner` | 3–5 | "backtest"、"run strategy"、"robustness check" |
| `statistical-validator` | 6 | "OOS"、"Monte Carlo"、"p-value"、"DSR" |
| `strategy-report` | 7 | "出 report"、"verdict"、"summary" |

---

## 1. `crypto-research`

### 1.1 目的
喺指定 sources 上搜尋、過濾、shortlist 可以做加密貨幣交易嘅 indicator / theory candidate。

### 1.2 必備工具
- `WebSearch` — query 學術 + 業界 sources
- `WebFetch` — 拉具體文章 / paper 內容
- `Write` — 落 `research/<date>-discovery.md`

### 1.3 輸入
- Scan window（default：過去 7 日）
- Source 清單（default：見 workflow.md Phase 1）
- 主題偏好（optional，例：mean-reversion、microstructure、on-chain）
- 排除清單（已研究過嘅 candidate slug）

### 1.4 行為
1. 為每個 source 構造 search query
2. WebSearch + WebFetch 拉內容（每篇 < 500 token excerpt）
3. 用 workflow.md 嘅「過濾準則」逐個 candidate 評
4. 對通過者，輸出 candidate card（格式見 workflow.md Phase 1）
5. 對 reject 者，喺 discovery.md 末尾 log 一行 reason

### 1.5 輸出
- 一個 `research/<YYYY-MM-DD>-discovery.md`
- 3–5 個 candidate card
- 每個 card 必須有：URL、hypothesis、data 需求、初步評分、next-step recommendation

### 1.6 驗收
- 所有 URL 可以 reach
- 無 hypothesis 缺失嘅 card
- 至少一個 candidate 嘅 source 喺 7 日內發佈
- 拒絕嘅 candidate 都有寫低 reason

### 1.7 邊界（NOT 包含）
- ❌ 唔做 spec 化（係 Phase 2 嘅事）
- ❌ 唔做 backtest
- ❌ 唔自己生成 indicator（必須 cite 來源）

---

## 2. `indicator-spec`

### 2.1 目的
將 prose 描述嘅 indicator/strategy 轉成 schema-valid YAML spec。

### 2.2 必備工具
- `Read` — 讀 discovery.md candidate card
- `WebFetch` — 如果 card 有 source URL 但 prose 唔夠詳細，再拉一次原文
- `Write` — 落 `specs/<slug>.yaml`
- `Bash` — 跑 schema validation script

### 2.3 輸入
- 一個 candidate card（藉由路徑或內嵌）

### 2.4 行為
1. 識別所有 free parameter，set default + range
2. 將 entry/exit logic 寫成偽代碼
3. 將 formula 寫成 LaTeX 或 reproducible Python expression
4. 填埋 risk section（stop_loss、max_concurrent、position_sizing）
5. 用 `pyyaml + jsonschema` validate

### 2.5 輸出
- `specs/<slug>.yaml`（schema 見 workflow.md Phase 2）

### 2.6 驗收
- YAML parse 成功
- Schema validation pass
- `formula` 入面每個 symbol 都喺 `parameters` 或 `data.fields` 出現
- 至少 1 個 parameter 有非 default range

### 2.7 邊界（NOT 包含）
- ❌ 唔生成 Python 實作
- ❌ 唔做 sanity backtest

---

## 3. `backtest-runner`

### 3.1 目的
讀 spec → 生成 Python implementation → 跑 Phase 4（in-sample）+ Phase 5（robustness）。

### 3.2 必備工具
- `Read` — 讀 spec
- `Write` — 生成 `strategies/<slug>.py`、`tests/test_<slug>.py`
- `Bash` — 跑 pytest、跑 backtest script
- `Edit` — 修 codegen 結果

### 3.3 輸入
- Spec 路徑
- Backtest config（symbol list、period override、cost override，全部 optional）

### 3.4 行為（順序）
1. **Codegen**：根據 spec 生成 strategy class
2. **Lookahead check**：跑靜態 lint，flag 任何冇 `.shift(1)` 嘅 rolling
3. **Unit test**：跑 pytest，必須全 pass 至下一步
4. **In-sample backtest**：default 2018-01-01 → 2022-12-31，BTC/USDT
5. **Robustness**：
   - 5.1 Param sensitivity heatmap
   - 5.2 Walk-forward（5×1）
   - 5.3 Multi-asset（7 個 alt）
   - 5.4 Regime breakdown
6. **記錄 trial count** N（grid search cell 總數），save 到 `backtests/<slug>/<run_id>/meta.yaml`

### 3.5 輸出
- `strategies/<slug>.py`
- `tests/test_<slug>.py`（≥ 3 個 case，全 pass）
- `backtests/<slug>/<run_id>/`：
  - `equity_curve.parquet`
  - `trades.parquet`
  - `metrics.json`
  - `param_heatmap.png`
  - `walk_forward.json`
  - `multi_asset.json`
  - `regime_breakdown.json`
  - `meta.yaml`（含 git commit、seed、N）

### 3.6 驗收
- pytest 全 pass
- Lookahead lint 0 warning
- `metrics.json` 包含 workflow.md 列嘅所有 metric
- `meta.yaml` 有 N、commit hash、data snapshot date

### 3.7 邊界（NOT 包含）
- ❌ 唔掂 OOS 數據（hard assert in code）
- ❌ 唔做 statistical test
- ❌ 唔出 verdict

---

## 4. `statistical-validator`

### 4.1 目的
解鎖 OOS，跑 Phase 6 全套（OOS replay + Monte Carlo + DSR + bootstrap p-value）。

### 4.2 必備工具
- `Read` — strategy code、in-sample backtest meta
- `Bash` — 跑 validation script
- `Write` — `validations/<slug>/<run_id>/`

### 4.3 輸入
- Strategy slug
- 對應嘅 in-sample run_id（用嚟攞 N、param、commit hash）

### 4.4 行為
1. **Guard**：assert in-sample 已完成 + 通過 Phase 5
2. **OOS replay**：用 in-sample 鎖定嘅 param，跑 2023-01-01 → 今日
3. **Monte Carlo A**：trade-order shuffle ×10,000，記錄 Max DD 分佈，計真實 DD 嘅 percentile
4. **Monte Carlo B**：bootstrap daily returns ×10,000，計 Sharpe 95% CI
5. **Random entry test**：1,000 次 random entry，計 p-value
6. **DSR**：用 Bailey/López de Prado 公式，input：SR、N、skew、kurt、T
7. **Paired t-test vs. buy-and-hold**

### 4.5 輸出
`validations/<slug>/<run_id>/`：
- `oos_metrics.json`
- `mc_drawdown.json`（含分佈、真實 percentile）
- `mc_sharpe_ci.json`
- `random_entry_pvalue.json`
- `dsr.json`
- `t_test_vs_bah.json`
- `summary.md`（pass/fail per criterion）

### 4.6 驗收
- 每個 criterion 都明確 pass / fail
- 所有 random number 都用 fixed seed（reproducible）
- 真實 OOS 期間嘅 data 喺 run 前確認未被 strategy code 接觸過（via git diff）

### 4.7 邊界（NOT 包含）
- ❌ 唔可以 re-tune param（如果 OOS fail 就 fail，唔回去 Phase 5）
- ❌ 唔出最終 verdict（係 Phase 7 嘅事）

---

## 5. `strategy-report`

### 5.1 目的
整合 Phase 4–6 嘅所有 output，按 workflow.md Phase 7 嘅格式出 markdown report，並決定 verdict。

### 5.2 必備工具
- `Read` — backtest + validation output
- `Write` — `reports/<YYYY-MM-DD>-<slug>.md`
- `Edit` — append 到 `decisions.md`

### 5.3 輸入
- Strategy slug
- In-sample run_id
- Validation run_id

### 5.4 行為
1. Collect 所有 metric 入一個 table（IS vs. OOS）
2. 對 workflow.md Phase 5/6 嘅每條 pass condition 逐項打勾
3. 按 GREEN/YELLOW/RED rule 決定 verdict
4. 寫 7 個 section（見 workflow.md Phase 7）
5. Append 一行入 `decisions.md`

### 5.5 輸出
- `reports/<YYYY-MM-DD>-<slug>.md`
- `decisions.md`（updated）

### 5.6 驗收
- 7 個 section 齊
- Verdict 同 pass condition 一致（無自相矛盾）
- 包含至少一個 caveat
- decisions.md 嘅新 row 同 report 嘅 verdict 一致

### 5.7 邊界（NOT 包含）
- ❌ 唔自己改 verdict 規則
- ❌ 唔幫 YELLOW 嘅 candidate 自動 retry

---

## 跨 Skill 嘅 contract

1. **檔案命名**：所有 artifact 用同一個 `<slug>`，方便 cross-reference
2. **Metadata**：每個 phase 嘅 output 都要有 `meta.yaml`，紀錄上游 run_id，可以追溯
3. **Git hygiene**：每個 phase 完成後 commit；report 完成後一定要 push
4. **錯誤處理**：如果上游 phase 嘅 artifact missing，下游 skill 必須**stop and ask**，唔好自己 regenerate

---

## 安全 & 範圍守則

- ❌ 唔接駁真實交易帳戶（呢套 system 純研究）
- ❌ 唔做 high-frequency / sub-second strategy（cost model 唔支持）
- ❌ 唔處理 private API key（如果要 live 行，係另一個 system）
- ✅ 只用 public market data
- ✅ 所有 web fetch 必須係 publicly readable URL
