from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Body shape for every deliberate 4xx/409 this API raises via HTTPException.

    FastAPI reserves 422 + ``HTTPValidationError`` for request-model validation,
    so business rejections (bad image bytes, ownership, conflicts) use their own
    status codes with this model instead of overloading 422.
    """

    detail: str
