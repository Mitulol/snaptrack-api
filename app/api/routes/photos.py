from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DbSession
from app.models import ThumbnailStatus
from app.schemas.photo import PhotoList, PhotoOut, PhotoUpdate, ThumbnailOut
from app.services import photo_service
from app.services.images import InvalidImageError
from app.storage import thumbnail_path
from app.workers.tasks import generate_thumbnail

router = APIRouter(prefix="/photos", tags=["photos"])

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@router.post("", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    current_user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form()] = None,
) -> PhotoOut:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large"
        )
    try:
        photo = photo_service.create_photo(
            db,
            current_user,
            data=data,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
        )
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    if caption is not None:
        photo = photo_service.update_photo(
            db, photo.id, requester=current_user, caption=caption
        )

    generate_thumbnail.delay(photo.id)
    return PhotoOut.model_validate(photo)


@router.get("", response_model=PhotoList)
def list_photos(
    current_user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PhotoList:
    items, total = photo_service.list_photos(db, current_user, limit=limit, offset=offset)
    return PhotoList(
        items=[PhotoOut.model_validate(p) for p in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{photo_id}", response_model=PhotoOut)
def get_photo(photo_id: int, current_user: CurrentUser, db: DbSession) -> PhotoOut:
    try:
        return photo_service.get_photo_cached(db, photo_id, requester=current_user)
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None


@router.patch("/{photo_id}", response_model=PhotoOut)
def update_photo(
    photo_id: int, payload: PhotoUpdate, current_user: CurrentUser, db: DbSession
) -> PhotoOut:
    try:
        photo = photo_service.update_photo(
            db, photo_id, requester=current_user, caption=payload.caption
        )
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None
    return PhotoOut.model_validate(photo)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(photo_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    try:
        photo_service.delete_photo(db, photo_id, requester=current_user)
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{photo_id}/thumbnail", response_model=ThumbnailOut)
def get_thumbnail_status(photo_id: int, current_user: CurrentUser, db: DbSession) -> ThumbnailOut:
    try:
        photo = photo_service.get_photo(db, photo_id, requester=current_user)
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None
    return ThumbnailOut.model_validate(photo.thumbnail)


@router.get("/{photo_id}/file")
def get_photo_file(photo_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    try:
        photo = photo_service.get_photo(db, photo_id, requester=current_user)
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None
    return FileResponse(photo.storage_path, media_type=photo.content_type)


@router.get("/{photo_id}/thumbnail/file")
def get_thumbnail_file(photo_id: int, current_user: CurrentUser, db: DbSession) -> FileResponse:
    try:
        photo = photo_service.get_photo(db, photo_id, requester=current_user)
    except photo_service.PhotoNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from None
    if photo.thumbnail.status != ThumbnailStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Thumbnail not ready (status={photo.thumbnail.status.value})",
        )
    return FileResponse(thumbnail_path(photo_id), media_type="image/jpeg")
