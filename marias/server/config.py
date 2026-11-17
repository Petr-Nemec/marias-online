"""Runtime configuration, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _origins(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    return tuple(o.strip().rstrip("/").lower() for o in raw.split(",") if o.strip())


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    #: Origins allowed to open the WebSocket.  Empty = same origin as the page only.
    allowed_origins: tuple[str, ...] = field(default_factory=tuple)
    max_tables: int = 50
    max_connections: int = 300
    max_connections_per_ip: int = 10
    #: Seconds a guest identity survives without any connection.
    session_ttl: int = 24 * 3600
    #: Send Strict-Transport-Security (enable only when served over HTTPS).
    hsts: bool = False
    log_level: str = "INFO"
    #: Who runs this server and how to reach them – shown in the privacy notice.
    operator: str = ""
    contact: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            host=os.environ.get("MARIAS_HOST", "127.0.0.1"),
            port=_int("MARIAS_PORT", 8000, minimum=1, maximum=65535),
            allowed_origins=_origins("MARIAS_ALLOWED_ORIGINS"),
            max_tables=_int("MARIAS_MAX_TABLES", 50, minimum=1, maximum=1000),
            max_connections=_int("MARIAS_MAX_CONNECTIONS", 300, minimum=1, maximum=10000),
            max_connections_per_ip=_int("MARIAS_MAX_CONNECTIONS_PER_IP", 10, minimum=1, maximum=1000),
            session_ttl=_int("MARIAS_SESSION_TTL", 24 * 3600, minimum=60, maximum=30 * 24 * 3600),
            hsts=_bool("MARIAS_HSTS", False),
            log_level=os.environ.get("MARIAS_LOG_LEVEL", "INFO").upper(),
            operator=os.environ.get("MARIAS_OPERATOR", "").strip()[:200],
            contact=os.environ.get("MARIAS_CONTACT", "").strip()[:200],
        )
