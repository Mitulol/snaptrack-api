"""Small ASGI middleware.

``AllowHeaderMiddleware`` — Starlette builds the ``Allow`` header of a 405 from
the single route object that matched, but FastAPI registers one route per
decorated function, so ``OPTIONS /photos`` (or any unsupported method) reports
only that route's method. This recomputes ``Allow`` as the union of every route
registered on the same path.
"""

from __future__ import annotations

from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AllowHeaderMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start" and message["status"] == 405:
                methods = {"OPTIONS"}
                for route in scope["app"].routes:
                    match, _ = route.matches(scope)
                    if match is not Match.NONE:
                        methods |= set(getattr(route, "methods", ()) or ())
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"allow"
                ]
                headers.append((b"allow", ", ".join(sorted(methods)).encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
