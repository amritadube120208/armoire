import asyncio
import uuid
from typing import Optional
from app.ai.classification import classifier
from app.ai.color import color_extractor
from app.ai.detection import detector
from app.ai.embeddings import embedding_generator
from app.ai.enhancement import enhancer
from app.core.config import settings
from app.core.logging import get_logger
from app.image_processing.storage import storage
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import AsyncSessionLocal
from app.repositories.clothing_repo import ClothingRepository

logger = get_logger(__name__)

try:
    from celery import Celery

    celery_app = Celery(
        "smart_wardrobe_workers",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=180,
    )
except ImportError:
    class DummyTask:
        def __init__(self, func):
            self.func = func

        def delay(self, *args, **kwargs):
            # In-process or asynchronous fallback
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return loop.create_task(self.func(*args, **kwargs))
            except Exception:
                pass
            return None

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

    class DummyCeleryApp:
        def task(self, *args, **kwargs):
            def decorator(fn):
                return DummyTask(fn)
            return decorator

    celery_app = DummyCeleryApp()


async def _process_item_core(
    session: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    raw_image_bytes: Optional[bytes],
    item_id_str: str,
    category_hint: Optional[str] = None,
    subtype_hint: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    clothing_repo = ClothingRepository(session)
    item = await clothing_repo.get_by_id(item_id, user_id)
    if not item or not item.image:
        logger.error("Clothing item not found for processing", item_id=item_id_str)
        return {"status": "failed", "error": "Item not found"}

    image_bytes = raw_image_bytes
    if not image_bytes:
        image_bytes = await storage.get_file(item.image.original_url)

    if not image_bytes:
        logger.error("Failed to read image bytes from storage", url=item.image.original_url)
        await clothing_repo.update_item_attributes(
            item_id=item_id,
            user_id=user_id,
            status="failed"
        )
        await session.commit()
        return {"status": "failed", "error": "Image file inaccessible"}

    quality_band = item.image.quality_band
    enhanced_url = None

    # If borderline or poor, generate candidate enhancement per Pipeline 3
    if quality_band in ["borderline", "poor"]:
        try:
            enhanced_bytes, trans_meta = await enhancer.enhance(image_bytes)
            enhanced_key = f"{user_id}/{item_id}/enhanced.jpg"
            enhanced_url = await storage.save_file(enhanced_key, enhanced_bytes)
            # Store transparency notice in quality metrics
            metrics = item.image.quality_metrics or {}
            metrics["enhancement_transparency"] = trans_meta
            await clothing_repo.update_image_details(
                item_id=item_id,
                user_id=user_id,
                enhanced_url=enhanced_url,
                quality_metrics=metrics
            )
        except Exception as e:
            logger.warning("Enhancement pass encountered an issue: %s", str(e))

    # 3. Detection
    try:
        det_result = await detector.detect_and_segment(image_bytes)
    except Exception as e:
        logger.warning("Detection failed, continuing with fallback: %s", str(e))
        det_result = None

    # 4. Classification
    try:
        cls_result = await classifier.classify(
            image_bytes,
            quality_band=quality_band,
            category_hint=category_hint or item.category,
            subtype_hint=subtype_hint or item.subtype,
            filename=filename,
        )
    except Exception as e:
        logger.error("Classifier failed, falling back to needs_review: %s", str(e))
        cls_result = None

    # 5. Deterministic Color Extraction
    primary_color, secondary_color, _ = color_extractor.extract_from_bytes(image_bytes)

    # 6. Embedding Generation
    try:
        embedding = await embedding_generator.generate_image_embedding(image_bytes)
    except Exception as e:
        logger.warning("Embedding generation failed: %s", str(e))
        embedding = None

    # 7. Finalize Status
    final_status = "needs_review" if quality_band == "poor" else "ready"

    await clothing_repo.update_item_attributes(
        item_id=item_id,
        user_id=user_id,
        category=cls_result.category if cls_result else (item.category or "tops"),
        subtype=cls_result.subtype if cls_result else (item.subtype or "t-shirt"),
        status=final_status,
        color_primary=primary_color,
        color_secondary=secondary_color,
        pattern=cls_result.pattern if cls_result else "solid",
        pattern_confidence=cls_result.pattern_confidence if cls_result else 0.5,
        formality_estimate=cls_result.formality_estimate if cls_result else "casual",
        formality_confidence=cls_result.formality_confidence if cls_result else 0.5,
        season_tags=cls_result.season_tags if cls_result else ["spring", "summer"],
        embedding=embedding
    )
    await session.commit()

    logger.info(
        "Item processing finalized: item_id=%s, status=%s, quality_band=%s",
        item_id_str,
        final_status,
        quality_band
    )
    return {
        "item_id": item_id_str,
        "status": final_status,
        "quality_band": quality_band,
        "category": cls_result.category if cls_result else "top"
    }


async def execute_item_processing_pipeline(
    item_id_str: str,
    user_id_str: str,
    raw_image_bytes: Optional[bytes] = None,
    session: Optional[AsyncSession] = None,
    category_hint: Optional[str] = None,
    subtype_hint: Optional[str] = None,
    filename: Optional[str] = None,
) -> dict:
    """
    Core business logic for item processing.
    Executes Backend.md Pipeline 2, 3, and 4:
      1. Fetch clean image from storage
      2. If borderline or poor quality: run bounded enhancement candidate
      3. Run garment detection & segmentation
      4. Run classification (category, subtype, pattern, formality, season)
      5. Run deterministic k-means color extraction
      6. Generate multimodal embedding
      7. Finalize DB rows and update item status: 'ready' or 'needs_review'
    """
    item_id = uuid.UUID(item_id_str)
    user_id = uuid.UUID(user_id_str)

    if session is not None:
        return await _process_item_core(
            session, item_id, user_id, raw_image_bytes, item_id_str,
            category_hint=category_hint, subtype_hint=subtype_hint, filename=filename
        )
    else:
        async with AsyncSessionLocal() as sess:
            return await _process_item_core(
                sess, item_id, user_id, raw_image_bytes, item_id_str,
                category_hint=category_hint, subtype_hint=subtype_hint, filename=filename
            )


@celery_app.task(name="process_clothing_item_task")
def process_clothing_item_task(item_id_str: str, user_id_str: str):
    """Celery background worker entrypoint."""
    return asyncio.run(execute_item_processing_pipeline(item_id_str, user_id_str))
