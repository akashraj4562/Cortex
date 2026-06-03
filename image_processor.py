import base64
import io
import os
import uuid

from PIL import Image, ImageOps
import anthropic

from config import ANTHROPIC_API_KEY, DB_PATH

_MAX_SIDE = 1600
_THUMB_MAX = 300
_ORIENTATION_TAG = 0x0112  # EXIF Orientation tag
_REJECTED_MEDIA_TYPES = {"image/heic", "image/heif"}
_ORIENTATION_MODEL = "claude-haiku-4-5-20251001"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _llm_orientation_check(thumbnail_b64: str) -> str:
    """Ask Claude if the image needs rotation. Returns OK | ROTATE_90_CW | ROTATE_90_CCW | ROTATE_180."""
    response = _get_client().messages.create(
        model=_ORIENTATION_MODEL,
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": thumbnail_b64},
                },
                {
                    "type": "text",
                    "text": (
                        "Is this image correctly oriented (upright, not sideways or upside-down)?\n"
                        "Reply with EXACTLY one of: OK | ROTATE_90_CW | ROTATE_90_CCW | ROTATE_180"
                    ),
                },
            ],
        }],
    )
    return response.content[0].text.strip()


def _apply_rotation(img: Image.Image, direction: str) -> Image.Image:
    if direction == "ROTATE_90_CW":
        return img.rotate(-90, expand=True)
    if direction == "ROTATE_90_CCW":
        return img.rotate(90, expand=True)
    if direction == "ROTATE_180":
        return img.rotate(180, expand=True)
    return img


def _resize_if_needed(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) <= _MAX_SIDE:
        return img
    scale = _MAX_SIDE / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)


def process_image(base64_str: str, media_type: str) -> dict:
    """
    Decode, orient, resize, and save an image.
    Returns {"image_path": str, "base64_jpeg": str}.
    Raises ValueError for rejected formats (HEIC/HEIF).
    """
    if media_type.lower() in _REJECTED_MEDIA_TYPES:
        raise ValueError("Please convert to JPG or PNG before uploading.")

    raw_bytes = base64.b64decode(base64_str)
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")

    exif = img.getexif()
    if _ORIENTATION_TAG in exif:
        img = ImageOps.exif_transpose(img)
    else:
        # No EXIF orientation tag — ask LLM with a downscaled thumbnail
        thumb = img.copy()
        thumb.thumbnail((_THUMB_MAX, _THUMB_MAX))
        buf = io.BytesIO()
        thumb.save(buf, format="JPEG", quality=70)
        thumb_b64 = base64.b64encode(buf.getvalue()).decode()
        direction = _llm_orientation_check(thumb_b64)
        img = _apply_rotation(img, direction)

    img = _resize_if_needed(img)

    data_dir = os.path.join(os.path.dirname(DB_PATH), "images")
    os.makedirs(data_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}.jpg"
    image_path = os.path.join(data_dir, filename)
    img.save(image_path, format="JPEG", quality=85)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64_jpeg = base64.b64encode(buf.getvalue()).decode()

    return {"image_path": image_path, "base64_jpeg": b64_jpeg}
