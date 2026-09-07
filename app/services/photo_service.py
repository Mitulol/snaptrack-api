"""Photo domain logic: create / read / update / delete plus cache-aside reads."""

from __future__ import annotations

import logging

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import cache
from app.models import Photo, Thumbnail, ThumbnailStatus, User
from app.schemas.photo import PhotoOut
from app.services import images
from app.storage import delete_photo_files, original_path

logger = logging.getLogger("snaptrack.photo")


class PhotoNotFoundError(Exception):
    pass


def _load(db: Session, photo_id: int) -> Photo | None:
    return db.scalar(
        select(Photo).options(selectinload(Photo.thumbnail)).where(Photo.id == photo_id)
    )


def create_photo(
    db: Session, owner: User, *, data: bytes, filename: str, content_type: str
) -> Photo:
    """Persist an uploaded image and its pending thumbnail row.

    Raises :class:`app.services.images.InvalidImageError` for junk uploads.
    """
    width, height, _fmt, ext = images.probe_image(data)

    photo = Photo(
        owner_id=owner.id,
        original_filename=filename or f"upload{ext}",
        content_type=content_type or "application/octet-stream",
        size_bytes=len(data),
        width=width,
        height=height,
        storage_path="",  # filled once we have an id
    )
    photo.thumbnail = Thumbnail(status=ThumbnailStatus.PENDING)
    db.add(photo)
    db.flush()  # assigns photo.id

    dest = original_path(photo.id, ext)
    dest.write_bytes(data)
    photo.storage_path = str(dest)

    db.commit()
    db.refresh(photo)
    return photo


def get_photo(db: Session, photo_id: int, *, requester: User) -> Photo:
    photo = _load(db, photo_id)
    if photo is None or photo.owner_id != requester.id:
        # Same response whether it is missing or not yours: no existence oracle.
        raise PhotoNotFoundError
    return photo


def get_photo_cached(db: Session, photo_id: int, *, requester: User) -> dict:
    """Return a serialised photo, from Redis when warm, else DB (and warm it)."""
    key = cache.photo_cache_key(photo_id)
    cached = cache.cache_get_json(key)
    if cached is not None:
        if cached.get("owner_id") != requester.id:
            raise PhotoNotFoundError
        return cached

    photo = get_photo(db, photo_id, requester=requester)
    payload = jsonable_encoder(PhotoOut.model_validate(photo))
    cache.cache_set_json(key, payload)
    return payload


def list_photos(
    db: Session, owner: User, *, limit: int, offset: int
) -> tuple[list[Photo], int]:
    total = db.scalar(
        select(func.count()).select_from(Photo).where(Photo.owner_id == owner.id)
    )
    rows = db.scalars(
        select(Photo)
        .options(selectinload(Photo.thumbnail))
        .where(Photo.owner_id == owner.id)
        .order_by(Photo.created_at.desc(), Photo.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), int(total or 0)


def update_photo(db: Session, photo_id: int, *, requester: User, caption: str | None) -> Photo:
    photo = get_photo(db, photo_id, requester=requester)
    photo.caption = caption
    db.commit()
    db.refresh(photo)
    cache.cache_delete(cache.photo_cache_key(photo_id))
    return photo


def delete_photo(db: Session, photo_id: int, *, requester: User) -> None:
    photo = get_photo(db, photo_id, requester=requester)
    db.delete(photo)
    db.commit()
    delete_photo_files(photo_id)
    cache.cache_delete(cache.photo_cache_key(photo_id))
