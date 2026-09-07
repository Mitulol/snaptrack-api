"""Unit tests for the Pillow helpers (no DB / Celery)."""

import io

import pytest
from PIL import Image

from app.services.images import InvalidImageError, make_thumbnail, probe_image


def _img(w, h, fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format=fmt)
    return buf.getvalue()


def test_probe_returns_dimensions_and_extension():
    w, h, fmt, ext = probe_image(_img(640, 480, "JPEG"))
    assert (w, h, fmt, ext) == (640, 480, "JPEG", ".jpg")


def test_probe_rejects_non_image():
    with pytest.raises(InvalidImageError):
        probe_image(b"\x00\x01\x02not an image")


def test_probe_rejects_unsupported_format():
    buf = io.BytesIO()
    Image.new("RGB", (5, 5)).save(buf, format="BMP")
    with pytest.raises(InvalidImageError):
        probe_image(buf.getvalue())


def test_make_thumbnail_preserves_aspect_and_caps_edge(tmp_path):
    src = tmp_path / "src.png"
    src.write_bytes(_img(1200, 600))
    dst = tmp_path / "thumb.jpg"

    w, h = make_thumbnail(src, dst, max_edge=256)
    assert (w, h) == (256, 128)
    assert dst.exists()
    with Image.open(dst) as out:
        assert out.format == "JPEG"


def test_make_thumbnail_does_not_upscale(tmp_path):
    src = tmp_path / "small.png"
    src.write_bytes(_img(100, 100))
    dst = tmp_path / "thumb.jpg"
    w, h = make_thumbnail(src, dst, max_edge=256)
    assert (w, h) == (100, 100)
