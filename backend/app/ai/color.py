import io
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

COLOR_PALETTE: Dict[str, Tuple[int, int, int]] = {
    "Black": (20, 20, 20),
    "White": (245, 245, 245),
    "Gray": (128, 128, 128),
    "Navy": (20, 30, 80),
    "Blue": (40, 100, 200),
    "Light Blue": (150, 200, 240),
    "Red": (200, 30, 30),
    "Burgundy": (110, 20, 40),
    "Green": (35, 130, 45),
    "Olive": (100, 110, 50),
    "Yellow": (240, 215, 40),
    "Orange": (240, 120, 30),
    "Purple": (128, 40, 160),
    "Pink": (240, 150, 180),
    "Brown": (110, 60, 30),
    "Beige": (225, 205, 175),
}


class ColorExtractor:
    """
    Deterministic color extraction using k-means clustering.
    Implements Backend.md Pipeline 4:
      - k-means (k=2 to 3) on image pixels
      - Reports dominant colors deterministically rather than model guessing
    """

    def __init__(self, k: int = 3):
        self.k = k

    def extract_from_bytes(
        self,
        image_bytes: bytes,
        mask: Optional[np.ndarray] = None
    ) -> Tuple[Optional[str], Optional[str], List[str]]:
        """
        Extract primary color, secondary color, and hex codes.
        """
        try:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # Downsample for fast clustering
            pil_img.thumbnail((150, 150))
            img_arr = np.array(pil_img)

            if mask is not None:
                mask_resized = cv2.resize(mask, (img_arr.shape[1], img_arr.shape[0]))
                pixels = img_arr[mask_resized > 0]
                if len(pixels) < 50:
                    pixels = img_arr.reshape(-1, 3)
            else:
                pixels = img_arr.reshape(-1, 3)

            pixels = np.float32(pixels)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            k = min(self.k, max(1, len(pixels)))
            flags = cv2.KMEANS_RANDOM_CENTERS

            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, flags)

            # Sort clusters by frequency
            counts = np.bincount(labels.flatten())
            sorted_indices = np.argsort(counts)[::-1]

            dominant_colors = []
            hex_codes = []

            for idx in sorted_indices:
                center_rgb = centers[idx].astype(int)
                rgb_tuple = (int(center_rgb[0]), int(center_rgb[1]), int(center_rgb[2]))
                named_color = self._closest_color_name(rgb_tuple)
                hex_code = f"#{rgb_tuple[0]:02x}{rgb_tuple[1]:02x}{rgb_tuple[2]:02x}"

                if named_color not in dominant_colors:
                    dominant_colors.append(named_color)
                    hex_codes.append(hex_code)

            primary = dominant_colors[0] if len(dominant_colors) > 0 else "Unknown"
            secondary = dominant_colors[1] if len(dominant_colors) > 1 else None

            return primary, secondary, hex_codes
        except Exception:
            return "Neutral", None, ["#808080"]

    def _closest_color_name(self, rgb: Tuple[int, int, int]) -> str:
        """Find the Euclidean closest named fashion color in RGB space."""
        min_dist = float("inf")
        closest_name = "Unknown"
        r1, g1, b1 = rgb

        for name, (r2, g2, b2) in COLOR_PALETTE.items():
            dist = (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
            if dist < min_dist:
                min_dist = dist
                closest_name = name

        return closest_name


# Global instance
color_extractor = ColorExtractor()
