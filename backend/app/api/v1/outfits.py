"""
Outfits API router.
Belongs to Phase 8 per Upgradation.md.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.repositories.outfit_repo import OutfitRepository
from app.schemas.outfit import OutfitCreateRequest, OutfitResponse

router = APIRouter(prefix="/outfits", tags=["Outfits"])


@router.post("", response_model=OutfitResponse, status_code=status.HTTP_201_CREATED)
async def save_outfit(
    req: OutfitCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """Save an outfit (manually built or recommended)."""
    repo = OutfitRepository(session)
    outfit = await repo.create_outfit(
        user_id=current_user.id,
        occasion=req.occasion,
        clothing_item_ids=req.clothing_item_ids,
        source=req.source
    )
    return OutfitResponse.model_validate(outfit)


@router.get("", response_model=List[OutfitResponse])
async def list_outfits(
    occasion: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """List saved outfits scoped to the user."""
    repo = OutfitRepository(session)
    outfits = await repo.list_outfits(
        user_id=current_user.id,
        occasion=occasion,
        limit=limit,
        offset=offset
    )
    return [OutfitResponse.model_validate(o) for o in outfits]


@router.get("/{id}", response_model=OutfitResponse)
async def get_outfit(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """Get outfit details."""
    repo = OutfitRepository(session)
    outfit = await repo.get_by_id(id, current_user.id)
    if not outfit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found.")
    return OutfitResponse.model_validate(outfit)


@router.delete("/{id}", status_code=status.HTTP_200_OK)
async def delete_outfit(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """Remove saved outfit."""
    repo = OutfitRepository(session)
    deleted = await repo.delete_outfit(id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outfit not found.")
    return {"message": "Outfit removed."}
