import asyncio
import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger
from app.image_processing.pipeline import image_pipeline
from app.image_processing.storage import storage
from app.models.base import AsyncSessionLocal
from app.models.clothing import ClothingItem
from app.repositories.clothing_repo import ClothingRepository
from app.schemas.clothing import ClothingItemResponse, ImageEnhanceRequest
from app.workers.tasks import (
    celery_app,
    execute_item_processing_pipeline,
    process_clothing_item_task,
)

logger = get_logger(__name__)


class ImageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.clothing_repo = ClothingRepository(session)

    async def upload_clothing_image(
        self,
        user_id: uuid.UUID,
        raw_bytes: bytes,
        filename: str = "upload.jpg",
        category: Optional[str] = None,
        subtype: Optional[str] = None,
        name: Optional[str] = None
    ) -> ClothingItemResponse:
        """
        Executes upload ingestion per Backend.md Pipeline 2:
          1. Validation (MIME + magic bytes + size limit)
          2. Re-encode server-side (strips EXIF/GPS, neutralizes payloads)
          3. Save original and thumbnail to object storage
          4. Create DB item stub with unique UUID in 'processing' status
          5. Enqueue background processing job with user & filename hints
        """
        # 1 & 2. Process, strip EXIF, and evaluate quality
        clean_bytes, thumb_bytes, quality_metrics = image_pipeline.process_and_reencode(raw_bytes)

        # Generate unique file keys
        item_uuid = uuid.uuid4()
        orig_key = f"{user_id}/{item_uuid}/original.jpg"
        thumb_key = f"{user_id}/{item_uuid}/thumbnail.jpg"

        orig_url = await storage.save_file(orig_key, clean_bytes)
        thumb_url = await storage.save_file(thumb_key, thumb_bytes)

        # 3. Create initial item row in DB with independent UUID
        initial_status = "needs_review" if quality_metrics.quality_band == "poor" else "processing"

        item = await self.clothing_repo.create_item(
            user_id=user_id,
            original_url=orig_url,
            category=category.lower().strip() if category else None,
            subtype=subtype.lower().strip() if subtype else (name.lower().strip() if name else None),
            status=initial_status,
            quality_band=quality_metrics.quality_band,
            quality_metrics=quality_metrics.model_dump()
        )
        # Update thumbnail url on image row
        await self.clothing_repo.update_image_details(
            item_id=item.id,
            user_id=user_id,
            thumbnail_url=thumb_url
        )
        item_id = item.id
        await self.session.commit()

        # 4. Execute pipeline directly for instant classification and ready status (< 200ms)
        try:
            await execute_item_processing_pipeline(
                str(item_id),
                str(user_id),
                clean_bytes,
                session=self.session,
                category_hint=category,
                subtype_hint=subtype or name,
                filename=filename,
            )
        except Exception as e:
            logger.exception("Error executing item processing pipeline: %s", e)

        refreshed_item = await self.clothing_repo.get_by_id(item_id, user_id)
        if not refreshed_item:
            refreshed_item = item
        return ClothingItemResponse.model_validate(refreshed_item)

    async def handle_enhancement_choice(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        req: ImageEnhanceRequest
    ) -> ClothingItemResponse:
        """
        Implements Backend.md Pipeline 3 Enhancement Transparency:
          - Lets user choose between original and enhanced image
          - Never forces enhancement or claims invented details
        """
        item = await self.clothing_repo.get_by_id(item_id, user_id)
        if not item or not item.image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clothing item not found in your wardrobe."
            )

        if req.action == "use_enhanced":
            if not item.image.enhanced_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No enhanced image candidate available for this item."
                )
            await self.clothing_repo.update_image_details(
                item_id=item_id,
                user_id=user_id,
                enhancement_applied=True
            )
        elif req.action == "use_original":
            await self.clothing_repo.update_image_details(
                item_id=item_id,
                user_id=user_id,
                enhancement_applied=False
            )
        elif req.action == "retake":
            # Item remains with original, flagged for user to re-upload if desired
            pass
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid enhancement action. Choose: 'use_enhanced', 'use_original', or 'retake'."
            )

        await self.session.commit()
        refreshed = await self.clothing_repo.get_by_id(item_id, user_id)
        return ClothingItemResponse.model_validate(refreshed)
