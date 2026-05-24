# BTC/USDT 5m backtest report

- Data source: **synthetic**
- Bars analysed: **1000**

## Headline metrics

| name               |   bars |   trades | win_rate   | avg_win_pct   | avg_loss_pct   |   profit_factor | expectancy_pct   | total_return_pct   | max_drawdown_pct   |   sharpe |   avg_bars_held |
|:-------------------|-------:|---------:|:-----------|:--------------|:---------------|----------------:|:-----------------|:-------------------|:-------------------|---------:|----------------:|
| vwap_pullback      |   1000 |        7 | 0.00%      | 0.000%        | -0.570%        |            0    | -0.570%          | -3.95%             | -3.95%             |   -19.63 |             8.6 |
| ema_breakout       |   1000 |       33 | 18.18%     | 0.695%        | -0.614%        |            0.25 | -0.376%          | -11.70%            | -14.22%            |   -24.74 |            12   |
| rsi_mean_reversion |   1000 |        0 | 0.00%      | 0.000%        | 0.000%         |            0    | 0.000%           | 0.00%              | 0.00%              |     0    |             0   |

![equity curves](equity_5m.png)

## vwap_pullback

- Trades: **7**  |  Win rate: **0.00%**  |  Profit factor: **0.00**  |  Max DD: **-3.95%**
- Total return: **-3.95%**  |  Expectancy/trade: **-0.570%**  |  Sharpe (annualised): **-19.63**

## ema_breakout

- Trades: **33**  |  Win rate: **18.18%**  |  Profit factor: **0.25**  |  Max DD: **-14.22%**
- Total return: **-11.70%**  |  Expectancy/trade: **-0.376%**  |  Sharpe (annualised): **-24.74**

## rsi_mean_reversion

- Trades: **0**  |  Win rate: **0.00%**  |  Profit factor: **0.00**  |  Max DD: **0.00%**
- Total return: **0.00%**  |  Expectancy/trade: **0.000%**  |  Sharpe (annualised): **0.00**
