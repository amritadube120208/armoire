import uuid
from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.clothing import ClothingAttributes, ClothingImage, ClothingItem


class ClothingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[ClothingItem]:
        """Fetch clothing item strictly scoped to the authenticated user."""
        stmt = (
            select(ClothingItem)
            .options(
                selectinload(ClothingItem.image),
                selectinload(ClothingItem.attributes)
            )
            .where(
                ClothingItem.id == item_id,
                ClothingItem.user_id == user_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_items(
        self,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        color: Optional[str] = None,
        season: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[ClothingItem], int]:
        """List clothing items strictly scoped to the authenticated user."""
        query = (
            select(ClothingItem)
            .options(
                selectinload(ClothingItem.image),
                selectinload(ClothingItem.attributes)
            )
            .where(ClothingItem.user_id == user_id)
        )

        if category:
            query = query.where(ClothingItem.category == category.lower().strip())
        if status:
            query = query.where(ClothingItem.status == status)

        if color:
            query = query.join(ClothingItem.attributes).where(
                (ClothingAttributes.color_primary.ilike(f"%{color}%")) |
                (ClothingAttributes.color_secondary.ilike(f"%{color}%"))
            )

        # Count total matching
        count_stmt = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply ordering and pagination
        query = query.order_by(ClothingItem.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        # If season filtering requested and season_tags stored in JSON
        if season:
            season_lower = season.lower().strip()
            items = [
                item for item in items
                if item.attributes and season_lower in [s.lower() for s in (item.attributes.season_tags or [])]
            ]

        return items, total

    async def create_item(
        self,
        user_id: uuid.UUID,
        original_url: str,
        category: Optional[str] = None,
        subtype: Optional[str] = None,
        status: str = "processing",
        quality_band: str = "good",
        quality_metrics: Optional[dict] = None
    ) -> ClothingItem:
        """Create clothing item and associated image and attributes records."""
        item = ClothingItem(
            user_id=user_id,
            category=category,
            subtype=subtype,
            status=status
        )
        self.session.add(item)
        await self.session.flush()

        image = ClothingImage(
            clothing_item_id=item.id,
            original_url=original_url,
            quality_band=quality_band,
            quality_metrics=quality_metrics or {}
        )
        self.session.add(image)

        attributes = ClothingAttributes(
            clothing_item_id=item.id,
            season_tags=[]
        )
        self.session.add(attributes)

        await self.session.flush()
        await self.session.refresh(item, attribute_names=["image", "attributes"])
        return item

    async def update_item_attributes(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        subtype: Optional[str] = None,
        status: Optional[str] = None,
        wear_count: Optional[int] = None,
        last_worn_date: Optional[date] = None,
        color_primary: Optional[str] = None,
        color_secondary: Optional[str] = None,
        pattern: Optional[str] = None,
        pattern_confidence: Optional[float] = None,
        formality_estimate: Optional[str] = None,
        formality_confidence: Optional[float] = None,
        season_tags: Optional[list] = None,
        embedding: Optional[list] = None
    ) -> Optional[ClothingItem]:
        """Update clothing item and attributes, strictly scoped to user_id."""
        item = await self.get_by_id(item_id, user_id)
        if not item:
            return None

        if category is not None:
            item.category = category.lower().strip()
        if subtype is not None:
            item.subtype = subtype.lower().strip()
        if status is not None:
            item.status = status
        if wear_count is not None:
            item.wear_count = wear_count
        if last_worn_date is not None:
            item.last_worn_date = last_worn_date

        if item.attributes is None:
            item.attributes = ClothingAttributes(clothing_item_id=item.id)
            self.session.add(item.attributes)

        if color_primary is not None:
            item.attributes.color_primary = color_primary
        if color_secondary is not None:
            item.attributes.color_secondary = color_secondary
        if pattern is not None:
            item.attributes.pattern = pattern
        if pattern_confidence is not None:
            item.attributes.pattern_confidence = pattern_confidence
        if formality_estimate is not None:
            item.attributes.formality_estimate = formality_estimate
        if formality_confidence is not None:
            item.attributes.formality_confidence = formality_confidence
        if season_tags is not None:
            item.attributes.season_tags = season_tags
        if embedding is not None:
            item.attributes.embedding = embedding

        await self.session.flush()
        return item

    async def update_image_details(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        enhanced_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        quality_band: Optional[str] = None,
        enhancement_applied: Optional[bool] = None,
        quality_metrics: Optional[dict] = None
    ) -> Optional[ClothingImage]:
        """Update clothing image details, strictly scoped to user_id."""
        item = await self.get_by_id(item_id, user_id)
        if not item or not item.image:
            return None

        if enhanced_url is not None:
            item.image.enhanced_url = enhanced_url
        if thumbnail_url is not None:
            item.image.thumbnail_url = thumbnail_url
        if quality_band is not None:
            item.image.quality_band = quality_band
        if enhancement_applied is not None:
            item.image.enhancement_applied = enhancement_applied
        if quality_metrics is not None:
            item.image.quality_metrics = quality_metrics

        await self.session.flush()
        return item.image

    async def delete_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Delete clothing item, strictly scoped to user_id."""
        item = await self.get_by_id(item_id, user_id)
        if not item:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True
