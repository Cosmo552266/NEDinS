"""Generate cover + per-scene + POD images via Imagen."""
from __future__ import annotations

from pathlib import Path

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models import Story
from nedins.models.schemas import Storyboard as StoryboardModel
from nedins.storage.artifacts import subdir


class ImageGenerator:
    name = "image_generator"

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.cfg = load_settings()["image_generator"]

    def run(self, campaign_id: str, story: Story,
            board: StoryboardModel) -> dict[str, Path]:
        images_dir = subdir(campaign_id, "images")
        pod_dir = subdir(campaign_id, "images/pod")

        cover_zh = images_dir / "cover_zh.png"
        cover_en = images_dir / "cover_en.png"
        self.gemini.generate_image(
            f"{board.cover_prompt}, title text: '{story.title_zh}'",
            out_path=cover_zh, model=self.cfg["imagen_model"],
            aspect_ratio=self.cfg["cover_aspect"],
        )
        self.gemini.generate_image(
            f"{board.cover_prompt}, title text: '{story.title_en}'",
            out_path=cover_en, model=self.cfg["imagen_model"],
            aspect_ratio=self.cfg["cover_aspect"],
        )

        for scene in board.scenes:
            scene_path = images_dir / f"scene_{scene.index:02d}.png"
            self.gemini.generate_image(
                scene.visual_prompt, out_path=scene_path,
                model=self.cfg["imagen_model"],
                aspect_ratio=self.cfg["scene_aspect"],
            )
            scene.image_path = scene_path

            if scene.pod_friendly:
                pod_path = pod_dir / f"scene_{scene.index:02d}_pod.png"
                # Same prompt, square hi-res for POD.
                self.gemini.generate_image(
                    f"{scene.visual_prompt}, centered composition, transparent-friendly background",
                    out_path=pod_path,
                    model=self.cfg["imagen_model"],
                    aspect_ratio=self.cfg["pod_aspect"],
                )

        return {"cover_zh": cover_zh, "cover_en": cover_en}
