"""Pipeline runner. Each step is resumable: existing artifacts are reused."""
from __future__ import annotations

import os
from datetime import date, datetime

import typer
from rich.console import Console

from nedins.agents.image_generator import ImageGenerator
from nedins.agents.marketing_copy import MarketingCopyAgent
from nedins.agents.pod_publisher import PodPublisher
from nedins.agents.story_writer import StoryWriter
from nedins.agents.storyboard import Storyboard
from nedins.agents.trend_scout import TrendScout
from nedins.agents.video_composer import VideoComposer
from nedins.agents.voiceover import Voiceover
from nedins.agents.youtube_publisher import YouTubePublisher
from nedins.models import Campaign

app = typer.Typer(add_completion=False, help="NEDinS pipeline runner")
console = Console()


def _campaign_id(target: date) -> str:
    week = target.isocalendar()
    return f"{week.year}-W{week.week:02d}-{target.isoformat()}"


@app.command()
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Mock all external API calls"),
    target: str = typer.Option("", help="ISO date (default: today)"),
    resume: str = typer.Option("", help="Existing campaign id to resume"),
    skip: str = typer.Option("", help="Comma-separated agent names to skip"),
) -> None:
    if dry_run:
        os.environ["NEDINS_DRY_RUN"] = "true"

    target_date = date.fromisoformat(target) if target else date.today()
    campaign_id = resume or _campaign_id(target_date)
    skip_set = {s.strip() for s in skip.split(",") if s.strip()}

    console.rule(f"[bold cyan]Campaign {campaign_id}  (dry_run={dry_run})")
    campaign = Campaign(id=campaign_id, target_date=target_date,
                        created_at=datetime.utcnow())

    def _skip(name: str) -> bool:
        if name in skip_set:
            console.print(f"[yellow]skip[/yellow] {name}")
            return True
        return False

    if not _skip("trend_scout"):
        campaign.theme = TrendScout().run(campaign_id, target_date=target_date)
        console.print(f"[green]✓[/green] theme: {campaign.theme.title}")

    if not _skip("story_writer"):
        assert campaign.theme
        campaign.story = StoryWriter().run(campaign_id, campaign.theme)
        console.print(f"[green]✓[/green] story: {campaign.story.title_zh} "
                      f"({campaign.story.word_count_zh}字)")

    if not _skip("storyboard"):
        assert campaign.story
        campaign.storyboard = Storyboard().run(campaign_id, campaign.story)
        console.print(f"[green]✓[/green] storyboard: {len(campaign.storyboard.scenes)} scenes")

    if not _skip("image_generator"):
        assert campaign.story and campaign.storyboard
        covers = ImageGenerator().run(campaign_id, campaign.story, campaign.storyboard)
        campaign.cover_path_zh = covers["cover_zh"]
        campaign.cover_path_en = covers["cover_en"]
        console.print(f"[green]✓[/green] images: cover + {len(campaign.storyboard.scenes)} scenes")

    if not _skip("voiceover"):
        assert campaign.storyboard
        campaign.storyboard = Voiceover().run(campaign_id, campaign.storyboard)
        console.print("[green]✓[/green] voiceover")

    if not _skip("video_composer"):
        assert campaign.storyboard
        vc = VideoComposer()
        campaign.video_path_zh = vc.run(campaign_id, campaign.storyboard, locale="zh")
        campaign.video_path_en = vc.run(campaign_id, campaign.storyboard, locale="en")
        console.print(f"[green]✓[/green] video: {campaign.video_path_zh.name}")

    if not _skip("marketing_copy"):
        assert campaign.story
        campaign.marketing = MarketingCopyAgent().run(campaign_id, campaign.story)
        console.print("[green]✓[/green] marketing copy")

    if not _skip("pod_publisher"):
        assert campaign.story
        campaign.pod_products = PodPublisher().run(campaign_id, campaign.story)
        console.print(f"[green]✓[/green] POD: {len(campaign.pod_products)} products")

    if not _skip("youtube_publisher"):
        assert campaign.story and campaign.marketing
        assert campaign.video_path_zh and campaign.video_path_en
        campaign.youtube_uploads = YouTubePublisher().run(
            campaign_id, campaign.story, campaign.marketing,
            campaign.video_path_zh, campaign.video_path_en,
        )
        console.print(f"[green]✓[/green] YouTube: {len(campaign.youtube_uploads)} uploads")

    out = campaign.root_dir / "campaign.json"
    out.write_text(campaign.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    console.rule(f"[bold green]done — {out}")


if __name__ == "__main__":
    app()
