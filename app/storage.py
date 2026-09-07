"""Local-filesystem blob storage shared by the API and the Celery worker.

Layout (rooted at ``settings.photo_storage_dir``, a compose volume mounted in
both containers)::

    photos/<photo_id>/original<ext>
    photos/<photo_id>/thumb.jpg
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings


def storage_root() -> Path:
    root = Path(settings.photo_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def photo_dir(photo_id: int) -> Path:
    d = storage_root() / "photos" / str(photo_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def original_path(photo_id: int, extension: str) -> Path:
    ext = extension if extension.startswith(".") else f".{extension}"
    return photo_dir(photo_id) / f"original{ext}"


def thumbnail_path(photo_id: int) -> Path:
    return photo_dir(photo_id) / "thumb.jpg"


def delete_photo_files(photo_id: int) -> None:
    shutil.rmtree(storage_root() / "photos" / str(photo_id), ignore_errors=True)
