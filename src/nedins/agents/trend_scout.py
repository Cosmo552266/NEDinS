"""Pick a campaign theme from Google Trends + upcoming holidays + historical priors."""
from __future__ import annotations

import json
from datetime import date, timedelta

import holidays

from nedins.clients.gemini import GeminiClient
from nedins.clients.google_trends import GoogleTrendsClient
from nedins.config import load_settings
from nedins.models import Theme
from nedins.prompts.templates import TREND_SCOUT_SYSTEM, TREND_SCOUT_USER
from nedins.storage.artifacts import campaign_root


class TrendScout:
    name = "trend_scout"

    def __init__(self, gemini: GeminiClient | None = None,
                 trends: GoogleTrendsClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.trends = trends or GoogleTrendsClient()
        self.cfg = load_settings()["trend_scout"]

    def run(self, campaign_id: str, *, target_date: date) -> Theme:
        out = campaign_root(campaign_id) / "theme.json"
        if out.exists():
            return Theme.model_validate_json(out.read_text(encoding="utf-8"))

        upcoming = self._upcoming_holidays(target_date)
        rising_en = self.trends.rising(self.cfg["pytrends_keywords_en"], region="US", top_k=5)
        rising_zh = self.trends.rising(self.cfg["pytrends_keywords_zh"], region="HK", top_k=5)

        prompt = TREND_SCOUT_USER.format(
            today=target_date.isoformat(),
            holidays=[(str(d), n) for d, n in upcoming] or "（未來 30 日冇主要節日）",
            rising_en=[t.term for t in rising_en],
            rising_zh=[t.term for t in rising_zh],
            priors="（M4 之前未有 prior 數據）",
            topics="、".join(self.cfg["topics"]),
        )
        resp = self.gemini.generate_text(prompt, json_mode=True,
                                         system=TREND_SCOUT_SYSTEM)
        theme = self._parse_or_fallback(resp.text, upcoming, rising_en, rising_zh)
        out.write_text(theme.model_dump_json(indent=2), encoding="utf-8")
        return theme

    def _upcoming_holidays(self, today: date) -> list[tuple[date, str]]:
        lookahead = self.cfg["holiday_lookahead_days"]
        end = today + timedelta(days=lookahead)
        merged: dict[date, str] = {}
        for h in [holidays.HK(years=[today.year, today.year + 1]),
                  holidays.TW(years=[today.year, today.year + 1]),
                  holidays.US(years=[today.year, today.year + 1])]:
            for d, name in h.items():
                if today <= d <= end:
                    merged[d] = name if d not in merged else f"{merged[d]} / {name}"
        return sorted(merged.items())

    def _parse_or_fallback(self, text: str, upcoming, rising_en, rising_zh) -> Theme:
        try:
            data = json.loads(text)
            return Theme(**data)
        except Exception:
            # M0 fallback so dry-run always returns something usable.
            seed = upcoming[0][1] if upcoming else (rising_zh[0].term if rising_zh else "電梯怪談")
            return Theme(
                title=f"懸疑短篇：{seed}",
                pitch=f"圍繞「{seed}」嘅都市傳說，成人向心理懸疑。",
                source="holiday" if upcoming else "google_trends",
                source_detail=str(upcoming[0]) if upcoming else "rising query fallback",
                keywords=[seed] + [t.term for t in rising_zh[:3]],
                holiday=upcoming[0][1] if upcoming else None,
                backup_pitches=[f"備胎：{t.term}" for t in rising_en[:3]],
            )
