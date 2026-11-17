"""State machine for a single deal of licitovaný mariáš.

The engine is pure and deterministic: it never touches I/O, clocks or random
numbers (the deck order is supplied by the caller).  Players are identified by
their role in the deal:

* ``0`` – forhont (first to receive cards, leads to the first trick),
* ``1`` – the middle player,
* ``2`` – zadák (the last player; the dealer in a three-handed game).

Every state-changing method validates its input and raises :class:`RuleError`
without modifying the state when the action is not allowed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cards import (
    Card,
    card_points,
    deal_cards,
    is_card,
    is_sharp,
    sort_hand,
)
from .contracts import (
    FLEK_NAMES_CS,
    LEVEL_NAMES_CS,
    MAX_FLEKS,
    MAX_LEVEL,
    MIN_LEVEL,
    TWO_SEVENS_TYPES,
    Contract,
    ContractType,
    Part,
)
from .rules import legal_cards, winning_index

FORHONT = 0
MIDDLE = 1
REAR = 2
PLAYERS = (FORHONT, MIDDLE, REAR)
TRICKS_PER_DEAL = 10


class RuleError(Exception):
    """An action that the rules (or the current state) do not allow."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Phase(StrEnum):
    BIDDING = "bidding"
    TALON = "talon"
    FLEK = "flek"
    PLAY = "play"
    DONE = "done"


class Outcome(StrEnum):
    """Why and how the deal ended."""

    PLAYED = "played"
    OMYL = "omyl"  # declarer folded a plain sedma
    APPROVED = "approved"  # sedma that is settled without play
    FOUR_HELPERS = "four_helpers"  # dvě sedmy against 4+ helper cards in one hand
    MISSING_SEVEN = "missing_seven"  # dvě sedmy announced without both sevens


@dataclass(frozen=True)
class TrickRecord:
    leader: int
    cards: tuple[Card, ...]
    winner: int

    def player_of(self, index: int) -> int:
        return (self.leader + index) % 3

    def card_of(self, player: int) -> Card:
        return self.cards[(player - self.leader) % 3]

    def to_dict(self) -> dict[str, Any]:
        return {
            "leader": self.leader,
            "cards": [{"p": self.player_of(i), "c": c} for i, c in enumerate(self.cards)],
            "winner": self.winner,
        }


class Deal:
    """One deal from the first bid to the settlement."""

    def __init__(self, deck: Sequence[Card]) -> None:
        hands, talon = deal_cards(deck)
        self.hands: list[list[Card]] = [sort_hand(h) for h in hands]
        self.initial_hands: tuple[tuple[Card, ...], ...] = tuple(tuple(h) for h in self.hands)
        self.talon: tuple[Card, ...] = tuple(talon)

        self.phase = Phase.BIDDING
        self.turn: int | None = REAR
        self.events: list[dict[str, Any]] = []

        # --- bidding -------------------------------------------------------
        self.bid_level = 0
        self.bid_asker = REAR
        self.bid_holder = FORHONT
        self.bid_reserve: int | None = MIDDLE
        self.bid_role = "ask"  # whose move it is: the asker's or the holder's
        self.bid_out: set[int] = set()

        # --- talon / contract -----------------------------------------------
        self.declarer: int | None = None
        self.min_level = 0
        self.forced = False  # nobody bid; forhont has to play
        self.contract: Contract | None = None
        self.declarer_twelve: tuple[Card, ...] = ()
        self.discards: tuple[Card, ...] = ()
        self.play_hands: tuple[tuple[Card, ...], ...] = ()

        # --- doubling --------------------------------------------------------
        self.flek_counts: dict[Part, int] = {}
        self.flek_stage = 0
        self.flek_open: list[Part] = []
        self.flek_queue: list[int] = []
        self._flek_stage_union: set[Part] = set()
        self.flekkers: set[int] = set()  # defenders who doubled anything

        # --- play ------------------------------------------------------------
        self.leader: int | None = None
        self.trick: list[Card] = []
        self.tricks: list[TrickRecord] = []
        self.hlasky: list[list[str]] = [[], [], []]
        self.auto_lost: set[Part] = set()
        self.two_sevens_failed = False

        # --- result ----------------------------------------------------------
        self.outcome: Outcome | None = None
        self.result: Any = None  # scoring.DealResult once the deal is done

        self._log("deal")

    # ------------------------------------------------------------------ utils

    def _log(self, kind: str, **data: Any) -> None:
        self.events.append({"t": kind, **data})

    def _require(self, phase: Phase, player: int) -> None:
        if player not in PLAYERS:
            raise RuleError("bad_player", "Neznámý hráč.")
        if self.phase is not phase:
            raise RuleError("wrong_phase", "Tahle akce teď není možná.")
        if self.turn != player:
            raise RuleError("not_your_turn", "Nejsi na řadě.")

    @property
    def defenders(self) -> tuple[int, int]:
        """The two defenders in playing order after the declarer."""
        if self.declarer is None:
            raise RuleError("no_declarer", "Aktér ještě není znám.")
        return ((self.declarer + 1) % 3, (self.declarer + 2) % 3)

    # ---------------------------------------------------------------- bidding

    def bid(self, player: int, level: int) -> None:
        """The asking player offers a step of the ladder (steps may be skipped)."""
        self._require(Phase.BIDDING, player)
        if self.bid_role != "ask":
            raise RuleError("must_answer", "Na nabídku odpovídáš jen „mám“, nebo „pas“.")
        if isinstance(level, bool) or not isinstance(level, int):
            raise RuleError("bad_level", "Neplatný licitační stupeň.")
        if not max(self.bid_level + 1, MIN_LEVEL) <= level <= MAX_LEVEL:
            raise RuleError("bid_too_low", "Musíš nabídnout vyšší stupeň než dosavadní.")
        self.bid_level = level
        self.bid_role = "answer"
        self.turn = self.bid_holder
        self._log("bid", p=player, level=level)

    def hold(self, player: int) -> None:
        """The player with priority matches the offered step („mám“)."""
        self._require(Phase.BIDDING, player)
        if self.bid_role != "answer":
            raise RuleError("must_ask", "Teď nabízíš ty: zvol stupeň, nebo pasuj.")
        self.bid_role = "ask"
        self.turn = self.bid_asker
        self._log("hold", p=player, level=self.bid_level)

    def pass_bid(self, player: int) -> None:
        """Withdraw from the auction (a withdrawn player cannot come back)."""
        self._require(Phase.BIDDING, player)
        self.bid_out.add(player)
        self._log("pass", p=player)
        if self.bid_role == "ask":
            if self.bid_reserve is not None:
                # The waiting player takes over the asker's position.
                self.bid_asker, self.bid_reserve = self.bid_reserve, None
                self.turn = self.bid_asker
            else:
                self._finish_bidding(self.bid_holder)
        elif self.bid_reserve is not None:
            # The waiting player inherits the priority and may simply hold.
            self.bid_holder, self.bid_reserve = self.bid_reserve, None
            self.turn = self.bid_holder
        else:
            self._finish_bidding(self.bid_asker)

    def _finish_bidding(self, winner: int) -> None:
        self.forced = self.bid_level == 0
        self.min_level = max(self.bid_level, MIN_LEVEL)
        self.declarer = winner
        self.hands[winner] = sort_hand([*self.hands[winner], *self.talon])
        self.declarer_twelve = tuple(self.hands[winner])
        self.phase = Phase.TALON
        self.turn = winner
        self._log("bid_won", p=winner, level=self.min_level, forced=self.forced)

    # ------------------------------------------------------------------ talon

    @property
    def can_omyl(self) -> bool:
        """Only a plain sedma may be folded without play („omyl“)."""
        return self.phase is Phase.TALON and self.min_level == MIN_LEVEL

    def omyl(self, player: int) -> None:
        self._require(Phase.TALON, player)
        if not self.can_omyl:
            raise RuleError("omyl_not_allowed", "Složit karty lze jen při vylicitované sedmě.")
        self._log("omyl", p=player)
        self._finish(Outcome.OMYL)

    def declare(self, player: int, contract: Contract, discards: Sequence[Card]) -> None:
        """Discard two cards to the talon and announce the final contract."""
        self._require(Phase.TALON, player)
        hand = self.hands[player]
        cards = list(discards)
        if len(cards) != 2 or cards[0] == cards[1] or not all(is_card(c) for c in cards):
            raise RuleError("bad_discard", "Do talonu musíš odložit právě dvě karty.")
        if any(c not in hand for c in cards):
            raise RuleError("bad_discard", "Odkládat můžeš jen karty, které máš v ruce.")
        if contract.level < self.min_level:
            raise RuleError(
                "contract_too_low",
                f"Musíš ohlásit nejméně vylicitovaný závazek: {LEVEL_NAMES_CS[self.min_level]}.",
            )
        if not contract.plain and any(is_sharp(c) for c in cards):
            raise RuleError("sharp_discard", "Esa a desítky smí do talonu jen při betlu a durchu.")
        if any(c in contract.announced_sevens for c in cards):
            raise RuleError("seven_discard", "Hlášenou sedmu nelze odložit do talonu.")
        if contract.type is ContractType.SEDMA and f"{contract.trump}7" not in hand:
            raise RuleError("no_seven", "Sedmu nelze hrát bez trumfové sedmy v ruce.")

        self.contract = contract
        self.discards = (cards[0], cards[1])
        remaining = [c for c in hand if c not in cards]
        self.hands[player] = sort_hand(remaining, plain=contract.plain)
        if contract.plain:
            for other in PLAYERS:
                self.hands[other] = sort_hand(self.hands[other], plain=True)
        self.play_hands = tuple(tuple(h) for h in self.hands)
        self._log("declare", p=player, contract=contract.to_dict())

        self.flek_counts = dict.fromkeys(contract.parts, 0)
        self.flek_stage = 1
        self.flek_open = list(contract.parts)
        self.flek_queue = list(self.defenders)
        self._flek_stage_union = set()
        self.phase = Phase.FLEK
        self.turn = self.flek_queue[0]

    # ------------------------------------------------------------------- flek

    def flek(self, player: int, parts: Sequence[Part]) -> None:
        """Double the given parts of the contract; an empty list means „dobrý“."""
        self._require(Phase.FLEK, player)
        chosen = list(parts)
        if len(set(chosen)) != len(chosen) or any(p not in self.flek_open for p in chosen):
            raise RuleError("bad_flek", "Tuhle část závazku teď flekovat nelze.")
        self._flek_stage_union.update(chosen)
        if chosen and player != self.declarer:
            self.flekkers.add(player)
        self._log("flek", p=player, parts=[p.value for p in chosen], stage=self.flek_stage)
        self.flek_queue.pop(0)
        if self.flek_queue:
            self.turn = self.flek_queue[0]
            return

        doubled = [p for p in self.flek_open if p in self._flek_stage_union]
        for part in doubled:
            self.flek_counts[part] += 1
        if not doubled or self.flek_stage >= MAX_FLEKS:
            self._after_flek()
            return
        # Next round: only what the other side has just doubled may be raised.
        self.flek_stage += 1
        self.flek_open = doubled
        self._flek_stage_union = set()
        assert self.declarer is not None
        self.flek_queue = [self.declarer] if self.flek_stage % 2 == 0 else list(self.defenders)
        self.turn = self.flek_queue[0]

    def _after_flek(self) -> None:
        assert self.contract is not None and self.declarer is not None
        contract = self.contract
        declarer_hand = self.hands[self.declarer]
        self.flek_open = []
        self.flek_queue = []

        # A sedma is played only when the sedma was doubled or the game redoubled;
        # otherwise the parts are settled as approved / conceded.
        if (
            contract.type is ContractType.SEDMA
            and self.flek_counts[Part.SEDMA] == 0
            and self.flek_counts[Part.HRA] < 2
        ):
            self._finish(Outcome.APPROVED)
            return

        missing_seven = any(c not in declarer_hand for c in contract.announced_sevens)
        if contract.type in TWO_SEVENS_TYPES:
            four_helpers = any(
                sum(1 for c in self.hands[d] if c[0] == contract.helper) >= 4 for d in self.defenders
            )
            if contract.type is ContractType.DVE_SEDMY:
                if four_helpers:
                    self._finish(Outcome.FOUR_HELPERS)
                    return
                if missing_seven:
                    self._finish(Outcome.MISSING_SEVEN)
                    return
            elif four_helpers or missing_seven:
                # With a sto on top the hand is played; the sevens are lost regardless.
                self.auto_lost.add(Part.DVE_SEDMY)
        elif contract.type is ContractType.STO_SEDMA and missing_seven:
            self.auto_lost.add(Part.SEDMA)

        self.phase = Phase.PLAY
        self.leader = self.declarer if contract.plain else FORHONT
        self.turn = self.leader
        self.trick = []
        self._log("play_start", leader=self.leader)

    # ------------------------------------------------------------------- play

    def legal_plays(self, player: int) -> list[Card]:
        if self.phase is not Phase.PLAY or self.contract is None:
            return []
        sevens: tuple[Card, ...] = ()
        if player == self.declarer:
            sevens = self.contract.announced_sevens
        return legal_cards(
            self.hands[player],
            self.trick,
            self.contract.trump,
            plain=self.contract.plain,
            announced_sevens=sevens,
        )

    def hlaska_value(self, player: int, card: Card) -> int:
        """Points a marriage would score if ``card`` were played now (0 = none)."""
        if self.contract is None or not self.contract.counts_points:
            return 0
        if card[1] not in ("K", "Q"):
            return 0
        partner = card[0] + ("Q" if card[1] == "K" else "K")
        if partner not in self.hands[player]:
            return 0
        return 40 if card[0] == self.contract.trump else 20

    def play(self, player: int, card: Card, *, announce: bool = True) -> None:
        self._require(Phase.PLAY, player)
        assert self.contract is not None and self.leader is not None
        if not is_card(card) or card not in self.hands[player]:
            raise RuleError("bad_card", "Tuhle kartu nemáš v ruce.")
        if card not in self.legal_plays(player):
            raise RuleError("illegal_card", self._illegal_reason(player, card))

        hlaska = self.hlaska_value(player, card) if announce else 0
        if hlaska:
            self.hlasky[player].append(card[0])
        self.hands[player].remove(card)
        self.trick.append(card)
        self._track_sevens(player, card)
        self._log("play", p=player, card=card, hlaska=hlaska or None)

        if len(self.trick) < 3:
            self.turn = (player + 1) % 3
            return

        winner_index = winning_index(self.trick, self.contract.trump, plain=self.contract.plain)
        winner = (self.leader + winner_index) % 3
        record = TrickRecord(self.leader, tuple(self.trick), winner)
        self.tricks.append(record)
        self._log("trick", winner=winner, n=len(self.tricks))
        self._check_two_sevens_trick(record)
        self.trick = []
        self.leader = winner
        self.turn = winner

        if len(self.tricks) == TRICKS_PER_DEAL or self._decided_early(record):
            self._finish(Outcome.PLAYED)

    def _illegal_reason(self, player: int, card: Card) -> str:
        assert self.contract is not None
        if player == self.declarer and card in self.contract.announced_sevens:
            return "Hlášenou sedmu smíš zahrát až jako poslední kartu své barvy."
        if not self.trick:
            return "Tuhle kartu teď nelze vynést."
        led = self.trick[0][0]
        hand = self.hands[player]
        if card[0] != led and any(c[0] == led for c in hand):
            return "Musíš přiznat barvu."
        if card[0] == led:
            return "Musíš přebít vyšší kartou."
        if self.contract.trump is not None and card[0] != self.contract.trump:
            return "Nemáš barvu, musíš hrát trumf."
        return "Musíš přebít vyšším trumfem."

    def _track_sevens(self, player: int, card: Card) -> None:
        assert self.contract is not None
        if self.contract.type not in TWO_SEVENS_TYPES or player != self.declarer:
            return
        trick_index = len(self.tricks)  # index of the trick being played
        if card == f"{self.contract.trump}7" and trick_index < TRICKS_PER_DEAL - 1:
            self.two_sevens_failed = True
        if card == f"{self.contract.helper}7" and trick_index != TRICKS_PER_DEAL - 2:
            self.two_sevens_failed = True

    def _check_two_sevens_trick(self, record: TrickRecord) -> None:
        assert self.contract is not None and self.declarer is not None
        if self.contract.type not in TWO_SEVENS_TYPES:
            return
        number = len(self.tricks)
        if number == TRICKS_PER_DEAL - 1:
            required = f"{self.contract.helper}7"
        elif number == TRICKS_PER_DEAL:
            required = f"{self.contract.trump}7"
        else:
            return
        if record.winner != self.declarer or record.card_of(self.declarer) != required:
            self.two_sevens_failed = True

    def _decided_early(self, record: TrickRecord) -> bool:
        """Contracts without points end as soon as they are lost."""
        assert self.contract is not None
        ctype = self.contract.type
        if ctype is ContractType.BETL:
            return record.winner == self.declarer
        if ctype is ContractType.DURCH:
            return record.winner != self.declarer
        if ctype is ContractType.DVE_SEDMY:
            return self.two_sevens_failed
        return False

    # ----------------------------------------------------------------- result

    def _finish(self, outcome: Outcome) -> None:
        from .scoring import score_deal  # noqa: PLC0415 - scoring imports this module

        self.outcome = outcome
        self.phase = Phase.DONE
        self.turn = None
        self.result = score_deal(self)
        self._log("done", outcome=outcome.value)

    def trick_points(self, player: int) -> int:
        """Card points in a player's tricks, including the ultimo."""
        points = sum(card_points(c) for t in self.tricks if t.winner == player for c in t.cards)
        if len(self.tricks) == TRICKS_PER_DEAL and self.tricks[-1].winner == player:
            points += 10
        return points

    def hlasky_points(self, player: int) -> list[int]:
        assert self.contract is not None
        return [40 if s == self.contract.trump else 20 for s in self.hlasky[player]]

    # ------------------------------------------------------------------ views

    def options(self, player: int) -> dict[str, Any] | None:
        """What the given player may do right now (``None`` when not on turn)."""
        if self.turn != player or self.phase is Phase.DONE:
            return None
        if self.phase is Phase.BIDDING:
            if self.bid_role == "ask":
                return {
                    "kind": "bid",
                    "role": "ask",
                    "min_level": max(self.bid_level + 1, MIN_LEVEL),
                    "max_level": MAX_LEVEL,
                    "can_bid": self.bid_level < MAX_LEVEL,
                }
            return {"kind": "bid", "role": "answer", "level": self.bid_level}
        if self.phase is Phase.TALON:
            return {
                "kind": "talon",
                "min_level": self.min_level,
                "can_omyl": self.can_omyl,
                "forced": self.forced,
                "talon": list(self.talon),
            }
        if self.phase is Phase.FLEK:
            return {
                "kind": "flek",
                "parts": [p.value for p in self.flek_open],
                "stage": self.flek_stage,
                "name": FLEK_NAMES_CS[self.flek_stage - 1],
            }
        legal = self.legal_plays(player)
        return {
            "kind": "play",
            "cards": legal,
            "hlasky": {c: self.hlaska_value(player, c) for c in legal if self.hlaska_value(player, c)},
        }

    def view(self, player: int | None) -> dict[str, Any]:
        """State visible to ``player`` (``None`` = a spectator)."""
        done = self.phase is Phase.DONE
        view: dict[str, Any] = {
            "phase": self.phase.value,
            "turn": self.turn,
            "hand_counts": [len(h) for h in self.hands],
            "hand": list(self.hands[player]) if player is not None else None,
            "bidding": {
                "level": self.bid_level,
                "asker": self.bid_asker,
                "holder": self.bid_holder,
                "reserve": self.bid_reserve,
                "role": self.bid_role,
                "out": sorted(self.bid_out),
            },
            "declarer": self.declarer,
            "min_level": self.min_level,
            "forced": self.forced,
            "contract": self.contract.to_dict() if self.contract else None,
            "flek": {
                "counts": {p.value: n for p, n in self.flek_counts.items()},
                "stage": self.flek_stage,
                "open": [p.value for p in self.flek_open],
            },
            "leader": self.leader,
            "trick": [{"p": (self.leader + i) % 3, "c": c} for i, c in enumerate(self.trick)]
            if self.leader is not None
            else [],
            "last_trick": self.tricks[-1].to_dict() if self.tricks else None,
            "tricks_won": [sum(1 for t in self.tricks if t.winner == p) for p in PLAYERS],
            "trick_number": len(self.tricks) + (0 if done else 1),
            "hlasky": [list(h) for h in self.hlasky],
            "options": self.options(player) if player is not None else None,
            "result": self.result.to_dict() if done and self.result is not None else None,
        }
        if done:
            view["reveal"] = {
                "initial_hands": [list(h) for h in self.initial_hands],
                "talon": list(self.talon),
                "discards": list(self.discards),
                "play_hands": [list(h) for h in self.play_hands],
                "remaining": [list(h) for h in self.hands],
                "tricks": [t.to_dict() for t in self.tricks],
            }
        return view
