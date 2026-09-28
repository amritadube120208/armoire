import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import UserSession


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        jti: str,
        token_family: uuid.UUID,
        expires_at: datetime,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> UserSession:
        user_session = UserSession(
            user_id=user_id,
            jti=jti,
            token_family=token_family,
            expires_at=expires_at,
            user_agent=user_agent[:500] if user_agent else None,
            ip_address=ip_address[:50] if ip_address else None,
            is_revoked=False,
            created_at=datetime.now(timezone.utc),
            last_used_at=datetime.now(timezone.utc)
        )
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_by_jti(self, jti: str) -> Optional[UserSession]:
        stmt = select(UserSession).where(UserSession.jti == jti)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_by_jti(self, jti: str) -> bool:
        stmt = (
            update(UserSession)
            .where(UserSession.jti == jti)
            .values(is_revoked=True, last_used_at=datetime.now(timezone.utc))
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount > 0

    async def revoke_family(self, token_family: uuid.UUID) -> int:
        """Revokes all sessions belonging to the given session family (reuse detection)."""
        stmt = (
            update(UserSession)
            .where(UserSession.token_family == token_family)
            .values(is_revoked=True, last_used_at=datetime.now(timezone.utc))
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id)
            .values(is_revoked=True, last_used_at=datetime.now(timezone.utc))
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return res.rowcount
