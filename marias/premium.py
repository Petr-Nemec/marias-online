"""Prémiové body (PB) – the ČSM scoring table for licitovaný mariáš, valid from 2014.

PB reward difficult contracts that were announced and won, and successful
fleks on betl and durch.  Every criterion has a value for a declarer *with the
lead* (the declarer is forhont) and *without the lead*.

Rules applied here:

* cards the declarer put into the talon count as if they were still in hand
  (trump and helper counts use all twelve cards);
* several criteria add up, but only the most valuable one is counted at its
  without-lead value, the others at their with-lead value;
* red trumps double the PB;
* no PB for a game that was not won (or a flek that did not succeed).

The betl and durch rows depend on judgement that the paper rules leave to the
players ("catching" cards, "laid-down" suits).  The interpretation used here is
documented in ``docs/PRAVIDLA.md``:

* a *catching card* in a betl is a card with more outstanding lower cards of
  its suit than the declarer holds below it;
* a suit is *laid down* (ložená) in a durch when the declarer cannot lose a
  trick in it even if one defender holds all the outstanding cards.

Cases that need a referee (laid-down or unwinnable hands, revokes) cannot occur
or cannot be judged by software and are not handled.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from .cards import SUITS, Card
from .contracts import ContractType, Part
from .rules import betl_catching_cards, durch_suit_is_solid

if TYPE_CHECKING:
    from .deal import Deal
    from .scoring import DealResult

Criterion = tuple[str, int, int]  # label, with lead, without lead

_SEDMA = {3: (5, 7), 2: (10, 14), 1: (20, 28)}

# trumps -> (both sharp trumps, without the ten, without the ace, without both)
_STO = {
    4: ((0, 10), (10, 12), (12, 16), (18, 24)),
    3: ((16, 20), (20, 24), (24, 32), (36, 48)),
    2: ((32, 40), (40, 48), (48, 64), (72, 96)),
}
_STO_PLAIN_MARRIAGE_BONUS = {4: 8, 3: 16, 2: 32, 1: 64}
_STO_ONE_TRUMP = {"ace": (80, 96), "other": (96, 128)}
_STO_LONG_WITHOUT_SHARPS = (9, 12)  # five or six trumps without both sharp trumps

# trumps -> ((plain), (with announced and won sto), bonus without the trump ace)
_TWO_SEVENS_TRUMPS = {
    4: ((30, 45), (40, 60), 10),
    3: ((60, 90), (80, 120), 20),
    2: ((120, 180), (160, 240), 40),
}
_TWO_SEVENS_HELPERS = ((20, 24), (24, 30))  # four helper cards: plain / with sto


def premium_points(deal: Deal, result: DealResult) -> tuple[dict[int, int], list[dict[str, Any]]]:
    """Return PB per player (deal roles 0-2) and an itemised explanation."""
    from .deal import Outcome  # noqa: PLC0415 - import cycle

    totals: dict[int, int] = {}
    items: list[dict[str, Any]] = []
    if deal.contract is None or deal.declarer is None or deal.outcome is Outcome.OMYL:
        return totals, items

    contract = deal.contract
    declarer = deal.declarer
    won = {p.part: p.won for p in result.parts}
    multiplier = 2 if contract.red else 1

    def award(player: int, label: str, points: int) -> None:
        if points <= 0:
            return
        points *= multiplier
        totals[player] = totals.get(player, 0) + points
        items.append({"player": player, "label": label, "points": points})

    criteria: list[Criterion] = []
    twelve = deal.declarer_twelve
    trumps = [c for c in twelve if c[0] == contract.trump] if contract.trump else []

    if won.get(Part.SEDMA.value) and len(trumps) in _SEDMA:
        with_lead, without_lead = _SEDMA[len(trumps)]
        criteria.append((f"sedma na {_trumps_cs(len(trumps))}", with_lead, without_lead))

    if contract.type in (ContractType.STO, ContractType.STO_SEDMA) and won.get(Part.STO.value):
        criteria.extend(_sto_criteria(deal, trumps))

    if won.get(Part.DVE_SEDMY.value):
        criteria.extend(_two_sevens_criteria(deal, result, trumps, bool(won.get(Part.STO.value))))

    if won.get(Part.BETL.value):
        criteria.extend(_betl_criteria(deal))

    if won.get(Part.DURCH.value):
        criteria.extend(_durch_criteria(deal))

    for label, points in _combine(criteria, with_lead=result.with_lead):
        award(declarer, label, points)

    # Successful fleks on betl and durch.
    if contract.type is ContractType.BETL and won.get(Part.BETL.value) is False:
        for defender in sorted(deal.flekkers):
            suits = {c[0] for c in deal.play_hands[defender]}
            if len(suits) in (2, 3):
                award(defender, f"flek na betl jen se {len(suits)} barvami v ruce", 5)
    if contract.type is ContractType.DURCH and won.get(Part.DURCH.value) is False:
        for defender in sorted(deal.flekkers):
            catching = _durch_catching_suits(deal.play_hands[defender], deal.play_hands[declarer])
            only_aces = len(catching) == 2 and all(is_ace for is_ace in catching.values())
            if 1 <= len(catching) <= 2 and not only_aces:
                award(defender, "flek na durch s chytajícími kartami nejvýše ve dvou barvách", 10)

    return totals, items


def _combine(criteria: Sequence[Criterion], *, with_lead: bool) -> list[tuple[str, int]]:
    """Only the most valuable criterion counts at the without-lead value."""
    if with_lead or not criteria:
        return [(label, a) for label, a, _ in criteria]
    best = max(range(len(criteria)), key=lambda i: criteria[i][2])
    return [
        (f"{label} (bez výnosu)" if i == best else label, b if i == best else a)
        for i, (label, a, b) in enumerate(criteria)
    ]


def _trumps_cs(count: int) -> str:
    return {1: "1 trumf", 2: "2 trumfy", 3: "3 trumfy", 4: "4 trumfy"}.get(count, f"{count} trumfů")


def _sto_criteria(deal: Deal, trumps: Sequence[Card]) -> list[Criterion]:
    assert deal.contract is not None and deal.declarer is not None
    trump = deal.contract.trump
    count = len(trumps)
    has_ace = f"{trump}A" in trumps
    has_ten = f"{trump}X" in trumps
    criteria: list[Criterion] = []

    if count >= 5:
        if count <= 6 and not has_ace and not has_ten:
            criteria.append((f"sto na {count} trumfů bez obou ostrých", *_STO_LONG_WITHOUT_SHARPS))
        return criteria

    if count <= 1:
        key = "ace" if has_ace else "other"
        label = "sto na 1 trumf (eso)" if has_ace else "sto na 1 trumf"
        criteria.append((label, *_STO_ONE_TRUMP[key]))
    else:
        both, no_ten, no_ace, neither = _STO[count]
        if has_ace and has_ten:
            criteria.append((f"sto na {_trumps_cs(count)} s oběma ostrými", *both))
        elif has_ace:
            criteria.append((f"sto na {_trumps_cs(count)} bez trumfové desítky", *no_ten))
        elif has_ten:
            criteria.append((f"sto na {_trumps_cs(count)} bez trumfového esa", *no_ace))
        else:
            criteria.append((f"sto na {_trumps_cs(count)} bez obou ostrých", *neither))

    if trump not in deal.hlasky[deal.declarer]:
        bonus = _STO_PLAIN_MARRIAGE_BONUS[max(count, 1)]
        label = f"příplatek: sto na {_trumps_cs(max(count, 1))} s netrumfovou hláškou"
        criteria.append((label, bonus, bonus))
    return criteria


def _two_sevens_criteria(
    deal: Deal, result: DealResult, trumps: Sequence[Card], with_sto: bool
) -> list[Criterion]:
    assert deal.contract is not None
    contract = deal.contract
    twelve = deal.declarer_twelve
    helpers = [c for c in twelve if c[0] == contract.helper]
    has_trump_ace = f"{contract.trump}A" in trumps
    suffix = " s hlášeným a uhraným stem" if with_sto else ""
    column = 1 if with_sto else 0
    criteria: list[Criterion] = []

    if len(helpers) <= 4:
        criteria.append((f"dvě sedmy na 4 pomocné{suffix}", *_TWO_SEVENS_HELPERS[column]))

    count = max(len(trumps), 2)
    if count in _TWO_SEVENS_TRUMPS:
        plain, sto, bonus = _TWO_SEVENS_TRUMPS[count]
        values = sto if with_sto else plain
        label = f"dvě sedmy na {_trumps_cs(count)}{suffix}"
        if count == 4 and result.with_lead and _strong_two_sevens(twelve, contract.trump, helpers):
            values = (0, values[1])  # footnote 4: nothing for the game with the lead
        criteria.append((label, *values))
        all_helpers = len(helpers) == 8
        if not has_trump_ace:
            # Footnote 5: holding all eight helpers cancels the bonus with the lead.
            criteria.append(
                (f"příplatek: {_trumps_cs(count)} bez trumfového esa", 0 if all_helpers else bonus, bonus)
            )
        if (
            count == 4
            and with_sto
            and not result.with_lead
            and has_trump_ace
            and f"{contract.trump}X" in trumps
        ):
            # Explicit exception: the sto on four trumps with both sharp trumps is
            # credited on top, at its without-lead value.
            criteria.append(("sto na 4 trumfy s oběma ostrými (bez výnosu)", 10, 0))
    return criteria


def _strong_two_sevens(twelve: Sequence[Card], trump: str | None, helpers: Sequence[Card]) -> bool:
    top_trumps = all(f"{trump}{r}" in twelve for r in ("A", "X", "K"))
    helper_suit = helpers[0][0] if helpers else None
    other_aces = all(f"{s}A" in twelve for s in SUITS if s not in (trump, helper_suit))
    return top_trumps and len(helpers) >= 6 and other_aces


def _betl_criteria(deal: Deal) -> list[Criterion]:
    assert deal.declarer is not None
    hand = deal.play_hands[deal.declarer]
    outstanding = _defence_cards(deal)
    first_lead = deal.tricks[0].cards[0] if deal.tricks else None
    criteria: list[Criterion] = []
    for suit in SUITS:
        cards = [c for c in hand if c[0] == suit]
        catching = betl_catching_cards(cards, outstanding)
        if len(cards) >= 6 and len(catching) == 1:
            if catching[0] != first_lead:  # footnote 2: not when it was simply led away
                criteria.append(("betl: šesterák s jednou chytající kartou", 5, 5))
            continue
        if f"{suit}A" in catching:
            criteria.append(("betl: chytající eso", 10, 10))
    return criteria


def _defence_cards(deal: Deal) -> list[Card]:
    """The defenders' cards at the start of play (the talon is out of play)."""
    return [c for d in deal.defenders for c in deal.play_hands[d]]


def _durch_criteria(deal: Deal) -> list[Criterion]:
    assert deal.declarer is not None
    hand = deal.play_hands[deal.declarer]
    defence = _defence_cards(deal)
    criteria: list[Criterion] = []
    for suit in SUITS:
        own = [c for c in hand if c[0] == suit]
        if not own:
            continue
        outstanding = [c for c in defence if c[0] == suit]
        if not durch_suit_is_solid(own, outstanding):
            criteria.append(("durch: barva, která není ložená", 10, 10))
    return criteria


def _durch_catching_suits(defender: Sequence[Card], declarer: Sequence[Card]) -> dict[str, bool]:
    """Suits in which the defender can catch the declarer; value = caught by an ace."""
    catching: dict[str, bool] = {}
    for suit in SUITS:
        mine = [c for c in defender if c[0] == suit]
        theirs = [c for c in declarer if c[0] == suit]
        if mine and theirs and not durch_suit_is_solid(theirs, mine):
            catching[suit] = f"{suit}A" in mine
    return catching
