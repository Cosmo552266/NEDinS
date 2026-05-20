"""Filesystem layout helpers. Every agent writes its output under a campaign dir."""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("NEDINS_DATA_DIR", "./data")).resolve()


def campaigns_dir() -> Path:
    p = DATA_DIR / "campaigns"
    p.mkdir(parents=True, exist_ok=True)
    return p


def campaign_root(campaign_id: str) -> Path:
    p = campaigns_dir() / campaign_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def subdir(campaign_id: str, name: str) -> Path:
    p = campaign_root(campaign_id) / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def trends_cache_dir() -> Path:
    p = DATA_DIR / "trends"
    p.mkdir(parents=True, exist_ok=True)
    return p


def analytics_dir() -> Path:
    p = DATA_DIR / "analytics"
    p.mkdir(parents=True, exist_ok=True)
    return p


def theme_priors_db() -> Path:
    return analytics_dir() / "theme_priors.duckdb"
