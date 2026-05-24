"""Tokenized US stock (xStocks) analysis + backtest layer.

Reuses ``btc_backtest`` engine modules (indicators, backtest, report) and
overrides only the asset-specific surfaces (fetcher, calendar, strategy
defaults). Universe is restricted to xStocks listed on Bybit.
"""
