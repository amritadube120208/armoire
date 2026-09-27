import io
import uuid
from typing import Dict, Optional, Tuple
from PIL import Image, ImageOps
from fastapi import HTTPException, status
from app.ai.quality import quality_analyzer
from app.core.config import settings
from app.schemas.clothing import QualityMetrics


class ImagePipeline:
    """
    Image validation, metadata stripping, re-encoding, and quality assessment.
    Implements Backend.md Pipeline 2 and Pipeline 3:
      - Validates MIME type and magic bytes
      - Strips EXIF/GPS metadata completely
      - Evaluates quality gate (Good / Borderline / Poor)
      - Generates thumbnail
    """

    ALLOWED_MIME_TYPES = {
        "image/jpeg": "JPEG",
        "image/jpg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }

    @staticmethod
    def validate_magic_bytes(header: bytes) -> str:
        """Inspects file magic bytes to verify genuine image format."""
        if len(header) < 12:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file: file header too short or corrupted."
            )

        if header.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        elif header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return "image/webp"
        elif b"ftyp" in header[4:12]:
            return "image/heic"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported image format. Allowed formats: JPEG, PNG, WEBP."
            )

    @classmethod
    def process_and_reencode(
        cls,
        raw_bytes: bytes,
        max_size_mb: int = settings.MAX_UPLOAD_SIZE_MB
    ) -> Tuple[bytes, bytes, QualityMetrics]:
        """
        Validates size & format, strips EXIF/GPS via re-encoding,
        generates thumbnail, and computes quality gate metrics.
        Returns: (clean_original_bytes, thumbnail_bytes, quality_metrics)
        """
        # 1. File size check
        size_mb = len(raw_bytes) / (1024 * 1024)
        if size_mb > max_size_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Image size ({size_mb:.1f}MB) exceeds maximum limit of {max_size_mb}MB."
            )

        # 2. Magic byte check
        cls.validate_magic_bytes(raw_bytes[:16])

        # 3. Decode image and strip EXIF
        try:
            image = Image.open(io.BytesIO(raw_bytes))
            # Handle orientation from EXIF if present before stripping
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupt or invalid image content: {str(e)}"
            )

        # Convert to RGB (neutralizing CMYK or transparent alpha if converting to JPEG)
        rgb_image = image.convert("RGB")

        # 4. Re-encode original (strips all EXIF, GPS, and malicious payloads)
        clean_buf = io.BytesIO()
        rgb_image.save(clean_buf, format="JPEG", quality=90, optimize=True)
        clean_bytes = clean_buf.getvalue()

        # 5. Generate thumbnail (300x300 box preservation)
        thumb_image = rgb_image.copy()
        thumb_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
        thumb_buf = io.BytesIO()
        thumb_image.save(thumb_buf, format="JPEG", quality=85, optimize=True)
        thumb_bytes = thumb_buf.getvalue()

        # 6. Quality Gate Analysis (Laplacian blur, brightness, resolution)
        quality_metrics = quality_analyzer.analyze_bytes(clean_bytes)

        return clean_bytes, thumb_bytes, quality_metrics


image_pipeline = ImagePipeline()
