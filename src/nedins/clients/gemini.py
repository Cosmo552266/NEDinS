"""Thin wrapper over google-genai for text / Imagen / Veo / TTS.

Why a wrapper:
- One place to inject safety_settings, retries, dry-run mocking.
- Lets us swap providers later without touching agents.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from nedins.config import is_dry_run

# Adult-suspense content needs relaxed safety. We still block the highest tier.
_ADULT_SAFETY_CATEGORIES = (
    "HARM_CATEGORY_HARASSMENT",
    "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT",
    "HARM_CATEGORY_DANGEROUS_CONTENT",
)


@dataclass
class GeminiResponse:
    text: str
    raw: object | None = None


class GeminiClient:
    def __init__(self, api_key: str | None = None,
                 safety_threshold: str = "BLOCK_ONLY_HIGH") -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.safety_threshold = safety_threshold
        self._client = None

    def _ensure(self) -> None:
        if self._client is not None or is_dry_run():
            return
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set (or run with --dry-run)")
        from google import genai
        self._client = genai.Client(api_key=self.api_key)

    def _safety_settings(self):
        from google.genai import types
        return [
            types.SafetySetting(
                category=getattr(types.HarmCategory, c),
                threshold=getattr(types.HarmBlockThreshold, self.safety_threshold),
            )
            for c in _ADULT_SAFETY_CATEGORIES
        ]

    # ---- text ----------------------------------------------------------------

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16),
           retry=retry_if_exception_type(Exception),
           reraise=True)
    def generate_text(self, prompt: str, *, model: str = "gemini-2.5-pro",
                      system: str | None = None, json_mode: bool = False) -> GeminiResponse:
        if is_dry_run():
            return GeminiResponse(text=_mock_text(prompt, json_mode=json_mode))
        self._ensure()
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json" if json_mode else None,
            safety_settings=self._safety_settings(),
        )
        resp = self._client.models.generate_content(  # type: ignore[union-attr]
            model=model, contents=prompt, config=config,
        )
        return GeminiResponse(text=resp.text or "", raw=resp)

    # ---- image (Imagen) ------------------------------------------------------

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16),
           reraise=True)
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

    @retry(stop=stop_after_attempt(3),
           wait=wait_exponential(multiplier=2, min=2, max=16),
           reraise=True)
    def synthesize_speech(self, text: str, *, out_path: Path,
                          voice: str = "en-US-Studio-O",
                          language_code: str = "en-US") -> Path:
        if is_dry_run():
            return _mock_audio(text, out_path)
        self._ensure()
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
    """Hand-crafted mocks so dry-run produces something resembling real output."""
    if json_mode:
        # Try to match the shape the calling agent expects.
        lower = prompt.lower()
        if "視覺記憶點" in prompt or "key visual" in lower:
            return (
                '[{"label": "霓虹閃爍的電梯按鈕", "description": '
                '"老舊住宅電梯內，14 樓按鈕無故亮起紅光，光線打在乘客僵硬的側臉。", '
                '"pod_friendly": true},'
                ' {"label": "走廊盡頭的拖鞋", "description": '
                '"昏黃走廊盡頭擺著一雙女童拖鞋，相機緩緩推近。", "pod_friendly": false},'
                ' {"label": "玻璃倒影中的第二張臉", "description": '
                '"電梯不鏽鋼門反射出乘客背後另一個輪廓。", "pod_friendly": true},'
                ' {"label": "破裂的監控鏡頭", "description": '
                '"管理處監視器螢幕雪花閃爍，時間戳跳回 14 樓。", "pod_friendly": false}]'
            )
        if "storyboard" in lower or "scenes" in lower or "場景" in prompt:
            scenes = []
            for i in range(8):
                scenes.append(
                    f'{{"index": {i+1}, '
                    f'"narration_zh": "場景 {i+1}：走廊燈一閃，他發現自己其實從未離開。", '
                    f'"narration_en": "Scene {i+1}: the hallway light flickers; he realises he never left.", '
                    f'"visual_prompt": "dark cinematic, film grain, muted teal-and-orange palette, '
                    f'35mm lens, dim corridor scene {i+1}, low-key lighting", '
                    f'"duration_sec": 8.0, "pod_friendly": {"true" if i in (0, 3) else "false"}}}'
                )
            return ('{"cover_prompt": "dark cinematic poster of a haunted elevator, '
                    'red 14th-floor button glowing, 16:9 cover art", '
                    '"scenes": [' + ", ".join(scenes) + "]}")
        if "marketing" in lower or "instagram_zh" in prompt or "hashtag" in lower:
            return ('{"instagram_zh": "今晚十點，一個人都唔好按 14 樓。#新短片", '
                    '"instagram_en": "Tonight 10pm — never press 14 alone.", '
                    '"x_zh": "如果電梯第 14 樓嘅鍵自己著咗，你會點？", '
                    '"x_en": "What if the 14th-floor button lit up by itself?", '
                    '"tiktok_hook_zh": "佢話呢部電梯，由 1998 年開始就停咗 14 樓⋯", '
                    '"tiktok_hook_en": "They say this elevator hasn\'t stopped at 14 since 1998.", '
                    '"facebook_zh": "全新成人懸疑短篇《電梯》上線。", '
                    '"facebook_en": "New adult suspense short: The Elevator.", '
                    '"hashtags": ["#懸疑", "#都市傳說", "#鬼故事", "#shortfilm", '
                    '"#suspense", "#urbanlegend", "#thrillertok", "#booktok"]}')
        if "title" in lower and "pitch" in lower:
            return ('{"title": "懸疑短篇：十四樓的訪客", '
                    '"pitch": "搬入新樓的單親媽媽發現，電梯每晚都會無故停在不存在的 14 樓。", '
                    '"source": "holiday", "source_detail": "中元節前後", '
                    '"keywords": ["電梯", "都市傳說", "中元", "14樓"], '
                    '"holiday": "中元節", '
                    '"backup_pitches": ["後巷便利店凌晨三點的常客", '
                    '"地鐵末班車的第十三節車廂", "舊唐樓天台的紅衣女孩"]}')
        return '{"mock": true}'
    # plain text mock
    if "繁體中文" in prompt or "繁中" in prompt:
        return (
            "# 十四樓的訪客\n\n"
            "她搬入太子嗰幢舊唐樓嘅第三晚，電梯第一次停咗。\n\n"
            "唔係故障——係十四樓著咗燈。\n\n"
            "「呢度冇十四樓。」管理員阿伯講嘢嗰陣，眼神冇對住佢。\n\n"
            "佢按返地下，門慢慢閂埋，鏡面入面映住佢身後另一個人嘅輪廓。\n\n"
            "（接落去係 dry-run mock，真正運行時 Gemini 會寫成完整 1500-2500 字短篇。）"
        )
    if "english" in prompt.lower() or "EN" in prompt or "Translate" in prompt:
        return (
            "# The Visitor on the 14th Floor\n\n"
            "The third night after she moved into the old walk-up in Prince Edward, "
            "the elevator stopped on its own.\n\n"
            "Not a glitch. The 14th-floor button was lit.\n\n"
            "\"There is no 14th floor,\" the old caretaker said, never quite meeting her eyes.\n\n"
            "(Dry-run mock — Gemini would write a full 1500-2200 word localized story here.)"
        )
    return f"[DRY-RUN MOCK]\n\nPrompt was: {prompt[:200]}..."


def _mock_image(prompt: str, out_path: Path, aspect_ratio: str) -> Path:
    from PIL import Image, ImageDraw
    w, h = {"16:9": (1920, 1080), "1:1": (1024, 1024),
            "9:16": (1080, 1920)}.get(aspect_ratio, (1024, 1024))
    img = Image.new("RGB", (w, h), color=(20, 20, 30))
    draw = ImageDraw.Draw(img)
    draw.text((40, 40), f"DRY-RUN\n{prompt[:200]}", fill=(220, 220, 220))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _mock_video(prompt: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Write a tiny non-empty file so downstream "file size > 0" checks pass.
    out_path.write_bytes(b"DRY-RUN-MP4-PLACEHOLDER")
    return out_path


def _mock_audio(text: str, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"DRY-RUN-MP3-PLACEHOLDER")
    return out_path
