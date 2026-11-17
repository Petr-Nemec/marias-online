"""A table: seats, the running deal, the score sheet and the table log.

The class contains no networking and no clocks of its own – the server passes
the current time in and decides when to call :meth:`Table.tick`.  That keeps
the whole table logic synchronous and easy to test.

Three or four players may sit at a table.  With four, the dealer pauses and is
settled as a defender, as in competition play.
"""

from __future__ import annotations

import logging
import random
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import bot
from .cards import HEARTS, SUIT_NAMES_CS, SUITS, card_name_cs, collect_deck, cut_deck, shuffled_deck
from .contracts import (
    FLEK_NAMES_CS,
    LEVEL_NAMES_CS,
    PART_NAMES_ACC_CS,
    Contract,
    ContractType,
    Part,
    ladder_table,
)
from .deal import PLAYERS, Deal, Outcome, Phase, RuleError

log = logging.getLogger("marias.table")

ROLE_NAMES = ("forhont", "middle", "rear")
STAKES_HALERE = (10, 20, 50, 100)
TURN_SECONDS = (0, 30, 60, 120)
DEALING_MODES = ("cut", "shuffle")

LOG_SIZE = 200
HISTORY_SIZE = 100
BETWEEN_DEALS_SECONDS = 45.0
DISCONNECTED_TURN_SECONDS = 20.0
DISCONNECT_GRACE_SECONDS = 300.0
#: Consecutive missed turns after which a connected player is removed from the table.
TIMEOUTS_BEFORE_KICK = 2
KICK_REASON = "Dvakrát po sobě jsi nestihl tah, proto tě hra od stolu odebrala."
LONG_DISCONNECT_REASON = "Byl jsi příliš dlouho odpojen, proto tě hra od stolu odebrala."
BOT_NAMES = ("Anča", "Béďa", "Cyril", "Dana")


class TableError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class TableOptions:
    name: str = "Stůl"
    seats: int = 3
    stake: int = 20  # base stake in haléře
    turn_seconds: int = 60
    dealing: str = "cut"
    private: bool = False

    def __post_init__(self) -> None:
        if self.seats not in (3, 4):
            raise TableError("bad_options", "U stolu mohou sedět 3 nebo 4 hráči.")
        if self.stake not in STAKES_HALERE:
            raise TableError("bad_options", "Neplatný základ hry.")
        if self.turn_seconds not in TURN_SECONDS:
            raise TableError("bad_options", "Neplatný časový limit.")
        if self.dealing not in DEALING_MODES:
            raise TableError("bad_options", "Neplatný způsob rozdávání.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "seats": self.seats,
            "stake": self.stake,
            "turn_seconds": self.turn_seconds,
            "dealing": self.dealing,
            "private": self.private,
        }


@dataclass
class Seat:
    index: int
    player_id: str | None = None
    name: str = ""
    is_bot: bool = False
    connected: bool = False
    ready: bool = False
    timeouts: int = 0
    money: int = 0  # units of the base stake
    pb: int = 0
    disconnected_at: float | None = None

    @property
    def occupied(self) -> bool:
        return self.is_bot or self.player_id is not None

    def clear(self) -> None:
        self.player_id = None
        self.name = ""
        self.is_bot = False
        self.connected = False
        self.ready = False
        self.timeouts = 0
        self.money = 0
        self.pb = 0
        self.disconnected_at = None


@dataclass
class Table:
    id: str
    options: TableOptions
    rng: random.Random
    code: str | None = None
    created_at: float = 0.0
    seats: list[Seat] = field(default_factory=list)
    spectators: set[str] = field(default_factory=set)
    status: str = "waiting"  # waiting | playing | between
    dealer: int = 0
    deal: Deal | None = None
    role_seats: tuple[int, int, int] = (0, 1, 2)
    deal_number: int = 0
    deadline: float | None = None
    next_deal_at: float | None = None
    bot_ready_at: float = 0.0
    last_activity: float = 0.0
    log: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=LOG_SIZE))
    history: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=HISTORY_SIZE))
    version: int = 0
    #: Players removed from the table, with the reason: drained by the server.
    departures: list[tuple[str, str]] = field(default_factory=list)
    wall_clock: Callable[[], float] = time.time  # timestamps shown in the log
    _seq: int = 0
    _deck: list[str] | None = None
    _events_seen: int = 0

    def __post_init__(self) -> None:
        if not self.seats:
            self.seats = [Seat(i) for i in range(self.options.seats)]
        self.last_activity = self.created_at

    # ------------------------------------------------------------------ seats

    def seat_of(self, player_id: str) -> Seat | None:
        for seat in self.seats:
            if seat.player_id == player_id:
                return seat
        return None

    @property
    def humans(self) -> list[Seat]:
        return [s for s in self.seats if s.player_id is not None]

    @property
    def full(self) -> bool:
        return all(s.occupied for s in self.seats)

    def sit(self, player_id: str, name: str, index: int | None, now: float) -> Seat:
        existing = self.seat_of(player_id)
        if existing is not None:
            existing.connected = True
            existing.disconnected_at = None
            return existing
        if index is None:
            free = [s for s in self.seats if not s.occupied]
            if not free:
                raise TableError("table_full", "U stolu už není volné místo.")
            seat = free[0]
        else:
            if not 0 <= index < len(self.seats):
                raise TableError("bad_seat", "Takové místo u stolu není.")
            seat = self.seats[index]
            if seat.occupied:
                raise TableError("seat_taken", "Tohle místo je obsazené.")
        seat.clear()
        seat.player_id = player_id
        seat.name = name
        seat.connected = True
        self.spectators.discard(player_id)
        self._say(f"{name} přisedl ke stolu.", now)
        self._touch(now)
        return seat

    def watch(self, player_id: str, now: float) -> None:
        if self.seat_of(player_id) is None:
            self.spectators.add(player_id)
            self._touch(now)

    def leave(self, player_id: str, now: float, *, removed: str | None = None) -> None:
        """A player gets up, or is removed (``removed`` = the reason shown to him).

        Mid-deal a computer finishes the hand for the departed player.
        """
        self.spectators.discard(player_id)
        seat = self.seat_of(player_id)
        if seat is None:
            return
        name = seat.name
        if removed is not None:
            self.departures.append((player_id, removed))
            what = f"{name} byl od stolu odebrán"
        else:
            what = f"{name} odešel od stolu"
        if self.status == "playing" and seat.index in self.role_seats:
            seat.player_id = None
            seat.is_bot = True
            seat.connected = False
            seat.name = f"Počítač (za {name})"
            self._say(f"{what}, hru za něj dohraje počítač.", now)
            self._schedule_turn(now)
        else:
            seat.clear()
            self._say(f"{what}.", now)
            if self.status == "between" and not self.full:
                self.status = "waiting"
                self.next_deal_at = None
        self._touch(now)

    def set_connected(self, player_id: str, connected: bool, now: float) -> None:
        seat = self.seat_of(player_id)
        if seat is None or seat.connected == connected:
            return
        seat.connected = connected
        seat.disconnected_at = None if connected else now
        if connected:
            seat.timeouts = 0
        self._say(f"{seat.name} se {'připojil zpět' if connected else 'odpojil'}.", now)
        if self.status == "playing":
            self._schedule_turn(now)
        self._touch(now)

    def add_bot(self, index: int, now: float) -> None:
        if not 0 <= index < len(self.seats):
            raise TableError("bad_seat", "Takové místo u stolu není.")
        seat = self.seats[index]
        if seat.occupied:
            raise TableError("seat_taken", "Tohle místo je obsazené.")
        used = {s.name for s in self.seats}
        name = next((n for n in BOT_NAMES if f"{n} (počítač)" not in used), "Počítač")
        seat.clear()
        seat.is_bot = True
        seat.name = f"{name} (počítač)"
        seat.ready = True
        self._say(f"Ke stolu přisedl počítač {name}.", now)
        self._touch(now)

    def remove_bot(self, index: int, now: float) -> None:
        if not 0 <= index < len(self.seats):
            raise TableError("bad_seat", "Takové místo u stolu není.")
        seat = self.seats[index]
        if not seat.is_bot:
            raise TableError("not_bot", "Na tomhle místě nesedí počítač.")
        if self.status == "playing":
            raise TableError("deal_running", "Počítač lze odebrat až po dohrání hry.")
        name = seat.name
        seat.clear()
        if self.status == "between":
            self.status = "waiting"
            self.next_deal_at = None
        self._say(f"{name} odešel od stolu.", now)
        self._touch(now)

    def set_ready(self, player_id: str, now: float) -> None:
        seat = self.seat_of(player_id)
        if seat is None:
            raise TableError("not_seated", "Nesedíš u stolu.")
        if self.status == "playing":
            return
        seat.ready = True
        self._touch(now)
        self._maybe_start(now)

    # ---------------------------------------------------------------- dealing

    def _maybe_start(self, now: float) -> None:
        if self.status == "playing" or not self.full:
            return
        present = [s for s in self.humans if s.connected]
        if not present:
            return
        everyone_ready = all(s.ready for s in present)
        timed_out = self.next_deal_at is not None and now >= self.next_deal_at
        if everyone_ready or timed_out:
            self._start_deal(now)

    def _start_deal(self, now: float) -> None:
        count = len(self.seats)
        if self.deal_number == 0:
            self.dealer = self.rng.randrange(count)
        else:
            self.dealer = (self.dealer + 1) % count
        self.role_seats = (
            (self.dealer + 1) % count,
            (self.dealer + 2) % count,
            (self.dealer + 3) % count,
        )
        if self.options.dealing == "cut" and self._deck is not None:
            deck = cut_deck(self._deck, self.rng)
        else:
            deck = shuffled_deck(self.rng)
        self.deal = Deal(deck)
        self._events_seen = 0
        self.deal_number += 1
        self.status = "playing"
        self.next_deal_at = None
        for seat in self.seats:
            seat.ready = seat.is_bot
        self._say(
            f"Hra č. {self.deal_number}: rozdává {self.seats[self.dealer].name}, "
            f"forhont je {self.seats[self.role_seats[0]].name}.",
            now,
            kind="game",
        )
        self._absorb_events(now)
        self._schedule_turn(now)

    # ---------------------------------------------------------------- actions

    def role_of(self, seat_index: int) -> int | None:
        if self.deal is None or seat_index not in self.role_seats:
            return None
        return self.role_seats.index(seat_index)

    def seat_on_turn(self) -> Seat | None:
        if self.status != "playing" or self.deal is None or self.deal.turn is None:
            return None
        return self.seats[self.role_seats[self.deal.turn]]

    def act(self, player_id: str, action: dict[str, Any], now: float) -> None:
        """Apply a game action sent by a human player."""
        seat = self.seat_of(player_id)
        if seat is None:
            raise TableError("not_seated", "Nesedíš u stolu.")
        role = self.role_of(seat.index)
        if self.status != "playing" or self.deal is None or role is None:
            raise TableError("no_deal", "Teď se nehraje.")
        self._apply(role, action)
        seat.timeouts = 0
        self._after_action(now)

    def _apply(self, role: int, action: dict[str, Any]) -> None:
        deal = self.deal
        assert deal is not None
        kind = action.get("a")
        try:
            if kind == "bid":
                deal.bid(role, action.get("level"))  # type: ignore[arg-type]
            elif kind == "hold":
                deal.hold(role)
            elif kind == "pass":
                deal.pass_bid(role)
            elif kind == "omyl":
                deal.omyl(role)
            elif kind == "declare":
                deal.declare(role, _parse_contract(action), _parse_cards(action.get("discard")))
            elif kind == "flek":
                deal.flek(role, _parse_parts(action.get("parts")))
            elif kind == "play":
                card = action.get("card")
                if not isinstance(card, str):
                    raise TableError("bad_action", "Chybí karta.")
                deal.play(role, card, announce=action.get("announce") is not False)
            else:
                raise TableError("bad_action", "Neznámá akce.")
        except RuleError as error:
            raise TableError(error.code, error.message) from error

    def _after_action(self, now: float) -> None:
        deal = self.deal
        assert deal is not None
        self._absorb_events(now)
        self._touch(now)
        if deal.phase is Phase.DONE:
            self._settle(now)
        else:
            self._schedule_turn(now)

    def _schedule_turn(self, now: float) -> None:
        """Set the deadline for whoever is on turn."""
        seat = self.seat_on_turn()
        if seat is None:
            self.deadline = None
            return
        if seat.is_bot:
            deal = self.deal
            assert deal is not None
            # A short, slightly irregular pause; longer right after a finished trick.
            pause = 0.9 + self.rng.random() * 0.8
            if deal.phase is Phase.PLAY and not deal.trick and deal.tricks:
                pause += 1.6
            self.deadline = now + pause
        elif not seat.connected:
            self.deadline = now + DISCONNECTED_TURN_SECONDS
        elif self.options.turn_seconds:
            self.deadline = now + self.options.turn_seconds
        else:
            self.deadline = None

    def tick(self, now: float) -> bool:
        """Advance time-driven behaviour.  Returns True when the state changed."""
        if self.status == "playing":
            seat = self.seat_on_turn()
            if seat is None or self.deadline is None or now < self.deadline:
                return False
            deal = self.deal
            assert deal is not None and deal.turn is not None
            role = deal.turn
            kick: str | None = None
            if seat.player_id is not None and seat.connected:
                # A disconnected player keeps his seat for a grace period instead.
                seat.timeouts += 1
                if seat.timeouts >= TIMEOUTS_BEFORE_KICK:
                    kick = seat.player_id
            try:
                self._apply(role, bot.choose_action(deal, role, self.rng))
            except TableError:
                log.exception("bot move rejected at table %s; using the fallback", self.id)
                self._apply(role, bot.fallback_action(deal, role))
            self._after_action(now)
            if kick is not None:
                self.leave(kick, now, removed=KICK_REASON)
            return True
        if self.status == "between" and self.next_deal_at is not None and now >= self.next_deal_at:
            if self.full and any(s.connected for s in self.humans):
                self._start_deal(now)
            else:
                self.status = "waiting"
                self.next_deal_at = None
                self._touch(now)
            return True
        return False

    def sweep(self, now: float) -> bool:
        """Free the seats of players who have been disconnected for too long."""
        changed = False
        for seat in self.seats:
            if (
                seat.player_id is not None
                and not seat.connected
                and seat.disconnected_at is not None
                and now - seat.disconnected_at > DISCONNECT_GRACE_SECONDS
            ):
                self.leave(seat.player_id, now, removed=LONG_DISCONNECT_REASON)
                changed = True
        return changed

    def next_wakeup(self) -> float | None:
        if self.status == "playing":
            return self.deadline
        if self.status == "between":
            return self.next_deal_at
        return None

    # ------------------------------------------------------------- settlement

    def _settle(self, now: float) -> None:
        deal = self.deal
        assert deal is not None and deal.result is not None and deal.declarer is not None
        result = deal.result
        declarer_seat = self.seats[self.role_seats[deal.declarer]]
        payers = [s for s in self.seats if s.occupied and s.index != declarer_seat.index]
        for seat in payers:
            seat.money -= result.units
            declarer_seat.money += result.units
        for role, points in result.pb.items():
            self.seats[self.role_seats[role]].pb += points

        total = result.units * len(payers)
        contract = result.contract["name"] if result.contract else "omyl"
        if result.units == 0:
            verdict = "vyrovnáno"
        else:
            verdict = f"{'získává' if total > 0 else 'platí'} {self.format_money(abs(total))}"
        self._say(f"{declarer_seat.name} – {contract}: {verdict}.", now, kind="result")
        self.history.append(
            {
                "n": self.deal_number,
                "declarer": declarer_seat.index,
                "declarer_name": declarer_seat.name,
                "contract": contract,
                "outcome": result.outcome,
                "units": result.units,
                "total": total,
                "pb": {str(self.role_seats[r]): p for r, p in result.pb.items()},
                "money": [s.money for s in self.seats],
            }
        )

        if self.options.dealing == "cut":
            self._deck = self._collect_cards(deal)
        self.status = "between"
        self.deadline = None
        self.next_deal_at = now + BETWEEN_DEALS_SECONDS
        for seat in self.seats:
            seat.ready = seat.is_bot
        if not self.humans:
            self.status = "waiting"
            self.next_deal_at = None

    def _collect_cards(self, deal: Deal) -> list[str]:
        """Stack the cards the way a dealer would: pile by pile, never shuffled."""
        piles: list[list[str]] = []
        for role in PLAYERS:
            piles.append([c for t in deal.tricks if t.winner == role for c in t.cards])
            piles.append(list(deal.hands[role]))
        if deal.outcome is Outcome.OMYL:
            pass  # the talon is still in the declarer's hand
        else:
            piles.append(list(deal.discards))
        return collect_deck(piles, self.rng)

    # -------------------------------------------------------------------- log

    def _touch(self, now: float) -> None:
        self.last_activity = now
        self.version += 1

    def _say(self, text: str, now: float, *, kind: str = "system", **extra: Any) -> None:
        self._seq += 1
        del now  # deadlines use the monotonic clock; the log shows wall-clock time
        entry = {"seq": self._seq, "kind": kind, "text": text, "ts": int(self.wall_clock() * 1000)}
        self.log.append({**entry, **extra})
        self.version += 1

    def chat(self, player_id: str, name: str, text: str, now: float) -> None:
        seat = self.seat_of(player_id)
        if seat is None and player_id not in self.spectators:
            raise TableError("not_at_table", "Nejsi u tohoto stolu.")
        label = name if seat is not None else f"{name} (divák)"
        self._say(text, now, kind="chat", name=label, seat=seat.index if seat else None)
        self._touch(now)

    def _absorb_events(self, now: float) -> None:
        """Turn new engine events into table log lines."""
        deal = self.deal
        assert deal is not None
        events = deal.events[self._events_seen :]
        self._events_seen = len(deal.events)
        for event in events:
            line = self._describe(event)
            if line is None:
                continue
            seat = self.role_seats[event["p"]] if "p" in event else None
            self._say(line, now, kind="game", seat=seat, ev=event["t"])

    def _describe(self, event: dict[str, Any]) -> str | None:
        if event.get("auto"):
            return None  # tricks credited by a laid-down hand are not narrated one by one
        kind = event["t"]
        name = self.seats[self.role_seats[event["p"]]].name if "p" in event else ""
        if kind == "bid":
            return f"{name}: {LEVEL_NAMES_CS[event['level']].lower()}?"
        if kind == "hold":
            return f"{name}: mám."
        if kind == "pass":
            return f"{name}: pas."
        if kind == "bid_won":
            if event["forced"]:
                return f"Nikdo nelicitoval – hrát musí forhont {name}. Bere talon."
            return f"{name} vyhrál licitaci ({LEVEL_NAMES_CS[event['level']].lower()}) a bere talon."
        if kind == "omyl":
            return f"{name} skládá karty – omyl."
        if kind == "declare":
            contract = event["contract"]
            text = f"{name} hlásí: {contract['name']}"
            if contract["trump"] and contract["trump"] != HEARTS:
                text += f", trumfy {SUIT_NAMES_CS[contract['trump']]}"
            if contract["helper"]:
                text += f", pomocná {SUIT_NAMES_CS[contract['helper']]}"
            return text + "."
        if kind == "flek":
            if not event["parts"]:
                return f"{name}: dobrý."
            word = FLEK_NAMES_CS[event["stage"] - 1]
            parts = " a ".join(PART_NAMES_ACC_CS[Part(p)] for p in event["parts"])
            return f"{name}: {word} na {parts}!"
        if kind == "play":
            text = f"{name}: {card_name_cs(event['card'])}"
            if event.get("hlaska"):
                text += f" – hlásí {event['hlaska']}"
            return text + "."
        if kind == "laid_down":
            if event["game"] == "all":
                return f"{name} pokládá karty: všechny zbývající štychy bere aktér."
            if event["game"] == "dve_sedmy" and "missing" in event:
                return f"{name} nemá obě hlášené sedmy – dvě sedmy prohrává (ložená hra)."
            if event["game"] == "dve_sedmy":
                return (
                    f"Ložená hra: {name} má {event['theirs']} pomocných proti "
                    f"{event['mine']} aktérovým – dvě sedmy nemohou vyjít."
                )
            game = "betl" if event["game"] == "betl" else "durch"
            return f"{name} pokládá karty: {game} je ložený a nemůže prohrát."
        if kind == "trick":
            winner = self.seats[self.role_seats[event["winner"]]].name
            return f"Štych bere {winner}."
        return None

    # ------------------------------------------------------------------ views

    def format_money(self, units: int) -> str:
        halere = units * self.options.stake
        sign = "-" if halere < 0 else ""
        crowns, rest = divmod(abs(halere), 100)
        return f"{sign}{crowns},{rest:02d} Kč"

    def summary(self) -> dict[str, Any]:
        """Public description for the lobby list."""
        return {
            "id": self.id,
            "options": self.options.to_dict(),
            "status": self.status,
            "deal_number": self.deal_number,
            "seats": [
                {"name": s.name, "bot": s.is_bot, "occupied": s.occupied, "connected": s.connected}
                for s in self.seats
            ],
            "spectators": len(self.spectators),
        }

    def snapshot(self, player_id: str | None, now: float) -> dict[str, Any]:
        """Everything a given client is allowed to know about the table."""
        seat = self.seat_of(player_id) if player_id else None
        role = self.role_of(seat.index) if seat is not None else None
        deal_view: dict[str, Any] | None = None
        if self.deal is not None and self.status in ("playing", "between"):
            deal_view = self.deal.view(role)
            deal_view["role_seats"] = list(self.role_seats)
            deal_view["your_role"] = role
        remaining: int | None = None
        target = self.deadline if self.status == "playing" else self.next_deal_at
        turn_seat = self.seat_on_turn()
        if target is not None and (self.status != "playing" or (turn_seat and not turn_seat.is_bot)):
            remaining = max(0, int((target - now) * 1000))
        return {
            "id": self.id,
            "version": self.version,
            "options": self.options.to_dict(),
            "code": self.code if seat is not None or player_id in self.spectators else None,
            "status": self.status,
            "dealer": self.dealer,
            "deal_number": self.deal_number,
            "you": {"seat": seat.index if seat else None, "spectator": seat is None},
            "seats": [
                {
                    "index": s.index,
                    "name": s.name,
                    "occupied": s.occupied,
                    "bot": s.is_bot,
                    "connected": s.connected or s.is_bot,
                    "ready": s.ready,
                    "money": s.money,
                    "pb": s.pb,
                }
                for s in self.seats
            ],
            "turn_seat": turn_seat.index if turn_seat else None,
            "remaining_ms": remaining,
            "deal": deal_view,
            "log": list(self.log),
            "history": list(self.history),
            "spectators": len(self.spectators),
        }


def static_info() -> dict[str, Any]:
    """Constant data the client needs to build its menus."""
    return {
        "ladder": ladder_table(),
        "suits": list(SUITS),
        "stakes": list(STAKES_HALERE),
        "turn_seconds": list(TURN_SECONDS),
        "dealing": list(DEALING_MODES),
    }


def _parse_contract(action: dict[str, Any]) -> Contract:
    raw = action.get("contract")
    try:
        ctype = ContractType(raw if isinstance(raw, str) else "")
    except ValueError as error:
        raise TableError("bad_action", "Neznámý závazek.") from error
    trump = action.get("trump")
    helper = action.get("helper")
    for value in (trump, helper):
        if value is not None and value not in SUITS:
            raise TableError("bad_action", "Neznámá barva.")
    try:
        return Contract(ctype, trump, helper)
    except ValueError as error:
        raise TableError("bad_contract", "Závazek není úplný: zkontroluj trumfy a pomocnou barvu.") from error


def _parse_cards(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(c, str) for c in value):
        raise TableError("bad_action", "Chybí karty.")
    return list(value)


def _parse_parts(value: Any) -> list[Part]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TableError("bad_action", "Neplatné fleky.")
    try:
        return [Part(p) for p in value]
    except ValueError as error:
        raise TableError("bad_action", "Neznámá část závazku.") from error
