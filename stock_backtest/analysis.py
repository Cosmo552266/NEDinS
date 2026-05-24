"""Pre-backtest screening: per-symbol regime snapshot + cross-symbol ranks.

Output artefacts under ``reports/``:
- analysis_snapshot_{interval}.csv       raw per-symbol features
- analysis_corr_{interval}.csv           N x N correlation of 1-bar returns
- analysis_corr_{interval}.png           heatmap of the above
- analysis_dashboard_{interval}.md       readable summary + recommendations
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from .calendar import BARS_PER_YEAR_RTH


@dataclass
class AnalysisOutput:
    snapshot: pd.DataFrame
    corr: pd.DataFrame
    dashboard_md: str
    snapshot_csv: str
    corr_csv: str
    corr_png: str


def _snapshot_row(symbol: str, df: pd.DataFrame, interval: str) -> dict:
    last = df.iloc[-1]
    close = float(last["close"])
    rets = df["close"].pct_change().dropna()
    bpy = BARS_PER_YEAR_RTH[interval]
    realised_vol_ann = float(rets.std() * np.sqrt(bpy))
    # Daily change vs first bar of the last session
    last_day = df.index[-1].tz_convert("America/New_York").normalize()
    same_day = df.index.tz_convert("America/New_York").normalize() == last_day
    first_today = df.loc[same_day, "close"].iloc[0] if same_day.any() else df["close"].iloc[0]
    daily_change_pct = float(close / first_today - 1.0)

    atr_pct = float(last["atr_14"] / close) if close else float("nan")
    vwap_dist_pct = float((close - last["vwap"]) / close) if close else float("nan")

    hh30 = df["high"].tail(30).max()
    ll30 = df["low"].tail(30).min()
    near_high = abs(close / hh30 - 1.0) < 0.002
    near_low = abs(close / ll30 - 1.0) < 0.002

    return {
        "symbol": symbol,
        "price": round(close, 4),
        "daily_change_pct": round(daily_change_pct, 5),
        "realised_vol_ann": round(realised_vol_ann, 4),
        "atr_pct": round(atr_pct, 5),
        "rsi_14": round(float(last["rsi_14"]), 2),
        "vwap_dist_pct": round(vwap_dist_pct, 5),
        "vol_z_30": round(float(last["vol_z_30"]), 2),
        "mom_20": round(float(np.log(close / df["close"].iloc[-21])), 5) if len(df) > 21 else 0.0,
        "_ema_ratio": float(last["ema_50"] / last["ema_200"]) if last["ema_200"] else 1.0,
        "_near_high": bool(near_high),
        "_near_low": bool(near_low),
    }


def _ema_trend(ema_ratio: float) -> str:
    if ema_ratio > 1.04:
        return "strong_up"
    if ema_ratio > 1.005:
        return "up"
    if ema_ratio < 0.96:
        return "strong_down"
    if ema_ratio < 0.995:
        return "down"
    return "range"


def _classify(row: pd.Series, atr_median: float) -> tuple[str, str]:
    ema_ratio = row["_ema_ratio"]
    atr_pct = row["atr_pct"]
    vol_z = row["vol_z_30"]

    trend_strength = abs(ema_ratio - 1.0)
    is_trend = (trend_strength > 0.02) and (atr_pct > atr_median)
    is_breakout = (row["_near_high"] or row["_near_low"]) and (vol_z > 1.0)
    regime = "trend" if is_trend else ("breakout" if is_breakout else "range")

    # Recommend: breakout > pullback > mean-reversion (per plan)
    score_breakout = trend_strength * (atr_pct / 0.002) if regime in ("trend", "breakout") else 0.0
    if score_breakout > 0.5:
        rec = "ema_breakout"
    elif regime == "trend" and atr_pct < 0.0025:
        rec = "vwap_pullback"
    elif regime == "range" and atr_pct < atr_median:
        rec = "rsi_mean_reversion"
    else:
        rec = "vwap_pullback"  # default fallback
    return regime, rec


def _plot_corr(corr: pd.DataFrame, out_path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(max(5, 0.6 * len(corr)), max(4, 0.6 * len(corr))))
    im = ax.imshow(corr.values, vmin=-1, vmax=1, cmap="RdBu_r")
    ax.set_xticks(range(len(corr)))
    ax.set_yticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticklabels(corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iat[i, j]:.2f}",
                    ha="center", va="center", fontsize=8,
                    color="white" if abs(corr.iat[i, j]) > 0.5 else "black")
    fig.colorbar(im, ax=ax, shrink=0.7)
    ax.set_title("xStock 1-bar return correlation")
    fig.tight_layout()
    fig.savefig(out_path, dpi=130)
    import matplotlib.pyplot as _plt
    _plt.close(fig)


def analyze_universe(enriched: Dict[str, pd.DataFrame], interval: str,
                     out_dir: str = "reports", sources: Dict[str, str] | None = None) -> AnalysisOutput:
    os.makedirs(out_dir, exist_ok=True)
    sources = sources or {}

    rows: List[dict] = [_snapshot_row(s, df, interval) for s, df in enriched.items()]
    snap = pd.DataFrame(rows).set_index("symbol")
    atr_median = float(snap["atr_pct"].median())

    regimes, recs, trends = [], [], []
    for sym, row in snap.iterrows():
        regime, rec = _classify(row, atr_median)
        regimes.append(regime)
        recs.append(rec)
        trends.append(_ema_trend(row["_ema_ratio"]))
    snap["ema_trend"] = trends
    snap["regime"] = regimes
    snap["recommended_strategy"] = recs

    public_cols = ["price", "daily_change_pct", "realised_vol_ann", "atr_pct",
                   "rsi_14", "vwap_dist_pct", "vol_z_30", "mom_20",
                   "ema_trend", "regime", "recommended_strategy"]
    snap_public = snap[public_cols]

    snapshot_csv = os.path.join(out_dir, f"analysis_snapshot_{interval}.csv")
    snap_public.to_csv(snapshot_csv)

    closes = pd.DataFrame({s: df["close"] for s, df in enriched.items()})
    rets = closes.pct_change().dropna(how="all")
    corr = rets.corr().round(3)
    corr_csv = os.path.join(out_dir, f"analysis_corr_{interval}.csv")
    corr.to_csv(corr_csv)
    corr_png = os.path.join(out_dir, f"analysis_corr_{interval}.png")
    _plot_corr(corr, corr_png)

    dashboard_md = _write_dashboard(snap_public, corr, interval, out_dir,
                                    corr_png, sources)
    return AnalysisOutput(snapshot=snap_public, corr=corr, dashboard_md=dashboard_md,
                          snapshot_csv=snapshot_csv, corr_csv=corr_csv, corr_png=corr_png)


def _write_dashboard(snap: pd.DataFrame, corr: pd.DataFrame, interval: str,
                     out_dir: str, corr_png: str, sources: Dict[str, str]) -> str:
    lines: list[str] = []
    lines.append(f"# xStocks pre-trade analysis ({interval})")
    lines.append("")
    lines.append("> **Caveat.** xStocks trade 24/7 on Bybit; the underlying US equities trade "
                 "09:30-16:00 ET. This backtest uses the underlying as a price proxy and **understates** "
                 "off-hours risk and NAV-premium/discount churn. The `ema_breakout` strategy in particular "
                 "overstates edge because real overnight gaps on the token are partially priced in.")
    lines.append("")
    if sources:
        src_summary = ", ".join(f"{s}={src}" for s, src in sources.items())
        lines.append(f"- Data sources: {src_summary}")
    lines.append("")
    lines.append("## Per-symbol snapshot")
    lines.append("")
    fmt = snap.copy()
    for c in ("daily_change_pct", "atr_pct", "vwap_dist_pct", "mom_20"):
        fmt[c] = (fmt[c] * 100).map(lambda x: f"{x:+.2f}%")
    fmt["realised_vol_ann"] = (fmt["realised_vol_ann"] * 100).map(lambda x: f"{x:.1f}%")
    lines.append(fmt.to_markdown())
    lines.append("")

    lines.append("## Ranked sub-tables (top 5)")
    lines.append("")
    for label, col, asc in [
        ("Highest realised vol", "realised_vol_ann", False),
        ("Strongest 20-bar momentum", "mom_20", False),
        ("Largest VWAP distance (|abs|)", "vwap_dist_pct", False),
        ("Most stretched RSI (|rsi - 50|)", "rsi_14", False),
    ]:
        if col == "vwap_dist_pct":
            ranked = snap.assign(_k=snap[col].abs()).sort_values("_k", ascending=asc).head(5)[["price", col]]
        elif col == "rsi_14":
            ranked = snap.assign(_k=(snap[col] - 50).abs()).sort_values("_k", ascending=asc).head(5)[["price", col]]
        else:
            ranked = snap.sort_values(col, ascending=asc).head(5)[["price", col]]
        lines.append(f"**{label}**")
        lines.append("")
        lines.append(ranked.to_markdown())
        lines.append("")

    lines.append("## Correlation matrix")
    lines.append("")
    lines.append(f"![correlation heatmap]({os.path.basename(corr_png)})")
    lines.append("")
    lines.append(corr.to_markdown())
    lines.append("")

    lines.append("## Strategy recommendations")
    lines.append("")
    grouped = snap.groupby("recommended_strategy").apply(lambda g: ", ".join(g.index))
    for strat, syms in grouped.items():
        lines.append(f"- **{strat}**: {syms}")
    lines.append("")

    path = os.path.join(out_dir, f"analysis_dashboard_{interval}.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path
