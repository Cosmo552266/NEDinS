"""Break a story into scenes with image prompts + narration lines."""
from __future__ import annotations

import json

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import Scene, Story
from nedins.models.schemas import Storyboard as StoryboardModel
from nedins.prompts.templates import STORYBOARD_PROMPT
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

        prompt = STORYBOARD_PROMPT.format(
            story_zh=story.body_zh, story_en=story.body_en,
            scenes_min=self.cfg["scenes_min"], scenes_max=self.cfg["scenes_max"],
            style=self.style,
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
