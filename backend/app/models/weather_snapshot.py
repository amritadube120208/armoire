import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.outfit import Outfit


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    feels_like: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    humidity: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    precipitation_prob: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    wind_speed: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    condition: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    outfit_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("outfits.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    weather_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("weather_snapshots.id", ondelete="SET NULL"),
        nullable=True
    )
    weather_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    occasion_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    color_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    style_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    personalization_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    diversity_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    final_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    outfit: Mapped["Outfit"] = relationship(
        "Outfit",
        back_populates="recommendations"
    )
    weather_snapshot: Mapped[Optional["WeatherSnapshot"]] = relationship(
        "WeatherSnapshot"
    )
