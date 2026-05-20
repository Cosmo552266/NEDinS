"""Thin wrapper over google-genai for text / Imagen / Veo / TTS.

Why a wrapper:
- One place to inject safety_settings, retries, dry-run mocking.
- Lets us swap providers later without touching agents.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from nedins.config import is_dry_run


@dataclass
class GeminiResponse:
    text: str
    raw: object | None = None


class GeminiClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = None

    def _ensure(self) -> None:
        if self._client is not None or is_dry_run():
            return
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set (or run with --dry-run)")
        from google import genai  # lazy import
        self._client = genai.Client(api_key=self.api_key)

    # ---- text ----------------------------------------------------------------

    def generate_text(self, prompt: str, *, model: str = "gemini-2.5-pro",
                      system: str | None = None, json_mode: bool = False) -> GeminiResponse:
        if is_dry_run():
            return GeminiResponse(text=_mock_text(prompt, json_mode=json_mode))
        self._ensure()
        from google.genai import types  # type: ignore
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if json_mode else None,
        )
        resp = self._client.models.generate_content(  # type: ignore[union-attr]
            model=model, contents=prompt, config=config,
        )
        return GeminiResponse(text=resp.text or "", raw=resp)

    # ---- image (Imagen) ------------------------------------------------------

    def generate_image(self, prompt: str, *, out_path: Path,
                       model: str = "imagen-3.0-generate-002",
                       aspect_ratio: str = "16:9") -> Path:
        if is_dry_run():
            return _mock_image(prompt, out_path, aspect_ratio)
        self._ensure()
        resp = self._client.models.generate_images(  # type: ignore[union-attr]
            model=model,
            prompt=prompt,
            config={"number_of_images": 1, "aspect_ratio": aspect_ratio},
        )
        img = resp.generated_images[0].image
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_path))
        return out_path

    # ---- video (Veo) — M5 ----------------------------------------------------

    def generate_video(self, prompt: str, *, out_path: Path,
                       model: str = "veo-3.0-generate-001",
                       duration_sec: int = 8) -> Path:
        if is_dry_run():
            return _mock_video(prompt, out_path)
        self._ensure()
        # Veo generation is async; this is a sketch — fill in for M5.
        op = self._client.models.generate_videos(  # type: ignore[union-attr]
            model=model, prompt=prompt,
            config={"duration_seconds": duration_sec, "aspect_ratio": "16:9"},
        )
        while not op.done:
            import time; time.sleep(10)
            op = self._client.operations.get(op)  # type: ignore[union-attr]
        video = op.response.generated_videos[0]  # type: ignore[union-attr]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        video.video.save(str(out_path))
        return out_path

    # ---- TTS (Chirp / Gemini TTS) -------------------------------------------

    def synthesize_speech(self, text: str, *, out_path: Path,
                          voice: str = "en-US-Studio-O",
                          language_code: str = "en-US") -> Path:
        if is_dry_run():
            return _mock_audio(text, out_path)
        self._ensure()
        # Sketch — replace with the exact TTS API call you settle on.
        resp = self._client.models.generate_content(  # type: ignore[union-attr]
            model="gemini-2.5-flash-preview-tts",
            contents=text,
            config={"response_modalities": ["AUDIO"],
                    "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice}}}},
        )
        audio_bytes = resp.candidates[0].content.parts[0].inline_data.data  # type: ignore[index]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_bytes)
        return out_path


# ---------- Mocks for --dry-run -----------------------------------------------

def _mock_text(prompt: str, *, json_mode: bool) -> str:
    if json_mode:
        return '{"mock": true, "prompt_preview": "' + prompt[:80].replace('"', "'") + '"}'
    return f"[DRY-RUN MOCK]\n\nPrompt was: {prompt[:200]}...\n\n(填入真實 Gemini output 後此處會係真故事)"


def _mock_image(prompt: str, out_path: Path, aspect_ratio: str) -> Path:
    from PIL import Image, ImageDraw
    w, h = {"16:9": (1920, 1080), "1:1": (1024, 1024), "9:16": (1080, 1920)}.get(aspect_ratio, (1024, 1024))
    img = Image.new("RGB", (w, h), color=(20, 20, 30))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), f"DRY-RUN\n{prompt[:200]}", fill=(220, 220, 220))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _mock_video(prompt: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"")  # empty placeholder
    return out_path


def _mock_audio(text: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"")
    return out_path
