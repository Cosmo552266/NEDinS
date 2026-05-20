"""Load YAML settings + env overrides."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "settings.yaml"


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Env overrides for a few flat keys
    if locale := os.environ.get("NEDINS_LOCALE_PRIMARY"):
        data["pipeline"]["locales"]["primary"] = locale
    if locale := os.environ.get("NEDINS_LOCALE_SECONDARY"):
        data["pipeline"]["locales"]["secondary"] = locale
    if regions := os.environ.get("NEDINS_REGIONS"):
        data["pipeline"]["regions"] = [r.strip() for r in regions.split(",")]
    return data


def is_dry_run() -> bool:
    return os.environ.get("NEDINS_DRY_RUN", "").lower() in {"1", "true", "yes"}
