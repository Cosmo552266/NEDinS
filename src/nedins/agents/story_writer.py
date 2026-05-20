"""Write a bilingual adult-suspense short story from a Theme."""
from __future__ import annotations

import json
import re

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import KeyVisual, Story, Theme
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
        prompt_zh = (
            f"主題：{theme.title}\n推介語：{theme.pitch}\n關鍵字：{theme.keywords}\n\n"
            f"請寫一篇 {self.cfg['target_word_count_zh']} 字嘅繁體中文成人懸疑短篇小說，"
            f"風格：{self.cfg['tone']}。\n"
            "結構：強 hook 開場 → 鋪陳 → 中段轉折 → 開放式結尾。\n"
            "第一行用 `# 標題` 寫出標題。"
        )
        zh = self.gemini.generate_text(
            prompt_zh, model=self.cfg["gemini_model"],
            system="你係一位專寫成人懸疑短篇嘅小說家，文字含蓄克制，重氣氛多於血腥。",
        ).text

        # ---- EN localization rewrite ----
        prompt_en = (
            "Translate-and-localize the following Traditional Chinese suspense short story "
            "into English for a Western adult audience. Preserve tension, but adapt cultural "
            "references. Keep `# Title` on the first line.\n\n"
            f"---\n{zh}\n---"
        )
        en = self.gemini.generate_text(prompt_en, model=self.cfg["gemini_model"]).text

        # ---- Key visuals ----
        kv_prompt = (
            f"以下故事：\n{zh}\n\n"
            f"請抽出 {self.cfg['key_visual_count']} 個「視覺記憶點」，每個包含 label / description / "
            "pod_friendly (boolean，呢個畫面適唔適合印成 T-shirt 或 poster)。輸出 JSON list。"
        )
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
