import io
import cv2
import numpy as np
import pytest
from PIL import Image
from app.ai.color import color_extractor
from app.ai.quality import ImageQualityAnalyzer, quality_analyzer
from app.image_processing.pipeline import image_pipeline


def create_test_image_bytes(
    width: int = 400,
    height: int = 400,
    color: tuple = (100, 150, 200),
    add_edges: bool = True
) -> bytes:
    """Helper to generate in-memory JPEG images with controlled properties."""
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    if add_edges:
        # Add sharp high-frequency checkerboard / lines for high Laplacian variance
        for y in range(0, height, 20):
            for x in range(0, width, 20):
                if (x // 20 + y // 20) % 2 == 0:
                    arr[y:y+20, x:x+20] = (255 - color[0], 255 - color[1], 255 - color[2])

    pil_img = Image.fromarray(arr)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG")
    return buf.getvalue()


def test_quality_gate_sharp_image():
    """Sharp, normal-exposure, high-res image should pass as 'good'."""
    image_bytes = create_test_image_bytes(width=400, height=400, add_edges=True)
    metrics = quality_analyzer.analyze_bytes(image_bytes)

    assert metrics.quality_band == "good"
    assert metrics.width == 400
    assert metrics.height == 400
    assert metrics.blur_score >= 100.0
    assert metrics.details["status"] == "pass"


def test_quality_gate_blurred_image():
    """Severely blurred image should fall into 'poor' or 'borderline' band."""
    # Create smooth image without sharp edges
    image_bytes = create_test_image_bytes(width=400, height=400, add_edges=False)
    metrics = quality_analyzer.analyze_bytes(image_bytes)

    assert metrics.quality_band in ["poor", "borderline"]
    assert metrics.blur_score < 100.0


def test_quality_gate_low_resolution():
    """Image below minimum width/height thresholds must be classified as 'poor'."""
    small_bytes = create_test_image_bytes(width=100, height=100, add_edges=True)
    metrics = quality_analyzer.analyze_bytes(small_bytes)

    assert metrics.quality_band == "poor"
    assert any("Low resolution" in issue for issue in metrics.details["issues"])


def test_quality_gate_underexposed():
    """Dark image should be flagged as underexposed."""
    dark_bytes = create_test_image_bytes(width=300, height=300, color=(5, 5, 5), add_edges=False)
    metrics = quality_analyzer.analyze_bytes(dark_bytes)

    assert metrics.brightness < 40.0
    assert metrics.quality_band == "poor"
    assert any("Underexposed" in issue for issue in metrics.details["issues"])


def test_color_extraction_deterministic():
    """Deterministic k-means color extraction identifies dominant palette."""
    # Create pure blue image
    blue_bytes = create_test_image_bytes(width=200, height=200, color=(0, 0, 220), add_edges=False)
    primary, secondary, hex_codes = color_extractor.extract_from_bytes(blue_bytes)

    assert primary in ["Blue", "Navy"]
    assert len(hex_codes) > 0


def test_magic_byte_validation():
    """Validates genuine magic bytes and rejects arbitrary non-image data."""
    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20
    assert image_pipeline.validate_magic_bytes(jpeg_bytes) == "image/jpeg"

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert image_pipeline.validate_magic_bytes(png_bytes) == "image/png"

    fake_bytes = b"NOT_AN_IMAGE_FILE_HEADER"
    with pytest.raises(Exception):
        image_pipeline.validate_magic_bytes(fake_bytes)


def test_exif_stripping_and_reencoding():
    """Verify that re-encoding produces valid images with stripped EXIF."""
    raw_bytes = create_test_image_bytes(width=300, height=300, add_edges=True)
    clean_bytes, thumb_bytes, metrics = image_pipeline.process_and_reencode(raw_bytes)

    assert len(clean_bytes) > 0
    assert len(thumb_bytes) > 0

    # Ensure thumbnail is bounded to 300x300
    thumb_img = Image.open(io.BytesIO(thumb_bytes))
    assert thumb_img.width <= 300
    assert thumb_img.height <= 300
    # Clean image has no EXIF dict
    clean_img = Image.open(io.BytesIO(clean_bytes))
    assert clean_img.getexif() == {}
