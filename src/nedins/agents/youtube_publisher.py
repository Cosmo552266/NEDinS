"""Upload composed videos to YouTube with marketing copy as description."""
from __future__ import annotations

import json
from pathlib import Path

from nedins.clients.youtube import YouTubeClient
from nedins.config import load_settings
from nedins.models import MarketingCopy, Story, YouTubeUpload
from nedins.storage.artifacts import campaign_root


class YouTubePublisher:
    name = "youtube_publisher"

    def __init__(self, youtube: YouTubeClient | None = None) -> None:
        self.youtube = youtube or YouTubeClient()
        self.cfg = load_settings()["youtube_publisher"]

    def run(self, campaign_id: str, story: Story, marketing: MarketingCopy,
            video_zh: Path, video_en: Path) -> list[YouTubeUpload]:
        out = campaign_root(campaign_id) / "youtube" / "upload.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            return [YouTubeUpload(**u) for u in json.loads(out.read_text())]

        uploads: list[YouTubeUpload] = []
        for locale, video, title, desc in [
            ("zh-Hant", video_zh, story.title_zh, marketing.facebook_zh),
            ("en", video_en, story.title_en, marketing.facebook_en),
        ]:
            if not video.exists() or video.stat().st_size == 0:
                continue
            tags = marketing.hashtags + story.theme.keywords
            tags = [t.lstrip("#") for t in tags]
            resp = self.youtube.upload_video(
                video_path=video, title=title, description=desc, tags=tags,
                category_id=self.cfg["category_id"],
                privacy_status=self.cfg["privacy_status"],
                default_language=self.cfg["default_language"] if locale == "zh-Hant" else "en",
            )
            uploads.append(YouTubeUpload(
                locale=locale, video_id=resp["id"], url=resp["url"],
                title=title, description=desc, tags=tags,
                privacy=self.cfg["privacy_status"],
            ))
        out.write_text(json.dumps([u.model_dump(mode="json") for u in uploads],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        return uploads
