# 自動交易研究 Workflow

> **目標**：建立一條由 Claude 驅動嘅 pipeline，自動上網搜尋進階交易指標／理論，落實成可執行策略，再用嚴謹嘅統計方法評測係咪真係有 edge。
> **市場**：加密貨幣（BTC/ETH 及主流 alt，spot + perp）
> **執行者**：Claude Code（透過 `.claude/skills/` 內嘅 5 個 skill）

---

## 高層架構

```
┌──────────────────────────────────────────────────────────────────┐
│                    研究循環（每次跑一個 candidate）               │
└──────────────────────────────────────────────────────────────────┘

  ① Discovery        ② Spec            ③ Implementation
  crypto-research →  indicator-spec →  backtest-runner
       │                  │                   │
       │                  │                   ▼
       │                  │           ④ In-sample backtest
       │                  │                   │
       │                  │                   ▼
       │                  │           ⑤ Robustness checks
       │                  │                   │
       │                  │                   ▼
       │                  │           ⑥ Statistical validation
       │                  │              statistical-validator
       │                  │                   │
       │                  │                   ▼
       │                  │           ⑦ Final report
       │                  │              strategy-report
       │                  │                   │
       ▼                  ▼                   ▼
   research/         specs/              reports/
   *.md              *.yaml              *.md
```

每個 candidate（一個指標／策略）行一次完整 pipeline，最後 archive 喺 `reports/<date>-<slug>.md`，無論 pass 或 fail 都保留紀錄，避免重複研究。

---

## Phase 1 — Discovery（發現候選指標／理論）

**Skill**：`crypto-research`

**目的**：每星期 scan 一批新嘅指標、market microstructure 理論、alpha factor 論文，shortlist 出 3–5 個值得進一步測試嘅 candidate。

**搜尋來源（優先順序）**：

1. **學術**：arXiv (q-fin.TR, q-fin.ST)、SSRN、Journal of Finance、Journal of Financial Markets
2. **業界研究**：QuantConnect blog、Quantpedia、Hudson & Thames、Robot Wealth、Marcos López de Prado 著作衍生內容
3. **Crypto-native**：Glassnode Insights、Coin Metrics State of the Network、Kaiko Research、Amberdata、Messari Research
4. **社群**：r/algotrading、Quantocracy aggregator、Twitter/X 上 quant 帳號（@macrocephalopod、@therobotjames、@QuantStratTrader 等）、TradingView Editors' Picks
5. **GitHub**：awesome-quant、awesome-systematic-trading、freqtrade strategies、jesse-ai community strategies

**過濾準則**（candidate 必須通過）：

- ✅ 有明確、可量化嘅 entry／exit rule（唔係 vague 「buy the dip」）
- ✅ 可用 OHLCV +（可選）on-chain／order-book 數據實作
- ✅ 有清晰嘅 economic／behavioral hypothesis 解釋點解會有 edge
- ✅ 唔係過度依賴單一資產嘅 idiosyncrasy（要可以 generalize）
- ❌ 拒絕：純 fitting、無 mechanism、需要 insider data、要求 < 1ms latency

**輸出**：`research/<YYYY-MM-DD>-discovery.md`，每個 candidate 一個 section：

```markdown
## Candidate: <名稱>
- **來源**：<URL + 作者 + 日期>
- **一句話描述**：...
- **假設**：點解佢應該 work
- **數據需求**：OHLCV / on-chain / order-book / funding rate
- **預期 edge 來源**：mean reversion / momentum / microstructure / sentiment
- **初步評分**：novelty / clarity / data feasibility / theoretical soundness (each 1–5)
- **下一步**：promote to Phase 2 / hold / reject + 理由
```

---

## Phase 2 — Specification（規格化）

**Skill**：`indicator-spec`

**目的**：將 Phase 1 嘅 prose 描述，轉成電腦可執行嘅 formal spec。一個 spec 就係一份合同——之後 Phase 3 implementation 必須跟住 spec 寫。

**輸出**：`specs/<slug>.yaml`

```yaml
name: hawkes-volatility-clustering
version: 0.1.0
source:
  url: https://...
  authors: [...]
  retrieved: 2026-05-18
hypothesis: |
  波動率成簇出現遵循 Hawkes self-exciting process；
  當 conditional intensity λ(t) 超過閾值，短期 mean reversion 概率上升。
data:
  symbols: [BTC/USDT, ETH/USDT]
  timeframe: 1h
  fields: [open, high, low, close, volume]
  history_required: 365d
parameters:
  decay_kernel:
    type: float
    default: 0.8
    range: [0.3, 0.99]
  intensity_threshold:
    type: float
    default: 2.0
    range: [1.2, 4.0]
  holding_period:
    type: int
    default: 12     # bars
    range: [4, 48]
formula: |
  λ(t) = μ + Σ α·exp(-β(t-t_i))  for t_i < t
  signal = +1 if λ(t) > threshold and last_return < 0
  signal = -1 if λ(t) > threshold and last_return > 0
  exit = after holding_period bars or stop_loss hit
entry_logic: ...
exit_logic: ...
position_sizing: fixed_fraction(0.02)
risk: 
  stop_loss_pct: 0.03
  take_profit_pct: null
  max_concurrent_positions: 3
```

**驗收**：spec YAML 必須通過 schema 檢查；formula section 要有 reproducible 偽代碼。

---

## Phase 3 — Implementation（落實）

**Skill**：`backtest-runner`（包含 codegen sub-step）

**步驟**：

1. 讀 `specs/<slug>.yaml`
2. 生成 `strategies/<slug>.py`，包含：
   - `compute_indicator(df) -> pd.Series`
   - `generate_signals(df, params) -> pd.DataFrame[signal, size]`
   - 純 vectorized，禁止 lookahead（用 `shift(1)` 確保 t 時刻只用 t-1 及之前資料）
3. 寫 `tests/test_<slug>.py`：
   - 至少 3 個 known-input/known-output unit test（用 source 提供嘅例子或手算）
   - 用 fixed seed 同 deterministic data 確保可重現

**Lookahead bias 檢查清單**（每個策略 implementation 都要過）：

- [ ] 所有 signal 都用 `t-1` 嘅 close 計算？
- [ ] Entry price 用 `t` 嘅 open 而唔係 `t-1` 嘅 close？
- [ ] 任何 rolling stat 都加咗 `.shift(1)`？
- [ ] 無用 future-knowing 嘅 z-score（用 full-sample mean）？
- [ ] Resampling 用咗 `closed='right', label='right'`？

---

## Phase 4 — In-Sample Backtest

**Skill**：`backtest-runner`

**設定**：

- **In-sample window**：2018-01-01 → 2022-12-31（5 年，涵蓋一個完整 bull-bear cycle）
- **Out-of-sample window**：2023-01-01 → 今日（held out，Phase 6 之前**禁止觸碰**）
- **資產**：BTC/USDT 為 primary，ETH/USDT 為 secondary validation
- **Timeframe**：以 spec 指定為主；如未指定，default 1h
- **成本模型**：
  - Taker fee 0.05%（Binance VIP 0 級保守估計）
  - Slippage：market order 5 bps，limit order 0 bps（但要計 fill probability）
  - Funding rate：perp 倉位每 8 小時扣
- **資金**：起始 $100,000，position sizing 跟 spec（default fixed fraction 2%）

**輸出 metrics**：

| 類別 | Metrics |
|---|---|
| Return | CAGR、Total return、Monthly return 分佈 |
| Risk-adjusted | Sharpe、Sortino、Calmar、Information ratio |
| Drawdown | Max DD、Avg DD、DD duration、Recovery time |
| Trade stats | Win rate、Profit factor、Avg win/loss、Expectancy |
| Distribution | Skew、Kurtosis、Tail ratio |

⚠️ **單一 metric 唔可以做決策**——必須睇成個 dashboard。

---

## Phase 5 — Robustness Checks

**Skill**：`backtest-runner`（同 `statistical-validator` 之間）

呢一 step 嘅目的：確認個 strategy 唔係 fit 過 in-sample 嘅 noise。

### 5.1 Parameter sensitivity heatmap

對所有 `parameters` 做 grid search（in-sample only），畫 Sharpe heatmap。
**通過條件**：default param 周圍 ±30% 範圍內，Sharpe 唔可以跌超過 20%。
**Fail signal**：得個 narrow peak → overfit。

### 5.2 Walk-forward analysis

- 用 5×1 rolling window（5 年 train → 6 個月 test → roll forward 6 個月）
- In-sample period 內重複 8 次
- 比較 in-sample Sharpe 同 out-of-window Sharpe
- **通過條件**：median walk-forward Sharpe ≥ 0.7 × in-sample Sharpe

### 5.3 Multi-asset robustness

- 喺 BTC、ETH、SOL、BNB、XRP、ADA、AVAX 上各跑一次
- **通過條件**：至少 4/7 嘅 asset Sharpe > 1.0

### 5.4 Regime breakdown

切分 in-sample 為 bull（BTC > 200-day MA）／bear（BTC < 200-day MA）／chop，分別計 Sharpe。
**警示**：如果 Sharpe 完全集中喺單一 regime → 策略無 generalization。

---

## Phase 6 — Statistical Validation

**Skill**：`statistical-validator`

呢一 step 解鎖 out-of-sample window。**全程只可以跑一次**——如果跑完發覺要 tune，就要重新搜集新 OOS data。

### 6.1 Out-of-sample test

- 直接 apply Phase 3 implementation（**禁止重新 tune parameter**）到 2023-01-01 → 今日嘅資料
- 報 OOS 嘅完整 metrics dashboard
- **通過條件**：OOS Sharpe ≥ 0.5 × in-sample Sharpe **且** OOS Sharpe > 0.5（絕對值）

### 6.2 Monte Carlo simulations

跑兩種 MC：

**(A) Trade-order shuffle**（測 drawdown 嘅 path-dependence）
- 攞晒所有 trade 嘅 PnL，隨機重排 10,000 次
- 計每次嘅 Max DD
- 真實 Max DD 應該落喺分佈嘅 median 附近——如果落喺 5th percentile，表示而家個 equity curve 係特別好彩。

**(B) Bootstrap returns**（測 Sharpe 嘅 CI）
- 從 daily returns sample with replacement 10,000 次
- 計每次 Sharpe
- 報 95% CI——**CI 下界必須 > 0** 先算 robust

### 6.3 Statistical significance

**(A) Bootstrap p-value vs. random entry**
- 用同樣嘅 holding period 但隨機 entry，跑 1,000 次
- 計策略 Sharpe 喺 random 分佈嘅 percentile
- **通過條件**：p < 0.05（即策略 Sharpe > random 嘅 95th percentile）

**(B) Deflated Sharpe Ratio**（Bailey & López de Prado, 2014）
- 修正 multiple testing bias：DSR = SR × adjustment(N_trials, skew, kurtosis)
- 必須記錄 Phase 5 grid search 嘅 trial 數 N
- **通過條件**：DSR > 0 且對應 p-value < 0.05

**(C) Whitened test vs. buy-and-hold**
- Paired t-test：strategy daily return − buy_and_hold daily return
- **通過條件**：t-stat 顯著為正（α = 0.05）

---

## Phase 7 — Final Report & Decision

**Skill**：`strategy-report`

**輸出**：`reports/<YYYY-MM-DD>-<slug>.md`

包含 sections：

1. **Hypothesis** — 一段話講清楚 economic mechanism
2. **Method** — 數據、period、costs、parameter
3. **Results summary** — 一個 metric table（IS / OOS / 差距）
4. **Robustness** — Phase 5 嘅 4 項結果
5. **Statistical validation** — Phase 6 嘅 3 項結果連 p-value
6. **Caveats** — known limitations、live trading 嘅 risk
7. **Verdict** — `GREEN` / `YELLOW` / `RED`

**Verdict 規則**：

| Verdict | 條件 |
|---|---|
| 🟢 GREEN | 通過所有 Phase 5 + Phase 6 條件；建議 paper trade 3 個月再考慮 live |
| 🟡 YELLOW | 通過 ≥ 80% 條件但有 1–2 項邊緣；建議改 spec 後重新跑 |
| 🔴 RED | OOS fail 或 DSR ≤ 0 或 CI 包含 0；archive 後 move on |

⚠️ **YELLOW 嘅 candidate 唔可以無限 retry**——同一個指標連續兩次 YELLOW 就要 RED。

---

## 守則（Non-negotiable）

1. **OOS 神聖不可侵犯**：Phase 6 之前無論 debug 幾耐都唔可以睇 OOS 數據。如果意外睇咗，要 reset OOS window 至更近期。
2. **Param trial 全部記錄**：Phase 5 grid search 每個組合都要 log，因為 Phase 6 嘅 DSR 要用 N。
3. **Report 包含 RED**：fail 嘅 strategy 一樣要寫 report——避免日後重複研究。
4. **代碼可重現**：每個 backtest run 要 commit hash + random seed + data snapshot date。
5. **唔好混淆 indicator 同 strategy**：indicator 係訊號，strategy 係 indicator + 倉位管理 + 風險控制。Spec 必須同時定義兩者。

---

## 目錄結構

```
NEDinS/
├── docs/
│   ├── workflow.md         # 本文件
│   ├── handbook.md         # 操作 SOP
│   └── skill-requirements.md
├── .claude/
│   └── skills/
│       ├── crypto-research/SKILL.md
│       ├── indicator-spec/SKILL.md
│       ├── backtest-runner/SKILL.md
│       ├── statistical-validator/SKILL.md
│       └── strategy-report/SKILL.md
├── research/               # Phase 1 輸出
├── specs/                  # Phase 2 輸出（YAML）
├── strategies/             # Phase 3 輸出（Python）
├── tests/                  # Phase 3 unit tests
├── backtests/              # Phase 4–5 raw output（json/parquet）
├── reports/                # Phase 7 最終報告（md）
└── data/                   # OHLCV / on-chain cache（gitignored）
```
