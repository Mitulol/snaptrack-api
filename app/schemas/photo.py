from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.thumbnail import ThumbnailStatus


class ThumbnailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ThumbnailStatus
    width: int | None = None
    height: int | None = None
    error: str | None = None
    attempts: int = 0
    updated_at: datetime | None = None


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    caption: str | None = None
    created_at: datetime
    updated_at: datetime
    thumbnail: ThumbnailOut | None = None


class PhotoUpdate(BaseModel):
    caption: str | None = Field(default=None, max_length=2048)


class PhotoList(BaseModel):
    items: list[PhotoOut]
    total: int
    limit: int
    offset: int
