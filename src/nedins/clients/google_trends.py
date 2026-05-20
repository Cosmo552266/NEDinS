"""Google Trends helper. M1 will wire pytrends; M0 returns canned data on dry-run."""
from __future__ import annotations

from dataclasses import dataclass

from nedins.config import is_dry_run


@dataclass
class TrendingTerm:
    term: str
    region: str
    score: int  # 0-100


class GoogleTrendsClient:
    def rising(self, seeds: list[str], region: str = "US", top_k: int = 10) -> list[TrendingTerm]:
        if is_dry_run():
            return [
                TrendingTerm(term=f"{s} {region}", region=region, score=80 - i * 5)
                for i, s in enumerate(seeds[:top_k])
            ]
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=0)
        out: list[TrendingTerm] = []
        for seed in seeds:
            pytrends.build_payload([seed], geo=region, timeframe="now 7-d")
            related = pytrends.related_queries().get(seed, {}).get("rising")
            if related is None:
                continue
            for _, row in related.head(top_k).iterrows():
                out.append(TrendingTerm(term=str(row["query"]), region=region, score=int(row["value"])))
        return out
