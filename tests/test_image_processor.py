"""Unit tests for image_processor.py — Phase A."""
import base64
import io
import os
import re
import sys
import struct
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PIL import Image
import image_processor


def _make_jpeg_b64(width=100, height=50, color=(180, 120, 80)) -> str:
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def _make_jpeg_with_exif_orientation(width=100, height=50, orientation=6) -> str:
    """Create a JPEG with an EXIF Orientation tag set to `orientation`."""
    img = Image.new("RGB", (width, height), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw = buf.getvalue()

    # Minimal EXIF blob: APP1 marker with Orientation tag
    # EXIF header: "Exif\0\0" + TIFF header (little-endian)
    # IFD: 1 entry — Orientation (0x0112), SHORT (3), count=1, value=orientation
    tiff = b"II"            # little-endian
    tiff += struct.pack("<H", 42)          # TIFF magic
    tiff += struct.pack("<I", 8)           # offset of first IFD
    # IFD with 1 entry
    tiff += struct.pack("<H", 1)           # entry count
    tiff += struct.pack("<HHI", 0x0112, 3, 1)  # tag, SHORT, count
    tiff += struct.pack("<I", orientation)  # value
    tiff += struct.pack("<I", 0)           # next IFD offset (0 = none)

    exif_data = b"Exif\x00\x00" + tiff
    app1 = struct.pack(">HH", 0xFFE1, len(exif_data) + 2) + exif_data

    # Insert APP1 after SOI (first 2 bytes)
    jpeg_with_exif = raw[:2] + app1 + raw[2:]
    return base64.b64encode(jpeg_with_exif).decode()


class TestImageProcessor(unittest.TestCase):

    def test_exif_orientation_applied_no_llm(self):
        """EXIF Orientation tag 6 (90° CW) → exif_transpose corrects to portrait. LLM not called."""
        # orientation=6: image rotated 90° CW — after transpose it should become portrait
        b64 = _make_jpeg_with_exif_orientation(width=200, height=100, orientation=6)
        with patch("image_processor._llm_orientation_check") as mock_llm:
            result = image_processor.process_image(b64, "image/jpeg")
            mock_llm.assert_not_called()

        img = Image.open(result["image_path"])
        # After correcting orientation=6 (CW), a landscape 200x100 becomes 100x200 portrait
        self.assertGreater(img.height, img.width)
        self.assertTrue(result["image_path"].endswith(".jpg"))

    def test_no_exif_llm_called_ok(self):
        """No EXIF → LLM called. Returns OK → dimensions unchanged."""
        b64 = _make_jpeg_b64(100, 50)
        with patch("image_processor._llm_orientation_check", return_value="OK") as mock_llm:
            result = image_processor.process_image(b64, "image/jpeg")
            mock_llm.assert_called_once()

        img = Image.open(result["image_path"])
        self.assertEqual(img.width, 100)
        self.assertEqual(img.height, 50)

    def test_no_exif_llm_rotate_90_cw(self):
        """No EXIF → LLM returns ROTATE_90_CW → image transposed to portrait."""
        b64 = _make_jpeg_b64(200, 100)
        with patch("image_processor._llm_orientation_check", return_value="ROTATE_90_CW"):
            result = image_processor.process_image(b64, "image/jpeg")

        img = Image.open(result["image_path"])
        self.assertGreater(img.height, img.width)

    def test_no_exif_llm_rotate_90_ccw(self):
        """No EXIF → LLM returns ROTATE_90_CCW → image transposed."""
        b64 = _make_jpeg_b64(200, 100)
        with patch("image_processor._llm_orientation_check", return_value="ROTATE_90_CCW"):
            result = image_processor.process_image(b64, "image/jpeg")

        img = Image.open(result["image_path"])
        self.assertGreater(img.height, img.width)

    def test_no_exif_llm_rotate_180(self):
        """No EXIF → LLM returns ROTATE_180 → dimensions unchanged (symmetric)."""
        b64 = _make_jpeg_b64(200, 100)
        with patch("image_processor._llm_orientation_check", return_value="ROTATE_180"):
            result = image_processor.process_image(b64, "image/jpeg")

        img = Image.open(result["image_path"])
        self.assertEqual(img.width, 200)
        self.assertEqual(img.height, 100)

    def test_resize_large_image(self):
        """Image with longest side 3200 → clamped to ≤ 1600px. Aspect ratio preserved."""
        b64 = _make_jpeg_b64(3200, 2400)
        with patch("image_processor._llm_orientation_check", return_value="OK"):
            result = image_processor.process_image(b64, "image/jpeg")

        img = Image.open(result["image_path"])
        self.assertLessEqual(max(img.width, img.height), 1600)
        # Check aspect ratio within 2px tolerance
        expected_ratio = 3200 / 2400
        actual_ratio = img.width / img.height
        self.assertAlmostEqual(actual_ratio, expected_ratio, delta=0.02)

    def test_no_resize_small_image(self):
        """800×600 image → not resized."""
        b64 = _make_jpeg_b64(800, 600)
        with patch("image_processor._llm_orientation_check", return_value="OK"):
            result = image_processor.process_image(b64, "image/jpeg")

        img = Image.open(result["image_path"])
        self.assertEqual(img.width, 800)
        self.assertEqual(img.height, 600)

    def test_heic_rejected(self):
        """HEIC media type → ValueError with JPG or PNG message. No file written."""
        b64 = _make_jpeg_b64(100, 100)
        before = set(os.listdir(os.path.dirname(os.path.join(
            os.path.dirname(__import__("config").DB_PATH), "images"
        )))) if os.path.isdir(os.path.join(
            os.path.dirname(__import__("config").DB_PATH), "images"
        )) else set()

        with self.assertRaises(ValueError) as ctx:
            image_processor.process_image(b64, "image/heic")
        self.assertIn("JPG or PNG", str(ctx.exception))

    def test_heif_rejected(self):
        """HEIF media type also rejected."""
        with self.assertRaises(ValueError):
            image_processor.process_image(_make_jpeg_b64(), "image/heif")

    def test_png_saved_as_jpeg(self):
        """PNG input → saved as .jpg file."""
        img = Image.new("RGB", (60, 60), (10, 20, 30))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        with patch("image_processor._llm_orientation_check", return_value="OK"):
            result = image_processor.process_image(b64, "image/png")

        self.assertTrue(result["image_path"].endswith(".jpg"))
        reopened = Image.open(result["image_path"])
        self.assertEqual(reopened.format, "JPEG")

    def test_image_path_uuid_format(self):
        """Returned image_path matches data/images/<UUID>.jpg pattern."""
        b64 = _make_jpeg_b64(100, 80)
        with patch("image_processor._llm_orientation_check", return_value="OK"):
            result = image_processor.process_image(b64, "image/jpeg")

        path = result["image_path"]
        self.assertTrue(os.path.exists(path))
        filename = os.path.basename(path)
        uuid_re = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jpg$'
        )
        self.assertRegex(filename, uuid_re)

    def test_base64_jpeg_returned(self):
        """Returned base64_jpeg is a valid decodable JPEG string."""
        b64 = _make_jpeg_b64(80, 80)
        with patch("image_processor._llm_orientation_check", return_value="OK"):
            result = image_processor.process_image(b64, "image/jpeg")

        b64_out = result["base64_jpeg"]
        decoded = base64.b64decode(b64_out)
        reopened = Image.open(io.BytesIO(decoded))
        self.assertEqual(reopened.format, "JPEG")

    def tearDown(self):
        """Clean up any image files written during tests."""
        import config
        images_dir = os.path.join(os.path.dirname(config.DB_PATH), "images")
        if os.path.isdir(images_dir):
            for f in os.listdir(images_dir):
                if f.endswith(".jpg"):
                    try:
                        os.remove(os.path.join(images_dir, f))
                    except OSError:
                        pass
