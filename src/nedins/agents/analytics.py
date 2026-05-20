"""Collect YouTube + Printify metrics back into theme_priors. (M4)"""
from __future__ import annotations

from datetime import date

from nedins.storage.artifacts import theme_priors_db


class Analytics:
    name = "analytics"

    def snapshot(self, today: date | None = None) -> None:
        """Pull metrics for all past campaigns and upsert into DuckDB.

        Schema (M4):
          campaigns(id PK, target_date, theme_keywords, holiday, source)
          metrics(campaign_id FK, yt_views, yt_watch_min, yt_ctr,
                  pod_orders, pod_revenue, captured_at)
          theme_priors(keyword PK, roi_score, sample_count, updated_at)
        """
        _ = theme_priors_db()  # ensures dir
        # TODO: implement in M4
        raise NotImplementedError("Analytics agent lands in M4")
