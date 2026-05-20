"""Compose image + audio + subtitle into mp4 (Phase 1: slideshow with Ken Burns)."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from nedins.config import is_dry_run, load_settings
from nedins.models.schemas import Storyboard as StoryboardModel
from nedins.storage.artifacts import subdir


class VideoComposer:
    name = "video_composer"

    def __init__(self) -> None:
        self.cfg = load_settings()["video_composer"]

    def run(self, campaign_id: str, board: StoryboardModel,
            locale: Literal["zh", "en"]) -> Path:
        video_dir = subdir(campaign_id, "video")
        out_path = video_dir / f"final_{locale}.mp4"
        if out_path.exists() and out_path.stat().st_size > 0:
            return out_path

        if is_dry_run():
            out_path.write_bytes(b"")  # placeholder
            return out_path

        # M2: real implementation using moviepy.
        from moviepy.editor import (
            AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips,
        )
        clips = []
        for scene in board.scenes:
            if scene.image_path is None:
                continue
            audio_path = scene.audio_path_zh if locale == "zh" else scene.audio_path_en
            duration = scene.duration_sec
            if audio_path and audio_path.exists() and audio_path.stat().st_size > 0:
                audio = AudioFileClip(str(audio_path))
                duration = max(duration, audio.duration + 0.5)
            else:
                audio = None
            img = ImageClip(str(scene.image_path)).set_duration(duration)
            if self.cfg["ken_burns"]:
                img = img.resize(lambda t: 1 + 0.04 * t)  # subtle zoom-in
            if audio is not None:
                img = img.set_audio(audio)
            clips.append(img)

        final = concatenate_videoclips(clips, method="compose") if clips else None
        if final is None:
            out_path.write_bytes(b"")
            return out_path
        final.write_videofile(str(out_path), fps=self.cfg["fps"],
                              codec="libx264", audio_codec="aac")
        return out_path
