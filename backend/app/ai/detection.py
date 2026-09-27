from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DetectionResult(BaseModel):
    garment_detected: bool = True
    bounding_box: List[int] = [0, 0, 100, 100]  # [ymin, xmin, ymax, xmax]
    confidence: float = 0.95
    category_hint: Optional[str] = None
    mask: Optional[Any] = None
    metadata: Dict[str, Any] = {}


class ClothingDetector:
    """
    Interface for clothing detection and segmentation.
    Isolated behind this wrapper per Backend.md §1 & §6.
    Can be seamlessly swapped for YOLOv8-seg or SAM in Level 2.
    """

    async def detect_and_segment(self, image_bytes: bytes) -> DetectionResult:
        """
        Detects garment in photo and returns bounding box and confidence.
        MVP implementation provides a structured baseline response.
        """
        if len(image_bytes) < 100:
            return DetectionResult(
                garment_detected=False,
                confidence=0.1,
                metadata={"reason": "Corrupted or empty image buffer"}
            )

        return DetectionResult(
            garment_detected=True,
            bounding_box=[10, 10, 90, 90],
            confidence=0.94,
            metadata={"model": "yolo-garment-detector-v1-stub"}
        )


detector = ClothingDetector()
