import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    hash_refresh_id,
    verify_password,
)
from app.models.user import RefreshSession, User
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

    def _save_refresh_session(self, user_id: uuid.UUID, token: str) -> None:
        payload = decode_token(token) or {}
        token_id = payload.get("jti")
        expires_at = payload.get("exp")
        if not token_id or not expires_at:
            raise RuntimeError("New refresh token is missing its session claims")
        self.session.add(RefreshSession(
            user_id=user_id,
            token_id_hash=hash_refresh_id(token_id),
            expires_at=datetime.fromtimestamp(float(expires_at), tz=timezone.utc),
        ))

    def _issue_tokens(self, user_id: uuid.UUID) -> Tuple[str, str]:
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        self._save_refresh_session(user_id, refresh_token)
        return access_token, refresh_token

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

        access_token, refresh_token = self._issue_tokens(user.id)
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

        access_token, refresh_token = self._issue_tokens(user.id)
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
        token_id = payload.get("jti")
        if not isinstance(user_id_str, str) or not isinstance(token_id, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject."
            )

        try:
            user_id = uuid.UUID(user_id_str)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject."
            )

        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive."
            )

        now = datetime.now(timezone.utc)
        token_hash = hash_refresh_id(token_id)
        active_session = await self.session.scalar(select(RefreshSession.id).where(
            RefreshSession.user_id == user.id,
            RefreshSession.token_id_hash == token_hash,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        ))
        if not active_session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has already been used or revoked."
            )

        consumed = await self.session.execute(update(RefreshSession).where(
            RefreshSession.id == active_session,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        ).values(revoked_at=now))
        if consumed.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has already been used or revoked."
            )

        new_access_token, new_refresh_token = self._issue_tokens(user.id)
        return new_access_token, new_refresh_token

    async def revoke_refresh_token(self, token: Optional[str], user_id: uuid.UUID) -> None:
        """Revoke the refresh cookie for this user when it is still valid."""
        if not token:
            return
        payload = decode_token(token)
        if not payload or payload.get("type") != "refresh":
            return
        token_id = payload.get("jti")
        try:
            token_user_id = uuid.UUID(payload.get("sub", ""))
        except (ValueError, TypeError, AttributeError):
            return
        if not token_id or token_user_id != user_id:
            return
        await self.session.execute(update(RefreshSession).where(
            RefreshSession.user_id == user_id,
            RefreshSession.token_id_hash == hash_refresh_id(token_id),
            RefreshSession.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)))

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
