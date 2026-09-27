import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.outfit import Outfit, OutfitItem


class OutfitRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        outfit_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[Outfit]:
        """Fetch outfit strictly scoped to user_id."""
        stmt = (
            select(Outfit)
            .options(
                selectinload(Outfit.items).selectinload(OutfitItem.clothing_item)
            )
            .where(
                Outfit.id == outfit_id,
                Outfit.user_id == user_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_outfits(
        self,
        user_id: uuid.UUID,
        occasion: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Outfit]:
        """List outfits strictly scoped to user_id."""
        stmt = (
            select(Outfit)
            .options(
                selectinload(Outfit.items).selectinload(OutfitItem.clothing_item)
            )
            .where(Outfit.user_id == user_id)
        )
        if occasion:
            stmt = stmt.where(Outfit.occasion == occasion.lower().strip())
        stmt = stmt.order_by(Outfit.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_outfit(
        self,
        user_id: uuid.UUID,
        occasion: str,
        clothing_item_ids: List[uuid.UUID],
        source: str = "manual"
    ) -> Outfit:
        outfit = Outfit(
            user_id=user_id,
            occasion=occasion,
            source=source
        )
        self.session.add(outfit)
        await self.session.flush()

        for item_id in clothing_item_ids:
            outfit_item = OutfitItem(
                outfit_id=outfit.id,
                clothing_item_id=item_id,
                role="item"
            )
            self.session.add(outfit_item)

        await self.session.flush()
        await self.session.refresh(outfit, attribute_names=["items"])
        return outfit

    async def delete_outfit(
        self,
        outfit_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        outfit = await self.get_by_id(outfit_id, user_id)
        if not outfit:
            return False
        await self.session.delete(outfit)
        await self.session.flush()
        return True
