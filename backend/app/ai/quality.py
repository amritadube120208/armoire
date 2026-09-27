import io
from typing import Dict, Tuple
import cv2
import numpy as np
from PIL import Image
from app.core.config import settings
from app.schemas.clothing import QualityMetrics


class ImageQualityAnalyzer:
    """
    Deterministic quality gate using OpenCV and NumPy (no external ML cost).
    Implements Backend.md Pipeline 3:
      - Blur score via Laplacian variance
      - Resolution check
      - Brightness/exposure histogram analysis
      - 3-band classification: Good / Borderline / Poor
    """

    def __init__(
        self,
        min_width: int = settings.MIN_IMAGE_WIDTH,
        min_height: int = settings.MIN_IMAGE_HEIGHT,
        blur_good: float = settings.BLUR_THRESHOLD_GOOD,
        blur_borderline: float = settings.BLUR_THRESHOLD_BORDERLINE,
        brightness_min: float = settings.BRIGHTNESS_MIN,
        brightness_max: float = settings.BRIGHTNESS_MAX
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.blur_good = blur_good
        self.blur_borderline = blur_borderline
        self.brightness_min = brightness_min
        self.brightness_max = brightness_max

    def analyze_bytes(self, image_bytes: bytes) -> QualityMetrics:
        """Analyze raw image bytes and return complete quality metrics."""
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            # Fallback if cv2 fails to decode but Pillow might
            try:
                pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception:
                return QualityMetrics(
                    blur_score=0.0,
                    width=0,
                    height=0,
                    brightness=0.0,
                    quality_band="poor",
                    details={"error": "Unable to decode image pixels"}
                )

        return self.analyze_cv2(img)

    def analyze_cv2(self, img: np.ndarray) -> QualityMetrics:
        height, width = img.shape[:2]

        # Convert to grayscale for Laplacian variance and luminance
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 1. Blur Detection (Laplacian Variance)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())

        # 2. Brightness Check (Average Luminance)
        brightness = float(np.mean(gray))

        # 3. Classify into Bands: Good / Borderline / Poor
        quality_band, details = self._classify_band(width, height, blur_score, brightness)

        return QualityMetrics(
            blur_score=round(blur_score, 2),
            width=width,
            height=height,
            brightness=round(brightness, 2),
            quality_band=quality_band,
            details=details
        )

    def _classify_band(
        self,
        width: int,
        height: int,
        blur_score: float,
        brightness: float
    ) -> Tuple[str, Dict[str, str]]:
        issues = []

        # Resolution gate
        if width < self.min_width or height < self.min_height:
            issues.append(f"Low resolution: {width}x{height} is below minimum {self.min_width}x{self.min_height}")

        # Brightness gate
        if brightness < self.brightness_min:
            issues.append(f"Underexposed: brightness {brightness:.1f} is below {self.brightness_min}")
        elif brightness > self.brightness_max:
            issues.append(f"Overexposed: brightness {brightness:.1f} is above {self.brightness_max}")

        # Blur gate
        if blur_score < self.blur_borderline:
            issues.append(f"Severe blur: score {blur_score:.1f} is below {self.blur_borderline}")
        elif blur_score < self.blur_good:
            issues.append(f"Moderate blur: score {blur_score:.1f} is below {self.blur_good}")

        # Decision rule
        if width < self.min_width or height < self.min_height or blur_score < self.blur_borderline or brightness < 20.0 or brightness > 240.0:
            band = "poor"
        elif blur_score < self.blur_good or brightness < self.brightness_min or brightness > self.brightness_max:
            band = "borderline"
        else:
            band = "good"

        details = {
            "status": "pass" if band == "good" else "needs_attention",
            "issues": issues,
            "transparency_notice": (
                "Photo passes quality checks cleanly."
                if band == "good"
                else (
                    "Photo is borderline clear. Optional enhancement is available without inventing detail."
                    if band == "borderline"
                    else "Photo quality is poor. Manual attribute verification is recommended."
                )
            )
        }
        return band, details


# Global instance
quality_analyzer = ImageQualityAnalyzer()
