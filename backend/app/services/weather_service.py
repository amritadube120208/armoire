"""
Weather Service — Phase 7 full implementation.

Responsibilities:
  1. Accept lat/lon from the caller (user's stored location or query param).
  2. Check Redis for a 30-minute cached snapshot.
  3. On cache miss: call WeatherClient, persist WeatherSnapshot to DB, cache result.
  4. Return normalised conditions + requirement_band to callers (recommendation engine).

Redis availability is optional — service degrades gracefully if Redis is down.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.weather_snapshot import WeatherSnapshot
from app.weather.client import WeatherClient, build_requirement_band

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60  # 30 minutes per Backend.md Phase 7 spec


def _make_cache_key(lat: float, lon: float) -> str:
    """Round to 2 decimal places so nearby coordinates share a cache slot."""
    return f"weather:{lat:.2f}:{lon:.2f}"


_redis_instance = None
_redis_checked = False


def _get_redis() -> Optional[Any]:
    """
    Lazily attempt to import and connect to Redis with fast availability check and memoization.
    Returns None (no error) if redis-py is not installed or Redis is unreachable.
    """
    global _redis_instance, _redis_checked
    if _redis_checked:
        return _redis_instance
    _redis_checked = True

    import socket
    try:
        host = "127.0.0.1" if settings.REDIS_HOST in ("localhost", "127.0.0.1") else settings.REDIS_HOST
        with socket.create_connection((host, settings.REDIS_PORT), timeout=0.08):
            pass
    except (socket.timeout, ConnectionRefusedError, OSError):
        _redis_instance = None
        return None

    try:
        import redis as redis_lib
        r = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            decode_responses=True,
        )
        r.ping()
        _redis_instance = r
        return r
    except Exception:
        _redis_instance = None
        return None


class WeatherService:
    """
    Orchestrates weather fetching with DB persistence and Redis caching.

    Usage:
        svc = WeatherService(db_session)
        conditions = await svc.get_current_weather(lat=28.6, lon=77.2)
        # → {"temperature": ..., "requirement_band": {...}, ...}
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._client = WeatherClient()
        self._redis = _get_redis()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_current_weather(
        self,
        lat: float = 28.6,
        lon: float = 77.2,
    ) -> Dict[str, Any]:
        """
        Return normalised weather conditions for the given coordinates.

        Priority:
          1. Redis cache (30-min TTL keyed by rounded lat/lon)
          2. Recent DB snapshot (< 30 min old)
          3. Live fetch from OpenWeatherMap → persist → cache
        """
        cache_key = _make_cache_key(lat, lon)

        # 1. Redis cache
        cached = self._read_cache(cache_key)
        if cached:
            return cached

        # 2. Recent DB snapshot
        db_snapshot = await self._get_recent_db_snapshot(lat, lon)
        if db_snapshot:
            result = self._snapshot_to_dict(db_snapshot)
            self._write_cache(cache_key, result)
            return result

        # 3. Live fetch
        try:
            conditions = await self._client.get_current_conditions(lat, lon)
        except Exception as exc:
            logger.warning("WeatherClient fetch failed: %s — using mock", exc)
            from app.weather.client import WeatherClient as WC
            conditions = WC()._mock_conditions(lat, lon)

        # Persist snapshot
        snapshot = await self._persist_snapshot(conditions)

        result = self._snapshot_to_dict(snapshot)
        result["source"] = conditions.get("source", "live")
        if "notice" in conditions:
            result["notice"] = conditions["notice"]

        self._write_cache(cache_key, result)
        return result

    async def get_snapshot_by_id(self, snapshot_id: str) -> Optional[WeatherSnapshot]:
        """Fetch a WeatherSnapshot ORM object by its UUID."""
        import uuid
        try:
            uid = uuid.UUID(snapshot_id)
        except ValueError:
            return None
        stmt = select(WeatherSnapshot).where(WeatherSnapshot.id == uid)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        if not self._redis:
            return None
        try:
            raw = self._redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _write_cache(self, key: str, data: Dict[str, Any]) -> None:
        if not self._redis:
            return
        try:
            self._redis.setex(key, CACHE_TTL_SECONDS, json.dumps(data))
        except Exception:
            pass

    async def _get_recent_db_snapshot(
        self, lat: float, lon: float
    ) -> Optional[WeatherSnapshot]:
        """Return a WeatherSnapshot from the DB that is < 30 minutes old."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=CACHE_TTL_SECONDS)
        stmt = (
            select(WeatherSnapshot)
            .where(WeatherSnapshot.fetched_at >= cutoff)
            .order_by(WeatherSnapshot.fetched_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _persist_snapshot(self, conditions: Dict[str, Any]) -> WeatherSnapshot:
        """Insert a new WeatherSnapshot and commit."""
        snapshot = WeatherSnapshot(
            temperature=conditions.get("temperature", 20.0),
            feels_like=conditions.get("feels_like", 20.0),
            humidity=conditions.get("humidity", 50.0),
            precipitation_prob=conditions.get("precipitation_prob", 0.0),
            wind_speed=conditions.get("wind_speed", 0.0),
            condition=conditions.get("condition", "Clear"),
        )
        self.session.add(snapshot)
        await self.session.commit()
        await self.session.refresh(snapshot)
        return snapshot

    @staticmethod
    def _snapshot_to_dict(snapshot: WeatherSnapshot) -> Dict[str, Any]:
        """Convert a WeatherSnapshot ORM row to the standard response dict."""
        conditions = {
            "snapshot_id": str(snapshot.id),
            "temperature": snapshot.temperature,
            "feels_like": snapshot.feels_like,
            "humidity": snapshot.humidity,
            "precipitation_prob": snapshot.precipitation_prob,
            "wind_speed": snapshot.wind_speed,
            "condition": snapshot.condition,
            "fetched_at": snapshot.fetched_at.isoformat(),
        }
        conditions["requirement_band"] = build_requirement_band(conditions)
        return conditions
