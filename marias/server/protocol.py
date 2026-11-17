"""Wire protocol: strict validation of everything a client may send.

Every message is a JSON object with a ``type`` field.  Unknown fields are
rejected, strings are length-limited and free text is normalised, so nothing
unchecked ever reaches the game logic.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

MAX_MESSAGE_BYTES = 2048
NAME_MIN = 2
NAME_MAX = 20
TABLE_NAME_MAX = 30
CHAT_MAX = 200

_SPACES = re.compile(r"\s+")

Suit = Literal["h", "l", "b", "a"]
CardStr = Annotated[str, Field(pattern=r"^[hlba][789XJQKA]$")]
TableId = Annotated[str, Field(pattern=r"^[A-Z2-9]{8}$")]
Code = Annotated[str, Field(pattern=r"^[A-Z2-9]{6}$")]


def clean_text(value: str, limit: int) -> str:
    """Normalise user text: NFC, no control or formatting characters, single spaces."""
    value = unicodedata.normalize("NFC", value)
    value = "".join(
        " " if ch.isspace() else ch
        for ch in value
        if ch.isspace() or unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn")
    )
    return _SPACES.sub(" ", value).strip()[:limit].strip()


class _Message(BaseModel):
    model_config = ConfigDict(extra="forbid", str_max_length=256)


class Hello(_Message):
    type: Literal["hello"]
    token: Annotated[str, Field(min_length=20, max_length=128)] | None = None
    name: Annotated[str, Field(max_length=64)] | None = None


class SetName(_Message):
    type: Literal["set_name"]
    name: Annotated[str, Field(max_length=64)]


class CreateTable(_Message):
    type: Literal["create_table"]
    name: Annotated[str, Field(max_length=64)] = ""
    seats: Literal[3, 4] = 3
    stake: Literal[10, 20, 50, 100] = 20
    turn_seconds: Literal[0, 30, 60, 120] = 60
    dealing: Literal["cut", "shuffle"] = "cut"
    private: bool = False


class JoinTable(_Message):
    type: Literal["join_table"]
    table: TableId
    code: Code | None = None
    seat: Annotated[int, Field(ge=0, le=3)] | None = None


class WatchTable(_Message):
    type: Literal["watch_table"]
    table: TableId
    code: Code | None = None


class LeaveTable(_Message):
    type: Literal["leave_table"]


class AddBot(_Message):
    type: Literal["add_bot"]
    seat: Annotated[int, Field(ge=0, le=3)]


class RemoveBot(_Message):
    type: Literal["remove_bot"]
    seat: Annotated[int, Field(ge=0, le=3)]


class Ready(_Message):
    type: Literal["ready"]


class Back(_Message):
    type: Literal["back"]


class Ping(_Message):
    type: Literal["ping"]


class Chat(_Message):
    type: Literal["chat"]
    text: Annotated[str, Field(min_length=1, max_length=CHAT_MAX * 2)]


class GameAction(_Message):
    """A move in the game; the engine checks it against the rules."""

    a: Literal["bid", "hold", "pass", "omyl", "declare", "flek", "play"]
    level: Annotated[int, Field(ge=1, le=12)] | None = None
    contract: Literal["sedma", "sto", "sto_sedma", "betl", "durch", "dve_sedmy", "dve_sedmy_sto"] | None = (
        None
    )
    trump: Suit | None = None
    helper: Suit | None = None
    discard: Annotated[list[CardStr], Field(max_length=2)] | None = None
    parts: (
        Annotated[list[Literal["hra", "sedma", "sto", "betl", "durch", "dve_sedmy"]], Field(max_length=2)]
        | None
    ) = None
    card: CardStr | None = None
    announce: bool | None = None

    @field_validator("level", mode="before")
    @classmethod
    def _no_bool_level(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("level must be an integer")
        return value


class Action(_Message):
    type: Literal["action"]
    action: GameAction


ClientMessage = Annotated[
    Hello
    | SetName
    | CreateTable
    | JoinTable
    | WatchTable
    | LeaveTable
    | AddBot
    | RemoveBot
    | Ready
    | Back
    | Ping
    | Chat
    | Action,
    Field(discriminator="type"),
]

client_message: TypeAdapter[Any] = TypeAdapter(ClientMessage)


def parse_client_message(raw: str) -> BaseModel:
    """Parse and validate one client frame (raises ``pydantic.ValidationError``)."""
    message: BaseModel = client_message.validate_json(raw, strict=True)
    return message
