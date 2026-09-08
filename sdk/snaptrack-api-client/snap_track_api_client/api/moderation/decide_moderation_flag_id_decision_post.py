from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.decision_create import DecisionCreate
from ...models.error_response import ErrorResponse
from ...models.flag_out import FlagOut
from ...models.http_validation_error import HTTPValidationError
from ...models.moderation_action_out import ModerationActionOut
from ...types import Response


def _get_kwargs(
    flag_id: int,
    *,
    body: DecisionCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/moderation/{flag_id}/decision".format(
            flag_id=quote(str(flag_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError | None:
    if response.status_code == 200:

        def _parse_response_200(data: object) -> FlagOut | ModerationActionOut:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_200_type_0 = FlagOut.from_dict(data)

                return response_200_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            response_200_type_1 = ModerationActionOut.from_dict(data)

            return response_200_type_1

        response_200 = _parse_response_200(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

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
) -> Response[ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    flag_id: int,
    *,
    client: AuthenticatedClient,
    body: DecisionCreate,
) -> Response[ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError]:
    """Decide

    Args:
        flag_id (int):
        body (DecisionCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        flag_id=flag_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    flag_id: int,
    *,
    client: AuthenticatedClient,
    body: DecisionCreate,
) -> ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError | None:
    """Decide

    Args:
        flag_id (int):
        body (DecisionCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError
    """

    return sync_detailed(
        flag_id=flag_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    flag_id: int,
    *,
    client: AuthenticatedClient,
    body: DecisionCreate,
) -> Response[ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError]:
    """Decide

    Args:
        flag_id (int):
        body (DecisionCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        flag_id=flag_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    flag_id: int,
    *,
    client: AuthenticatedClient,
    body: DecisionCreate,
) -> ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError | None:
    """Decide

    Args:
        flag_id (int):
        body (DecisionCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | FlagOut | ModerationActionOut | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            flag_id=flag_id,
            client=client,
            body=body,
        )
    ).parsed
