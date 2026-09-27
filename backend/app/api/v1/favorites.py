"""
Favorites API router.
Belongs to Phase 8 per Upgradation.md.
"""
import uuid
from fastapi import APIRouter, Depends, status
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/favorites", tags=["Favorites"])


@router.post("/{outfit_id}", status_code=status.HTTP_200_OK)
async def favorite_outfit(
    outfit_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Favorite an outfit."""
    return {"message": "Outfit favorited.", "outfit_id": outfit_id}


@router.delete("/{outfit_id}", status_code=status.HTTP_200_OK)
async def unfavorite_outfit(
    outfit_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Unfavorite an outfit."""
    return {"message": "Outfit unfavorited.", "outfit_id": outfit_id}
