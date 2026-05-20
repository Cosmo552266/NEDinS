"""Write a bilingual adult-suspense short story from a Theme."""
from __future__ import annotations

import json
import re

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import KeyVisual, Story, Theme
from nedins.prompts.templates import (
    KEY_VISUALS_PROMPT, STORY_WRITER_EN_LOCALIZE, STORY_WRITER_SYSTEM, STORY_WRITER_ZH,
)
from nedins.storage.artifacts import campaign_root


class StoryWriter:
    name = "story_writer"

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.cfg = load_settings()["story_writer"]

    def run(self, campaign_id: str, theme: Theme) -> Story:
        root = campaign_root(campaign_id)
        zh_path = root / "story_zh.md"
        en_path = root / "story_en.md"
        kv_path = root / "key_visuals.json"
        if zh_path.exists() and en_path.exists() and kv_path.exists():
            return Story(
                theme=theme,
                body_zh=zh_path.read_text(encoding="utf-8"),
                body_en=en_path.read_text(encoding="utf-8"),
                title_zh=_first_h1(zh_path.read_text(encoding="utf-8")) or theme.title,
                title_en=_first_h1(en_path.read_text(encoding="utf-8")) or theme.title,
                key_visuals=[KeyVisual(**kv) for kv in json.loads(kv_path.read_text())],
                word_count_zh=len(zh_path.read_text(encoding="utf-8")),
                word_count_en=len(en_path.read_text(encoding="utf-8").split()),
            )

        # ---- ZH first ----
        prompt_zh = STORY_WRITER_ZH.format(
            title=theme.title, pitch=theme.pitch,
            keywords=theme.keywords, holiday=theme.holiday or "（無）",
            word_count=self.cfg["target_word_count_zh"],
        )
        zh = self.gemini.generate_text(
            prompt_zh, model=self.cfg["gemini_model"], system=STORY_WRITER_SYSTEM,
        ).text

        # ---- EN localization rewrite ----
        prompt_en = STORY_WRITER_EN_LOCALIZE.format(zh_story=zh)
        en = self.gemini.generate_text(prompt_en, model=self.cfg["gemini_model"]).text

        # ---- Key visuals ----
        kv_prompt = KEY_VISUALS_PROMPT.format(story=zh, count=self.cfg["key_visual_count"])
        kv_text = self.gemini.generate_text(kv_prompt, json_mode=True,
                                            model=self.cfg["gemini_model"]).text
        try:
            kv_data = json.loads(kv_text)
            key_visuals = [KeyVisual(**kv) for kv in kv_data]
        except Exception:
            key_visuals = [KeyVisual(label=f"visual {i+1}",
                                     description="placeholder", pod_friendly=(i == 0))
                           for i in range(self.cfg["key_visual_count"])]

        zh_path.write_text(zh, encoding="utf-8")
        en_path.write_text(en, encoding="utf-8")
        kv_path.write_text(json.dumps([kv.model_dump() for kv in key_visuals],
                                      ensure_ascii=False, indent=2), encoding="utf-8")

        return Story(
            theme=theme, body_zh=zh, body_en=en,
            title_zh=_first_h1(zh) or theme.title,
            title_en=_first_h1(en) or theme.title,
            key_visuals=key_visuals,
            word_count_zh=len(zh),
            word_count_en=len(en.split()),
        )


def _first_h1(md: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else None
