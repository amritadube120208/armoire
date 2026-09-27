import uuid
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.image_processing.storage import storage
from app.repositories.clothing_repo import ClothingRepository
from app.schemas.clothing import (
    ClothingItemResponse,
    ClothingItemUpdate,
    ClothingListResponse,
    ItemStatusResponse,
)


class WardrobeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.clothing_repo = ClothingRepository(session)

    async def list_wardrobe(
        self,
        user_id: uuid.UUID,
        category: Optional[str] = None,
        color: Optional[str] = None,
        season: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> ClothingListResponse:
        items, total = await self.clothing_repo.list_items(
            user_id=user_id,
            category=category,
            color=color,
            season=season,
            status=status,
            limit=limit,
            offset=offset
        )
        return ClothingListResponse(
            items=[ClothingItemResponse.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset
        )

    async def get_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ClothingItemResponse:
        item = await self.clothing_repo.get_by_id(item_id, user_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clothing item not found in your wardrobe."
            )
        return ClothingItemResponse.model_validate(item)

    async def update_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        update: ClothingItemUpdate
    ) -> ClothingItemResponse:
        item = await self.clothing_repo.update_item_attributes(
            item_id=item_id,
            user_id=user_id,
            category=update.category,
            subtype=update.subtype,
            color_primary=update.color_primary,
            color_secondary=update.color_secondary,
            pattern=update.pattern,
            pattern_confidence=update.pattern_confidence,
            formality_estimate=update.formality_estimate,
            formality_confidence=update.formality_confidence,
            season_tags=update.season_tags,
            wear_count=update.wear_count,
            last_worn_date=update.last_worn_date,
        )
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clothing item not found in your wardrobe."
            )
        return ClothingItemResponse.model_validate(item)

    async def delete_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        item = await self.clothing_repo.get_by_id(item_id, user_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clothing item not found in your wardrobe."
            )

        # Remove image assets from storage if present
        if item.image:
            if item.image.original_url:
                await storage.delete_file(item.image.original_url)
            if item.image.enhanced_url:
                await storage.delete_file(item.image.enhanced_url)
            if item.image.thumbnail_url:
                await storage.delete_file(item.image.thumbnail_url)

        return await self.clothing_repo.delete_item(item_id, user_id)

    async def get_status(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> ItemStatusResponse:
        item = await self.clothing_repo.get_by_id(item_id, user_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clothing item not found in your wardrobe."
            )

        quality_band = item.image.quality_band if item.image else "unknown"
        needs_review = (item.status == "needs_review") or (quality_band == "poor")

        return ItemStatusResponse(
            id=item.id,
            status=item.status,
            quality_band=quality_band,
            needs_review=needs_review,
            message=(
                "Item processing complete and ready."
                if item.status == "ready"
                else (
                    "Item photo has quality concerns. Please review and verify attributes."
                    if item.status == "needs_review"
                    else "Item is being analyzed in background."
                )
            )
        )
