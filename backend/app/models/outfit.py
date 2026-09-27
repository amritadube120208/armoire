import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.clothing import ClothingItem
    from app.models.feedback import Feedback
    from app.models.weather_snapshot import Recommendation


class Outfit(Base):
    __tablename__ = "outfits"

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
    occasion: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(50),
        default="recommendation",
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="outfits"
    )
    items: Mapped[List["OutfitItem"]] = relationship(
        "OutfitItem",
        back_populates="outfit",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        back_populates="outfit",
        cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        "Recommendation",
        back_populates="outfit",
        cascade="all, delete-orphan"
    )


class OutfitItem(Base):
    __tablename__ = "outfit_items"

    outfit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("outfits.id", ondelete="CASCADE"),
        primary_key=True
    )
    clothing_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("clothing_items.id", ondelete="CASCADE"),
        primary_key=True
    )
    role: Mapped[str] = mapped_column(
        String(50),
        default="item",
        nullable=False
    )

    # Relationships
    outfit: Mapped["Outfit"] = relationship(
        "Outfit",
        back_populates="items"
    )
    clothing_item: Mapped["ClothingItem"] = relationship(
        "ClothingItem",
        lazy="selectin"
    )
