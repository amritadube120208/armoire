"""
Demo Wardrobe Seed Script.

Seeds a realistic demo user and a diverse 15-piece capsule wardrobe across
all major categories, formality levels, seasons, and colors.
Allows instant evaluation of the Recommendation Engine and Feedback Loop.

Usage:
    python -m scripts.seed_demo_wardrobe
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.security import get_password_hash
from app.models.base import AsyncSessionLocal, Base, async_engine
from app.models.clothing import ClothingAttributes, ClothingImage, ClothingItem
from app.models.user import User, UserPreference


DEMO_EMAIL = "demo@smartwardrobe.com"
DEMO_PASSWORD = "Password123!"

SEED_ITEMS = [
    # Tops
    {
        "category": "tops",
        "subtype": "button-up",
        "color_primary": "blue",
        "pattern": "solid",
        "formality_estimate": "smart-casual",
        "formality_confidence": 0.88,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Classic Blue Oxford Shirt",
    },
    {
        "category": "tops",
        "subtype": "t-shirt",
        "color_primary": "white",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.95,
        "season_tags": ["summer", "spring"],
        "quality_band": "good",
        "name": "White Heavyweight Crewneck T-Shirt",
    },
    {
        "category": "tops",
        "subtype": "sweater",
        "color_primary": "black",
        "pattern": "solid",
        "formality_estimate": "smart-casual",
        "formality_confidence": 0.90,
        "season_tags": ["autumn", "winter"],
        "quality_band": "good",
        "name": "Merino Wool Knit Sweater",
    },
    {
        "category": "tops",
        "subtype": "hoodie",
        "color_primary": "gray",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.92,
        "season_tags": ["autumn", "winter"],
        "quality_band": "good",
        "name": "Relaxed French Terry Hoodie",
    },
    # Bottoms
    {
        "category": "bottoms",
        "subtype": "chinos",
        "color_primary": "navy",
        "pattern": "solid",
        "formality_estimate": "smart-casual",
        "formality_confidence": 0.89,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Slim-Fit Stretch Chinos",
    },
    {
        "category": "bottoms",
        "subtype": "jeans",
        "color_primary": "blue",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.94,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Vintage Wash Straight Denim",
    },
    {
        "category": "bottoms",
        "subtype": "trousers",
        "color_primary": "charcoal",
        "pattern": "solid",
        "formality_estimate": "formal",
        "formality_confidence": 0.92,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Tailored Charcoal Wool Trousers",
    },
    {
        "category": "bottoms",
        "subtype": "shorts",
        "color_primary": "beige",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.90,
        "season_tags": ["summer"],
        "quality_band": "good",
        "name": "Tailored Linen Shorts",
    },
    # Outerwear
    {
        "category": "outerwear",
        "subtype": "jacket",
        "color_primary": "black",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.87,
        "season_tags": ["autumn", "spring"],
        "quality_band": "good",
        "name": "Minimalist Leather Bomber Jacket",
    },
    {
        "category": "outerwear",
        "subtype": "wool-coat",
        "color_primary": "camel",
        "pattern": "solid",
        "formality_estimate": "formal",
        "formality_confidence": 0.91,
        "season_tags": ["winter"],
        "quality_band": "good",
        "name": "Double-Breasted Camel Overcoat",
    },
    {
        "category": "outerwear",
        "subtype": "jacket",
        "color_primary": "olive",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.86,
        "season_tags": ["spring", "autumn"],
        "quality_band": "good",
        "name": "Waxed Cotton Utility Field Jacket",
    },
    # Shoes
    {
        "category": "shoes",
        "subtype": "sneakers",
        "color_primary": "white",
        "pattern": "solid",
        "formality_estimate": "casual",
        "formality_confidence": 0.96,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Clean White Minimalist Leather Sneakers",
    },
    {
        "category": "shoes",
        "subtype": "boots",
        "color_primary": "brown",
        "pattern": "solid",
        "formality_estimate": "smart-casual",
        "formality_confidence": 0.90,
        "season_tags": ["autumn", "winter"],
        "quality_band": "good",
        "name": "Dark Brown Leather Chelsea Boots",
    },
    {
        "category": "shoes",
        "subtype": "dress-shoes",
        "color_primary": "black",
        "pattern": "solid",
        "formality_estimate": "formal",
        "formality_confidence": 0.93,
        "season_tags": ["all-season"],
        "quality_band": "good",
        "name": "Handcrafted Cap-Toe Oxford Shoes",
    },
    # Dresses
    {
        "category": "dresses",
        "subtype": "midi-dress",
        "color_primary": "emerald",
        "pattern": "solid",
        "formality_estimate": "formal",
        "formality_confidence": 0.91,
        "season_tags": ["summer", "spring"],
        "quality_band": "good",
        "name": "Silk Satin Emerald Midi Dress",
    },
]


async def seed():
    print("[*] Connecting to database...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 1. Check or create demo user
        from sqlalchemy import select
        stmt = select(User).where(User.email == DEMO_EMAIL)
        res = await session.execute(stmt)
        user = res.scalars().first()

        if not user:
            print(f"Creating demo user: {DEMO_EMAIL}")
            user = User(
                email=DEMO_EMAIL,
                password_hash=get_password_hash(DEMO_PASSWORD),
                name="Alex Rivers",
                location={"lat": 40.7128, "lon": -74.0060, "city": "New York"},
                units="metric",
            )
            session.add(user)
            await session.flush()

            pref = UserPreference(
                user_id=user.id,
                style_tags=["minimalist", "smart-casual", "contemporary"],
                color_affinity={"navy": 8.0, "white": 9.0, "black": 7.5, "camel": 6.5},
                category_affinity={"tops": 8.0, "bottoms": 8.0, "outerwear": 7.0, "shoes": 7.5},
                dress_code_overrides={},
            )
            session.add(pref)
            await session.flush()
        else:
            print(f"Demo user already exists: {DEMO_EMAIL} (ID: {user.id})")

        # 2. Check existing clothing items
        item_stmt = select(ClothingItem).where(ClothingItem.user_id == user.id)
        existing_items = (await session.execute(item_stmt)).scalars().all()

        if len(existing_items) >= len(SEED_ITEMS):
            print(f"Wardrobe already populated ({len(existing_items)} items).")
            return

        print(f"Seeding {len(SEED_ITEMS)} curated clothing items...")
        for item_data in SEED_ITEMS:
            item = ClothingItem(
                user_id=user.id,
                category=item_data["category"],
                subtype=item_data["subtype"],
                status="ready",
                wear_count=0,
            )
            session.add(item)
            await session.flush()

            # Image record
            slug = item_data["name"].lower().replace(" ", "_")
            img = ClothingImage(
                clothing_item_id=item.id,
                original_url=f"/storage/demo_{slug}.jpg",
                thumbnail_url=f"/storage/demo_{slug}_thumb.jpg",
                quality_band=item_data["quality_band"],
                quality_metrics={
                    "blur_score": 180.5,
                    "resolution": [1080, 1440],
                    "exposure": "normal",
                },
            )

            # Attributes record
            attr = ClothingAttributes(
                clothing_item_id=item.id,
                color_primary=item_data["color_primary"],
                pattern=item_data["pattern"],
                formality_estimate=item_data["formality_estimate"],
                formality_confidence=item_data["formality_confidence"],
                season_tags=item_data["season_tags"],
            )

            session.add_all([img, attr])

        await session.commit()
        print(f"[OK] Successfully seeded {len(SEED_ITEMS)} wardrobe items for {DEMO_EMAIL}!")
        print("\nDemo Credentials:")
        print(f"  Email:    {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
