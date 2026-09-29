"""Idempotently seed the public presentation account and private sample images."""

import asyncio
import re

from sqlalchemy import select

from app.image_processing.storage import storage
from app.models.base import AsyncSessionLocal
from app.models.clothing import ClothingAttributes, ClothingImage, ClothingItem
from scripts.seed_demo_wardrobe import seed

SHAPES = {
    "tops": "M90 68 L140 45 Q180 80 220 45 L270 68 L304 130 L260 155 L245 125 L245 292 L115 292 L115 125 L100 155 L56 130 Z",
    "bottoms": "M108 55 L250 55 L258 150 L237 306 L183 306 L179 164 L164 306 L109 306 L99 150 Z",
    "outerwear": "M95 70 L143 45 L180 100 L217 45 L265 70 L295 285 L251 293 L230 140 L245 315 L115 315 L130 140 L109 293 L65 285 Z",
    "shoes": "M90 178 L155 165 L190 205 L277 221 Q314 232 303 270 L65 270 Q50 238 72 215 Z",
    "dresses": "M140 50 L164 50 Q180 74 196 50 L220 50 L210 125 L274 304 L86 304 L150 125 Z",
}
COLORS = {
    "blue": "#6f8aa0", "white": "#ece7db", "black": "#343332", "gray": "#92928b",
    "navy": "#34435a", "charcoal": "#55514e", "beige": "#c9b58f", "camel": "#b18d62",
    "olive": "#777e59", "brown": "#765544", "emerald": "#326e59",
}


def illustration(category: str, color: str) -> bytes:
    shape = SHAPES.get(category, SHAPES["tops"])
    fill = COLORS.get(color, "#8e8273")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 400">'
        '<rect width="360" height="400" fill="#eee9df"/>'
        f'<path d="{shape}" fill="{fill}" stroke="#655f55" stroke-width="2"/>'
        '<text x="180" y="365" text-anchor="middle" fill="#736a5c" '
        'font-family="serif" font-size="13">ARMOIRE · SAMPLE ILLUSTRATION</text></svg>'
    ).encode("utf-8")


async def prepare() -> None:
    await seed()
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ClothingItem, ClothingImage, ClothingAttributes)
                .join(ClothingImage, ClothingImage.clothing_item_id == ClothingItem.id)
                .join(ClothingAttributes, ClothingAttributes.clothing_item_id == ClothingItem.id)
            )
        ).all()
        for item, image, attributes in rows:
            if not image.original_url.startswith("/storage/demo_"):
                continue
            slug = re.sub(r"[^a-z0-9]+", "_", item.subtype or item.category or "piece").strip("_")
            key = f"demo/{item.id}-{slug}.svg"
            image_url = await storage.save_file(
                key,
                illustration(item.category or "tops", attributes.color_primary or "gray"),
                content_type="image/svg+xml",
            )
            image.original_url = image_url
            image.thumbnail_url = image_url
        await session.commit()


if __name__ == "__main__":
    asyncio.run(prepare())
