import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.user import User


class ClothingItem(Base):
    __tablename__ = "clothing_items"

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
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True
    )
    subtype: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="processing",
        index=True,
        nullable=False
    )
    wear_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    last_worn_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="clothing_items"
    )
    image: Mapped[Optional["ClothingImage"]] = relationship(
        "ClothingImage",
        back_populates="clothing_item",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    attributes: Mapped[Optional["ClothingAttributes"]] = relationship(
        "ClothingAttributes",
        back_populates="clothing_item",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin"
    )


class ClothingImage(Base):
    __tablename__ = "clothing_images"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    clothing_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("clothing_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    original_url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False
    )
    enhanced_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True
    )
    quality_band: Mapped[str] = mapped_column(
        String(20),
        default="good",
        nullable=False
    )
    enhancement_applied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    quality_metrics: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False
    )

    # Relationship
    clothing_item: Mapped["ClothingItem"] = relationship(
        "ClothingItem",
        back_populates="image"
    )


class ClothingAttributes(Base):
    __tablename__ = "clothing_attributes"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    clothing_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("clothing_items.id", ondelete="CASCADE"),
        unique=True,
        nullable=False
    )
    color_primary: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True
    )
    color_secondary: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    pattern: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    pattern_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    formality_estimate: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    formality_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True
    )
    season_tags: Mapped[list] = mapped_column(
        JSON,
        default=list,
        nullable=False
    )
    embedding: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True
    )

    # Relationship
    clothing_item: Mapped["ClothingItem"] = relationship(
        "ClothingItem",
        back_populates="attributes"
    )
