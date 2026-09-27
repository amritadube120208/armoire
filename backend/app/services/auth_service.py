import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    UserResponse,
    UserUpdateRequest,
)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(self, req: SignupRequest) -> Tuple[User, str, str]:
        """
        User Registration per Backend.md Pipeline 1:
          - Email format & password validated
          - Uniqueness check
          - Password hashed via bcrypt
          - User row created
          - Access + Refresh tokens issued
        """
        existing = await self.user_repo.get_by_email(req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists."
            )

        password_hash = get_password_hash(req.password)
        user = await self.user_repo.create(
            email=req.email,
            password_hash=password_hash,
            name=req.name
        )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token

    async def authenticate(self, req: LoginRequest) -> Tuple[User, str, str]:
        """Authenticates user credentials and issues tokens."""
        user = await self.user_repo.get_by_email(req.email)
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive."
            )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        return user, access_token, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> Tuple[str, str]:
        """Validates refresh token and issues fresh access and refresh tokens."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token."
            )

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject."
            )

        user = await self.user_repo.get_by_id(uuid.UUID(user_id_str))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive."
            )

        new_access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id)
        return new_access_token, new_refresh_token

    async def update_profile(
        self,
        user_id: uuid.UUID,
        req: UserUpdateRequest
    ) -> UserResponse:
        user = await self.user_repo.update(
            user_id=user_id,
            name=req.name,
            location=req.location,
            units=req.units,
            style_tags=req.style_tags,
            color_affinity=req.color_affinity,
            category_affinity=req.category_affinity,
            dress_code_overrides=req.dress_code_overrides,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )
        return UserResponse.model_validate(user)
