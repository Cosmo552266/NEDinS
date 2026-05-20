"""Break a story into scenes with image prompts + narration lines."""
from __future__ import annotations

import json

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import Scene, Story
from nedins.models.schemas import Storyboard as StoryboardModel
from nedins.storage.artifacts import campaign_root


class Storyboard:
    name = "storyboard"

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.cfg = load_settings()["storyboard"]
        self.style = load_settings()["image_generator"]["style"]

    def run(self, campaign_id: str, story: Story) -> StoryboardModel:
        out = campaign_root(campaign_id) / "storyboard.json"
        if out.exists():
            return StoryboardModel.model_validate_json(out.read_text(encoding="utf-8"))

        prompt = (
            f"故事 (繁中)：\n{story.body_zh}\n\n"
            f"故事 (EN)：\n{story.body_en}\n\n"
            f"請拆成 {self.cfg['scenes_min']}–{self.cfg['scenes_max']} 個場景，輸出 JSON：\n"
            "{\n"
            '  "cover_prompt": "封面英文 prompt (16:9)",\n'
            '  "scenes": [\n'
            "    {\n"
            '      "index": 1,\n'
            '      "narration_zh": "繁中旁白 1-2 句",\n'
            '      "narration_en": "EN narration 1-2 sentences",\n'
            '      "visual_prompt": "Imagen 用英文 prompt，加入風格修飾",\n'
            '      "duration_sec": 8.0,\n'
            '      "pod_friendly": false\n'
            "    }, ...\n"
            "  ]\n"
            "}\n"
            f"視覺風格 prefix 必須係：「{self.style}」"
        )
        resp = self.gemini.generate_text(prompt, json_mode=True,
                                         model=self.cfg["gemini_model"])
        try:
            data = json.loads(resp.text)
            scenes = [Scene(**s) for s in data["scenes"]]
            cover_prompt = data["cover_prompt"]
        except Exception:
            scenes = [
                Scene(index=i + 1,
                      narration_zh=f"場景 {i+1}（mock）",
                      narration_en=f"Scene {i+1} (mock)",
                      visual_prompt=f"{self.style}, mock scene {i+1}",
                      duration_sec=8.0,
                      pod_friendly=(i == 0))
                for i in range(self.cfg["scenes_min"])
            ]
            cover_prompt = f"{self.style}, cover art for {story.title_en}"

        board = StoryboardModel(scenes=scenes, cover_prompt=cover_prompt)
        out.write_text(board.model_dump_json(indent=2), encoding="utf-8")
        return board
