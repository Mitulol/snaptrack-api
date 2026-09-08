from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.flag_create import FlagCreate
from ...models.flag_out import FlagOut
from ...models.http_validation_error import HTTPValidationError
from ...types import Response


def _get_kwargs(
    photo_id: int,
    *,
    body: FlagCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/photos/{photo_id}/flag".format(
            photo_id=quote(str(photo_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | FlagOut | HTTPValidationError | None:
    if response.status_code == 201:
        response_201 = FlagOut.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 405:
        response_405 = ErrorResponse.from_dict(response.json())

        return response_405

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | FlagOut | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    photo_id: int,
    *,
    client: AuthenticatedClient,
    body: FlagCreate,
) -> Response[ErrorResponse | FlagOut | HTTPValidationError]:
    """Flag Photo

    Args:
        photo_id (int):
        body (FlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagOut | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        photo_id=photo_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    photo_id: int,
    *,
    client: AuthenticatedClient,
    body: FlagCreate,
) -> ErrorResponse | FlagOut | HTTPValidationError | None:
    """Flag Photo

    Args:
        photo_id (int):
        body (FlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagOut | HTTPValidationError
    """

    return sync_detailed(
        photo_id=photo_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    photo_id: int,
    *,
    client: AuthenticatedClient,
    body: FlagCreate,
) -> Response[ErrorResponse | FlagOut | HTTPValidationError]:
    """Flag Photo

    Args:
        photo_id (int):
        body (FlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagOut | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        photo_id=photo_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    photo_id: int,
    *,
    client: AuthenticatedClient,
    body: FlagCreate,
) -> ErrorResponse | FlagOut | HTTPValidationError | None:
    """Flag Photo

    Args:
        photo_id (int):
        body (FlagCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagOut | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            photo_id=photo_id,
            client=client,
            body=body,
        )
    ).parsed
