# Discovery — 2026-05-18

**Scan window**: 過去 ~12 個月（focused on 2026 publications）
**Skill**: `crypto-research`
**主題偏好**: BTC perp / funding-rate / on-chain mean-reversion
**排除清單**: 無（first run）

---

## Candidate: funding-rate-extreme-mr

- **來源**：
  - https://arxiv.org/abs/2506.08573 ("Designing funding rates for perpetual futures in cryptocurrency markets") | author n/a | 2025-06
  - https://arxiv.org/html/2605.06405 ("Funding-Aware Optimal Market Making for Perpetual DEXs") | author n/a | 2026
  - WebSearch synthesis: Binance ETHUSDT funding 嘅 Ornstein-Uhlenbeck half-life = 7.96h（2025-11 → 2026-05 calibration）
- **一句話描述**：當 perp funding rate 達 historical 95th percentile（BTC 通常 > 0.12% per 8h），預期短期 mean-revert，建立反向 perp 倉位（funding 正→short perp、funding 負→long perp），用 spot 對沖 delta。
- **假設**：Funding rate 反映槓桿 demand imbalance；extreme reading → liquidation cascade 後 demand reset → funding 回歸均值。OU half-life 量化呢個 reset 速度。
- **數據需求**：BTC/USDT:USDT perp OHLCV (1h)、funding_rate (每 8h)；可選 spot 對沖。Binance/Bybit ccxt 免費。
- **預期 edge 來源**：Microstructure mean-reversion + carry harvesting（funding payment 本身）
- **初步評分**：novelty=3 / clarity=5 / data=5 / theory=5
- **下一步**：✅ **PROMOTE** — 規則明確、數據易取、有 OU 模型作 theoretical backbone

---

## Candidate: ou-funding-zscore

- **來源**：同上 arxiv 2605.06405；輔以 WebSearch synthesis 提及 ETHUSDT funding OU half-life 7.96h
- **一句話描述**：對 funding rate fit OU process，計 instantaneous z-score = (funding_t - θ_t) / σ_t，當 |z| > 2 進入反向倉，z 回歸 ±0.5 時平倉。
- **假設**：比 percentile-based rule 更 adaptive，可以喺 funding regime 轉變時自動 re-calibrate（OU 參數 rolling estimate）。
- **數據需求**：funding_rate 歷史（≥ 1 年）；可加 ETHUSDT、SOLUSDT 做 cross-asset robustness。
- **預期 edge 來源**：同 funding-rate-extreme-mr 但加 adaptive normalization，理論上應該更 robust。
- **初步評分**：novelty=4 / clarity=4 / data=5 / theory=5
- **下一步**：✅ **PROMOTE** — 視為 funding-rate-extreme-mr 嘅 variant，可以後續再做。今次先做 simpler version。

---

## Candidate: mvrv-zscore-bottom-confluence

- **來源**：
  - https://insights.glassnode.com/sth-lth-sopr-mvrv/ | Glassnode Insights | undated
  - https://www.spotedcrypto.com/bitcoin-onchain-bottom-signals-march-2026/ | spotedcrypto | 2026-03-27
  - WebSearch synthesis 提及 5-indicator confluence：MVRV Z-Score < 1.2、aSOPR < 1.0、realized profit down 96%、hashrate −22%、exchange reserves 7-year low（only 3 historical occurrences：2015-end、2018-end、2022-mid，each preceded 300%+ rally within 18 months）
- **一句話描述**：5 個 on-chain bottom indicator 同時觸發 → 長期 BTC long entry，hold 18 個月或 trailing-stop。
- **假設**：On-chain capitulation 同 cycle bottom 高度相關（"smart money cost basis < market price" + "hash rate collapse signals miner capitulation"）。
- **數據需求**：Glassnode API（付費）或開源代理（NVT、circulating supply、realized cap）；BTC daily 已足夠。
- **預期 edge 來源**：Cycle-level mean reversion（非高頻）。Theoretical：miner-driven supply dynamics + holder behavior。
- **初步評分**：novelty=2 / clarity=4 / data=2 / theory=4
- **下一步**：🟡 **HOLD** — clarity OK 但只 3 次歷史事件，sample size 太細，DSR 一定 fail。如要 promote，要 expand 到其他 chain 或 lower-frequency variant。

---

## Candidate: hawkes-lob-return-sign

- **來源**：
  - https://link.springer.com/article/10.1007/s10203-026-00570-z | Springer DEF | 2026
  - https://arxiv.org/html/2312.16190v1 (Hawkes-based crypto forecasting via LOB) | 2023-12
- **一句話描述**：用 multivariate Hawkes process model BTC/USD LOB 各類 event（market buy、market sell、limit add/cancel），輸出 next-bar return sign forecast，搭配 COE pipeline。
- **假設**：Self-excitation 捕捉 order splitting，cross-excitation 捕捉 liquidity replenishment，從而預測 short-horizon directional move。
- **數據需求**：**Limit Order Book historical data**（Tardis.dev 付費，或 Kaiko）。OHLCV 不夠。
- **預期 edge 來源**：Microstructure，short horizon（秒至分鐘）。
- **初步評分**：novelty=5 / clarity=3 / data=1 / theory=5
- **下一步**：🔴 **REJECT for now** — data feasibility 太差（要 LOB data + sub-minute latency），同 workflow 嘅 cost model（5 bps slippage、無 LOB simulator）不匹配。Archive 到日後有 LOB infra 再 revisit。

---

## Rejected

| Slug | Reason |
|---|---|
| hawkes-lob-return-sign | 需要 LOB data + sub-minute infra，當前 cost model 唔支持 |
| momentum-fx-bitcoin-trend | super.so 嘅 PDF 403，無法 extract 具體 rule；而且 trend-following 喺 crypto 已 extensively studied，novelty 低 |

---

## Promote summary

| Slug | 評分（avg） | 下一步 |
|---|---|---|
| **funding-rate-extreme-mr** | **4.5** | → `indicator-spec` Phase 2 |
| ou-funding-zscore | 4.5 | hold；funding-rate-extreme-mr 跑完先做 |
| mvrv-zscore-bottom-confluence | 3.0 | hold；要 lower-frequency variant |

**Pick for Phase 2**：`funding-rate-extreme-mr`
- 數據成本最低（Binance API 免費）
- 規則最 deterministic（純 funding rate threshold）
- 有 OU theoretical foundation，可以 supports DSR multi-trial counting

---

## Methodological notes (run log)

- arxiv direct links 403 → 用 WebSearch 嘅 synthesis output
- Glassnode insights 403 → 同上
- GitHub repo `50shadesofgwei/funding-rate-arbitrage` 可訪問，extract 到 `DELTA_BOUND=0.03`、`TRADE_LEVERAGE=5`、`DEFAULT_TRADE_DURATION_HOURS=8` 作參數 prior
- 下次 run 建議改用 Twitter/X archive + Quantocracy aggregator（HTML 較簡單，403 機率低）
