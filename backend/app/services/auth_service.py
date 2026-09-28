import uuid
from datetime import datetime, timedelta, timezone
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
from app.repositories.session_repo import SessionRepository
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
        self.session_repo = SessionRepository(session)

    async def register(
        self,
        req: SignupRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """
        User Registration per Backend.md Pipeline 1:
          - Email format & password validated
          - Uniqueness check
          - Password hashed via bcrypt
          - User row created
          - Session row created in DB
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

        jti = str(uuid.uuid4())
        token_family = uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.session_repo.create(
            user_id=user.id,
            jti=jti,
            token_family=token_family,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id, jti=jti, family=token_family)
        return user, access_token, refresh_token

    async def authenticate(
        self,
        req: LoginRequest,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """Authenticates user credentials and issues tokens with a persisted session."""
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

        jti = str(uuid.uuid4())
        token_family = uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.session_repo.create(
            user_id=user.id,
            jti=jti,
            token_family=token_family,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address
        )

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id, jti=jti, family=token_family)
        return user, access_token, refresh_token

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Validates refresh token against database session store with atomic rotation
        and token reuse detection.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token."
            )

        user_id_str = payload.get("sub")
        jti = payload.get("jti")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject."
            )

        try:
            user_uuid = uuid.UUID(user_id_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed user ID in token."
            )

        user = await self.user_repo.get_by_id(user_uuid)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive."
            )

        # If jti is present, verify against database session store
        if jti:
            db_session = await self.session_repo.get_by_jti(jti)
            if not db_session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found or expired."
                )

            # REUSE DETECTION: A revoked token is being re-presented!
            if db_session.is_revoked:
                # Invalidate the entire token family immediately to contain compromise
                await self.session_repo.revoke_family(db_session.token_family)
                await self.session.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session revoked or compromised. Please sign in again."
                )

            # Check expiration against DB record
            now = datetime.now(timezone.utc)
            session_exp = db_session.expires_at
            if session_exp.tzinfo is None:
                session_exp = session_exp.replace(tzinfo=timezone.utc)
            if session_exp <= now:
                await self.session_repo.revoke_by_jti(jti)
                await self.session.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has expired."
                )

            # ATOMIC ROTATION: Revoke current session, create next in family
            await self.session_repo.revoke_by_jti(jti)
            token_family = db_session.token_family
        else:
            token_family = uuid.uuid4()

        new_jti = str(uuid.uuid4())
        new_expires = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        await self.session_repo.create(
            user_id=user.id,
            jti=new_jti,
            token_family=token_family,
            expires_at=new_expires,
            user_agent=user_agent,
            ip_address=ip_address
        )

        new_access_token = create_access_token(user.id)
        new_refresh_token = create_refresh_token(user.id, jti=new_jti, family=token_family)
        return new_access_token, new_refresh_token

    async def revoke_session_by_token(self, refresh_token: str) -> bool:
        """Revokes the database session identified by the refresh token's jti claim."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return False
        jti = payload.get("jti")
        if not jti:
            return False
        revoked = await self.session_repo.revoke_by_jti(jti)
        if revoked:
            await self.session.commit()
        return revoked

    async def revoke_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revokes all active sessions for a user."""
        count = await self.session_repo.revoke_all_for_user(user_id)
        if count:
            await self.session.commit()
        return count

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
