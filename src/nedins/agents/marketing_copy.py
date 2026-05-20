"""Generate IG / X / TikTok / FB captions in both locales."""
from __future__ import annotations

import json

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import MarketingCopy, Story
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

        prompt = (
            f"故事標題 (中)：{story.title_zh}\n標題 (EN)：{story.title_en}\n"
            f"主題：{story.theme.title}\n關鍵字：{story.theme.keywords}\n\n"
            f"請為以下平台寫宣傳文案 (繁中 + 英文)：{self.cfg['platforms']}。"
            f"每個 caption 結尾附 {self.cfg['hashtag_count']} 個 hashtag (整體共用一份)。"
            "輸出 JSON 鍵：instagram_zh, instagram_en, x_zh, x_en, tiktok_hook_zh, "
            "tiktok_hook_en, facebook_zh, facebook_en, hashtags (list of str)。"
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
