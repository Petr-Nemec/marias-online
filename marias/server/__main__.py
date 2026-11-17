"""Run the server: ``python -m marias.server``.

The game state lives in the memory of one process, so always run exactly one
worker.  Put a TLS-terminating reverse proxy (Caddy, nginx) in front of it.
"""

from __future__ import annotations

import logging

import uvicorn

from .app import create_app
from .config import Settings
from .protocol import MAX_MESSAGE_BYTES


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        # Honour X-Forwarded-* only from proxies listed in FORWARDED_ALLOW_IPS
        # (default 127.0.0.1), so per-IP limits see the real client address.
        proxy_headers=True,
        ws_max_size=MAX_MESSAGE_BYTES * 2,
        ws_ping_interval=20.0,
        ws_ping_timeout=20.0,
        server_header=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
