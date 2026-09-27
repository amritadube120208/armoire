import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.user import User, UserPreference


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.preference))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = (
            select(User)
            .options(selectinload(User.preference))
            .where(User.email == email.lower().strip())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        email: str,
        password_hash: str,
        name: Optional[str] = None
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            name=name
        )
        self.session.add(user)
        await self.session.flush()

        # Initialize default preferences
        preference = UserPreference(
            user_id=user.id,
            style_tags=[],
            color_affinity={},
            category_affinity={},
            dress_code_overrides={}
        )
        self.session.add(preference)
        await self.session.flush()
        await self.session.refresh(user, attribute_names=["preference"])
        return user

    async def update(
        self,
        user_id: uuid.UUID,
        name: Optional[str] = None,
        location: Optional[dict] = None,
        units: Optional[str] = None,
        style_tags: Optional[list] = None,
        color_affinity: Optional[dict] = None,
        category_affinity: Optional[dict] = None,
        dress_code_overrides: Optional[dict] = None,
    ) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None

        if name is not None:
            user.name = name
        if location is not None:
            user.location = location
        if units is not None:
            user.units = units

        if user.preference is None:
            user.preference = UserPreference(user_id=user.id)
            self.session.add(user.preference)

        if style_tags is not None:
            user.preference.style_tags = style_tags
        if color_affinity is not None:
            user.preference.color_affinity = color_affinity
        if category_affinity is not None:
            user.preference.category_affinity = category_affinity
        if dress_code_overrides is not None:
            user.preference.dress_code_overrides = dress_code_overrides

        await self.session.flush()
        return user
