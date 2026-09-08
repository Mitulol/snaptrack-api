from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.http_validation_error import HTTPValidationError
from ...models.thumbnail_out import ThumbnailOut
from ...types import Response


def _get_kwargs(
    photo_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/photos/{photo_id}/thumbnail".format(
            photo_id=quote(str(photo_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | HTTPValidationError | ThumbnailOut | None:
    if response.status_code == 200:
        response_200 = ThumbnailOut.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 405:
        response_405 = ErrorResponse.from_dict(response.json())

        return response_405

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | HTTPValidationError | ThumbnailOut]:
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
) -> Response[ErrorResponse | HTTPValidationError | ThumbnailOut]:
    """Get Thumbnail Status

    Args:
        photo_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | HTTPValidationError | ThumbnailOut]
    """

    kwargs = _get_kwargs(
        photo_id=photo_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    photo_id: int,
    *,
    client: AuthenticatedClient,
) -> ErrorResponse | HTTPValidationError | ThumbnailOut | None:
    """Get Thumbnail Status

    Args:
        photo_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | HTTPValidationError | ThumbnailOut
    """

    return sync_detailed(
        photo_id=photo_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    photo_id: int,
    *,
    client: AuthenticatedClient,
) -> Response[ErrorResponse | HTTPValidationError | ThumbnailOut]:
    """Get Thumbnail Status

    Args:
        photo_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | HTTPValidationError | ThumbnailOut]
    """

    kwargs = _get_kwargs(
        photo_id=photo_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    photo_id: int,
    *,
    client: AuthenticatedClient,
) -> ErrorResponse | HTTPValidationError | ThumbnailOut | None:
    """Get Thumbnail Status

    Args:
        photo_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | HTTPValidationError | ThumbnailOut
    """

    return (
        await asyncio_detailed(
            photo_id=photo_id,
            client=client,
        )
    ).parsed
