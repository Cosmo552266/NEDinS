# 操作手冊（Handbook / SOP）

> 呢份係 day-to-day 操作 guide。Workflow 講 "what & why"，呢份講 "how & when"。

---

## 0. 開工前

每次新 session 開始：

```bash
# 確認喺正確 branch
git status

# 拉最新
git pull origin main

# 確認 data cache 未過期（> 7 日就要 refresh）
ls -lh data/ohlcv/
```

---

## 1. 每週循環（Weekly cadence）

| 星期 | 任務 | Skill |
|---|---|---|
| 一 | Discovery scan（搵 candidate） | `crypto-research` |
| 二 | Spec 化 shortlist 嘅 candidate | `indicator-spec` |
| 三 | Implementation + unit test | `backtest-runner` |
| 四 | In-sample backtest + robustness | `backtest-runner` |
| 五 | Statistical validation（OOS、MC、p-value） | `statistical-validator` |
| 六 | 寫 report、決定 verdict | `strategy-report` |
| 日 | Review、archive、計劃下週 | 人手 |

⚠️ **唔好趕 timeline**——如果 Phase 5 fail，唔好硬推上 Phase 6。

---

## 2. Skill 呼叫範例

### 2.1 Discovery

```
Claude，跑 crypto-research，搵呢個星期 arXiv + Quantpedia + Glassnode
有冇新嘅 mean-reversion 或 microstructure 指標可以喺 BTC perp 上用。
shortlist 5 個，每個出一個 candidate card。
```

### 2.2 Spec

```
Claude，攞 research/2026-05-18-discovery.md 入面第 2 個 candidate
（Hawkes volatility clustering），用 indicator-spec skill 轉成 YAML spec。
Save 到 specs/hawkes-vol.yaml。
```

### 2.3 Backtest

```
Claude，用 backtest-runner 跑 specs/hawkes-vol.yaml：
- in-sample period 跟 default
- 包括 Phase 5 嘅 4 項 robustness check
- 結果落 backtests/hawkes-vol/<timestamp>/
```

### 2.4 Validation

```
Claude，hawkes-vol 通過 Phase 5。
用 statistical-validator 跑 Phase 6 全套（OOS + MC + DSR）。
記得 Phase 5 我跑咗 N=42 個 param 組合，DSR 要用呢個數。
```

### 2.5 Report

```
Claude，用 strategy-report skill 整合 hawkes-vol 嘅所有結果，
寫成最終 report。Verdict 你自己決定（按 workflow.md 嘅 rule）。
```

---

## 3. 常見錯誤 & 避免方法

### 3.1 Lookahead bias（最致命）

❌ **錯**：
```python
df['zscore'] = (df['close'] - df['close'].mean()) / df['close'].std()
df['signal'] = (df['zscore'] < -2).astype(int)
```
（用咗 full-sample mean／std）

✅ **啱**：
```python
df['rolling_mean'] = df['close'].rolling(100).mean().shift(1)
df['rolling_std'] = df['close'].rolling(100).std().shift(1)
df['zscore'] = (df['close'].shift(1) - df['rolling_mean']) / df['rolling_std']
df['signal'] = (df['zscore'] < -2).astype(int)
```

### 3.2 Survivorship bias

❌ **錯**：用「而家 top 20 嘅 alt」back-test 三年前。
✅ **啱**：用 historical top-20 by market cap on each rebalance date。或者只 stick to BTC/ETH（無 survivorship 問題）。

### 3.3 Overfitting via repeated testing

❌ **錯**：Phase 5 grid search 跑 200 個 param 組合，揀最好嘅去 Phase 6。
✅ **啱**：用 walk-forward 揀 param，或者用 DSR 修正 trial 數。**N 必須誠實 log**。

### 3.4 偷睇 OOS

❌ **錯**：「我快快脆 sample 一下 OOS 睇下 reasonable 唔 reasonable...」
✅ **啱**：Phase 6 之前完全唔 load OOS data。可以喺 backtest engine 加 hard guard：

```python
if not phase_6_unlocked:
    assert df.index.max() <= pd.Timestamp(IN_SAMPLE_END)
```

### 3.5 Cost model 過於樂觀

❌ **錯**：用 maker fee 0% 假設所有 limit order 都 fill。
✅ **啱**：limit order 加 fill probability model；或者保守用 taker fee + 5 bps slippage。

### 3.6 唔記得 funding rate（perp）

❌ **錯**：用 BTC perp data 但用 spot cost model。
✅ **啱**：perp strategies 必須計 8h funding rate（historical funding 可以喺 Binance API 攞）。

---

## 4. Data hygiene

### 4.1 Sources

| Data | Source | API |
|---|---|---|
| Spot OHLCV | Binance (primary)、Coinbase (cross-check) | ccxt |
| Perp OHLCV + funding | Binance Futures、Bybit | ccxt |
| On-chain | Glassnode、CryptoQuant | REST |
| Order book L2 | Tardis.dev（historical） | REST |

### 4.2 Storage

- 全部 OHLCV save 做 parquet：`data/ohlcv/<exchange>/<symbol>/<timeframe>.parquet`
- 每星期跑一次 incremental update
- ⚠️ **唔好 commit 到 git**——已喺 `.gitignore`

### 4.3 Reproducibility

每個 backtest run 嘅 metadata 必須記錄：
```yaml
run_id: 2026-05-18T14:30:00Z
git_commit: a3f5e9b
data_snapshot: 2026-05-18
random_seed: 42
spec_file: specs/hawkes-vol.yaml
spec_version: 0.1.0
```

---

## 5. Code style

### 5.1 Backtest code

- 全部 vectorized（pandas + numpy），唔好 for-loop bar-by-bar 除非真係必要
- 一個策略一個檔，唔好 share state
- Type hints 必須
- 用 `pytest` 唔用 unittest

### 5.2 Naming

- Spec slug：`kebab-case`，例：`hawkes-vol-clustering`
- Strategy class：`PascalCase`，例：`HawkesVolClusteringStrategy`
- Param：`snake_case`

### 5.3 Logging

用 `loguru`，唔用 `print`。每個 phase 嘅 log 落到 `logs/<phase>/<run_id>.log`。

---

## 6. Decision log

每個 candidate 嘅 final verdict 都要記入 `decisions.md`：

```markdown
| Date | Candidate | Verdict | OOS Sharpe | DSR | Note |
|---|---|---|---|---|---|
| 2026-05-18 | hawkes-vol | 🟡 YELLOW | 0.8 | 0.4 | 邊緣，retry with longer kernel |
| 2026-05-11 | funding-rate-skew | 🟢 GREEN | 1.4 | 1.1 | paper trade started |
```

呢份 log 係**唯一 source of truth**——避免 "我覺得試過呢個" 嘅 confusion。

---

## 7. Live trading promotion（GREEN 之後）

呢份 handbook **唔覆蓋** live execution。但 GREEN candidate 之後嘅流程大致：

1. Paper trade 3 個月，每週對比 paper vs. backtest expected
2. 如果 paper Sharpe ≥ 0.6 × OOS Sharpe，可以細注 live（總 portfolio 1–2%）
3. Live 三個月再 review，先考慮 scale up
4. **Kill switch**：rolling 30-day Sharpe < 0 或 DD > 1.5× backtest max DD → halt

詳細 live ops 寫另一份 `docs/live-trading.md`（暫時 out of scope）。
