import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.clothing import ClothingItem
    from app.models.outfit import Outfit
    from app.models.feedback import Feedback


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    location: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    units: Mapped[str] = mapped_column(
        String(20),
        default="metric",
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    preference: Mapped[Optional["UserPreference"]] = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    clothing_items: Mapped[List["ClothingItem"]] = relationship(
        "ClothingItem",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    outfits: Mapped[List["Outfit"]] = relationship(
        "Outfit",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    sessions: Mapped[List["UserSession"]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False
    )
    token_family: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        index=True,
        nullable=False
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="sessions"
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    style_tags: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False
    )
    color_affinity: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    category_affinity: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )
    dress_code_overrides: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="preference"
    )
