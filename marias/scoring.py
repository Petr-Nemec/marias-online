"""Settlement of a finished deal.

All amounts are expressed in *units* – multiples of the base stake (0,20 Kč in
competition play).  A positive amount means that every defender (and a pausing
fourth player) pays the declarer; a negative amount means the declarer pays
each of them.

Implemented according to the ČSM general rules and the 2014 competition rules
of licitovaný mariáš:

* rates: hra 1, sedma 2, sto 4, betl 15, durch 30, dvě sedmy 40; red trumps
  double every rate of a trump contract; each flek doubles the part it was
  given on;
* **sto**: when made, the doubled rate is paid once plus once more for every
  10 points above 100 (all the declarer's marriages count); when lost, it is
  paid for every 10 points missing to 100 (only one marriage counts towards
  the 100) and for every 10 points the defence scored in marriages;
* **tiché sto** (in the game of a sedma contract): 100 or more points double
  the game and add the doubled game again for every further 10 points;
* **tichá sedma** (sto contract only): half the sedma rate, never doubled;
  won by taking the last trick with the trump seven, lost only when the seven
  is beaten in the last trick – also by the owner's partner;
* **omyl**: a plain sedma folded without play costs the doubled game and
  doubled sedma (6 units);
* the amount is capped by the limit (500 units), or the raised limit
  (750 units) when both defenders joined the doubling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .contracts import (
    LIMIT_UNITS,
    OMYL_UNITS,
    PART_NAMES_CS,
    RAISED_LIMIT_UNITS,
    RATE_UNITS,
    TICHA_SEDMA_UNITS,
    ContractType,
    Part,
)

if TYPE_CHECKING:
    from .deal import Deal


@dataclass
class PartResult:
    part: str  # Part value, or "ticha_sedma" / "omyl"
    name: str
    won: bool  # from the declarer's point of view
    fleks: int
    units: int  # signed, per defender
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "part": self.part,
            "name": self.name,
            "won": self.won,
            "fleks": self.fleks,
            "units": self.units,
            "note": self.note,
        }


@dataclass
class DealResult:
    outcome: str
    declarer: int
    contract: dict[str, Any] | None
    with_lead: bool
    parts: list[PartResult] = field(default_factory=list)
    declarer_points: int | None = None
    defence_points: int | None = None
    hlasky: list[list[int]] = field(default_factory=lambda: [[], [], []])
    units_raw: int = 0
    units: int = 0
    limit: int = LIMIT_UNITS
    limited: bool = False
    pb: dict[int, int] = field(default_factory=dict)
    pb_items: list[dict[str, Any]] = field(default_factory=list)

    @property
    def declarer_won(self) -> bool:
        """Did the declarer come out ahead financially?"""
        return self.units > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "declarer": self.declarer,
            "contract": self.contract,
            "with_lead": self.with_lead,
            "parts": [p.to_dict() for p in self.parts],
            "declarer_points": self.declarer_points,
            "defence_points": self.defence_points,
            "hlasky": self.hlasky,
            "units_raw": self.units_raw,
            "units": self.units,
            "limit": self.limit,
            "limited": self.limited,
            "pb": {str(k): v for k, v in self.pb.items()},
            "pb_items": self.pb_items,
        }


def score_deal(deal: Deal) -> DealResult:
    """Evaluate a deal that has just ended."""
    from .deal import FORHONT, Outcome  # noqa: PLC0415 - import cycle
    from .premium import premium_points  # noqa: PLC0415 - import cycle

    assert deal.declarer is not None and deal.outcome is not None
    declarer = deal.declarer
    result = DealResult(
        outcome=deal.outcome.value,
        declarer=declarer,
        contract=deal.contract.to_dict() if deal.contract else None,
        with_lead=declarer == FORHONT,
    )

    if deal.outcome is Outcome.OMYL:
        result.parts.append(
            PartResult(
                part="omyl",
                name="omyl",
                won=False,
                fleks=0,
                units=-OMYL_UNITS,
                note="složená sedma: flekovaná hra a flekovaná sedma",
            )
        )
        _total(result, deal)
        return result

    assert deal.contract is not None
    contract = deal.contract
    red = 2 if contract.red else 1
    # A laid-down point game was credited trick by trick, so it scores like a played one.
    played = deal.outcome is Outcome.PLAYED or deal.laid_after is not None

    def rate(part: Part) -> int:
        return RATE_UNITS[part] * red << deal.flek_counts[part]

    def add(part: Part, won: bool, factor: int = 1, note: str = "") -> None:
        units = rate(part) * factor
        result.parts.append(
            PartResult(
                part=part.value,
                name=PART_NAMES_CS[part],
                won=won,
                fleks=deal.flek_counts[part],
                units=units if won else -units,
                note=note,
            )
        )

    defenders = deal.defenders
    if contract.counts_points and played:
        result.hlasky = [deal.hlasky_points(p) for p in range(3)]
        own_marriages = result.hlasky[declarer]
        defence_marriages = [v for d in defenders for v in result.hlasky[d]]
        declarer_cards = deal.trick_points(declarer)
        defence_cards = sum(deal.trick_points(d) for d in defenders)
        result.declarer_points = declarer_cards + sum(own_marriages)
        result.defence_points = defence_cards + sum(defence_marriages)
    else:
        own_marriages = defence_marriages = []
        declarer_cards = 0

    last = deal.tricks[-1] if len(deal.tricks) == 10 else None

    for part in contract.parts:
        if part is Part.HRA:
            if not played:
                # Unplayed sedma: an undoubled game is approved, a doubled game
                # without „re“ is conceded by the declarer.
                conceded = deal.flek_counts[Part.HRA] > 0
                add(part, not conceded, note="vzdaná bez re" if conceded else "schválená")
                continue
            assert result.declarer_points is not None and result.defence_points is not None
            won = result.declarer_points > result.defence_points
            winner_points = max(result.declarer_points, result.defence_points)
            factor, note = 1, f"{result.declarer_points}:{result.defence_points}"
            if winner_points >= 100:
                factor = 2 * (1 + (winner_points - 100) // 10)
                note += f", tiché sto {winner_points}"
            add(part, won, factor, note)

        elif part is Part.SEDMA:
            if not played:
                add(part, True, note="schválená")
            else:
                assert last is not None
                won = last.winner == declarer and last.card_of(declarer) == f"{contract.trump}7"
                add(part, won)

        elif part is Part.STO:
            best = max(own_marriages, default=0)
            counted = declarer_cards + best
            if counted >= 100:
                total = declarer_cards + sum(own_marriages)
                add(part, True, 1 + (total - 100) // 10, f"uhráno {total}")
            else:
                missing = (100 - counted) // 10
                against = sum(defence_marriages) // 10
                note = f"uhráno {counted}"
                if against:
                    note += f", hlášky obrany {sum(defence_marriages)}"
                add(part, False, missing + against, note)

        elif part is Part.BETL:
            note = "ložený" if part in deal.laid_down else ""
            add(part, not any(t.winner == declarer for t in deal.tricks), note=note)

        elif part is Part.DURCH:
            if part in deal.laid_down:
                add(part, True, note="ložený")
            else:
                add(part, len(deal.tricks) == 10 and all(t.winner == declarer for t in deal.tricks))

        elif part is Part.DVE_SEDMY:
            if part in deal.laid_down:
                details = deal.laid_down[part][1]
                if "missing" in details:
                    note = "ložená: aktér nemá obě hlášené sedmy"
                else:
                    note = f"ložená: obránce má {details['theirs']} pomocných, aktér {details['mine']}"
                add(part, False, note=note)
            else:
                add(part, len(deal.tricks) == 10 and not deal.two_sevens_failed)

    if contract.type is ContractType.STO and played and last is not None:
        _silent_seven(deal, result, last, red)

    _total(result, deal)
    pb, items = premium_points(deal, result)
    result.pb = pb
    result.pb_items = items
    return result


def _silent_seven(deal: Deal, result: DealResult, last: Any, red: int) -> None:
    """Tichá sedma in a sto contract (half the sedma rate, never doubled)."""
    assert deal.contract is not None and deal.declarer is not None
    seven = f"{deal.contract.trump}7"
    if seven not in last.cards:
        return
    owner = last.player_of(last.cards.index(seven))
    took = last.winner == owner
    owner_is_declarer = owner == deal.declarer
    # The owner's side collects when the seven wins the last trick and pays when
    # it is beaten there (even by the owner's own partner).
    declarer_gains = took == owner_is_declarer
    units = TICHA_SEDMA_UNITS * red
    if took:
        note = "uhrál aktér" if owner_is_declarer else "uhrála obrana"
    else:
        note = "zabita aktérovi" if owner_is_declarer else "zabita obraně"
    result.parts.append(
        PartResult(
            part="ticha_sedma",
            name="tichá sedma",
            won=declarer_gains,
            fleks=0,
            units=units if declarer_gains else -units,
            note=note,
        )
    )


def _total(result: DealResult, deal: Deal) -> None:
    result.units_raw = sum(p.units for p in result.parts)
    both_doubled = deal.declarer is not None and len(deal.flekkers) == 2
    result.limit = RAISED_LIMIT_UNITS if both_doubled else LIMIT_UNITS
    result.units = max(-result.limit, min(result.limit, result.units_raw))
    result.limited = result.units != result.units_raw
