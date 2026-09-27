"""
Feedback Service — Phase 9 implementation.

Handles recording of user feedback on outfits, drives the personalization loop:
  - Stores Feedback row.
  - Updates UserPreference (color_affinity, category_affinity) via Exponential Moving Average (EMA).
  - Updates wear_count and last_worn_date on ClothingItem when outfit is worn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.clothing import ClothingAttributes, ClothingItem
from app.models.feedback import Feedback
from app.models.outfit import Outfit, OutfitItem
from app.models.user import UserPreference


class FeedbackService:
    VALID_ACTIONS = {"like", "dislike", "save", "wear", "mark-as-worn", "swap"}
    ALPHA = 0.3  # EMA smoothing factor
    TARGET_POSITIVE = 10.0
    TARGET_NEGATIVE = 0.0
    DEFAULT_PRIOR = 5.0

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_feedback(
        self,
        user_id: uuid.UUID,
        outfit_id: uuid.UUID,
        action: str,
    ) -> Dict[str, Any]:
        """
        Record user feedback action and trigger preference / wear updates.

        Raises:
            ValueError: If action is unknown or outfit not found/unauthorized.
        """
        norm_action = action.lower().strip()
        if norm_action not in self.VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}'. Expected one of {sorted(self.VALID_ACTIONS)}"
            )

        # Normalize alias
        if norm_action == "mark-as-worn":
            norm_action = "wear"

        # Fetch outfit with items and clothing attributes
        stmt = (
            select(Outfit)
            .options(
                selectinload(Outfit.items)
                .selectinload(OutfitItem.clothing_item)
                .selectinload(ClothingItem.attributes)
            )
            .where(
                Outfit.id == outfit_id,
                Outfit.user_id == user_id,
            )
        )
        res = await self.session.execute(stmt)
        outfit = res.scalars().first()

        if not outfit:
            raise ValueError("Outfit not found or does not belong to the user.")

        # 1. Record Feedback row
        feedback = Feedback(
            user_id=user_id,
            outfit_id=outfit_id,
            action=norm_action,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(feedback)

        preference_updated = False
        wear_updated = False

        # 2. EMA Preference update for like, wear, save, dislike
        if norm_action in {"like", "wear", "save", "dislike"}:
            target = (
                self.TARGET_POSITIVE
                if norm_action in {"like", "wear", "save"}
                else self.TARGET_NEGATIVE
            )
            await self._update_preferences(user_id, outfit, target)
            preference_updated = True

        # 3. If worn, update wear_count and last_worn_date for constituent items
        if norm_action == "wear":
            today = datetime.now(timezone.utc).date()
            for oi in outfit.items:
                if oi.clothing_item:
                    oi.clothing_item.wear_count = (oi.clothing_item.wear_count or 0) + 1
                    oi.clothing_item.last_worn_date = today
            wear_updated = True

        await self.session.flush()

        return {
            "id": str(feedback.id),
            "user_id": str(user_id),
            "outfit_id": str(outfit_id),
            "action": norm_action,
            "created_at": feedback.created_at.isoformat(),
            "preference_updated": preference_updated,
            "wear_count_updated": wear_updated,
        }

    async def _update_preferences(
        self,
        user_id: uuid.UUID,
        outfit: Outfit,
        target_val: float,
    ) -> None:
        """Apply EMA update to UserPreference maps based on items in the outfit."""
        pref_stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        pref_res = await self.session.execute(pref_stmt)
        pref = pref_res.scalars().first()

        if not pref:
            pref = UserPreference(
                user_id=user_id,
                style_tags=[],
                color_affinity={},
                category_affinity={},
                dress_code_overrides={},
            )
            self.session.add(pref)
            await self.session.flush()

        # Copy existing dicts to ensure SQLAlchemy detects mutation
        color_map = dict(pref.color_affinity or {})
        cat_map = dict(pref.category_affinity or {})

        for oi in outfit.items:
            item = oi.clothing_item
            if not item:
                continue

            # Update category affinity
            if item.category:
                cat = item.category.lower().strip()
                old_w = float(cat_map.get(cat, self.DEFAULT_PRIOR))
                cat_map[cat] = round(self.ALPHA * target_val + (1.0 - self.ALPHA) * old_w, 2)

            # Update color affinity
            if item.attributes and item.attributes.color_primary:
                color = item.attributes.color_primary.lower().strip()
                old_w = float(color_map.get(color, self.DEFAULT_PRIOR))
                color_map[color] = round(self.ALPHA * target_val + (1.0 - self.ALPHA) * old_w, 2)

        pref.color_affinity = color_map
        pref.category_affinity = cat_map
