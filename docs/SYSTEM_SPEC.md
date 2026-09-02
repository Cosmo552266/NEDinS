# Nedkins Bybit 自動交易情報及執行系統 — 系統概念規格書

**版本**：v1.0 Draft（概念整理版）
**日期**：2026-09-02
**狀態**：概念規格，非 Live 授權文件
**權威來源**：本文件係對 Notion Project Hub、Production Readiness Roadmap、Capital-linked Risk Policy 及 1x/3x/5x Leverage Ladder 決定嘅綜合整理。如有衝突，以 Notion 已批准決定及 Git 內已 Release 嘅 Strategy Version 為準。

---

## 0. 點樣閱讀本文件

### 0.1 目的

呢份文件將整套系統嘅概念、規則、邊界、流程同狀態，用一個連貫嘅結構寫低，目的係：

1. 令任何人（包括未來嘅自己、Reviewer、AI Assistant）可以喺唔睇 Code 嘅情況下理解系統「應該」點運作；
2. 令每一條規則都有明確嘅「來源」同「狀態」（已確認 / 候選 / 建議）；
3. 成為日後 Strategy Version、Release Approval、Incident Post-mortem 嘅對照基準；
4. 令「系統絕對唔會做嘅事」變成可以審計嘅承諾，而唔係口頭原則。

### 0.2 規則狀態標籤

本文件每條重要規則都會標示其中一個狀態：

| 標籤 | 意思 |
|---|---|
| **[已確認]** | 已經喺 Notion 記錄為正式決定，或已有通過測試嘅實作 |
| **[候選]** | 已有方向，但具體參數或細則仲未正式批准 |
| **[建議]** | 本文件整理時補充嘅設計建議，未經批准，只作討論起點 |

任何 **[建議]** 都唔可以直接當成系統規則實施，必須先經人工審批並記錄。

### 0.3 術語表

| 術語 | 定義 |
|---|---|
| **Cycle** | Scanner 一次完整運行：由健康檢查開始，到輸出 `NO TRADE` 或一個候選 Setup 為止 |
| **Regime** | BTC 4H 市場環境分類（見 §5） |
| **Universe** | 當前 Cycle 合資格分析嘅 Bybit USDT Linear Perpetual 集合 |
| **Candidate** | 通過全市場掃描後，被選入深入分析嘅幣（最多 3 個） |
| **Setup** | 一個完整、可執行嘅交易計劃（方向、觸發、入場、止損、目標、失效條件） |
| **Signal** | 一個 Setup 加上其評分及證據，係決策紀錄嘅單位，唔一定會變成 Order |
| **Trade Intent** | 系統決定嘗試執行嘅交易意圖，已寫入 SQLite，仲未發送到 Bybit |
| **Order** | 已發送到 Bybit 嘅訂單請求，有唯一 `orderLinkId` |
| **Fill** | Bybit 私人資料流或 Reconciliation 確認嘅真實成交 |
| **Position** | Bybit 確認存在嘅真實倉位 |
| **Protection** | 交易所側止損（Exchange-side Stop），已由 Bybit 確認存在並覆蓋整個倉位 |
| **Authoritative Settled Strategy Equity** | 可用作風險計算嘅本金定義（見 §13.2） |
| **Qualified Stage Equity** | 當前已批准嘅資本階段上限（見 §22） |
| **Sydney Trading Day** | 以 Australia/Sydney 時區計算嘅交易日，用作每日損失預算重置邊界 |
| **SAFE_MANAGEMENT** | 系統狀態：停止新交易，但繼續優先保護及管理現有倉位 |
| **Circuit Breaker** | 觸發即阻止新倉嘅條件（見 §20） |
| **Outbox** | 本地待同步到 Notion 嘅事件隊列，必須 Idempotent |
| **Reconciliation** | 將本地狀態與 Bybit 真實狀態對比並修正差異嘅程序 |
| **Strategy Version** | 一組完整嘅入場 / 離場 / 風險 / 評分規則，對應特定 Git Commit 及 Notion Registry 紀錄 |
| **Release** | 一個獲批准可以喺特定 Mode 運行嘅 Artifact，附帶 Digest、Symbol Allowlist、Risk Limit 及有效期 |

---

## 1. 系統定位與核心哲學

### 1.1 一句話定義

> 一套以 BTC 大市為先、用客觀數據掃描 Bybit USDT 永續合約、只選擇最高質素 Long 或 Short 機會、以固定 1% 本金風險及波動調整 1x／3x／5x 槓桿、確認真實成交及交易所止損、持續監控持倉、將所有決定寫入 Notion，並透過版本化實驗持續改善但永不自行修改 Live 策略嘅安全型自動交易作業系統。

### 1.2 系統係咩、唔係咩

| 系統 **係** | 系統 **唔係** |
|---|---|
| 一套持續運作嘅交易情報 + 執行 + 審計作業系統 | 一個「見訊號就落單」嘅普通 Trading Bot |
| 以「唔交易」為預設結果嘅篩選器 | 一個每日必須產生交易嘅機器 |
| 由確定性程式控制風險、由 AI 輔助分析嘅系統 | 由 AI 自由決定倉位嘅系統 |
| 以真實 Fill 及交易所止損為權威嘅執行層 | 以「API 接受請求」為成功標準嘅執行層 |
| 一個每個決定都有紀錄、可回溯、可審計嘅系統 | 一個只記錄成功交易嘅日誌 |
| 以人工審批為策略演進閘門嘅學習系統 | 一個會自我修改 Live 策略嘅「自學習」系統 |

### 1.3 七大核心原則 [已確認]

1. **`NO TRADE` 係正常結果**。多數 Cycle 應該以 `NO TRADE` 結束。
2. **高分訊號唔代表一定落單**。分數只係入場資格之一，所有風險及執行閘門仍然要通過。
3. **槓桿唔等於可以承受更大損失**。槓桿只改變鎖住嘅 Margin，唔改變每單容許損失。
4. **API 接受 Order Request 唔代表已成交**。`ORDER_ACCEPTED ≠ FILLED`。
5. **AI 可以分析同解釋，但唔可以任意決定倉位或推翻風險規則**。
6. **系統唔會因為 Paper／Testnet 成功就自動轉成 Live**。Mode 提升永遠係人工決定。
7. **每一個決定、拒絕、下單、成交、保護、離場同事故都要有紀錄**。

### 1.4 設計優先次序

當規則之間有衝突，優先次序如下（高 → 低）：

1. **資本安全**（唔可以有裸露倉位、唔可以超過損失預算）
2. **狀態真確**（本地紀錄必須同 Bybit 真實狀態一致，否則停止）
3. **可審計性**（所有決定有證據、有時間、有版本）
4. **一致性**（相同輸入必須產生相同決定）
5. **機會捕捉**（喺以上全部滿足後，先考慮盈利機會）

即係：寧願錯過一個好機會，唔可以為咗捕捉機會而犧牲上面任何一項。

---

## 2. 系統架構總覽

### 2.1 主要模組

```text
┌─────────────────────────────────────────────────────────────────┐
│                        Operator Interface                        │
│   (Mode 切換 / Pause / Kill Switch / Approval / Manual Takeover)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                       Scheduler / Runtime                        │
│   • Scanner Cycle (~1h)   • Position Monitor (高頻)              │
│   • Maintenance / Backup  • Notion Outbox Worker                 │
└───┬───────────────┬──────────────────┬──────────────────┬───────┘
    │               │                  │                  │
┌───▼────┐   ┌──────▼──────┐   ┌───────▼────────┐  ┌──────▼──────┐
│ Market │   │  Analysis   │   │   Risk &       │  │  Execution  │
│  Data  │──▶│  Pipeline   │──▶│   Sizing       │─▶│   Gateway   │
│ Layer  │   │             │   │  (Determin.)   │  │             │
└───┬────┘   └──────┬──────┘   └───────┬────────┘  └──────┬──────┘
    │               │                  │                  │
    │        ┌──────▼──────┐           │           ┌──────▼──────┐
    │        │  AI / LLM   │           │           │  Position   │
    │        │  Critic     │           │           │  Monitor    │
    │        └─────────────┘           │           └──────┬──────┘
    │                                  │                  │
┌───▼──────────────────────────────────▼──────────────────▼───────┐
│                    SQLite (Local Truth)                          │
│   intents / orders / fills / positions / events / incidents      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Outbox (idempotent)
┌──────────────────────────▼──────────────────────────────────────┐
│                    Notion (Human Memory)                         │
│   7 databases: Signal / Trade / Strategy / Daily / Weekly /      │
│                Experiments / Incidents                           │
└─────────────────────────────────────────────────────────────────┘

External:  Bybit Public API ──▶ Market Data Layer
           Bybit Private REST/WS ◀─▶ Execution Gateway / Position Monitor
           Git / GitHub ◀─▶ Strategy Version / Release Artifacts
```

### 2.2 模組職責一覽

| 模組 | 職責 | 權威性 |
|---|---|---|
| **Market Data Layer** | 讀取 Bybit Public API（Kline、Ticker、Funding、OI、Orderbook、Instrument），做資料完整性及新鮮度檢查 | 市場事實嘅唯一入口 |
| **Analysis Pipeline** | BTC Regime → Universe → Scan → Rank → Candidate → 4H/1H 分析 → Score → Setup | 決定「有冇機會」 |
| **AI / LLM Critic** | 對候選 Setup 做矛盾證據檢查、解釋、總結；**唔可以**改變風險數字 | 只有否決建議權，冇擴權 |
| **Risk & Sizing** | 用固定公式計算 Risk Amount、Quantity、Leverage；檢查所有閘門 | 純確定性程式，AI 不可修改 |
| **Execution Gateway** | 產生 Idempotent Order、發送、確認 Fill、建立 Protection、Reconcile | 唯一可以觸碰 Bybit Private API 嘅模組 |
| **Position Monitor** | 持倉存在時嘅獨立守護：Stop Coverage、Liquidation Distance、狀態差異 | 優先權高於 Scanner |
| **SQLite** | 所有本地意圖、決定、事件、狀態嘅權威紀錄 | 系統操作真相 |
| **Notion Outbox** | 將 SQLite 事件以 Idempotent 方式同步到 Notion | 唔係執行權威 |
| **Operator Interface** | 人類最高控制權入口 | 最終權威 |

### 2.3 完整運作流程 [已確認]

```text
 1. 時間／資料健康檢查
 2. BTC 4H 市場環境判斷（Regime）
 3. 讀取 Bybit USDT Perpetual 市場名單（Instrument Info）
 4. 流動性、價差、深度、上市時間篩選 → Universe
 5. 全市場客觀數值掃描
 6. 最強／最弱資產排名（TOP STRONG / TOP WEAK）
 7. 選出最多 3 個候選幣
 8. 4H 趨勢與結構分析
 9. 1H Setup 與確認
10. 分開計算 LONG_SCORE／SHORT_SCORE
11. 選擇最高質素機會（或 NO TRADE）
12. Critic／矛盾證據檢查
13. 確定入場、止損、目標、R:R
14. 固定公式風險與倉位計算
15. 執行安全閘門（全部通過先可以繼續）
16. 按 Mode 執行：PAPER／TESTNET／LIVE
17. 成交確認與保護單驗證
18. 獨立持倉監控（直至完全平倉）
19. 寫入 Notion Journal
20. 每日／每週績效分析
21. 提出策略改良實驗
22. 人工審批新策略版本
```

流程中任何一步失敗，結果都係 `NO TRADE`（如無倉位）或 `SAFE_MANAGEMENT`（如有倉位），唔會跳步。

---

## 3. 時間、排程與資料健康

### 3.1 時間權威 [已確認]

- 所有市場分析以 **Bybit Server Time** 為準，唔用本機時鐘判斷 Candle 是否收市。
- 本機時鐘與 Bybit Server Time 偏差超過閾值 → Circuit Breaker（見 §20）。
- 每日損失預算以 **Sydney Trading Day** 重置（Australia/Sydney 時區，自動處理夏令時間）。

**[建議]** 時鐘偏差閾值：> 2 秒警告，> 5 秒阻止新倉。實際數值需經審批。

### 3.2 Candle 確認規則 [已確認]

- **未完成嘅 1H Candle 唔可以當成已確認突破。**
- 所有 Candle-dependent Signal 必須使用**已確認收市**嘅 Candle。
- 判斷「已收市」：`candle_open_time + interval ≤ bybit_server_time`，並且 Bybit 已返回該 Candle 為 `confirm=true`（或等效欄位）。
- 4H 及 1H 都適用；15m 未來加入時同樣適用。

### 3.3 排程頻率 [已確認]

| 任務 | 頻率 | 備註 |
|---|---|---|
| 全市場 Scanner Cycle | 約每小時一次 | 對齊 1H Candle 收市後執行 |
| Position Monitor | 明顯比 Scanner 頻密 | 有倉位時必須運行；具體秒數為 [候選] |
| Notion Outbox Worker | 持續 / 短間隔 | 唔阻塞交易流程 |
| Backup / Maintenance | 每日 | 包括 SQLite Integrity Check |
| Daily Performance | 每個 Sydney Trading Day 結束後 | |
| Weekly Review | 每週 | 產生建議，唔自動實施 |

**[已確認]** 交易所保護止損唔可以等下一次 AI 分析先處理——Protection 係由 Execution Gateway 即時建立，唔依賴 Scanner 週期。

### 3.4 資料健康檢查（每 Cycle 開始）[已確認]

Cycle 開始前必須通過：

- Bybit Public API 可達，回應時間正常；
- Server Time 可讀，本機偏差在閾值內；
- BTC 4H 及 1H Kline 數量足夠，最新 Candle 已確認；
- Instrument Info 可讀且非空；
- SQLite Integrity Check 通過；
- 上一個 Cycle 已正確結束（冇殘留 Lock、冇未處理 Incident）；
- 如有持倉，Private WebSocket 狀態健康。

任何一項失敗 → 該 Cycle 直接輸出 `NO TRADE (DATA_HEALTH_FAILED)`，並記錄原因。

### 3.5 資料新鮮度 [建議]

| 資料 | 最大容許陳舊時間 |
|---|---|
| Ticker / Mark Price | 10 秒 |
| Orderbook Snapshot | 5 秒 |
| Funding Rate | 1 個 Funding 週期 |
| Open Interest | 5 分鐘 |
| Kline（已確認） | 1 個 Interval |

超過閾值 → 該資料標記 `STALE`，依賴該資料嘅 Score Component 設為不可用，整體 Data Quality 降級。

---

## 4. 市場資料層

### 4.1 資料來源 [已確認]

| 資料 | 端點類型 | 用途 |
|---|---|---|
| Instrument Info | Public REST | Universe 建構、Tick Size、Qty Step、Min/Max Qty、Leverage Range |
| Kline（1H / 4H / 15m） | Public REST | 趨勢、結構、指標 |
| Ticker（Last / Mark / Index / Bid1 / Ask1 / 24h Turnover） | Public REST / WS | 流動性、Spread、價格 |
| Funding Rate（當前 + 歷史） | Public REST | Funding Context |
| Open Interest（當前 + 歷史） | Public REST | OI Change、Price/OI Divergence |
| Orderbook Depth | Public REST / WS | 深度、執行質素 |
| Server Time | Public REST | 時間權威 |

### 4.2 資料品質標記 [已確認方向，細節建議]

每份用於決策嘅資料集都附帶 Data Quality 標記，並保存喺 Signal 紀錄：

| 等級 | 意思 | 對交易嘅影響 |
|---|---|---|
| `COMPLETE` | 所有欄位齊全、新鮮、已確認 | 可以正常評分 |
| `DEGRADED` | 部分非關鍵資料缺失或陳舊 | 相關 Component 降分，整體上限降低 |
| `INSUFFICIENT` | 關鍵資料缺失（例如 Candle 不足、Instrument 不可讀） | 該幣 `NO TRADE` |
| `SUSPECT` | 偵測到異常（價格跳空、Volume 為零、Timestamp 錯亂） | 該幣排除，記錄 Incident（低嚴重性） |

### 4.3 歷史資料要求 [建議]

- 4H 分析最少需要 200 支已確認 Candle（支援 EMA 200）；
- 1H 分析最少需要 300 支已確認 Candle；
- 少於要求 → 該幣標記 `INSUFFICIENT_HISTORY`，排除出 Universe。

---

## 5. BTC Regime Engine

### 5.1 目的 [已確認]

每次分析先判斷 BTC，因為 BTC 影響大部分山寨幣嘅方向、波動同流動性。Regime 唔係一個交易訊號，係一個**環境濾網**，用嚟調整候選 Setup 嘅分數同要求。

### 5.2 分類 [已確認]

```text
STRONG_BULL
BULL
NEUTRAL
BEAR
STRONG_BEAR
HIGH_VOLATILITY_UNCERTAIN
```

### 5.3 判斷證據 [已確認]

全部基於 **BTC 4H 已確認 Candle**：

| 類別 | 指標 |
|---|---|
| 結構 | Higher High／Higher Low；Lower High／Lower Low；最近 Swing Structure |
| 均線 | EMA 15／34／111；EMA 50／200；價格與均線相對位置及排列 |
| 動量 | RSI(14)；MACD（線、訊號、柱） |
| 趨勢強度 | ADX；+DI／−DI |
| 波動 | ATR；波動擴張／收縮 |
| 成交量 | 成交量趨勢、放量／縮量 |
| 位置 | 主要支持及阻力 |

### 5.4 判斷原則 [已確認]

- **唔會由單一指標決定 Regime**。必須多個類別證據一致先可以判定為 `STRONG_*`。
- 證據互相矛盾（例如結構向上但動量急速轉弱、ATR 急升）→ `HIGH_VOLATILITY_UNCERTAIN` 或 `NEUTRAL`。
- Regime 判定連同所有輸入指標值一併保存，唔只保存結果標籤。

### 5.5 Regime 對候選嘅影響 [已確認]

| Regime | 對 Altcoin Long | 對 Altcoin Short |
|---|---|---|
| `STRONG_BULL` | 結構強嘅 Long Setup 得到額外支持 | 逆勢，需要更高分數、更明確確認、更好入場位置 |
| `BULL` | 輕微支持 | 輕微扣分 |
| `NEUTRAL` | 中性，靠個別幣結構 | 中性，靠個別幣結構 |
| `BEAR` | 輕微扣分 | 輕微支持 |
| `STRONG_BEAR` | 逆勢，需要更高分數 | 結構弱嘅 Short Setup 得到額外支持 |
| `HIGH_VOLATILITY_UNCERTAIN` | 整體分數上限降低；**[建議]** 或直接 `NO TRADE` | 同左 |

**[建議]** `HIGH_VOLATILITY_UNCERTAIN` 期間預設 `NO TRADE`，除非 Strategy Version 明確定義例外規則。

---

## 6. Market Universe 建構

### 6.1 原則 [已確認]

- 主要市場係 **Bybit USDT Linear Perpetual**。
- 每次 Cycle 重新讀取 Bybit Instrument 資料，**唔依賴永久硬編碼幣種名單**。
- 流動性門檻**唔應該永遠固定一個數字**，而係參考當時整個市場分布（例如百分位數）。

### 6.2 排除或大幅扣分條件 [已確認]

| 條件 | 處理 |
|---|---|
| 成交額太低 | 排除 |
| 買賣差價太闊 | 排除或扣分 |
| Orderbook 深度不足 | 排除或扣分 |
| 上市時間太短 | 排除 |
| 歷史 Candle 不足 | 排除 |
| 異常價格或異常交易環境 | 排除，記錄 |
| 帳戶不可交易嘅 Instrument | 排除 |
| Tick Size／Qty Step／Min Qty 無法安全滿足 | 排除 |
| 最低合法訂單會超過風險預算 | 排除 |
| Instrument 狀態非 `Trading` | 排除 |

### 6.3 動態門檻 [建議]

- 24h Turnover：保留 Universe 中位數以上，或最少 Top 40%；
- Spread：排除高於 Universe 第 80 百分位；
- 上市時間：最少 30 日；
- 每次排除都記錄**具體原因碼**（例如 `EXCLUDED_LOW_TURNOVER`, `EXCLUDED_NEW_LISTING`），方便日後分析是否過嚴或過鬆。

### 6.4 最低訂單可行性預檢 [已確認]

喺 Universe 階段就用**當前 Base Risk** 及每個 Instrument 嘅 Min Qty / Min Notional 做一次粗略檢查：如果以合理止損距離計算，最低合法訂單已經超過 Base Risk，該 Instrument 直接排除，唔浪費分析資源。

---

## 7. 全市場掃描與排名

### 7.1 計算特徵 [已確認]

對每個 Universe 成員計算：

**價格與相對強弱**
- 1H、4H、24H Return
- 相對 BTC 強弱（Return 差、Beta-adjusted Return）

**成交量**
- 成交量水平及 Volume Acceleration

**波動**
- ATR 及 ATR Expansion
- Squeeze／Volatility Expansion 狀態

**動量與趨勢**
- RSI
- MACD
- ADX／DI
- EMA 結構（排列、斜率）
- 距離均線幅度（過度延伸偵測）

**衍生品 Context**
- Funding Rate 及 Funding 異常（相對自身歷史及 Universe 分布）
- Open Interest 及 OI Change
- Price／OI Divergence

**結構事件**
- Breakout／Breakdown
- Failed Breakout／Failed Breakdown
- Support／Resistance 距離
- Market Structure（HH/HL/LH/LL）

**執行質素**
- Spread（bps）
- Orderbook Depth（指定 Notional 內嘅滑點估算）

### 7.2 排名輸出 [已確認]

系統分開建立兩個榜：

- `TOP STRONG`：相對強勢、結構向上、有 Long 潛力
- `TOP WEAK`：相對弱勢、結構向下、有 Short 潛力

然後合併選出**最多 3 個候選**。

### 7.3 候選選擇邏輯 [建議]

- 每個榜各取最多 2 個，合併後按綜合分數截取 3 個；
- Regime 為 `STRONG_BULL` 時偏向 `TOP STRONG`；`STRONG_BEAR` 時偏向 `TOP WEAK`；
- 同一 Sector（例如同屬 L2、同屬 Meme）唔取超過 1 個，減低相關性；
- 已有持倉嘅 Symbol 唔會再成為候選（因為 Max Position = 1，其實整個 Scanner 都唔會發出 Entry）。

### 7.4 AI 嘅角色邊界 [已確認]

- 大量幣種嘅初步篩選**由程式完成**，唔會逐隻交畀 LLM 自由判斷。
- AI 只集中處理**經數值篩選後嘅候選**（最多 3 個）。
- AI 唔可以將被 Scanner 排除嘅幣「撈返」入候選。

---

## 8. 多週期結構分析

### 8.1 週期職責 [已確認]

| 週期 | 職責 | 邊界 |
|---|---|---|
| **4H** | 判斷趨勢、結構、Regime；決定「可以做邊個方向」 | 決定方向偏好 |
| **1H** | 尋找 Setup、確認突破／回調／拒絕、入場條件 | 決定「幾時入」 |
| **15m** | 未來可用作改善入場位置 | **唔可以推翻 4H 結構** |

### 8.2 4H 分析輸出 [已確認方向]

對每個候選：

- 趨勢方向（Up／Down／Range）
- Market Structure 標籤（HH-HL／LH-LL／Mixed）
- 最近 Swing High／Low 位置
- 主要支持／阻力區
- EMA 排列及價格相對位置
- ADX 趨勢強度
- 過度延伸程度（距離 EMA 嘅 ATR 倍數）

### 8.3 1H 分析輸出 [已確認方向]

- 當前 Setup Type（見 §9）
- Trigger 是否已發生（已確認 Candle）
- Confirmation 是否滿足（例如收市於關鍵位之上／下、成交量確認）
- Entry Zone
- 結構性 Stop 位置
- Invalidation 條件

### 8.4 週期一致性規則 [已確認]

- 1H Setup 方向必須與 4H 結構方向一致，或屬於明確定義嘅逆勢 Setup 類型（需要更高分數）。
- 4H 結構為 Range 時，只接受 Range 邊界反應類 Setup，唔接受趨勢延續類 Setup。

---

## 9. Setup 分類與定義

### 9.1 偏好嘅 Setup 類型 [已確認]

| Setup Type | 描述 | 典型 Trigger | 典型 Invalidation |
|---|---|---|---|
| `BREAKOUT_RETEST_CONTINUATION` | 突破阻力 → 回測 → 延續 | 1H 收市重新企穩於突破位之上 | 1H 收市跌返突破位之下 |
| `BREAKDOWN_RETEST_REJECTION` | 跌穿支持 → 反彈回測 → 拒絕 | 1H 收市重新跌穿回測位 | 1H 收市升返支持位之上 |
| `TREND_PULLBACK_CONFIRMATION` | 趨勢中回調至結構／均線 → 確認 | 1H 出現拒絕 Candle 並收市於回調區之外 | 跌穿回調區低點（Long）／升穿高點（Short） |
| `FAILED_BREAKOUT` | 突破後迅速收返關鍵位之下 | 1H 收市確認回落 | 重新突破並企穩 |
| `FAILED_BREAKDOWN` | 跌穿後迅速收返關鍵位之上 | 1H 收市確認回升 | 重新跌穿並企穩 |
| `RELATIVE_STRENGTH_CONTINUATION` | BTC 弱但目標幣強，結構延續 | 1H 結構延續確認 | 相對強弱逆轉 |
| `RELATIVE_WEAKNESS_CONTINUATION` | BTC 強但目標幣弱，結構延續 | 1H 結構延續確認 | 相對強弱逆轉 |
| `KEY_LEVEL_REACTION` | 關鍵支持／阻力有明確反應 | 1H 拒絕 Candle + 成交量 | 收市穿越關鍵位 |
| `PRICE_VOLUME_OI_ALIGNED_CONTINUATION` | 價格、成交量、OI 同向延續 | 三者同步確認 | 任何一項明顯背離 |

### 9.2 明確避免嘅行為 [已確認]

系統**唔會**因為以下理由建立 Setup：

- RSI 高就盲目 Short；
- RSI 低就盲目 Long；
- 猜頂；
- 撈底；
- 接 Falling Knife；
- 過度延伸後 FOMO 追入；
- 因為「跌咗好多」而自動買入；
- 因為「升咗好多」而自動沽空。

### 9.3 完整 Setup 必要欄位 [已確認]

一個 Setup 缺少任何一項都唔可以進入評分：

```text
Direction            LONG / SHORT
Setup Type           見 §9.1
Trigger              已確認嘅觸發事件及 Candle Timestamp
Entry Zone           價格區間（非單一點）
Confirmation         已滿足嘅確認條件清單
Stop Loss            具體價格，對應結構位置
Invalidation         Setup 失效嘅結構條件（可能早於 Stop 觸發）
TP1 / TP2 / TP3      具體價格，每個對應真實結構
Expected R:R         以 Entry Zone 中點、Stop、加權 TP 計算
Supporting Evidence  支持證據清單
Contradictory Evidence  矛盾證據清單（可以為空但必須明確標示已檢查）
Cancel Conditions    Entry 未成交前取消 Setup 嘅條件（例如價格已離開 Entry Zone、Trigger 被否定）
```

---

## 10. 評分系統

### 10.1 分開評分 [已確認]

每個候選會**同時**得到：

- `LONG_SCORE`（0–10）
- `SHORT_SCORE`（0–10）

唔係一個「淨分」——因為一隻幣可能同時有弱嘅 Long 理由同強嘅 Short 理由，分開計先可以睇到全貌。

### 10.2 分數組成 [已確認]

| # | Component | 方向 |
|---|---|---|
| 1 | 4H 趨勢一致性 | 加分 |
| 2 | 1H 市場結構 | 加分 |
| 3 | Momentum | 加分 |
| 4 | 成交量確認 | 加分 |
| 5 | 相對強弱 | 加分 |
| 6 | BTC Regime 一致性 | 加分／扣分 |
| 7 | Funding／OI Context | 加分／扣分 |
| 8 | 入場質素 | 加分 |
| 9 | Risk／Reward | 加分 |
| 10 | 流動性及執行質素 | 加分／扣分 |
| 11 | 過度延伸 | **扣分** |
| 12 | 矛盾證據 | **扣分** |

**[已確認]** 每一個 Component 嘅分數都會單獨保存，唔會只留下總分。目的係日後可以分析「邊個 Component 最有預測力」。

### 10.3 權重 [候選]

各 Component 嘅權重屬於 Strategy Version 嘅一部分，必須：

- 寫入 Strategy Registry；
- 對應 Git Commit；
- 任何改動都係新 Strategy Version，唔可以靜默調整。

**[建議]** 初始版本用等權重起步，等有足夠樣本再做權重實驗。

### 10.4 分數門檻 [已確認]

| 分數 | 結果 |
|---|---|
| `< 7.0` | `NO TRADE` |
| `7.0 – 7.9` | 有潛力，但早期部署需要更強確認或人工批准 |
| `≥ 8.0` | 高質素候選，**但仍然必須通過所有風險及執行閘門** |

### 10.5 分數唔係最終決定 [已確認]

即使分數係 9.5，只要以下任何一項失敗，都唔可以交易：

- 數據不完整；
- Stop 不合理；
- R:R 不足；
- 最低訂單超過安全風險；
- Account State 不清楚；
- WebSocket 不可靠；
- 保護單不能建立；
- 已經有另一個 Position；
- Circuit Breaker 生效。

### 10.6 Data Quality 對分數嘅影響 [建議]

- `COMPLETE`：分數無上限調整；
- `DEGRADED`：總分上限 7.9（即最多只可到「需人工批准」級別）；
- `INSUFFICIENT` / `SUSPECT`：唔評分，直接 `NO TRADE`。

---

## 11. Critic 與矛盾證據檢查

### 11.1 目的 [已確認]

喺選出最高分候選後、進入風險計算前，系統做一次獨立嘅「反方論證」：主動搵推翻呢個 Setup 嘅理由。

### 11.2 Critic 檢查內容 [已確認方向]

- 有冇更高週期嘅阻力／支持就喺 TP1 之前？
- Funding／OI 有冇同方向矛盾（例如 Long Setup 但 Funding 極高、OI 急增——擠倉風險）？
- 成交量確認係否真實（有冇單一巨型 Candle 扭曲）？
- 相對強弱係否只係 BTC 短暫波動造成？
- Entry Zone 係否已經被價格離開？
- Stop 位置係否喺明顯嘅流動性獵取區（Stop Hunt Zone）？
- 近期有冇該幣嘅異常事件（Listing、Delisting 公告、異常 Spread）？

### 11.3 Critic 嘅權力邊界 [已確認]

Critic（無論係規則引擎定 LLM）**可以**：

- 增加矛盾證據到 Component 12，令分數下降；
- 建議 `NO TRADE`；
- 要求人工批准。

Critic **唔可以**：

- 提高分數；
- 改變 Stop、Entry、TP 嘅數字；
- 改變 Risk Amount 或 Quantity；
- 將被排除嘅候選重新引入。

即係 Critic 只有「踩 Brake」嘅權力，冇「踩油」嘅權力。

### 11.4 LLM 使用原則 [已確認]

- LLM 輸出必須係結構化格式（JSON Schema 驗證），唔接受自由文字作為決策輸入；
- LLM 輸出嘅所有數字只作參考，**唔會**直接進入風險計算；
- LLM 唔可用時，Critic 退化為純規則版本，唔會因此阻止 `NO TRADE` 輸出，但會阻止 Trade（因為 Critic 未完成）。

---

## 12. 交易計劃：Entry、Stop、Target、R:R

### 12.1 Reward／Risk Gate [已確認]

```text
最低 Expected R:R = 1.8
偏好 Expected R:R ≥ 2.0
```

### 12.2 目標必須對應真實結構 [已確認]

系統**唔會**為咗令 R:R 睇落好睇而製造不合理 TP。每個 TP 必須對應以下其中一項：

- 真實支持／阻力；
- Swing High／Low；
- Volume Profile／Liquidity Zone；
- Breakout Measured Move；
- 結構失效點。

如果按結構找唔到足夠遠嘅目標令 R:R ≥ 1.8 → `NO TRADE (RR_INSUFFICIENT)`。

### 12.3 Expected R:R 計算 [建議]

```text
Entry     = Entry Zone 中點（或預期成交價）
Risk      = |Entry − Stop| + 預期 Slippage + Fees（以價格單位表示）
Reward    = Σ (TP_i 分配比例 × |TP_i − Entry|) − 預期 Slippage − Fees
Expected R:R = Reward ÷ Risk
```

用**加權 TP** 而唔係只用 TP3，避免用一個遙遠目標美化 R:R。

### 12.4 Partial Take Profit [已確認為初始研究模型]

```text
TP1: 30%
TP2: 40%
TP3: 30%
```

呢個係**可測試模型**，唔係永遠固定真理。

### 12.5 TP1 後止損處理 [候選]

可能方案（每種都必須有獨立 Strategy Version 同歷史結果分開比較）：

- 移動到 Breakeven；
- 移動到新結構位；
- Trailing Stop；
- 保持原有 Stop。

### 12.6 小資金 Partial TP 處理 [已確認]

如果小資金導致 30%／40% 部分數量低過 Bybit 最低合法數量，系統應使用**經版本化嘅單一離場方法**，而唔係製造不合法 Partial TP。

**[建議]** 單一離場方法預設為：全倉於 TP2 位置離場（因為 TP2 通常係加權 R:R 嘅中位）。

### 12.7 Stop 合理性檢查 [建議]

Stop 必須同時滿足：

- 距離 Entry 最少 1.0 × ATR(1H)（避免被正常波動掃走）；
- 距離 Entry 最多 3.0 × ATR(1H)（避免風險單位過大令 Quantity 太細）；
- 位於明確結構位之外（唔係隨意百分比）；
- 對應 Liquidation Price 有足夠緩衝（見 §15.6）。

---

## 13. 風險引擎

### 13.1 每單基礎風險 [已確認]

```text
Base Risk =
floor_to_cent(
    1% × min(
        Authoritative Settled Strategy Equity,
        Qualified Stage Equity
    )
)
```

`floor_to_cent` 係向下取整到 0.01 USDT，永遠唔向上取。

### 13.2 Authoritative Settled Strategy Equity 定義 [已確認]

可以用作風險計算及增長計算嘅 Equity 必須係：

- 已平倉；
- 已結算；
- Fees 已計；
- Funding 已計；
- 無未實現盈虧；
- 無未分類 Deposit／Withdrawal；
- 無 Bonus；
- 無 Borrowing；
- 無 Wallet／Ledger 差異；
- 無未解決 Incident。

系統**唔會**將以下項目當成策略增長：

- 新 Deposit；
- Bonus；
- Borrowed Funds；
- 未實現盈利；
- 未 Reconcile 嘅 Funding；
- 未分類 Transfer。

### 13.3 可執行風險 [已確認]

```text
Executable Risk =
min(
    Base Risk,
    Active Release Remaining Limit,
    Remaining Unsettled Reservations,
    Remaining 1 USDT Sydney Daily Loss Budget,
    Remaining 5 USDT First-Pilot Loss Budget
)
```

每一項嘅意思：

| 項 | 意思 |
|---|---|
| Base Risk | §13.1 計出嘅 1% |
| Active Release Remaining Limit | 當前 Release 批准嘅風險上限剩餘額 |
| Remaining Unsettled Reservations | 扣除已保留但未結算嘅風險（例如 Pending Order） |
| Remaining Sydney Daily Loss Budget | 今個 Sydney Trading Day 剩餘可損失額（上限 1 USDT） |
| Remaining First-Pilot Loss Budget | 第一個 Pilot 剩餘可損失額（上限 5 USDT） |

如果 `Executable Risk ≤ 0` → `NO TRADE (RISK_BUDGET_EXHAUSTED)`。

### 13.4 已確認參數 [已確認]

| 參數 | 值 |
|---|---|
| 每單基礎風險 | 1% |
| 每個 Sydney Trading Day 最多消耗 | 1 USDT |
| 第一個 Pilot 累積最多消耗 | 5 USDT |
| Profit 會否補滿已消耗嘅 Daily／Pilot Loss Budget | **唔會** |
| 連續損失阻止新交易 | 3 次 |
| 整個實驗資金概念 | 約 100 USDT（**唔係**授權自動輸晒 100 USDT） |

### 13.5 例子 [已確認]

| 合資格本金 | 1% 基礎風險 | 備註 |
|---:|---:|---|
| 25 USDT | 0.25 USDT | 初始例子 |
| 50 USDT | 0.50 USDT | 隨本金調整 |
| 75 USDT | 0.75 USDT | 仍受每日／Pilot 上限限制 |
| 100 USDT | 1.00 USDT | 不代表必定可以使用全部 |

0.25 USDT **唔係**永久固定風險，而係本金為 25 USDT 時嘅 1% 例子。

### 13.6 損失預算計算方式 [建議]

- Daily Loss Budget 以**已實現淨損失**（含 Fees、Funding、Slippage）計算；
- 一筆交易嘅損失喺**完全平倉並結算後**先扣減預算；
- Pending 交易嘅 Executable Risk 會先「保留」（Reservation），令同一 Day 內唔會超額開倉；
- 連續損失計數只計已平倉交易，Breakeven 離場（|淨 PnL| < 0.01 USDT）唔重置亦唔累加。

---

## 14. 倉位計算

### 14.1 概念公式 [已確認]

```text
Risk Amount   = Executable Risk（§13.3）

Risk Per Unit =
    Stop Distance
    + Entry Slippage
    + Exit Slippage
    + Entry Fee
    + Exit Fee
    （全部以每單位合約嘅價格差表示）

Raw Quantity  = Risk Amount ÷ Risk Per Unit

Safe Quantity = floor(Raw Quantity to Bybit Quantity Step)
```

### 14.2 計算後檢查 [已確認]

Safe Quantity 必須通過：

- ≥ Minimum Quantity；
- Safe Quantity × Entry ≥ Minimum Notional；
- ≤ Maximum Market Quantity（如用 Market Order）；
- 符合 Quantity Step；
- Entry／Stop／TP 價格符合 Tick Size；
- 所需 Margin ≤ Available Margin（考慮 Leverage）；
- Fees 已計入；
- Slippage 估算合理（基於 Orderbook Depth）；
- Funding 對持倉期間嘅預期影響已估算；
- Leverage 符合 Instrument Min／Max 及 Step；
- Liquidation Distance 遠於 Stop Distance（見 §15.6）。

### 14.3 不符合最低訂單嘅處理 [已確認]

```text
如果 Safe Quantity < Minimum Quantity
或 Safe Quantity × Entry < Minimum Notional
→ NO_TRADE (MIN_ORDER_EXCEEDS_RISK)
```

**唔會為咗符合最低訂單而向上增加風險。**

### 14.4 Slippage 估算 [建議]

- Entry Slippage：用當前 Orderbook，模擬 Safe Quantity 嘅 Market Order 成交加權價 vs Mid；
- Exit Slippage：假設 Stop 觸發時為 Market Order，用同一方法估算，並加 50% 保守緩衝（Stop 觸發時流動性通常較差）；
- 如 Orderbook 深度不足以估算 → 該幣 `NO_TRADE (INSUFFICIENT_DEPTH)`。

---

## 15. 波動槓桿階梯 1x／3x／5x

### 15.1 PAPER Research Policy [已確認]

```text
High Volatility   → 1x
Medium Volatility → 3x
Low Volatility    → 5x
```

Policy ID：`closed-1h4h-volatility-leverage-v2`

### 15.2 核心原則 [已確認]

> 槓桿只改變需要鎖住嘅 Margin，唔會增加每單容許損失。

假設止損、風險預算同倉位數量完全相同：

| 槓桿 | Margin 需求 | 最大計劃損失 |
|---|---|---|
| 1x | 較多 | 相同 |
| 3x | 較少 | 相同 |
| 5x | 更少 | 相同 |

即係 Quantity 由 §14 決定，槓桿只影響 Margin 佔用，唔影響 Quantity。

### 15.3 波動判斷輸入 [已確認]

波動判斷唔係簡單上網見到一個 Volatility 數字就直接決定，而係需要：

- 相同 Bybit Server Time 快照；
- 已確認 1H Candle；
- 已確認 4H Candle；
- 足夠 Candle 數量；
- 1H／4H Realised Log Volatility；
- 1H／4H ATR Percentage；
- 同一合資格 Universe 內嘅相對排名；
- 絕對波動上限；
- Instrument 當前 Min／Max Leverage；
- Leverage Step；
- Spread／Liquidity／Execution Quality。

### 15.4 分類邏輯 [候選]

**[建議]** 用 Universe 相對排名 + 絕對上限雙重判斷：

- 波動指標於 Universe 前 1/3 **或** 超過絕對上限 → `High`；
- 中間 1/3 → `Medium`；
- 後 1/3 **且** 低於絕對上限 → `Low`；
- 1H 與 4H 分類不一致時，取較高波動（較保守）嘅分類。

### 15.5 5x 只係 PAPER 上限 [已確認]

現時 5x 只係 **PAPER Research Ceiling**，唔代表 Testnet 或 Live 可以使用 5x。Testnet／Live 槓桿要再根據以下**獨立批准**：

- Account Mode；
- Isolated Margin；
- Auto-add-margin 關閉；
- Actual Liquidation Price；
- Stop Distance；
- Instrument 規則；
- Release Policy；
- Testnet 證據。

### 15.6 Liquidation Distance 規則 [建議]

無論選定邊個槓桿，都必須滿足：

```text
|Liquidation Price − Entry| ≥ 2.0 × |Stop − Entry|
```

即係 Stop 必須喺 Liquidation 之前有至少一倍距離嘅緩衝。唔滿足 → 自動降一級槓桿重新檢查；1x 都唔滿足 → `NO_TRADE (LIQUIDATION_TOO_CLOSE)`。

### 15.7 Margin Mode 要求 [已確認方向]

- Isolated Margin（唔用 Cross）；
- Auto-add-margin **關閉**；
- One-way Position Mode（唔用 Hedge Mode）。

---

## 16. 執行安全閘門

### 16.1 原則 [已確認]

喺任何 Order 發送前，以下**全部**必須通過。任何一項失敗即停止，唔會「部分通過就試下」。

### 16.2 閘門清單 [已確認方向，整理版]

**資料與時間**
- [ ] Data Quality = `COMPLETE`
- [ ] Bybit Server Time 偏差在閾值內
- [ ] 所有依賴 Candle 已確認收市

**策略與評分**
- [ ] Score ≥ 當前 Mode 要求門檻
- [ ] Setup 所有必要欄位齊全（§9.3）
- [ ] Critic 已完成，冇未處理嘅重大矛盾證據
- [ ] Expected R:R ≥ 1.8

**風險**
- [ ] Executable Risk > 0
- [ ] Safe Quantity ≥ Min Qty 及 Min Notional
- [ ] Liquidation Distance 合規
- [ ] 連續損失 < 3
- [ ] 所有 Circuit Breaker 未觸發

**帳戶與執行**
- [ ] Account Balance 可確認且足夠
- [ ] 現有 Position 數量 = 0
- [ ] 冇 Pending Order
- [ ] Private WebSocket 健康（TESTNET／LIVE）
- [ ] Instrument 可交易、規則已讀取
- [ ] Spread 及估算 Slippage 在限制內
- [ ] Margin Mode／Position Mode／Leverage 已正確設定並確認

**配置與授權**
- [ ] `TRADING_MODE` 明確且與 API Key 環境一致
- [ ] 當前 Release 有效（未過期、Digest 匹配、Symbol 在 Allowlist）
- [ ] LIVE 時：所有 §21.3 條件滿足
- [ ] 需人工批准嘅情況已獲批准

**系統狀態**
- [ ] SQLite Integrity 通過
- [ ] Outbox 冇無法 Reconcile 嘅積壓
- [ ] 冇 Duplicate Order 風險（同一 Signal 冇已存在 Order）
- [ ] Operator 冇 Pause New Entries

### 16.3 閘門結果紀錄 [已確認]

無論通過或失敗，每個閘門嘅結果都寫入 Signal 紀錄，令「高分但被拒絕」嘅機會有完整追蹤。

---

## 17. 訂單執行與狀態機

### 17.1 Order State Machine [已確認]

```text
SIGNAL_CREATED
    ↓
RISK_APPROVED
    ↓
ORDER_PENDING          ← Trade Intent 已寫入 SQLite，orderLinkId 已產生
    ↓
ORDER_ACCEPTED         ← Bybit REST 返回接受（≠ 成交）
    ↓
PARTIALLY_FILLED  ⇄    ← 由 Private Stream 或 Reconciliation 確認
    ↓
FILLED                 ← 全數成交確認
    ↓
PROTECTION_PENDING     ← 正在建立 Exchange-side Stop
    ↓
PROTECTED              ← Stop 已確認存在並覆蓋全部倉位
    ↓
TP1_FILLED
    ↓
TP2_FILLED
    ↓
CLOSED                 ← 倉位 = 0，所有 Order 已結束，PnL 已結算

其他終止／異常狀態：
CANCELLED
REJECTED
ERROR
RECONCILIATION_REQUIRED
```

### 17.2 狀態轉移規則 [已確認方向]

| 由 | 到 | 觸發 | 證據來源 |
|---|---|---|---|
| `SIGNAL_CREATED` | `RISK_APPROVED` | 所有閘門通過 | 本地 |
| `RISK_APPROVED` | `ORDER_PENDING` | Intent 寫入 SQLite，orderLinkId 產生 | 本地 |
| `ORDER_PENDING` | `ORDER_ACCEPTED` | REST 返回 `retCode=0` 及 orderId | Bybit REST |
| `ORDER_PENDING` | `REJECTED` | REST 返回錯誤 | Bybit REST |
| `ORDER_PENDING` | `RECONCILIATION_REQUIRED` | REST 超時／結果不確定 | 本地 |
| `ORDER_ACCEPTED` | `PARTIALLY_FILLED` / `FILLED` | Execution Stream 事件 | **Bybit Private WS** |
| `ORDER_ACCEPTED` | `CANCELLED` | Cancel 確認 | Bybit |
| `FILLED` | `PROTECTION_PENDING` | 自動 | 本地 |
| `PROTECTION_PENDING` | `PROTECTED` | Stop 建立 **並** 再次讀取確認 | Bybit REST/WS |
| `PROTECTION_PENDING` | `RECONCILIATION_REQUIRED` | Stop 建立失敗或狀態不清 | 本地 → SAFE_MANAGEMENT |
| 任何 | `RECONCILIATION_REQUIRED` | 本地與 Bybit 狀態不一致 | Reconciliation |
| `RECONCILIATION_REQUIRED` | 正確狀態 | Reconcile 成功 | Bybit REST 為權威 |

### 17.3 最重要規則 [已確認]

```text
ORDER_ACCEPTED ≠ FILLED
```

Bybit REST 接受 Request，只代表系統收到請求，**唔代表**：

- 已經有成交；
- 成交數量等於要求數量；
- 成交價等於預期；
- Position 已經建立；
- Stop Loss 已經生效。

真正成交必須由 **Private Execution Stream、Order Stream 或可靠 REST Reconciliation** 確認。

### 17.4 Idempotency [已確認]

每張 Order 必須有唯一、可重現嘅 Client Order ID（`orderLinkId`）。

**[建議]** 格式：`{strategy_version_short}-{signal_id}-{leg}-{attempt}`，例如 `sv12-000481-entry-1`。同一 Signal 同一 Leg 嘅 Retry 只改 `attempt`，其他不變。

正確流程 [已確認]：

1. 先保存交易意圖到 SQLite；
2. 產生唯一 Order ID；
3. 發出 Request；
4. 如果結果不確定，先向 Bybit Reconcile（用 `orderLinkId` 查詢）；
5. 確認舊 Order 不存在先決定下一步；
6. **禁止**同一 Signal／Evidence 建立第二張 Order。

**[已確認]** 完全相同嘅 Retry（同一 Plan、Risk、Entry、Quantity、Metadata）可以被視為 Idempotent Retry；任何欄位改變都係衝突，必須當成新 Signal 重新走全部閘門。

**[已確認]** 不確定 Request **唔可以**盲目重試。

### 17.5 Partial Fill 處理 [已確認]

系統必須處理：

- 部分 Entry 成交；
- 未成交餘額；
- Cancelled Remainder；
- Partial TP；
- Partial Stop；
- Limit Order 過期；
- Cancel／Fill Race（發出 Cancel 同時有 Fill）。

實際風險必須根據以下重新計算：

- Actual Filled Quantity；
- Weighted Average Fill Price；
- Actual Fees；
- Actual Slippage。

**[建議]** Partial Entry 處理策略（需版本化）：
- 如果已成交部分 ≥ 50% 計劃數量 → 取消餘額，以實際數量建立 Protection，繼續管理；
- 如果 < 50% → 取消餘額，評估實際 R:R；如果實際 Quantity 低於 Min Qty 令 Partial TP 不可行，轉用單一離場方法；
- 任何情況下 Protection 必須覆蓋**實際**數量，唔係計劃數量。

### 17.6 Reconciliation 程序 [已確認方向，整理版]

觸發時機：

- 任何 REST 結果不確定；
- Private WS 斷線重連後；
- 系統 Restart 後；
- Position Monitor 偵測到本地與 Bybit 差異；
- 定期（**[建議]** 每 5 分鐘有倉位時）。

程序：

1. 用 REST 讀取 Bybit 當前：Open Orders、Order History（按 `orderLinkId`）、Positions、Wallet Balance、Executions；
2. 對比 SQLite 中每個非終止狀態嘅 Order／Position；
3. **Bybit 為權威**：本地狀態更新以匹配 Bybit；
4. 任何無法解釋嘅差異（例如 Bybit 有 Position 但本地冇 Intent）→ `SAFE_MANAGEMENT` + Critical Incident；
5. Reconciliation 結果寫入事件表；
6. 只有 Reconciliation 完成且一致，先可以恢復正常運作。

---

## 18. 保護單（Protective Stop）與 SAFE_MANAGEMENT

### 18.1 Protection 建立流程 [已確認]

Entry 成交確認後，系統必須：

1. 建立 Exchange-side Stop（Bybit 條件單／Position TP-SL）；
2. 再次讀取 Bybit 狀態；
3. 確認 Stop 真係存在；
4. 確認 Stop 覆蓋**全部實際倉位**數量；
5. 保存保護證據（Stop Order ID、Trigger Price、Quantity、確認時間）。

### 18.2 Protection 失敗處理 [已確認]

如果 Stop 無法建立或狀態不清：

1. 阻止新交易；
2. 進入 `SAFE_MANAGEMENT`；
3. 嘗試預先定義嘅恢復流程（**[建議]** 最多 3 次重試，每次先 Reconcile）；
4. 必要時用 **Reduce-only** 關閉實際剩餘倉位；
5. 建立 Critical Incident；
6. **絕對唔可以明知有裸露槓桿倉位而繼續運作。**

### 18.3 Protection 持續驗證 [已確認方向]

Position Monitor 每次運行都要確認：

- Stop Order 仍然存在（未被取消、未過期）；
- Stop Quantity = 當前 Position Quantity（Partial TP 後要同步縮減或確認 Bybit 自動調整）；
- Stop Trigger Price 未被改動（除非係系統本身按版本化規則移動）。

任何一項唔滿足 → 立即重建 Protection；重建失敗 → §18.2。

### 18.4 SAFE_MANAGEMENT 狀態定義 [已確認]

```text
SAFE_MANAGEMENT =
    停止所有新 Entry
  + Scanner 繼續運行但只輸出 NO TRADE
  + Position Monitor 以最高優先級運行
  + 優先確保 Protection 存在
  + 允許 Reduce-only 離場操作
  + 禁止任何增加倉位嘅操作
  + 所有事件標記為 SAFE_MANAGEMENT 期間
  + 需人工確認先可以退出
```

**[建議]** 退出 `SAFE_MANAGEMENT` 條件：倉位 = 0 **或** Protection 已重新確認，**且** Operator 明確確認退出，**且** 相關 Incident 已標記 Contained。

---

## 19. 持倉管理

### 19.1 倉位上限 [已確認]

```text
Maximum Concurrent Positions = 1
```

原因：小本金、系統初期、相關性風險。

### 19.2 持倉期間行為 [已確認]

- Position Monitor 優先於新 Scanner；
- 唔會發出第二個可執行 Entry；
- 持續確認 Position Quantity；
- 確認 Stop Coverage；
- 監控 TP／SL 狀態；
- 計算已付／應付 Funding；
- 監控 Liquidation Distance；
- 偵測本地狀態同 Bybit 狀態差異；
- Restart 後重新 Reconcile；
- 完全平倉後先恢復下一次全市場掃描。

### 19.3 Position Monitor 檢查項目 [建議]

每次運行：

| 檢查 | 失敗處理 |
|---|---|
| Bybit Position 存在且數量與本地一致 | `RECONCILIATION_REQUIRED` |
| Protection 存在且覆蓋全數 | 重建；失敗 → `SAFE_MANAGEMENT` |
| Liquidation Distance ≥ 2 × Stop Distance | 警告；如果因 Funding 累積導致 → 評估 Reduce-only |
| Mark Price 與 Last Price 偏差正常 | 警告 |
| Private WS 最後心跳在閾值內 | 重連；失敗 → `SAFE_MANAGEMENT` |
| Funding 累計 vs 預期 | 記錄；超出預期 2 倍 → 警告 |
| Setup Invalidation 條件是否已觸發（早於 Stop） | 按 Strategy Version 決定是否提早離場 |
| 持倉時間是否超過 Strategy Version 最大持倉時間 | 按版本規則處理 |

### 19.4 建議 vs 實際成交分開紀錄 [已確認]

交易建議同用戶實際成交要分開紀錄。只有以下三種證據之一，先可以將建議標記為真實成交：

1. Private Account Evidence（Execution Stream／REST）；
2. 用戶明確確認；
3. 用戶提供 Fill Evidence。

---

## 20. Circuit Breakers

### 20.1 觸發即阻止新倉嘅條件 [已確認]

**資本**
- Sydney Daily Loss Budget 已用完；
- First-Pilot 5 USDT Loss Budget 已用完；
- 三次連續損失。

**市場資料**
- 市場數據過期；
- Candle 不完整；
- Spread／Slippage 超出限制。

**交易所連接**
- Bybit API 狀態不清；
- Private WebSocket 失效；
- WebSocket Sequence Gap；
- Account Balance 無法確認。

**狀態一致性**
- Position State 同本地資料不一致；
- Stop 未能建立或驗證；
- 有 Duplicate Order 風險；
- Journal／Outbox 無法可靠 Reconcile。

**系統健康**
- 系統時間不同步；
- Risk Calculation 失敗；
- Database Integrity 失敗；
- Queue Overflow。

**配置**
- API Key 環境不清楚；
- Testnet／Live Configuration 有矛盾。

### 20.2 行為 [已確認]

| 情況 | 行為 |
|---|---|
| 冇倉位 | 停止新交易，Scanner 只輸出 `NO TRADE (CIRCUIT_BREAKER: <原因>)` |
| 有倉位 | 進入 `SAFE_MANAGEMENT`（§18.4），**唔係**簡單停止程式 |

### 20.3 重置規則 [建議]

| Breaker | 自動重置 | 需人工重置 |
|---|---|---|
| Daily Loss Budget | 下一個 Sydney Trading Day | — |
| Pilot Loss Budget | — | 需要新 Pilot 批准 |
| 三次連續損失 | — | 需人工 Review 後重置 |
| 市場資料類 | 資料恢復健康並持續 N 個 Cycle | — |
| 連接類 | 連接恢復並 Reconciliation 通過 | — |
| 狀態一致性類 | — | 必須人工確認 |
| 系統健康類 | — | 必須人工確認 |
| 配置類 | — | 必須人工確認 |

每次觸發及重置都寫入 Incident Log。

---

## 21. 三種交易模式

### 21.1 PAPER [已確認]

**定位**：預設模式。使用真實 Bybit Public Market Data，但所有執行係模擬。

**必須模擬嘅項目**：
- Trigger；
- Spread；
- Fees；
- Slippage；
- Partial Fill；
- Limit Order 行為（成交／過期／部分成交）；
- Funding；
- Stop Gap（Stop 觸發時嘅跳空）；
- TP／SL；
- Restart；
- 完整 Position Lifecycle。

**原則**：PAPER 唔可以假設每次都喺完美價格成交。

**14 日／300 Cycles Burn-in 驗證目標**：
- Scheduler 有冇持續運作；
- 有冇重複 Cycle；
- 有冇重複 Order；
- Database 有冇損壞；
- Restart 能否恢復；
- Backup／Restore 是否可靠；
- Incident 是否正確紀錄；
- Notion Outbox 是否 Idempotent；
- Pause／Recovery／Kill Switch 是否有效。

**明確聲明**：Burn-in 通過**唔係**14 日後自動證明策略賺錢。佢證明嘅係**系統工程可靠性**，唔係策略盈利能力。

### 21.2 TESTNET [已確認]

**前置要求**：
- 明確證明係 Testnet Key（**[建議]** 用 API 讀取帳戶資訊，確認 Endpoint 為 testnet 域名，並記錄 Key 指紋）；
- Trading-only；
- No Withdrawal 權限；
- 正確 Account Type；
- 正確 Position Mode；
- 正確 Margin Mode；
- 正確 Leverage。

**必須驗證嘅能力**：
- Signed REST；
- Private WebSocket；
- Fill Confirmation；
- Partial Fill；
- Stop／TP 建立及觸發；
- Cancel；
- Reconnect；
- Restart；
- Reconciliation；
- Duplicate Prevention；
- Kill Switch；
- Emergency Close。

**必須完成最少一次完整流程**：

```text
Entry
→ Accepted
→ Authoritative Fill
→ Verified Stop
→ Position Management
→ Exact Close
→ Reconciliation
```

### 21.3 LIVE [已確認]

**Live 永遠唔係 Default。**

**最低配置要求**：
```text
TRADING_MODE=LIVE
LIVE_TRADING_ACKNOWLEDGED=true
```

**但兩個設定仍然不足夠**，仲需要：
- 特定 Release 批准；
- 指定 Artifact Digest（部署嘅程式碼必須與批准嘅 Digest 完全一致）；
- 指定 Symbol Allowlist；
- 指定 Risk Limits；
- 指定有效時間（Release 過期即自動退回不可交易）；
- 專用 Trading-only／No-withdrawal Key；
- Testnet 全流程通過；
- Reconnect／Restart Drill 通過；
- Exchange Stop 通過；
- Operator Takeover 通過；
- **明確行動時批准**（每次 Live Entry 需人工批准，至少於早期 Pilot）。

**早期 Live Pilot 限制**：
- 一個 Symbol；
- 一個 Position；
- 同日完成（唔隔夜）；
- 人工批准 Entry；
- 固定 Loss Ceiling（5 USDT Pilot Budget）；
- 有異常立即停止新倉；
- 不能自動擴大本金或風險；
- 不能因一次成功就提升槓桿。

### 21.4 Mode 提升規則 [已確認]

```text
PAPER  → TESTNET   永不自動，需人工決定
TESTNET → LIVE     永不自動，需人工決定 + Release 批准
LIVE   → PAPER     可以自動（任何 Circuit Breaker 或 Release 過期）
```

即係只有**降級**可以自動，**升級**永遠人工。

### 21.5 各 Mode 嘅分數門檻 [建議]

| Mode | 最低可交易分數 | 7.0–7.9 處理 |
|---|---|---|
| PAPER | 7.0 | 自動執行（研究目的） |
| TESTNET | 7.5 | 需人工批准 |
| LIVE（早期 Pilot） | 8.0 | 拒絕 |
| LIVE（成熟後） | 8.0 | 需人工批准 |

---

## 22. 資本與複利政策

### 22.1 方向 [已確認]

本金增長後，1% 風險金額亦隨**已確認本金**增長，唔係永遠固定 0.25 USDT。

### 22.2 候選增長模型 [候選]

```text
25 → 27.50 → 30.25 → 33.28 → … → 94.94 → 100 USDT
```

即每個 Reporting Target 約增加 10%。

「使用複利」方向已確認；具體 10% 階梯、每階段要幾多交易、Drawdown 門檻等**仍屬候選規則**，正式 Live 前需要再次批准。

### 22.3 階段更新規則 [已確認]

- 達到目標後先更新下一個目標；
- 只可以喺**完全平倉及已結算 Checkpoint** 更新；
- 每次只提升一個風險 Stage；
- 增長要慢；
- Drawdown 時減風險要快；
- **絕對唔會**因目標提升而改變現有 Position 或 Stop；
- 到 100 USDT **暫停**並重新審批下一個 Capital Policy。

### 22.4 Drawdown 降級規則 [建議]

- 由 Stage 高點回撤 ≥ 10% → 自動降一個 Stage（Qualified Stage Equity 下調）；
- 回撤 ≥ 20% → 降兩個 Stage 並觸發人工 Review；
- 回撤 ≥ 30% → 退回 PAPER Mode，需重新 Release 批准。

降級即時生效（喺下一個 Cycle），升級只喺 Checkpoint 生效——即係「減風險快、加風險慢」嘅非對稱設計。

### 22.5 Stage 提升最低條件 [建議]

除達到 Equity 目標外：
- 該 Stage 內最少完成 10 筆已結算交易；
- 該 Stage 內 Max Drawdown < 10%；
- 該 Stage 內冇未解決 Incident；
- Weekly Review 明確批准提升。

---

## 23. 資料權威與持久化

### 23.1 權威來源表 [已確認]

| 資料 | 權威來源 | 用途 |
|---|---|---|
| 市場價格、Kline、Funding、OI、Orderbook | Bybit Public API | 分析及掃描 |
| 真實 Order、Fill、Position、Wallet | Bybit Private API／WebSocket | 確認真實帳戶狀態 |
| 本地交易意圖、風險決策、事件與狀態 | SQLite | 系統操作及審計真相 |
| 策略版本及程式版本 | Git／GitHub | 回溯、測試、Release、Rollback |
| 人類閱讀、Trade Journal、Review | Notion | 長期記憶與學習 |
| 倉位大小及風險 | Deterministic Code | AI 不可自行更改 |

### 23.2 Notion 嘅邊界 [已確認]

Notion 係人類使用嘅長期交易筆記，但：
- **唔會**負責即時止損；
- **唔可以**成為交易執行嘅權威來源；
- Notion 不可用時，交易系統繼續運作（Outbox 積壓），但 Outbox 積壓超過閾值會觸發 Circuit Breaker（因為審計鏈斷裂）。

### 23.3 秘密資料 [已確認]

API Key、API Secret、Notion Token 等秘密資料**永遠唔會**寫入：
- Notion；
- GitHub；
- 日誌；
- 程式碼；
- SQLite。

**[建議]** 秘密只由環境變數或 OS Keyring 提供；日誌對任何長度 ≥ 20 嘅 Hex／Base64 字串做遮蔽；Incident Log 有專門欄位「有冇 Secrets Exposed」。

### 23.4 SQLite Schema 概念 [建議，整理版]

| 表 | 主要欄位 | 用途 |
|---|---|---|
| `cycles` | cycle_id, started_at, server_time, regime, universe_size, candidates, result, data_quality | 每次 Scanner 運行 |
| `signals` | signal_id, cycle_id, symbol, direction, setup_type, long_score, short_score, components(JSON), setup(JSON), gates(JSON), decision, reject_reason | 每個認真考慮過嘅候選 |
| `trade_intents` | intent_id, signal_id, strategy_version, risk_amount, quantity, leverage, entry, stop, tps(JSON), mode, created_at | 決定嘗試執行嘅意圖 |
| `orders` | order_id(orderLinkId), intent_id, leg, attempt, bybit_order_id, state, requested_qty, filled_qty, avg_price, fees, created_at, updated_at | 每張 Order |
| `fills` | fill_id, order_id, exec_id, qty, price, fee, timestamp, source | 每筆成交（來自 WS 或 Reconciliation） |
| `positions` | position_id, intent_id, symbol, side, qty, avg_entry, protection_order_id, state, opened_at, closed_at, realized_pnl, funding_paid | 倉位生命週期 |
| `events` | event_id, entity_type, entity_id, from_state, to_state, evidence(JSON), timestamp | 所有狀態轉移 |
| `incidents` | incident_id, severity, category, detected_at, contained_at, root_cause, secrets_exposed, notion_synced | 事故 |
| `risk_ledger` | day(Sydney), pilot_id, budget, consumed, reserved, consecutive_losses | 風險預算追蹤 |
| `equity_checkpoints` | checkpoint_id, settled_equity, stage, stage_target, timestamp, evidence | 資本階段 |
| `outbox` | outbox_id, target_db, payload(JSON), idempotency_key, status, attempts, last_error | Notion 同步隊列 |
| `strategy_versions` | version_id, git_commit, config(JSON), approved_by, effective_from, rollback_to | 本地策略版本副本 |

### 23.5 Backup 與 Restore [已確認方向]

- SQLite 每日備份，保留最少 30 日；
- 每次備份後做 Integrity Check；
- Restore Drill 定期執行（**[建議]** 每月一次），確認可以由備份完整恢復並 Reconcile；
- 備份檔唔含秘密（本身 SQLite 都唔應該有秘密）。

---

## 24. Notion 交易記憶系統

### 24.1 七個功能分明嘅部分 [已確認]

| # | Database | 職責 |
|---|---|---|
| 1 | Signal & Decision Journal | 所有認真考慮過嘅候選（包括被拒絕嘅） |
| 2 | Trade Journal | 真實或模擬交易嘅完整生命週期 |
| 3 | Strategy Registry | 每個策略版本嘅規則、證據、批准 |
| 4 | Daily Performance | 每個 Sydney Trading Day 嘅總結 |
| 5 | Weekly Review | 每週分析及改良建議 |
| 6 | Strategy Experiments | 所有策略改動嘅假設、測試、結果 |
| 7 | Incident Log | 所有事故 |

### 24.2 Signal & Decision Journal 欄位 [已確認]

- 所有認真考慮過嘅候選；
- 最後有冇交易；
- 點解考慮；
- 點解拒絕；
- BTC Regime；
- 1H／4H 分析；
- Score Components（逐項）；
- Expected Entry／Stop／RR；
- Data Quality；
- Post Mortem（事後該 Setup 實際點走）。

**重要概念**：唔只記錄成功落單嘅訊號，亦要記錄高分但被風險閘門拒絕嘅機會。呢啲「錯過嘅機會」係評估閘門是否過嚴嘅唯一數據來源。

### 24.3 Trade Journal 欄位 [已確認]

- Trade ID；Symbol／Direction；Trading Mode；Strategy Version；
- Planned Entry／Actual Entry；
- Stop／TP1／TP2／TP3；
- Quantity／Notional／Leverage；
- Risk %／Risk USDT；
- Expected RR；Actual Exit；
- Gross／Net PnL；Fees／Funding／Slippage；
- R Multiple；Holding Time；
- MFE（Maximum Favorable Excursion）／MAE（Maximum Adverse Excursion）；
- Bybit Order IDs；Client Order IDs；
- Contradictory Evidence；Post-trade Review；Data Quality。

推薦交易同實際執行分開保存，避免將 Recommendation 當成 Fill。

### 24.4 Strategy Registry 欄位 [已確認]

- Entry Rules；Exit Rules；Risk Config；Score Config；
- Code Commit；Evidence；Approval；Rollback Version；Effective Date。

Live Strategy **唔可以**被 AI 靜默修改。

### 24.5 Daily Performance 欄位 [已確認]

- Starting／Ending Equity；Trades；Wins／Losses；No Trade Count；
- Gross／Net PnL；Fees／Funding；R Total；Drawdown；
- Circuit Breaker（有冇觸發、原因）；Data Quality。

### 24.6 Weekly Review 欄位 [已確認]

- Win Rate；Average R；Profit Factor；Max Drawdown；Net PnL；
- Strategy Versions（本週用過嘅）；
- Contradictions（本週發現嘅矛盾）；
- Observations；Proposed Changes；
- Approve／Reject／Continue（人工決定）。

### 24.7 Strategy Experiments 欄位 [已確認]

- Hypothesis；Baseline；Dataset；Sample Size；Success Metric；
- Guardrails（實驗期間唔可以超越嘅界線）；
- Result；Decision；Approved／Rejected。

### 24.8 Incident Log 欄位 [已確認]

- Severity；Category；Detection；Impact；Containment；Recovery；
- Root Cause；Verification；Follow-up；
- **有冇 Secrets Exposed**。

### 24.9 Outbox 同步原則 [已確認]

- 每個 Outbox 項目有 Idempotency Key（例如 `{entity_type}:{entity_id}:{version}`）；
- Notion 寫入前先查詢是否已存在同 Key 嘅頁面，存在則 Update 而非 Create；
- 失敗 Retry 用指數退避；
- 積壓超過閾值（**[建議]** 100 項或 24 小時）→ Circuit Breaker。

---

## 25. 學習與策略演進迴路

### 25.1 學習迴路 [已確認]

```text
記錄每次訊號與交易
        ↓
計算分 Setup／Regime／Symbol 嘅結果
        ↓
分析 Win Rate、R、Expectancy、Drawdown、MFE、MAE
        ↓
找出重複問題或優勢
        ↓
提出 Hypothesis
        ↓
建立 Strategy Experiment
        ↓
用歷史 Replay／Paper／Testnet 測試
        ↓
Critic Review
        ↓
人工批准或拒絕
        ↓
建立新 Strategy Version
        ↓
保留舊版本作 Rollback
```

### 25.2 AI 可以做嘅事 [已確認]

- 解釋市場；
- 找矛盾證據；
- 總結交易；
- 分類失敗模式；
- 提出策略改良；
- 產生 Weekly Review 草稿。

### 25.3 AI 唔可以做嘅事 [已確認]

- 任意選擇倉位；
- 增加風險；
- 自動取消 Stop；
- 自動放寬交易門檻；
- 因為連輸而加注；
- 自動修改 Live Strategy；
- 將 Backtest Result 當成 Live Profit 保證。

### 25.4 實驗最低要求 [建議]

- 樣本量：最少 30 筆同類 Setup 先可以得出方向性結論；
- 對照：必須有 Baseline（現行版本）同期比較；
- 多重檢驗：每週最多批准一個策略改動，避免同時改多樣令歸因不可能；
- Out-of-sample：Replay 測試嘅資料期唔可以係提出假設時已經睇過嘅期間。

### 25.5 Rollback 規則 [建議]

- 新 Strategy Version 生效後首 20 筆交易為「觀察期」；
- 觀察期內 Max Drawdown 超過舊版本同期 1.5 倍 → 自動 Rollback 到前一版本並觸發 Review；
- Rollback 本身亦係一個 Strategy Version 事件，寫入 Registry。

---

## 26. 系統絕對唔會做嘅事 [已確認]

- Martingale；
- 輸錢後 Double Down；
- Revenge Trade；
- 自動 Average Down；
- 價格接近止損就擴闊 Stop；
- 無限開倉；
- 無 Stop 交易；
- 盲目 Retry Order；
- 將 Accepted 當 Filled；
- 將 Recommendation 當真實交易；
- 為符合最低訂單而增加風險；
- 將槓桿當風險預算；
- 自動由 PAPER 轉 TESTNET；
- 自動由 TESTNET 轉 LIVE；
- 將 Secret 放入 Notion／Git；
- 宣稱測試通過就代表策略一定賺錢。

**[建議]** 呢個清單應該以自動化測試形式存在（每條一個 Test Case），令「絕對唔會」變成 CI 可以驗證嘅承諾。

---

## 27. 操作介面與人類控制權

### 27.1 你保留嘅最高控制權 [已確認]

- PAPER／TESTNET／LIVE Mode 切換；
- Pause New Entries；
- 進入／退出 Safe Management；
- Kill Switch；
- Strategy Approval；
- Live Release Approval；
- Manual Takeover；
- Emergency Close。

### 27.2 Kill Switch 定義 [建議]

```text
Kill Switch =
    立即停止 Scanner
  + 取消所有 Pending Entry Order
  + 保留 Protection（唔取消 Stop）
  + 系統進入 SAFE_MANAGEMENT
  + 唔自動平倉（除非 Operator 同時觸發 Emergency Close）
  + 需 Operator 明確重啟
```

### 27.3 Emergency Close 定義 [建議]

```text
Emergency Close =
    Kill Switch
  + 用 Reduce-only Market Order 關閉所有倉位
  + 確認倉位 = 0
  + 取消所有殘餘 Order
  + 建立 Critical Incident
```

### 27.4 每個 Cycle 嘅輸出格式 [已確認方向]

理想操作體驗：系統每次 Cycle 給你一個結果——

**情況 A：`NO TRADE`**
```text
Cycle #1234 | 2026-09-02 14:00 UTC | Mode: PAPER
Result: NO TRADE
Reason: NO_CANDIDATE_ABOVE_THRESHOLD
BTC Regime: NEUTRAL
Universe: 187 instruments (23 excluded)
Candidates analysed: SOLUSDT (L 6.2 / S 4.1), AVAXUSDT (L 5.8 / S 5.0), ARBUSDT (L 4.5 / S 6.4)
Data Quality: COMPLETE
Circuit Breakers: none
```

**情況 B：一個最高質素 Setup**
```text
Cycle #1235 | 2026-09-02 15:00 UTC | Mode: PAPER
Result: SETUP CANDIDATE
Symbol: SOLUSDT
Direction: LONG
Setup Type: BREAKOUT_RETEST_CONTINUATION
Score: LONG 8.3 / SHORT 2.1
  4H Trend 0.9 | 1H Structure 0.8 | Momentum 0.7 | Volume 0.8 | RelStrength 0.9
  Regime 0.6 | Funding/OI 0.7 | Entry Quality 0.8 | R:R 0.9 | Liquidity 0.9
  Overextension −0.3 | Contradictions −0.4
BTC Regime: BULL
Entry Zone: 178.20 – 178.80
Stop: 175.40 (below 1H retest low, 1.6 × ATR)
Invalidation: 1H close < 176.00
TP1: 182.50 (30%) | TP2: 185.20 (40%) | TP3: 189.00 (30%)
Expected R:R: 2.4
Risk Amount: 0.25 USDT (1% of 25.00 settled equity; daily remaining 0.75; pilot remaining 4.25)
Quantity: 0.1 SOL (floored to step; min qty OK; min notional OK)
Leverage: 3x (Medium Volatility; policy closed-1h4h-volatility-leverage-v2)
Margin Required: ~5.95 USDT | Liquidation Distance: 5.1 × Stop Distance ✓
Supporting: 4H HH/HL intact; 1H breakout of 177.50 confirmed with 1.8× avg volume; RS vs BTC +2.1% 24h; OI rising with price
Contradicting: Funding 0.028%/8h (elevated, 78th pct); 4H RSI 68 (approaching overextension)
Gates: 24/24 passed
Action: PAPER execute (auto) | TESTNET/LIVE would require approval
```

---

## 28. 可觀察性、事故與維護

### 28.1 日誌原則 [建議]

- 結構化日誌（JSON Lines），每條有 `cycle_id` / `signal_id` / `order_id` 關聯鍵；
- 日誌等級：`DEBUG` / `INFO` / `WARN` / `ERROR` / `CRITICAL`；
- `CRITICAL` 自動建立 Incident；
- 所有日誌經秘密遮蔽過濾器。

### 28.2 Incident Severity [建議]

| 等級 | 定義 | 例子 | 行動 |
|---|---|---|---|
| P0 | 資本即時風險 | 裸露倉位、Duplicate Order 已成交、Secret 洩露 | 立即 SAFE_MANAGEMENT + 通知 |
| P1 | 狀態不確定 | Reconciliation 失敗、WS 長時間斷線有倉位 | SAFE_MANAGEMENT + 通知 |
| P2 | 功能降級 | Notion Outbox 積壓、資料 DEGRADED 持續 | 阻止新倉 + 記錄 |
| P3 | 觀察項 | 單次 API 超時已恢復、Spread 短暫超限 | 記錄 |

### 28.3 維護任務 [已確認方向]

- 每日：SQLite Backup + Integrity Check；Daily Performance 產生；
- 每週：Weekly Review 產生；Log Rotation；
- 每月：Restore Drill；Reconnect／Restart Drill；
- 每次 Release：全部測試 + Digest 記錄。

---

## 29. 測試與驗證策略

### 29.1 測試層次 [已確認方向]

| 層次 | 內容 | 目前狀態（截至 Project Hub） |
|---|---|---|
| Unit | 風險公式、倉位計算、狀態機轉移、Idempotency Key | WP2.5 333/333 通過 |
| Integration | Private Stream Continuity、Reconciliation | WP3 366/366 通過，兩次零 P0/P1 Review |
| Replay | 用歷史資料重放完整 Cycle，驗證決定一致性 | Phase 1 完成 |
| Burn-in | 14 日／300 Cycles PAPER 持續運作 | 16/300 Cycles、0.632/14 Days 進行中 |
| Chaos | Fault Injection（WS 斷線、API 超時、Restart 中途） | Phase 5 未開始 |
| Testnet E2E | §21.2 完整流程 | 未開始 |

### 29.2 每個測試層證明嘅事 [已確認]

| 測試通過 | 證明 | **唔證明** |
|---|---|---|
| Unit | 公式正確 | 策略有 Edge |
| Burn-in | 系統可以持續穩定運作 | 策略賺錢 |
| Testnet | 執行層與 Bybit 正確互動 | Live 流動性相同 |
| Backtest／Replay | 規則喺歷史上一致 | 未來會重複 |

### 29.3 Release 流程 [建議]

1. 所有測試通過；
2. 產生 Artifact 並記錄 Digest；
3. Strategy Version 寫入 Registry 並連結 Commit；
4. Release Approval 記錄（Mode、Symbol Allowlist、Risk Limit、有效期、批准人、時間）；
5. 部署時驗證運行中嘅 Digest = 批准嘅 Digest；
6. 不匹配 → 拒絕啟動。

---

## 30. 開發階段與目前狀態

### 30.1 Phase 表 [已確認]

| Phase | 內容 | 狀態 |
|---|---|---|
| Phase 0 | 基礎安全、鎖、CI、Rollback | 完成 |
| Phase 1 | 市場證據、SQLite、Replay、Backup | 完成 |
| Phase 2 | 真實化 Paper Fill／Protection／Exit | 完成 |
| Phase 3 | 自動 Scanner、Monitor、Incident、Maintenance | 已安裝，Burn-in 進行中 |
| Phase 4 | Bybit Private API、WS、REST Reconciliation、Testnet | Source Engineering 進行中 |
| Phase 5 | Testnet Chaos、Fault Injection、Shadow Evidence | 未開始完整運作 |
| Phase 6 | Controlled Live v1 | **未獲授權** |

### 30.2 最新已記錄狀態 [已確認，截至 Project Hub]

- 操作中 PAPER Runtime：穩定，schema v11；
- 最新 Burn-in Checkpoint：16/300 Cycles、0.632/14 Days；
- 0 Incident、0 Order／Position、Notion Pending 0；
- WP2.5 風險／1x-3x-5x 證據層：333/333 測試通過；
- WP3 Private Stream Continuity Source Candidate：366/366 測試通過，兩次零 P0/P1 Review；
- Phase 4A Source：**未 Commit、未部署、未連接 Private Bybit**；
- 下一步：WP4 Account／Equity／Position／Fee／Liquidation／Protection Derived Truth；
- Testnet 同 Live：**仍然不可用**。

以上唔代表目前已經可以安全 Live。

---

## 31. 未決事項（需人工批准先可以實施）

以下係本文件中標記為 **[候選]** 或 **[建議]** 嘅項目，整理成一個待決清單：

### 31.1 已有方向、待定參數 [候選]
- [ ] Score Component 權重（§10.3）
- [ ] 波動分類具體閾值及相對排名邏輯（§15.4）
- [ ] TP1 後止損處理方法（§12.5）
- [ ] 複利 10% 階梯、每階段交易數、Drawdown 門檻（§22.2）
- [ ] Position Monitor 具體頻率（§3.3）

### 31.2 本文件補充、待審批 [建議]
- [ ] 時鐘偏差閾值（§3.1）
- [ ] 資料新鮮度閾值（§3.5）
- [ ] 歷史 Candle 最低數量（§4.3）
- [ ] `HIGH_VOLATILITY_UNCERTAIN` 預設 NO TRADE（§5.5）
- [ ] Universe 動態門檻具體百分位（§6.3）
- [ ] 候選選擇邏輯及 Sector 去相關（§7.3）
- [ ] Data Quality 對分數上限嘅影響（§10.6）
- [ ] Expected R:R 加權計算法（§12.3）
- [ ] 小資金單一離場預設用 TP2（§12.6）
- [ ] Stop 距離 ATR 上下限（§12.7）
- [ ] 損失預算計算細則及 Breakeven 定義（§13.6）
- [ ] Slippage 估算方法（§14.4）
- [ ] Liquidation Distance ≥ 2 × Stop Distance（§15.6）
- [ ] orderLinkId 格式（§17.4）
- [ ] Partial Entry 50% 規則（§17.5）
- [ ] Reconciliation 定期頻率（§17.6）
- [ ] Protection 重試次數（§18.2）
- [ ] SAFE_MANAGEMENT 退出條件（§18.4）
- [ ] Position Monitor 檢查清單（§19.3）
- [ ] Circuit Breaker 重置規則（§20.3）
- [ ] 各 Mode 分數門檻（§21.5）
- [ ] Drawdown 降級規則（§22.4）
- [ ] Stage 提升最低條件（§22.5）
- [ ] 秘密遮蔽規則（§23.3）
- [ ] SQLite Schema 概念（§23.4）
- [ ] Outbox 積壓閾值（§24.9）
- [ ] 實驗最低樣本量及 Rollback 規則（§25.4–25.5）
- [ ] 「絕對唔會做」清單轉為自動化測試（§26）
- [ ] Kill Switch／Emergency Close 定義（§27.2–27.3）
- [ ] Incident Severity 分級（§28.2）
- [ ] Release 流程（§29.3）

---

## 32. 附錄

### 32.1 Notion 頁面連結

| 頁面 | 連結 |
|---|---|
| Project Hub / Bybit Trading Intelligence System | https://app.notion.com/p/3cc58d7ccb6781f59357e5dab6d3b51d |
| Production Readiness Roadmap | https://app.notion.com/p/3cc58d7ccb67816f964cd6164c8cacb0 |
| Capital-linked Risk Policy | https://app.notion.com/p/3cd58d7ccb678190b21ac7c7adf31ccc |
| 1x/3x/5x Leverage Ladder | https://app.notion.com/p/3cd58d7ccb6781e891e6f6ad3b6c4d5e |
| Signal & Decision Journal | https://app.notion.com/p/c5081b3b94954636b260da2e1e399211 |
| Trade Journal | https://app.notion.com/p/d6fe9f768ce2428cbf3a45132d986cfc |
| Strategy Registry | https://app.notion.com/p/a76e12adc34b4ae48850ddb8bfe5acff |
| Daily Performance | https://app.notion.com/p/4e22c14d46af4be2910c5e2e066bcbcc |
| Weekly Review | https://app.notion.com/p/ac3d474d33204a71b1da8716ba845195 |
| Strategy Experiments | https://app.notion.com/p/11538c62f11d48719f83f201733cf269 |
| Incident Log | https://app.notion.com/p/d3476ca17e304b09ad1c63c866a1be4c |

### 32.2 NO_TRADE 原因碼 [建議]

| 原因碼 | 觸發階段 |
|---|---|
| `DATA_HEALTH_FAILED` | §3.4 |
| `REGIME_UNCERTAIN` | §5.5 |
| `NO_CANDIDATE_ABOVE_THRESHOLD` | §10.4 |
| `CRITIC_VETO` | §11 |
| `RR_INSUFFICIENT` | §12.1 |
| `STOP_UNREASONABLE` | §12.7 |
| `RISK_BUDGET_EXHAUSTED` | §13.3 |
| `MIN_ORDER_EXCEEDS_RISK` | §14.3 |
| `INSUFFICIENT_DEPTH` | §14.4 |
| `LIQUIDATION_TOO_CLOSE` | §15.6 |
| `GATE_FAILED:<gate_name>` | §16 |
| `POSITION_EXISTS` | §19.1 |
| `CIRCUIT_BREAKER:<name>` | §20 |
| `SAFE_MANAGEMENT_ACTIVE` | §18.4 |
| `OPERATOR_PAUSED` | §27.1 |
| `RELEASE_EXPIRED` | §21.3 |
| `APPROVAL_REQUIRED` | §21.5 |

### 32.3 狀態機總覽（系統層級）[建議]

```text
                ┌──────────────┐
                │   STOPPED    │
                └──────┬───────┘
                       │ operator start
                ┌──────▼───────┐
        ┌──────▶│   SCANNING   │◀──────────────┐
        │       └──────┬───────┘               │
        │              │ setup + all gates     │ position closed
        │       ┌──────▼───────┐               │ + reconciled
        │       │  EXECUTING   │               │
        │       └──────┬───────┘               │
        │              │ filled + protected    │
        │       ┌──────▼───────┐               │
        │       │  MANAGING    │───────────────┘
        │       └──────┬───────┘
        │              │ any breaker / protection lost
        │       ┌──────▼───────────┐
        │       │ SAFE_MANAGEMENT  │
        │       └──────┬───────────┘
        │              │ position = 0 + operator confirm
        └──────────────┘

 Kill Switch: 任何狀態 → SAFE_MANAGEMENT
 Emergency Close: 任何狀態 → SAFE_MANAGEMENT + reduce-only close all
 Release Expired / Mode downgrade: 任何狀態 → SCANNING (PAPER only)
```

### 32.4 最精簡版本 [已確認]

> 我想建立一套以 BTC 大市為先、用客觀數據掃描 Bybit USDT 永續合約、只選擇最高質素 Long 或 Short 機會、以固定 1% 本金風險及波動調整 1x／3x／5x 槓桿、確認真實成交及交易所止損、持續監控持倉、將所有決定寫入 Notion，並透過版本化實驗持續改善但永不自行修改 Live 策略嘅安全型自動交易作業系統。

---

*本文件為概念規格整理，非 Live 授權。任何 [候選] 或 [建議] 項目實施前必須經人工審批並記錄於 Strategy Registry。*
