"""ASGI application: static web client, health check and the game WebSocket."""

from __future__ import annotations

import contextlib
import logging
import re
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from urllib.parse import urlsplit

import anyio
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from .. import __version__
from .config import Settings
from .hub import HELLO_TIMEOUT, Client, Hub

log = logging.getLogger("marias.server")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-:\[\]]{1,255}$")


def origin_allowed(headers: Mapping[str, str], settings: Settings) -> bool:
    """Reject cross-site WebSocket hijacking: browsers always send ``Origin``."""
    origin = headers.get("origin")
    if origin is None:
        return True  # not a browser; such clients cannot ride on a victim's session
    origin = origin.rstrip("/").lower()
    if settings.allowed_origins:
        return origin in settings.allowed_origins
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.netloc == headers.get("host", "").lower()


class SecurityHeaders:
    """Pure ASGI middleware that adds security headers to every HTTP response."""

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        host = ""
        for key, value in scope.get("headers", []):
            if key == b"host":
                host = value.decode("latin-1")
                break
        connect = "'self'"
        if _HOST_RE.match(host):
            connect += f" ws://{host} wss://{host}"
        csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            f"font-src 'self'; connect-src {connect}; object-src 'none'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'"
        )
        extra = [
            (b"content-security-policy", csp.encode("latin-1")),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"no-referrer"),
            (b"cross-origin-opener-policy", b"same-origin"),
            (b"cross-origin-resource-policy", b"same-origin"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
            (b"cache-control", b"no-cache"),
        ]
        if self.hsts:
            extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
        names = {name for name, _ in extra}

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in names]
                message = {**message, "headers": headers + extra}
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def healthz(request: Request) -> Response:
    hub: Hub = request.app.state.hub
    return JSONResponse({"status": "ok", "version": __version__, **hub.stats()})


async def game_socket(websocket: WebSocket) -> None:
    hub: Hub = websocket.app.state.hub
    settings: Settings = websocket.app.state.settings
    ip = websocket.client.host if websocket.client else "unknown"

    if not origin_allowed(websocket.headers, settings):
        log.warning("rejected websocket from origin %r", websocket.headers.get("origin"))
        await websocket.close(code=1008)
        return
    if not hub.can_accept(ip):
        await websocket.close(code=1013)
        return

    await websocket.accept()
    client = Client(websocket.send_text, ip)
    hub.connect(client)
    writer_done = anyio.Event()

    async def write(scope: anyio.CancelScope) -> None:
        try:
            await client.writer()
        except Exception:  # the peer is gone; the reader will notice too
            log.debug("websocket send failed", exc_info=True)
        finally:
            writer_done.set()
            scope.cancel()

    async def read(scope: anyio.CancelScope) -> None:
        try:
            # An anonymous connection must introduce itself promptly.
            with anyio.fail_after(HELLO_TIMEOUT):
                first = await websocket.receive_text()
            hub.receive(client, first)
            if client.session is None:
                client.close(1008)
            while not client.closed:
                hub.receive(client, await websocket.receive_text())
        except (WebSocketDisconnect, TimeoutError, KeyError, RuntimeError):
            # Disconnect, hello timeout, or a binary frame / frame after close.
            pass
        client.close(client.close_code if client.closed else 1000)
        # Let the writer flush a final message (e.g. "replaced"), but not forever.
        with anyio.move_on_after(1.0):
            await writer_done.wait()
        scope.cancel()

    try:
        async with anyio.create_task_group() as group:
            group.start_soon(write, group.cancel_scope)
            group.start_soon(read, group.cancel_scope)
    finally:
        # Release the connection synchronously first, so it happens even when the
        # handler itself is being cancelled; otherwise per-IP counters would leak.
        code = client.close_code if client.closed else 1000
        hub.disconnect(client)
        with anyio.CancelScope(shield=True), contextlib.suppress(Exception):
            await websocket.close(code=code)


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    hub = Hub(settings)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        hub.start()
        try:
            yield
        finally:
            await hub.stop()

    app = Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            WebSocketRoute("/ws", game_socket),
            Mount("/", app=StaticFiles(directory=WEB_DIR, html=True), name="web"),
        ],
        lifespan=lifespan,
    )
    app.state.hub = hub
    app.state.settings = settings
    app.add_middleware(SecurityHeaders, hsts=settings.hsts)
    return app
