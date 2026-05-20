"""Upload POD-friendly images to Printify and create product listings."""
from __future__ import annotations

import json
from pathlib import Path

from nedins.clients.printify import PrintifyClient
from nedins.config import load_settings
from nedins.models import PodProduct, Story
from nedins.storage.artifacts import campaign_root, subdir


class PodPublisher:
    name = "pod_publisher"

    def __init__(self, printify: PrintifyClient | None = None) -> None:
        self.printify = printify or PrintifyClient()
        self.cfg = load_settings()["pod_publisher"]

    def run(self, campaign_id: str, story: Story) -> list[PodProduct]:
        out = campaign_root(campaign_id) / "pod" / "products.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            return [PodProduct(**p) for p in json.loads(out.read_text())]

        pod_dir = subdir(campaign_id, "images/pod")
        pod_images = sorted(pod_dir.glob("*.png"))
        if not pod_images:
            out.write_text("[]", encoding="utf-8")
            return []

        products: list[PodProduct] = []
        for img in pod_images:
            image_id = self.printify.upload_image(img, file_name=img.name)
            for bp in self.cfg["blueprints"]:
                title_zh = f"{story.title_zh}｜{bp['name']}"
                title_en = f"{story.title_en} {bp['name']}"
                desc = (
                    f"{story.title_en}\n\n{story.theme.pitch}\n\n"
                    f"Inspired by the short story «{story.title_zh}»."
                )
                product_id = self.printify.create_product(
                    blueprint_id=bp["blueprint_id"],
                    print_provider_id=bp["print_provider_id"],
                    image_id=image_id,
                    title=title_en,
                    description=desc,
                )
                if self.cfg.get("publish"):
                    self.printify.publish_product(product_id)
                products.append(PodProduct(
                    blueprint_name=bp["name"],
                    printify_product_id=product_id,
                    listing_title_zh=title_zh,
                    listing_title_en=title_en,
                    listing_description=desc,
                    image_path=img,
                ))

        out.write_text(json.dumps([p.model_dump(mode="json") for p in products],
                                  ensure_ascii=False, indent=2), encoding="utf-8")
        return products
