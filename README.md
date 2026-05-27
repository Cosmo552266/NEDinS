# Bybit Funding Arb Toolkit

Bybit-only delta-neutral funding rate arbitrage 嘅學習 / 紀錄工具箱。**Paper trading + 公開市場數據**，唔涉及真錢交易。

> ⚠️ 本 repo 唔係投資建議。Crypto 交易有極高風險，包括可以蝕清本金。

## 4 個工具

```
bybit_toolkit/
├── scanner.py       # 1. Real-time funding rate scanner
├── paper_trader.py  # 2. 模擬 delta-neutral 開倉 / 收 funding / 平倉
├── portfolio.py     # 3. 多策略 portfolio + Sharpe / drawdown
├── bybit_api.py     # 共用 Bybit public API client
└── fixtures.py      # 離線 sample data (--demo mode)

templates/
├── trade_log_template.csv   # 4. CSV 交易紀錄模板
└── SHEET_GUIDE.md           # Google Sheets formula 指南

docs/
└── GUIDE.md         # 詳細用家指南（粵語）
```

## Quick Start

```bash
pip install -r requirements.txt

# Scan 即時 funding rates
python -m bybit_toolkit.scanner --top 15

# 開一個 paper 倉
python -m bybit_toolkit.paper_trader open BTCUSDT --notional 200

# 過 8 小時後 credit funding
python -m bybit_toolkit.paper_trader tick

# 睇狀態
python -m bybit_toolkit.paper_trader status

# 初始化 portfolio
python -m bybit_toolkit.portfolio init
python -m bybit_toolkit.portfolio show
```

冇 internet？所有 command 加 `--demo` 用 fixture data：

```bash
python -m bybit_toolkit.scanner --demo --top 10 --estimate 500
python -m bybit_toolkit.paper_trader open BTCUSDT --notional 200 --demo
```

## 學習路徑

詳見 [`docs/GUIDE.md`](docs/GUIDE.md)。簡要：

1. **Week 1-2**：跑 scanner 熟悉市場
2. **Month 1**：用 paper trader 開幾個倉，simulate funding
3. **Month 2-3**：portfolio tracker init，每日 log equity，月尾睇 metrics
4. **Month 3-6**：Bybit native demo trading + 手填 sheet
5. **Month 6+**：細注實戰（< $100），continue 記錄
6. **Year 1+**：評估真有冇 edge，先考慮加碼

## 點解 delta-neutral funding arb？

- ✅ Edge 來源**結構性**（perp 同 spot 嘅利率差），唔靠預測升跌
- ✅ Retail 攞得到（唔需要 HFT 速度）
- ✅ 風險可量化（爆倉風險 = leverage 嘅 function）
- ✅ 歷史平均 10-20% APR 喺合理 leverage 下

## 點解唔啱？

- ❌ 想短期暴富（funding arb 唔會令 $100 一個月變 $200）
- ❌ 唔做 record（無紀律會搵藉口跳出 neutral，變賭博）
- ❌ 用全副身家入（platform risk、爆倉風險都需要 buffer）
- ❌ 認為「自動化 = 賺錢」（自動化 = 執行你已知有 edge 嘅嘢，冇 edge 就係自動蝕錢）

## License

MIT
