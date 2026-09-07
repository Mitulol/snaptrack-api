"""Reusable OpenAPI ``responses=`` fragments.

Keeping these here means the committed spec lists every status code the API
actually returns — which is what the nightly Schemathesis run checks.
"""

from __future__ import annotations

from app.schemas.errors import ErrorResponse

_M = {"model": ErrorResponse}

UNAUTHORIZED = {401: {**_M, "description": "Missing or invalid bearer token"}}
FORBIDDEN = {403: {**_M, "description": "Authenticated but not allowed"}}
NOT_FOUND = {404: {**_M, "description": "Not found, or not owned by the caller"}}
CONFLICT = {409: {**_M, "description": "Resource state conflict"}}
BAD_REQUEST = {400: {**_M, "description": "Malformed request body or unsupported image"}}
TOO_LARGE = {413: {**_M, "description": "Upload exceeds the size limit"}}
METHOD_NOT_ALLOWED = {405: {**_M, "description": "HTTP method not supported for this path"}}

# Merged into every route of both routers at include time.
COMMON = {**METHOD_NOT_ALLOWED}
# Every authenticated route can produce a 401.
AUTH = {**UNAUTHORIZED}
# Authenticated route that also addresses a specific resource.
AUTH_RESOURCE = {**UNAUTHORIZED, **NOT_FOUND}
# JSON-body route: Starlette returns 400 on unparseable bodies (not 422).
JSON_BODY = {**BAD_REQUEST}
