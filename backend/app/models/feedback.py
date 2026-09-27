import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.outfit import Outfit


class Feedback(Base):
    __tablename__ = "feedbacks"

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
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("outfits.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(50),
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
        back_populates="feedbacks"
    )
    outfit: Mapped["Outfit"] = relationship(
        "Outfit",
        back_populates="feedbacks"
    )
