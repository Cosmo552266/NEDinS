"""Printify REST client — minimal surface for upload + create product + publish."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from nedins.config import is_dry_run


class PrintifyClient:
    BASE = "https://api.printify.com/v1"

    def __init__(self, token: str | None = None, shop_id: str | None = None) -> None:
        self.token = token or os.environ.get("PRINTIFY_API_TOKEN")
        self.shop_id = shop_id or os.environ.get("PRINTIFY_SHOP_ID")

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("PRINTIFY_API_TOKEN not set")
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def upload_image(self, image_path: Path, file_name: str | None = None) -> str:
        """Returns Printify image id."""
        if is_dry_run():
            return f"dry-img-{image_path.stem}"
        import base64
        with image_path.open("rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        payload = {"file_name": file_name or image_path.name, "contents": b64}
        r = httpx.post(f"{self.BASE}/uploads/images.json", json=payload, headers=self._headers(), timeout=60)
        r.raise_for_status()
        return r.json()["id"]

    def create_product(self, *, blueprint_id: int, print_provider_id: int,
                       image_id: str, title: str, description: str,
                       variants: list[dict[str, Any]] | None = None) -> str:
        if is_dry_run():
            return f"dry-prod-{blueprint_id}"
        if not self.shop_id:
            raise RuntimeError("PRINTIFY_SHOP_ID not set")
        payload = {
            "title": title,
            "description": description,
            "blueprint_id": blueprint_id,
            "print_provider_id": print_provider_id,
            "variants": variants or [],
            "print_areas": [{
                "variant_ids": [v["id"] for v in (variants or [])],
                "placeholders": [{"position": "front",
                                  "images": [{"id": image_id, "x": 0.5, "y": 0.5, "scale": 1, "angle": 0}]}],
            }],
        }
        r = httpx.post(f"{self.BASE}/shops/{self.shop_id}/products.json",
                       json=payload, headers=self._headers(), timeout=60)
        r.raise_for_status()
        return r.json()["id"]

    def publish_product(self, product_id: str) -> None:
        if is_dry_run():
            return
        r = httpx.post(f"{self.BASE}/shops/{self.shop_id}/products/{product_id}/publish.json",
                       json={"title": True, "description": True, "images": True,
                             "variants": True, "tags": True, "keyFeatures": True},
                       headers=self._headers(), timeout=60)
        r.raise_for_status()
