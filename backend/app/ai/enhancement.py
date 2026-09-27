import io
from typing import Any, Dict, Tuple
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from app.core.config import settings


class ImageEnhancer:
    """
    Bounded super-resolution and deblur client.
    STRICTLY ENFORCES Backend.md Pipeline 3:
      - Never silently enhance without transparency
      - Only sharpens/upscales existing pixel information
      - NEVER generatively invents missing garment details or textures
    """

    def __init__(self, api_token: str = settings.REPLICATE_API_TOKEN):
        self.api_token = api_token

    async def enhance(self, image_bytes: bytes) -> Tuple[bytes, Dict[str, Any]]:
        """
        Enhances image using bounded unsharp masking, contrast normalization,
        and sharpening. Returns (enhanced_bytes, transparency_metadata).
        """
        # Load image via Pillow
        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # 1. Unsharp Mask to recover subtle edges from existing pixels
        sharpened = pil_img.filter(ImageFilter.UnsharpMask(radius=2, percent=130, threshold=3))

        # 2. Gentle contrast adjustment
        enhancer = ImageEnhance.Contrast(sharpened)
        enhanced_img = enhancer.enhance(1.08)

        # 3. Export to JPEG bytes
        output_buffer = io.BytesIO()
        enhanced_img.save(output_buffer, format="JPEG", quality=92, optimize=True)
        enhanced_bytes = output_buffer.getvalue()

        transparency_metadata = {
            "technique": "Bounded unsharp mask & edge contrast enhancement",
            "generative_infill_applied": False,
            "transparency_notice": (
                "Image sharpened using existing pixel edge information. "
                "No synthetic textures, logos, or patterns were generated."
            ),
            "original_size_bytes": len(image_bytes),
            "enhanced_size_bytes": len(enhanced_bytes)
        }

        return enhanced_bytes, transparency_metadata


enhancer = ImageEnhancer()
