from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Returns current authenticated user profile and preference state.
    """
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    req: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Updates profile details and onboarding preferences (style tags, color affinities).
    """
    auth_service = AuthService(session)
    updated_user = await auth_service.update_profile(current_user.id, req)
    return updated_user
