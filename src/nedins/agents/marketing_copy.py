"""Generate IG / X / TikTok / FB captions in both locales."""
from __future__ import annotations

import json

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import MarketingCopy, Story
from nedins.prompts.templates import MARKETING_PROMPT
from nedins.storage.artifacts import campaign_root


class MarketingCopyAgent:
    name = "marketing_copy"

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.cfg = load_settings()["marketing"]

    def run(self, campaign_id: str, story: Story) -> MarketingCopy:
        out = campaign_root(campaign_id) / "marketing.json"
        if out.exists():
            return MarketingCopy.model_validate_json(out.read_text(encoding="utf-8"))

        prompt = MARKETING_PROMPT.format(
            title_zh=story.title_zh, title_en=story.title_en,
            theme=story.theme.title, keywords=story.theme.keywords,
            pitch=story.theme.pitch,
            platforms=self.cfg["platforms"], hashtag_count=self.cfg["hashtag_count"],
        )
        resp = self.gemini.generate_text(prompt, json_mode=True)
        try:
            data = json.loads(resp.text)
            copy = MarketingCopy(**data)
        except Exception:
            copy = MarketingCopy(
                instagram_zh=f"{story.title_zh}｜成人懸疑短篇，今晚十點上線。",
                instagram_en=f"{story.title_en}: a suspense short. Tonight 10pm.",
                x_zh=f"#{story.title_zh} 你敢一個人睇？",
                x_en=f"{story.title_en} — would you watch this alone?",
                tiktok_hook_zh="如果電梯第 14 樓嘅鍵突然著……",
                tiktok_hook_en="If the 14th-floor elevator button lights up by itself…",
                facebook_zh=f"全新短篇《{story.title_zh}》上線。",
                facebook_en=f"New short: {story.title_en}.",
                hashtags=["#懸疑", "#都市傳說", "#鬼故事", "#suspense", "#urbanlegend",
                          "#shortfilm", "#booktok", "#thrillertok"][: self.cfg["hashtag_count"]],
            )
        out.write_text(copy.model_dump_json(indent=2), encoding="utf-8")
        return copy
