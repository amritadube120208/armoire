import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.schemas.clothing import ClothingItemResponse, ImageEnhanceRequest
from app.services.image_service import ImageService

router = APIRouter(prefix="/images", tags=["Images & Enhancement"])


@router.post("/{item_id}/enhance", response_model=ClothingItemResponse)
async def confirm_image_enhancement(
    item_id: uuid.UUID,
    req: ImageEnhanceRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Implements Backend.md Pipeline 3 Enhancement Transparency:
      - Lets user choose 'use_enhanced', 'use_original', or 'retake'
      - Ensures enhancement is never applied silently without user confirmation
    """
    image_service = ImageService(session)
    return await image_service.handle_enhancement_choice(
        item_id=item_id,
        user_id=current_user.id,
        req=req
    )
