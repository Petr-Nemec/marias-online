"""The hub: guest sessions, the lobby, tables and message routing.

Everything here runs on a single asyncio event loop and the table logic never
awaits, so state changes are atomic without locks.  Outgoing messages go
through a bounded per-connection queue; a client that cannot keep up is
disconnected instead of slowing everybody else down.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import json
import logging
import random
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from .. import __version__
from ..table import Table, TableError, TableOptions, static_info
from . import protocol
from .config import Settings

log = logging.getLogger("marias.hub")

ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SEND_QUEUE_SIZE = 64
TICK_SECONDS = 0.2
SWEEP_SECONDS = 5.0
EMPTY_TABLE_TTL = 120.0
IDLE_TABLE_TTL = 1800.0
HELLO_TIMEOUT = 10.0
MAX_SESSIONS = 20_000

# Token-bucket limits: (capacity, refill per second).
MESSAGE_RATE = (30.0, 10.0)
CHAT_RATE = (5.0, 0.5)
CREATE_RATE = (3.0, 1 / 30)
MAX_VIOLATIONS = 20


def new_id(length: int) -> str:
    return "".join(secrets.choice(ID_ALPHABET) for _ in range(length))


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Bucket:
    """A token bucket rate limiter."""

    def __init__(self, capacity: float, refill: float) -> None:
        self.capacity = capacity
        self.refill = refill
        self.tokens = capacity
        self.updated = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.refill)
        self.updated = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


@dataclass
class Session:
    """A guest identity that survives reconnects (identified by a secret token)."""

    id: str
    token_hash: str
    name: str
    table_id: str | None = None
    client: Client | None = None
    last_seen: float = 0.0
    create_bucket: Bucket = field(default_factory=lambda: Bucket(*CREATE_RATE))


class Client:
    """One WebSocket connection."""

    def __init__(self, sender: Any, ip: str) -> None:
        self._sender = sender
        self.ip = ip
        self.session: Session | None = None
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=SEND_QUEUE_SIZE)
        self.closed = False
        self.close_code = 1000
        self.messages = Bucket(*MESSAGE_RATE)
        self.chat = Bucket(*CHAT_RATE)
        self.violations = 0

    def send(self, message: dict[str, Any]) -> None:
        if self.closed:
            return
        text = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        try:
            self.queue.put_nowait(text)
        except asyncio.QueueFull:
            # The client is not reading: drop what is queued and hang up.
            while not self.queue.empty():
                self.queue.get_nowait()
            self.close(1013)

    def error(self, code: str, message: str) -> None:
        self.send({"type": "error", "code": code, "message": message})

    def close(self, code: int = 1000) -> None:
        if self.closed:
            return
        self.closed = True
        self.close_code = code
        # The sentinel must always get in, so the writer is guaranteed to stop.
        while True:
            try:
                self.queue.put_nowait(None)
            except asyncio.QueueFull:
                self.queue.get_nowait()
            else:
                return

    async def writer(self) -> None:
        """Pump queued messages to the socket until the closing sentinel arrives."""
        while (text := await self.queue.get()) is not None:
            await self._sender(text)


class Hub:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rng = random.SystemRandom()
        self.sessions: dict[str, Session] = {}  # by public id
        self._by_token: dict[str, Session] = {}  # by token hash
        self.tables: dict[str, Table] = {}
        self.clients: set[Client] = set()
        self._per_ip: dict[str, int] = {}
        self._lobby_dirty = False
        self._ticker: asyncio.Task[None] | None = None
        self._last_sweep = 0.0

    # --------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._ticker is None:
            self._ticker = asyncio.create_task(self._run(), name="marias-ticker")

    async def stop(self) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ticker
            self._ticker = None
        for client in list(self.clients):
            client.close(1001)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                self.tick(time.monotonic())
            except Exception:  # a bug in one table must not stop the server
                log.exception("tick failed")

    def tick(self, now: float) -> None:
        for table in list(self.tables.values()):
            wakeup = table.next_wakeup()
            if wakeup is not None and now >= wakeup:
                try:
                    changed = table.tick(now)
                except Exception:
                    log.exception("table %s failed and was closed", table.id)
                    self._close_table(table, "Stůl byl kvůli chybě zavřen. Omlouváme se.")
                    continue
                if changed:
                    self._notify_departures(table)
                    self._broadcast_table(table, now)
        if now - self._last_sweep >= SWEEP_SECONDS:
            self._last_sweep = now
            self._sweep(now)
        if self._lobby_dirty:
            self._lobby_dirty = False
            self._broadcast_lobby()

    def _sweep(self, now: float) -> None:
        for table in list(self.tables.values()):
            if table.sweep(now):
                self._notify_departures(table)
                self._broadcast_table(table, now)
                self._lobby_dirty = True
            nobody = not table.humans and not table.spectators
            idle = now - table.last_activity
            if (nobody and idle > EMPTY_TABLE_TTL) or idle > IDLE_TABLE_TTL:
                self._close_table(table, "Stůl byl pro nečinnost zavřen.")
        expired = [
            s
            for s in self.sessions.values()
            if s.client is None and s.table_id is None and now - s.last_seen > self.settings.session_ttl
        ]
        for session in expired:
            self.sessions.pop(session.id, None)
            self._by_token.pop(session.token_hash, None)

    def _notify_departures(self, table: Table) -> None:
        """Tell players the table removed (two missed turns, long disconnect) and send them to the lobby."""
        departures, table.departures = table.departures, []
        for player_id, reason in departures:
            session = self.sessions.get(player_id)
            if session is None or session.table_id != table.id:
                continue
            session.table_id = None
            if session.client is not None:
                session.client.send({"type": "left", "reason": reason})
                self._send_lobby(session.client)
            self._lobby_dirty = True

    def _close_table(self, table: Table, reason: str) -> None:
        self.tables.pop(table.id, None)
        for session in self.sessions.values():
            if session.table_id == table.id:
                session.table_id = None
                if session.client is not None:
                    session.client.send({"type": "left", "reason": reason})
                    self._send_lobby(session.client)
        self._lobby_dirty = True

    # ------------------------------------------------------------- connections

    def can_accept(self, ip: str) -> bool:
        if len(self.clients) >= self.settings.max_connections:
            return False
        return self._per_ip.get(ip, 0) < self.settings.max_connections_per_ip

    def connect(self, client: Client) -> None:
        self.clients.add(client)
        self._per_ip[client.ip] = self._per_ip.get(client.ip, 0) + 1

    def disconnect(self, client: Client) -> None:
        if client not in self.clients:
            return
        self.clients.discard(client)
        remaining = self._per_ip.get(client.ip, 1) - 1
        if remaining > 0:
            self._per_ip[client.ip] = remaining
        else:
            self._per_ip.pop(client.ip, None)
        client.close()
        session = client.session
        if session is None or session.client is not client:
            return
        now = time.monotonic()
        session.client = None
        session.last_seen = now
        table = self.tables.get(session.table_id) if session.table_id else None
        if table is None:
            return
        if table.seat_of(session.id) is not None:
            table.set_connected(session.id, False, now)
            self._broadcast_table(table, now)
        else:
            table.spectators.discard(session.id)
            session.table_id = None
        self._lobby_dirty = True

    # ---------------------------------------------------------------- messages

    def receive(self, client: Client, raw: str) -> None:
        """Handle one text frame from a client."""
        if len(raw.encode("utf-8")) > protocol.MAX_MESSAGE_BYTES:
            self._violation(client, "too_large", "Zpráva je příliš dlouhá.")
            return
        if not client.messages.take():
            self._violation(client, "rate_limited", "Posíláš zprávy příliš rychle.")
            return
        try:
            message = protocol.parse_client_message(raw)
        except ValidationError:
            self._violation(client, "bad_message", "Neplatná zpráva.")
            return
        try:
            self._dispatch(client, message)
        except TableError as error:
            client.error(error.code, error.message)

    def _violation(self, client: Client, code: str, message: str) -> None:
        client.violations += 1
        client.error(code, message)
        if client.violations >= MAX_VIOLATIONS:
            client.close(1008)

    def _dispatch(self, client: Client, message: BaseModel) -> None:
        now = time.monotonic()
        if isinstance(message, protocol.Hello):
            self._hello(client, message, now)
            return
        if isinstance(message, protocol.Ping):
            client.send({"type": "pong"})
            return
        session = client.session
        if session is None:
            raise TableError("no_session", "Nejdřív se představ.")
        session.last_seen = now

        if isinstance(message, protocol.SetName):
            self._set_name(client, session, message.name)
        elif isinstance(message, protocol.CreateTable):
            self._create_table(client, session, message, now)
        elif isinstance(message, protocol.JoinTable):
            self._join_table(session, message, now)
        elif isinstance(message, protocol.WatchTable):
            self._watch_table(session, message, now)
        elif isinstance(message, protocol.LeaveTable):
            self._leave_table(session, now)
        else:
            table = self._table_of(session)
            if isinstance(message, protocol.AddBot):
                self._require_seat(table, session)
                table.add_bot(message.seat, now)
            elif isinstance(message, protocol.RemoveBot):
                self._require_seat(table, session)
                table.remove_bot(message.seat, now)
            elif isinstance(message, protocol.Ready):
                table.set_ready(session.id, now)
            elif isinstance(message, protocol.Chat):
                if not client.chat.take():
                    raise TableError("rate_limited", "Píšeš příliš rychle.")
                text = protocol.clean_text(message.text, protocol.CHAT_MAX)
                if text:
                    table.chat(session.id, session.name, text, now)
            elif isinstance(message, protocol.Action):
                table.act(session.id, message.action.model_dump(exclude_none=True), now)
            self._broadcast_table(table, now)
            self._lobby_dirty = True

    # ---------------------------------------------------------------- sessions

    def _hello(self, client: Client, message: protocol.Hello, now: float) -> None:
        if client.session is not None:
            raise TableError("already_hello", "Už jsme se pozdravili.")
        session: Session | None = None
        token = message.token
        if token:
            candidate = self._by_token.get(hash_token(token))
            if candidate is not None and hmac.compare_digest(candidate.token_hash, hash_token(token)):
                session = candidate
        if session is None:
            self._make_room_for_session()
            token = secrets.token_urlsafe(32)
            name = self._valid_name(message.name) or f"Host {self.rng.randint(1000, 9999)}"
            session = Session(id=new_id(12), token_hash=hash_token(token), name=name)
            self.sessions[session.id] = session
            self._by_token[session.token_hash] = session
        elif message.name:
            # A returning player may only rename himself while not seated.
            new_name = self._valid_name(message.name)
            if new_name and session.table_id is None:
                session.name = new_name

        if session.client is not None and session.client is not client:
            # The same identity opened a second tab: the newest connection wins.
            previous = session.client
            previous.session = None
            previous.send({"type": "replaced"})
            previous.close(4001)
        session.client = client
        session.last_seen = now
        client.session = session
        client.send(
            {
                "type": "welcome",
                "version": __version__,
                "token": token,
                "player": {"id": session.id, "name": session.name},
                "info": static_info(),
            }
        )
        table = self.tables.get(session.table_id) if session.table_id else None
        if table is not None and table.seat_of(session.id) is not None:
            table.set_connected(session.id, True, now)
            self._broadcast_table(table, now)
            self._lobby_dirty = True
        else:
            session.table_id = None
            self._send_lobby(client)

    def _make_room_for_session(self) -> None:
        """Bound memory: forget the longest-idle guests that are neither online nor seated."""
        if len(self.sessions) < MAX_SESSIONS:
            return
        idle = sorted(
            (s for s in self.sessions.values() if s.client is None and s.table_id is None),
            key=lambda s: s.last_seen,
        )
        for session in idle[: max(1, len(self.sessions) - MAX_SESSIONS + 100)]:
            self.sessions.pop(session.id, None)
            self._by_token.pop(session.token_hash, None)
        if len(self.sessions) >= MAX_SESSIONS:
            raise TableError("server_busy", "Server je právě plný, zkus to prosím později.")

    @staticmethod
    def _valid_name(raw: str | None) -> str | None:
        if not raw:
            return None
        name = protocol.clean_text(raw, protocol.NAME_MAX)
        return name if len(name) >= protocol.NAME_MIN else None

    def _set_name(self, client: Client, session: Session, raw: str) -> None:
        name = self._valid_name(raw)
        if name is None:
            raise TableError("bad_name", "Jméno musí mít 2 až 20 znaků.")
        if session.table_id is not None:
            raise TableError("seated", "Jméno lze změnit jen mimo stůl.")
        session.name = name
        client.send({"type": "renamed", "player": {"id": session.id, "name": name}})

    # ------------------------------------------------------------------ tables

    def _table_of(self, session: Session) -> Table:
        table = self.tables.get(session.table_id) if session.table_id else None
        if table is None:
            session.table_id = None
            raise TableError("no_table", "Nejsi u žádného stolu.")
        return table

    @staticmethod
    def _require_seat(table: Table, session: Session) -> None:
        if table.seat_of(session.id) is None:
            raise TableError("not_seated", "Tohle mohou jen hráči u stolu.")

    def _find_table(self, table_id: str, code: str | None) -> Table:
        table = self.tables.get(table_id)
        # The same answer for a missing table and a wrong code: nothing to probe.
        if table is None:
            raise TableError("no_such_table", "Stůl neexistuje, nebo k němu nemáš kód.")
        if table.code is not None and not (code and hmac.compare_digest(table.code, code)):
            raise TableError("no_such_table", "Stůl neexistuje, nebo k němu nemáš kód.")
        return table

    def _create_table(
        self, client: Client, session: Session, message: protocol.CreateTable, now: float
    ) -> None:
        if session.table_id is not None:
            raise TableError("already_at_table", "Nejdřív odejdi od současného stolu.")
        if len(self.tables) >= self.settings.max_tables:
            raise TableError("too_many_tables", "Je otevřeno příliš mnoho stolů, zkus to později.")
        if not session.create_bucket.take():
            raise TableError("rate_limited", "Stoly zakládáš příliš často, chvíli počkej.")
        name = protocol.clean_text(message.name, protocol.TABLE_NAME_MAX) or f"Stůl hráče {session.name}"
        options = TableOptions(
            name=name[: protocol.TABLE_NAME_MAX],
            seats=message.seats,
            stake=message.stake,
            turn_seconds=message.turn_seconds,
            dealing=message.dealing,
            private=message.private,
        )
        table_id = new_id(8)
        while table_id in self.tables:
            table_id = new_id(8)
        table = Table(
            id=table_id,
            options=options,
            rng=self.rng,
            code=new_id(6) if message.private else None,
            created_at=now,
        )
        self.tables[table_id] = table
        table.sit(session.id, session.name, None, now)
        session.table_id = table_id
        self._broadcast_table(table, now)
        self._lobby_dirty = True
        del client

    def _join_table(self, session: Session, message: protocol.JoinTable, now: float) -> None:
        table = self._find_table(message.table, message.code)
        if session.table_id not in (None, table.id):
            raise TableError("already_at_table", "Nejdřív odejdi od současného stolu.")
        if table.status == "playing" and table.seat_of(session.id) is None:
            # Free seats exist mid-deal only next to a pausing player; wait for the deal to end.
            raise TableError("deal_running", "Právě se hraje – přisednout lze po dohrání hry.")
        table.sit(session.id, session.name, message.seat, now)
        session.table_id = table.id
        self._broadcast_table(table, now)
        self._lobby_dirty = True

    def _watch_table(self, session: Session, message: protocol.WatchTable, now: float) -> None:
        table = self._find_table(message.table, message.code)
        if session.table_id not in (None, table.id):
            raise TableError("already_at_table", "Nejdřív odejdi od současného stolu.")
        table.watch(session.id, now)
        session.table_id = table.id
        self._broadcast_table(table, now)
        self._lobby_dirty = True

    def _leave_table(self, session: Session, now: float) -> None:
        table = self.tables.get(session.table_id) if session.table_id else None
        session.table_id = None
        if table is not None:
            table.leave(session.id, now)
            if not table.humans and not table.spectators:
                self._close_table(table, "Stůl byl zavřen.")
            else:
                self._broadcast_table(table, now)
        if session.client is not None:
            session.client.send({"type": "left", "reason": None})
            self._send_lobby(session.client)
        self._lobby_dirty = True

    # --------------------------------------------------------------- broadcast

    def _broadcast_table(self, table: Table, now: float) -> None:
        if table.id not in self.tables:
            return
        members = [s.player_id for s in table.humans] + list(table.spectators)
        for player_id in members:
            session = self.sessions.get(player_id) if player_id else None
            if session is not None and session.client is not None:
                session.client.send({"type": "table", "state": table.snapshot(session.id, now)})

    def _lobby_message(self) -> dict[str, Any]:
        tables = [t.summary() for t in self.tables.values() if not t.options.private]
        tables.sort(key=lambda t: (t["status"] != "waiting", t["options"]["name"].lower()))
        return {"type": "lobby", "tables": tables, "online": len(self.clients)}

    def _send_lobby(self, client: Client) -> None:
        client.send(self._lobby_message())

    def _broadcast_lobby(self) -> None:
        message = self._lobby_message()
        for client in self.clients:
            if client.session is not None and client.session.table_id is None:
                client.send(message)

    def stats(self) -> dict[str, int]:
        return {"tables": len(self.tables), "connections": len(self.clients)}
