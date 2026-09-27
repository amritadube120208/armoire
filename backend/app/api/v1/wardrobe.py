import uuid
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.schemas.clothing import (
    ClothingItemResponse,
    ClothingItemUpdate,
    ClothingListResponse,
    ItemStatusResponse,
)
from app.services.image_service import ImageService
from app.services.wardrobe_service import WardrobeService

router = APIRouter(prefix="/wardrobe", tags=["Wardrobe"])


@router.post(
    "/items",
    response_model=ClothingItemResponse,
    status_code=status.HTTP_201_CREATED
)
async def upload_clothing_item(
    file: UploadFile = File(..., description="Clothing photo (JPEG, PNG, WEBP)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Uploads new clothing photo per Backend.md Pipeline 2:
      - Validates MIME type and magic bytes
      - Strips EXIF/GPS server-side
      - Evaluates quality gate (Laplacian blur, brightness, resolution)
      - Enqueues background worker for detection, classification, and embedding
    """
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    image_service = ImageService(session)
    item = await image_service.upload_clothing_image(
        user_id=current_user.id,
        raw_bytes=raw_bytes,
        filename=file.filename or "upload.jpg"
    )
    return item


@router.get("/items", response_model=ClothingListResponse)
async def list_wardrobe_items(
    category: Optional[str] = Query(None, description="Filter by category (top, bottom, shoes, etc.)"),
    color: Optional[str] = Query(None, description="Filter by color name"),
    season: Optional[str] = Query(None, description="Filter by season (summer, winter, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (processing, ready, needs_review)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    List and filter wardrobe items strictly scoped to the authenticated user.
    """
    wardrobe_service = WardrobeService(session)
    return await wardrobe_service.list_wardrobe(
        user_id=current_user.id,
        category=category,
        color=color,
        season=season,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/items/{id}", response_model=ClothingItemResponse)
async def get_clothing_item(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed clothing item information including image links and confidence-scored attributes.
    """
    wardrobe_service = WardrobeService(session)
    return await wardrobe_service.get_item(item_id=id, user_id=current_user.id)


@router.patch("/items/{id}", response_model=ClothingItemResponse)
async def update_clothing_item(
    id: uuid.UUID,
    update: ClothingItemUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Update clothing item attributes (user corrections).
    Feeds the user-corrected label data flywheel.
    """
    wardrobe_service = WardrobeService(session)
    return await wardrobe_service.update_item(
        item_id=id,
        user_id=current_user.id,
        update=update
    )


@router.delete("/items/{id}", status_code=status.HTTP_200_OK)
async def delete_clothing_item(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Delete clothing item and purge stored image assets.
    """
    wardrobe_service = WardrobeService(session)
    await wardrobe_service.delete_item(item_id=id, user_id=current_user.id)
    return {"message": "Clothing item successfully deleted."}


@router.get("/items/{id}/status", response_model=ItemStatusResponse)
async def get_clothing_item_status(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Poll processing status of an uploaded clothing item.
    """
    wardrobe_service = WardrobeService(session)
    return await wardrobe_service.get_status(item_id=id, user_id=current_user.id)
