# NEDinS — 自動交易研究 Pipeline

由 Claude 驅動嘅加密貨幣交易策略研究工作流：自動上網搵 indicator / theory，spec 化，落實成代碼，再用嚴謹統計方法評測。

## 文件

| 文件 | 內容 |
|---|---|
| [`docs/workflow.md`](docs/workflow.md) | 端到端 pipeline、7 個 phase、verdict 規則 |
| [`docs/handbook.md`](docs/handbook.md) | 每日 / 每週操作 SOP、常見錯誤、data hygiene |
| [`docs/skill-requirements.md`](docs/skill-requirements.md) | 5 個 skill 嘅輸入 / 輸出 / 驗收條件 |

## Skills

`.claude/skills/` 下有 5 個 skill，對應 7 個 phase：

| Skill | Phase | 用途 |
|---|---|---|
| `crypto-research` | 1 | Web scan 出 candidate indicator |
| `indicator-spec` | 2 | Prose → YAML spec |
| `backtest-runner` | 3–5 | Codegen + in-sample + robustness |
| `statistical-validator` | 6 | OOS + Monte Carlo + DSR + p-value |
| `strategy-report` | 7 | 整合輸出 + verdict（🟢/🟡/🔴） |

## 目錄結構

```
NEDinS/
├── docs/                   # 規格 / SOP
├── .claude/skills/         # Claude Code skill 骨架
├── research/               # Phase 1 — discovery markdown
├── specs/                  # Phase 2 — YAML spec
├── strategies/             # Phase 3 — Python implementation
├── tests/                  # Phase 3 — pytest
├── backtests/              # Phase 4–5 — backtest output (gitignored)
├── validations/            # Phase 6 — validation output (gitignored)
├── reports/                # Phase 7 — final markdown report
├── decisions.md            # 所有 candidate verdict log
└── data/                   # OHLCV / on-chain cache (gitignored)
```

## 開始使用

開新 session 後，直接同 Claude 講：

```
跑 crypto-research，scan 過去 7 日嘅 arXiv + Glassnode，
focus 喺 BTC perp 嘅 mean-reversion idea。
```

Claude 會 load `crypto-research` skill，按 `docs/workflow.md` Phase 1 嘅 SOP 執行。

詳細用法見 [`docs/handbook.md`](docs/handbook.md)。

## 守則

- 🔒 OOS data 神聖不可侵犯 —— Phase 6 之前完全唔 load
- 📊 所有 verdict 跟 `workflow.md` 嘅 rule，唔自由發揮
- 📝 RED 嘅 candidate 一樣要寫 report，避免重複研究
- ♻️ 每個 backtest run 必須 commit hash + seed，可重現

## License

MIT — 見 [LICENSE](LICENSE)
