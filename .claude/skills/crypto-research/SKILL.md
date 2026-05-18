---
name: crypto-research
description: Discover and shortlist candidate crypto trading indicators and theories from academic papers, industry blogs, and crypto-native research sources. Use when the user asks to "find candidates", "scan for new indicators", "discover", or runs a weekly research scan. Outputs a structured discovery markdown with 3-5 candidate cards.
---

# crypto-research

Phase 1 嘅 skill。喺 web 上搜尋加密貨幣交易嘅 indicator / theory candidate，shortlist 後出 discovery markdown。

## 何時用

- 用戶話「scan / 搵 candidate / discover / 揾新指標」
- 每週固定 research cycle 嘅第一步
- 已有 spec 但想搵 variant／替代理論

## 流程

1. **確定搜尋範圍**
   - Scan window：default 過去 7 日（如用戶有指定就用指定）
   - 主題：問用戶有冇 preference（mean-reversion / momentum / microstructure / on-chain / sentiment）
   - 排除清單：讀 `decisions.md` 入面過去 30 日做過嘅 candidate

2. **搵 sources**（按優先順序，每組至少 query 一次）：
   - **Academic**：`site:arxiv.org q-fin cryptocurrency <theme>`、`site:ssrn.com bitcoin <theme>`
   - **Industry**：QuantConnect blog、Quantpedia、Hudson & Thames、Robot Wealth
   - **Crypto-native**：Glassnode Insights、Coin Metrics SOTN、Kaiko Research
   - **社群**：r/algotrading top week、Quantocracy crypto tag

3. **WebFetch 拉內容**
   - 每個 hit 拉一次，extract 唔超過 500 token
   - 留意：published date、author、明確 entry/exit rule、可量化參數

4. **過濾**（每個 candidate 行 checklist，見 `docs/workflow.md` Phase 1）
   - ✅ 有明確 entry/exit rule
   - ✅ 用 OHLCV ± on-chain 可實作
   - ✅ 有 economic/behavioral mechanism
   - ✅ 可 generalize
   - ❌ 拒絕 pure fitting / 需要 insider data / sub-ms latency

5. **評分**（每項 1–5）：novelty、clarity、data feasibility、theoretical soundness

6. **寫 discovery.md** 到 `research/<YYYY-MM-DD>-discovery.md`，每個 candidate 一個 section：

```markdown
## Candidate: <slug>
- **來源**：<URL> | <作者> | <日期>
- **一句話描述**：...
- **假設**：...
- **數據需求**：...
- **預期 edge 來源**：...
- **初步評分**：novelty=X / clarity=X / data=X / theory=X
- **下一步**：promote / hold / reject + 理由
```

末尾加 `## Rejected` section log 拒絕嘅 candidate + 一句 reason。

## 必要工具
- `WebSearch`
- `WebFetch`
- `Write`
- `Read`（讀 decisions.md）

## 唔做嘅嘢

- ❌ 唔做 spec 化 → 用 `indicator-spec`
- ❌ 唔做 backtest → 用 `backtest-runner`
- ❌ 唔自己發明 indicator（必須 cite 來源）

## 驗收 checklist

行完之後 self-check：
- [ ] 至少 3 個 promoted candidate
- [ ] 所有 URL reachable
- [ ] 每個 card 有 hypothesis
- [ ] 至少 1 個 source 喺 7 日內
- [ ] Rejected section 有齊 reason
- [ ] 已 Write 到 `research/<date>-discovery.md`

## 範例 prompt

```
跑 crypto-research，scan 過去 7 日嘅 arXiv + Quantpedia + Glassnode，
focus 喺 BTC perp 嘅 mean-reversion 同 funding-rate 相關 idea。
排除 decisions.md 入面已做嘅。
```
