# Trade Log Sheet — 手動記錄模板

最低門檻版：唔寫程式都可以開始。`trade_log_template.csv` 直接 import 入 Google Sheets / Excel，跟住加 formula 自動計 KPI。

## 欄位定義

| 欄 | 意思 | 例子 |
|---|---|---|
| `date` | 開倉或事件日期 | `2026-01-15` |
| `symbol` | 交易對 | `BTCUSDT` |
| `side` | `delta_neutral` / `long` / `short` / `lend` / `buy` / `sell` | `delta_neutral` |
| `strategy` | `funding_arb` / `earn_flexi` / `btc_hold` / `cash_buffer` | `funding_arb` |
| `notional_usd` | 倉位 USD 大小（per leg） | `200.00` |
| `entry_price` | 開倉價（mid） | `102345.0` |
| `exit_price` | 平倉價，未平就留空 | `103120.0` |
| `qty` | 數量（base units） | `0.001954` |
| `funding_received_usd` | 累積收到 funding | `0.504` |
| `fees_usd` | 累積手續費 | `0.32` |
| `net_pnl_usd` | `funding_received_usd - fees_usd` | `0.184` |
| `holding_hours` | 持倉小時數 | `168` |
| `notes` | 自由文字 | `closed after 1 week` |

## 必加 Formula（Google Sheets）

假設第 2 行係 header，data 由第 3 行開始。建議新增以下 cells / sheet：

### 1. Auto-fill `net_pnl_usd` (column K)
```
=I3 - J3
```
（`funding_received_usd` 減 `fees_usd`）

### 2. Realized APR per trade (新欄 L)
```
=IF(L3>0, K3 / E3 / (L3/24) * 365, "")
```
即 `net_pnl / notional / days * 365`

### 3. Strategy 總結（另開 sheet「Summary」）

| Strategy | Total Net PnL | Trade Count | Avg APR |
|---|---|---|---|
| funding_arb | `=SUMIF(Trades!D:D,"funding_arb",Trades!K:K)` | `=COUNTIF(Trades!D:D,"funding_arb")` | `=AVERAGEIFS(...)` |
| earn_flexi | similar | similar | similar |
| btc_hold | similar | similar | similar |

### 4. Equity Curve（另開 sheet「Equity」）

Column A: date  
Column B: total equity (手動填，或 `=SUMIFS` 加埋仲開倉嘅 notional + 已平嘅 net_pnl 累積）  
Insert → Chart → Line chart  
睇住條線斜唔斜，比任何指標都直觀。

### 5. 監察 funding payment 規律
新欄 N (`funding_per_day`)：
```
=IF(L3>0, I3 / (L3/24), "")
```
睇你每日平均收幾多 funding，估下 forward APR。

## Excel 對應 Formula

語法一樣，只係 `IF`、`SUMIF`、`COUNTIF`、`AVERAGEIFS` 通用。

## 工作流程（每日 5 分鐘）

1. **開倉時**：填新一行（exit_price、funding、fees 空住）
2. **每日**：update `funding_received_usd`、`fees_usd`（喺 Bybit App → Funding Fee History 對數）
3. **平倉時**：填 `exit_price`、`holding_hours`，net_pnl 自動算
4. **每週**：睇 Summary sheet，計唔同 strategy 表現
5. **每月**：export CSV → 餵俾 `bybit_toolkit.portfolio metrics` 計 Sharpe / drawdown

## 進階：連結 Bybit API（之後再做）

當你想自動化呢個 sheet：
- Google Apps Script + Bybit public API → 每小時自動 update funding rate
- 或者用 `bybit_toolkit/portfolio.py log` 每日寫一行 equity，再 import CSV 入 sheet

但 **first 3-6 個月一定要手動填**，原因：
1. 強迫你對每筆交易有 awareness
2. 發現自己重複犯嘅錯（emotional trade、追高、忘記 funding 轉負）
3. 累積真實數據，將來自動化先有 baseline 對比
