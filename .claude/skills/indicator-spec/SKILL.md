---
name: indicator-spec
description: Convert a prose candidate description (from discovery markdown) into a schema-valid YAML spec file. Use when the user asks to "spec a candidate", "formalize", "convert to YAML", or promote a discovery card to Phase 2. Validates the formula references and parameter bounds before writing.
---

# indicator-spec

Phase 2 嘅 skill。將 discovery 入面嘅 candidate card → schema-valid `specs/<slug>.yaml`。

## 何時用

- discovery.md 已 ready，要 promote 某個 candidate
- 用戶手寫 prose 描述一個指標，想轉成 formal spec
- 要 revise 一個 existing spec（例如想擴大 param range）

## 流程

1. **讀來源 candidate card**
   - 由用戶指定路徑 + section header，或直接讀 prose
   - 如果 card 嘅描述太疏漏，用 `WebFetch` 再拉一次原始 source

2. **逐項 fill 落 schema**（schema 見 `docs/workflow.md` Phase 2）

   必填 sections：
   - `name`（kebab-case slug）
   - `version`（semver，新 spec 由 0.1.0 開始）
   - `source`（url / authors / retrieved date）
   - `hypothesis`（一段 prose，講 economic mechanism）
   - `data`（symbols / timeframe / fields / history_required）
   - `parameters`（每個都要有 type / default / range）
   - `formula`（LaTeX 或 reproducible Python expression）
   - `entry_logic`、`exit_logic`
   - `position_sizing`
   - `risk`（stop_loss_pct / take_profit_pct / max_concurrent_positions）

3. **檢查內部一致性**
   - `formula` 入面每個 symbol 都喺 `parameters` 或 `data.fields` 出現過？
   - 至少 1 個 parameter 有非 trivial range（唔係 default=1, range=[1,1]）？
   - `entry_logic` 同 `exit_logic` mutually exclusive？

4. **Schema validation**
   ```bash
   python -c "import yaml, jsonschema; s=yaml.safe_load(open('specs/<slug>.yaml')); jsonschema.validate(s, yaml.safe_load(open('specs/_schema.yaml')))"
   ```
   （如果 `_schema.yaml` 未存在，第一次跑時要 create）

5. **Write** 到 `specs/<slug>.yaml`

## 必要工具
- `Read`
- `WebFetch`（可選）
- `Write`
- `Bash`（schema validate）

## 唔做嘅嘢

- ❌ 唔生成 Python 實作 → 用 `backtest-runner`
- ❌ 唔做 sanity backtest
- ❌ 唔自己發明 parameter——必須來自 source 或 reasonable extrapolation

## 驗收 checklist

- [ ] YAML parse OK
- [ ] Schema validation pass
- [ ] formula 入面所有 symbol 都有定義
- [ ] 至少 1 個 param 有 non-trivial range
- [ ] source URL + authors 齊
- [ ] hypothesis 唔係 copy-paste prose，係用自己嘅話講

## 範例 prompt

```
讀 research/2026-05-18-discovery.md 嘅第 2 個 candidate (hawkes-vol-clustering)，
用 indicator-spec 轉成 YAML spec。Save 到 specs/hawkes-vol-clustering.yaml。
```
