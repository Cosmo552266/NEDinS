"""Smoke test: --dry-run should produce a full campaign folder with no API keys."""
import os
import shutil
from datetime import date
from pathlib import Path


def test_dry_run_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("NEDINS_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NEDINS_DRY_RUN", "true")

    # Reset config cache so new env vars are picked up.
    from nedins import config as cfg_mod
    cfg_mod.load_settings.cache_clear()
    from nedins.storage import artifacts
    artifacts.DATA_DIR = Path(str(tmp_path))

    from nedins.orchestrator import run as run_pipeline
    # Typer commands are callable directly with their python signature.
    run_pipeline(dry_run=True, target=date.today().isoformat(), resume="", skip="")

    campaigns = list((tmp_path / "campaigns").iterdir())
    assert len(campaigns) == 1
    root = campaigns[0]
    assert (root / "theme.json").exists()
    assert (root / "story_zh.md").exists()
    assert (root / "story_en.md").exists()
    assert (root / "storyboard.json").exists()
    assert (root / "marketing.json").exists()
    assert (root / "campaign.json").exists()
