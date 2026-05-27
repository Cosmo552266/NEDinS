# Bybit Funding Arb Toolkit — 用家指南

呢個 repo 係用嚟學 + 試 **Bybit delta-neutral funding rate arbitrage** 嘅工具箱。冇用真錢，全部係 paper trading + 公開市場數據。

## 4 個工具一覽

| # | 工具 | 用途 | 入口 |
|---|---|---|---|
| 1 | **Scanner** | Real-time scan Bybit 所有 USDT perp 嘅 funding rate，揀最高 | `python -m bybit_toolkit.scanner` |
| 2 | **Paper Trader** | 模擬 delta-neutral 開倉、收 funding、平倉，計 P&L | `python -m bybit_toolkit.paper_trader` |
| 3 | **Portfolio Tracker** | 追蹤多策略組合、計 Sharpe / drawdown / CAGR | `python -m bybit_toolkit.portfolio` |
| 4 | **Sheet Template** | 手動記錄交易嘅 CSV + Google Sheets formula | `templates/` |

## 安裝

```bash
pip install -r requirements.txt
```

只需要 `requests`。Python 3.10+。

---

## 1. Scanner — Funding Rate 排行榜

### 基本用法
```bash
# 即時 scan，揀 funding 最高嘅 15 個 perp（成交量 > 10M USD）
python -m bybit_toolkit.scanner

# 揀 top 20，最低成交量 5M
python -m bybit_toolkit.scanner --top 20 --min-volume 5000000

# 加埋過去 30 期平均 funding（睇邊個係持續高 vs 暫時高）
python -m bybit_toolkit.scanner --history

# 估算 200 USD 倉位每年收幾多
python -m bybit_toolkit.scanner --estimate 200

# 冇 internet / 想睇個 output 樣：用 sample data
python -m bybit_toolkit.scanner --demo
```

### Output 點睇

```
Symbol         Funding 8h  APR (now)  Next in   Mark         Spread bps  Vol 24h
WIFUSDT        0.1250%     136.9%      3.50h   1.229           16.26    $75.0M
FETUSDT        0.0980%     107.3%      3.50h   1.149            1.74    $80.0M
```

- **Funding 8h**：而家嘅 funding rate（每 8 小時收 / 俾一次）
- **APR (now)**：年化（× 3 × 365），假設 funding 唔變
- **Next in**：距離下次 funding 結算嘅時間
- **Spread bps**：bid/ask spread。**> 10 bps 嘅要小心**，平倉時會蝕呢個 spread
- **Vol 24h**：流動性。太低嘅 perp 唔好掂

### 揀邊個交易？
1. **funding > 0.02% / 8h**（年化 > 22%）
2. **spread < 10 bps**
3. **volume > 50M**
4. **過去 30 期平均 funding 都係正**（用 `--history` 睇）

如果同時滿足 4 項，就係 funding arb 嘅 candidate。

---

## 2. Paper Trader — 唔使真錢試 delta-neutral

### 完整 workflow 例子

```bash
# 開倉：BTCUSDT，200 USD per leg（spot long + perp short）
python -m bybit_toolkit.paper_trader open BTCUSDT --notional 200

# 過 8 小時後，credit 一次 funding payment
python -m bybit_toolkit.paper_trader tick

# 隨時睇狀態
python -m bybit_toolkit.paper_trader status

# 平倉
python -m bybit_toolkit.paper_trader close 1

# 全部 reset 重新嚟
python -m bybit_toolkit.paper_trader reset
```

### 快速模擬（唔等 wall-clock）

```bash
# 開倉
python -m bybit_toolkit.paper_trader open BTCUSDT --notional 200 --demo

# 模擬已經過咗 7 日（21 次 funding）
python -m bybit_toolkit.paper_trader tick --simulate-hours 168

# 睇結果
python -m bybit_toolkit.paper_trader status
```

### 細節
- 預設手續費 **4 bps per leg**（spot taker 0.1% × 0.5 + perp taker 0.055% 嘅 mix 估算）。用 `--fee-bps` 改
- 兩條腿都食 fee → 入場、平倉各 8 bps 總成本
- Funding 用 scan 時嘅 rate × notional × ticks 計
- 全部 state 寫入 `bybit_toolkit/data/paper_state.json`（gitignored）

### 學嘢角度
跑佢 30-90 日，你會親身體驗到：
- 「funding rate 高」唔等於「淨賺多」（fees 食晒）
- Funding rate 會跌（牛市初期高，後期降）
- 細 notional + 高 fee% 嘅幣，breakeven 都做唔到

---

## 3. Portfolio Tracker — 多策略管理

### 第一次設定

```bash
python -m bybit_toolkit.portfolio init
```

會 generate `bybit_toolkit/data/portfolio.json`，預設 60/25/10/5 split（funding_arb / earn_flexi / btc_hold / cash）。

打開個 file 改 `current_usd`：

```json
{
  "sleeves": [
    {"name": "funding_arb", "target_pct": 60, "current_usd": 580.0, ...},
    {"name": "earn_flexi",  "target_pct": 25, "current_usd": 280.0, ...},
    {"name": "btc_hold",    "target_pct": 10, "current_usd": 95.0,  ...},
    {"name": "cash_buffer", "target_pct":  5, "current_usd": 45.0,  ...}
  ]
}
```

### 睇配置 + rebalance 建議

```bash
python -m bybit_toolkit.portfolio show
```

```
Sleeve            Target  Current           USD     Drift     Rebalance
funding_arb        60.0%    58.0%       $580.00     -2.0%   BUY $  20.00
earn_flexi         25.0%    28.0%       $280.00     +3.0%   SELL$  30.00
```

### 每日記 equity（計 Sharpe 用）

```bash
# 從 portfolio.json 自動加總
python -m bybit_toolkit.portfolio log

# 或者手動 override
python -m bybit_toolkit.portfolio log --equity 1027.50
```

### 計指標

```bash
python -m bybit_toolkit.portfolio metrics
```

```
Equity metrics  2026-04-01 -> 2026-05-30  (59 days)
  Start equity:      $1,000.40
  End equity:        $1,027.36
  Total return:      +2.69%
  CAGR (annualized): +17.88%
  Sharpe ratio:      3.02
  Max drawdown:      -2.37%
```

**目標**：CAGR 10-20%，Sharpe > 1.5，Max drawdown < 10%。如果 Sharpe < 0.5 即係 returns 都係 random，唔係 edge。

---

## 4. Sheet Template

睇 `templates/SHEET_GUIDE.md`。

最簡單嘅做法：每筆交易記一行，每日 5 分鐘 update。3 個月之後你會見到自己嘅 pattern。

---

## 建議學習路徑

**Week 1-2**: 跑 scanner，每日睇幾次 funding rates，熟悉邊啲幣常高 / 常低  
**Week 3-4**: 用 paper trader 開 3-5 個倉，等 simulate funding payments，睇 P&L  
**Week 5-8**: 用 portfolio tracker init 一個假倉，每日 log，月尾睇 metrics  
**Month 3+**: Bybit 開 demo trading（佢 native 有，唔係呢個 repo 嘅 paper），同時手動填 sheet  
**Month 6+**: 細注實戰（< $100），仲要繼續記 sheet  
**Month 12+**: 評估有冇真 edge，先決定加大本金 or 加自動化

## 重要警告

1. **呢套工具 != 賺錢工具**。佢只係教學 + 紀錄。真正賺錢嘅係**你嘅紀律 + 你嘅本金**
2. **唔好用 leverage > 3x**。爆倉一次，幾個月嘅 funding 都係白做
3. **Bybit 集中風險**：賺到嘅錢定期 withdraw 去 cold wallet
4. **澳洲稅**：每筆交易係 CGT event，由 Day 1 開始記錄
5. **Funding 可以變負**：永遠寫定 exit rule，唔好死揸
