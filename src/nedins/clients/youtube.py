"""YouTube Data API v3 client. M3 will wire OAuth refresh + videos.insert."""
from __future__ import annotations

import os
from pathlib import Path

from nedins.config import is_dry_run


class YouTubeClient:
    def __init__(self) -> None:
        self.client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        self.client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        self.refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        self._service = None

    def _ensure(self) -> None:
        if self._service is not None or is_dry_run():
            return
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            raise RuntimeError("YouTube OAuth creds incomplete")
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        self._service = build("youtube", "v3", credentials=creds)

    def upload_video(self, *, video_path: Path, title: str, description: str,
                     tags: list[str], category_id: str = "24",
                     privacy_status: str = "unlisted",
                     default_language: str = "zh-Hant") -> dict[str, str]:
        if is_dry_run():
            return {"id": f"dry-yt-{video_path.stem}",
                    "url": f"https://youtube.com/watch?v=dry-{video_path.stem}"}
        self._ensure()
        from googleapiclient.http import MediaFileUpload
        body = {
            "snippet": {"title": title, "description": description, "tags": tags,
                        "categoryId": category_id, "defaultLanguage": default_language},
            "status": {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
        req = self._service.videos().insert(part="snippet,status", body=body, media_body=media)  # type: ignore[union-attr]
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        return {"id": resp["id"], "url": f"https://youtube.com/watch?v={resp['id']}"}
