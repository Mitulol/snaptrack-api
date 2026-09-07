"""Pillow image helpers, kept free of DB / Celery so they unit-test cleanly."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Pillow format -> file extension for formats we accept on upload.
SUPPORTED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}


class InvalidImageError(ValueError):
    """Raised when uploaded bytes are not a decodable image we support."""


def probe_image(data: bytes) -> tuple[int, int, str, str]:
    """Return ``(width, height, pillow_format, extension)`` for ``data``."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"not a readable image: {exc}") from exc

    with Image.open(io.BytesIO(data)) as img:
        fmt = (img.format or "").upper()
        if fmt not in SUPPORTED_FORMATS:
            raise InvalidImageError(f"unsupported image format: {fmt or 'unknown'}")
        return img.width, img.height, fmt, SUPPORTED_FORMATS[fmt]


def make_thumbnail(src_path: str | Path, dst_path: str | Path, max_edge: int) -> tuple[int, int]:
    """Write a JPEG thumbnail no larger than ``max_edge`` on its longest side."""
    with Image.open(src_path) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(dst_path, format="JPEG", quality=85, optimize=True)
        return img.width, img.height
