"""Generate narration audio per scene, in both locales."""
from __future__ import annotations

from nedins.clients.gemini import GeminiClient
from nedins.config import load_settings
from nedins.models.schemas import Storyboard as StoryboardModel
from nedins.storage.artifacts import subdir


class Voiceover:
    name = "voiceover"

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or GeminiClient()
        self.cfg = load_settings()["voiceover"]

    def run(self, campaign_id: str, board: StoryboardModel) -> StoryboardModel:
        audio_dir = subdir(campaign_id, "audio")
        for scene in board.scenes:
            zh_path = audio_dir / f"scene_{scene.index:02d}_zh.mp3"
            en_path = audio_dir / f"scene_{scene.index:02d}_en.mp3"
            self.gemini.synthesize_speech(
                scene.narration_zh, out_path=zh_path,
                voice=self.cfg["voice_zh"], language_code="zh-HK",
            )
            self.gemini.synthesize_speech(
                scene.narration_en, out_path=en_path,
                voice=self.cfg["voice_en"], language_code="en-US",
            )
            scene.audio_path_zh = zh_path
            scene.audio_path_en = en_path
        return board
