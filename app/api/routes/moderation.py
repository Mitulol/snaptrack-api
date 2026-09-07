from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api import responses
from app.api.deps import CurrentAdmin, DbSession
from app.models import ModerationAction
from app.schemas.moderation import (
    DecisionCreate,
    FlagOut,
    ModerationActionOut,
    ModerationQueue,
    QueueItem,
    QueuePhoto,
)
from app.services import moderation_service

router = APIRouter(prefix="/moderation", tags=["moderation"])
# Endpoints are admin-only (CurrentAdmin); flagging lives on the photos router.


@router.get("/queue", response_model=ModerationQueue, responses={**responses.AUTH, **responses.FORBIDDEN})
def moderation_queue(
    _admin: CurrentAdmin,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> ModerationQueue:
    flags, total = moderation_service.list_queue(db, limit=limit, offset=offset)
    items = []
    for f in flags:
        item = QueueItem.model_validate(f)
        item.photo = QueuePhoto.model_validate(f.photo) if f.photo else None
        item.reporter_email = f.reporter.email if f.reporter else None
        items.append(item)
    return ModerationQueue(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{flag_id}/decision",
    response_model=FlagOut | ModerationActionOut,
    responses={
        **responses.AUTH,
        **responses.FORBIDDEN,
        **responses.NOT_FOUND,
        **responses.CONFLICT,
        **responses.JSON_BODY,
    },
)
def decide(
    flag_id: int, payload: DecisionCreate, admin: CurrentAdmin, db: DbSession
) -> FlagOut | ModerationActionOut:
    try:
        result = moderation_service.decide(
            db, flag_id, moderator=admin, decision=payload.decision.value, note=payload.note
        )
    except moderation_service.FlagNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Flag not found"
        ) from None
    except moderation_service.FlagAlreadyResolvedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Flag is already resolved"
        ) from None

    if isinstance(result, ModerationAction):
        return ModerationActionOut.model_validate(result)
    return FlagOut.model_validate(result)
