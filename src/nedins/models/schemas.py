"""Pydantic schemas — the wire format between agents."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Locale = Literal["zh-Hant", "en", "zh-Hans"]


class Theme(BaseModel):
    title: str
    pitch: str
    locale_titles: dict[Locale, str] = Field(default_factory=dict)
    source: Literal["google_trends", "holiday", "prior", "manual"]
    source_detail: str
    keywords: list[str]
    holiday: str | None = None
    backup_pitches: list[str] = Field(default_factory=list)


class KeyVisual(BaseModel):
    label: str
    description: str
    pod_friendly: bool = False


class Story(BaseModel):
    theme: Theme
    body_zh: str
    body_en: str
    title_zh: str
    title_en: str
    key_visuals: list[KeyVisual]
    word_count_zh: int
    word_count_en: int


class Scene(BaseModel):
    index: int
    narration_zh: str
    narration_en: str
    visual_prompt: str
    duration_sec: float
    pod_friendly: bool = False
    image_path: Path | None = None
    audio_path_zh: Path | None = None
    audio_path_en: Path | None = None


class Storyboard(BaseModel):
    scenes: list[Scene]
    cover_prompt: str


class MarketingCopy(BaseModel):
    instagram_zh: str
    instagram_en: str
    x_zh: str
    x_en: str
    tiktok_hook_zh: str
    tiktok_hook_en: str
    facebook_zh: str
    facebook_en: str
    hashtags: list[str]


class PodProduct(BaseModel):
    blueprint_name: str
    printify_product_id: str
    listing_title_zh: str
    listing_title_en: str
    listing_description: str
    image_path: Path
    published_at: datetime | None = None


class YouTubeUpload(BaseModel):
    locale: Locale
    video_id: str
    url: str
    title: str
    description: str
    tags: list[str]
    privacy: str


class Campaign(BaseModel):
    """Root artifact. Every step writes to disk under data/campaigns/{id}/."""

    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    target_date: date

    theme: Theme | None = None
    story: Story | None = None
    storyboard: Storyboard | None = None
    cover_path_zh: Path | None = None
    cover_path_en: Path | None = None
    video_path_zh: Path | None = None
    video_path_en: Path | None = None
    marketing: MarketingCopy | None = None
    pod_products: list[PodProduct] = Field(default_factory=list)
    youtube_uploads: list[YouTubeUpload] = Field(default_factory=list)

    @property
    def root_dir(self) -> Path:
        from nedins.storage.artifacts import campaign_root
        return campaign_root(self.id)
